"""Tests for verifier_gate.py and ensemble (Phase 3)."""
from __future__ import annotations

import pytest

from riemann.research.verifier_gate import (
    GateDecision,
    EnsembleResult,
    ProposalEnsemble,
    apply_verifier_gate,
)


# ---------------------------------------------------------------------------
# apply_verifier_gate — core gate logic
# ---------------------------------------------------------------------------


def test_gate_fails_when_delta_zero_and_obstruction_present() -> None:
    decision = apply_verifier_gate(
        0,
        lean_delta_decls=0,
        ensemble_results=[],
        obstruction_count=2,
    )
    assert decision.passed is False
    assert "FAIL" in decision.reason
    assert decision.lean_delta_count == 0


def test_gate_passes_when_delta_positive_despite_obstructions() -> None:
    decision = apply_verifier_gate(
        1,
        lean_delta_decls=1,
        ensemble_results=[],
        obstruction_count=5,
    )
    assert decision.passed is True
    assert decision.lean_delta_count == 1


def test_gate_passes_when_obstruction_count_zero() -> None:
    decision = apply_verifier_gate(
        2,
        lean_delta_decls=0,
        ensemble_results=[],
        obstruction_count=0,
    )
    assert decision.passed is True


def test_gate_round_index_stored() -> None:
    decision = apply_verifier_gate(
        7,
        lean_delta_decls=0,
        ensemble_results=[],
        obstruction_count=0,
    )
    assert decision.round_index == 7


def test_gate_ensemble_rejection_rate_computed() -> None:
    ensemble_results = [
        {"accepted": True},
        {"accepted": False},
        {"accepted": False},
    ]
    decision = apply_verifier_gate(
        0,
        lean_delta_decls=1,
        ensemble_results=ensemble_results,
        obstruction_count=0,
    )
    # 2 rejected out of 3 → 2/3 ≈ 0.667
    assert abs(decision.ensemble_rejection_rate - 2 / 3) < 1e-6


def test_gate_rejection_rate_zero_when_no_ensemble_results() -> None:
    decision = apply_verifier_gate(
        0,
        lean_delta_decls=1,
        ensemble_results=[],
        obstruction_count=0,
    )
    assert decision.ensemble_rejection_rate == 0.0


# ---------------------------------------------------------------------------
# GateDecision fields
# ---------------------------------------------------------------------------


def test_gate_decision_to_dict_serializable() -> None:
    import json

    decision = apply_verifier_gate(
        3,
        lean_delta_decls=2,
        ensemble_results=[{"accepted": True}],
        obstruction_count=1,
    )
    data = decision.to_dict()
    # Must be JSON-serializable.
    serialized = json.dumps(data)
    parsed = json.loads(serialized)
    assert parsed["lean_delta_count"] == 2
    assert parsed["passed"] is True


# ---------------------------------------------------------------------------
# ProposalEnsemble
# ---------------------------------------------------------------------------


def test_ensemble_rejects_empty_lean_skeleton() -> None:
    ensemble = ProposalEnsemble()
    result = ensemble.run(["-- no declarations here\n"])
    assert result.consensus == 0
    assert len(result.rejected) == 1
    assert result.total == 1


def test_ensemble_accepts_valid_lean_source() -> None:
    ensemble = ProposalEnsemble()
    source = "theorem rh_candidate_001 : True := trivial\n"
    result = ensemble.run([source])
    assert result.consensus > 0
    assert len(result.accepted) == 1


def test_ensemble_rejection_rate_calculation() -> None:
    ensemble = ProposalEnsemble()
    sources = [
        "theorem ok_1 : True := trivial\n",
        "-- nothing here\n",
        "-- also nothing\n",
    ]
    result = ensemble.run(sources)
    assert result.total == 3
    assert result.consensus == 1
    # 2 rejected out of 3.
    assert abs(result.rejection_rate() - 2 / 3) < 1e-6


def test_ensemble_rejection_rate_method_on_class() -> None:
    ensemble = ProposalEnsemble()
    sources = ["-- empty\n", "-- also empty\n"]
    ensemble.run(sources)
    assert ensemble.rejection_rate() == 1.0


def test_ensemble_result_to_dict() -> None:
    import json

    ensemble = ProposalEnsemble()
    result = ensemble.run(["theorem x : True := trivial\n"])
    data = result.to_dict()
    serialized = json.dumps(data)
    parsed = json.loads(serialized)
    assert parsed["total"] == 1
    assert parsed["consensus"] == 1
