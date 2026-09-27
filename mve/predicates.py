"""Frozen P1 predicate canonicalization; target expressions are not compiled proofs."""

from itertools import permutations, product
import json
from pathlib import Path
from mve.errors import RecordError

REGISTRY = json.loads(
    (Path(__file__).parent / "registry/predicates_v1.json").read_text()
)["predicates"]


def orders(args, symmetry):
    if symmetry.startswith("S"):
        return permutations(args)
    if symmetry == "endpoints":
        return [args, [args[0], args[2], args[1]]]
    if symmetry == "angle":
        return [args, list(reversed(args))]
    if symmetry in ("pairs", "angles"):
        n = 2 if symmetry == "pairs" else 3
        left, right = args[:n], args[n:]
        variants = []
        for a, b in product([left, left[::-1]], [right, right[::-1]]):
            variants.extend([a + b, b + a])
        return variants
    return [args]


def canonical_proposition(prop, mapping=None):
    row = REGISTRY.get(prop["pred"])
    if row is None or not row["active"]:
        raise RecordError("unsupported predicate")
    if any(prop.get(k) is not None for k in ("value", "value_exact", "unit")):
        raise RecordError("active predicates do not accept scalar values")
    args = [(mapping or {}).get(a, a) for a in prop["args"]]
    if len(args) != row["arity"]:
        raise RecordError("wrong predicate arity")
    result = {**prop, "args": list(min(orders(args, row["symmetry"])))}
    return result
