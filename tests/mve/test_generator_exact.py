from itertools import combinations, combinations_with_replacement
import pytest
from mve.generator.exact import ExactEvaluator, ExactError
from mve.generator.universe import candidate_universe
from mve.predicates import canonical_proposition


@pytest.mark.parametrize(
    "predicate,coordinates,truth",
    [
        ("Collinear", [(0, 0), (1, 1), (2, 2)], "true"),
        ("Collinear", [(0, 0), (1, 1), (2, 3)], "false"),
        ("Concyclic", [(0, 0), (2, 0), (2, 2), (0, 2)], "true"),
        ("Concyclic", [(0, 0), (2, 0), (2, 2), (0, 3)], "false"),
        ("Concyclic", [(0, 0), (1, 0), (2, 0), (0, 1)], "degenerate"),
        ("Parallel", [(0, 0), (2, 0), (1, 1), (3, 1)], "true"),
        ("Parallel", [(0, 0), (2, 0), (1, 1), (3, 2)], "false"),
        ("Perpendicular", [(0, 0), (2, 0), (3, 1), (3, 3)], "true"),
        ("Perpendicular", [(0, 0), (2, 0), (3, 1), (4, 3)], "false"),
        ("EqualLength", [(0, 0), (2, 0), (1, 1), (1, 3)], "true"),
        ("EqualLength", [(0, 0), (2, 0), (1, 1), (1, 4)], "false"),
        ("Midpoint", [(1, 0), (0, 0), (2, 0)], "true"),
        ("Midpoint", [(1, 1), (0, 0), (2, 0)], "false"),
        ("SBetween", [(1, 0), (0, 0), (3, 0)], "true"),
        ("SBetween", [(4, 0), (0, 0), (3, 0)], "false"),
        ("RightAngle", [(1, 0), (0, 0), (0, 1)], "true"),
        ("RightAngle", [(1, 0), (0, 0), (1, 1)], "false"),
        ("Distinct", [(0, 0), (0, 0)], "false"),
        ("NotCollinear", [(0, 0), (1, 1), (0, 2)], "true"),
        ("NotCollinear", [(0, 0), (0, 0), (0, 2)], "false"),
        ("EqualAngle", [(1, 0), (0, 0), (1, 1), (12, 0), (10, 0), (12, 2)], "true"),
        ("EqualAngle", [(1, 0), (0, 0), (1, 1), (12, 0), (10, 0), (8, 2)], "false"),
    ],
)
def test_independent_exact_geometry_fixtures(predicate, coordinates, truth):
    names = list("ABCDEFGH")[: len(coordinates)]
    evaluator = ExactEvaluator(
        {name: list(map(str, xy)) for name, xy in zip(names, coordinates)}
    )
    assert evaluator.classify({"pred": predicate, "args": names}) == truth


def test_radicals_and_arbitrarily_close_nonincidence_are_exact():
    data = {
        "A": ["0", "0"],
        "B": ["sqrt(2)", "sqrt(2)"],
        "C": ["2*sqrt(2)", "2*sqrt(2)"],
    }
    assert (
        ExactEvaluator(data).classify({"pred": "Collinear", "args": ["A", "B", "C"]})
        == "true"
    )
    data["C"][1] = "1/100000000000000000000+2*sqrt(2)"
    assert (
        ExactEvaluator(data).classify({"pred": "Collinear", "args": ["A", "B", "C"]})
        == "false"
    )
    data["C"] = ["0", "0"]
    assert (
        ExactEvaluator(data).classify({"pred": "Collinear", "args": ["A", "B", "C"]})
        == "degenerate"
    )


@pytest.mark.parametrize("bad", ["pi", "1.5", "sqrt(-1)", "2/4"])
def test_unsupported_or_noncanonical_coordinates_are_excluded(bad):
    with pytest.raises(ExactError):
        ExactEvaluator({"A": [bad, "0"]})


def test_candidate_universe_is_complete_canonical_and_stable():
    names = list("ABCDEF")
    actual = candidate_universe(names)
    # Independently count unordered segments and unordered nonzero-arm angles.
    angles = [
        (a, b, c)
        for b in names
        for a, c in combinations_with_replacement([n for n in names if n != b], 2)
    ]
    lengths = list(combinations(names, 2))
    assert len(angles) == 90 and len(lengths) == 15
    assert sum(p["pred"] == "EqualAngle" for p in actual) == len(
        list(combinations(angles, 2))
    )
    assert sum(p["pred"] == "EqualLength" for p in actual) == len(
        list(combinations_with_replacement(lengths, 2))
    )
    assert len(actual) == 4507
    assert candidate_universe(list(reversed(names))) == actual


def test_erratum_e1_shared_points_and_excluded_duplicate_facts():
    coords = {"A": ["0", "0"], "B": ["1", "0"], "C": ["0", "1"], "D": ["1", "1"]}
    evaluator = ExactEvaluator(coords)
    isosceles = {"pred": "EqualLength", "args": ["A", "B", "A", "C"]}
    bisector = {"pred": "EqualAngle", "args": ["B", "A", "D", "D", "A", "C"]}
    candidates = candidate_universe(coords)
    for prop in (isosceles, bisector):
        assert evaluator.classify(prop) == "true"
        assert canonical_proposition(prop) in candidates
    assert (
        canonical_proposition(
            {"pred": "EqualAngle", "args": ["B", "A", "C", "C", "A", "B"]}
        )
        not in candidates
    )
    for pred in ("Parallel", "Perpendicular"):
        assert (
            canonical_proposition({"pred": pred, "args": ["A", "B", "A", "C"]})
            not in candidates
        )
    assert (
        evaluator.classify({"pred": "EqualLength", "args": ["A", "A", "B", "C"]})
        == "degenerate"
    )
    assert (
        evaluator.classify(
            {"pred": "EqualAngle", "args": ["A", "A", "B", "C", "A", "D"]}
        )
        == "degenerate"
    )
