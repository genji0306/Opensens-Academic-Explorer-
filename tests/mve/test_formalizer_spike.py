import json
import pytest
from mve.record import Record, create
from mve.formalizer import build_ir, emit
from tests.mve.fixtures import populated


def test_ir_only_uses_explicit_authorized_problem_statements():
    record = Record.from_dict(populated())
    ir = build_ir(record)
    assert ir["record_id"] == record.to_dict()["record_id"]
    assert [p["evidence"] for p in ir["premises"]] == ["prm_1"]
    assert ir["goal"]["evidence"] == "goal_1"
    assert "measurements" not in ir
    source = emit(ir)
    assert source == emit(json.loads(json.dumps(ir)))
    assert "def statement : Prop :=" in source
    assert "Collinear ℝ ({p0,p1,p2} : Set Point)" in source
    assert "sorry" not in source and "axiom" not in source
    assert "theorem" not in source


def test_no_goal_emits_assumptions_only_and_names_cannot_inject_code():
    data = populated()
    data["problem"]["goal"] = None
    for entity in data["entities"]:
        entity["depends_on"] = ["prm_1"]
    data["problem"]["binders"][0]["name"] = "theorem"
    data["problem"]["premises"][0]["proposition"]["args"][0] = "theorem"
    from mve.predicates import canonical_proposition

    data["problem"]["premises"][0]["proposition"] = canonical_proposition(
        data["problem"]["premises"][0]["proposition"]
    )
    record = create({**data, "stage": "ingested"}, "2026-09-27T00:00:00Z")
    source = emit(build_ir(record))
    assert "def assumption_0" in source
    assert "def statement" not in source
    assert "theorem" not in source


def test_unsupported_ir_and_binders_fail_closed():
    ir = build_ir(Record.from_dict(populated()))
    ir["premises"][0]["proposition"]["pred"] = "Tangency"
    with pytest.raises(ValueError):
        emit(ir)
    ir = build_ir(Record.from_dict(populated()))
    ir["binders"][0]["type"] = "Circle"
    with pytest.raises(ValueError):
        emit(ir)


def test_leangeo_interface_cannot_claim_integration():
    from mve.formalizer.leangeo import UnavailableLeanGeo

    result = UnavailableLeanGeo().translate(build_ir(Record.from_dict(populated())))
    assert result["status"] == "unsupported"
    assert result["statement"] is None
    assert result["integration_checked"] is False


def test_binder_name_takes_precedence_over_entity_alias():
    ir = build_ir(Record.from_dict(populated()))
    ir["binders"][0].update(name="ent_2", entity="ent_1")
    ir["premises"][0]["proposition"] = {"pred": "Midpoint", "args": ["ent_2", "B", "C"]}
    ir["goal"] = None
    assert "p0 = midpoint ℝ p1 p2" in emit(ir)
