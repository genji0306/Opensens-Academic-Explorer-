"""WO-6c capture preparation; Opus alone runs the native browser outside sandbox.

Reuses WO-1's archive, isolation, native injection and repeat path. No WO-1b
inventory loader, block generator, cache or prospective artifact is accessed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time
from mve.observer import development_c as dev, storage, snapshots as s
from mve.observer import snapshot_capture as old, snapshot_render as render
from mve.observer import snapshot_batch as batch, render_c
from mve.observer.snapshot_inventory import seal
from mve.observer import capture_policy as policy, renderer_pin
from mve.observer.refusals import Parser

ROOT = dev.ROOT
BASE = Path("mve/generated/wo6c-pilot/captures")


def capture_data(module, source):
    data = dev.data(dict(module=module, sealed={"A": source}), "A")
    if module not in dev.ZERO:
        data["extent"] = 30000 if module == "polar-ulam" else 100000
    return dev.encoded(data)


def plan():
    r = dev.load()
    jobs = []
    for module in dev.MODULES:
        for source in ("real", "null", "new-0", "new-1"):
            raw = capture_data(module, source)
            ident = digest_id(module, source)
            block = dict(
                id=ident,
                module=module,
                data_sha256=hashlib.sha256(raw).hexdigest(),
                role="development",
                crop=dict(
                    selector=s.MODULES[module]["selector"],
                    resize=[
                        640,
                        {
                            "spectral": 221,
                            "field-dyson": 187,
                            "polar-ulam": 348,
                            "space-08": 270,
                        }[module],
                    ],
                ),
                camera=dict(views=[dict(viewport=[1440, 1100])]),
            )
            jobs.append(
                dict(
                    snapshot_id=ident, module=module, source=source, block=block, view=0
                )
            )
    return seal(
        dict(
            schema="mve-wo6c-capture-v1",
            development_sha256=r["sha256"],
            jobs=jobs,
            source_commits=s.COMMITS,
            source_pathspecs={k: list(v) for k, v in s.PATHS.items()},
            runtime_sha256={
                name: hashlib.sha256(
                    (dev.ROOT / "mve/observer" / name).read_bytes()
                ).hexdigest()
                for name in (
                    "capture_policy.py",
                    "capture_evidence.py",
                    "capture_c.py",
                    "render_c.py",
                    "snapshot_render.py",
                    "snapshot_capture.py",
                    "snapshot_batch.py",
                    "snapshots.py",
                    "development_c.py",
                )
            },
        )
    )


def digest_id(module, source):
    return s.digest(["wo6c", module, source, dev.ORDER_SEED])[:24]


def image(job, side):
    p = plan()
    ident = digest_id(job["module"], job["sealed"][side])
    j = next(j for j in p["jobs"] if j["snapshot_id"] == ident)
    folder = storage.local(BASE / "snapshots" / ident)
    if not batch.completed(folder, p, j):
        raise ValueError("native development capture required")
    return render_c.crop(job["module"], (folder / "blind-0.png").read_bytes())


def check_stage(stage):
    dist = stage / "atlas/vendor/zeta-explorer/dist"
    hashes = {}
    for name in set(render.PATCHES) | set(render_c.PATCHES):
        raw = (dist / name).read_text()
        transformed = render_c.transform(name, raw)
        hashes[name] = dict(
            source_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            response_sha256=hashlib.sha256(transformed.encode()).hexdigest(),
        )
    return hashes


def worker(args, out, p, jobs):
    if os.environ.get("MVE_WO1_SANDBOX_WORKER") != "1":
        raise ValueError("isolated parent required")
    private = Path(os.environ["MVE_WO1_PRIVATE_DIR"])
    old.private_paths(private)
    snapshots = storage.local(BASE / "snapshots")
    dist = out / "stage/atlas/vendor/zeta-explorer/dist"
    for j in jobs:
        j["raw"] = capture_data(j["module"], j["source"])
        (snapshots / j["snapshot_id"]).mkdir()
    packets = []
    began = time.monotonic()
    for number in (0, 1):

        def capture(context, root, j, versions, ocr):
            context.route("**/*", render_c.handler(dist))
            with policy.deadline(args.page_load_timeout + policy.POST_LOAD_SECONDS):
                packet = render.capture_block(
                    context,
                    root,
                    j,
                    versions,
                    ocr,
                    page_load_timeout=args.page_load_timeout,
                )
                batch.save_pass(snapshots / j["snapshot_id"], number, packet)
            return packet

        def expired(signum, frame):
            raise ValueError("capture pass timeout")

        previous = signal.signal(signal.SIGALRM, expired)
        try:
            signal.setitimer(signal.ITIMER_REAL, args.timeout_per_pass)
            packets.append(
                render.run_browser(
                    dist,
                    out / f"pass-{number}",
                    args.chrome,
                    shutil.which("tesseract"),
                    private,
                    jobs=jobs,
                    capture=capture,
                )
            )
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    browser_version = policy.one_version(
        packet["versions"].get("chrome") for part in packets for packet in part
    )
    candidates = [
        batch.finish_snapshot(snapshots / j["snapshot_id"], p, j, a, b, 0)
        for j, a, b in zip(jobs, *packets)
    ]
    batch.write(
        out / "capture.json",
        dict(
            browser_version=browser_version,
            candidates=candidates,
            seconds=time.monotonic() - began,
        ),
    )
    return 0


def run(args):
    p = plan()
    if args.batch not in range(4):
        raise ValueError("batch must be 0..3")
    jobs = p["jobs"][4 * args.batch : 4 * args.batch + 4]
    base = storage.local(BASE)
    out = base / ("prepare" if args.prepare_only else "native") / str(args.batch)
    if args.worker:
        if args.output != str(out.relative_to(ROOT)):
            raise ValueError("worker output mismatch")
        return worker(args, out, p, jobs)
    load_start = policy.load(args.max_load)
    limits = policy.bounds(args, 4)
    version_start = (
        renderer_pin.preflight(args.chrome, args.renderer_pin)
        if not args.prepare_only
        else None
    )
    with storage.lock():
        if out.exists():
            raise ValueError("immutable capture attempt exists")
        snapshots = base / "snapshots"
        for j in jobs:
            if (snapshots / j["snapshot_id"]).exists():
                raise ValueError("immutable snapshot exists")
        storage.disk_guard(storage.local(storage.GENERATED), 80 * 1024**2)
        out.mkdir(parents=True)
        snapshots.mkdir(exist_ok=True)
        repos = {k: Path(getattr(args, k)).expanduser().resolve() for k in s.COMMITS}
        before = s.isolation_state(repos)
        stage = out / "stage"
        archive_before = None
        receipt = dict(
            status="failed",
            hosted_calls=0,
            plan_sha256=p["sha256"],
            load_start=load_start,
            bounds=limits,
            browser_version=None,
            browser_version_start=version_start,
            renderer_pin=args.renderer_pin,
        )
        try:
            for name, repo in repos.items():
                batch.archive_repo(
                    repo, name, stage / name, storage.local(storage.GENERATED)
                )
            batch.write(out / "sources.json", check_stage(stage))
            archive_before = s.tree_listing(stage)
            batch.write(out / "plan.json", p)
            if args.prepare_only:
                receipt["status"] = "prepared_only"
            else:
                args.worker_module = "mve.observer.capture_c"
                args.worker_args = [
                    "--batch",
                    str(args.batch),
                    "--page-load-timeout",
                    str(args.page_load_timeout),
                ]
                if args.renderer_pin:
                    args.worker_args += ["--renderer-pin", args.renderer_pin]
                args.output = str(out.relative_to(ROOT))
                args.repeat = False
                args.sandbox_output = base
                args.log_limit = 65536
                old.isolated_capture(args, out, repos, receipt)
                captured = json.loads((out / "capture.json").read_text())
                receipt["browser_version"] = policy.one_version(
                    [version_start, captured["browser_version"]]
                    + [r["browser_version"] for r in captured["candidates"]]
                )
                receipt["status"] = "captured"
        finally:
            receipt["load_end"] = policy.load()
            policy.end_version(receipt, args.chrome, version_start)
            after = s.isolation_state(repos)
            receipt.update(
                source_repos_unchanged=before == after,
                source_audit_before_sha256=s.digest(before),
                source_audit_after_sha256=s.digest(after),
                archive_unchanged=archive_before is None
                or archive_before == s.tree_listing(stage),
            )
            if stage.exists():
                shutil.rmtree(stage)
            batch.write(out / "receipt.json", receipt)
            batch.require_audit(receipt)
        if receipt["status"] == "renderer_drift":
            raise policy.RendererVersionError("renderer version changed during batch")
        if receipt["status"] == "captured":
            candidates = json.loads((out / "capture.json").read_text())["candidates"]
            if len(candidates) != len(jobs):
                raise ValueError("missing capture candidates")
            for j, r in zip(jobs, candidates):
                batch.accept_snapshot(snapshots / j["snapshot_id"], p, j, r, receipt)
        print(
            json.dumps(
                dict(status=receipt["status"], snapshots=len(jobs), hosted_calls=0)
            )
        )
        return 0


def main(argv=None):
    p = Parser(description=__doc__)
    p.add_argument("--batch", type=int, required=True)
    p.add_argument("--prepare-only", action="store_true")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--output", help=argparse.SUPPRESS)
    policy.options(p)
    for key, value in old.DEFAULT_REPOS.items():
        p.add_argument("--" + key, default=value)
    p.add_argument(
        "--chrome",
        default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    a = p.parse_args(argv)
    try:
        policy.bounds(a, 4)
        return run(a)
    except Exception as exc:
        print("WO-6 refused: " + getattr(exc, "label", "source_pin"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
