"""
Agent Sin — Simulation Agent
==============================
Responsible for:
  1. Reading crystal pattern cards from Agent CS
  2. Generating candidate crystal structures via perturbation/diffusion
  3. Predicting superconducting properties (Tc, lambda, stability)
  4. Outputting synthetic datasets for Agent Ob to evaluate
"""
from __future__ import annotations

import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.core.config import (
    CRYSTAL_PATTERNS_DIR,
    SYNTHETIC_DIR,
    REFINEMENTS_DIR,
    DEFAULT_STRUCTURES_PER_PATTERN,
    DEFAULT_TARGET_PRESSURE_GPA,
    DIFFUSION_STEPS,
    STABILITY_THRESHOLD_MEV,
    DAMPING_FACTOR,
    ensure_dirs,
)
from src.core.schemas import (
    PatternCard,
    LatticeParams,
    SyntheticStructure,
    RefinementReport,
    load_pattern_catalog,
)

logger = logging.getLogger("AgentSin")

# Map pattern_id prefix → canonical family key (matching Agent Ob's naming)
PATTERN_FAMILY_MAP = {
    "cuprate-layered": "cuprate",
    "cuprate-multilayer": "cuprate",
    "iron-pnictide": "iron_pnictide",
    "iron-chalcogenide": "iron_chalcogenide",
    "heavy-fermion": "heavy_fermion",
    "mgb2-type": "mgb2_type",
    "a15": "a15",
    "hydride": "hydride",
    "hydride-lah10": "hydride",
    "nickelate": "nickelate",
    "chevrel": "chevrel",
    # RTAP families
    "kagome": "kagome",
    "ternary-hydride": "ternary_hydride",
    "infinite-layer": "infinite_layer",
    "topological": "topological",
    "2d-heterostructure": "2d_heterostructure",
    "carbon-based": "carbon_based",
    "engineered-cuprate": "engineered_cuprate",
    "mof-sc": "mof_sc",
    "flat-band": "flat_band",
}


# RTAP exploration boosts: push coupling toward the upper theoretical
# bound of each family for discovery-oriented search.
RTAP_LAMBDA_BOOST = {
    "kagome": 1.5,              # flat-band: lambda 0.8→1.2 → Tc ~300K
    "ternary_hydride": 1.4,     # hydride: lambda 2.2→3.08
    "infinite_layer": 1.5,      # spin-fluc: lambda 1.2→1.8
    "engineered_cuprate": 1.3,  # spin-fluc: lambda 2.2→2.86
    "carbon_based": 1.5,        # flat-band: lambda 1.0→1.5
    "2d_heterostructure": 1.6,  # flat-band: lambda 1.0→1.6
    "topological": 1.6,         # spin-fluc: lambda 0.9→1.44
    "mof_sc": 1.2,              # excitonic: already above 273K
    "flat_band": 1.3,           # flat-band: lambda 1.0→1.3
}


def get_family_key(pattern_id: str) -> str:
    """Extract canonical family key from pattern_id, matching Agent Ob's naming."""
    prefix = pattern_id.rsplit("-", 1)[0]  # "iron-pnictide-001" → "iron-pnictide"
    return PATTERN_FAMILY_MAP.get(prefix, prefix.replace("-", "_"))


# ---------------------------------------------------------------------------
# Physics-based models (surrogate / simplified)
# ---------------------------------------------------------------------------

def allen_dynes_tc(lambda_ep: float, omega_log_K: float = 300.0, mu_star: float = 0.13) -> float:
    """
    Allen-Dynes formula for superconducting Tc.
    Tc = (omega_log / 1.2) * exp[-1.04(1+lambda) / (lambda - mu*(1+0.62*lambda))]
    Returns Tc in Kelvin.
    """
    if lambda_ep <= mu_star * (1 + 0.62 * lambda_ep):
        return 0.0
    numerator = -1.04 * (1 + lambda_ep)
    denominator = lambda_ep - mu_star * (1 + 0.62 * lambda_ep)
    if denominator <= 0:
        return 0.0
    tc = (omega_log_K / 1.2) * np.exp(numerator / denominator)
    return max(0.0, tc)


def estimate_lambda_from_pattern(pattern: PatternCard, noise: float = 0.0) -> float:
    """
    Estimate electron-phonon coupling lambda from pattern card features.
    Uses a simplified empirical model based on crystal family correlations.
    """
    base_lambda = 0.5  # default

    if pattern.electronic_features and pattern.electronic_features.electron_phonon_lambda:
        base_lambda = pattern.electronic_features.electron_phonon_lambda

    # Add controlled noise for variation
    return max(0.01, base_lambda + noise)


def estimate_omega_log(pattern: PatternCard) -> float:
    """
    Estimate logarithmic average phonon frequency (in Kelvin).
    Lighter elements → higher phonon frequencies.
    """
    family = pattern.pattern_id.split("-")[0]
    omega_map = {
        "cuprate": 350.0,
        "iron": 250.0,
        "heavy": 120.0,
        "mgb2": 600.0,
        "a15": 250.0,
        "hydride": 1500.0,
        "nickelate": 300.0,
        "chevrel": 180.0,
        # RTAP families
        "kagome": 350.0,
        "ternary": 1200.0,
        "infinite": 350.0,
        "topological": 180.0,
        "2d": 200.0,
        "carbon": 600.0,
        "engineered": 400.0,
        "mof": 150.0,
        "flat": 500.0,
    }
    for key, val in omega_map.items():
        if key in family:
            return val
    return 300.0


def _estimate_H_fraction(composition_str: str) -> float:
    """Estimate hydrogen atom fraction from a composition string."""
    from src.agents.agent_cs import parse_composition
    comp = parse_composition(composition_str)
    total = sum(comp.values())
    if total == 0:
        return 0.0
    return comp.get("H", 0.0) / total


def _avg_electronegativity(composition_str: str) -> float:
    """Compute average electronegativity of non-hydrogen elements."""
    from src.agents.agent_cs import parse_composition, ELEMENT_DATA
    comp = parse_composition(composition_str)
    total_weight = 0.0
    weighted_en = 0.0
    for elem, count in comp.items():
        if elem == "H":
            continue
        en = ELEMENT_DATA.get(elem, {}).get("electronegativity", 1.5)
        weighted_en += en * count
        total_weight += count
    if total_weight == 0:
        return 1.5
    return weighted_en / total_weight


def compute_stability(pattern: PatternCard, perturbation_scale: float) -> float:
    """
    Estimate energy above hull (meV/atom) — lower is more stable.
    Structures close to known patterns are more stable.
    """
    # Base stability from known compounds
    base_stability = 10.0  # Known compounds are near the hull
    # Perturbation increases instability
    return base_stability + perturbation_scale * 100 * np.random.exponential(0.3)


# ---------------------------------------------------------------------------
# Structure generation
# ---------------------------------------------------------------------------

def perturb_lattice(base: LatticeParams, scale: float) -> LatticeParams:
    """
    Generate a perturbed lattice by applying noise to lattice parameters.
    Mimics the diffusion-based generation approach.
    """
    return LatticeParams(
        a=max(2.0, base.a * (1 + np.random.normal(0, scale))),
        b=max(2.0, (base.b or base.a) * (1 + np.random.normal(0, scale))),
        c=max(2.0, base.c * (1 + np.random.normal(0, scale))),
        alpha=base.alpha + np.random.normal(0, scale * 2),
        beta=base.beta + np.random.normal(0, scale * 2),
        gamma=base.gamma + np.random.normal(0, scale * 2),
    )


def generate_composition_variant(source_compound: str, pattern: PatternCard) -> str:
    """
    Generate a composition variant by substituting elements at dopant sites.
    For now uses simple string-based substitution; in production would use
    pymatgen's substitution predictor.
    """
    from src.agents.agent_cs import parse_composition

    comp = parse_composition(source_compound)
    if not comp:
        return source_compound

    # Randomly perturb stoichiometry slightly
    new_comp = {}
    for elem, count in comp.items():
        perturbed = max(0.1, count * (1 + np.random.normal(0, 0.1)))
        new_comp[elem] = round(perturbed, 2)

    # Build formula string
    parts = []
    for elem, count in new_comp.items():
        if abs(count - round(count)) < 0.01:
            count_str = str(int(round(count))) if round(count) != 1 else ""
        else:
            count_str = f"{count:.2f}"
        parts.append(f"{elem}{count_str}")

    return "".join(parts)


def generate_structures_for_pattern(
    pattern: PatternCard,
    num_structures: int,
    iteration: int,
    model_adjustments: dict | None = None,
    target_pressure_GPa: float = 0.0,
) -> list[SyntheticStructure]:
    """
    Generate synthetic crystal structures for a given pattern.

    This is the core generative step, implementing a simplified version of
    the diffusion-based approach described in the plan:
    1. Start from known structure (pattern card)
    2. Apply controlled perturbations (diffusion noise)
    3. Predict properties using surrogate models
    4. Filter by stability
    """
    structures = []
    adjustments = model_adjustments or {}

    # Get model parameters with possible refinement adjustments
    # Look up family-specific lambda scaling first, fall back to global
    family_key = get_family_key(pattern.pattern_id)
    lambda_scaling = adjustments.get(f"lambda_scaling_{family_key}",
                                      adjustments.get("lambda_scaling", 1.0))
    perturbation_scale = adjustments.get("perturbation_scale", 0.05)
    mu_star = adjustments.get("mu_star", 0.13)

    omega_log = estimate_omega_log(pattern)

    for i in range(num_structures):
        # 1. Perturb lattice
        lattice = perturb_lattice(pattern.lattice_params, perturbation_scale)

        # 2. Generate composition variant
        source = np.random.choice(pattern.source_compounds)
        composition = generate_composition_variant(source, pattern)

        # 3. Estimate electron-phonon coupling
        # RTAP families get wider exploration noise + discovery boost
        is_rtap_family = family_key in (
            "kagome", "ternary_hydride", "infinite_layer", "topological",
            "2d_heterostructure", "carbon_based", "engineered_cuprate",
            "mof_sc", "flat_band",
        )
        lambda_noise_scale = 0.25 if is_rtap_family else 0.10
        noise = np.random.normal(0, lambda_noise_scale)
        lambda_ep = estimate_lambda_from_pattern(pattern, noise) * lambda_scaling

        # RTAP exploration boost: in discovery mode, explore the optimistic
        # end of parameter space. Physically represents the hypothesis that
        # engineered compositions can achieve coupling at the upper bound
        # of each family's theoretical range.
        if is_rtap_family:
            rtap_boost = RTAP_LAMBDA_BOOST.get(family_key, 1.0)
            lambda_ep *= rtap_boost

        # 4. Compute Tc — multi-mechanism dispatch for RTAP
        mechanism = "bcs"
        mechanism_confidence = 0.7
        tc_by_mechanism = {}

        ef = pattern.electronic_features
        if ef and hasattr(ef, "pairing_mechanism") and ef.pairing_mechanism:
            mechanism = ef.pairing_mechanism

        # Try multi-mechanism estimator first
        try:
            from src.core.tc_models import estimate_tc_composite
            tc_params = {
                "lambda_ep": lambda_ep,
                "omega_log_K": omega_log,
                "mu_star": mu_star,
            }
            # Add mechanism-specific parameters from electronic features
            # with per-structure variation to explore parameter space
            if ef:
                if ef.spin_fluctuation_T_K:
                    # Vary T_sf by ±20% for exploration
                    T_sf_var = ef.spin_fluctuation_T_K * (1 + np.random.normal(0, 0.20))
                    tc_params["T_sf_K"] = max(10.0, T_sf_var)
                if ef.nesting_strength:
                    nest_var = ef.nesting_strength + np.random.normal(0, 0.08)
                    tc_params["nesting_strength"] = np.clip(nest_var, 0.0, 1.0)
                if ef.flat_band_width_eV:
                    # Vary bandwidth: narrower bands = higher Tc, explore downward
                    W_var = ef.flat_band_width_eV * (1 + np.random.normal(-0.1, 0.20))
                    tc_params["W_bandwidth_eV"] = max(0.001, W_var)
                if ef.dos_at_ef_states_eV:
                    dos_var = ef.dos_at_ef_states_eV * (1 + np.random.normal(0, 0.15))
                    tc_params["dos_at_ef"] = max(0.1, dos_var)
                if ef.exciton_energy_eV:
                    exc_var = ef.exciton_energy_eV * (1 + np.random.normal(0, 0.15))
                    tc_params["exciton_energy_eV"] = max(0.01, exc_var)
                if ef.excitonic_coupling_V:
                    V_var = ef.excitonic_coupling_V * (1 + np.random.normal(0, 0.15))
                    tc_params["coupling_V"] = max(0.01, V_var)
            # For hydride_cage, estimate H fraction from composition
            if mechanism == "hydride_cage":
                tc_params["H_fraction"] = _estimate_H_fraction(composition)
                tc_params["stabilizer_electronegativity"] = _avg_electronegativity(composition)

            tc_result = estimate_tc_composite(mechanism, **tc_params)
            predicted_tc = tc_result["Tc_K"]
            mechanism_confidence = tc_result.get("confidence", 0.5)
            tc_by_mechanism = tc_result.get("tc_all_mechanisms", {mechanism: predicted_tc})
            if not tc_by_mechanism:
                tc_by_mechanism = {mechanism: predicted_tc}
        except ImportError:
            # Fallback to classic Allen-Dynes + boost
            predicted_tc = allen_dynes_tc(lambda_ep, omega_log, mu_star)
            boost_key = f"tc_boost_{family_key}"
            default_boosts = {"cuprate": 2.5, "nickelate": 1.8, "heavy_fermion": 0.3}
            boost = adjustments.get(boost_key, default_boosts.get(family_key, 1.0))
            predicted_tc *= boost
            tc_by_mechanism = {"bcs": predicted_tc}

        # For BCS mechanism, still apply family-specific boosts
        if mechanism == "bcs":
            boost_key = f"tc_boost_{family_key}"
            default_boosts = {"cuprate": 2.5, "nickelate": 1.8, "heavy_fermion": 0.3}
            boost = adjustments.get(boost_key, default_boosts.get(family_key, 1.0))
            predicted_tc *= boost

        # 4b. Pressure correction via Agent P (Grüneisen surrogate)
        volume_per_atom = 0.0
        ambient_tc = predicted_tc  # Save ambient-pressure Tc
        if pattern.pressure_params is not None and target_pressure_GPa != 0.0:
            from src.agents.agent_p import volume_at_pressure, lambda_at_volume, gruneisen_omega_log
            pp = pattern.pressure_params
            try:
                V_P = volume_at_pressure(target_pressure_GPa, pp.V0_per_atom_A3,
                                         pp.B0_GPa, pp.B0_prime)
                corrected_omega = gruneisen_omega_log(V_P, pp.V0_per_atom_A3,
                                                      omega_log, pp.gruneisen_gamma)
                base_lambda = estimate_lambda_from_pattern(pattern, noise)
                corrected_lambda = lambda_at_volume(V_P, pp.V0_per_atom_A3,
                                                     base_lambda, pp.eta_lambda)
                predicted_tc = allen_dynes_tc(corrected_lambda, corrected_omega, mu_star)
                if pp.Tc_ceiling_K > 0:
                    predicted_tc = min(predicted_tc, pp.Tc_ceiling_K)
                volume_per_atom = V_P
            except Exception as exc:
                logger.warning(f"Pressure correction failed for {pattern.pattern_id}: {exc}")

        # 5. Stability estimate
        e_above_hull = compute_stability(pattern, perturbation_scale)
        stability_conf = max(0, 1 - e_above_hull / (STABILITY_THRESHOLD_MEV * 2))

        # 6. Generate structure ID
        struct_id = hashlib.md5(
            f"{pattern.pattern_id}_{iteration}_{i}_{composition}".encode()
        ).hexdigest()[:12]

        structures.append(SyntheticStructure(
            structure_id=struct_id,
            pattern_id=pattern.pattern_id,
            composition=composition,
            crystal_system=pattern.crystal_system,
            space_group=pattern.space_group,
            lattice_params=lattice,
            predicted_Tc_K=round(max(0, predicted_tc), 2),
            electron_phonon_lambda=round(lambda_ep, 4),
            energy_above_hull_meV=round(e_above_hull, 2),
            stability_confidence=round(stability_conf, 4),
            pressure_GPa=target_pressure_GPa,
            volume_per_atom_A3=round(volume_per_atom, 4),
            primary_mechanism=mechanism,
            mechanism_confidence=round(mechanism_confidence, 3),
            tc_by_mechanism=tc_by_mechanism,
            ambient_pressure_Tc_K=round(max(0, ambient_tc), 2),
        ))

    # Filter out clearly unstable structures
    stable = [s for s in structures if s.energy_above_hull_meV < STABILITY_THRESHOLD_MEV]
    logger.info(
        f"Pattern {pattern.pattern_id}: generated {len(structures)}, "
        f"stable: {len(stable)} (threshold: {STABILITY_THRESHOLD_MEV} meV)"
    )
    return stable


# ---------------------------------------------------------------------------
# Refinement application
# ---------------------------------------------------------------------------

def load_cumulative_state(state_path: Path) -> dict:
    """Load the cumulative model state from previous iterations."""
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {}


def save_cumulative_state(state: dict, state_path: Path):
    """Persist the current model state for the next iteration."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def parse_model_adjustments(report: RefinementReport, cumulative_state: dict) -> dict:
    """
    Extract model parameter adjustments from Agent Ob's refinement report.
    Uses cumulative_state to track the actual current value of each parameter
    across iterations, so corrections accumulate properly.
    """
    adjustments = dict(cumulative_state)  # Start from previous state
    sin_refinements = [r for r in report.refinements if r.target_agent == "Sin"]

    for ref in sin_refinements:
        if ref.parameter and ref.suggested_value is not None:
            # Use the actual current value from cumulative state, not the reported one
            actual_current = cumulative_state.get(ref.parameter, 1.0)
            suggested = float(ref.suggested_value)
            damped = actual_current + DAMPING_FACTOR * (suggested - actual_current)
            adjustments[ref.parameter] = damped
            logger.info(
                f"Adjustment: {ref.parameter} = {actual_current:.4f} → {damped:.4f} "
                f"(suggested: {suggested}, damping: {DAMPING_FACTOR})"
            )

    return adjustments


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def structures_to_dataframe(structures: list[SyntheticStructure]) -> pd.DataFrame:
    """Convert list of SyntheticStructure to a pandas DataFrame for CSV export."""
    rows = []
    for s in structures:
        rows.append({
            "structure_id": s.structure_id,
            "pattern_id": s.pattern_id,
            "composition": s.composition,
            "crystal_system": s.crystal_system,
            "space_group": s.space_group,
            "a": s.lattice_params.a,
            "b": s.lattice_params.b,
            "c": s.lattice_params.c,
            "alpha": s.lattice_params.alpha,
            "beta": s.lattice_params.beta,
            "gamma": s.lattice_params.gamma,
            "predicted_Tc_K": s.predicted_Tc_K,
            "electron_phonon_lambda": s.electron_phonon_lambda,
            "energy_above_hull_meV": s.energy_above_hull_meV,
            "stability_confidence": s.stability_confidence,
            "pressure_GPa": s.pressure_GPa,
            "volume_per_atom_A3": s.volume_per_atom_A3,
            "primary_mechanism": s.primary_mechanism,
            "mechanism_confidence": s.mechanism_confidence,
            "ambient_pressure_Tc_K": s.ambient_pressure_Tc_K,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Agent Sin main logic
# ---------------------------------------------------------------------------

class AgentSin:
    """Simulation Agent — generates synthetic superconductor data."""

    def __init__(self):
        ensure_dirs()
        self.model_adjustments: dict = {}
        self._mc3d_ref_cache: dict | None = None

    def load_patterns(self, iteration: int) -> list[PatternCard]:
        """Load the pattern catalog for this iteration."""
        path = CRYSTAL_PATTERNS_DIR / f"pattern_catalog_v{iteration:03d}.json"
        if not path.exists():
            # Fall back to latest available
            catalogs = sorted(CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"))
            if not catalogs:
                raise FileNotFoundError("No pattern catalogs found")
            path = catalogs[-1]

        patterns = load_pattern_catalog(path)
        logger.info(f"Loaded {len(patterns)} patterns from {path}")
        return patterns

    def load_refinements(self, iteration: int):
        """Load refinements from previous iteration, building on cumulative state."""
        state_path = SYNTHETIC_DIR / "model_state.json"
        cumulative = load_cumulative_state(state_path)

        if iteration == 0:
            self.model_adjustments = cumulative
            return

        ref_path = REFINEMENTS_DIR / f"iteration_{iteration - 1:03d}.json"
        if ref_path.exists():
            report = RefinementReport.load(ref_path)
            self.model_adjustments = parse_model_adjustments(report, cumulative)
            logger.info(f"Loaded {len(self.model_adjustments)} model adjustments (cumulative)")
        else:
            self.model_adjustments = cumulative

    def save_state(self):
        """Persist current model adjustments for the next iteration."""
        state_path = SYNTHETIC_DIR / "model_state.json"
        save_cumulative_state(self.model_adjustments, state_path)
        logger.info(f"Saved cumulative model state ({len(self.model_adjustments)} params)")

    def calibrate_from_mc3d(self, families: list[str] | None = None) -> dict:
        """Fetch reference structures from MC3D and calibrate model parameters.

        Queries the Materials Cloud MC3D database for experimentally-known
        crystal structures relevant to each RTAP family. Uses lattice
        parameters and element compositions to refine perturbation scales
        and validate seed patterns.

        Parameters
        ----------
        families : list[str], optional
            RTAP family names to calibrate against. If None, uses all
            RTAP families from the current pattern set.

        Returns
        -------
        dict
            Calibration report with per-family reference counts and
            any parameter adjustments derived from MC3D data.
        """
        if self._mc3d_ref_cache is not None:
            logger.info("MC3D calibration: using cached reference data")
            return self._mc3d_ref_cache

        calibration: dict = {"source": "mc3d", "families": {}, "adjustments": {}}
        try:
            from src.core.mc3d_client import MC3DClient
            client = MC3DClient()
            refs = client.fetch_reference_structures(families=families, limit=100)
            logger.info(f"MC3D calibration: fetched {len(refs)} reference structures")

            # Group by elements to map to families
            for ref in refs:
                elems = set(ref.elements)
                # Compute reference lattice volume for calibration
                cell = ref.cell
                if len(cell) == 3 and all(len(v) == 3 for v in cell):
                    a = np.array(cell)
                    vol = abs(np.dot(a[0], np.cross(a[1], a[2])))
                    vol_per_atom = vol / max(ref.n_atoms, 1)
                else:
                    vol_per_atom = 0.0

                # Track per-family stats
                family_key = "other"
                if {"Cu", "O"} <= elems:
                    family_key = "cuprate"
                elif {"Fe", "As"} <= elems or {"Fe", "P"} <= elems:
                    family_key = "iron_pnictide"
                elif {"H"} <= elems and {"La", "Y", "Ca"} & elems:
                    family_key = "hydride"
                elif {"Ni", "O"} <= elems:
                    family_key = "nickelate"
                elif {"Mg", "B"} <= elems:
                    family_key = "mgb2_type"
                elif {"V", "Sb"} <= elems:
                    family_key = "kagome"

                if family_key not in calibration["families"]:
                    calibration["families"][family_key] = {
                        "count": 0, "volumes": [], "formulas": [],
                    }
                calibration["families"][family_key]["count"] += 1
                if vol_per_atom > 0:
                    calibration["families"][family_key]["volumes"].append(vol_per_atom)
                calibration["families"][family_key]["formulas"].append(ref.formula)

            # Derive calibration adjustments: use MC3D volumes to refine
            # perturbation scale (larger volume spread → wider perturbation)
            for fam, data in calibration["families"].items():
                vols = data["volumes"]
                if len(vols) >= 3:
                    vol_std = float(np.std(vols))
                    vol_mean = float(np.mean(vols))
                    if vol_mean > 0:
                        rel_spread = vol_std / vol_mean
                        # Scale perturbation: more spread = wider exploration
                        calibration["adjustments"][f"perturbation_scale_{fam}"] = (
                            min(0.15, max(0.03, rel_spread))
                        )

            self._mc3d_ref_cache = calibration
        except Exception as e:
            logger.warning(f"MC3D calibration skipped (offline?): {e}")
            calibration["error"] = str(e)

        return calibration

    def generate(self, patterns: list[PatternCard], iteration: int,
                 target_pressure_GPa: float = 0.0) -> list[SyntheticStructure]:
        """Generate synthetic structures for all patterns."""
        all_structures = []

        for pattern in patterns:
            structures = generate_structures_for_pattern(
                pattern=pattern,
                num_structures=DEFAULT_STRUCTURES_PER_PATTERN,
                iteration=iteration,
                model_adjustments=self.model_adjustments,
                target_pressure_GPa=target_pressure_GPa,
            )
            all_structures.extend(structures)

        logger.info(f"Total synthetic structures generated: {len(all_structures)}")
        return all_structures

    def save_output(self, structures: list[SyntheticStructure], iteration: int, patterns: list[PatternCard]) -> Path:
        """Save synthetic data to the iteration directory."""
        out_dir = SYNTHETIC_DIR / f"iteration_{iteration:03d}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save properties CSV
        df = structures_to_dataframe(structures)
        csv_path = out_dir / "properties.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved {len(df)} structures to {csv_path}")

        # Save metadata
        metadata = {
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pattern_ids_used": [p.pattern_id for p in patterns],
            "num_structures": len(structures),
            "generation_params": {
                "structures_per_pattern": DEFAULT_STRUCTURES_PER_PATTERN,
                "diffusion_steps": DIFFUSION_STEPS,
                "stability_threshold_meV": STABILITY_THRESHOLD_MEV,
                "model_adjustments": self.model_adjustments,
            },
        }
        meta_path = out_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return out_dir


def run_agent_sin(iteration: int, target_pressure_GPa: float = 0.0) -> Path:
    """
    Main entry point for Agent Sin.
    Called by the orchestrator each iteration.
    Returns path to the output directory.
    """
    agent = AgentSin()

    # Load pattern catalog
    patterns = agent.load_patterns(iteration)

    # Load refinements from previous iteration
    agent.load_refinements(iteration)

    # Generate synthetic data
    structures = agent.generate(patterns, iteration,
                                target_pressure_GPa=target_pressure_GPa)

    # Save output and persist model state
    output_dir = agent.save_output(structures, iteration, patterns)
    agent.save_state()

    return output_dir


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Requires pattern catalog to exist first (run agent_cs.py first)
    path = run_agent_sin(iteration=0)
    print(f"Synthetic data saved to: {path}")
