"""Phase H simulator abstractions.

Every simulator implements the :class:`Simulator` Protocol: given a
``SimulationRequest`` return a ``SimulationResult``. The lab selects a
backend based on the ``kind`` field plus the candidate metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol

SimulationKind = Literal[
    "relaxation",
    "formation_energy",
    "band_gap",
    "phonon",
    "electrochem",
    "cv_baseline",
    "eis_baseline",
    "md",
]


@dataclass(frozen=True)
class SimulationRequest:
    """Simulation request routed to a backend by the lab."""

    kind: SimulationKind
    candidate_id: str
    composition: str = ""
    family: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
    priority: float = 0.5


@dataclass(frozen=True)
class SimulationResult:
    """Normalized output produced by any simulation backend."""

    request: SimulationRequest
    backend: str
    ok: bool
    observables: Mapping[str, float] = field(default_factory=dict)
    summary: str = ""
    elapsed_s: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": {
                "kind": self.request.kind,
                "candidate_id": self.request.candidate_id,
                "composition": self.request.composition,
                "family": self.request.family,
                "parameters": dict(self.request.parameters),
                "priority": self.request.priority,
            },
            "backend": self.backend,
            "ok": self.ok,
            "observables": dict(self.observables),
            "summary": self.summary,
            "elapsed_s": self.elapsed_s,
            "error": self.error,
        }


@dataclass(frozen=True)
class SimulationBackend:
    """Backend metadata: what the simulator supports, what it costs."""

    name: str
    kinds: tuple[SimulationKind, ...]
    hot: bool = True              # hot = offline stub, cold = real compute
    cost_estimate: float = 1.0    # unitless, relative priority to scheduler
    requires_gpu: bool = False


class Simulator(Protocol):
    """Structural type implemented by every simulation backend."""

    backend: SimulationBackend

    def supports(self, kind: SimulationKind) -> bool: ...

    def run(self, request: SimulationRequest) -> SimulationResult: ...


@dataclass(frozen=True)
class SimulationBatchResult:
    """Batch output: aggregated results plus backend utilisation."""

    results: tuple[SimulationResult, ...] = field(default_factory=tuple)
    backend_counts: Mapping[str, int] = field(default_factory=dict)

    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.ok)

    def by_kind(self, kind: SimulationKind) -> tuple[SimulationResult, ...]:
        return tuple(r for r in self.results if r.request.kind == kind)
