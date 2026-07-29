"""Deterministic M3GNet surrogate for phonon / band-gap queries."""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..base import (
    SimulationBackend,
    SimulationKind,
    SimulationRequest,
    SimulationResult,
)
from .mace_stub import _hash_float


@dataclass
class M3GNetStub:
    backend: SimulationBackend = SimulationBackend(
        name="m3gnet_stub",
        kinds=("phonon", "band_gap", "md"),
        hot=True,
        cost_estimate=0.7,
        requires_gpu=False,
    )

    def supports(self, kind: SimulationKind) -> bool:
        return kind in self.backend.kinds

    def run(self, request: SimulationRequest) -> SimulationResult:
        if not self.supports(request.kind):
            return SimulationResult(
                request=request,
                backend=self.backend.name,
                ok=False,
                error=f"kind {request.kind!r} not supported",
            )

        t0 = time.time()
        seed = f"{request.candidate_id}|{request.composition}|{request.kind}"
        if request.kind == "band_gap":
            observables = {
                "band_gap_eV": _hash_float(seed, 0.0, 5.0),
            }
        elif request.kind == "phonon":
            observables = {
                "max_phonon_cm1": _hash_float(seed, 200.0, 1_200.0),
                "imaginary_modes": 0.0,
            }
        else:  # md
            observables = {
                "msd_A2_per_ps": _hash_float(seed, 0.01, 0.5),
                "T_K": float(request.parameters.get("temperature_K", 300.0)),
            }

        return SimulationResult(
            request=request,
            backend=self.backend.name,
            ok=True,
            observables=observables,
            summary=f"m3gnet_stub: {request.kind}",
            elapsed_s=time.time() - t0,
        )
