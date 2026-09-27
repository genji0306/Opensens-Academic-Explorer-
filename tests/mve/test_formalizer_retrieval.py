"""Retrieval examples are bound to record images in existing frozen family splits."""

import pytest
from mve.evaluation.splits import FrozenSplit, canonical
from mve.formalizer.retrieval import examples, nearest
from mve.formalizer.ir import build_ir
from tests.mve.formalizer_fixtures import trusted_record


def split_for(record, role="retrieval"):
    roles = ["development", "retrieval", "fit", "calibration", "sealed"]
    return FrozenSplit(
        canonical(
            {
                "schema": "mve-split-v1",
                "seed": "fixture",
                "allocations": dict.fromkeys(roles, 1),
                "retired": False,
                "reason": None,
                "parent_sha256": None,
                "items": [
                    {
                        "id": record.to_dict()["image"]["sha256"] if s == role else s,
                        "family": s,
                        "split": s,
                    }
                    for s in roles
                ],
            }
        )
    )


def test_only_retrieval_family_is_available_as_examples():
    record = trusted_record()
    split = split_for(record)
    catalog = examples([record], split)
    assert nearest(build_ir(record), catalog).ir() == build_ir(record)
    assert nearest(build_ir(record), ()) is None
    for role in ["sealed", "fit", "calibration", "development"]:
        with pytest.raises(ValueError, match="retrieval"):
            examples([record], split_for(record, role))
    with pytest.raises(ValueError, match="retired"):
        examples([record], split.retire("exposed"))
    with pytest.raises(ValueError, match="duplicate"):
        examples([record, record], split)


def test_unknown_and_conflicting_origin_refused():
    record = trusted_record()
    data = split_for(record).manifest()
    data["items"][1]["id"] = "unbound"
    with pytest.raises(ValueError, match="missing"):
        examples([record], FrozenSplit(canonical(data)))


def test_truth_family_mismatch_and_evaluation_alias_refused():
    from mve.formalizer.tasks import task

    record = task("midpoint_grid", 0, 0)
    with pytest.raises(ValueError, match="conflicts"):
        examples([record], split_for(record))
    record = trusted_record()
    data = split_for(record, "sealed").manifest()
    data["allocations"]["evaluation"] = data["allocations"].pop("sealed")
    for row in data["items"]:
        if row["split"] == "sealed":
            row["split"] = "evaluation"
    with pytest.raises(ValueError, match="retrieval"):
        examples([record], FrozenSplit(canonical(data)))
