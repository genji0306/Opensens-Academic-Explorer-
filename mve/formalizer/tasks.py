"""WP-2 constructions with explicit text tasks; no private candidate truth is consumed."""

from itertools import combinations
from mve.generator.constructions import construct, FAMILIES
from mve.generator.corpus import ALLOCATIONS
from mve.generator.render import render
from mve.generator.records import record_from, AT
from mve.generator.truth import build_truth
from mve.evaluation.splits import freeze, FrozenSplit, canonical
from mve.predicates import canonical_proposition
from mve.formalizer.runtime import sha
from mve.record import create


def task(family, seed, variant, split="fit"):
    construction = construct(family, seed, control="exact_positive")
    png, metadata = render(construction)
    truth = build_truth(
        {n: construction["coordinates"][n] for n in "ABC"},
        construction["premises"],
        construction["generator"],
        None,
        budget_s=0,
    )
    data = record_from(truth, png, metadata, family=family, split=split).to_dict()
    data["image"].update(track="annotated_problem", eval_task="none")
    data["image"]["isolation"]["visible"].append("stated_givens")

    data["problem"] = problem(variant)
    text = canonical(
        {"construction": construction["generator"], "problem": data["problem"]}
    )
    data["sources"] += [
        {
            "id": "txt_1",
            "kind": "text",
            "sha256": sha(text.encode()),
            "span": [0, len(text)],
            "depends_on": [],
        }
    ]
    nodes = [
        *data["problem"]["premises"],
        *data["problem"]["nondegeneracy"],
        data["problem"]["goal"],
    ]
    data["entities"] = [
        {
            "id": f"ent_{i}",
            "kind": "point",
            "label": name,
            "geometries": data["entities"][i - 1]["geometries"],
            "depends_on": [n["id"] for n in nodes if name in n["proposition"]["args"]],
        }
        for i, name in enumerate("ABC", 1)
    ]
    return create(data, AT)


def build_tasks(count=100):
    if type(count) is not int or count < 2 or count > 100:
        raise ValueError("task count must be 2..100")
    base = freeze(
        [{"id": f, "family": f} for f in FAMILIES],
        seed="mve-family-split-v1",
        allocations=ALLOCATIONS,
    )
    manifest = base.manifest()
    roles = {
        role: sorted(r["family"] for r in manifest["items"] if r["split"] == role)
        for role in ALLOCATIONS
    }
    records, rows = {}, []
    for role, families in roles.items():
        records[role] = []
        for index in range(count if role == "sealed" else len(families)):
            family = families[index % len(families)]
            record = task(family, index // len(families), index, role)
            records[role].append(record)
            rows.append(
                {
                    "id": record.to_dict()["image"]["sha256"],
                    "family": family,
                    "split": role,
                }
            )
    manifest["items"] = rows
    return records["sealed"], records["retrieval"], FrozenSplit(canonical(manifest))


def problem(variant):
    def node(ident, pred, args):
        return {
            "id": ident,
            "proposition": canonical_proposition({"pred": pred, "args": args}),
            "depends_on": ["txt_1"],
        }

    goals = [
        ("Collinear", list("ABC")),
        ("SBetween", list("CAB")),
        ("EqualLength", list("CACB")),
    ]
    goal = node("goal_1", *goals[variant % 3])
    goal["kind"] = "prove"
    return {
        "binders": [
            {"name": n, "type": "Point", "entity": f"ent_{i}"}
            for i, n in enumerate("ABC", 1)
        ],
        "premises": [node("prm_1", "Midpoint", list("CAB"))],
        "nondegeneracy": [
            node(f"ndg_{i}", "Distinct", list(pair))
            for i, pair in enumerate(combinations("ABC", 2), 1)
        ],
        "goal": goal,
    }
