"""Complete named-point universe under the frozen v1 predicate symmetries."""

from itertools import product
from functools import lru_cache
from mve.degeneracy import repeated_degenerate, excluded_identity
import re
from mve.predicates import REGISTRY, canonical_proposition


def candidate_universe(names):
    names = list(names)
    if not names or len(names) > 8 or len(set(names)) != len(names):
        raise ValueError("need 1..8 unique named points")
    if any(
        not isinstance(n, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}", n)
        for n in names
    ):
        raise ValueError("invalid point name")
    names = sorted(names)
    return [
        {"pred": pred, "args": list(args)} for pred, args in _universe(tuple(names))
    ]


@lru_cache(maxsize=32)
def _universe(names):
    result = set()
    for pred, row in REGISTRY.items():
        if not row["active"]:
            continue
        for args in product(names, repeat=row["arity"]):
            if repeated_degenerate(pred, args) or excluded_identity(pred, args):
                continue
            prop = canonical_proposition({"pred": pred, "args": list(args)})
            result.add((pred, tuple(prop["args"])))
    return tuple(sorted(result))
