"""Addressable nodes and dependency validation for v5 evidence records."""

from mve.errors import RecordError

COLLECTIONS = {
    "candidates": ("can",),
    "sources": ("txt", "geo"),
    "entities": ("ent",),
    "observations": ("obs",),
    "measurements": ("mea",),
    "derivations": ("der",),
    "assumptions": ("asm",),
    "judgments": ("jud",),
    "decisions": ("dec",),
}


def nodes(data):
    result = {}

    def add(node, prefixes):
        if node["id"].split("_")[0] not in prefixes or node["id"] in result:
            raise RecordError("duplicate id or wrong id prefix")
        result[node["id"]] = node

    for collection, prefixes in COLLECTIONS.items():
        for node in data.get(collection, []):
            add(node, prefixes)
    for entity in data["entities"]:
        for geometry in entity["geometries"]:
            add(geometry, ("geo",))
    for name, prefix in [("premises", "prm"), ("nondegeneracy", "ndg")]:
        for node in data["problem"][name]:
            add(node, (prefix,))
    if data["problem"]["goal"]:
        add(data["problem"]["goal"], ("goal",))
    for node in data["formal"]["propositions"]:
        add(node, ("prop",))
    for name, prefix in [
        ("typecheck", "tc"),
        ("proof", "prf"),
        ("equivalence", "eqv"),
        ("render_back", "rnd"),
    ]:
        if data["formal"].get(name):
            add(data["formal"][name], (prefix,))
    return result


def validate_graph(graph):
    done, active = set(), set()

    def visit(key):
        if key in active:
            raise RecordError("dependency cycle")
        if key in done:
            return
        active.add(key)
        node = graph[key]
        for dep in node["depends_on"]:
            if dep not in graph:
                raise RecordError("dangling dependency")
            if node.get("valid", True) and not graph[dep].get("valid", True):
                raise RecordError("valid node cites invalidated evidence")
            visit(dep)
        active.remove(key)
        done.add(key)

    for key in graph:
        visit(key)


def downstream(graph, roots):
    affected = set(roots)
    while True:
        added = {
            key for key, node in graph.items() if set(node["depends_on"]) & affected
        }
        if added <= affected:
            return affected - set(roots)
        affected |= added


def reject_hypothesis_support(refs, graph):
    """Reject hyp_N anywhere in an authorization closure, including dangling hyp ids.

    Cards deliberately remain outside schema v5. This guard also protects callers
    of individual semantic/formalization functions before whole-record validation.
    """
    pending, seen = list(refs), set()
    while pending:
        key = pending.pop()
        if key.startswith("hyp_"):
            raise RecordError("hypothesis evidence never authorizes formalization")
        if key not in seen:
            seen.add(key)
            pending.extend(graph.get(key, {}).get("depends_on", []))
