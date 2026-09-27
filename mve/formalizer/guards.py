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


def reject_hypothesis_ir(ir):
    """Defense for raw IR callers; record-built IR already checks full closure."""
    from mve.graph import reject_hypothesis_support

    items = [*ir["premises"]] + ([ir["goal"]] if ir["goal"] else [])
    graph = {
        node.get("evidence", node.get("id")): {
            "depends_on": [*node.get("source_refs", []), *node.get("depends_on", [])]
        }
        for node in items
        if node.get("evidence", node.get("id")) is not None
    }
    for node in items:
        ident = node.get("evidence", node.get("id"))
        refs = (
            ([ident] if ident is not None else [])
            + node.get("source_refs", [])
            + node.get("depends_on", [])
        )
        reject_hypothesis_support(refs, graph)
