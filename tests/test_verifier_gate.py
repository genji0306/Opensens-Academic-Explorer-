"""Tests for verifier_gate.py and ensemble (Phase 3)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from riemann.research.d_phi_disruption_metric import score_research_dir
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


# ---------------------------------------------------------------------------
# D_phi obligation-adjusted metric
# ---------------------------------------------------------------------------


def _write_d_phi_campaign(tmp_path: Path, *, rh_proof_claim: bool) -> Path:
    research_dir = tmp_path / "data" / "riemann" / "research"
    campaign_dir = research_dir / "rh-disruptive-tail-reduction"
    lean_dir = tmp_path / "lean" / "RH"
    campaign_dir.mkdir(parents=True)
    lean_dir.mkdir(parents=True)

    (lean_dir / "TailReduction.lean").write_text(
        "def uniform_tail_recombination_budget_reduction : True := True.intro\n",
        encoding="utf-8",
    )
    (campaign_dir / "summary.json").write_text(
        json.dumps({"campaign_id": "rh-disruptive-tail-reduction", "best_score": 0.956}),
        encoding="utf-8",
    )
    (campaign_dir / "certificate_report.json").write_text(
        json.dumps(
            {
                "candidate_reports": [
                    {
                        "open_obligation_classes": [
                            "analytic_xi_bridge_theorem",
                            "global_off_line_exclusion_theorem",
                            "uniform_tail_recombination_theorem",
                        ],
                        "core_obligation_reduction_evidence": [
                            {
                                "core_obligation": "uniform_tail_recombination_theorem",
                                "reduced_to": "weil_guinand_tail_budget_certificate",
                                "mechanical_check": "mock_lean_bridge_decl_present",
                                "lean_path": "lean/RH/TailReduction.lean",
                                "lean_declaration": "uniform_tail_recombination_budget_reduction",
                                "rh_proof_claim": rh_proof_claim,
                            }
                        ],
                        "lane_reports": [
                            {
                                "check_id": "d_phi_formalization",
                                "passed": True,
                                "metrics": {"threshold_gap": 0.0},
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return research_dir


def test_d_phi_metric_promotes_evidence_backed_core_reduction(tmp_path: Path) -> None:
    metric = score_research_dir(_write_d_phi_campaign(tmp_path, rh_proof_claim=False))

    assert metric.score == 0.956
    assert metric.reduced_core_obligations == ("uniform_tail_recombination_theorem",)
    assert len(metric.open_core_obligations) == 2


def test_d_phi_metric_rejects_reduction_with_rh_proof_claim(tmp_path: Path) -> None:
    metric = score_research_dir(_write_d_phi_campaign(tmp_path, rh_proof_claim=True))

    assert metric.score == 0.949
    assert metric.reduced_core_obligations == ()
    assert len(metric.open_core_obligations) == 3
