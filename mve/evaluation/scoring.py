"""Binary relation scorers with frozen denominators and separate tasks/modes."""

from statistics import mean

TASKS = {"appearance", "annotation_reading", "problem_understanding"}
METRICS = (
    "accuracy",
    "precision",
    "recall",
    "fpr",
    "coverage",
    "negative_error_or_missing_rate",
)


class ScoreError(ValueError):
    pass


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def validate(gold, predictions, mode, task):
    if mode not in {"query_set", "full_record"} or task not in TASKS:
        raise ScoreError("one declared task and scoring mode required")
    if not isinstance(gold, dict) or not gold or not isinstance(predictions, dict):
        raise ScoreError("nonempty gold and prediction mappings required")
    if set(predictions) - set(gold):
        raise ScoreError("prediction diagrams outside frozen set")
    for diagram, queries in gold.items():
        if (
            not isinstance(diagram, str)
            or not diagram
            or not isinstance(queries, dict)
            or not queries
        ):
            raise ScoreError("nonempty diagram and query ids required")
        if any(
            not isinstance(q, str) or not q or type(v) is not bool
            for q, v in queries.items()
        ):
            raise ScoreError("gold must contain exact binary labels")


def answers(queries, prediction, mode):
    if prediction is None or isinstance(prediction, str):
        return {}, "missing_or_failed"
    if mode == "full_record":
        if not isinstance(prediction, list) or any(
            not isinstance(q, str) for q in prediction
        ):
            return {}, "malformed"
        if len(set(prediction)) != len(prediction) or set(prediction) - set(queries):
            return {}, "malformed"
        return {q: q in prediction for q in queries}, "valid"
    if not isinstance(prediction, dict) or set(prediction) - set(queries):
        return {}, "malformed"
    if any(
        type(value) is not bool and value is not None for value in prediction.values()
    ):
        return {}, "malformed"
    return prediction, "valid"


def counts(queries, prediction):
    result = dict.fromkeys(
        (
            "queries",
            "positives",
            "negatives",
            "tp",
            "fp",
            "tn",
            "fn",
            "unanswered",
            "negative_unanswered",
            "correct",
        ),
        0,
    )
    for query, truth in queries.items():
        result["queries"] += 1
        result["positives" if truth else "negatives"] += 1
        answer = prediction.get(query)
        if answer is None:
            result["unanswered"] += 1
            result["negative_unanswered"] += not truth
            continue
        result[
            "tp" if truth and answer else "fn" if truth else "fp" if answer else "tn"
        ] += 1
        result["correct"] += answer == truth
    return result


def metrics(c):
    return {
        **c,
        "accuracy": ratio(c["correct"], c["queries"]),
        "precision": ratio(c["tp"], c["tp"] + c["fp"]),
        "recall": ratio(c["tp"], c["positives"]),
        "fpr": ratio(c["fp"], c["negatives"]),
        "coverage": ratio(c["queries"] - c["unanswered"], c["queries"]),
        "negative_error_or_missing_rate": ratio(
            c["fp"] + c["negative_unanswered"], c["negatives"]
        ),
    }


def macro(rows):
    result = {"diagrams": len(rows), "metric_diagrams": {}}
    for name in METRICS:
        values = [row[name] for row in rows.values() if row[name] is not None]
        result[name] = mean(values) if values else None
        result["metric_diagrams"][name] = len(values)
    return result


def all_positive_baseline(gold):
    rows = {
        diagram: metrics(counts(queries, dict.fromkeys(queries, True)))
        for diagram, queries in gold.items()
    }
    totals = {key: sum(row[key] for row in rows.values()) for key in counts({}, {})}
    return {"micro": metrics(totals), "macro": macro(rows)}


def score(gold, predictions, *, mode, task):
    validate(gold, predictions, mode, task)
    rows, outcomes = {}, {}
    exact = 0
    for diagram, queries in gold.items():
        prediction, outcome = answers(queries, predictions.get(diagram), mode)
        rows[diagram] = metrics(counts(queries, prediction))
        outcomes[diagram] = outcome
        exact += outcome == "valid" and all(
            prediction.get(q) is v for q, v in queries.items()
        )
    totals = {key: sum(row[key] for row in rows.values()) for key in counts({}, {})}
    prevalence = ratio(totals["positives"], totals["queries"])
    null = {
        "description": "Independent fair binary guesses per frozen query"
        if mode == "query_set"
        else "N/A: full-record output has no universal random-set distribution",
        "micro": {"precision": prevalence, "recall": 0.5, "fpr": 0.5, "accuracy": 0.5},
        "macro": {
            "precision": mean(r["positives"] / r["queries"] for r in rows.values()),
            "recall": 0.5,
            "fpr": 0.5,
            "accuracy": 0.5,
        },
    }
    if mode == "full_record":
        null["micro"] = null["macro"] = None
    return {
        "scorer_version": "mve-binary-v1",
        "mode": mode,
        "task": task,
        "micro": metrics(totals),
        "macro": macro(rows),
        "diagrams": rows,
        "outcomes": outcomes,
        "null": null,
        "full_record_exact": exact if mode == "full_record" else None,
        "all_positive_baseline": all_positive_baseline(gold),
        "gate_status": "not_evaluated: confidence bounds and sampling design required",
    }
