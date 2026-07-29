"""Phase H — Simulation Lab.

Offline-first simulation substrate: every consumer calls a single
``Simulator`` protocol and the lab routes the request to the best
available backend. Hot backends (MACE-MP-0, M3GNet, Materials Project
lookup, analytical electrochem) are wrapped as deterministic stubs so
CI runs without any external dependency; cold backends (VASP,
OpenFOAM) are represented by metadata-only placeholders until the real
compute hardware is wired.
"""
from __future__ import annotations

from .base import (
    Simulator,
    SimulationBackend,
    SimulationBatchResult,
    SimulationKind,
    SimulationRequest,
    SimulationResult,
)
from .backends.analytical_electrochem import AnalyticalElectrochemSimulator
from .backends.mace_stub import MACEMP0Stub
from .backends.mp_lookup import MaterialsProjectLookupStub
from .backends.m3gnet_stub import M3GNetStub
from .dataset_builder import DatasetBuilder, SimulationDataset, build_mof_1k_seed
from .lab import SimulationLab

__all__ = [
    "Simulator",
    "SimulationBackend",
    "SimulationBatchResult",
    "SimulationKind",
    "SimulationRequest",
    "SimulationResult",
    "AnalyticalElectrochemSimulator",
    "MACEMP0Stub",
    "MaterialsProjectLookupStub",
    "M3GNetStub",
    "DatasetBuilder",
    "SimulationDataset",
    "build_mof_1k_seed",
    "SimulationLab",
]
