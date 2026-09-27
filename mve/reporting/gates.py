"""Explicit conjunctive gate decisions. Missing evidence takes precedence over failure."""

from mve.evaluation.scoring import score

PLAN = "docs/mve/MVE_PLAN.md"
G3 = "mve/lean/artifacts/g3-taskset/g3.json"
REVIEW = "docs/mve/reviews/OFFLINE_PACKETS_REVIEW_OPUS_20260927.md"
SPECS = {
    "G0": {
        "null": "Validation N/A; Geoperception weighted per-item 1/k_i and majority baseline (sample absent)",
        "requirements": {
            "records": "100 independently generated records validate",
            "negative_fixtures": "bad references, arities, unauthorized support and invalid transitions rejected",
            "coverage": "coverage target met",
            "comparison": "300 frozen Geoperception items, three pinned models and pinned scorer within USD 2; comparison incomplete without results",
        },
    },
    "G1": {
        "null": "Query-set independent guessing: recall=FPR=1/2, precision=prevalence; all-positive precision=prevalence, recall=1. Full-record random-set null N/A.",
        "requirements": {
            "sealed": "500 sealed incidence diagrams; fixed queries, family split, no tolerance fitting on evaluation",
            "precision": "precision >= 0.90",
            "recall": "recall >= 0.70",
            "fpr": "per-predicate suitable negatives: one-sided 95% FPR upper bound <= 0.02; otherwise insufficient evidence",
            "separate_scores": "raw, coordinate-consistency, image-measurement; micro/macro; query/full-record; separate real-data transfer",
        },
    },
    "G2": {
        "null": "Balanced binary 1/2; uniform k-class 1/k; majority, code-only and previous-lock baselines",
        "requirements": {
            "floors": "only floor-met questions active with three family-disjoint splits",
            "paired_accuracy": "independent gold: paired 95% lower bound cascade minus Opus >= -0.03",
            "queue": "human queue <= 25%",
            "route_error": "per active question one-sided 95% automatic-route error upper bound <= 5%",
            "weight_refit": "real production weight refit, ONNX export and inference parity",
            "promotion": "promote/rollback decision on calibration evidence",
        },
    },
    "G3": {
        "null": "N/A; empty/trivial, nearest-retrieval, weakened/strengthened/vacuous/unrelated-but-provable controls",
        "requirements": {
            "tasks": "100 distinct sealed statements with explicit premises and goals",
            "first_pass": "at least 80/100 first-pass well-typed artifacts",
            "post_repair": "at least 95/100 post-repair well-typed artifacts",
            "references": "50 retrieval-disjoint blinded reference tasks",
            "semantic_rubric": "at least 20/50 human rubric passes: binders, premises, goal, nondegeneracy",
        },
    },
    "G4a": {
        "null": "N/A; fixed trivial-tactic baseline",
        "requirements": {
            "eligible": "50 semantically accepted statements frozen before tuning",
            "comparison": "both provers, 120 s, declared resources; proved/timeout/error, latency, memory",
            "proofs": "default >= 15/50 proved with checked dependency closures",
            "selection": "proved count then latency; DeepSeek on exact tie",
            "end_to_end": "end-to-end success and trivial-tactic baseline reported",
        },
    },
    "G4b": {
        "null": "N/A; previous lock and unchanged-record round trip",
        "requirements": {
            "session": "30-minute, 20-diagram session",
            "verdicts": "persisted verdicts, not_visible abstention, revision invalidation, label provenance",
            "routing": "routing effects replayable",
            "refit": "floor-conditional refit or documented no-update",
            "atlas": "pinned atlas integration test passes from archived build",
        },
    },
    "G5": {
        "null": "N/A general PD; conditional orientation-only 2^(-c); knot-type 1/k plus majority",
        "requirements": {
            "grammar": "frozen diagram grammar and PD scorer",
            "synthetic": ">= 30% complete PD on separate synthetic <= 7-crossing set",
            "external": ">= 30% complete PD on permitted external <= 7-crossing set; missing external incomplete",
            "scores": "exact/canonicalized apart; component validity, crossing/orientation errors, unknowns, invariant consistency",
        },
    },
    "G6": {
        "null": "N/A integration; each scientific claim declares its own null and unit",
        "requirements": {
            "record": "one reproducible record: image, revisions, evidence, assumptions, statement hash, actual statuses and baselines",
            "review": "Sol review",
            "ingest": "real ingest/validation contract passes; negative or inconclusive science is acceptable",
        },
    },
}


def evaluate_gate(gate, checks):
    spec = SPECS[gate]
    if set(checks) - set(spec["requirements"]):
        raise ValueError("unknown gate criterion")
    complete = {}
    for key, requirement in spec["requirements"].items():
        row = checks.get(
            key,
            {
                "outcome": None,
                "reason": "Missing evidence: " + requirement,
                "sources": [],
            },
        )
        if row["outcome"] is not None and type(row["outcome"]) is not bool:
            raise ValueError("criterion outcome must be true, false or null")
        if row["outcome"] is not None and not row["sources"]:
            raise ValueError("criterion outcome requires evidence")
        complete[key] = {
            **row,
            "requirement": requirement,
            "policy_source": PLAN + "#8",
        }
    outcomes = [r["outcome"] for r in complete.values()]
    state = (
        "not established"
        if None in outcomes
        else "established"
        if all(outcomes)
        else "failed"
    )
    return {
        "status": state,
        "criteria": complete,
        "null": spec["null"],
        "counts": {
            "criteria_expected": len(outcomes),
            "criteria_evidenced": sum(v is not None for v in outcomes),
            "criteria_met": sum(v is True for v in outcomes),
        },
        "reasons": [r["reason"] for r in complete.values() if r["outcome"] is not True],
        "micro": None,
        "macro": None,
        "aggregation_reason": "gate criteria are conjunctions, not relation or diagram scores",
        "interval95": None,
        "interval_reason": "gate decision is not a sampled accuracy",
        "sources": [PLAN + "#8", PLAN + "#11"],
    }


def validate_g3_counts(data):
    denominators = {
        "unique_canonical_statements": "tasks",
        "first_pass_well_typed": "tasks",
        "post_repair_well_typed": "tasks",
        "human_reviews": "reference_tasks",
        "semantic_rubric_passes": "human_reviews",
    }
    for key in {*denominators, *denominators.values()}:
        if type(data[key]) is not int or data[key] < 0:
            raise ValueError("G3 requires nonnegative integer counts")
    if any(data[key] > data[total] for key, total in denominators.items()):
        raise ValueError("G3 count exceeds denominator")
    if data["first_pass_well_typed"] > data["post_repair_well_typed"]:
        raise ValueError("G3 post-repair count cannot discard first-pass successes")


def g3_checks(data):
    validate_g3_counts(data)
    values = {
        "tasks": (
            True
            if data["tasks"] == 100 and data["unique_canonical_statements"] == 100
            else None,
            f"{data['unique_canonical_statements']}/{data['tasks']} unique sealed statements",
        ),
        "first_pass": (
            data["first_pass_well_typed"] >= 80,
            f"{data['first_pass_well_typed']}/{data['tasks']} first-pass",
        ),
        "post_repair": (
            data["post_repair_well_typed"] >= 95,
            f"{data['post_repair_well_typed']}/{data['tasks']} post-repair",
        ),
        "references": (
            True if data["reference_tasks"] == 50 else None,
            f"{data['reference_tasks']}/50 retrieval-disjoint references",
        ),
        "semantic_rubric": (
            True
            if data["semantic_rubric_passes"] >= 20
            else False
            if data["human_reviews"] == 50
            else None,
            f"{data['human_reviews']}/50 human reviews; {data['semantic_rubric_passes']}/50 rubric passes"
            + (
                "; pending human rubric"
                if data["human_reviews"] < 50 and data["semantic_rubric_passes"] < 20
                else ""
            ),
        ),
    }
    return {
        k: {
            "outcome": value,
            "reason": reason,
            "sources": [G3 + "#/", REVIEW + "#addendum-9"],
        }
        for k, (value, reason) in values.items()
    }


def relation_table(gold, predictions, *, mode, task, sources):
    result = score(gold, predictions, mode=mode, task=task)
    c = result["micro"]
    result["denominators"] = {
        "micro": {
            "accuracy": c["queries"],
            "precision": c["tp"] + c["fp"],
            "recall": c["positives"],
            "fpr": c["negatives"],
            "coverage": c["queries"],
            "negative_error_or_missing_rate": c["negatives"],
        },
        "macro": result["macro"]["metric_diagrams"],
    }
    return {
        **result,
        "sources": sources,
        "interval95": None,
        "interval_reason": "sampling design/independence absent; no confidence gate inferred",
    }
