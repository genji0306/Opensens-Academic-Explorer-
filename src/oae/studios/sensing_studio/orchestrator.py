"""Sensing Studio recursive orchestrator.

Five nodes, closed loop:

1. Experiment Design (Agent LS) — plan conditions and sample ids.
2. Ingest (PotentiostatBridge) — fetch normalized measurements.
3. Signal Intelligence (Agent ER) — extract features + summary.
4. Scientific Priors (Agent AR) — compile theory-driven prior summary.
5. Predictive Model (orchestrator core) — fit + predict concentration.
6. Observer — blind evaluation against the hidden vault, emits
   :class:`VerificationBundle` + :class:`RoutingDecision`.

After each round the orchestrator dispatches the routing decision:

* ``stop``       → exit loop (converged).
* ``experiment`` → Agent LS expands coverage for next round.
* ``signal``     → rerun the signal analyzer with an alternative
                    baseline strategy.
* ``priors``     → rebuild the prior summary for next round.
* ``model``      → call :meth:`PredictiveModel.redesign` with a new
                    feature strategy.

The orchestrator is *reusable* — it can be driven by the
:class:`MaterialDiscoveryLoop` kernel by wrapping this logic in a
subclass; it can also be driven directly (as Phase F does) because
the recursive logic is intrinsically condition-space, not
candidate-space.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from src.oae.kernel.schemas import VerificationBundle
from src.oae.studios.sensing_studio.experiment import (
    ExperimentPlan,
    ExperimentPlanner,
)
from src.oae.studios.sensing_studio.ingest.bridge import (
    MeasurementRecord,
    PotentiostatBridge,
)
from src.oae.studios.sensing_studio.model.predictive import (
    FeatureStrategy,
    PredictiveModel,
)
from src.oae.studios.sensing_studio.observer import (
    ObserverStudio,
    RoutingDecision,
)
from src.oae.studios.sensing_studio.reasoning import ScientificPriors
from src.oae.studios.sensing_studio.session import (
    RecursiveSensingSession,
    RoundState,
)
from src.oae.studios.sensing_studio.signal import SignalAnalyzer

logger = logging.getLogger("SensingStudioOrchestrator")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class RecursiveSensingResult:
    """Outcome of one :meth:`SensingStudioOrchestrator.run` invocation."""

    session: RecursiveSensingSession
    final_observer_score: float
    converged: bool
    routing_history: list[RoutingDecision] = field(default_factory=list)
    verification_bundles: list[VerificationBundle] = field(default_factory=list)

    @property
    def n_rounds(self) -> int:
        return len(self.session.rounds)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


# Feature-strategy rotation for ``model`` routing decisions.
_REDESIGN_ROTATION: tuple[FeatureStrategy, ...] = (
    "peak",
    "peak_theory",
    "peak_linear",
)


@dataclass
class SensingStudioOrchestrator:
    """Five-node recursive sensing orchestrator.

    Dependencies are injected so tests can swap in stubs. The default
    configuration is deterministic and matches the Phase F CSV replay
    scenarios.
    """

    bridge: PotentiostatBridge
    planner: ExperimentPlanner = field(default_factory=ExperimentPlanner)
    analyzer: SignalAnalyzer = field(default_factory=SignalAnalyzer)
    priors: ScientificPriors = field(default_factory=ScientificPriors)
    observer: ObserverStudio = field(default_factory=ObserverStudio)

    # --- public API ---------------------------------------------------

    def run(
        self,
        *,
        session: RecursiveSensingSession,
        concentrations_uM: Sequence[float],
        sample_concentration_map: dict[str, float],
        expansion_ph: Iterable[float] = (5.5, 8.5),
        expansion_ionic_mM: Iterable[float] = (25.0, 250.0),
    ) -> RecursiveSensingResult:
        """Execute the recursive sensing loop.

        Parameters
        ----------
        session:
            Caller-supplied session. The vault is populated from
            ``sample_concentration_map`` and then frozen.
        concentrations_uM:
            Ordered list of true concentrations. The planner uses the
            *length* of this list to generate sample ids; the actual
            binding happens in ``sample_concentration_map``.
        sample_concentration_map:
            ``sample_id → true concentration`` binding. The Observer's
            hidden label vault is populated from this map.
        expansion_ph, expansion_ionic_mM:
            Candidate pH / ionic-strength values the planner will try
            when routing lands on ``"experiment"``.
        """
        self._seed_vault(session, sample_concentration_map)

        model = PredictiveModel(feature_strategy="peak")
        plan = self.planner.initial_plan(
            session=session.calibration,
            concentrations_uM=concentrations_uM,
        )

        prior_bundle = self.priors.build_for_analyte(session.calibration.analyte)
        prior_summary = self.priors.summarise(
            prior_bundle, session.calibration.analyte
        )

        verification_bundles: list[VerificationBundle] = []
        routing_history: list[RoutingDecision] = []
        analyzer = self.analyzer
        redesign_idx = 0

        for _ in range(session.max_rounds):
            round_state = session.begin_round()
            round_state.conditions = plan.conditions

            # 1. Ingest.
            records = self.bridge.fetch(s.sample_id for s in plan.samples)
            if not records:
                logger.warning("bridge returned no records for round %d", round_state.round_index)
                break

            # 2. Signal analysis.
            features = analyzer.analyze_batch(records)
            signal_summary = analyzer.summarise(features)
            round_state.signal_feature_summary = signal_summary

            # 3. Scientific priors (recomputed per round so ``priors``
            #    routing has something to change).
            round_state.prior_summary = dict(prior_summary)

            # 4. Predictive model: fit on calibration samples + predict.
            truth = {
                sid: sample_concentration_map[sid]
                for sid in (f.sample_id for f in features)
                if sid in sample_concentration_map
            }
            fit_features = [f for f in features if f.sample_id in truth]
            fit_targets = [truth[f.sample_id] for f in fit_features]
            if fit_features:
                model.fit(fit_features, fit_targets, prior_summary)
            predictions = model.predict(features) if model.fitted else ()

            round_state.predictions = {
                p.sample_id: p.predicted_concentration_uM for p in predictions
            }
            round_state.prediction_uncertainty = {
                p.sample_id: p.uncertainty_uM for p in predictions
            }

            # 5. Observer — blind evaluation + routing.
            report, bundle, decision = self.observer.evaluate(
                round_index=round_state.round_index,
                predictions=predictions,
                signal_features=features,
                signal_summary=signal_summary,
                prior_summary=round_state.prior_summary,
                vault=session.vault,
            )
            round_state.observer_score = report.observer_score
            round_state.verification = bundle
            round_state.record_routing(
                self.observer.to_routing_record(
                    round_state.round_index, decision
                )
            )
            verification_bundles.append(bundle)
            routing_history.append(decision)

            if decision.target == "stop":
                logger.info(
                    "sensing studio converged at round %d with score %.3f",
                    round_state.round_index,
                    report.observer_score,
                )
                break

            # 6. Dispatch routing → prepare next round.
            plan, model, prior_summary, analyzer, redesign_idx = (
                self._dispatch_routing(
                    decision=decision,
                    plan=plan,
                    model=model,
                    prior_summary=prior_summary,
                    analyzer=analyzer,
                    redesign_idx=redesign_idx,
                    session=session,
                    concentrations_uM=concentrations_uM,
                    expansion_ph=expansion_ph,
                    expansion_ionic_mM=expansion_ionic_mM,
                )
            )

        final_score = session.rounds[-1].observer_score if session.rounds else 0.0
        converged = any(d.target == "stop" for d in routing_history)
        return RecursiveSensingResult(
            session=session,
            final_observer_score=final_score,
            converged=converged,
            routing_history=routing_history,
            verification_bundles=verification_bundles,
        )

    # --- helpers ------------------------------------------------------

    def _seed_vault(
        self,
        session: RecursiveSensingSession,
        sample_concentration_map: dict[str, float],
    ) -> None:
        if session.vault.is_frozen:
            return
        session.vault.deposit_batch(sample_concentration_map)
        session.vault.freeze()

    def _dispatch_routing(
        self,
        *,
        decision: RoutingDecision,
        plan: ExperimentPlan,
        model: PredictiveModel,
        prior_summary: dict[str, float],
        analyzer: SignalAnalyzer,
        redesign_idx: int,
        session: RecursiveSensingSession,
        concentrations_uM: Sequence[float],
        expansion_ph: Iterable[float],
        expansion_ionic_mM: Iterable[float],
    ) -> tuple[
        ExperimentPlan,
        PredictiveModel,
        dict[str, float],
        SignalAnalyzer,
        int,
    ]:
        target = decision.target
        if target == "experiment":
            plan = self.planner.expand_coverage(
                session=session.calibration,
                previous_plan=plan,
                concentrations_uM=concentrations_uM,
                extra_ph=expansion_ph,
                extra_ionic_mM=expansion_ionic_mM,
            )
        elif target == "model":
            redesign_idx = (redesign_idx + 1) % len(_REDESIGN_ROTATION)
            model = model.redesign(_REDESIGN_ROTATION[redesign_idx])
        elif target == "signal":
            # Swap in a tighter baseline estimator.
            new_fraction = max(0.1, analyzer.baseline_fraction - 0.05)
            analyzer = SignalAnalyzer(
                baseline_fraction=new_fraction,
                anomaly_snr_threshold_db=analyzer.anomaly_snr_threshold_db,
            )
        elif target == "priors":
            # Rebuild priors for the analyte — a real Phase G upgrade
            # would pull fresh literature here. In Phase F we simply
            # recompute the summary with a broader family list.
            bundle = self.priors.build_for_analyte(
                session.calibration.analyte,
                families=(
                    "electrochemical-voltammetric",
                    "electrochemical-amperometric",
                    "electrochemical-impedimetric",
                ),
            )
            prior_summary = self.priors.summarise(
                bundle, session.calibration.analyte
            )
        return plan, model, prior_summary, analyzer, redesign_idx


__all__ = [
    "RecursiveSensingResult",
    "SensingStudioOrchestrator",
]
