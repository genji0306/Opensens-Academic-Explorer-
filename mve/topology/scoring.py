"""Denominator-explicit descriptive scores; missing predictions never disappear."""

from collections import Counter
from mve.topology.model import Diagram, TopologyError, canonical_pd


def ratio(n, d):
    return {"numerator": n, "denominator": d, "value": n / d if d else None}


def aggregate(rows, field):
    crossed = [r for r in rows if r["crossings"]]
    return {
        "micro": ratio(sum(r[field] for r in rows), sum(r["crossings"] for r in rows)),
        "macro": ratio(sum(r[field] / r["crossings"] for r in crossed), len(crossed)),
        "macro_excluded_crossing_free": len(rows) - len(crossed),
    }


def nulls(items):
    types = Counter(x.knot_type for x in items)
    chance = {x.id: 2 ** (-len(x.truth.pd)) for x in items}
    return {
        "exact_pd": None,
        "exact_pd_reason": "N/A; no general PD null",
        "orientation_complete": {
            "per_diagram": chance,
            "mean": sum(chance.values()) / len(chance) if chance else None,
            "condition": "fixed detected crossings and arc correspondence; independent sign guessing; c=0 is vacuous",
        },
        "knot_type": {
            "k": len(types),
            "uniform": 1 / len(types) if types else None,
            "majority": max(types.values()) / len(items) if types else None,
            "counts": dict(types),
        },
    }


def type_score(items, predictions):
    count = sum(predictions.get(x.id) == x.knot_type for x in items)
    value = ratio(count, len(items))
    return {
        **value,
        "micro": value.copy(),
        "macro": value.copy(),
        "unit": "one class label per diagram; micro equals diagram macro",
    }


def score(items, predictions, *, knot_types=None):
    items = tuple(items)
    ids = [x.id for x in items]
    if len(set(ids)) != len(ids) or set(predictions) - set(ids):
        raise ValueError("duplicate truth ids or unknown prediction ids")
    knot_types = knot_types or {}
    if set(knot_types) - set(ids):
        raise ValueError("unknown knot-type prediction ids")
    rows = [score_row(x, predictions.get(x.id)) for x in items]
    crossings, orientation = (
        aggregate(rows, "matched_rows"),
        aggregate(rows, "orientation_matches"),
    )
    orientation["complete"] = ratio(
        sum(r["orientation_complete"] for r in rows), len(rows)
    )
    orientation["unaligned_diagrams"] = sum(not r["orientation_aligned"] for r in rows)
    return {
        "scope": "descriptive fixture census; not G5 perception evidence",
        "exact": ratio(sum(r["exact"] for r in rows), len(rows)),
        "canonicalized": ratio(sum(r["canonicalized"] for r in rows), len(rows)),
        "complete": ratio(sum(r["complete"] for r in rows), len(rows)),
        "micro": {"unit": "crossing rows", **crossings["micro"]},
        "macro": {"unit": "diagrams with crossings", **crossings["macro"]},
        "macro_excluded_crossing_free": crossings["macro_excluded_crossing_free"],
        "orientation": orientation,
        "component_validity": ratio(sum(r["component_valid"] for r in rows), len(rows)),
        "crossing_count": ratio(
            sum(r["crossing_count_correct"] for r in rows), len(rows)
        ),
        "crossing_errors": sum(r["crossing_errors"] for r in rows),
        "knot_type": type_score(items, knot_types),
        "knot_type_unknowns": sum(x.id not in knot_types for x in items),
        "unknowns": sum(r["unknown"] for r in rows),
        "errors": dict(Counter(e for r in rows for e in r["errors"])),
        "invariant_consistency": ratio(0, 0),
        "invariant_reason": "no SnapPy invariant run; agreement would not verify transcription",
        "nulls": nulls(items),
        "interval95": None,
        "interval_reason": "public finite regression census, no sampling inference",
        "rows": rows,
    }


def shadow(row):
    """Unoriented through-strand pairs, preserving the crossing index."""
    a, b, c, d = row
    return sorted((sorted((a, c)), sorted((b, d))))


def errors(p, gold, aligned, signs):
    if p is None:
        return ["unresolved"]
    result = []
    if len(p.pd) != len(gold.pd):
        result.append("crossing_detection")
    elif not aligned:
        result.append("arc_association")
    elif signs != len(gold.pd):
        result.append("orientation")
    elif p.pd != gold.pd:
        result.append("labels")
    if len(p.components) != len(gold.components):
        result.append("traversal")
    return result


def score_row(item, prediction):
    gold = item.truth
    p = prediction if isinstance(prediction, Diagram) else None
    same_count = p is not None and len(p.pd) == len(gold.pd)
    aligned = bool(
        same_count and all(shadow(a) == shadow(b) for a, b in zip(p.pd, gold.pd))
    )
    signs = sum(a == b for a, b in zip(p.signs, gold.signs)) if aligned else 0
    component_valid = bool(p is not None and len(p.components) == len(gold.components))
    exact = bool(p is not None and p.pd == gold.pd)
    return {
        "id": item.id,
        "crossings": len(gold.pd),
        "unknown": p is None,
        "exact": exact,
        "complete": exact and component_valid,
        "canonicalized": bool(p is not None and canonical_pd(p) == canonical_pd(gold)),
        "matched_rows": sum(a == b for a, b in zip(p.pd, gold.pd)) if same_count else 0,
        "orientation_matches": signs,
        "orientation_aligned": aligned,
        "orientation_complete": bool(aligned and p.signs == gold.signs),
        "component_valid": component_valid,
        "crossing_count_correct": same_count,
        "crossing_errors": abs(len(p.pd) - len(gold.pd))
        if p is not None
        else len(gold.pd),
        "errors": [prediction.category]
        if isinstance(prediction, TopologyError)
        else errors(p, gold, aligned, signs),
    }
