"""MOF schemas — Metal–Organic Framework structural primitives (Phase B).

Used by the upcoming ``domains/mof.py`` domain pack and the MOF pipeline
inside Material Explorer. Designed to slot into ``MaterialDiscoveryLoop``
without modifying the loop contract: a ``MOFStructure`` can populate a
``LoopCandidate.metadata`` dict directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TopologyNet = Literal[
    "pcu", "sod", "fcu", "rht", "tbo", "mtn", "ftw",
    "nbo", "acs", "bcu", "dia", "lon", "srs", "the",
]
SBUGeometry = Literal[
    "paddlewheel", "oxo_trimer", "zr6_cluster", "zn4o",
    "cu2_paddlewheel", "single_metal", "porphyrin", "custom",
]
LinkerShape = Literal["ditopic", "tritopic", "tetratopic", "hexatopic", "mixed"]


@dataclass(frozen=True)
class PoreDescriptor:
    """Geometric characterization of a MOF's void space.

    All lengths are angstroms; all areas are m²/g; all volumes are cm³/g.
    """

    pore_volume_cm3_g: float = 0.0
    surface_area_m2_g: float = 0.0
    pld_angstrom: float = 0.0          # pore-limiting diameter
    lcd_angstrom: float = 0.0          # largest-cavity diameter
    asa_m2_g: float = 0.0              # accessible surface area
    density_g_cm3: float = 0.0


@dataclass(frozen=True)
class SBU:
    """A single inorganic secondary building unit."""

    sbu_id: str
    metal: str
    geometry: SBUGeometry = "custom"
    coordination_number: int = 0
    charge: int = 0
    formula: str = ""


@dataclass(frozen=True)
class Linker:
    """A single organic linker connecting SBUs."""

    linker_id: str
    smiles: str
    shape: LinkerShape = "ditopic"
    length_angstrom: float = 0.0
    functional_groups: tuple[str, ...] = field(default_factory=tuple)
    charge: int = 0


@dataclass(frozen=True)
class RCSRTopology:
    """Reference topology from the Reticular Chemistry Structure Resource."""

    net: TopologyNet
    rcsr_symbol: str = ""
    vertex_symbol: str = ""
    coordination_sequence: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SBULibrary:
    """Curated library of inorganic SBUs available to the seeder."""

    name: str
    entries: tuple[SBU, ...] = field(default_factory=tuple)

    def by_metal(self, metal: str) -> tuple[SBU, ...]:
        return tuple(s for s in self.entries if s.metal == metal)


@dataclass(frozen=True)
class LinkerLibrary:
    """Curated library of organic linkers available to the seeder."""

    name: str
    entries: tuple[Linker, ...] = field(default_factory=tuple)

    def by_shape(self, shape: LinkerShape) -> tuple[Linker, ...]:
        return tuple(linker for linker in self.entries if linker.shape == shape)


@dataclass(frozen=True)
class MOFStructure:
    """A single MOF candidate produced by the seeder or predictor."""

    mof_id: str
    family: str                        # "zif" | "uio" | "mil" | "hkust" | ...
    topology: RCSRTopology
    sbus: tuple[SBU, ...] = field(default_factory=tuple)
    linkers: tuple[Linker, ...] = field(default_factory=tuple)
    pore: PoreDescriptor = field(default_factory=PoreDescriptor)
    cif_path: str = ""
    thermal_stability_c: float = 0.0
    water_stability_score: float = 0.0
    target_property: float = 0.0       # domain-specific (CO2 uptake, etc.)
    provenance: dict[str, str] = field(default_factory=dict)
