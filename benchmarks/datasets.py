"""Benchmark datasets for crystal structure prediction agents."""
import json
import sys
import logging
from pathlib import Path

logger = logging.getLogger("Benchmarks.Datasets")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATASETS_DIR = PROJECT_ROOT / "data" / "datasets"


def _load_json_or_fallback(name: str, fallback_fn):
    """Load dataset from JSON file, falling back to embedded data."""
    json_path = DATASETS_DIR / f"{name}.json"
    if json_path.exists():
        try:
            with open(json_path) as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} entries from {json_path.name}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load {json_path}: {e}. Using embedded data.")
    return fallback_fn()

AVAILABLE_DATASETS = {
    "supercon_24": "24 reference superconductors from Agent Ob experimental data",
    "seed_patterns_12": "12 seed crystal patterns from Agent CS",
    "icsd_ref_30": "30 ICSD reference structures — well-characterized binary/ternary crystals",
    "formation_energy_25": "25 compounds with DFT formation energies (Materials Project reference)",
    "rtap_candidates_40": "40 RTAP reference entries spanning 133K cuprates to speculative 300K compositions",
    "high_tc_reference_15": "15 highest confirmed Tc values for calibration",
}


def load_dataset(name: str) -> list:
    """Load a benchmark dataset as list of dicts.

    Each dict contains: composition, crystal_system, space_group,
    lattice_params (dict), and family-specific properties.
    """
    if name == "supercon_24":
        return load_supercon_24()
    elif name == "seed_patterns_12":
        return load_seed_patterns()
    elif name == "icsd_ref_30":
        return load_icsd_ref_30()
    elif name == "formation_energy_25":
        return load_formation_energy_25()
    elif name == "rtap_candidates_40":
        return load_rtap_candidates_40()
    elif name == "high_tc_reference_15":
        return load_high_tc_reference_15()
    else:
        raise ValueError(f"Unknown dataset: {name}. "
                         f"Available: {list(AVAILABLE_DATASETS.keys())}")


def load_supercon_24() -> list:
    """Load 24-compound reference dataset from Agent Ob's EXPERIMENTAL_DATA.

    Returns list of dicts with: composition, Tc_K, crystal_system,
    space_group, lattice (a, c), family.
    """
    # Try JSON file first
    json_path = DATASETS_DIR / "supercon_24.json"
    if json_path.exists():
        try:
            with open(json_path) as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} entries from {json_path.name}")
            return data
        except Exception:
            pass

    # Then try Agent Ob live data
    try:
        from src.agents.agent_ob import EXPERIMENTAL_DATA
    except ImportError:
        logger.warning("Cannot import Agent Ob. Using embedded reference data.")
        return _embedded_supercon_24()

    records = []
    for comp, data in EXPERIMENTAL_DATA.items():
        record = {
            "composition": comp,
            "Tc_K": data.get("Tc_K", 0),
            "crystal_system": data.get("crystal_system", "unknown"),
            "space_group": data.get("space_group", "P1"),
            "lattice_a": data.get("a_angstrom", 0),
            "lattice_c": data.get("c_angstrom", 0),
            "family": data.get("family", "other"),
        }
        records.append(record)

    logger.info(f"Loaded {len(records)} reference superconductors")
    return records


def load_seed_patterns() -> list:
    """Load 12 seed crystal patterns from Agent CS."""
    try:
        from src.agents.agent_cs import SEED_PATTERNS
    except ImportError:
        logger.warning("Cannot import Agent CS. Returning empty patterns.")
        return []

    records = []
    for pattern in SEED_PATTERNS:
        record = {
            "pattern_id": pattern.get("pattern_id", ""),
            "composition": pattern.get("representative_compound", ""),
            "crystal_system": pattern.get("crystal_system", ""),
            "space_group": pattern.get("space_group", ""),
            "family": pattern.get("family", ""),
            "lattice_params": pattern.get("lattice_params", {}),
            "Tc_range": pattern.get("Tc_range_K", []),
        }
        records.append(record)

    logger.info(f"Loaded {len(records)} seed patterns")
    return records


def _embedded_supercon_24() -> list:
    """Fallback embedded reference data (subset of Agent Ob's data)."""
    return [
        {"composition": "YBa2Cu3O7", "Tc_K": 92, "crystal_system": "orthorhombic",
         "space_group": "Pmmm", "lattice_a": 3.82, "lattice_c": 11.68, "family": "cuprate"},
        {"composition": "MgB2", "Tc_K": 39, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "lattice_a": 3.086, "lattice_c": 3.524, "family": "mgb2-type"},
        {"composition": "Nb3Sn", "Tc_K": 18.3, "crystal_system": "cubic",
         "space_group": "Pm-3n", "lattice_a": 5.29, "lattice_c": 5.29, "family": "a15"},
        {"composition": "LaFeAsO", "Tc_K": 26, "crystal_system": "tetragonal",
         "space_group": "P4/nmm", "lattice_a": 4.03, "lattice_c": 8.74, "family": "iron-pnictide"},
        {"composition": "FeSe", "Tc_K": 8, "crystal_system": "tetragonal",
         "space_group": "P4/nmm", "lattice_a": 3.77, "lattice_c": 5.52, "family": "iron-chalcogenide"},
        {"composition": "CeCoIn5", "Tc_K": 2.3, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "lattice_a": 4.62, "lattice_c": 7.56, "family": "heavy-fermion"},
        {"composition": "La3Ni2O7", "Tc_K": 80, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "lattice_a": 3.83, "lattice_c": 20.5, "family": "nickelate"},
        {"composition": "H3S", "Tc_K": 203, "crystal_system": "cubic",
         "space_group": "Im-3m", "lattice_a": 3.09, "lattice_c": 3.09, "family": "hydride"},
    ]


def load_icsd_ref_30() -> list:
    """Load 30 ICSD-quality reference structures for structure prediction benchmarking.

    Covers binary/ternary compounds across all 7 crystal systems with
    experimentally determined lattice parameters and space groups.
    """
    return _load_json_or_fallback("icsd_ref_30", _embedded_icsd_ref_30)


def _embedded_icsd_ref_30() -> list:
    """30 well-characterized reference structures from ICSD / literature.

    Sources: ICSD, Materials Project, Pearson's Crystal Data.
    Each entry: composition, space_group (H-M symbol), space_group_number,
    crystal_system, lattice_a/b/c (Angstrom), lattice_alpha/beta/gamma (deg),
    n_atoms_cell, category.
    """
    return [
        # --- Elemental & simple metals ---
        {"composition": "Cu", "space_group": "Fm-3m", "space_group_number": 225,
         "crystal_system": "cubic", "lattice_a": 3.615, "lattice_b": 3.615,
         "lattice_c": 3.615, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 4, "category": "elemental"},
        {"composition": "Si", "space_group": "Fd-3m", "space_group_number": 227,
         "crystal_system": "cubic", "lattice_a": 5.431, "lattice_b": 5.431,
         "lattice_c": 5.431, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "elemental"},
        {"composition": "Fe", "space_group": "Im-3m", "space_group_number": 229,
         "crystal_system": "cubic", "lattice_a": 2.867, "lattice_b": 2.867,
         "lattice_c": 2.867, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 2, "category": "elemental"},
        {"composition": "Ti", "space_group": "P6_3/mmc", "space_group_number": 194,
         "crystal_system": "hexagonal", "lattice_a": 2.951, "lattice_b": 2.951,
         "lattice_c": 4.686, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 2, "category": "elemental"},
        # --- Binary compounds ---
        {"composition": "NaCl", "space_group": "Fm-3m", "space_group_number": 225,
         "crystal_system": "cubic", "lattice_a": 5.640, "lattice_b": 5.640,
         "lattice_c": 5.640, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "binary_halide"},
        {"composition": "MgO", "space_group": "Fm-3m", "space_group_number": 225,
         "crystal_system": "cubic", "lattice_a": 4.212, "lattice_b": 4.212,
         "lattice_c": 4.212, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "binary_oxide"},
        {"composition": "TiO2", "space_group": "P4_2/mnm", "space_group_number": 136,
         "crystal_system": "tetragonal", "lattice_a": 4.594, "lattice_b": 4.594,
         "lattice_c": 2.959, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 6, "category": "binary_oxide"},
        {"composition": "ZnO", "space_group": "P6_3mc", "space_group_number": 186,
         "crystal_system": "hexagonal", "lattice_a": 3.250, "lattice_b": 3.250,
         "lattice_c": 5.207, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 4, "category": "binary_oxide"},
        {"composition": "GaAs", "space_group": "F-43m", "space_group_number": 216,
         "crystal_system": "cubic", "lattice_a": 5.653, "lattice_b": 5.653,
         "lattice_c": 5.653, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "binary_semiconductor"},
        {"composition": "SiC", "space_group": "F-43m", "space_group_number": 216,
         "crystal_system": "cubic", "lattice_a": 4.358, "lattice_b": 4.358,
         "lattice_c": 4.358, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "binary_carbide"},
        {"composition": "BN", "space_group": "P6_3/mmc", "space_group_number": 194,
         "crystal_system": "hexagonal", "lattice_a": 2.504, "lattice_b": 2.504,
         "lattice_c": 6.661, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 4, "category": "binary_nitride"},
        {"composition": "AlN", "space_group": "P6_3mc", "space_group_number": 186,
         "crystal_system": "hexagonal", "lattice_a": 3.112, "lattice_b": 3.112,
         "lattice_c": 4.982, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 4, "category": "binary_nitride"},
        {"composition": "CaF2", "space_group": "Fm-3m", "space_group_number": 225,
         "crystal_system": "cubic", "lattice_a": 5.463, "lattice_b": 5.463,
         "lattice_c": 5.463, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 12, "category": "binary_fluoride"},
        {"composition": "MgB2", "space_group": "P6/mmm", "space_group_number": 191,
         "crystal_system": "hexagonal", "lattice_a": 3.086, "lattice_b": 3.086,
         "lattice_c": 3.524, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 3, "category": "binary_boride"},
        {"composition": "Nb3Sn", "space_group": "Pm-3n", "space_group_number": 223,
         "crystal_system": "cubic", "lattice_a": 5.290, "lattice_b": 5.290,
         "lattice_c": 5.290, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "a15_intermetallic"},
        {"composition": "V3Si", "space_group": "Pm-3n", "space_group_number": 223,
         "crystal_system": "cubic", "lattice_a": 4.722, "lattice_b": 4.722,
         "lattice_c": 4.722, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "a15_intermetallic"},
        {"composition": "NbN", "space_group": "Fm-3m", "space_group_number": 225,
         "crystal_system": "cubic", "lattice_a": 4.392, "lattice_b": 4.392,
         "lattice_c": 4.392, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "binary_nitride"},
        # --- Ternary compounds ---
        {"composition": "SrTiO3", "space_group": "Pm-3m", "space_group_number": 221,
         "crystal_system": "cubic", "lattice_a": 3.905, "lattice_b": 3.905,
         "lattice_c": 3.905, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 5, "category": "perovskite"},
        {"composition": "BaTiO3", "space_group": "P4mm", "space_group_number": 99,
         "crystal_system": "tetragonal", "lattice_a": 3.994, "lattice_b": 3.994,
         "lattice_c": 4.034, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 5, "category": "perovskite"},
        {"composition": "CaTiO3", "space_group": "Pnma", "space_group_number": 62,
         "crystal_system": "orthorhombic", "lattice_a": 5.381, "lattice_b": 7.645,
         "lattice_c": 5.443, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 20, "category": "perovskite"},
        {"composition": "LaAlO3", "space_group": "R-3c", "space_group_number": 167,
         "crystal_system": "trigonal", "lattice_a": 5.365, "lattice_b": 5.365,
         "lattice_c": 13.11, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 30, "category": "perovskite"},
        {"composition": "YBa2Cu3O7", "space_group": "Pmmm", "space_group_number": 47,
         "crystal_system": "orthorhombic", "lattice_a": 3.820, "lattice_b": 3.886,
         "lattice_c": 11.680, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 13, "category": "cuprate"},
        {"composition": "La2CuO4", "space_group": "I4/mmm", "space_group_number": 139,
         "crystal_system": "tetragonal", "lattice_a": 3.787, "lattice_b": 3.787,
         "lattice_c": 13.229, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 14, "category": "cuprate"},
        {"composition": "LaFeAsO", "space_group": "P4/nmm", "space_group_number": 129,
         "crystal_system": "tetragonal", "lattice_a": 4.035, "lattice_b": 4.035,
         "lattice_c": 8.741, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 8, "category": "iron_pnictide"},
        {"composition": "BaFe2As2", "space_group": "I4/mmm", "space_group_number": 139,
         "crystal_system": "tetragonal", "lattice_a": 3.963, "lattice_b": 3.963,
         "lattice_c": 13.017, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 10, "category": "iron_pnictide"},
        # --- Low-symmetry / monoclinic / triclinic ---
        {"composition": "Li2MnO3", "space_group": "C2/m", "space_group_number": 12,
         "crystal_system": "monoclinic", "lattice_a": 4.937, "lattice_b": 8.532,
         "lattice_c": 5.030, "lattice_alpha": 90, "lattice_beta": 109.46,
         "lattice_gamma": 90, "n_atoms_cell": 24, "category": "layered_oxide"},
        {"composition": "CuFeS2", "space_group": "I-42d", "space_group_number": 122,
         "crystal_system": "tetragonal", "lattice_a": 5.289, "lattice_b": 5.289,
         "lattice_c": 10.423, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 16, "category": "chalcopyrite"},
        {"composition": "Al2O3", "space_group": "R-3c", "space_group_number": 167,
         "crystal_system": "trigonal", "lattice_a": 4.759, "lattice_b": 4.759,
         "lattice_c": 12.991, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 120, "n_atoms_cell": 30, "category": "corundum"},
        {"composition": "CeCoIn5", "space_group": "P4/mmm", "space_group_number": 123,
         "crystal_system": "tetragonal", "lattice_a": 4.620, "lattice_b": 4.620,
         "lattice_c": 7.560, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 7, "category": "heavy_fermion"},
        {"composition": "FeSe", "space_group": "P4/nmm", "space_group_number": 129,
         "crystal_system": "tetragonal", "lattice_a": 3.770, "lattice_b": 3.770,
         "lattice_c": 5.520, "lattice_alpha": 90, "lattice_beta": 90,
         "lattice_gamma": 90, "n_atoms_cell": 4, "category": "iron_chalcogenide"},
    ]


def load_formation_energy_25() -> list:
    """Load 25 compounds with DFT formation energies for energy prediction benchmarking.

    Energies are formation energies per atom in eV/atom from Materials Project
    (GGA/GGA+U calculations). Useful for benchmarking GNN energy models.
    """
    return _load_json_or_fallback("formation_energy_25", _embedded_formation_energy_25)


def _embedded_formation_energy_25() -> list:
    """25 compounds with experimentally validated DFT formation energies.

    Sources: Materials Project (mp-ids), corrected GGA/GGA+U.
    Fields: composition, mp_id, space_group, space_group_number,
    formation_energy_eV_atom, energy_above_hull_eV_atom,
    lattice_a, lattice_c, band_gap_eV, category.
    """
    return [
        # --- Simple binary compounds ---
        {"composition": "NaCl", "mp_id": "mp-22862", "space_group": "Fm-3m",
         "space_group_number": 225, "formation_energy_eV_atom": -1.887,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.640, "lattice_c": 5.640,
         "band_gap_eV": 5.0, "category": "binary_halide"},
        {"composition": "MgO", "mp_id": "mp-1265", "space_group": "Fm-3m",
         "space_group_number": 225, "formation_energy_eV_atom": -3.054,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 4.212, "lattice_c": 4.212,
         "band_gap_eV": 4.45, "category": "binary_oxide"},
        {"composition": "TiO2", "mp_id": "mp-2657", "space_group": "P4_2/mnm",
         "space_group_number": 136, "formation_energy_eV_atom": -3.264,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 4.594, "lattice_c": 2.959,
         "band_gap_eV": 1.78, "category": "binary_oxide"},
        {"composition": "Al2O3", "mp_id": "mp-1143", "space_group": "R-3c",
         "space_group_number": 167, "formation_energy_eV_atom": -3.346,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 4.759, "lattice_c": 12.991,
         "band_gap_eV": 5.85, "category": "binary_oxide"},
        {"composition": "ZnO", "mp_id": "mp-2133", "space_group": "P6_3mc",
         "space_group_number": 186, "formation_energy_eV_atom": -1.768,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 3.250, "lattice_c": 5.207,
         "band_gap_eV": 0.73, "category": "binary_oxide"},
        {"composition": "GaAs", "mp_id": "mp-2534", "space_group": "F-43m",
         "space_group_number": 216, "formation_energy_eV_atom": -0.358,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.653, "lattice_c": 5.653,
         "band_gap_eV": 0.19, "category": "binary_semiconductor"},
        {"composition": "SiC", "mp_id": "mp-8062", "space_group": "F-43m",
         "space_group_number": 216, "formation_energy_eV_atom": -0.365,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 4.358, "lattice_c": 4.358,
         "band_gap_eV": 1.37, "category": "binary_carbide"},
        {"composition": "CaF2", "mp_id": "mp-2741", "space_group": "Fm-3m",
         "space_group_number": 225, "formation_energy_eV_atom": -4.213,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.463, "lattice_c": 5.463,
         "band_gap_eV": 7.0, "category": "binary_fluoride"},
        {"composition": "BN", "mp_id": "mp-984", "space_group": "P6_3/mmc",
         "space_group_number": 194, "formation_energy_eV_atom": -1.330,
         "energy_above_hull_eV_atom": 0.003, "lattice_a": 2.504, "lattice_c": 6.661,
         "band_gap_eV": 4.48, "category": "binary_nitride"},
        {"composition": "AlN", "mp_id": "mp-661", "space_group": "P6_3mc",
         "space_group_number": 186, "formation_energy_eV_atom": -1.613,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 3.112, "lattice_c": 4.982,
         "band_gap_eV": 4.04, "category": "binary_nitride"},
        {"composition": "NbN", "mp_id": "mp-2634", "space_group": "Fm-3m",
         "space_group_number": 225, "formation_energy_eV_atom": -1.276,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 4.392, "lattice_c": 4.392,
         "band_gap_eV": 0.0, "category": "binary_nitride"},
        # --- Superconductor-relevant compounds ---
        {"composition": "MgB2", "mp_id": "mp-763", "space_group": "P6/mmm",
         "space_group_number": 191, "formation_energy_eV_atom": -0.144,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 3.086, "lattice_c": 3.524,
         "band_gap_eV": 0.0, "category": "binary_boride"},
        {"composition": "Nb3Sn", "mp_id": "mp-2071", "space_group": "Pm-3n",
         "space_group_number": 223, "formation_energy_eV_atom": -0.134,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.290, "lattice_c": 5.290,
         "band_gap_eV": 0.0, "category": "a15_intermetallic"},
        {"composition": "V3Si", "mp_id": "mp-978", "space_group": "Pm-3n",
         "space_group_number": 223, "formation_energy_eV_atom": -0.218,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 4.722, "lattice_c": 4.722,
         "band_gap_eV": 0.0, "category": "a15_intermetallic"},
        {"composition": "FeSe", "mp_id": "mp-2008", "space_group": "P4/nmm",
         "space_group_number": 129, "formation_energy_eV_atom": -0.440,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 3.770, "lattice_c": 5.520,
         "band_gap_eV": 0.0, "category": "iron_chalcogenide"},
        # --- Perovskites ---
        {"composition": "SrTiO3", "mp_id": "mp-5229", "space_group": "Pm-3m",
         "space_group_number": 221, "formation_energy_eV_atom": -3.336,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 3.905, "lattice_c": 3.905,
         "band_gap_eV": 1.77, "category": "perovskite"},
        {"composition": "BaTiO3", "mp_id": "mp-5986", "space_group": "P4mm",
         "space_group_number": 99, "formation_energy_eV_atom": -3.217,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 3.994, "lattice_c": 4.034,
         "band_gap_eV": 1.75, "category": "perovskite"},
        {"composition": "CaTiO3", "mp_id": "mp-4019", "space_group": "Pnma",
         "space_group_number": 62, "formation_energy_eV_atom": -3.425,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.381, "lattice_c": 5.443,
         "band_gap_eV": 1.95, "category": "perovskite"},
        {"composition": "LaAlO3", "mp_id": "mp-2920", "space_group": "R-3c",
         "space_group_number": 167, "formation_energy_eV_atom": -3.530,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.365, "lattice_c": 13.11,
         "band_gap_eV": 3.52, "category": "perovskite"},
        # --- Battery / energy materials ---
        {"composition": "LiFePO4", "mp_id": "mp-19017", "space_group": "Pnma",
         "space_group_number": 62, "formation_energy_eV_atom": -2.403,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 10.334, "lattice_c": 4.694,
         "band_gap_eV": 3.71, "category": "olivine"},
        {"composition": "LiCoO2", "mp_id": "mp-22526", "space_group": "R-3m",
         "space_group_number": 166, "formation_energy_eV_atom": -2.090,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 2.816, "lattice_c": 14.054,
         "band_gap_eV": 0.98, "category": "layered_oxide"},
        {"composition": "LiMn2O4", "mp_id": "mp-18767", "space_group": "Fd-3m",
         "space_group_number": 227, "formation_energy_eV_atom": -2.300,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 8.248, "lattice_c": 8.248,
         "band_gap_eV": 0.90, "category": "spinel"},
        # --- Other functional materials ---
        {"composition": "Fe3O4", "mp_id": "mp-19306", "space_group": "Fd-3m",
         "space_group_number": 227, "formation_energy_eV_atom": -1.911,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 8.394, "lattice_c": 8.394,
         "band_gap_eV": 0.0, "category": "spinel"},
        {"composition": "CuFeS2", "mp_id": "mp-2519", "space_group": "I-42d",
         "space_group_number": 122, "formation_energy_eV_atom": -0.546,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.289, "lattice_c": 10.423,
         "band_gap_eV": 0.05, "category": "chalcopyrite"},
        {"composition": "ZrO2", "mp_id": "mp-2858", "space_group": "P2_1/c",
         "space_group_number": 14, "formation_energy_eV_atom": -3.650,
         "energy_above_hull_eV_atom": 0.0, "lattice_a": 5.169, "lattice_c": 5.232,
         "band_gap_eV": 3.44, "category": "binary_oxide"},
    ]


def load_rtap_candidates_40() -> list:
    """Load 40 RTAP reference entries spanning confirmed, theoretical, and speculative SC.

    Covers the full landscape from 133K cuprates through high-pressure hydrides
    to speculative room-temperature ambient-pressure targets, plus non-SC controls.

    Each entry: composition, Tc_K, crystal_system, space_group, family,
    mechanism, pressure_GPa, is_confirmed (bool).
    """
    return _load_json_or_fallback("rtap_candidates_40", _embedded_rtap_candidates_40)


def _embedded_rtap_candidates_40() -> list:
    return [
        # --- Confirmed high-Tc superconductors (15 entries) ---
        {"composition": "HgBa2Ca2Cu3O8", "Tc_K": 133, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "HgBa2Ca3Cu4O10", "Tc_K": 127, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Tl2Ba2Ca2Cu3O10", "Tc_K": 125, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Bi2Sr2Ca2Cu3O10", "Tc_K": 110, "crystal_system": "orthorhombic",
         "space_group": "Amaa", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "YBa2Cu3O7", "Tc_K": 92, "crystal_system": "orthorhombic",
         "space_group": "Pmmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "La3Ni2O7", "Tc_K": 80, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "family": "nickelate", "mechanism": "s+-_pairing",
         "pressure_GPa": 14, "is_confirmed": True},
        {"composition": "MgB2", "Tc_K": 39, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "mgb2-type", "mechanism": "phonon-mediated",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Cs3C60", "Tc_K": 38, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "fulleride", "mechanism": "phonon-mediated",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "LaFeAsO0.9F0.1", "Tc_K": 26, "crystal_system": "tetragonal",
         "space_group": "P4/nmm", "family": "iron-pnictide", "mechanism": "spin-fluctuation",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Nd0.8Sr0.2NiO2", "Tc_K": 15, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "nickelate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "H3S", "Tc_K": 203, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 150, "is_confirmed": True},
        {"composition": "LaH10", "Tc_K": 250, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 190, "is_confirmed": True},
        {"composition": "YH9", "Tc_K": 243, "crystal_system": "hexagonal",
         "space_group": "P6_3/mmc", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 201, "is_confirmed": True},
        {"composition": "CaH6", "Tc_K": 215, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 172, "is_confirmed": True},
        {"composition": "CeH10", "Tc_K": 116, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 90, "is_confirmed": True},
        # --- Theoretical predictions (10 entries) ---
        {"composition": "LaBeH8", "Tc_K": 110, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 50, "is_confirmed": False},
        {"composition": "YCeH20", "Tc_K": 280, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 150, "is_confirmed": False},
        {"composition": "LaBH8", "Tc_K": 180, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 100, "is_confirmed": False},
        {"composition": "MgScH12", "Tc_K": 260, "crystal_system": "hexagonal",
         "space_group": "P6_3/mmc", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 120, "is_confirmed": False},
        {"composition": "CaYH12", "Tc_K": 235, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 80, "is_confirmed": False},
        {"composition": "SrScH12", "Tc_K": 220, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 90, "is_confirmed": False},
        {"composition": "HgBa2Ca4Cu5O12", "Tc_K": 145, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "Tl2Ba2Ca3Cu4O12", "Tc_K": 138, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "Bi2Sr2Ca3Cu4O12", "Tc_K": 120, "crystal_system": "orthorhombic",
         "space_group": "Amaa", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "BaSrNi2O6", "Tc_K": 90, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "family": "nickelate", "mechanism": "s+-_pairing",
         "pressure_GPa": 10, "is_confirmed": False},
        # --- Speculative targets (10 entries) ---
        {"composition": "Li2MoH12", "Tc_K": 300, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 50, "is_confirmed": False},
        {"composition": "NaScH10", "Tc_K": 290, "crystal_system": "hexagonal",
         "space_group": "P6_3/mmc", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 30, "is_confirmed": False},
        {"composition": "BaYH14", "Tc_K": 310, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "ternary-hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 20, "is_confirmed": False},
        {"composition": "CsTi3Bi5", "Tc_K": 4, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "kagome", "mechanism": "flat-band",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "RbV3Sb5", "Tc_K": 5, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "kagome", "mechanism": "flat-band",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "CsV3Sb5", "Tc_K": 2.5, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "kagome", "mechanism": "flat-band",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Cu3(BHT)2", "Tc_K": 0.25, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "mof-sc", "mechanism": "electron-phonon_mof",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "Ni3(HITP)2", "Tc_K": 0.3, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "mof-sc", "mechanism": "electron-phonon_mof",
         "pressure_GPa": 0, "is_confirmed": False},
        {"composition": "TBG-C2", "Tc_K": 1.7, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "flat-band", "mechanism": "flat-band",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "CaKFe4As4", "Tc_K": 35, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "iron-pnictide", "mechanism": "spin-fluctuation",
         "pressure_GPa": 0, "is_confirmed": True},
        # --- Control non-SC compositions (5 entries) ---
        {"composition": "Cu", "Tc_K": 0, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "elemental-metal", "mechanism": "none",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Fe", "Tc_K": 0, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "elemental-metal", "mechanism": "none",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "SiO2", "Tc_K": 0, "crystal_system": "trigonal",
         "space_group": "P3_121", "family": "insulator", "mechanism": "none",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "Al2O3", "Tc_K": 0, "crystal_system": "trigonal",
         "space_group": "R-3c", "family": "insulator", "mechanism": "none",
         "pressure_GPa": 0, "is_confirmed": True},
        {"composition": "NaCl", "Tc_K": 0, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "insulator", "mechanism": "none",
         "pressure_GPa": 0, "is_confirmed": True},
    ]


def load_high_tc_reference_15() -> list:
    """Load 15 highest confirmed Tc values for calibration.

    Contains the most important reference points for superconductor Tc
    prediction, spanning ambient-pressure cuprates through high-pressure
    hydrides and unconventional superconductors.

    Each entry: composition, Tc_K, crystal_system, space_group, family,
    mechanism, pressure_GPa.
    """
    return _load_json_or_fallback("high_tc_reference_15", _embedded_high_tc_reference_15)


def _embedded_high_tc_reference_15() -> list:
    return [
        {"composition": "LaH10", "Tc_K": 250, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 190},
        {"composition": "YH9", "Tc_K": 243, "crystal_system": "hexagonal",
         "space_group": "P6_3/mmc", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 201},
        {"composition": "CaH6", "Tc_K": 215, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 172},
        {"composition": "H3S", "Tc_K": 203, "crystal_system": "cubic",
         "space_group": "Im-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 150},
        {"composition": "HgBa2Ca2Cu3O8", "Tc_K": 133, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0},
        {"composition": "HgBa2Ca3Cu4O10", "Tc_K": 127, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0},
        {"composition": "Tl2Ba2Ca2Cu3O10", "Tc_K": 125, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0},
        {"composition": "CeH10", "Tc_K": 116, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 90},
        {"composition": "Bi2Sr2Ca2Cu3O10", "Tc_K": 110, "crystal_system": "orthorhombic",
         "space_group": "Amaa", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0},
        {"composition": "LaBeH8", "Tc_K": 110, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "hydride", "mechanism": "phonon-mediated",
         "pressure_GPa": 50},
        {"composition": "YBa2Cu3O7", "Tc_K": 92, "crystal_system": "orthorhombic",
         "space_group": "Pmmm", "family": "cuprate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0},
        {"composition": "La3Ni2O7", "Tc_K": 80, "crystal_system": "tetragonal",
         "space_group": "I4/mmm", "family": "nickelate", "mechanism": "s+-_pairing",
         "pressure_GPa": 14},
        {"composition": "Cs3C60", "Tc_K": 38, "crystal_system": "cubic",
         "space_group": "Fm-3m", "family": "fulleride", "mechanism": "phonon-mediated",
         "pressure_GPa": 0},
        {"composition": "Nd0.8Sr0.2NiO2", "Tc_K": 15, "crystal_system": "tetragonal",
         "space_group": "P4/mmm", "family": "nickelate", "mechanism": "d-wave_pairing",
         "pressure_GPa": 0},
        {"composition": "CsV3Sb5", "Tc_K": 2.5, "crystal_system": "hexagonal",
         "space_group": "P6/mmm", "family": "kagome", "mechanism": "flat-band",
         "pressure_GPa": 0},
    ]
