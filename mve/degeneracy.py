"""Shared executable r5 E1a requirements, indexed by the frozen predicate registry."""

from mve.predicates import REGISTRY, canonical_proposition


def distinct_pairs(pred, args):
    return [(args[i], args[j]) for i, j in REGISTRY[pred]["distinct_arguments"]]


def repeated_degenerate(pred, args):
    return any(a == b for a, b in distinct_pairs(pred, args))


def excluded_identity(pred, args):
    if REGISTRY[pred].get("exclude_self_segment", False):
        return sorted(args[:2]) == sorted(args[2:])
    if not REGISTRY[pred]["exclude_self_angle"]:
        return False
    a, b, c, d, e, f = args
    return b == e and sorted((a, c)) == sorted((d, f))


def required_nondegeneracy(proposition):
    prop = canonical_proposition(proposition)
    args = prop["args"]
    pred = prop["pred"]
    required = [
        {"pred": "Distinct", "args": list(pair)} for pair in distinct_pairs(pred, args)
    ]
    required += [
        {"pred": "NotCollinear", "args": [args[i] for i in triple]}
        for triple in REGISTRY[pred]["noncollinear_arguments"]
    ]
    canonical = [canonical_proposition(p) for p in required]
    return list({(p["pred"], tuple(p["args"])): p for p in canonical}.values())
