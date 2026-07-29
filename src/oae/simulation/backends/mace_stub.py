"""Deterministic MACE-MP-0 stub.

This backend emulates the relaxation/energy predictions MACE-MP-0 would
produce for a candidate. It is *not* a physics model — it is a stable,
cheap surrogate that lets the simulation lab, dataset builder, and the
Phase D MOF pipeline exercise the ``relaxation``/``formation_energy``
contract without downloading the real 500 MB checkpoint or needing
GPU hardware.

The surrogate is a deterministic pseudo-random function over the
composition string so repeated runs return identical results.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from ..base import (
    SimulationBackend,
    SimulationKind,
    SimulationRequest,
    SimulationResult,
)


def _hash_float(seed: str, lo: float, hi: float) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    frac = int.from_bytes(digest[:8], "big") / 2**64
    return lo + (hi - lo) * frac


@dataclass
class MACEMP0Stub:
    backend: SimulationBackend = SimulationBackend(
        name="mace_mp_0_stub",
        kinds=("relaxation", "formation_energy"),
        hot=True,
        cost_estimate=0.5,
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
        seed = f"{request.candidate_id}|{request.composition}|{request.family}"
        e_form = _hash_float(seed + "|form", -3.5, 0.5)              # eV/atom
        e_hull = _hash_float(seed + "|hull", 0.0, 120.0)             # meV/atom
        max_force = _hash_float(seed + "|force", 0.005, 0.05)        # eV/Å
        observables = {
            "formation_energy_per_atom_eV": e_form,
            "energy_above_hull_meV": e_hull,
            "max_force_eV_per_A": max_force,
        }
        summary = (
            f"MACE-MP-0 (stub): E_form={e_form:.3f} eV/atom, "
            f"E_hull={e_hull:.1f} meV/atom, |F|max={max_force:.3f} eV/Å"
        )
        return SimulationResult(
            request=request,
            backend=self.backend.name,
            ok=True,
            observables=observables,
            summary=summary,
            elapsed_s=time.time() - t0,
        )
