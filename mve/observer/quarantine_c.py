"""Write-ahead quarantine of one superseded WO-6c capture plan."""

import argparse
import json
import os
from pathlib import Path

from mve.observer import capture_c, snapshot_inventory as inv, snapshots as s, storage

SCHEMA = "mve-wo6c-plan-quarantine-v1"


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
        if (base / source).exists() or (base / source).is_symlink():
            raise ValueError("superseded evidence still active")
        expected[source.parts[0]].add(source.parts[1])
        if inventory(base / dest) != move["inventory"]:
            raise ValueError("quarantine artifact digest mismatch")
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
        jobs = current_plan["jobs"]
        known_ids = {j["snapshot_id"] for j in jobs}
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
