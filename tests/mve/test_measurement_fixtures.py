import math
import pytest
from mve.measurement import measure, measure_record
from mve.record import Record
from tests.mve.fixtures import populated

CASES = [
    ("Collinear", [(0, 0), (2, 0), (4, 0)], 0),
    ("Collinear", [(0, 0), (2, 0), (1, 1)], 1 / math.sqrt(20000)),
    ("Concyclic", [(0, 0), (2, 0), (2, 2), (0, 2)], 0),
    ("Parallel", [(0, 0), (2, 0), (0, 2), (2, 2)], 0),
    ("Parallel", [(0, 0), (2, 0), (3, 1), (3, 3)], 1),
    ("Perpendicular", [(0, 0), (2, 0), (3, 1), (3, 3)], 0),
    ("Perpendicular", [(0, 0), (2, 0), (0, 2), (2, 2)], 1),
    ("EqualLength", [(0, 0), (2, 0), (0, 2), (2, 2)], 0),
    ("EqualLength", [(0, 0), (2, 0), (0, 2), (3, 2)], 1 / math.sqrt(20000)),
    ("EqualAngle", [(1, 0), (0, 0), (1, 1), (4, 0), (3, 0), (4, 1)], 0),
    ("EqualAngle", [(1, 0), (0, 0), (1, 1), (4, 0), (3, 0), (2, 1)], 90),
    ("Midpoint", [(1, 0), (0, 0), (2, 0)], 0),
    ("Midpoint", [(1, 1), (0, 0), (2, 0)], 1 / math.sqrt(20000)),
    ("SBetween", [(1, 0), (0, 0), (2, 0)], 0),
    ("SBetween", [(3, 0), (0, 0), (2, 0)], 1 / math.sqrt(20000)),
    ("RightAngle", [(1, 0), (0, 0), (0, 1)], 0),
    ("RightAngle", [(1, 0), (0, 0), (1, 1)], 45),
]


def run(pred, points, tolerance=1e-10):
    names = [chr(65 + i) for i in range(len(points))]
    return measure(
        {"pred": pred, "args": names},
        dict(zip(names, points)),
        width=100,
        height=100,
        tolerance=tolerance,
    )


@pytest.mark.parametrize("pred,points,expected", CASES)
def test_independent_residual_fixtures(pred, points, expected):
    result = run(pred, points)
    assert result["residual"] == pytest.approx(expected, abs=1e-12)
    assert result["outcome"] == ("consistent" if expected <= 1e-10 else "inconsistent")
    assert result["method"] == "coordinate_consistency"
    assert result["kernel"].startswith("numpy:")


@pytest.mark.parametrize("pred,points,_", CASES)
def test_similarity_invariance(pred, points, _):
    names = [chr(65 + i) for i in range(len(points))]
    changed = {name: [500 - 7 * y, 300 + 7 * x] for name, (x, y) in zip(names, points)}
    result = measure(
        {"pred": pred, "args": names}, changed, width=700, height=700, tolerance=1e-10
    )
    assert result["residual"] == pytest.approx(run(pred, points)["residual"], abs=1e-10)


def test_degenerate_near_degenerate_and_unmeasurable_are_not_consistency():
    assert run("Collinear", [(0, 0), (0, 0), (2, 2)])["outcome"] == "degenerate"
    assert run("Collinear", [(0, 0), (1e-9, 0), (2, 2)])["outcome"] == "near_degenerate"
    assert run("Concyclic", [(0, 0), (1, 0), (2, 0), (0, 1)])["outcome"] == "degenerate"
    assert (
        run("Collinear", [(0, 0), (1, 0), (float("nan"), 1)])["outcome"]
        == "unmeasurable"
    )
    with pytest.raises(ValueError):
        run("EqualLength", [(0, 0), (1, 0), (2, 2), (3, 3)], -1)


def test_record_measurement_names_exact_geometry_and_never_promotes_premises():
    original = Record.from_dict(populated())
    prop = {"pred": "Collinear", "args": ["ent_1", "ent_2", "ent_3"]}
    measured = measure_record(
        original, prop, geometry_ids=["geo_1", "geo_2", "geo_3"], tolerance=1e-8
    )
    data = measured.to_dict()
    assert data["stage"] == "measured"
    assert data["measurements"][0]["depends_on"] == ["geo_1", "geo_2", "geo_3"]
    assert data["problem"] == original.to_dict()["problem"]
    assert data["derivations"] == data["assumptions"] == []
    assert data["measurements"][0]["uncertainty"] is None
    with pytest.raises(ValueError):
        measure_record(original, prop, geometry_ids=["geo_1", "geo_2"], tolerance=1e-8)


@pytest.mark.parametrize(
    "pred,points,expected",
    [
        ("Distinct", [(0, 0), (1, 0)], "consistent"),
        ("Distinct", [(0, 0), (0, 0)], "inconsistent"),
        ("NotCollinear", [(0, 0), (1, 0), (0, 1)], "consistent"),
        ("NotCollinear", [(0, 0), (1, 0), (2, 0)], "inconsistent"),
    ],
)
def test_nondegeneracy_indicator_contract(pred, points, expected):
    assert run(pred, points, tolerance=0)["outcome"] == expected
    with pytest.raises(ValueError):
        run(pred, points, tolerance=1)


def test_ground_truth_coordinates_can_be_measured_without_truth_access():
    from tests.mve.test_authority import synthetic

    data = synthetic()
    data["entities"] = populated()["entities"]
    for entity in data["entities"]:
        entity["depends_on"] = []
        entity["geometries"][0].update(
            source="ground_truth", depends_on=[entity["id"], "geo_100"]
        )
    result = measure_record(
        Record.from_dict(data),
        {"pred": "Collinear", "args": ["ent_1", "ent_2", "ent_3"]},
        geometry_ids=["geo_1", "geo_2", "geo_3"],
        tolerance=1e-8,
    )
    assert result.to_dict()["measurements"][0]["outcome"] == "consistent"
    assert result.to_dict()["provenance"]["perceiver_calls"] == 0


def test_missing_geometry_and_numerical_tolerance_boundary():
    prop = {"pred": "Midpoint", "args": ["A", "B", "C"]}
    coords = {"A": [1, 1], "B": [0, 0], "C": [2, 0]}
    value = measure(prop, coords, width=100, height=100, tolerance=0)["residual"]
    assert (
        measure(prop, coords, width=100, height=100, tolerance=value)["outcome"]
        == "consistent"
    )
    assert (
        measure(
            prop, coords, width=100, height=100, tolerance=math.nextafter(value, 0)
        )["outcome"]
        == "inconsistent"
    )
    assert measure(prop, {}, width=100, height=100, tolerance=0)["residual"] is None
    with pytest.raises(ValueError):
        measure(prop, coords, width=0, height=100, tolerance=0)
    assert (
        run("Concyclic", [(0, 0), (2, 0), (2, 2), (0, 3)])["outcome"] == "inconsistent"
    )


def test_drawn_coordinates_can_disagree_with_a_trusted_given():
    data = populated()
    data["entities"][2]["geometries"][0]["params"] = [30, 40]
    result = measure_record(
        Record.from_dict(data),
        {"pred": "Collinear", "args": ["ent_1", "ent_2", "ent_3"]},
        geometry_ids=["geo_1", "geo_2", "geo_3"],
        tolerance=1e-8,
    ).to_dict()
    assert result["measurements"][0]["outcome"] == "inconsistent"
    assert result["problem"]["premises"] == data["problem"]["premises"]
