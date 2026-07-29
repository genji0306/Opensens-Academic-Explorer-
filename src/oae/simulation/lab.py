"""Simulation Lab — backend registry and job dispatcher.

``SimulationLab.submit(request)`` picks the cheapest available backend
that supports the request's kind and routes the call. ``submit_batch``
fans out a list of requests and returns a :class:`SimulationBatchResult`
alongside backend-utilisation stats.

The lab is deliberately a thin scheduler: no threads, no persistent
queue state, no global singleton. The value-scoring-aware queue lives
next door in :mod:`src.oae.studios.simulation_lab.job_queue`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from .backends.analytical_electrochem import AnalyticalElectrochemSimulator
from .backends.m3gnet_stub import M3GNetStub
from .backends.mace_stub import MACEMP0Stub
from .backends.mp_lookup import MaterialsProjectLookupStub
from .base import (
    SimulationBatchResult,
    SimulationKind,
    SimulationRequest,
    SimulationResult,
    Simulator,
)

logger = logging.getLogger("SimulationLab")


def _default_simulators() -> list[Simulator]:
    return [
        MaterialsProjectLookupStub(),
        MACEMP0Stub(),
        M3GNetStub(),
        AnalyticalElectrochemSimulator(),
    ]


@dataclass
class SimulationLab:
    """Registry + dispatcher for all simulation backends."""

    simulators: list[Simulator] = field(default_factory=_default_simulators)
    _backend_counts: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------

    def register(self, simulator: Simulator) -> None:
        self.simulators.append(simulator)

    def backends(self) -> list[str]:
        return [sim.backend.name for sim in self.simulators]

    def supports(self, kind: SimulationKind) -> bool:
        return any(sim.supports(kind) for sim in self.simulators)

    def choose_backend(self, request: SimulationRequest) -> Simulator | None:
        eligible = [sim for sim in self.simulators if sim.supports(request.kind)]
        if not eligible:
            return None
        preferred = request.parameters.get("preferred_backend")
        if preferred:
            for sim in eligible:
                if sim.backend.name == preferred:
                    return sim
        return min(eligible, key=lambda s: s.backend.cost_estimate)

    # ------------------------------------------------------------------

    def submit(self, request: SimulationRequest) -> SimulationResult:
        simulator = self.choose_backend(request)
        if simulator is None:
            logger.warning("no backend available for kind=%s", request.kind)
            return SimulationResult(
                request=request,
                backend="unavailable",
                ok=False,
                error=f"no backend for kind={request.kind!r}",
            )
        try:
            result = simulator.run(request)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("backend %s crashed", simulator.backend.name)
            return SimulationResult(
                request=request,
                backend=simulator.backend.name,
                ok=False,
                error=str(exc),
            )
        self._backend_counts[simulator.backend.name] = (
            self._backend_counts.get(simulator.backend.name, 0) + 1
        )
        return result

    def submit_batch(
        self,
        requests: Iterable[SimulationRequest],
    ) -> SimulationBatchResult:
        results = tuple(self.submit(req) for req in requests)
        return SimulationBatchResult(
            results=results,
            backend_counts=dict(self._backend_counts),
        )

    def reset_stats(self) -> None:
        self._backend_counts.clear()
