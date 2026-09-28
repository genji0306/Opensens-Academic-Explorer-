"""Re-render one accepted WO-1b cluster in a fresh immutable evidence directory.

python3 -m mve.observer.renderer_drift --plan mve/observer/config/wo1b_manifest.json \
  --batch 0 --drift-cluster spectral-ordinary-0 --drift-from mve/generated/wo1b-d286a45abc8187fd \
  --drift-output mve/generated/wo1b-renderer-drift-001
"""

import json
from mve.observer import snapshot_batch as batch, capture_policy as policy
from mve.observer.capture_evidence import snapshot_version


def accepted_cluster(base, plan, jobs):
    if not jobs or len(jobs) > 10 or len({j["block"]["cluster"] for j in jobs}) != 1:
        raise ValueError("drift requires one complete cluster")
    expected = {
        j["snapshot_id"]
        for j in batch.inv.jobs(plan)
        if j["block"]["cluster"] == jobs[0]["block"]["cluster"]
    }
    if {j["snapshot_id"] for j in jobs} != expected:
        raise ValueError("drift requires all cluster blocks")
    versions = []
    for j in jobs:
        folder = base / "snapshots" / j["snapshot_id"]
        if not batch.completed(folder, plan, j):
            raise ValueError("drift requires accepted snapshots")
        versions.append(
            snapshot_version(folder, json.loads((folder / "complete.json").read_text()))
        )
    return policy.one_version(versions)


def compare(base, fresh, plan, jobs):
    old_version = accepted_cluster(base, plan, jobs)
    new_version = accepted_cluster(fresh, plan, jobs)
    comparisons = []
    for j in jobs:
        old = base / "snapshots" / j["snapshot_id"]
        new = fresh / "snapshots" / j["snapshot_id"]
        row = dict(
            snapshot_id=j["snapshot_id"],
            accepted_complete_sha256=batch.s.sha256(old / "complete.json"),
            new_complete_sha256=batch.s.sha256(new / "complete.json"),
            data_bytes_equal=(old / "data.json").read_bytes()
            == (new / "data.json").read_bytes(),
        )
        for n in (0, 1):
            row[f"blind_{n}"] = batch.s.compare_png(
                old / f"blind-{n}.png", new / f"blind-{n}.png"
            )
        row["passed"] = row["data_bytes_equal"] and all(
            row[f"blind_{n}"]["passed"] for n in (0, 1)
        )
        comparisons.append(row)
    return batch.inv.seal(
        dict(
            plan_sha256=plan["sha256"],
            cluster=jobs[0]["block"]["cluster"],
            accepted_browser_version=old_version,
            browser_version=new_version,
            tolerance=batch.s.PNG_REPEAT_TOLERANCE,
            comparisons=comparisons,
            passed=all(r["passed"] for r in comparisons),
        )
    )


def main(argv=None):
    args = batch.parse_args(argv)
    if (
        not args.drift_from
        or not args.drift_output
        or not args.drift_cluster
        or args.prepare_only
        or args.pilot
    ):
        print("WO-1b refused: drift_arguments")
        return 2
    try:
        return batch.run(args)
    except (ValueError, OSError, KeyError) as exc:
        print("WO-1b refused: " + getattr(exc, "label", type(exc).__name__))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
