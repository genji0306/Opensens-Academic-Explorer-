"""Record-level regressions for Opus WP-1 follow-ups 1–3."""

from copy import deepcopy
import pytest
from mve.record import Record, RecordError, transition
from tests.mve.fixtures import populated
from tests.mve.test_authority import checked, proof, AT


@pytest.mark.parametrize("value", ["2/4", "sqrt(8)", "1+0"])
def test_record_rejects_noncanonical_exact_expression_before_scalar_policy(value):
    data = populated()
    data["observations"][0]["proposition"]["value_exact"] = value
    with pytest.raises(RecordError, match="noncanonical exact expression"):
        Record.from_dict(data)


@pytest.mark.parametrize("value", ["pi", "1.5", "sqrt(-1)", "1/0"])
def test_record_rejects_invalid_exact_expression(value):
    data = populated()
    data["observations"][0]["proposition"]["value_exact"] = value
    with pytest.raises(RecordError, match="invalid exact expression"):
        Record.from_dict(data)


def test_canonical_exact_value_does_not_activate_scalar_predicates():
    data = populated()
    data["observations"][0]["proposition"]["value_exact"] = "1/2"
    with pytest.raises(RecordError, match="predicates do not accept scalar values"):
        Record.from_dict(data)


def test_binder_remapping_invalidates_formal_and_evidence_closure():
    data = checked()
    data["formal"].update(status="proved", proof=proof())
    data["stage"] = "proved"
    original = Record.from_dict(data)
    edited = transition(
        original,
        "edit",
        actor="human:alice",
        expected_revision=1,
        at=AT,
        payload={
            "patch": [
                {
                    "op": "replace",
                    "path": "/problem/binders/0/entity",
                    "value": "ent_2",
                },
                {
                    "op": "replace",
                    "path": "/problem/binders/1/entity",
                    "value": "ent_1",
                },
            ]
        },
    )
    result = edited.to_dict()
    assert result["problem"]["binders"][0]["entity"] == "ent_2"
    assert result["content_hash"] == data["content_hash"]
    assert result["revision"] == 2 and result["stage"] == "ingested"
    assert result["formal"]["status"] == "none"
    expected = set("geo_1 geo_2 geo_3 obs_1 asm_1 prop_1 prop_2 tc_1 prf_1".split())
    assert set(result["events"][-1]["invalidates"]) == expected
    assert set(result["events"][-1]["touches"]) == {
        "prm_1",
        "goal_1",
        "ent_1",
        "ent_2",
        "ent_3",
    }
    assert not result["formal"]["proof"]["valid"]
    assert not result["formal"]["typecheck"]["valid"]
    assert all(not node["valid"] for node in result["formal"]["propositions"])
    assert result["sources"][0].get("valid", True)
    assert original.to_dict() == data


@pytest.mark.parametrize("dependencies", [["mea_1"], ["prm_1", "mea_1"]])
def test_derivation_cannot_promote_a_measurement_to_a_premise(dependencies):
    data = populated()
    proposition = deepcopy(data["observations"][0]["proposition"])
    data["measurements"] = [
        {
            "id": "mea_1",
            "proposition": proposition,
            "method": "coordinate_consistency",
            "kernel": "fixture",
            "outcome": "consistent",
            "residual": 0,
            "residual_unit": "px_normalized",
            "tolerance": 0.01,
            "depends_on": ["obs_1", "geo_1", "geo_2", "geo_3"],
        }
    ]
    data["derivations"] = [
        {
            "id": "der_1",
            "engine": "fixture",
            "target": proposition,
            "outcome": "proved",
            "trace_sha256": "a" * 64,
            "budget_s": 1,
            "depends_on": ["prm_1"],
        }
    ]
    Record.from_dict(
        data
    )  # Control: the record is valid before the unsupported citation.
    data["derivations"][0]["depends_on"] = dependencies
    with pytest.raises(RecordError, match="measurement is not a premise"):
        Record.from_dict(data)
