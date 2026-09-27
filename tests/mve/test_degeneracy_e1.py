from mve.degeneracy import (
    required_nondegeneracy,
    repeated_degenerate,
    excluded_identity,
)
from mve.measurement import measure


def test_e1_requires_only_nonzero_length_segments_and_angle_arms():
    assert not repeated_degenerate("EqualLength", "ABAC")
    assert (
        len(required_nondegeneracy({"pred": "EqualLength", "args": list("ABAC")})) == 2
    )
    assert not repeated_degenerate("EqualAngle", "BAD DAC".replace(" ", ""))
    assert repeated_degenerate("Parallel", "ABAC")
    assert repeated_degenerate("Perpendicular", "ABAC")
    assert excluded_identity("EqualAngle", "ABC CBA".replace(" ", ""))
    assert (
        len(required_nondegeneracy({"pred": "Concyclic", "args": list("ABCD")})) == 10
    )


def test_coordinate_kernel_respects_shared_point_registry_policy():
    coords = {"A": [0, 0], "B": [1, 0], "C": [0, 1], "D": [1, 1]}
    for pred, args in [("EqualLength", "ABAC"), ("EqualAngle", "BADDAC")]:
        result = measure(
            {"pred": pred, "args": list(args)},
            coords,
            width=100,
            height=100,
            tolerance=1e-9,
        )
        assert result["outcome"] == "consistent"
