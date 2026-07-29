"""Work-package ranking for Timeguard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.oae.studios.timeguard.schemas import (
    CampaignEvidence,
    MetricForecast,
    TimeguardContext,
    WorkPackagePrediction,
)

RANKING_WEIGHTS = {
    "unresolved_obligation_pressure": 0.35,
    "repeated_dead_end_pressure": 0.20,
    "forecasted_metric_gain": 0.20,
    "forecast_confidence": 0.15,
    "topology_fit": 0.10,
}


@dataclass(frozen=True)
class _WorkPackageCandidate:
    title: str
    why_now: str
    target_orchestrator: str
    blocking_obligations: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    expected_metric_delta: dict[str, float]
    unresolved_obligation_pressure: float
    repeated_dead_end_pressure: float
    forecasted_metric_gain: float
    forecast_confidence: float
    topology_fit: float

    @property
    def ranking_score(self) -> float:
        return (
            RANKING_WEIGHTS["unresolved_obligation_pressure"] * self.unresolved_obligation_pressure
            + RANKING_WEIGHTS["repeated_dead_end_pressure"] * self.repeated_dead_end_pressure
            + RANKING_WEIGHTS["forecasted_metric_gain"] * self.forecasted_metric_gain
            + RANKING_WEIGHTS["forecast_confidence"] * self.forecast_confidence
            + RANKING_WEIGHTS["topology_fit"] * self.topology_fit
        )

    def to_prediction(self) -> WorkPackagePrediction:
        return WorkPackagePrediction(
            title=self.title,
            why_now=self.why_now,
            target_orchestrator=self.target_orchestrator,
            expected_metric_delta=self.expected_metric_delta,
            blocking_obligations=self.blocking_obligations,
            evidence_refs=self.evidence_refs,
            confidence=min(0.95, 0.40 + 0.50 * self.forecast_confidence),
            ranking_score=self.ranking_score,
        )


def rank_work_packages(
    context: TimeguardContext,
    forecasts: tuple[MetricForecast, ...],
    *,
    top_k: int = 3,
) -> tuple[WorkPackagePrediction, ...]:
    forecast_by_id = {forecast.orchestrator_id: forecast for forecast in forecasts}
    candidates = [
        *_baseline_candidates(context.baseline, forecast_by_id[context.baseline.orchestrator_id]),
        *_klein_candidates(context.klein, forecast_by_id[context.klein.orchestrator_id]),
        _local_validation_candidate(context.baseline, forecast_by_id[context.baseline.orchestrator_id]),
        _local_validation_candidate(context.klein, forecast_by_id[context.klein.orchestrator_id]),
    ]
    candidates.sort(key=lambda item: (-item.ranking_score, item.title))
    predictions = [item.to_prediction() for item in candidates[:top_k]]
    return tuple(predictions)


def _baseline_candidates(campaign: CampaignEvidence, forecast: MetricForecast) -> list[_WorkPackageCandidate]:
    last_signal = campaign.round_signals[-1]
    tail_metric = _forecast_value(forecast, "tail_control_gap")
    best_score_metric = _forecast_value(forecast, "best_score")
    finite_window_pressure = _normalize_count(campaign.repeated_failures.get("finite_window_only", 0))
    tail_pressure = max(
        _normalize_count(campaign.repeated_failures.get("tail_control_gap", 0)),
        0.60 if "explicit_formula_tail_control" in last_signal.unresolved_obligations else 0.0,
    )
    global_pressure = _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0))
    control_plane_pressure = max(tail_pressure, min(1.0, 0.80 * finite_window_pressure))
    return [
        _WorkPackageCandidate(
            title="Strengthen explicit-formula tail control and window-escape certificates",
            why_now="Baseline keeps recycling bounded explicit-formula evidence; the next useful step is to turn tail control into a reusable exclusion-grade certificate.",
            target_orchestrator=campaign.orchestrator_id,
            blocking_obligations=("explicit_formula_tail_control",),
            evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs),
            expected_metric_delta={
                "tail_control_gap": -max(1.0, round(0.15 * max(1.0, tail_metric), 2)),
                "best_score": round(max(0.01, 0.03 * (1.0 - best_score_metric)), 4),
            },
            unresolved_obligation_pressure=control_plane_pressure,
            repeated_dead_end_pressure=finite_window_pressure,
            forecasted_metric_gain=max(0.30, min(0.95, 0.50 + 0.10 * tail_metric)),
            forecast_confidence=forecast.confidence,
            topology_fit=0.95,
        ),
        _WorkPackageCandidate(
            title="Convert baseline xi and explicit-formula checks into a global exclusion bridge",
            why_now="Baseline resolves bounded checks, but the run still stops short of a global off-line-zero exclusion argument.",
            target_orchestrator=campaign.orchestrator_id,
            blocking_obligations=("off_line_zero_exclusion", "xi_coefficient_exclusion_bridge"),
            evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs),
            expected_metric_delta={
                "global_exclusion_gap": -max(1.0, round(0.20 * max(1.0, _forecast_value(forecast, "global_exclusion_gap")), 2)),
                "best_score": round(max(0.01, 0.02 * (1.0 - best_score_metric)), 4),
            },
            unresolved_obligation_pressure=global_pressure,
            repeated_dead_end_pressure=_normalize_count(campaign.repeated_dead_ends.get("dead_end_generic_explicit_formula_restatement", 0)),
            forecasted_metric_gain=max(0.25, min(0.90, 0.40 + 0.12 * _forecast_value(forecast, "global_exclusion_gap"))),
            forecast_confidence=forecast.confidence,
            topology_fit=0.80,
        ),
    ]


def _klein_candidates(campaign: CampaignEvidence, forecast: MetricForecast) -> list[_WorkPackageCandidate]:
    last_signal = campaign.round_signals[-1]
    translation_metric = _forecast_value(forecast, "translation_gap")
    global_metric = _forecast_value(forecast, "global_exclusion_gap")
    certificate_metric = _forecast_value(forecast, "certificate_pass_rate")
    translation_pressure = _normalize_count(campaign.repeated_failures.get("translation_gap", 0))
    translation_dependency_penalty = 0.60 if translation_pressure >= 0.50 else 0.0
    phase_refs = _phase_support_refs(campaign)
    if _has_phase_reference(campaign, "phase bn"):
        return [
            _WorkPackageCandidate(
                title="Open a Phase BO character-variety topology program around the unitary locus of the Langlands local system",
                why_now=(
                    "Phase BN turns the frontier into a precise geometric problem: RH is now framed as flat positive-definite Hermitian structure on a specific GL1 local system."
                    + " The best next move is BO.1-style work on the character variety and its unitary locus instead of another generic post-BK reformulation."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("character_variety_topology_gap", "unitary_locus_closure_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -1.0,
                    "best_score": round(max(0.004, 0.01 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.98,
                repeated_dead_end_pressure=0.88,
                forecasted_metric_gain=0.89,
                forecast_confidence=forecast.confidence,
                topology_fit=1.0,
            ),
            _WorkPackageCandidate(
                title="Test restricted-class Weil positivity certificates from Phase BO without demanding full RH immediately",
                why_now=(
                    "BN isolates the Connes obstruction exactly at Weil positivity and explicitly names BO.4 as the strongest bounded route still capable of unconditional partial progress."
                    + " The practical next move is restricted-class positivity, not another all-or-nothing claim."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("restricted_weil_positivity_gap", "partial_zero_free_region_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.6,
                    "certificate_pass_rate": round(max(0.02, 0.06 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=0.84,
                repeated_dead_end_pressure=0.66,
                forecasted_metric_gain=0.76,
                forecast_confidence=forecast.confidence,
                topology_fit=0.93,
            ),
            _WorkPackageCandidate(
                title="Probe BO.2 quantum-ergodic or self-adjointness transfer only after the monodromy invariants are explicit",
                why_now=(
                    "BN keeps the Pólya-Hilbert language alive, but it is no longer the first move."
                    + " BO.2 should stay behind BO.1: quantum-ergodic or self-adjointness arguments are only useful once the monodromy and unitary-locus invariants are concrete enough to test."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("quantum_ergodicity_transfer_gap", "self_adjointness_bridge_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.3,
                    "best_score": round(max(0.002, 0.006 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.62,
                repeated_dead_end_pressure=0.58,
                forecasted_metric_gain=0.52,
                forecast_confidence=forecast.confidence,
                topology_fit=0.80,
            ),
        ]
    if _has_phase_reference(campaign, "phase bj"):
        return [
            _WorkPackageCandidate(
                title="Open a Phase BK automorphic or class-C' extension beyond BJ's ceiling theorem",
                why_now=(
                    "Phase BJ proved that the 0.999999 ceiling is structural inside the current resurgence class C."
                    + " The best next move is BK.1-style work: leave class C explicitly and test automorphic, trace-formula, or other class-C' inputs that BJ does not already prove to be bottlenecked."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("outside_class_c_bridge", "automorphic_extension_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -1.0,
                    "best_score": round(max(0.004, 0.01 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.97,
                repeated_dead_end_pressure=0.86,
                forecasted_metric_gain=0.88,
                forecast_confidence=forecast.confidence,
                topology_fit=0.99,
            ),
            _WorkPackageCandidate(
                title="Test Rankin-Selberg or modular lifts of BI/BJ Stokes data outside class C",
                why_now=(
                    "BJ.2-W1 closed the naive Stokes-arithmetic bridge, but BJ itself names BK.2 and BK.4 as the remaining worthwhile variants:"
                    + " try Rankin-Selberg or Eichler-Shimura/modular lifts of the Stokes data that escape the closed class-C route."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("stokes_lift_gap", "modular_extension_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.8,
                    "best_score": round(max(0.003, 0.008 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.90,
                repeated_dead_end_pressure=0.80,
                forecasted_metric_gain=0.79,
                forecast_confidence=forecast.confidence,
                topology_fit=0.96,
            ),
            _WorkPackageCandidate(
                title="Formalize a BK-class boundary so new routes cannot regress into BJ-closed class C",
                why_now=(
                    "Once BJ.6-R1 is on the table, a practical next step is to encode its boundary explicitly."
                    + " That keeps later exploration honest by forcing new BK candidates to show why they are outside the already-closed resurgence class."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("class_boundary_audit",),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.2,
                    "certificate_pass_rate": round(max(0.01, 0.03 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=0.48,
                repeated_dead_end_pressure=0.52,
                forecasted_metric_gain=0.43,
                forecast_confidence=forecast.confidence,
                topology_fit=0.72,
            ),
        ]
    if _has_phase_reference(campaign, "phase bi"):
        return [
            _WorkPackageCandidate(
                title="Open a Phase BJ Lambert-only resurgence program on L^{formal}(w)",
                why_now=(
                    "Phase BI reduced the late Klein program to its cleanest form: RH is now framed as analytic continuation of the resurgent Lambert series L^{formal}(w) on D_+."
                    + " The best next move is BJ.1, which works on the Lambert side directly instead of carrying the full Bernoulli/Eisenstein tower or repeating another equivalence audit."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("lambert_resurgent_cancellation", "global_exclusion_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -1.0,
                    "best_score": round(max(0.004, 0.01 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.96,
                repeated_dead_end_pressure=0.84,
                forecasted_metric_gain=0.86,
                forecast_confidence=forecast.confidence,
                topology_fit=0.99,
            ),
            _WorkPackageCandidate(
                title="Study Stokes arithmetic of the explicit c_n constants from BI.2-R1",
                why_now=(
                    "BI.2-R1 exposed the alien-derivative closure explicitly and gave concrete Stokes constants c_n = -2 pi i / [n^3 (e^{2 pi n} - 1)]."
                    + " BJ.2 is therefore the highest-signal bounded follow-up: treat those constants as arithmetic data and ask whether their relations can force a non-circular cancellation condition."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("stokes_arithmetic_gap", "resurgent_cancellation_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.8,
                    "best_score": round(max(0.003, 0.008 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.88,
                repeated_dead_end_pressure=0.78,
                forecasted_metric_gain=0.78,
                forecast_confidence=forecast.confidence,
                topology_fit=0.97,
            ),
            _WorkPackageCandidate(
                title="Formalize BI's equivalence-wall ceiling before another reformulation sweep",
                why_now=(
                    "Phase BI says the remaining 0.000001 gap will not close by more equivalent reformulations alone."
                    + " A low-cost but still useful next move is to make that ceiling explicit, so later branches are forced to justify why they are not just another RH iff X relocation."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("equivalence_wall_meta_proof",),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.2,
                    "certificate_pass_rate": round(max(0.01, 0.03 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=0.50,
                repeated_dead_end_pressure=0.52,
                forecasted_metric_gain=0.44,
                forecast_confidence=forecast.confidence,
                topology_fit=0.70,
            ),
        ]
    if _has_phase_reference(campaign, "phase ay"):
        return [
            _WorkPackageCandidate(
                title="Open a Phase AZ infinite-data integral/operator certificate program beyond AY's finite-data no-go",
                why_now=(
                    "Phase AY proved that Padé, Hankel, Prony, and finite-data rational reconstruction collapse to the same precision wall already isolated in Phase AV."
                    + " The only live Klein move left in that direction is a Phase AZ-style infinite-data certificate program that pools all coefficients at once instead of trying to localize poles from a finite Ω_k table."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("finite_data_reconstruction_wall", "infinite_data_certificate_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "best_score": round(max(0.004, 0.01 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.95,
                repeated_dead_end_pressure=0.88,
                forecasted_metric_gain=0.84,
                forecast_confidence=forecast.confidence,
                topology_fit=0.99,
            ),
            _WorkPackageCandidate(
                title="Build Weil-Guinand explicit-formula zero-sum certificates independent of coefficient asymptotics",
                why_now=(
                    "AY explicitly recommends shifting from aggregate coefficient recovery to explicit-formula zero-sums."
                    + " If Klein is going to move after the Padé/Hankel no-go, the best bounded branch is to test whether Weil-Guinand zero-sum constraints can bypass the coefficient-precision wall without falling back into the same equivalence class immediately."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("explicit_formula_zero_sum_gap", "equivalence_wall_audit"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -0.8,
                    "best_score": round(max(0.003, 0.008 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.88,
                repeated_dead_end_pressure=0.80,
                forecasted_metric_gain=0.78,
                forecast_confidence=forecast.confidence,
                topology_fit=0.96,
            ),
            _WorkPackageCandidate(
                title="Test functional-equation symmetrisation of G and the pole locus for a self-dual certificate",
                why_now=(
                    "AY identifies functional-equation symmetrisation as the other serious post-finite-data route."
                    + " That branch is still weaker than a full infinite-data certificate program, but it is more targeted than reopening another Padé or Hankel experiment that AY already closed."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("functional_equation_symmetrisation_gap", "self_dual_certificate_gap"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.4,
                    "best_score": round(max(0.002, 0.006 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.78,
                repeated_dead_end_pressure=0.70,
                forecasted_metric_gain=0.68,
                forecast_confidence=forecast.confidence,
                topology_fit=0.93,
            ),
        ]
    if _has_phase_reference(campaign, "phase av"):
        return [
            _WorkPackageCandidate(
                title="Audit the Phase AV equivalence wall for overlooked non-LP escape routes",
                why_now=(
                    "Phase AV says the known Stieltjes, Weil, Borel, Li, and de Bruijn-Newman routes all land back in the RH-equivalence class."
                    + " The best next Klein move is therefore not another Phase-AV-style asymptotic replay, but a direct audit for holes or non-LP formulations that do not factor through the same wall."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("equivalence_wall_audit", "weillike_non_lp_escape_route"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "best_score": round(max(0.004, 0.01 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.92,
                repeated_dead_end_pressure=0.86,
                forecasted_metric_gain=0.78,
                forecast_confidence=forecast.confidence,
                topology_fit=0.99,
            ),
            _WorkPackageCandidate(
                title="Search for novel G-equivalents beyond the current G1-G7 envelope",
                why_now=(
                    "AV concludes that no strictly weaker known open problem sits between the current campaign state and RH."
                    + " If Klein is going to move again, it needs a genuinely new G-equivalent or reduction target rather than another pass over the existing Li/Weil/Nyman-Beurling envelope."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("novel_equivalent_search", "equivalence_wall_escape"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -0.5,
                    "best_score": round(max(0.003, 0.008 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.88,
                repeated_dead_end_pressure=0.82,
                forecasted_metric_gain=0.76,
                forecast_confidence=forecast.confidence,
                topology_fit=0.97,
            ),
            _WorkPackageCandidate(
                title="Probe zero-density and pair-correlation bridges that could partially uncondition AV's conditional routes",
                why_now=(
                    "Phase AV explicitly leaves conditional-to-unconditional bridging as one of the few post-wall tasks still worth trying."
                    + " The realistic version is to test whether zero-density or pair-correlation inputs can be weakened without collapsing back into full RH equivalence immediately."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=("conditional_route_unconditioning", "zero_density_bridge"),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -0.5,
                    "best_score": round(max(0.002, 0.006 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
                },
                unresolved_obligation_pressure=0.82,
                repeated_dead_end_pressure=0.74,
                forecasted_metric_gain=0.72,
                forecast_confidence=forecast.confidence,
                topology_fit=0.94,
            ),
        ]
    candidates = [
        _WorkPackageCandidate(
            title="Translate Klein surface-return artifacts into exclusion-ready certificates",
            why_now=_translation_why_now(campaign),
            target_orchestrator=campaign.orchestrator_id,
            blocking_obligations=("translation_gap", "visual_or_surrogate_translation"),
            evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
            expected_metric_delta={
                "translation_gap": -max(1.0, round(0.20 * max(1.0, translation_metric), 2)),
                "certificate_pass_rate": round(max(0.02, 0.10 * (1.0 - certificate_metric)), 4),
            },
            unresolved_obligation_pressure=max(
                _normalize_count(campaign.repeated_failures.get("translation_gap", 0)),
                0.60 if "xi_coefficient_exclusion_bridge" in last_signal.unresolved_obligations else 0.0,
            ),
            repeated_dead_end_pressure=_normalize_count(campaign.repeated_failures.get("novelty_requires_translation", 0)),
            forecasted_metric_gain=max(0.35, min(0.95, 0.45 + 0.10 * translation_metric)),
            forecast_confidence=forecast.confidence,
            topology_fit=0.96,
        ),
        _WorkPackageCandidate(
            title="Force Klein cross-lane branches to return with a tighter global exclusion payload",
            why_now=_global_payload_why_now(campaign),
            target_orchestrator=campaign.orchestrator_id,
            blocking_obligations=("global_exclusion_gap", "off_line_zero_exclusion"),
            evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
            expected_metric_delta={
                "global_exclusion_gap": -max(1.0, round(0.22 * max(1.0, global_metric), 2)),
                "best_score": round(max(0.01, 0.02 * (1.0 - _forecast_value(forecast, "best_score"))), 4),
            },
            unresolved_obligation_pressure=_normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
            repeated_dead_end_pressure=max(
                0.0,
                _normalize_count(campaign.repeated_dead_ends.get("dead_end_finite_window_well_depth", 0))
                - translation_dependency_penalty,
            ),
            forecasted_metric_gain=max(0.20, min(0.70, 0.22 + 0.03 * global_metric)),
            forecast_confidence=forecast.confidence,
            topology_fit=0.30 if translation_pressure >= 0.50 else 0.98,
        ),
        _WorkPackageCandidate(
            title="Reduce Klein same-lane loops before another novelty-heavy sweep",
            why_now="Klein can still spend rounds on same-lane or translation-only artifacts; tightening that gate is cheaper than another broad novelty pass.",
            target_orchestrator=campaign.orchestrator_id,
            blocking_obligations=("klein_same_lane_loop",),
            evidence_refs=(campaign.failure_atlas_path, campaign.summary_path),
            expected_metric_delta={
                "translation_gap": -1.0,
                "certificate_pass_rate": round(max(0.01, 0.06 * (1.0 - certificate_metric)), 4),
            },
            unresolved_obligation_pressure=_normalize_count(campaign.repeated_failures.get("klein_same_lane_loop", 0)),
            repeated_dead_end_pressure=_normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
            forecasted_metric_gain=max(0.15, min(0.60, 0.22 + 0.06 * translation_metric)),
            forecast_confidence=forecast.confidence,
            topology_fit=0.60,
        ),
    ]
    if _has_phase_reference(campaign, "phase au"):
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AV Stieltjes subleading asymptotics bridge beyond AU's obstruction theorem",
                why_now=(
                    "Phase AU proved that the A+B+C+D decomposition cannot non-circularly force R(G) >= 1 on its own:"
                    + " F_A and F_D have explicit poles, F_B is formally divergent on the Stieltjes side, and the functional equation only forces the B_k + D_k cancellation without yielding the missing radius statement."
                    + " The next viable move is Phase AV: recover |gamma_{k-1}| at R_1^{-k}/2^k precision, roughly 14^k more precise than Matsuoka's bound, because that is the only missing input that would non-circularly close the G(w) radius argument."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "stieltjes_subleading_asymptotics",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -1.0,
                    "translation_gap": -1.0,
                    "certificate_pass_rate": round(max(0.03, 0.13 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_finite_window_well_depth", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_finite_window_well_depth", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                forecasted_metric_gain=max(
                    0.44,
                    min(0.92, 0.47 + 0.04 * translation_metric + 0.04 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.99,
            )
        )
    elif _has_phase_reference(campaign, "phase at"):
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AU global A+B+C+D convergence bridge for the Omega_k tail",
                why_now=(
                    "Phases AP through AT exhausted the late finite-window refinements: the Weil positivity matrix, large-n Maslanka crossover, pole statistics, Laguerre kernels, and the first exact Omega_k breakdown are now explicit"
                    + "; Phase AO already supplied the exact A+B+C+D arithmetic decomposition"
                    + ", but dead_end_finite_window_well_depth still blocks proof closure."
                    + " Phase AU should turn that decomposition into a global all-k convergence and radius-of-convergence argument for G(w)=sum Omega_k w^k instead of another finite extension capped near k<=46."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "dead_end_finite_window_well_depth",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "global_exclusion_gap": -1.0,
                    "translation_gap": -1.0,
                    "certificate_pass_rate": round(max(0.03, 0.13 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_finite_window_well_depth", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_finite_window_well_depth", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                forecasted_metric_gain=max(
                    0.44,
                    min(0.92, 0.48 + 0.04 * translation_metric + 0.04 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.99,
            )
        )
    elif _has_phase_doc(campaign, "phase ao"):
        generating_function_ready = _has_phase_doc(campaign, "phase al")
        prime_kernel_ready = _has_phase_doc(campaign, "phase an")
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AP analytic positivity bridge for G(w) and exact Omega_k kernels",
                why_now=(
                    "Phase AO gave Klein an exact Stieltjes formula for Omega_k"
                    + ("; Phase AN already exposed the Weil prime-sum kernel" if prime_kernel_ready else "")
                    + ("; and Phase AL already showed where the generating-function shortcut fails" if generating_function_ready else "")
                    + ", so the next specific move is a Phase AP bridge: turn those exact formulas into a positivity-preserving analytic or kernel argument instead of another larger finite computation."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "dead_end_lp_equivalent_reformulation",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "global_exclusion_gap": -1.0,
                    "certificate_pass_rate": round(max(0.02, 0.12 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                ),
                forecasted_metric_gain=max(
                    0.36,
                    min(0.88, 0.42 + 0.04 * translation_metric + 0.02 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.99 if prime_kernel_ready and generating_function_ready else 0.97,
            )
        )
    elif _has_phase_doc(campaign, "phase ai"):
        omega_series_ready = _has_phase_doc(campaign, "phase ae")
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AL Keiper-Li generating-function bridge from calibrated lambda_n data",
                why_now=(
                    "Phase AI turned the Li side into a second high-precision calibration route"
                    + (" and Phase AE already linked alpha_n to Omega_k and lambda_n," if omega_series_ready else ",")
                    + " so the next specific Klein move is a Phase AL program: study the analytic structure of G(w)=sum lambda_n w^n instead of extending finite positivity checks round by round."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "dead_end_lp_equivalent_reformulation",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "global_exclusion_gap": -1.0,
                    "certificate_pass_rate": round(max(0.02, 0.11 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                ),
                forecasted_metric_gain=max(
                    0.34,
                    min(0.86, 0.40 + 0.04 * translation_metric + 0.02 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.98 if omega_series_ready else 0.96,
            )
        )
    elif _has_phase_doc(campaign, "phase ac"):
        alpha_backbone_ready = _has_phase_doc(campaign, "phase ah")
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AG full Laguerre-tower bridge beyond first-order Turan control",
                why_now=(
                    "Phase AC showed that first-order Turan or Laguerre control is not enough to force universal Li positivity, "
                    + (
                        "and Phase AH restored the high-precision alpha_n backbone, "
                        if alpha_backbone_ready
                        else ""
                    )
                    + "so the next specific Klein move is a Phase AG program: test whether higher-order Laguerre tower structure can supply the missing bridge from coefficient control to systematic lambda_n positivity."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "dead_end_lp_equivalent_reformulation",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "global_exclusion_gap": -1.0,
                    "certificate_pass_rate": round(max(0.02, 0.10 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                ),
                forecasted_metric_gain=max(
                    0.32,
                    min(0.84, 0.38 + 0.04 * translation_metric + 0.02 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.97 if alpha_backbone_ready else 0.95,
            )
        )
    elif _has_phase_doc(campaign, "phase ab"):
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AC Turan-type bridge from Laguerre to Li positivity",
                why_now=(
                    "Phase AB already closed the Li normalization and finite-lambda computation path, so the next specific Klein move is a Phase AC bridge: identify what extra coefficient structure could promote first-order Laguerre control into systematic Li positivity."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "dead_end_lp_equivalent_reformulation",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "global_exclusion_gap": -1.0,
                    "certificate_pass_rate": round(max(0.02, 0.09 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                ),
                forecasted_metric_gain=max(
                    0.30,
                    min(0.82, 0.36 + 0.04 * translation_metric + 0.02 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.96,
            )
        )
    elif _has_phase_doc(campaign, "phase aa"):
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AB Li-criterion program in the Z-language",
                why_now=(
                    "Phase AA already converted the Z-language bridge into Laguerre, stability, and trace diagnostics, so the next specific Klein move is the Phase AB Li-criterion branch: turn those trace invariants into a systematic positivity program at Z=-1/4 and beyond."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "global_exclusion_gap",
                    "translation_gap",
                    "dead_end_conditional_heat_flow_monotonicity",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "global_exclusion_gap": -1.0,
                    "certificate_pass_rate": round(max(0.02, 0.09 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                forecasted_metric_gain=max(
                    0.30,
                    min(0.80, 0.35 + 0.04 * translation_metric + 0.02 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.95,
            )
        )
    elif _has_phase_doc(campaign, "phase z"):
        candidates.append(
            _WorkPackageCandidate(
                title="Open a Phase AA Laguerre and stability program for the Z-language bridge",
                why_now=(
                    "Phase Z closed the conditional heat-flow Lyapunov route cleanly, so the next specific Klein move is a Phase AA program: turn the Y/Z Hardy-Z and F(Z) bridge into Laguerre, stability, or Fredholm constraints that can attack the finite-window-to-global gap directly."
                ),
                target_orchestrator=campaign.orchestrator_id,
                blocking_obligations=(
                    "translation_gap",
                    "global_exclusion_gap",
                    "dead_end_conditional_heat_flow_monotonicity",
                ),
                evidence_refs=(campaign.failure_atlas_path, campaign.summary_path, *last_signal.evidence_refs, *phase_refs),
                expected_metric_delta={
                    "translation_gap": -1.0,
                    "global_exclusion_gap": -1.0,
                    "certificate_pass_rate": round(max(0.02, 0.08 * (1.0 - certificate_metric)), 4),
                },
                unresolved_obligation_pressure=max(
                    translation_pressure,
                    _normalize_count(campaign.repeated_failures.get("global_exclusion_gap", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                ),
                repeated_dead_end_pressure=max(
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_conditional_heat_flow_monotonicity", 0)),
                    _normalize_count(campaign.repeated_dead_ends.get("dead_end_lp_equivalent_reformulation", 0)),
                ),
                forecasted_metric_gain=max(
                    0.28,
                    min(0.78, 0.32 + 0.04 * translation_metric + 0.02 * global_metric),
                ),
                forecast_confidence=forecast.confidence,
                topology_fit=0.92,
            )
        )
    return candidates


def _local_validation_candidate(campaign: CampaignEvidence, forecast: MetricForecast) -> _WorkPackageCandidate:
    return _WorkPackageCandidate(
        title=f"Continue bounded local validation sweeps for {campaign.orchestrator_id}",
        why_now="This is the easy default, but it mostly adds more bounded evidence without reducing the repeated obstruction set.",
        target_orchestrator=campaign.orchestrator_id,
        blocking_obligations=tuple(),
        evidence_refs=(campaign.summary_path,),
        expected_metric_delta={"best_score": round(0.01 * (1.0 - _forecast_value(forecast, "best_score")), 4)},
        unresolved_obligation_pressure=0.10,
        repeated_dead_end_pressure=0.05,
        forecasted_metric_gain=0.10,
        forecast_confidence=forecast.confidence * 0.5,
        topology_fit=0.15,
    )


def _forecast_value(forecast: MetricForecast, metric: str) -> float:
    values = forecast.point_forecast.get(metric, ())
    if not values:
        return 0.0
    return float(values[-1])


def _normalize_count(value: int) -> float:
    return min(1.0, value / 20.0)


def _phase_support_refs(campaign: CampaignEvidence) -> tuple[str, ...]:
    refs = []
    for doc in campaign.support_docs:
        token_space = _normalize_phase_tokens(" ".join((doc.title, doc.path, *doc.highlights)))
        if "phase " in token_space:
            refs.append(doc.path)
    return tuple(refs)


def _translation_why_now(campaign: CampaignEvidence) -> str:
    if _has_phase_reference(campaign, "phase bn"):
        return (
            "Klein now has post-Phase-BN structure in hand: BN isolates the live problem as flat-versus-multi-valued Hermitian structure on a specific Langlands local system,"
            + " so any further translation work is only worthwhile if it sharpens character-variety invariants, restricted Weil positivity, or another BO-class proof object."
        )
    if _has_phase_reference(campaign, "phase bj"):
        return (
            "Klein now has post-Phase-BJ structure in hand: BJ proves the class-C ceiling formally,"
            + " so any further translation work is only worthwhile if it demonstrates why the new route lies outside the already-closed resurgence toolkit."
        )
    if _has_phase_reference(campaign, "phase bi"):
        return (
            "Klein now has post-Phase-BI structure in hand: BI collapses the late analytic program to a Lambert-only resurgence problem and explicit Stokes constants,"
            + " so any further translation work is only worthwhile if it moves into Lambert cancellation, Stokes arithmetic, or another genuinely non-equivalent proof object."
        )
    if _has_phase_reference(campaign, "phase bh"):
        return (
            "Klein now has post-Phase-BH structure in hand: Hecke stability, de Branges kernel norms, and the Voros-symbol reformulation are explicit,"
            + " so any further translation work is only worthwhile if it exploits those cleaner structures rather than reopening closed finite-data or multiplicative attacks."
        )
    if _has_phase_reference(campaign, "phase bg"):
        return (
            "Klein now has post-Phase-BG structure in hand: the K_0 Borel-Laplace reconstruction and the structural equivalence wall are explicit,"
            + " so any further translation work is only worthwhile if it attacks the independence gap directly rather than generating another RH iff X reformulation."
        )
    if _has_phase_reference(campaign, "phase ay"):
        return (
            "Klein now has post-Phase-AY structure in hand: AY says finite-data Padé/Hankel reconstruction is quantitatively the same wall as AV,"
            + " so any further translation work is only worthwhile if it moves into explicit-formula zero-sums, functional-equation symmetrisation, or infinite-data certificates."
        )
    if _has_phase_reference(campaign, "phase av"):
        return (
            "Klein now has post-Phase-AV structure in hand: AV says the known non-circular routes already collapse back into the RH-equivalence class,"
            + " so any further translation work is only worthwhile if it opens a genuinely new G-equivalent or exposes a hole in that reduction."
        )
    if _has_phase_reference(campaign, "phase au"):
        return (
            "Klein now has post-Phase-AU structure in hand: AU converted finite_window_well_depth into a formal obstruction theorem and isolated one remaining analytic missing input,"
            + " |gamma_{k-1}| at R_1^{-k}/2^k precision, roughly 14^k more precise than Matsuoka's bound."
        )
    if _has_phase_reference(campaign, "phase at"):
        return (
            "Klein now has post-Phase-AT structure in hand: the AP-AT analytic refinements exhausted the finite-window side of the program,"
            + " but dead_end_finite_window_well_depth still prevents those exact Omega_k, G(w), kernel, and crossover artifacts from becoming an all-k exclusion-ready certificate."
        )
    if _has_phase_doc(campaign, "phase ao"):
        return (
            "Klein now has post-Phase-AO structure in hand: exact Omega_k formulas, prime-sum lambda_n representations, and generating-function diagnostics are all explicit"
            + (
                ","
                if _has_phase_doc(campaign, "phase an") and _has_phase_doc(campaign, "phase al")
                else ","
            )
            + " but the finite-window-to-global gap still prevents those Y/Z/AA/AB/AC/AE/AI/AL/AN/AO artifacts from becoming exclusion-ready certificates."
        )
    if _has_phase_doc(campaign, "phase ai"):
        return (
            "Klein now has post-Phase-AI structure in hand: calibrated alpha_n, Omega_k, and direct high-precision lambda_n routes are all explicit"
            + (
                ", and those AE/AI checkpoints agree on the finite data,"
                if _has_phase_doc(campaign, "phase ae")
                else ","
            )
            + " but the finite-window-to-global gap still prevents those Y/Z/AA/AB/AC/AE/AI artifacts from becoming exclusion-ready certificates."
        )
    if _has_phase_doc(campaign, "phase ac"):
        return (
            "Klein now has post-Phase-AC structure in hand: Li normalization, the first-order Turan insufficiency result, and the no-negative-real-zeros lemma are explicit, "
            + (
                "and Phase AH repaired the high-precision alpha_n backbone, "
                if _has_phase_doc(campaign, "phase ah")
                else ""
            )
            + "but the finite-window-to-global gap still prevents those Y/Z/AA/AB/AC artifacts from becoming exclusion-ready certificates."
        )
    if _has_phase_doc(campaign, "phase ab"):
        return (
            "Klein now has post-Phase-AB structure in hand: Laguerre control, Li-criterion normalization, and finite lambda positivity are all explicit, but the finite-window-to-global gap still prevents those Y/Z/AA/AB artifacts from becoming exclusion-ready certificates."
        )
    if _has_phase_doc(campaign, "phase aa"):
        return (
            "Klein now has post-Phase-AA structure in hand: Laguerre positivity, stability diagnostics, and trace invariants are on the table, but the finite-window-to-global gap still prevents those Y/Z/AA artifacts from becoming exclusion-ready certificates."
        )
    if _has_phase_doc(campaign, "phase z"):
        return (
            "Klein now has a coherent Z-language from Phases Y/Z, but the finite-window-to-global gap is still preventing those mirror, Hardy-Z, and xi-bridge artifacts from closing proof obligations."
        )
    if _has_phase_doc(campaign, "phase y"):
        return (
            "Klein now carries Hardy-Z and Jensen-Pólya structure in addition to the earlier mirror/Klein-4 work, and translation pressure is still the blocker that keeps those artifacts from becoming proof-grade certificates."
        )
    return (
        "Klein already generates better cross-lane artifacts, and Phases W/X sharpened the mirror, Klein-4, and Lee-Yang structure; translation pressure is now the blocker that keeps those artifacts from closing proof obligations."
    )


def _global_payload_why_now(campaign: CampaignEvidence) -> str:
    if _has_phase_reference(campaign, "phase bn"):
        return (
            "Klein should not spend another branch on generic post-BK reformulations after BN: the next exclusion push must be BO-class work on character varieties, unitary loci, or restricted Weil positivity rather than another relabeling of the same unitarity obstruction."
        )
    if _has_phase_reference(campaign, "phase bj"):
        return (
            "Klein should not spend another branch on any route still inside class C after BJ: the ceiling theorem is now explicit, so the next exclusion push must justify why it lies in a broader class such as automorphic, trace-formula, or modular extensions."
        )
    if _has_phase_reference(campaign, "phase bi"):
        return (
            "Klein should not spend another branch on generic reformulation payloads after BI: the score ceiling is now explicit, so the next exclusion push must be Lambert-only resurgence, Stokes arithmetic, or another route that is not merely RH iff X in different notation."
        )
    if _has_phase_reference(campaign, "phase bh"):
        return (
            "Klein should not spend another branch on naive WKB, de Branges, or multiplicative D_k payloads after BH: those subroutes were cleaned up already, so the next exclusion push must exploit the remaining Lambert/resurgent or genuinely outside-C_RH structure."
        )
    if _has_phase_reference(campaign, "phase bg"):
        return (
            "Klein should not spend another branch on yet another reformulation payload after BG: the current wall is not lack of equivalences, but lack of an independently provable one."
        )
    if _has_phase_reference(campaign, "phase ay"):
        return (
            "Klein should not spend another branch on finite Padé/Hankel payloads after AY: that route is now closed as precision-equivalent to the AV wall, so the next exclusion push should be explicit-formula or infinite-data only."
        )
    if _has_phase_reference(campaign, "phase av"):
        return (
            "Klein should not spend another branch on known global-exclusion payload routes after AV: the current report says those routes already sit in the RH-equivalence class unless a genuinely new reformulation is found."
        )
    if _has_phase_reference(campaign, "phase au"):
        return (
            "Klein should not spend another branch trying to globalize A+B+C+D directly after AU: the decomposition-only route is now a proved circular obstruction, so the next exclusion push should wait for a Phase AV Stieltjes-asymptotics input."
        )
    if _has_phase_reference(campaign, "phase at"):
        return (
            "Klein has already pushed the late AP-AT refinements as far as the finite window will take them, so the next global exclusion push should wait until a Phase AU bridge globalizes the A+B+C+D Omega_k decomposition and removes the finite-window well-depth ceiling."
        )
    if _has_phase_doc(campaign, "phase ao"):
        return (
            "Klein now has stronger arithmetic-spectral formulas than it had in Phase AI, but after AL/AN/AO the global exclusion push should still wait until those exact Omega_k and prime-kernel identities are turned into a positivity-preserving analytic bridge rather than another finite-data extension."
        )
    if _has_phase_doc(campaign, "phase ai"):
        return (
            "Klein now has stronger Li-side calibration than it had in Phase AC, but after AE and AI the global exclusion push should still wait until the lambda_n and Omega_k evidence is translated into a structural analytic bridge rather than another finite-data extension."
        )
    if _has_phase_doc(campaign, "phase ac"):
        return (
            "Klein now has better structural diagnostics than it had in Phase AB, but after Phase AC the global exclusion push should still wait until the Turan-gap analysis and corrected alpha_n layer are translated into certificate-grade obligations."
        )
    if _has_phase_doc(campaign, "phase ab"):
        return (
            "Klein now has better invariants than it had in Phase AA, but even after Phase AB the global exclusion push should land only after the Laguerre and Li diagnostics are translated into certificate-grade obligations."
        )
    if _has_phase_doc(campaign, "phase aa"):
        return (
            "Klein now has better invariants than it had in Phase Z, but even after Phase AA the global exclusion push should land only after the Laguerre and trace diagnostics are translated into certificate-grade obligations."
        )
    if _has_phase_doc(campaign, "phase z"):
        return (
            "Klein is already better than baseline at cross-lane and certificate-aware search, but Phase Z closed the conditional heat-flow route, so the next global exclusion push should land only after the Y/Z bridge is translated cleanly."
        )
    return (
        "Klein is already better than baseline at cross-lane and certificate-aware search, but Phase V closed the sterile integer-surface path and the global exclusion push should land only after W/X artifacts are translated cleanly."
    )


def _has_phase_doc(campaign: CampaignEvidence, phase_label: str) -> bool:
    target = phase_label.lower()
    return any(target in _normalize_phase_tokens(f"{doc.title} {doc.path}") for doc in campaign.support_docs)


def _has_phase_reference(campaign: CampaignEvidence, phase_label: str) -> bool:
    target = phase_label.lower()
    target_code = target.split()[-1]
    for doc in campaign.support_docs:
        normalized = _normalize_phase_tokens(f"{doc.title} {doc.path}")
        tokens = set(normalized.split())
        if target in normalized or ("phase" in tokens and target_code in tokens):
            return True
        for highlight in doc.highlights:
            stripped = highlight.strip()
            if not stripped.startswith("#"):
                continue
            normalized_highlight = _normalize_phase_tokens(stripped)
            highlight_tokens = set(normalized_highlight.split())
            if target in normalized_highlight or ("phase" in highlight_tokens and target_code in highlight_tokens):
                return True
    return False


def _normalize_phase_tokens(value: str) -> str:
    return value.lower().replace("-", " ").replace("_", " ")
