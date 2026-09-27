"""IR from validated, explicit problem evidence; numerical measurements are never premises."""

from mve.graph import nodes, reject_hypothesis_support
from mve.predicates import canonical_proposition


def build_ir(record):
    data = record.to_dict()
    if data["domain"] != "euclidean_plane":
        raise ValueError("unsupported formal domain")
    graph = nodes(data)
    problem = data["problem"]
    for p in (
        problem["premises"]
        + problem["nondegeneracy"]
        + data["assumptions"]
        + ([problem["goal"]] if problem["goal"] else [])
    ):
        reject_hypothesis_support(p["depends_on"], graph)
    if any(b["type"] != "Point" for b in problem["binders"]):
        raise ValueError("spike supports Point binders only")
    goal = problem["goal"]
    if goal and goal["kind"] != "prove":
        raise ValueError("unsupported goal kind")

    def node(p, role):
        return {
            "proposition": canonical_proposition(p["proposition"]),
            "evidence": p["id"],
            "role": role,
            "source_refs": p["depends_on"],
        }

    premises = [
        node(p, role)
        for key, role in [
            ("premises", "hypothesis"),
            ("nondegeneracy", "nondegeneracy"),
        ]
        for p in problem[key]
        if p.get("valid", True)
    ]
    premises += [
        node(p, "hypothesis") for p in data["assumptions"] if p.get("valid", True)
    ]
    if goal and not goal.get("valid", True):
        raise ValueError("invalidated goal")
    return {
        "schema": "mve-formal-ir-v1",
        "record_id": data["record_id"],
        "revision": data["revision"],
        "content_hash": data["content_hash"],
        "binders": problem["binders"],
        "premises": premises,
        "goal": node(goal, "goal") if goal else None,
        "exact_constants": [],
    }
