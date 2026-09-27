"""WP-8a labels remain authoritative; no pseudo-labels or split reassignment."""

from mve.classifier.catalogue import catalogue
from mve.verdicts import export_labels


def label_sets(records, split):
    """Use the existing frozen family manifest, preserving all five upstream uses."""
    records = tuple(records)
    return {
        purpose: export_labels(records, split, purpose=purpose)
        for purpose in ("training", "calibration", "evaluation")
    }


def training_rows(rows):
    """Defense in depth at the training boundary; rows must be resolved WP-8a exports."""
    seen = set()
    for row in rows:
        if row["split"] != "fit":
            raise ValueError("training accepts fit only")
        kind = row["actor_kind"]
        if (
            row["schema"] != "mve-label-row-v1"
            or kind not in ("human", "model")
            or not row["actor"].startswith(kind + ":")
            or row["weight"] != (1.0 if kind == "human" else 0.5)
            or row["verdict"] != "label"
            or row["abstained"]
            or row["label"] not in catalogue()[row["question"]]["labels"]
        ):
            raise ValueError("unresolved or invalid WP-8a training target")
        key = (row["image_sha256"], row["target"], row["question"])
        if key in seen:
            raise ValueError("duplicate training target")
        seen.add(key)
    return list(rows)


def support(bundle):
    """Count unique images per class: repeated judgments cannot manufacture floors."""
    result = {}
    for qid, q in catalogue().items():
        counts = {
            split: {
                label: len(
                    {
                        r["image_sha256"]
                        for r in bundle[split]
                        if r["question"] == qid and r["label"] == label
                    }
                )
                for label in q["labels"]
            }
            for split in ("training", "calibration", "evaluation")
        }
        result[qid] = {
            "enabled": all(n >= 10 for c in counts.values() for n in c.values()),
            "counts": counts,
            "minimum_per_label_per_split": 10,
        }
    return result


def no_update(bundle):
    floors = support(bundle)
    missing = sorted(q for q, values in floors.items() if not values["enabled"])
    return {
        "decision": "no_update",
        "production_weight_refit": False,
        "reason": "spike fixture is not an activation dataset; no production promotion",
        "floor_unmet_questions": missing,
        "support": floors,
        "g2": "G2 not established",
        "gaps": [
            "independent evaluation gold and paired Opus predictions absent",
            "calibration promotion/rollback evidence absent",
            "original openJev head refit with ONNX parity absent",
        ],
        "nulls": {q: 1 / len(v["labels"]) for q, v in catalogue().items()},
        "baselines": {"majority": None, "code_only": None, "previous_lock": None},
        "accuracy": None,
        "human_queue_rate": None,
        "automatic_error_upper95": None,
    }
