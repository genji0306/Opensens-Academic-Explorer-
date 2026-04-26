"""Sensing Studio — recursive context-aware sensing platform (Phase F).

Sensing Studio reframes sensing as recursive scientific inference
instead of curve fitting. Five modules cooperate under a closed-loop
orchestrator that learns how a real sensor behaves across matrices,
conditions, and batches:

* :mod:`~src.oae.studios.sensing_studio.experiment` — Agent LS, the
  condition-space experiment planner.
* :mod:`~src.oae.studios.sensing_studio.ingest` — CSV replay driver and
  the potentiostat bridge protocol (Opensens OEPS adapter lives here).
* :mod:`~src.oae.studios.sensing_studio.signal` — Agent ER, the signal
  feature and drift/anomaly analyzer.
* :mod:`~src.oae.studios.sensing_studio.reasoning` — Agent AR, the
  scientific priors engine (wraps Agent R + mechanism library).
* :mod:`~src.oae.studios.sensing_studio.model` — predictive model /
  lab leader / orchestrator core.
* :mod:`~src.oae.studios.sensing_studio.observer` — Observer Studio,
  blind evaluator that routes diagnostic feedback and emits
  :class:`~src.oae.kernel.schemas.VerificationBundle`-compatible output.
* :mod:`~src.oae.studios.sensing_studio.deploy` — deployment export.

The orchestrator is :class:`SensingStudioOrchestrator` and the session
state lives in :class:`RecursiveSensingSession`. Hidden labels are kept
in :class:`HiddenLabelVault`; only the Observer can read them.
"""
from __future__ import annotations

from src.oae.studios.sensing_studio.experiment import (
    ExperimentPlan,
    ExperimentPlanner,
)
from src.oae.studios.sensing_studio.ingest import (
    CSVReplayDriver,
    MeasurementRecord,
    OEPSPotentiostatAdapter,
    PotentiostatBridge,
)
from src.oae.studios.sensing_studio.model import (
    PredictiveModel,
    PredictiveOutput,
)
from src.oae.studios.sensing_studio.observer import (
    ObserverStudio,
    RoutingDecision,
    RoutingTarget,
)
from src.oae.studios.sensing_studio.orchestrator import (
    RecursiveSensingResult,
    SensingStudioOrchestrator,
)
from src.oae.studios.sensing_studio.reasoning import ScientificPriors
from src.oae.studios.sensing_studio.session import (
    HiddenLabelVault,
    RecursiveSensingSession,
    RoundState,
    RoutingRecord,
)
from src.oae.studios.sensing_studio.signal import SignalAnalyzer, SignalFeatures

__all__ = [
    "CSVReplayDriver",
    "ExperimentPlan",
    "ExperimentPlanner",
    "HiddenLabelVault",
    "MeasurementRecord",
    "OEPSPotentiostatAdapter",
    "ObserverStudio",
    "PotentiostatBridge",
    "PredictiveModel",
    "PredictiveOutput",
    "RecursiveSensingResult",
    "RecursiveSensingSession",
    "RoundState",
    "RoutingDecision",
    "RoutingRecord",
    "RoutingTarget",
    "ScientificPriors",
    "SensingStudioOrchestrator",
    "SignalAnalyzer",
    "SignalFeatures",
]
