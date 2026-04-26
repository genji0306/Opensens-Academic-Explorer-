"""Observer Studio — blind evaluation + diagnostic routing.

The Observer is the only module that is allowed to read the hidden
label vault. It takes the orchestrator's predictions for a round,
compares them to the true concentrations, and emits:

1. An :class:`ObserverReport` with per-sample error, MAPE, and the
   overall observer score (a composite of accuracy and coverage).
2. A :class:`~src.oae.kernel.schemas.VerificationBundle` built from
   labeling functions that encode the Observer's diagnostic rules.
   This is the hand-off point to the Phase E Snorkel verifier:
   because the bundle is schema-compatible, swapping in the real
   label model is a one-line change.
3. A :class:`RoutingDecision` naming which node of the five-node
   topology should be updated next. The decision is *deterministic*
   given the Observer's rules — ambiguous routing is a design failure.

Five possible routing targets:

* ``"model"`` — predictions are systematically biased but signal
  features look fine → redesign the predictive model.
* ``"signal"`` — feature quality is degraded (low SNR, anomalies) →
  re-run Agent ER with different baseline / feature strategy.
* ``"priors"`` — predictions agree with signal but disagree with
  theory (e.g. peak at the wrong potential) → revisit Agent AR.
* ``"experiment"`` — error is concentrated at under-covered conditions
  → Agent LS expands the plan.
* ``"stop"`` — acceptance criteria reached.

Each target maps one-to-one to a sensing-studio module, so the
orchestrator's ``dispatch_routing`` hook is a flat switch.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from src.oae.kernel.schemas import (
    LabelModelPosterior,
    LFOutput,
    VerificationBundle,
)
from src.oae.studios.sensing_studio.model.predictive import PredictiveOutput
from src.oae.studios.sensing_studio.session import (
    HiddenLabelVault,
    RoutingRecord,
)
from src.oae.studios.sensing_studio.signal.analyzer import SignalFeatures

RoutingTarget = Literal["model", "signal", "priors", "experiment", "stop"]

ACTOR_ID = "observer"


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObserverReport:
    """Per-sample diagnostic result produced by :meth:`ObserverStudio.evaluate`."""

    round_index: int
    n_samples: int
    mape: float
    rmse_uM: float
    observer_score: float
    per_sample_error: dict[str, float] = field(default_factory=dict)
    mean_signal_snr_db: float = 0.0
    signal_anomaly_fraction: float = 0.0
    theory_alignment: float = 0.0
    contradiction_penalty: float = 0.0


@dataclass(frozen=True)
class RoutingDecision:
    """Observer routing decision for the next recursive round."""

    target: RoutingTarget
    reason: str
    observer_score: float


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------


@dataclass
class ObserverStudio:
    """Blind evaluator and routing engine.

    Parameters
    ----------
    acceptance_mape:
        MAPE (mean absolute percentage error) at or below which the
        Observer emits ``"stop"``. Default 5 % matches the binding
        acceptance criterion in §11 of the phase plan.
    min_snr_db:
        SNR threshold below which the Observer routes to signal
        analysis.
    min_theory_alignment:
        Theory alignment below which the Observer routes to priors
        when predictions and signal look acceptable.
    min_coverage_per_condition:
        Minimum fraction of conditions that must appear in the round
        before the Observer considers routing to experiment design.
    """

    acceptance_mape: float = 0.05
    min_snr_db: float = 6.0
    min_theory_alignment: float = 0.25
    min_coverage_per_condition: float = 0.5

    # --- public API ---------------------------------------------------

    def evaluate(
        self,
        *,
        round_index: int,
        predictions: Sequence[PredictiveOutput],
        signal_features: Sequence[SignalFeatures],
        signal_summary: Mapping[str, float],
        prior_summary: Mapping[str, float],
        vault: HiddenLabelVault,
    ) -> tuple[ObserverReport, VerificationBundle, RoutingDecision]:
        """Run a full blind evaluation for one round.

        Returns the diagnostic report, a Snorkel-compatible
        verification bundle, and the routing decision for the next
        round. The call is the *only* place in the system that calls
        ``vault.reveal_all(actor="observer")``.
        """
        truth = vault.reveal_all(actor=ACTOR_ID)

        errors: dict[str, float] = {}
        percent_errors: list[float] = []
        squared: list[float] = []
        for pred in predictions:
            if pred.sample_id not in truth:
                continue
            true_v = truth[pred.sample_id]
            err = pred.predicted_concentration_uM - true_v
            errors[pred.sample_id] = err
            squared.append(err * err)
            if true_v > 0:
                percent_errors.append(abs(err) / true_v)

        n_samples = len(errors)
        mape = sum(percent_errors) / len(percent_errors) if percent_errors else 1.0
        rmse = math.sqrt(sum(squared) / len(squared)) if squared else 0.0

        observer_score = self._observer_score(
            mape=mape,
            signal_summary=signal_summary,
            prior_summary=prior_summary,
            coverage=self._coverage(signal_features),
        )

        report = ObserverReport(
            round_index=round_index,
            n_samples=n_samples,
            mape=mape,
            rmse_uM=rmse,
            observer_score=observer_score,
            per_sample_error=errors,
            mean_signal_snr_db=float(signal_summary.get("mean_snr_db", 0.0)),
            signal_anomaly_fraction=float(
                signal_summary.get("anomaly_fraction", 0.0)
            ),
            theory_alignment=float(prior_summary.get("theory_alignment", 0.0)),
            contradiction_penalty=float(
                prior_summary.get("contradiction_penalty", 0.0)
            ),
        )

        bundle = self._build_verification_bundle(
            round_index=round_index,
            report=report,
            signal_summary=signal_summary,
            prior_summary=prior_summary,
        )
        decision = self._route(report)
        return report, bundle, decision

    def to_routing_record(
        self,
        round_index: int,
        decision: RoutingDecision,
    ) -> RoutingRecord:
        return RoutingRecord(
            round_index=round_index,
            target=decision.target,
            reason=decision.reason,
            observer_score=decision.observer_score,
        )

    # --- scoring ------------------------------------------------------

    def _observer_score(
        self,
        *,
        mape: float,
        signal_summary: Mapping[str, float],
        prior_summary: Mapping[str, float],
        coverage: float,
    ) -> float:
        accuracy = max(0.0, 1.0 - min(1.0, mape))
        signal = max(0.0, min(1.0, float(signal_summary.get("mean_snr_db", 0.0)) / 20.0))
        signal *= 1.0 - float(signal_summary.get("anomaly_fraction", 0.0))
        theory = float(prior_summary.get("theory_alignment", 0.0))
        return max(
            0.0,
            min(
                1.0,
                0.55 * accuracy
                + 0.20 * signal
                + 0.15 * theory
                + 0.10 * coverage,
            ),
        )

    def _coverage(self, features: Sequence[SignalFeatures]) -> float:
        if not features:
            return 0.0
        # Condition id is encoded in the sample id as the middle segment
        # (`r{round}_c{cond}_s{sample}`); extract uniquely.
        conditions: set[str] = set()
        for f in features:
            parts = f.sample_id.split("_")
            if len(parts) >= 2:
                conditions.add(parts[1])
        # Baseline expectation: at least three condition slots per round.
        target = 3.0
        return min(1.0, len(conditions) / target)

    # --- verification bundle -----------------------------------------

    def _build_verification_bundle(
        self,
        *,
        round_index: int,
        report: ObserverReport,
        signal_summary: Mapping[str, float],
        prior_summary: Mapping[str, float],
    ) -> VerificationBundle:
        lfs: list[LFOutput] = []

        # LF1: MAPE check.
        mape_vote = 1 if report.mape <= self.acceptance_mape else -1
        lfs.append(
            LFOutput(
                lf_name="mape_under_threshold",
                vote=mape_vote,
                confidence=min(1.0, 1.0 - report.mape),
                rationale=f"MAPE={report.mape:.3f} vs target {self.acceptance_mape:.3f}",
                source="observer.mape",
            )
        )

        # LF2: signal SNR check.
        snr = float(signal_summary.get("mean_snr_db", 0.0))
        snr_vote = 1 if snr >= self.min_snr_db else -1
        lfs.append(
            LFOutput(
                lf_name="signal_snr",
                vote=snr_vote,
                confidence=min(1.0, snr / 20.0) if snr > 0 else 0.0,
                rationale=f"mean SNR={snr:.1f} dB vs threshold {self.min_snr_db} dB",
                source="observer.signal",
            )
        )

        # LF3: theory alignment check.
        theory = float(prior_summary.get("theory_alignment", 0.0))
        theory_vote = 1 if theory >= self.min_theory_alignment else -1
        lfs.append(
            LFOutput(
                lf_name="theory_alignment",
                vote=theory_vote,
                confidence=theory,
                rationale=f"theory alignment={theory:.2f}",
                source="observer.priors",
            )
        )

        # LF4: anomaly fraction check.
        anomaly = float(signal_summary.get("anomaly_fraction", 0.0))
        anomaly_vote = 1 if anomaly <= 0.2 else -1
        lfs.append(
            LFOutput(
                lf_name="anomaly_fraction",
                vote=anomaly_vote,
                confidence=1.0 - anomaly,
                rationale=f"{anomaly:.0%} of samples flagged anomalous",
                source="observer.signal",
            )
        )

        # LF5: contradiction penalty check.
        contradiction = float(prior_summary.get("contradiction_penalty", 0.0))
        contradiction_vote = 1 if contradiction <= 0.3 else -1
        lfs.append(
            LFOutput(
                lf_name="contradiction_penalty",
                vote=contradiction_vote,
                confidence=1.0 - contradiction,
                rationale=f"theory contradictions penalty={contradiction:.2f}",
                source="observer.priors",
            )
        )

        # Majority-vote label model — matches Phase B default.
        votes = [lf.vote for lf in lfs if lf.vote != 0]
        support_ratio = (
            sum(1 for v in votes if v == 1) / len(votes) if votes else 0.5
        )
        posterior = LabelModelPosterior(
            credibility_prob=support_ratio,
            confidence_interval=(
                max(0.0, support_ratio - 0.1),
                min(1.0, support_ratio + 0.1),
            ),
            source_disagreement=self._disagreement(votes),
            model="majority_vote",
        )
        return VerificationBundle(
            candidate_id=f"round_{round_index}",
            lf_outputs=tuple(lfs),
            posterior=posterior,
            provenance={
                "source": "sensing_studio.observer",
                "round": str(round_index),
            },
        )

    def _disagreement(self, votes: Sequence[int]) -> float:
        if len(votes) < 2:
            return 0.0
        supports = sum(1 for v in votes if v == 1)
        contradicts = len(votes) - supports
        minority = min(supports, contradicts)
        return (2.0 * minority) / len(votes)

    # --- routing ------------------------------------------------------

    def _route(self, report: ObserverReport) -> RoutingDecision:
        if report.mape <= self.acceptance_mape:
            return RoutingDecision(
                target="stop",
                reason=f"MAPE {report.mape:.3f} meets target",
                observer_score=report.observer_score,
            )

        # Signal quality is the first-line failure cause.
        if (
            report.mean_signal_snr_db < self.min_snr_db
            or report.signal_anomaly_fraction > 0.2
        ):
            return RoutingDecision(
                target="signal",
                reason=(
                    f"signal quality low: SNR={report.mean_signal_snr_db:.1f} dB, "
                    f"anomaly_frac={report.signal_anomaly_fraction:.2f}"
                ),
                observer_score=report.observer_score,
            )

        # If theory alignment is weak, the priors module is the bottleneck.
        if report.theory_alignment < self.min_theory_alignment:
            return RoutingDecision(
                target="priors",
                reason=(
                    f"theory alignment {report.theory_alignment:.2f} "
                    f"below {self.min_theory_alignment}"
                ),
                observer_score=report.observer_score,
            )

        # If the MAPE is still high with good signal and theory, the
        # predictive model is the problem.
        if report.mape > self.acceptance_mape * 2:
            return RoutingDecision(
                target="model",
                reason=(
                    f"model bias: MAPE={report.mape:.3f} "
                    f"with good signal + theory"
                ),
                observer_score=report.observer_score,
            )

        # Otherwise, add more experimental coverage.
        return RoutingDecision(
            target="experiment",
            reason="expand experiment coverage",
            observer_score=report.observer_score,
        )


__all__ = [
    "ObserverReport",
    "ObserverStudio",
    "RoutingDecision",
    "RoutingTarget",
]
