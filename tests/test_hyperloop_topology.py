"""Tests for hyperloop_topology.py (Phase 7)."""
from __future__ import annotations

import json

import pytest

from riemann.research.hyperloop_topology import (
    HyperloopBenchmark,
    HyperloopDecision,
    HyperloopSignals,
    HyperloopTopology,
    run_hyperloop_round,
)

_VALID_AXES = frozenset({"klein", "lean", "meta", "external"})
_VALID_ACTIONS = frozenset({"continue", "replan", "escalate", "halt"})


# ---------------------------------------------------------------------------
# Hard gate 1: Lean residue
# ---------------------------------------------------------------------------


def test_lean_gate_fails_when_delta_zero_and_obstruction_present() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.80,
        lean_residue_delta=0,
        meta_closure_count=0,
        ensemble_rejection_rate=0.5,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=2)
    assert decision.hard_gate_passed is False
    assert decision.dominant_axis == "lean"
    assert decision.recommended_action == "halt"
    assert decision.proceed is False


def test_lean_gate_passes_when_delta_positive() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.60,
        lean_residue_delta=1,
        meta_closure_count=0,
        ensemble_rejection_rate=0.2,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=5)
    assert decision.hard_gate_passed is True


def test_lean_gate_passes_when_obstruction_zero_despite_empty_delta() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.70,
        lean_residue_delta=0,
        meta_closure_count=0,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    assert decision.hard_gate_passed is True


# ---------------------------------------------------------------------------
# Hard gate 2: Meta-closure escalation
# ---------------------------------------------------------------------------


def test_meta_gate_escalates_when_threshold_reached() -> None:
    topo = HyperloopTopology(meta_gate_threshold=2)
    signals = HyperloopSignals(
        klein_score=0.90,
        lean_residue_delta=3,
        meta_closure_count=2,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    assert decision.recommended_action == "escalate"
    assert decision.dominant_axis == "meta"
    assert decision.proceed is False


def test_meta_gate_does_not_fire_below_threshold() -> None:
    topo = HyperloopTopology(meta_gate_threshold=2)
    signals = HyperloopSignals(
        klein_score=0.75,
        lean_residue_delta=1,
        meta_closure_count=1,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    # meta_closure_count=1 < threshold=2 → meta gate should not fire.
    assert decision.recommended_action != "escalate"


# ---------------------------------------------------------------------------
# External falsification
# ---------------------------------------------------------------------------


def test_external_score_triggers_replan_when_below_klein() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.70,
        lean_residue_delta=1,
        meta_closure_count=0,
        ensemble_rejection_rate=0.1,
        external_score=0.50,  # 0.50 < 0.70 - 0.10 = 0.60
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    assert decision.recommended_action == "replan"
    assert decision.dominant_axis == "external"


def test_external_score_zero_does_not_trigger_external_axis() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.80,
        lean_residue_delta=2,
        meta_closure_count=0,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    assert decision.dominant_axis != "external"


# ---------------------------------------------------------------------------
# Klein tiebreaker
# ---------------------------------------------------------------------------


def test_klein_tiebreaker_continue_when_score_above_threshold() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.65,
        lean_residue_delta=1,
        meta_closure_count=0,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    assert decision.recommended_action == "continue"
    assert decision.dominant_axis == "klein"


def test_klein_tiebreaker_replan_when_score_below_threshold() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.40,
        lean_residue_delta=1,
        meta_closure_count=0,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    assert decision.recommended_action == "replan"
    assert decision.dominant_axis == "klein"


# ---------------------------------------------------------------------------
# run_hyperloop_round convenience function
# ---------------------------------------------------------------------------


def test_run_hyperloop_round_default_topology() -> None:
    signals = HyperloopSignals(
        klein_score=0.61,
        lean_residue_delta=0,
        meta_closure_count=0,
        ensemble_rejection_rate=0.5,
        external_score=0.0,
    )
    decision = run_hyperloop_round(signals, obstruction_count=3)
    assert isinstance(decision, HyperloopDecision)
    assert decision.hard_gate_passed is False  # lean gate fails: delta=0, obstruction=3


def test_run_hyperloop_round_custom_topology() -> None:
    topo = HyperloopTopology(meta_gate_threshold=5)
    signals = HyperloopSignals(
        klein_score=0.70,
        lean_residue_delta=2,
        meta_closure_count=3,
        ensemble_rejection_rate=0.0,
        external_score=0.0,
    )
    decision = run_hyperloop_round(signals, obstruction_count=0, topology=topo)
    # meta_closure_count=3 < threshold=5 → meta gate should not fire.
    assert decision.recommended_action != "escalate"


# ---------------------------------------------------------------------------
# HyperloopDecision.dominant_axis is always valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "klein_score,lean_delta,meta_count,obstruction,external",
    [
        (0.80, 1, 0, 0, 0.0),
        (0.30, 1, 0, 0, 0.0),
        (0.80, 0, 0, 3, 0.0),
        (0.80, 1, 3, 0, 0.0),
        (0.80, 1, 0, 0, 0.50),
    ],
)
def test_dominant_axis_always_valid(
    klein_score: float,
    lean_delta: int,
    meta_count: int,
    obstruction: int,
    external: float,
) -> None:
    topo = HyperloopTopology(meta_gate_threshold=2)
    signals = HyperloopSignals(
        klein_score=klein_score,
        lean_residue_delta=lean_delta,
        meta_closure_count=meta_count,
        ensemble_rejection_rate=0.0,
        external_score=external,
    )
    decision = topo.evaluate(signals, obstruction_count=obstruction)
    assert decision.dominant_axis in _VALID_AXES, (
        f"dominant_axis={decision.dominant_axis!r} not in {_VALID_AXES}"
    )
    assert decision.recommended_action in _VALID_ACTIONS


# ---------------------------------------------------------------------------
# HyperloopTopology.to_dict — JSON serializable
# ---------------------------------------------------------------------------


def test_to_dict_returns_json_serializable_dict() -> None:
    topo = HyperloopTopology()
    signals = HyperloopSignals(
        klein_score=0.60,
        lean_residue_delta=1,
        meta_closure_count=0,
        ensemble_rejection_rate=0.3,
        external_score=0.0,
    )
    decision = topo.evaluate(signals, obstruction_count=0)
    data = topo.to_dict(decision)
    serialized = json.dumps(data)
    parsed = json.loads(serialized)
    assert "dominant_axis" in parsed
    assert "recommended_action" in parsed
    assert "hard_gate_passed" in parsed
