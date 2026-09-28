"""Read-only admission of historical completions and manual quarantine evidence."""

import json
from pathlib import Path
from mve.observer import capture_policy as policy, snapshots as s


def snapshot_version(folder, receipt):
    values = [
        json.loads((folder / f"pass-{n}.json").read_text())["versions"].get("chrome")
        for n in (0, 1)
    ]
    if "browser_version" in receipt:
        values.append(receipt["browser_version"])
    return policy.one_version(values)


def plain_child(root, name):
    if not isinstance(name, str) or Path(name).name != name or name in (".", ".."):
        raise ValueError("unsafe evidence name")
    p = root / name
    if p.is_symlink():
        raise ValueError("symlink evidence")
    return p


def quarantine(base, plan):
    from mve.observer import snapshot_batch as batch

    root = plain_child(base, "quarantine")
    if not root.exists():
        return []
    records = []
    for folder in sorted(root.iterdir()):
        plain_child(root, folder.name)
        path = plain_child(folder, "QUARANTINE.json")
        record = json.loads(path.read_text())
        if (
            record["schema"] != "mve-wo1b-quarantine-v1"
            or record["attempt"] != folder.name
        ):
            raise ValueError("quarantine identity mismatch")
        attempt = plain_child(base, record["attempt"])
        receipt = plain_child(attempt, "receipt.json")
        if s.sha256(receipt) != record["attempt_receipt_sha256"]:
            raise ValueError("quarantine attempt digest mismatch")
        audit = json.loads(receipt.read_text())
        batch.require_audit(audit)
        selected = {j["snapshot_id"] for j in batch.select_jobs(plan, record["batch"])}
        if (
            set(record["snapshots"]) != selected
            or audit["batch"] != record["batch"]
            or set(audit["selected"]) != selected
            or record["source_repos_unchanged"] is not True
            or record["archive_unchanged"] is not True
        ):
            raise ValueError("quarantine selection mismatch")
        if set(p.name for p in folder.iterdir()) != selected | {"QUARANTINE.json"}:
            raise ValueError("quarantine artifact set mismatch")
        for ident, files in record["snapshots"].items():
            snapshot = plain_child(folder, ident)
            if set(p.name for p in snapshot.iterdir()) != set(files):
                raise ValueError("quarantine artifact set mismatch")
            for name, expected in files.items():
                if s.sha256(plain_child(snapshot, name)) != expected:
                    raise ValueError("quarantine artifact digest mismatch")
        records.append(
            dict(
                attempt=folder.name,
                record_sha256=s.sha256(path),
                snapshot_ids=sorted(selected),
            )
        )
    return records


def resume_state(base, plan):
    from mve.observer import snapshot_batch as batch, snapshot_inventory as inv

    records = quarantine(base, plan)
    snapshots = plain_child(base, "snapshots")
    jobs = inv.jobs(plan)
    if snapshots.exists() and not {p.name for p in snapshots.iterdir()} <= {
        j["snapshot_id"] for j in jobs
    }:
        raise ValueError("unknown snapshot evidence")
    completed, remaining, clusters = [], [], {}
    for j in jobs:
        folder = snapshots / j["snapshot_id"]
        if batch.completed(folder, plan, j):
            r = json.loads((folder / "complete.json").read_text())
            version = snapshot_version(folder, r)
            clusters.setdefault(j["block"]["cluster"], []).append(version)
            completed.append(j)
        else:
            remaining.append(j)
    versions = {
        cluster: policy.one_version(values) for cluster, values in clusters.items()
    }
    return dict(
        completed=completed,
        remaining=remaining,
        cluster_versions=versions,
        quarantine=records,
    )
