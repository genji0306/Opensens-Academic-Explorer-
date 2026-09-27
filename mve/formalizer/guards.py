"""Fail closed on missing explicit registry-required nondegeneracy hypotheses."""

from mve.degeneracy import required_nondegeneracy
from mve.predicates import canonical_proposition


def require_nondegeneracy(ir, mapping):
    def key(prop):
        canonical = canonical_proposition(prop, mapping)
        return canonical["pred"], tuple(canonical["args"])

    authorized = {
        key(n["proposition"])
        for n in ir["premises"]
        if n["proposition"]["pred"] in {"Distinct", "NotCollinear"}
    }
    nodes = [*ir["premises"]] + ([ir["goal"]] if ir["goal"] else [])
    missing = {}
    for node in nodes:
        for requirement in required_nondegeneracy(node["proposition"]):
            ident = key(requirement)
            if ident not in authorized:
                missing[ident] = (
                    requirement["pred"] + "(" + ",".join(requirement["args"]) + ")"
                )
    if missing:
        raise ValueError(
            "missing registry-required premises: " + ", ".join(sorted(missing.values()))
        )
