"""Complete named-point universe under the frozen v1 predicate symmetries."""

from itertools import permutations, product
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
    result = {}
    for pred, row in REGISTRY.items():
        if not row["active"]:
            continue
        # Nondegeneracy rows explicitly allow repeats; e.g. Distinct(A,A) is false.
        tuples = (
            product(names, repeat=row["arity"])
            if row["degeneracy"] == "none"
            else permutations(names, row["arity"])
        )
        for args in tuples:
            prop = canonical_proposition({"pred": pred, "args": list(args)})
            result[(pred, tuple(prop["args"]))] = prop
    return [result[key] for key in sorted(result)]
