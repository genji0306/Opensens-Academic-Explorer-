"""Evidence tables: every row carries units, denominators, nulls and provenance."""

from collections import Counter
from mve.reporting.gates import G3

PREFLIGHT = "mve/preflight/results/report.json"
CORPUS = "docs/mve/reviews/WP2_CORPUS_RENDER_V2_RECEIPT_20260927.json"
GENERATION = "docs/mve/reviews/WP2_CORPUS_RECEIPT_20260927.json"
SPIKE = "mve/classifier/spike_receipt.json"
LIVE = "docs/mve/reviews/wp0b-live/receipt.json"
TASKS = "mve/lean/artifacts/g3-taskset/tasks.json"
REFERENCES = "mve/lean/artifacts/g3-taskset/references.json"


def metric(
    name,
    count,
    denominator,
    unit,
    source,
    pointer,
    *,
    note="",
    null="N/A: structural or operational census",
):
    return {
        "name": name,
        "count": count,
        "denominator": denominator,
        "unit": unit,
        "null": null,
        "micro": None,
        "macro": None,
        "aggregation_reason": "not scored relations; no micro/macro relation score implied",
        "interval95": None,
        "interval_reason": "finite committed fixture census; independent sampling design not established",
        "sources": [source + "#" + pointer],
        "note": note,
    }


def preflight_table(data):
    rows = data["checks"]
    return [
        metric(
            r["name"],
            int(r["status"] == "ran"),
            1,
            "capability check",
            PREFLIGHT,
            f"/checks/{i}",
            note="WP-0a historical status: "
            + r["status"]
            + "; capability-specific only",
        )
        for i, r in enumerate(rows)
    ]


def corpus_table(data, generation):
    if generation is not None:
        for key in ("counts", "class_counts", "manifest_sha256", "split_sha256"):
            if generation[key] != data[key]:
                raise ValueError("generation/audit receipts disagree")
    total = sum(data["counts"].values())
    rows = [
        metric("corpus/" + k, v, total, "diagrams", CORPUS, "/counts/" + k)
        for k, v in sorted(data["counts"].items())
    ]
    rows.append(
        metric(
            "records validated",
            data["records_validated"],
            total,
            "records",
            CORPUS,
            "/records_validated",
            note="Receipt evidence; generated private corpus not re-audited by this report",
        )
    )
    relations = sum(data["class_counts"].values())
    rows += [
        metric(
            "truth class/" + k,
            v,
            relations,
            "candidate relations",
            CORPUS,
            "/class_counts/" + k,
            note="Truth census, not perception scores; per-diagram truth counts unavailable in receipt",
        )
        for k, v in sorted(data["class_counts"].items())
    ]
    rows += [
        metric(
            k,
            data[k],
            None,
            "cross-split collisions",
            CORPUS,
            "/" + k,
            note="Pair denominator not retained by receipt",
        )
        for k in ("cross_split_coordinate_collisions", "cross_split_image_collisions")
    ]
    return rows


def validate_g3_details(data, tasks, references):
    expected = {
        "empty",
        "trivial",
        "nearest_retrieval",
        "weakened",
        "strengthened",
        "vacuous",
        "unrelated_but_provable",
    }
    if set(data["controls"]) != expected:
        raise ValueError("G3 control kinds incomplete")
    predicates = dict(Counter(row["predicate"] for row in tasks))
    if predicates != data["per_predicate_counts"]:
        raise ValueError("G3 predicate summary disagrees with task receipts")
    receipts = [row[stage] for row in tasks for stage in ("first_pass", "post_repair")]
    receipts += [row["typecheck"] for row in references]
    for receipt in receipts:
        if type(receipt["ok"]) is not bool or receipt["proof_checked"] is not False:
            raise ValueError("G3 typecheck receipt has invalid status or proof claim")
        if receipt["ok"] != (receipt["outcome"] == "typechecked"):
            raise ValueError("G3 typecheck outcome disagrees with status")


def g3_headline_rows(data):
    note = data["scope"] + "; typechecking is not proof or semantic acceptance"
    rows = [
        metric(
            k,
            data[k],
            data["reference_tasks"]
            if k in ("human_reviews", "semantic_rubric_passes")
            else data["tasks"],
            "reference tasks"
            if k in ("human_reviews", "semantic_rubric_passes")
            else "statements",
            G3,
            "/" + k,
            note=note,
        )
        for k in (
            "first_pass_well_typed",
            "post_repair_well_typed",
            "unique_canonical_statements",
            "human_reviews",
            "semantic_rubric_passes",
        )
    ]
    return rows


def g3_table(data, tasks, references):
    validate_g3_details(data, tasks, references)
    computed = {
        "tasks": len(tasks),
        "reference_tasks": len(references),
        "first_pass_well_typed": sum(r["first_pass"]["ok"] is True for r in tasks),
        "post_repair_well_typed": sum(r["post_repair"]["ok"] is True for r in tasks),
        "human_reviews": sum("review" in r["equivalence"] for r in references),
        "semantic_rubric_passes": sum(
            r["equivalence"]["semantic_acceptance"] is True for r in references
        ),
        "unique_canonical_statements": len(
            {r["canonical_statement_sha256"] for r in tasks}
        ),
    }
    if any(data[key] != value for key, value in computed.items()):
        raise ValueError("G3 summary disagrees with task/reference receipts")
    controls = {
        k: {
            "detected": sum("refusal" in r["controls"][k] for r in tasks),
            "total": len(tasks),
        }
        for k in data["controls"]
    }
    levels = dict(Counter(r["equivalence"]["level"] for r in references))
    if controls != data["controls"] or any(
        levels.get(k, 0) != v for k, v in data["equivalence_counts"].items()
    ):
        raise ValueError("G3 controls/equivalence summary disagrees with rows")
    return g3_detail_rows(data, tasks, references, controls)


def g3_detail_rows(data, tasks, references, controls):
    rows = g3_headline_rows(data)
    rows += [
        metric(
            "control/" + k,
            v["detected"],
            v["total"],
            "control statements",
            G3,
            "/controls/" + k,
        )
        for k, v in sorted(controls.items())
    ]
    rows += [
        metric(
            "equivalence/" + k,
            v,
            len(references),
            "reference tasks",
            G3,
            "/equivalence_counts/" + k,
        )
        for k, v in sorted(data["equivalence_counts"].items())
    ]
    rows += [
        metric(
            "predicate/" + k,
            v,
            len(tasks),
            "statements",
            G3,
            "/per_predicate_counts/" + k,
            note=str(data["quota_gaps"].get(k, "")),
        )
        for k, v in sorted(data["per_predicate_counts"].items())
    ]
    for row in rows:
        row["sources"] += [TASKS + "#/", REFERENCES + "#/"]
    return rows


def spike_table(data):
    rows = [
        metric(
            "ONNX argmax parity",
            data["onnx_parity"]["argmax_matches"],
            data["onnx_parity"]["fixtures"],
            "fixture states",
            SPIKE,
            "/onnx_parity",
            note=data["scope"] + "; fixture only, not G2",
        ),
        metric(
            "training rows",
            data["training_rows"],
            data["training_rows"],
            "fixture rows",
            SPIKE,
            "/training_rows",
        ),
        metric(
            "training families",
            data["training_families"],
            None,
            "families",
            SPIKE,
            "/training_families",
        ),
    ]
    for question, support in sorted(data["learning"]["support"].items()):
        for split, labels in sorted(support["counts"].items()):
            row = metric(
                question + "/" + split,
                sum(labels.values()),
                None,
                "label rows",
                SPIKE,
                "/learning/support/" + question + "/counts/" + split,
                null="uniform 1/k = " + str(data["learning"]["nulls"][question]),
                note="No independent gold accuracy; majority/code-only/previous-lock unavailable",
            )
            row["label_counts"] = labels
            rows.append(row)
    return rows


def live_table(data):
    observation = data["observation"]
    rows = [
        metric(
            "image accepted",
            int(observation["image_accepted"]),
            1,
            "live probe",
            LIVE,
            "/observation/image_accepted",
            note="No truth-scored accuracy from the probe",
        )
    ]
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        rows.append(
            metric(
                key,
                observation["usage"][key],
                1,
                "tokens per probe",
                LIVE,
                "/observation/usage/" + key,
            )
        )
    rows.append(
        metric(
            "latency_s",
            observation["latency_s"],
            1,
            "seconds per probe",
            LIVE,
            "/observation/latency_s",
        )
    )
    return rows


def missing_scores():
    return [
        {
            "population": population,
            "stage": stage,
            "mode": mode,
            "task": "appearance",
            "count": None,
            "denominator": None,
            "micro": None,
            "macro": None,
            "sources": [],
            "null": "independent query guesses: recall/FPR 1/2, precision prevalence (unknown)"
            if mode == "query_set"
            else "N/A: no universal full-record random-set null",
            "interval95": None,
            "reason": "No committed scored predictions; corpus availability is not scored evidence",
        }
        for population in ("sealed_synthetic", "real_data_transfer")
        for stage in ("raw_perception", "coordinate_consistency", "image_measurement")
        for mode in ("query_set", "full_record")
    ]
