from mve.degeneracy import (
    required_nondegeneracy,
    repeated_degenerate,
    excluded_identity,
)
from mve.measurement import measure


def test_e1a_requires_nonzero_segments_and_distinct_points_in_each_angle():
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


def test_e1a_angle_endpoint_pairs_are_explicit_requirements():
    required = required_nondegeneracy({"pred": "EqualAngle", "args": list("ABCDEF")})
    pairs = {tuple(p["args"]) for p in required}
    assert pairs == {
        ("A", "B"),
        ("B", "C"),
        ("A", "C"),
        ("D", "E"),
        ("E", "F"),
        ("D", "F"),
    }
    assert repeated_degenerate("EqualAngle", "ABADEF")
    assert repeated_degenerate("EqualAngle", "ABCDED")
    assert excluded_identity("EqualLength", "ABBA")
    assert not excluded_identity("EqualLength", "ABAC")


def test_e1a_coordinate_kernel_rejects_coincident_angle_endpoints():
    coords = dict(zip("ABCDEF", [[1, 0], [0, 0], [1, 0], [0, 1], [1, 1], [0, 1]]))
    result = measure(
        {"pred": "EqualAngle", "args": list("ABCDEF")},
        coords,
        width=100,
        height=100,
        tolerance=1e-9,
    )
    assert result["outcome"] == "degenerate"
