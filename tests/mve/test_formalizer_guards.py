import pytest
from mve.formalizer import emit
from mve.degeneracy import required_nondegeneracy


def ir_for(pred, args):
    names = sorted(set(args))
    prop = {"pred": pred, "args": list(args)}
    return {
        "schema": "mve-formal-ir-v1",
        "binders": [
            {"name": n, "type": "Point", "entity": f"ent_{i}"}
            for i, n in enumerate(names, 1)
        ],
        "premises": [],
        "goal": {"proposition": prop},
        "exact_constants": [],
    }


@pytest.mark.parametrize(
    "pred,args,count",
    [
        ("Collinear", "ABC", 3),
        ("Concyclic", "ABCD", 10),
        ("Parallel", "ABCD", 6),
        ("Perpendicular", "ABCD", 6),
        ("EqualLength", "ABAC", 2),
        ("EqualAngle", "BADDAC", 3),
        ("RightAngle", "ABC", 3),
        ("SBetween", "ABC", 3),
        ("Midpoint", "CAB", 3),
    ],
)
def test_every_required_guard_must_be_an_explicit_premise(pred, args, count):
    ir = ir_for(pred, args)
    required = required_nondegeneracy(ir["goal"]["proposition"])
    assert len(required) == count
    with pytest.raises(ValueError, match="missing.*Distinct"):
        emit(ir)
    ir["premises"] = [{"proposition": p} for p in required]
    assert "def statement" in emit(ir)
    for index, requirement in enumerate(required):
        without = {
            **ir,
            "premises": ir["premises"][:index] + ir["premises"][index + 1 :],
        }
        with pytest.raises(ValueError, match="missing.*" + requirement["pred"]):
            emit(without)


def test_guards_apply_to_hypotheses_and_no_goal_inputs_too():
    ir = ir_for("Parallel", "ABCD")
    ir["premises"] = [ir["goal"]]
    ir["goal"] = None
    with pytest.raises(ValueError, match="Distinct"):
        emit(ir)


def test_equal_angle_cross_half_sharing_does_not_require_false_distinctness():
    ir = ir_for("EqualAngle", "BADDAC")
    ir["premises"] = [
        {"proposition": p} for p in required_nondegeneracy(ir["goal"]["proposition"])
    ]
    assert "EuclideanGeometry.angle" in emit(ir)
