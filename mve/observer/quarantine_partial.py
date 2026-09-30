"""Manual operator tool: preserve named accepted snapshots of one cluster."""

import argparse
import json
from pathlib import Path
from mve.observer import capture_evidence as evidence, snapshot_inventory as inv
from mve.observer import snapshot_batch as batch, storage, snapshots as s

SCHEMA = "mve-wo1b-partial-quarantine-v1"


def validate(base, plan, record):
    """Validate provenance and the explicitly named subset before any move."""
    if record["schema"] != SCHEMA or record["plan_sha256"] != plan["sha256"]:
        raise ValueError("partial quarantine identity mismatch")
    storage.token(record["name"])
    if not isinstance(record["reason"], str) or not record["reason"].strip():
        raise ValueError("quarantine reason required")
    attempt = evidence.plain_child(base, record["attempt"])
    receipt = evidence.plain_child(attempt, "receipt.json")
    if s.sha256(receipt) != record["attempt_receipt_sha256"]:
        raise ValueError("quarantine attempt digest mismatch")
    audit = json.loads(receipt.read_text())
    batch.require_audit(audit)
    capture_path = evidence.plain_child(attempt, "capture.json")
    if s.sha256(capture_path) != record["attempt_capture_sha256"]:
        raise ValueError("quarantine capture digest mismatch")
    capture = json.loads(capture_path.read_text())
    if [c["snapshot_id"] for c in capture["candidates"]] != audit["selected"]:
        raise ValueError("quarantine capture selection mismatch")
    audit = {
        **audit,
        "candidates": {c["snapshot_id"]: c for c in capture["candidates"]},
    }
    jobs = {j["snapshot_id"]: j for j in batch.select_jobs(plan, audit["batch"])}
    ids = set(record["snapshots"])
    if (
        audit["status"] != "captured"
        or audit["plan_sha256"] != plan["sha256"]
        or not ids
        or not ids <= set(audit["selected"]) <= set(jobs)
        or {jobs[i]["block"]["cluster"] for i in ids} != {record["cluster"]}
    ):
        raise ValueError("partial quarantine selection mismatch")
    return jobs, audit


def verify_snapshot(folder, plan, job, files, audit):
    if set(p.name for p in folder.iterdir()) != set(files):
        raise ValueError("quarantine artifact set mismatch")
    for name, expected in files.items():
        if s.sha256(evidence.plain_child(folder, name)) != expected:
            raise ValueError("quarantine artifact digest mismatch")
    if not batch.completed(folder, plan, job):
        raise ValueError("accepted snapshot required")
    complete = json.loads((folder / "complete.json").read_text())
    if any(complete["source_audit"][k] != audit[k] for k in complete["source_audit"]):
        raise ValueError("source attempt audit mismatch")
    candidate = audit["candidates"][job["snapshot_id"]]
    if inv.seal({**candidate, "source_audit": complete["source_audit"]}) != complete:
        raise ValueError("source attempt candidate mismatch")


def read(base, folder, plan, record):
    jobs, audit = validate(base, plan, record)
    if record["name"] != folder.name:
        raise ValueError("partial quarantine name mismatch")
    if set(p.name for p in folder.iterdir()) != set(record["snapshots"]) | {
        "QUARANTINE.json"
    }:
        raise ValueError("quarantine artifact set mismatch")
    for ident, files in record["snapshots"].items():
        verify_snapshot(
            evidence.plain_child(folder, ident), plan, jobs[ident], files, audit
        )
    return dict(
        attempt=record["attempt"],
        name=folder.name,
        record_sha256=s.sha256(folder / "QUARANTINE.json"),
        snapshot_ids=sorted(record["snapshots"]),
    )


def run(args):
    plan = inv.load(args.plan)
    base = storage.local(args.base)
    storage.token(args.name)
    if len(set(args.snapshots)) != len(args.snapshots):
        raise ValueError("duplicate snapshot selection")
    with storage.lock():
        evidence.resume_state(base, plan)
        root = evidence.plain_child(base, "quarantine")
        folder = evidence.plain_child(root, args.name)
        if folder.exists():
            raise ValueError("immutable quarantine exists")
        receipt = evidence.plain_child(
            evidence.plain_child(base, args.attempt), "receipt.json"
        )
        snapshots = evidence.plain_child(base, "snapshots")
        files = {}
        for ident in args.snapshots:
            source = evidence.plain_child(snapshots, ident)
            files[ident] = {
                p.name: s.sha256(evidence.plain_child(source, p.name))
                for p in source.iterdir()
            }
        record = dict(
            schema=SCHEMA,
            name=args.name,
            reason=args.reason,
            plan_sha256=plan["sha256"],
            cluster=args.cluster,
            attempt=args.attempt,
            attempt_receipt_sha256=s.sha256(receipt),
            attempt_capture_sha256=s.sha256(
                evidence.plain_child(receipt.parent, "capture.json")
            ),
            snapshots=files,
        )
        jobs, audit = validate(base, plan, record)
        for ident in files:
            verify_snapshot(snapshots / ident, plan, jobs[ident], files[ident], audit)
        raw = storage.encoded(record)
        storage.disk_guard(storage.local(storage.GENERATED), len(raw))
        folder.mkdir(parents=True)
        # Write-ahead record: interrupted moves fail closed on admission. Never
        # erase the record or evidence; operator can finish the recorded moves.
        batch.write(folder / "QUARANTINE.json", raw)
        for ident in files:
            (snapshots / ident).rename(folder / ident)
        evidence.resume_state(base, plan)
    print(json.dumps(dict(status="quarantined", name=args.name, snapshots=len(files))))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", type=Path, required=True, help="worktree-relative mve/generated path"
    )
    parser.add_argument("--plan", type=Path, required=True)
    for name in ("name", "cluster", "attempt", "reason"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--snapshots", nargs="+", required=True)
    try:
        return run(parser.parse_args(argv))
    except (ValueError, OSError, KeyError) as exc:
        print("quarantine refused: " + getattr(exc, "label", type(exc).__name__))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
