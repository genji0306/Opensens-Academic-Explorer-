"""Read-only WO-6 v1 audit under v2 diagnostics; never retrofit citations/tags."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from mve.observer import grounded as g, pilot_b_accounting as accounting, power
from mve.observer.card import digest

EVIDENCE = accounting.EVIDENCE


def build():
    plan = json.loads((EVIDENCE / "design.json").read_text())
    report = json.loads((EVIDENCE / "report.json").read_text())
    rows, repetitions, malformed, sources = [], {}, [], {}
    for job in plan["jobs"]:
        if job["arm"] in ("real", "null_twin"):
            path = EVIDENCE / "attempts" / job["id"] / "2/response.raw"
            raw = path.read_bytes()
            sources[path.relative_to(accounting.ROOT).as_posix()] = hashlib.sha256(
                raw
            ).hexdigest()
            values = g.proposals(
                g.parse(g.parse(raw)["choices"][0]["message"]["content"])
            )
            repetitions[job["id"]] = dict(
                module=job["module"],
                arm=job["arm"],
                tag_jaccard=None,
                reason="v1 contains strings, no versioned feature tags; not inferred after seeing outcomes",
            )
        else:
            values = []
            for r in report["slots"]:
                if r["job"] == job["id"] and r["card"]:
                    d = r["card"]
                    p = {
                        k: deepcopy(d[k])
                        for k in (
                            "claim",
                            "testable_form",
                            "prediction",
                            "resemblance_target",
                        )
                    }
                    p["testable_form"]["direction"] = p["testable_form"][
                        "direction"
                    ].split(";")[0]
                    p["kill_threshold"] = d["kill_criterion"]["components"][0][
                        "threshold"
                    ]
                    values.append(p)
        assessments = g.assess(values, [], job_id=job["id"], legacy=True)
        for slot in range(3):
            row = dict(
                job=job["id"],
                module=job["module"],
                arm=job["arm"],
                slot=slot,
                status="unavailable_donor" if job["arm"] == "shuffled" else "empty",
                check=dict(status="unavailable", inferential=False),
            )
            if slot < len(values):
                row.update(assessments[slot])
                row["proposal"] = values[slot]
                if row["reason"]:
                    malformed.append(
                        dict(
                            job=job["id"],
                            module=job["module"],
                            arm=job["arm"],
                            slot=slot,
                            reason=row["reason"],
                            detail="prediction is a JSON number; v1 and v2 require a replication-condition string",
                        )
                    )
                else:
                    mapped = deepcopy(values[slot])
                    mapped["testable_form"]["data"] = g.canonical(
                        mapped["testable_form"]["data"], g.CONTRACT["data_aliases"]
                    )
                    row["check"] = power.check(mapped, job)
            rows.append(row)
    result = dict(
        schema="mve-wo6b-offline-rescore-v1",
        hosted_calls=0,
        slots=rows,
        by_arm=g.arm_counts(rows),
        malformed_slots=malformed,
        repeatability=g.repetition_report(repetitions),
        sources=sources,
        contract_sha256=digest(g.CONTRACT),
        power_sha256=power.load()["sha256"],
        meaning="Retrospective diagnostic only. Status precedence: malformed, contradictory, ungrounded; flags overlap. No invented observations, citations, feature tags or survivors.",
    )
    return {**result, "sha256": digest(result)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.write_text(json.dumps(build(), sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
