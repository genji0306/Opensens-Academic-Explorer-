import json
import pytest
from mve.evaluation.splits import FrozenSplit, SplitError, freeze


def items():
    return [
        {"id": f"{f}-{style}", "family": f"family-{f}"}
        for f in range(10)
        for style in ("a", "b")
    ]


def allocations():
    return {
        "development": 2,
        "retrieval": 2,
        "fit": 2,
        "calibration": 2,
        "evaluation": 2,
    }


def test_family_variants_remain_together_and_input_order_is_irrelevant():
    result = freeze(items(), seed="fixture-v1", allocations=allocations())
    assert (
        result.sha256
        == freeze(
            list(reversed(items())), seed="fixture-v1", allocations=allocations()
        ).sha256
    )
    rows = result.manifest()["items"]
    for family in {r["family"] for r in rows}:
        assert len({r["split"] for r in rows if r["family"] == family}) == 1
    assert {s: sum(r["split"] == s for r in rows) for s in allocations()} == {
        s: 4 for s in allocations()
    }


def test_hash_checked_load_and_evaluation_retirement():
    result = freeze(items(), seed="fixture", allocations=allocations())
    assert FrozenSplit.load(result.payload, expected_sha256=result.sha256) == result
    with pytest.raises(SplitError):
        FrozenSplit.load(result.payload + " ", expected_sha256=result.sha256)
    retired = result.retire("evaluation influenced tolerance fitting")
    with pytest.raises(SplitError):
        retired.require_evaluation()
    assert retired.manifest()["parent_sha256"] == result.sha256
    assert result.require_evaluation()


def test_duplicate_ids_and_invalid_allocations_are_refused():
    for rows in [[], items() + [items()[0]], [{"id": "x", "family": ""}]]:
        with pytest.raises(SplitError):
            freeze(rows, seed="fixture", allocations=allocations())
    for counts in [
        {},
        {**allocations(), "evaluation": 1},
        {**allocations(), "fit": True},
    ]:
        with pytest.raises(SplitError):
            freeze(items(), seed="fixture", allocations=counts)
    original = freeze(items(), seed="fixture", allocations=allocations())
    forged = json.loads(original.payload)
    forged["items"][0]["split"] = "unknown"
    from hashlib import sha256

    payload = json.dumps(forged)
    with pytest.raises(SplitError):
        FrozenSplit.load(payload, expected_sha256=sha256(payload.encode()).hexdigest())


def test_forged_family_leakage_and_retirement_metadata_are_refused():
    original = freeze(items(), seed="fixture", allocations=allocations())
    data = original.manifest()
    family = data["items"][0]["family"]
    variants = [r for r in data["items"] if r["family"] == family]
    variants[1]["split"] = next(s for s in allocations() if s != variants[0]["split"])
    with pytest.raises(SplitError):
        FrozenSplit(json.dumps(data))
    data = original.manifest()
    data["retired"] = True
    with pytest.raises(SplitError):
        FrozenSplit(json.dumps(data))
