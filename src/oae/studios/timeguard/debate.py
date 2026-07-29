"""Deterministic debate generation for Timeguard."""
from __future__ import annotations

from src.oae.studios.timeguard.schemas import (
    DebateTurn,
    MetricForecast,
    OrchestratorScorecard,
    TimeguardContext,
    WorkPackagePrediction,
)


class TimeguardDebate:
    """Generate a fixed-role deterministic debate over baseline vs Klein."""

    def run(
        self,
        context: TimeguardContext,
        *,
        baseline_scorecard: OrchestratorScorecard,
        klein_scorecard: OrchestratorScorecard,
        forecasts: tuple[MetricForecast, ...],
        work_packages: tuple[WorkPackagePrediction, ...],
    ) -> tuple[DebateTurn, ...]:
        forecast_by_id = {item.orchestrator_id: item for item in forecasts}
        baseline_forecast = forecast_by_id[context.baseline.orchestrator_id]
        klein_forecast = forecast_by_id[context.klein.orchestrator_id]
        low_confidence = min(baseline_forecast.confidence, klein_forecast.confidence) < 0.55

        return (
            DebateTurn(
                role="BaselineAdvocate",
                target="baseline",
                achievements=baseline_scorecard.achievements,
                remaining_work=baseline_scorecard.remaining_work,
                pros=baseline_scorecard.pros,
                cons=baseline_scorecard.cons,
                verdict=(
                    "Baseline remains the honest control branch: it is slower, but it exposes exactly where the classical proof program keeps stalling."
                ),
                evidence_refs=baseline_scorecard.evidence_refs,
                confidence=0.78,
            ),
            DebateTurn(
                role="KleinAdvocate",
                target="klein",
                achievements=klein_scorecard.achievements,
                remaining_work=klein_scorecard.remaining_work,
                pros=klein_scorecard.pros,
                cons=klein_scorecard.cons,
                verdict=(
                    "Klein is the better research engine for next-step selection because it adds cross-lane pressure and certificate discipline instead of repeating the baseline search unchanged."
                ),
                evidence_refs=klein_scorecard.evidence_refs,
                confidence=0.82,
            ),
            DebateTurn(
                role="Skeptic",
                target="both",
                achievements=(
                    "Both orchestrators stay inside explicit research-only framing and avoid pretending that the current artifacts prove RH.",
                    "Baseline is a cleaner control; Klein is a better generator of structured next-step pressure.",
                ),
                remaining_work=(
                    "Neither orchestrator has closed the global exclusion problem yet.",
                    "Both still need stronger translation from local or bounded evidence into full exclusion-ready obligations.",
                ),
                pros=(
                    "The pair together gives a useful dialectic: baseline shows what repeats, Klein shows which structural constraints improve branch quality.",
                    "The current benchmark already separates stable validation from exploratory cross-lane branching.",
                ),
                cons=(
                    "Baseline alone overfits the same finite-window / tail-control trap.",
                    "Klein alone can still overproduce translation-heavy artifacts without fully cashing them out into proof-grade exclusions.",
                ),
                verdict=(
                    "The right near-term posture is not choosing one orchestrator over the other; it is using baseline as the control plane and Klein as the intervention plane."
                ),
                evidence_refs=(
                    *baseline_scorecard.evidence_refs,
                    *klein_scorecard.evidence_refs,
                ),
                confidence=0.80,
            ),
            DebateTurn(
                role="Forecaster",
                target="both",
                achievements=(
                    f"Built a {baseline_forecast.horizon}-round forecast for both orchestrators using their primary round series plus comparable historical campaigns from the benchmark ledgers.",
                    f"Tracked best_score, certificate_pass_rate, global_exclusion_gap, tail_control_gap, translation_gap, and the top repeated dead-end counts with backend `{baseline_forecast.backend}`.",
                ),
                remaining_work=(
                    "Forecast confidence is limited by short primary histories, so the ranking must treat forecast output as advisory rather than decisive.",
                    "The main value of the forecast is directional: which obstruction family is most likely to remain sticky if the team does nothing different.",
                ),
                pros=(
                    "Forecasting makes future work packages explicit instead of leaving the next round as a vague retry.",
                    "Auxiliary campaign context prevents the model from pretending that three to four rounds are enough for high-confidence trajectory claims.",
                ),
                cons=(
                    "Primary series are still short, so uncertainty bands remain wide.",
                    "The forecast should not drive narrative claims; it only informs metric and work-package ranking.",
                ),
                verdict=(
                    "Klein is likely to stay ahead on structured branch quality, while baseline is likely to remain flatter but cleaner. "
                    + ("Confidence is low-to-moderate, so Timeguard must downweight TimesFM-style guidance in the final ranking." if low_confidence else "Confidence is moderate, so forecast guidance can influence the final ranking but should not dominate it.")
                ),
                trajectory_forecast=(
                    _trajectory_line(context.baseline.orchestrator_id, baseline_forecast, sticky_metric="tail_control_gap"),
                    _trajectory_line(context.klein.orchestrator_id, klein_forecast, sticky_metric="translation_gap"),
                ),
                evidence_refs=(
                    *baseline_forecast.evidence_refs,
                    *klein_forecast.evidence_refs,
                ),
                confidence=min(baseline_forecast.confidence, klein_forecast.confidence),
            ),
            DebateTurn(
                role="Moderator",
                target="both",
                verdict=(
                    "Timeguard recommends continuing with the paired baseline-vs-Klein setup. "
                    + ("Forecast confidence is low enough that ranking is driven mainly by repeated proof pressure and only secondarily by forecast deltas." if low_confidence else "Forecast confidence is sufficient to influence prioritization, but repeated proof pressure still dominates the final ranking.")
                ),
                next_work_packages=tuple(item.title for item in work_packages),
                trajectory_forecast=(
                    _trajectory_line(context.baseline.orchestrator_id, baseline_forecast, sticky_metric="tail_control_gap"),
                    _trajectory_line(context.klein.orchestrator_id, klein_forecast, sticky_metric="global_exclusion_gap"),
                ),
                evidence_refs=(
                    *baseline_scorecard.evidence_refs,
                    *klein_scorecard.evidence_refs,
                    *baseline_forecast.evidence_refs,
                    *klein_forecast.evidence_refs,
                ),
                confidence=min(0.90, 0.60 + 0.20 * min(baseline_forecast.confidence, klein_forecast.confidence)),
            ),
        )


def _trajectory_line(orchestrator_id: str, forecast: MetricForecast, *, sticky_metric: str) -> str:
    best_score = forecast.point_forecast.get("best_score", ())
    sticky = forecast.point_forecast.get(sticky_metric, ())
    if not best_score:
        return f"{orchestrator_id}: no trajectory forecast available."
    sticky_value = sticky[-1] if sticky else 0.0
    return (
        f"{orchestrator_id}: best_score projects to {best_score[-1]:.3f} over the next {forecast.horizon} rounds, "
        f"while {sticky_metric} remains at approximately {sticky_value:.2f} unless a targeted intervention lands."
    )
