"""WO-1b offline bounded, immutable two-pass native capture.

python3 -m mve.observer.snapshot_batch --plan mve/observer/config/wo1b_manifest.json --batch 0 --prepare-only
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import time

from mve.observer import snapshot_inventory as inv, snapshots as s, storage
from mve.observer import snapshot_capture as old, snapshot_render as render

from mve.observer import capture_policy as policy, renderer_pin
from mve.observer.capture_evidence import resume_state, snapshot_version

ROOT = inv.ROOT
RECEIPT_ALLOWANCE = 4 * 1024**2


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw):
    if not isinstance(raw, bytes):
        storage.encoded(raw)  # Shared portable-path guard; keep canonical WO-1b bytes.
        raw = inv.encoded(raw)
    storage.disk_guard(ROOT / "mve/generated", len(raw))
    with path.open("xb") as stream:
        stream.write(raw)


def select_jobs(plan, k, *, size=10, pilot=False):
    if type(k) is not int or k < 0 or type(size) is not int or size != 10:
        raise ValueError("invalid bounded batch")
    all_jobs = inv.jobs(plan)
    if pilot:
        if k != 0:
            raise ValueError("pilot is batch zero")
        cid = plan["clusters"][0]["id"]
        return [j for j in all_jobs if j["block"]["cluster"] == cid]
    chosen = all_jobs[k * size : (k + 1) * size]
    if not chosen:
        raise ValueError("batch outside inventory")
    return chosen


def selected_jobs(plan, args):
    if args.drift_from:
        chosen = [
            j for j in inv.jobs(plan) if j["block"]["cluster"] == args.drift_cluster
        ]
        if not chosen or len(chosen) > 10 or args.pilot or args.prepare_only:
            raise ValueError("drift requires one bounded cluster")
        return chosen
    return select_jobs(plan, args.batch, size=args.batch_size, pilot=args.pilot)


def admit(generated, remaining, archive_bytes):
    incoming = remaining * inv.SNAPSHOT_CAP + archive_bytes + RECEIPT_ALLOWANCE
    projected = s.tree_bytes(generated) + incoming
    if projected > 200 * 1024**2:
        raise ValueError("full inventory cannot fit generated cap")
    storage.disk_guard(generated, incoming)
    return dict(
        existing_bytes=s.tree_bytes(generated),
        remaining_snapshots=remaining,
        snapshot_cap=inv.SNAPSHOT_CAP,
        archive_bytes=archive_bytes,
        receipt_allowance=RECEIPT_ALLOWANCE,
        projected_bytes=projected,
        cap_bytes=200 * 1024**2,
    )


def save_pass(folder, number, packet):
    if number not in (0, 1):
        raise ValueError("invalid pass")
    copies = 2 if number == 0 else 1
    base = s.tree_bytes(folder) + 8192
    if number == 0:
        base += len(packet["data"])
    if base + copies * len(packet["blind"]) > inv.SNAPSHOT_CAP:
        raise ValueError("snapshot byte envelope exceeded")
    receipt = dict(
        full_sha256=sha(packet["full"]),
        blind_sha256=sha(packet["blind"]),
        data_sha256=sha(packet["data"]),
        crop=packet["crop"],
        masks=packet["masks"],
        state=packet["state"],
        versions=packet["versions"],
        chunks=s.png_chunks(packet["blind"]),
    )
    # Reserve both passes before writing pass zero. Recheck the actual second
    # PNG/metadata on pass one. 1 KiB covers the fixed leakage report per pass;
    # 8 KiB reserves the difference and completion receipts, including audit.
    storage.encoded(receipt)
    pass_bytes = len(packet["blind"]) + len(inv.encoded(receipt)) + 1024
    projected = base + copies * pass_bytes
    if projected > inv.SNAPSHOT_CAP:
        raise ValueError("snapshot byte envelope exceeded")
    # Full pages are only transient RAM; hash before releasing each packet.
    if number == 0:
        write(folder / "data.json", packet["data"])
    elif (folder / "data.json").read_bytes() != packet["data"]:
        raise ValueError("repeat numeric bytes mismatch")
    write(folder / f"blind-{number}.png", packet["blind"])
    leakage = s.leakage_report(
        folder / f"blind-{number}.png",
        render.WITHHELD,
        executable=shutil.which("tesseract"),
    )
    write(
        folder / f"pass-{number}.json",
        dict(
            **receipt,
            leakage=leakage,
        ),
    )


def finish_snapshot(folder, plan, job, first, second, seconds):
    browser_version = policy.one_version(
        [first["versions"].get("chrome"), second["versions"].get("chrome")]
    )
    repeat = dict(
        tolerance=s.PNG_REPEAT_TOLERANCE,
        data_bytes_equal=first["data"] == second["data"],
    )
    for key in ("full", "blind"):
        repeat[key] = s.compare_png(io.BytesIO(first[key]), io.BytesIO(second[key]))
    repeat["passed"] = repeat["data_bytes_equal"] and all(
        repeat[k]["passed"] for k in ("full", "blind")
    )
    write(folder / "difference.json", repeat)
    if not repeat["passed"]:
        raise ValueError("repeat tolerance failed")
    files = {p.name: s.sha256(p) for p in folder.iterdir() if p.is_file()}
    receipt = inv.seal(
        dict(
            browser_version=browser_version,
            plan_sha256=plan["sha256"],
            snapshot_id=job["snapshot_id"],
            block=job["block"]["id"],
            view=job["view"],
            repeat=repeat,
            files=files,
            seconds=seconds,
            bytes=s.tree_bytes(folder),
        )
    )
    if receipt["bytes"] + len(inv.encoded(receipt)) > inv.SNAPSHOT_CAP:
        raise ValueError("snapshot byte envelope exceeded")
    return receipt


def completed(folder, plan, job):
    if not folder.exists():
        return False
    if (
        folder.is_symlink()
        or any(p.is_symlink() for p in folder.iterdir())
        or not (folder / "complete.json").is_file()
    ):
        raise ValueError("incomplete immutable snapshot; no overwrite/resume")
    r = json.loads((folder / "complete.json").read_text())
    audit = r["source_audit"]
    require_audit(audit)
    verify_artifacts(folder, plan, job, r, final=True)
    snapshot_version(folder, r)
    return True


def require_audit(audit):
    if (
        audit["source_repos_unchanged"] is not True
        or audit["archive_unchanged"] is not True
        or audit["source_audit_before_sha256"] != audit["source_audit_after_sha256"]
    ):
        raise ValueError("source audit required before completion")


def verify_artifacts(folder, plan, job, r, *, final=False):
    if (
        inv.seal(r) != r
        or (r["plan_sha256"], r["snapshot_id"], r["block"], r["view"])
        != (plan["sha256"], job["snapshot_id"], job["block"]["id"], job["view"])
        or not r["repeat"]["passed"]
    ):
        raise ValueError("immutable snapshot identity mismatch")
    if set(p.name for p in folder.iterdir()) != set(r["files"]) | (
        {"complete.json"} if final else set()
    ):
        raise ValueError("immutable artifact set mismatch")
    for name, expected in r["files"].items():
        if s.sha256(s.inside(folder, name)) != expected:
            raise ValueError("immutable artifact digest mismatch")
    if s.sha256(folder / "data.json") != job["block"]["data_sha256"]:
        raise ValueError("immutable numeric mismatch")


def accept_snapshot(folder, plan, job, candidate, audit):
    require_audit(audit)
    verify_artifacts(folder, plan, job, candidate)
    snapshot_version(folder, candidate)
    receipt = inv.seal({**candidate, "source_audit": audit})
    if s.tree_bytes(folder) + len(inv.encoded(receipt)) > inv.SNAPSHOT_CAP:
        raise ValueError("snapshot byte envelope exceeded")
    write(folder / "complete.json", receipt)
    return receipt


def archive_size(repos):
    """Read only pinned allowlisted git trees; include extraction directory slack."""
    import subprocess

    total = 0
    for name, repo in repos.items():
        raw = subprocess.check_output(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(repo),
                "ls-tree",
                "-rl",
                s.COMMITS[name],
                "--",
                *s.PATHS[name],
            ]
        )
        for line in raw.decode().splitlines():
            parts = line.split()
            if parts[1] != "blob" or parts[0] not in ("100644", "100755"):
                raise ValueError("unsupported archive entry")
            total += int(parts[3])
    return total + 1024**2


def archive_repo(repo, name, dest, generated):
    """WO-1b admission before WO-1's bounded, allowlisted extraction.

    The extractor enforces a 64 MiB maximum, so reserving that whole bound with
    storage's 200 MiB/5 GiB guard covers every extraction write under our lock.
    WO-1's pinned guard and archive semantics remain unchanged.
    """
    storage.disk_guard(generated, 64 * 1024**2)
    s.archive_repo(repo, name, dest, generated)


def check_stage(stage):
    old.check_sources(stage)
    dist = stage / "atlas/vendor/zeta-explorer/dist"
    hashes = {}
    for name in render.BLOCK_PATCHES:
        raw = (dist / name).read_text()
        changed = render.block_transform(name, render.transform(name, raw))
        hashes[name] = {
            "source_sha256": sha(raw.encode()),
            "response_sha256": sha(changed.encode()),
        }
    return hashes


def worker(args, out):
    if os.environ.get("MVE_WO1_SANDBOX_WORKER") != "1":
        raise ValueError("worker requires sandboxed parent")
    private = Path(os.environ["MVE_WO1_PRIVATE_DIR"])
    old.private_paths(private)
    plan = inv.load(args.plan)
    chosen = selected_jobs(plan, args)
    snapshots = out.parent / "snapshots"
    chosen = [j for j in chosen if not completed(snapshots / j["snapshot_id"], plan, j)]
    for job in chosen:
        job["raw"] = inv.block_data(plan, job["block"], args.cache, purpose="capture")
        (snapshots / job["snapshot_id"]).mkdir()
    packets = []
    began = time.monotonic()
    for number in (0, 1):
        pass_dir = out / f"runtime-pass-{number}"

        # Browser profile is under the private runtime, pass dir is only a name.
        def capture(context, root, job, versions, ocr):
            started = time.monotonic()
            with policy.deadline(args.page_load_timeout + policy.POST_LOAD_SECONDS):
                packet = render.capture_block(
                    context,
                    root,
                    job,
                    versions,
                    ocr,
                    page_load_timeout=args.page_load_timeout,
                )
                save_pass(snapshots / job["snapshot_id"], number, packet)
            packet["seconds"] = time.monotonic() - started
            return packet

        def expired(signum, frame):
            raise policy.PageTimeoutError("batch pass timeout")

        previous = signal.signal(signal.SIGALRM, expired)
        try:
            signal.setitimer(signal.ITIMER_REAL, args.timeout_per_pass)
            if args.renderer_pin:
                renderer_pin.verify(args.chrome, args.renderer_pin)
            packets.append(
                render.run_browser(
                    out / "stage/atlas/vendor/zeta-explorer/dist",
                    pass_dir,
                    args.chrome,
                    shutil.which("tesseract"),
                    private,
                    jobs=chosen,
                    capture=capture,
                )
            )
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    browser_version = policy.one_version(
        p["versions"].get("chrome")
        for packets_in_pass in packets
        for p in packets_in_pass
    )
    elapsed = time.monotonic() - began
    receipts = [
        finish_snapshot(
            snapshots / j["snapshot_id"], plan, j, a, b, a["seconds"] + b["seconds"]
        )
        for j, a, b in zip(chosen, *packets)
    ]
    write(
        out / "capture.json",
        dict(
            browser_version=browser_version,
            snapshots=len(receipts),
            seconds=elapsed,
            seconds_per_snapshot=elapsed / max(1, len(receipts)),
            bytes=sum(s.tree_bytes(snapshots / j["snapshot_id"]) for j in chosen),
            candidates=receipts,
            hosted_calls=0,
            pilot=args.pilot,
        ),
    )
    return 0


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--batch", type=int, required=True)
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--prepare-only", action="store_true")
    p.add_argument("--cache", type=Path, default=inv.data.CACHE)
    p.add_argument("--atlas", default=old.DEFAULT_REPOS["atlas"])
    p.add_argument("--lab", default=old.DEFAULT_REPOS["lab"])
    p.add_argument(
        "--chrome",
        default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--output", help=argparse.SUPPRESS)
    policy.options(p)
    p.add_argument("--drift-from", type=Path)
    p.add_argument("--drift-output", type=Path)
    p.add_argument("--drift-cluster")
    args = p.parse_args(argv)
    try:
        policy.bounds(args, 10)
    except ValueError as exc:
        p.error(str(exc))
    return args


def run(args):
    plan = inv.load(args.plan)
    chosen = selected_jobs(plan, args)
    cache = inv.data.verify_cache(args.cache)
    if cache != plan["cache"]:
        raise ValueError("cache provenance drift")
    base = storage.local(Path("mve/generated") / ("wo1b-" + plan["sha256"][:16]))
    if bool(args.drift_from) != bool(args.drift_output):
        raise ValueError("both drift paths required")
    if args.drift_from:
        from mve.observer import renderer_drift

        args.drift_from = args.drift_from.expanduser().resolve()
        renderer_drift.accepted_cluster(args.drift_from, plan, chosen)
        base = storage.local(args.drift_output)
        if (
            base == args.drift_from
            or base.is_relative_to(args.drift_from)
            or args.drift_from.is_relative_to(base)
        ):
            raise ValueError("drift output overlaps accepted evidence")
        if not args.worker and base.exists():
            raise ValueError("immutable drift output exists")
    if args.worker:
        out = old.output_path(ROOT, args.output)
        args.attempt_path = out
        if out.parent != base:
            raise ValueError("worker output identity mismatch")
        return worker(args, out)
    load_start = policy.load(args.max_load)
    # Native pin checks precede even the lock's directory creation. Resume and
    # version checks are repeated under lock before selecting an attempt.
    pre_state = resume_state(base, plan)
    pending = {j["snapshot_id"] for j in pre_state["remaining"]}
    version_start = (
        renderer_pin.preflight(args.chrome, args.renderer_pin)
        if not args.prepare_only and any(j["snapshot_id"] in pending for j in chosen)
        else None
    )
    for j in chosen:
        prior = pre_state["cluster_versions"].get(j["block"]["cluster"])
        if (
            prior
            and version_start
            and j["snapshot_id"] in pending
            and not args.drift_from
        ):
            policy.one_version([prior, version_start])
    with storage.lock():
        if args.drift_from and base.exists():
            raise ValueError("immutable drift output exists")
        snapshots = storage.local(base.relative_to(ROOT) / "snapshots")
        state = resume_state(base, plan)
        remaining = chosen if args.drift_from else state["remaining"]
        chosen = [
            j
            for j in chosen
            if j["snapshot_id"] in {r["snapshot_id"] for r in remaining}
        ]
        if chosen and not args.prepare_only and version_start is None:
            raise policy.RendererVersionError("selection changed; rerun preflight")
        repos = {
            name: Path(getattr(args, name)).expanduser().resolve() for name in s.COMMITS
        }
        projected = admit(ROOT / "mve/generated", len(remaining), archive_size(repos))
        for j in chosen:
            prior = state["cluster_versions"].get(j["block"]["cluster"])
            if prior and version_start:
                policy.one_version([prior, version_start])
        snapshots.mkdir(parents=True, exist_ok=True)
        prefix = f'{"pilot" if args.pilot else "batch"}-{args.batch:03d}-'
        attempt = len(list(base.glob(prefix + "*")))
        out = base / (prefix + f"{attempt:03d}")
        out.mkdir()
        args.attempt_path = out
        before = s.isolation_state(repos)
        write(out / "admission.json", projected)
        stage = out / "stage"
        archive_before = None
        receipt = dict(
            load_start=load_start,
            browser_version_start=version_start,
            renderer_pin=args.renderer_pin,
            browser_version=None,
            bounds=policy.bounds(args, 10),
            quarantine=state["quarantine"],
            plan_sha256=plan["sha256"],
            batch=args.batch,
            mode="offline",
            hosted_calls=0,
            selected=[j["snapshot_id"] for j in chosen],
            status="failed",
        )
        try:
            for name, repo in repos.items():
                archive_repo(repo, name, stage / name, ROOT / "mve/generated")
            write(out / "sources.json", check_stage(stage))
            archive_before = s.tree_listing(stage)
            for j in chosen:
                inv.block_data(plan, j["block"], args.cache, purpose="capture")
            if args.prepare_only:
                receipt["status"] = "prepared_only"
            elif not chosen:
                receipt["status"] = "already_complete"
            else:
                # Old parent supplies OS network/write denial, fresh runtime,
                # process-group cleanup and a bounded log. This packet supplies its
                # derived overall ceiling, leaving the original WO-1 default intact.
                args.worker_module = "mve.observer.snapshot_batch"
                args.worker_args = [
                    "--plan",
                    str(args.plan.resolve()),
                    "--batch",
                    str(args.batch),
                    "--batch-size",
                    str(args.batch_size),
                    "--cache",
                    str(args.cache.expanduser().resolve()),
                ]
                args.worker_args += ["--page-load-timeout", str(args.page_load_timeout)]
                if args.renderer_pin:
                    args.worker_args += ["--renderer-pin", args.renderer_pin]
                if args.drift_from:
                    args.worker_args += [
                        "--drift-from",
                        str(args.drift_from),
                        "--drift-output",
                        str(args.drift_output),
                        "--drift-cluster",
                        args.drift_cluster,
                    ]
                if args.pilot:
                    args.worker_args.append("--pilot")
                args.repeat = False
                args.output = str(out.relative_to(ROOT))
                # Allow snapshots and this attempt, but never lab/atlas writes.
                args.sandbox_output = base
                args.log_limit = 65536
                try:
                    old.isolated_capture(args, out, repos, receipt)
                except Exception as exc:
                    policy.relay_worker_refusal(out, exc)
                capture = json.loads((out / "capture.json").read_text())
                receipt["browser_version"] = policy.one_version(
                    [version_start, capture["browser_version"]]
                    + [r["browser_version"] for r in capture["candidates"]]
                )
                receipt["status"] = "captured"
        finally:
            receipt["load_end"] = policy.load()
            policy.end_version(receipt, args.chrome, version_start)
            if args.renderer_pin and version_start is not None:
                try:
                    renderer_pin.verify(args.chrome, args.renderer_pin)
                except policy.RendererPinError:
                    receipt["status"] = "renderer_pin"
            after = s.isolation_state(repos)
            receipt["source_repos_unchanged"] = before == after
            receipt["source_audit_before_sha256"] = s.digest(before)
            receipt["source_audit_after_sha256"] = s.digest(after)
            receipt["archive_unchanged"] = (
                archive_before is None or archive_before == s.tree_listing(stage)
            )
            # Only disposable copies from this attempt, never immutable evidence.
            if stage.exists():
                shutil.rmtree(stage)
            receipt["generated_bytes"] = s.tree_bytes(ROOT / "mve/generated")
            write(out / "receipt.json", receipt)
            if (
                not receipt["source_repos_unchanged"]
                or not receipt["archive_unchanged"]
            ):
                raise ValueError("source drift")
        if receipt["status"] == "renderer_pin":
            raise policy.RendererPinError("renderer bundle changed during batch")
        if receipt["status"] == "renderer_drift":
            raise policy.RendererVersionError("renderer version changed during batch")
        if receipt["status"] == "captured":
            capture = json.loads((out / "capture.json").read_text())
            candidates = capture["candidates"]
            if [r["snapshot_id"] for r in candidates] != [
                j["snapshot_id"] for j in chosen
            ]:
                raise ValueError("missing completed snapshot")
            audit = {
                k: receipt[k]
                for k in (
                    "source_repos_unchanged",
                    "archive_unchanged",
                    "source_audit_before_sha256",
                    "source_audit_after_sha256",
                )
            }
            for j, candidate in zip(chosen, candidates):
                accept_snapshot(snapshots / j["snapshot_id"], plan, j, candidate, audit)
            write(
                out / "accepted.json",
                dict(
                    browser_version=receipt["browser_version"],
                    snapshots=len(chosen),
                    bytes=sum(
                        s.tree_bytes(snapshots / j["snapshot_id"]) for j in chosen
                    ),
                    generated_bytes=s.tree_bytes(ROOT / "mve/generated"),
                    seconds=capture["seconds"],
                    seconds_per_snapshot=capture["seconds_per_snapshot"],
                ),
            )
        if args.drift_from and receipt["status"] == "captured":
            drift = renderer_drift.compare(args.drift_from, base, plan, chosen)
            write(out / "drift.json", drift)
            if not drift["passed"]:
                raise ValueError("renderer drift exceeds WO-1 tolerance")
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "receipt": str((out / "receipt.json").relative_to(ROOT)),
                }
            )
        )
        return 0


def main(argv=None):
    args = parse_args(argv)
    try:
        return run(args)
    except Exception as exc:
        # No local paths, inherited environment or exception text in stdout.
        policy.write_traceback(getattr(args, "attempt_path", None), exc)
        if args.worker:
            policy.write_worker_refusal(getattr(args, "attempt_path", None), exc)
        print("WO-1b refused: " + getattr(exc, "label", "internal_error"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
