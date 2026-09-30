"""Write-ahead quarantine of one superseded WO-6c capture plan."""

import argparse
import json
import os
from pathlib import Path

from mve.observer import capture_c, snapshot_inventory as inv, snapshots as s, storage

SCHEMA = "mve-wo6c-plan-quarantine-v1"
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


def verify(base, record):
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
        active = base / source
        if active.exists() or active.is_symlink():
            marker = active / (
                "receipt.json" if source.parts[0] == "native" else "complete.json"
            )
            if (
                active.is_symlink()
                or not marker.is_file()
                or json.loads(marker.read_text()).get("plan_sha256")
                != capture_c.plan()["sha256"]
            ):
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


def run(args):
    base = storage.local(capture_c.BASE)
    storage.token(args.name)
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
    parser.add_argument("--plan-sha256", required=True)
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
