"""Materials Project lookup stub.

Offline deterministic replacement for the MP REST API. Supplies a small
catalogue of hand-picked entries keyed by composition so the simulation
lab has something concrete to return for the ``formation_energy`` and
``band_gap`` kinds when MACE/M3GNet are not available.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Mapping

from ..base import (
    SimulationBackend,
    SimulationKind,
    SimulationRequest,
    SimulationResult,
)


_CATALOGUE: Mapping[str, Mapping[str, float]] = {
    "YBa2Cu3O7": {
        "formation_energy_per_atom_eV": -2.85,
        "band_gap_eV": 0.0,
    },
    "Ca4S4": {
        "formation_energy_per_atom_eV": -2.10,
        "band_gap_eV": 2.36,
    },
    "SrTiO3": {
        "formation_energy_per_atom_eV": -3.55,
        "band_gap_eV": 3.25,
    },
    "ZIF-8": {
        "formation_energy_per_atom_eV": -1.20,
        "band_gap_eV": 4.8,
    },
    "UiO-66": {
        "formation_energy_per_atom_eV": -1.82,
        "band_gap_eV": 4.0,
    },
    "HKUST-1": {
        "formation_energy_per_atom_eV": -1.45,
        "band_gap_eV": 3.1,
    },
}


@dataclass
class MaterialsProjectLookupStub:
    backend: SimulationBackend = SimulationBackend(
        name="materials_project_lookup_stub",
        kinds=("formation_energy", "band_gap"),
        hot=True,
        cost_estimate=0.05,
    )
    catalogue: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: dict(_CATALOGUE)
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
        entry = self.catalogue.get(request.composition)
        if entry is None:
            return SimulationResult(
                request=request,
                backend=self.backend.name,
                ok=False,
                summary=f"no MP entry for {request.composition!r}",
                error="not_found",
                elapsed_s=time.time() - t0,
            )

        if request.kind == "formation_energy":
            observables = {
                "formation_energy_per_atom_eV": entry["formation_energy_per_atom_eV"],
            }
        else:
            observables = {"band_gap_eV": entry["band_gap_eV"]}
        return SimulationResult(
            request=request,
            backend=self.backend.name,
            ok=True,
            observables=observables,
            summary=f"MP stub lookup: {request.composition}",
            elapsed_s=time.time() - t0,
        )
