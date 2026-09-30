"""Write-ahead quarantine of one superseded WO-6c capture plan."""

import argparse
import json
import os
from pathlib import Path

from mve.observer import capture_c, snapshot_inventory as inv, snapshots as s, storage

SCHEMA = "mve-wo6c-plan-quarantine-v1"
FAILED_SCHEMA = "mve-wo6c-failed-attempt-quarantine-v1"
ATTEMPTS = {"0", "1", "2", "3"}


def expected_snapshots(native, plan_sha256):
    """Recover the complete superseded set from all four sealed plan copies."""
    if (
        native.is_symlink()
        or not native.is_dir()
        or {p.name for p in native.iterdir()} != ATTEMPTS
    ):
        raise ValueError("complete native attempt set required")
    expected = None
    for number in sorted(ATTEMPTS):
        attempt = native / number
        if attempt.is_symlink() or not attempt.is_dir():
            raise ValueError("native attempt must be a plain directory")
        plan = json.loads((attempt / "plan.json").read_text())
        receipt = json.loads((attempt / "receipt.json").read_text())
        if (
            inv.seal(plan) != plan
            or plan.get("schema") != "mve-wo6c-capture-v1"
            or plan.get("sha256") != plan_sha256
            or receipt.get("plan_sha256") != plan_sha256
        ):
            raise ValueError("superseded plan and receipt mismatch")
        jobs = plan.get("jobs")
        if not isinstance(jobs, list) or len(jobs) != 16:
            raise ValueError("complete superseded plan required")
        ids = [j["snapshot_id"] for j in jobs]
        if len(set(ids)) != 16 or any(
            not isinstance(ident, str)
            or len(ident) != 24
            or any(c not in "0123456789abcdef" for c in ident)
            for ident in ids
        ):
            raise ValueError("invalid superseded snapshot identities")
        expected = set(ids)
    return expected


def inventory(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError("quarantine source must be a plain directory")
    files = {}
    directories = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("symlink in quarantine evidence")
        rel = item.relative_to(path).as_posix()
        if item.is_dir():
            directories.append(rel)
        elif item.is_file():
            files[rel] = s.sha256(item)
        else:
            raise ValueError("unsupported quarantine artifact")
    return dict(files=files, directories=directories)


def current_attempt_plan(attempt):
    """Return a current sealed plan only when its receipt agrees."""
    plan_file = attempt / "plan.json"
    receipt_file = attempt / "receipt.json"
    if plan_file.is_symlink() or receipt_file.is_symlink():
        raise ValueError("symlink active provenance")
    if not plan_file.is_file() or not receipt_file.is_file():
        return None
    plan = json.loads(plan_file.read_text())
    receipt = json.loads(receipt_file.read_text())
    if (
        inv.seal(plan) == plan
        and plan.get("schema") == "mve-wo6c-capture-v1"
        and plan.get("sha256") == capture_c.plan()["sha256"]
        and receipt.get("plan_sha256") == plan["sha256"]
    ):
        return plan
    return None


def recapture_claim(base, ident, old_plan_sha256, old_inventory=None):
    native = base / "native"
    if native.is_symlink():
        raise ValueError("symlink native root")
    if native.is_dir():
        for attempt in native.iterdir():
            if attempt.is_symlink() or not attempt.is_dir():
                raise ValueError("invalid active attempt")
            if attempt.name not in ATTEMPTS:
                continue
            plan = current_attempt_plan(attempt)
            if plan is None or plan["sha256"] == old_plan_sha256:
                continue
            jobs = plan.get("jobs")
            if not isinstance(jobs, list) or len(jobs) != 16:
                continue
            number = int(attempt.name)
            if ident in {
                job.get("snapshot_id") for job in jobs[4 * number : 4 * number + 4]
            }:
                if old_inventory is not None:
                    active_files = inventory(base / "snapshots" / ident)["files"]
                    old_files = old_inventory["files"]
                    if not active_files and not old_files:
                        continue
                    if set(active_files.values()) & set(old_files.values()):
                        continue
                return True
    return False


def active_is_superseded(base, move, plan_sha256):
    """IDs are data-derived; only matching evidence provenance is superseded."""
    source = Path(move["source"])
    active = base / source
    if not active.exists() and not active.is_symlink():
        return False
    if active.is_symlink() or not active.is_dir():
        raise ValueError("invalid active evidence")
    marker = active / (
        "receipt.json" if source.parts[0] == "native" else "complete.json"
    )
    if source.parts[0] == "native":
        plan_file = active / "plan.json"
        receipt_file = active / "receipt.json"
        if plan_file.is_symlink() or receipt_file.is_symlink():
            raise ValueError("symlink active provenance")
        if plan_file.is_file() and receipt_file.is_file():
            plan = json.loads(plan_file.read_text())
            receipt = json.loads(receipt_file.read_text())
            if (
                inv.seal(plan) == plan
                and plan.get("sha256") == plan_sha256
                and receipt.get("plan_sha256") == plan_sha256
            ):
                return True
        if current_attempt_plan(active) is not None:
            return False
        raise ValueError("unidentified active attempt")
    if marker.is_file():
        sha = json.loads(marker.read_text()).get("plan_sha256")
        if sha == plan_sha256:
            return True
        if sha != capture_c.plan()["sha256"]:
            raise ValueError("unidentified active snapshot")
    # An unfinished snapshot requires a current-plan batch claim and fresh bytes.
    if recapture_claim(base, source.parts[1], plan_sha256, move["inventory"]):
        return False
    if inventory(active) == move["inventory"]:
        return True
    raise ValueError("unidentified active snapshot")


def verify_failed(base, record):
    if inv.seal(record) != record or record.get("schema") != FAILED_SCHEMA:
        raise ValueError("failed attempt record mismatch")
    if not isinstance(record.get("reason"), str) or not record["reason"].strip():
        raise ValueError("failed attempt reason required")
    name = storage.token(record["name"])
    number = record["attempt"]
    if number not in ATTEMPTS:
        raise ValueError("invalid failed attempt number")
    folder = base / "quarantine" / name
    if (
        folder.is_symlink()
        or not folder.is_dir()
        or {p.name for p in folder.iterdir()}
        != {"QUARANTINE.json", "native", "snapshots"}
    ):
        raise ValueError("failed attempt quarantine root mismatch")
    attempt = folder / "native" / number
    plan = json.loads((attempt / "plan.json").read_text())
    receipt = json.loads((attempt / "receipt.json").read_text())
    if (
        inv.seal(plan) != plan
        or plan.get("schema") != "mve-wo6c-capture-v1"
        or len(plan.get("jobs", [])) != 16
        or receipt.get("status") != "failed"
        or receipt.get("plan_sha256") != plan.get("sha256")
        or record.get("attempt_plan_sha256") != plan.get("sha256")
    ):
        raise ValueError("failed attempt provenance mismatch")
    ids = {
        j["snapshot_id"] for j in plan["jobs"][4 * int(number) : 4 * int(number) + 4]
    }
    if len(ids) != 4:
        raise ValueError("failed attempt batch incomplete")
    sources = {m["source"] for m in record["moves"]}
    if len(sources) != len(record["moves"]) or f"native/{number}" not in sources:
        raise ValueError("failed attempt moves incomplete")
    if any(
        src != f"native/{number}" and src not in {f"snapshots/{i}" for i in ids}
        for src in sources
    ):
        raise ValueError("failed attempt snapshot selection mismatch")
    for move in record["moves"]:
        source = Path(move["source"])
        if Path(move["dest"]) != Path("quarantine") / name / source:
            raise ValueError("failed attempt path mismatch")
        if inventory(base / move["dest"]) != move["inventory"]:
            raise ValueError("failed attempt artifact digest mismatch")
        if active_is_superseded(base, move, plan["sha256"]):
            raise ValueError("failed attempt evidence still active")
    if {p.name for p in (folder / "native").iterdir()} != {number} or {
        p.name for p in (folder / "snapshots").iterdir()
    } != {Path(src).name for src in sources if src.startswith("snapshots/")}:
        raise ValueError("failed attempt artifact set mismatch")
    for ident in ids - {
        Path(src).name for src in sources if src.startswith("snapshots/")
    }:
        active = base / "snapshots" / ident
        if active.is_symlink():
            raise ValueError("symlink active snapshot")
        if active.exists():
            if recapture_claim(base, ident, plan["sha256"]):
                continue
            raise ValueError("unrecorded failed attempt snapshot")
    return dict(
        name=name,
        plan_sha256=plan["sha256"],
        record_sha256=s.sha256(folder / "QUARANTINE.json"),
        moves=len(sources),
    )


def verify(base, record):
    if record.get("schema") == FAILED_SCHEMA:
        return verify_failed(base, record)
    if inv.seal(record) != record:
        raise ValueError("quarantine record hash mismatch")
    if record.get("schema") != SCHEMA or not record.get("reason"):
        raise ValueError("quarantine identity mismatch")
    if (
        not isinstance(record.get("superseded_plan_sha256"), str)
        or len(record["superseded_plan_sha256"]) != 64
    ):
        raise ValueError("superseded plan hash required")
    folder = base / "quarantine" / storage.token(record["name"])
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("quarantine missing")
    if set(p.name for p in folder.iterdir()) != {
        "QUARANTINE.json",
        "native",
        "snapshots",
    }:
        raise ValueError("quarantine root artifact set mismatch")
    expected_ids = expected_snapshots(
        folder / "native", record["superseded_plan_sha256"]
    )
    required = {"native": ATTEMPTS, "snapshots": expected_ids}
    expected = {"native": set(), "snapshots": set()}
    if len({move["source"] for move in record["moves"]}) != len(record["moves"]):
        raise ValueError("duplicate quarantine source")
    for move in record["moves"]:
        source = Path(move["source"])
        dest = Path(move["dest"])
        if (
            len(source.parts) != 2
            or source.parts[0] not in expected
            or dest != Path("quarantine") / record["name"] / source
        ):
            raise ValueError("quarantine path mismatch")
        expected[source.parts[0]].add(source.parts[1])
        if active_is_superseded(base, move, record["superseded_plan_sha256"]):
            raise ValueError("superseded evidence still active")
        if inventory(base / dest) != move["inventory"]:
            raise ValueError("quarantine artifact digest mismatch")
    if expected != required:
        raise ValueError("quarantine record lacks complete expected set")
    for kind, names in expected.items():
        if set(p.name for p in (folder / kind).iterdir()) != names:
            raise ValueError("quarantine artifact set mismatch")
    return dict(
        name=record["name"],
        plan_sha256=record["superseded_plan_sha256"],
        record_sha256=s.sha256(folder / "QUARANTINE.json"),
        moves=len(record["moves"]),
    )


def admission(base):
    root = base / "quarantine"
    if not root.exists():
        return []
    if root.is_symlink():
        raise ValueError("symlink quarantine")
    results = []
    for folder in sorted(root.iterdir()):
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("invalid quarantine folder")
        record = json.loads((folder / "QUARANTINE.json").read_text())
        if record["name"] != folder.name:
            raise ValueError("quarantine name mismatch")
        results.append(verify(base, record))
    return results


def failed_attempt(base, args):
    number = args.failed_attempt
    if number not in ATTEMPTS:
        raise ValueError("failed attempt must be 0..3")
    if not isinstance(args.reason, str) or not args.reason.strip():
        raise ValueError("failed attempt reason required")
    with storage.lock():
        folder = base / "quarantine" / args.name
        if folder.exists() or folder.is_symlink():
            raise ValueError("immutable quarantine exists")
        attempt = base / "native" / number
        if attempt.is_symlink() or not attempt.is_dir():
            raise ValueError("failed attempt missing")
        plan = json.loads((attempt / "plan.json").read_text())
        receipt = json.loads((attempt / "receipt.json").read_text())
        if (
            inv.seal(plan) != plan
            or plan.get("schema") != "mve-wo6c-capture-v1"
            or len(plan.get("jobs", [])) != 16
            or receipt.get("plan_sha256") != plan.get("sha256")
            or receipt.get("status") != "failed"
        ):
            raise ValueError("only a sealed failed attempt can be set aside")
        ids = {
            j["snapshot_id"]
            for j in plan["jobs"][4 * int(number) : 4 * int(number) + 4]
        }
        if len(ids) != 4:
            raise ValueError("failed attempt batch incomplete")
        snapshots = base / "snapshots"
        if snapshots.is_symlink():
            raise ValueError("symlink snapshots root")
        moves = []
        for source in [attempt] + [
            snapshots / ident
            for ident in sorted(ids)
            if (snapshots / ident).exists() or (snapshots / ident).is_symlink()
        ]:
            if source != attempt:
                complete = source / "complete.json"
                if complete.exists():
                    raise ValueError("accepted snapshot cannot be set aside")
            rel = source.relative_to(base)
            moves.append(
                dict(
                    source=rel.as_posix(),
                    dest=(Path("quarantine") / args.name / rel).as_posix(),
                    inventory=inventory(source),
                )
            )
        record = inv.seal(
            dict(
                schema=FAILED_SCHEMA,
                name=args.name,
                reason=args.reason,
                attempt=number,
                attempt_plan_sha256=plan["sha256"],
                moves=moves,
            )
        )
        raw = storage.encoded(record)
        storage.disk_guard(storage.local(storage.GENERATED), len(raw))
        folder.mkdir(parents=True)
        (folder / "native").mkdir()
        (folder / "snapshots").mkdir()
        fd = os.open(
            folder / "QUARANTINE.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        for move in moves:
            dest = base / move["dest"]
            if dest.exists() or dest.is_symlink():
                raise ValueError("quarantine destination exists")
            (base / move["source"]).rename(dest)
        admission(base)
        return verify_failed(base, record)


def run(args):
    base = storage.local(capture_c.BASE)
    storage.token(args.name)
    if getattr(args, "failed_attempt", None) is not None:
        if args.plan_sha256 is not None:
            raise ValueError("failed attempt does not take superseded plan hash")
        return failed_attempt(base, args)
    if len(args.plan_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in args.plan_sha256
    ):
        raise ValueError("invalid superseded plan hash")
    with storage.lock():
        admission(base)
        folder = base / "quarantine" / args.name
        if folder.exists():
            raise ValueError("immutable quarantine exists")
        current_plan = capture_c.plan()
        if args.plan_sha256 == current_plan["sha256"]:
            raise ValueError("current plan cannot be quarantined")
        known_ids = expected_snapshots(base / "native", args.plan_sha256)
        snapshot_root = base / "snapshots"
        if (
            snapshot_root.is_symlink()
            or not snapshot_root.is_dir()
            or {p.name for p in snapshot_root.iterdir()} != known_ids
        ):
            raise ValueError("complete superseded snapshot set required")
        moves = []
        for kind in ("native", "snapshots"):
            root = base / kind
            if not root.exists():
                continue
            for source in sorted(root.iterdir()):
                if kind == "native" and source.name not in {"0", "1", "2", "3"}:
                    raise ValueError("unexpected native attempt")
                if kind == "snapshots" and source.name not in known_ids:
                    raise ValueError("unexpected snapshot identity")
                if kind == "native":
                    receipt = source / "receipt.json"
                    if (
                        receipt.is_file()
                        and json.loads(receipt.read_text()).get("plan_sha256")
                        != args.plan_sha256
                    ):
                        raise ValueError("attempt belongs to another plan")
                rel = Path(kind) / source.name
                moves.append(
                    dict(
                        source=rel.as_posix(),
                        dest=(Path("quarantine") / args.name / rel).as_posix(),
                        inventory=inventory(source),
                    )
                )
        if not moves or not any(m["source"].startswith("native/") for m in moves):
            raise ValueError("no superseded attempts")
        record = inv.seal(
            dict(
                schema=SCHEMA,
                name=args.name,
                reason=args.reason,
                superseded_plan_sha256=args.plan_sha256,
                moves=moves,
            )
        )
        raw = storage.encoded(record)
        storage.disk_guard(storage.local(storage.GENERATED), len(raw))
        folder.mkdir(parents=True)
        (folder / "native").mkdir()
        (folder / "snapshots").mkdir()
        fd = os.open(
            folder / "QUARANTINE.json",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        for move in moves:
            source, dest = base / move["source"], base / move["dest"]
            if dest.exists():
                raise ValueError("quarantine destination exists")
            source.rename(dest)
        return verify(base, record)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--plan-sha256")
    selector.add_argument("--failed-attempt")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("WO-6 quarantine refused: " + getattr(exc, "label", "internal_error"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
