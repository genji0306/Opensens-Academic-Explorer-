from itertools import permutations, product
import pytest
from mve.generator.exact import ExactEvaluator, ExactError
from mve.generator.universe import candidate_universe
from mve.predicates import REGISTRY, canonical_proposition


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
    names = ["A", "B", "C", "D", "E", "F"]
    actual = candidate_universe(names)
    expected = set()
    for pred, row in REGISTRY.items():
        if row["active"]:
            tuples = (
                product(names, repeat=row["arity"])
                if row["degeneracy"] == "none"
                else permutations(names, row["arity"])
            )
            for args in tuples:
                canonical = canonical_proposition({"pred": pred, "args": list(args)})
                expected.add((pred, tuple(canonical["args"])))
    assert {(p["pred"], tuple(p["args"])) for p in actual} == expected
    assert len(actual) == len(expected) == 517
    assert candidate_universe(list(reversed(names))) == actual
    assert any(p == {"pred": "Distinct", "args": ["A", "A"]} for p in actual)
    assert all(
        len(set(p["args"])) == len(p["args"])
        for p in actual
        if REGISTRY[p["pred"]]["category"] == "P1"
    )
