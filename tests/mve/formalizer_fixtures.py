"""Explicit trusted nondegeneracy for the three distinct fixture points."""

from itertools import combinations
from tests.mve.fixtures import populated
from mve.record import create
from mve.predicates import canonical_proposition


def trusted_data():
    data = populated()
    data["problem"]["nondegeneracy"] = [
        {
            "id": f"ndg_{i}",
            "proposition": {"pred": "Distinct", "args": list(pair)},
            "depends_on": ["txt_1"],
        }
        for i, pair in enumerate(combinations("ABC", 2), 1)
    ]
    for entity in data["entities"]:
        entity["depends_on"] += [
            n["id"]
            for n in data["problem"]["nondegeneracy"]
            if entity["label"] in n["proposition"]["args"]
        ]
    return data


def trusted_record():
    return create({**trusted_data(), "stage": "ingested"}, "2026-09-27T00:00:00Z")


def guarded_ir(ir):
    # Tests supply explicit pairwise hypotheses; no production autofill.
    names = [b["name"] for b in ir["binders"]]
    ir["premises"] += [
        {"proposition": canonical_proposition({"pred": "Distinct", "args": list(pair)})}
        for pair in combinations(names, 2)
    ]
    return ir
