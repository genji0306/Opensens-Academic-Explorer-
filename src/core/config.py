"""
Central configuration for Opensens Academic Explorer (OAE).
All paths are relative to PROJECT_ROOT.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# --- Directory layout ---
DATA_DIR = PROJECT_ROOT / "data"
EXPERIMENTAL_DIR = DATA_DIR / "experimental"
CRYSTAL_PATTERNS_DIR = DATA_DIR / "crystal_patterns"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
REFINEMENTS_DIR = DATA_DIR / "refinements"
NOVEL_CANDIDATES_DIR = DATA_DIR / "novel_candidates"
REPORTS_DIR = DATA_DIR / "reports"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"

# External references (references/)
REFERENCES_DIR = PROJECT_ROOT / "references"
NEMAD_DIR = REFERENCES_DIR / "nemad"
NEMAD_DATASET_DIR = NEMAD_DIR / "Dataset"
ALPHAFOLD3_DIR = REFERENCES_DIR / "alphafold" / "alphafold3-main"

# --- v2.0 Agent directories ---
AGENT_PB_DIR = PROJECT_ROOT / "agent_pb"
AGENT_XC_DIR = PROJECT_ROOT / "agent_xc"
AGENT_V_DIR = PROJECT_ROOT / "agent_v"
BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"
SKILL_V2_DIR = PROJECT_ROOT / "skill_v2"

# v2.0 output directories
PREDICTIONS_DIR = DATA_DIR / "predictions"
PREDICTIONS_PB_DIR = PREDICTIONS_DIR / "agent_pb"
PREDICTIONS_XC_DIR = PREDICTIONS_DIR / "agent_xc"
EXPORTS_DIR = DATA_DIR / "exports"
BENCHMARK_RESULTS_DIR = DATA_DIR / "benchmarks" / "results"

# --- Convergence settings ---
CONVERGENCE_TARGET = 0.95  # v1 default; use 0.99 for v2 mode
MAX_ITERATIONS = 20
PLATEAU_WINDOW = 5
PLATEAU_THRESHOLD = 0.005
DAMPING_FACTOR = 0.35  # Apply 35% of suggested refinements (lower = less oscillation)

# --- Convergence score weights ---
SCORE_WEIGHTS = {
    "tc_distribution": 0.25,
    "lattice_accuracy": 0.22,
    "space_group_correctness": 0.13,
    "electronic_property_match": 0.13,
    "composition_validity": 0.09,
    "coordination_geometry": 0.05,
    "pressure_tc_accuracy": 0.13,
}

# --- Simulation defaults ---
DEFAULT_STRUCTURES_PER_PATTERN = 200
DIFFUSION_STEPS = 1000
STABILITY_THRESHOLD_MEV = 50.0  # meV/atom above hull

# --- Pressure scan settings ---
BENCHMARK_PRESSURE_DIR = REFERENCES_DIR / "utils" / "benchmark_pressure" / "data"
DEFAULT_PRESSURE_SCAN_POINTS = 20
DEFAULT_TARGET_PRESSURE_GPA = 0.0

# --- Known superconductor families ---
SC_FAMILIES = [
    "cuprate",
    "iron-pnictide",
    "iron-chalcogenide",
    "heavy-fermion",
    "mgb2-type",
    "hydride",
    "nickelate",
    "a15",
    "chevrel",
    "organic",
    "other",
]


def ensure_dirs():
    """Create all data directories if they don't exist."""
    for d in [
        EXPERIMENTAL_DIR,
        CRYSTAL_PATTERNS_DIR,
        SYNTHETIC_DIR,
        REFINEMENTS_DIR,
        NOVEL_CANDIDATES_DIR,
        REPORTS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


# --- v2.0 convergence settings ---
V2_CONVERGENCE_TARGET = 0.99
V2_SCORE_WEIGHTS = {
    "tc_distribution": 0.22,
    "lattice_accuracy": 0.20,
    "space_group_correctness": 0.15,
    "electronic_property_match": 0.15,
    "composition_validity": 0.10,
    "coordination_geometry": 0.08,
    "pressure_tc_accuracy": 0.10,
}


def ensure_dirs_v2():
    """Create v2.0 output directories alongside v1 dirs."""
    ensure_dirs()
    for d in [
        PREDICTIONS_PB_DIR,
        PREDICTIONS_XC_DIR,
        EXPORTS_DIR,
        BENCHMARK_RESULTS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


# ===================================================================
# RTAP (Room-Temperature Ambient-Pressure) Discovery Mode — v3
# ===================================================================
RTAP_CONVERGENCE_TARGET = 0.85  # Lower: no experimental ground truth for RT-SC
RTAP_MAX_ITERATIONS = 50
RTAP_DAMPING_FACTOR = 0.25  # More aggressive parameter shifts for exploration

RTAP_SCORE_WEIGHTS = {
    "ambient_tc_score": 0.30,           # Predicted Tc at P <= 1 GPa, >= 273K
    "ambient_stability_score": 0.25,    # Thermodynamic stability at ambient
    "synthesizability_score": 0.15,     # Practical synthesis feasibility
    "electronic_indicator_score": 0.15, # Flat bands, nesting, vHS proximity
    "mechanism_plausibility_score": 0.10,  # Self-consistency of proposed mechanism
    "composition_validity": 0.05,       # Basic chemical sanity
}

RTAP_FAMILIES = [
    # Existing families with RTAP potential
    "cuprate",
    "nickelate",
    "hydride",
    "iron-pnictide",
    "iron-chalcogenide",
    # New RTAP-targeted families
    "kagome",
    "ternary-hydride",
    "infinite-layer",
    "topological",
    "2d-heterostructure",
    "carbon-based",
    "engineered-cuprate",
    "mof-sc",
    "flat-band",
]

RTAP_TC_THRESHOLD_K = 273.0    # Minimum Tc target for room temperature
RTAP_MAX_PRESSURE_GPA = 1.0    # Maximum acceptable operating pressure
RTAP_STABILITY_THRESHOLD_MEV = 100.0  # meV above hull (relaxed for metastable)

# RTAP output directories
RTAP_DIR = DATA_DIR / "rtap"
RTAP_CANDIDATES_DIR = RTAP_DIR / "candidates"
RTAP_REPORTS_DIR = RTAP_DIR / "reports"


# --- OAE Data Registry ---
REGISTRY_PATH = DATA_DIR / "registry.json"
DATASETS_DIR = DATA_DIR / "datasets"
NEMAD_ADAPTER_CACHE = DATA_DIR / "nemad_cache"


def ensure_dirs_rtap():
    """Create RTAP output directories alongside v1/v2 dirs."""
    ensure_dirs_v2()
    for d in [RTAP_DIR, RTAP_CANDIDATES_DIR, RTAP_REPORTS_DIR, DATASETS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
