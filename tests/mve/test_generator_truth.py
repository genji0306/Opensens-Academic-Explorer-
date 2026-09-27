import pytest
from mve.generator.truth import build_truth, FrozenTruth, TruthError
from mve.identity import digest

COORDS = {"A": ["0", "0"], "B": ["1", "0"], "C": ["2", "0"]}
PROP = {"pred": "Collinear", "args": ["A", "B", "C"]}
GENERATOR = {"id": "fixture", "version": "v1", "config_sha256": "a" * 64, "seed": 7}


class FakeDDAR:
    version = "fake-ddar-v1"

    def __init__(self, outcome="unknown"):
        self.outcome = outcome
        self.calls = 0

    def prove(self, proposition, premises, budget_s):
        self.calls += 1
        return {
            "outcome": self.outcome,
            "trace_sha256": "b" * 64 if self.outcome == "proved" else None,
        }


def find(truth, prop=PROP):
    return next(row for row in truth.data()["candidates"] if row["proposition"] == prop)


def test_truth_math_is_independent_of_frozen_proof_refinement():
    unknown = build_truth(COORDS, [], GENERATOR, FakeDDAR(), budget_s=1)
    backend = FakeDDAR("proved")
    proved = build_truth(COORDS, [], GENERATOR, backend, budget_s=2)
    assert find(unknown)["math_class"] == find(proved)["math_class"] == "true"
    assert find(unknown)["class"] == "incidental_unproved"
    assert find(proved)["class"] == "consequence"
    assert unknown.sha256 != proved.sha256
    assert (
        unknown.data()["math_coordinates_sha256"]
        == proved.data()["math_coordinates_sha256"]
    )
    before = backend.calls
    assert (
        FrozenTruth.load(proved.payload, expected_sha256=proved.sha256).data()
        == proved.data()
    )
    assert backend.calls == before  # Loading evidence never silently reruns DDAR.
    with pytest.raises(TruthError):
        FrozenTruth.load(proved.payload + " ", expected_sha256=proved.sha256)


def test_premise_priority_unsupported_and_degeneracy():
    truth = build_truth(COORDS, [PROP], GENERATOR, FakeDDAR("unsupported"), budget_s=0)
    assert find(truth)["class"] == "premise"
    assert find(truth)["ddar"]["outcome"] == "unsupported"
    duplicate = {**COORDS, "C": ["0", "0"]}
    degenerate = build_truth(duplicate, [], GENERATOR, FakeDDAR(), budget_s=0)
    assert find(degenerate)["math_class"] == "degenerate"
    assert find(degenerate)["class"] == "unknown"


def test_false_ddar_proof_is_a_defect_and_excludes_fit():
    truth = build_truth(COORDS, [], GENERATOR, FakeDDAR("proved"), budget_s=1)
    assert truth.data()["defects"]
    assert truth.data()["fit_eligible"] is False
    with pytest.raises(TruthError, match="evaluator_conflict"):
        truth.require_fit()
    row = next(
        row for row in truth.data()["candidates"] if row["math_class"] == "false"
    )
    assert row["class"] == "evaluator_conflict"


def test_universe_and_coordinate_bytes_are_pinned():
    truth = build_truth(COORDS, [], GENERATOR, budget_s=0)
    data = truth.data()
    assert data["candidate_universe_sha256"] == digest(
        [r["proposition"] for r in data["candidates"]]
    )
    assert data["math_coordinates_sha256"] == digest(COORDS)
    assert data["generator"]["coordinates_exact"] is True
    assert data["generator"]["ddar_version"] == "unavailable:no-local-ddar"
    assert truth.require_fit() == truth.sha256
    with pytest.raises(TruthError):
        build_truth(
            COORDS, [{"pred": "NotCollinear", "args": ["A", "B", "C"]}], GENERATOR
        )


def test_e1a_frozen_truth_omits_zero_angles_and_same_segment_equalities():
    coordinates = {"A": ["0", "0"], "B": ["1", "0"], "C": ["0", "1"], "D": ["1", "1"]}
    truth = build_truth(coordinates, [], GENERATOR).data()
    for row in truth["candidates"]:
        prop = row["proposition"]
        args = prop["args"]
        if prop["pred"] == "EqualAngle":
            assert len(set(args[:3])) == len(set(args[3:])) == 3
        if prop["pred"] == "EqualLength":
            assert sorted(args[:2]) != sorted(args[2:])
    assert truth["generator"]["evaluator_version"] == "mve-algebraic-plane-v1-e1a"
    assert truth["candidate_universe_sha256"] == digest(
        [r["proposition"] for r in truth["candidates"]]
    )
    for excluded in [
        {"pred": "EqualLength", "args": list("ABBA")},
        {"pred": "EqualAngle", "args": list("ABACDC")},
    ]:
        with pytest.raises(TruthError, match="exact-true candidate"):
            build_truth(coordinates, [excluded], GENERATOR)
