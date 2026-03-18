"""
Data classes mirroring the JSON schemas, used throughout all agents.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import json
from pathlib import Path


@dataclass
class LatticeParams:
    a: float
    c: float
    b: Optional[float] = None
    alpha: float = 90.0
    beta: float = 90.0
    gamma: float = 90.0


@dataclass
class ElectronicFeatures:
    d_band_filling: Optional[float] = None
    Fermi_surface: Optional[str] = None
    band_gap_eV: Optional[float] = None
    electron_phonon_lambda: Optional[float] = None
    # RTAP fields for multi-mechanism Tc prediction
    pairing_mechanism: str = "bcs"  # bcs|eliashberg|spin_fluctuation|flat_band|excitonic|hydride_cage|mixed
    flat_band_width_eV: Optional[float] = None
    spin_fluctuation_T_K: Optional[float] = None
    nesting_strength: Optional[float] = None
    van_hove_distance_eV: Optional[float] = None
    topological_index: Optional[int] = None
    dos_at_ef_states_eV: Optional[float] = None
    exciton_energy_eV: Optional[float] = None
    excitonic_coupling_V: Optional[float] = None


@dataclass
class PressureParams:
    """Birch-Murnaghan EOS and Grüneisen parameters for a superconductor family."""
    V0_per_atom_A3: float         # Ambient volume per atom (Å³)
    B0_GPa: float                 # Bulk modulus (GPa)
    B0_prime: float               # dB/dP (dimensionless, typically 4-6)
    gruneisen_gamma: float        # Phonon Grüneisen parameter γ
    eta_lambda: float             # Lambda volume exponent: λ(V) = λ₀(V/V₀)^η
    thermal_gruneisen: float      # Thermal Grüneisen for low-T contraction
    debye_T_K: float              # Debye temperature (K)
    dTc_dP_exp_K_per_GPa: Optional[float] = None  # Experimental dTc/dP for validation
    P_min_GPa: float = 0.0
    P_max_GPa: float = 200.0
    Tc_ceiling_K: float = 300.0          # Physical upper bound for Tc (K)
    notes: str = ""


@dataclass
class PressureResult:
    """Result of pressure-dependent Tc calculation."""
    structure_id: str
    Tc_ambient_K: float
    Tc_at_target_K: float
    target_pressure_GPa: float
    V_at_target_A3: float
    lambda_at_target: float
    omega_log_at_target_K: float
    Tc_optimal_K: float
    P_optimal_GPa: float
    Tc_vs_P: list[list[float]] = field(default_factory=list)
    thermal_correction_K: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class PatternCard:
    pattern_id: str
    crystal_system: str
    space_group: str
    lattice_params: LatticeParams
    key_motifs: list[str]
    typical_Tc_range_K: list[float]
    source_compounds: list[str]
    dopant_sites: list[str] = field(default_factory=list)
    electronic_features: Optional[ElectronicFeatures] = None
    nemad_magnetic_class: str = "NM"
    feature_vector: list[float] = field(default_factory=list)
    pressure_params: Optional[PressureParams] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> PatternCard:
        lp = d.get("lattice_params", {})
        d["lattice_params"] = LatticeParams(**lp)
        ef = d.get("electronic_features")
        if ef and isinstance(ef, dict):
            d["electronic_features"] = ElectronicFeatures(**ef)
        pp = d.get("pressure_params")
        if pp and isinstance(pp, dict):
            d["pressure_params"] = PressureParams(**pp)
        return cls(**d)


@dataclass
class Refinement:
    target_agent: str  # "CS" or "Sin"
    action: str
    detail: str
    pattern_id: Optional[str] = None
    parameter: Optional[str] = None
    current_value: Optional[float] = None
    suggested_value: Optional[float] = None
    priority: str = "medium"


@dataclass
class ComponentScores:
    tc_distribution: float = 0.0
    lattice_accuracy: float = 0.0
    space_group_correctness: float = 0.0
    electronic_property_match: float = 0.0
    composition_validity: float = 0.0
    coordination_geometry: float = 0.0
    pressure_tc_accuracy: float = 0.0
    # RTAP discovery-mode scores
    ambient_tc_score: float = 0.0
    ambient_stability_score: float = 0.0
    synthesizability_score: float = 0.0
    electronic_indicator_score: float = 0.0
    mechanism_plausibility_score: float = 0.0


@dataclass
class RefinementReport:
    iteration: int
    convergence_score: float
    component_scores: ComponentScores
    refinements: list[Refinement]
    novel_candidates_flagged: int = 0
    convergence_trend: str = "improving"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> RefinementReport:
        d["component_scores"] = ComponentScores(**d["component_scores"])
        d["refinements"] = [Refinement(**r) for r in d["refinements"]]
        return cls(**d)

    @classmethod
    def load(cls, path: Path) -> RefinementReport:
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())


@dataclass
class SyntheticStructure:
    structure_id: str
    pattern_id: str
    composition: str
    crystal_system: str
    space_group: str
    lattice_params: LatticeParams
    predicted_Tc_K: float
    electron_phonon_lambda: float = 0.0
    energy_above_hull_meV: float = 0.0
    stability_confidence: float = 0.0
    fractional_coords: list[list[float]] = field(default_factory=list)
    species: list[str] = field(default_factory=list)
    pressure_GPa: float = 0.0
    volume_per_atom_A3: float = 0.0
    # RTAP multi-mechanism fields
    primary_mechanism: str = "bcs"
    mechanism_confidence: float = 0.0
    tc_by_mechanism: dict = field(default_factory=dict)
    ambient_pressure_Tc_K: float = 0.0


@dataclass
class WyckoffSite:
    """A crystallographic site with Wyckoff label and fractional coordinates."""
    label: str              # e.g., "4a", "2b"
    element: str            # e.g., "Cu"
    x: float                # fractional coordinate
    y: float
    z: float
    occupancy: float = 1.0  # site occupancy (0-1)


@dataclass
class CrystalModel:
    """Complete crystal structure model built by Agent CB."""
    candidate_id: str
    composition: str
    space_group: str
    crystal_system: str
    lattice_params: LatticeParams
    sites: list[WyckoffSite]
    predicted_Tc_K: float
    bond_lengths: dict[str, float] = field(default_factory=dict)
    coordination_numbers: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class FeasibilityReport:
    """Structural feasibility evaluation from Agent CB."""
    candidate_id: str
    goldschmidt_tolerance: Optional[float] = None
    bond_valence_sums: dict[str, float] = field(default_factory=dict)
    min_interatomic_distance_A: float = 0.0
    distance_violations: list[str] = field(default_factory=list)
    feasibility_score: float = 0.0
    synthesis_difficulty: str = "moderate"
    recommended_method: str = "solid-state"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AmbientStability:
    """Thermodynamic stability assessment at ambient conditions (1 atm, 300K)."""
    formation_energy_eV_atom: float = 0.0
    energy_above_hull_meV: float = 999.0
    decomposition_products: list = field(default_factory=list)
    is_metastable: bool = False
    metastability_barrier_eV: float = 0.0
    air_stability: str = "unknown"  # stable|degrades_slowly|reactive
    moisture_sensitivity: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RTSCCandidate:
    """Room-temperature superconductor candidate — enriched structure."""
    structure_id: str
    pattern_id: str
    composition: str
    crystal_system: str
    space_group: str
    lattice_params: LatticeParams
    predicted_Tc_K: float
    tc_by_mechanism: dict = field(default_factory=dict)
    primary_mechanism: str = "bcs"
    mechanism_confidence: float = 0.0
    ambient_stability: Optional[AmbientStability] = None
    electronic_features: Optional[ElectronicFeatures] = None
    ambient_pressure_Tc_K: float = 0.0
    minimum_stabilization_pressure_GPa: float = 0.0
    rtsc_score: float = 0.0
    synthesizability_score: float = 0.0
    novelty_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class MaterialEntry:
    """Unified material entry for the OAE data registry.

    Supports superconductors, magnetic materials, general crystals, etc.
    """
    material_id: str
    material_type: str = ""       # superconductor|magnetic|crystal|general
    composition: str = ""
    crystal_system: str = ""
    space_group: str = ""
    source: str = ""              # agent_cs|agent_pb|nemad|mc3d|icsd|user
    properties: dict = field(default_factory=dict)
    data_paths: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MaterialEntry":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def load_pattern_catalog(path: Path) -> list[PatternCard]:
    with open(path) as f:
        data = json.load(f)
    return [PatternCard.from_dict(p) for p in data["patterns"]]


def save_pattern_catalog(patterns: list[PatternCard], path: Path, version: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {
        "version": version,
        "num_patterns": len(patterns),
        "patterns": [p.to_dict() for p in patterns],
    }
    with open(path, "w") as f:
        json.dump(catalog, f, indent=2)
