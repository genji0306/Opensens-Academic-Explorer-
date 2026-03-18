"""
Agent Ob — Observator Agent
==============================
Responsible for:
  1. Loading real experimental superconductor data
  2. Loading synthetic data from Agent Sin
  3. Computing multi-component convergence scores
  4. Identifying discrepancies and generating refinement instructions
  5. Flagging novel candidates that don't match known compounds
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.core.config import (
    EXPERIMENTAL_DIR,
    SYNTHETIC_DIR,
    REFINEMENTS_DIR,
    NOVEL_CANDIDATES_DIR,
    REPORTS_DIR,
    SCORE_WEIGHTS,
    RTAP_SCORE_WEIGHTS,
    RTAP_TC_THRESHOLD_K,
    RTAP_MAX_PRESSURE_GPA,
    CONVERGENCE_TARGET,
    ensure_dirs,
)
from src.core.schemas import (
    RefinementReport,
    ComponentScores,
    Refinement,
)

logger = logging.getLogger("AgentOb")


# ---------------------------------------------------------------------------
# Reference experimental data (embedded knowledge base)
# ---------------------------------------------------------------------------

# Representative experimental superconductor data for validation.
# In production, this would be loaded from SuperCon + Materials Project + ICSD.
EXPERIMENTAL_DATA = pd.DataFrame([
    # Cuprates
    {"compound": "YBa2Cu3O7", "family": "cuprate", "Tc_K": 92, "crystal_system": "orthorhombic",
     "space_group": "Pmmm", "a": 3.82, "b": 3.89, "c": 11.68},
    {"compound": "La1.85Sr0.15CuO4", "family": "cuprate", "Tc_K": 38, "crystal_system": "tetragonal",
     "space_group": "I4/mmm", "a": 3.78, "c": 13.2},
    {"compound": "Bi2Sr2CaCu2O8", "family": "cuprate", "Tc_K": 85, "crystal_system": "tetragonal",
     "space_group": "I4/mmm", "a": 3.81, "c": 30.6},
    {"compound": "HgBa2Ca2Cu3O8", "family": "cuprate", "Tc_K": 133, "crystal_system": "tetragonal",
     "space_group": "P4/mmm", "a": 3.85, "c": 15.85},
    {"compound": "Tl2Ba2Ca2Cu3O10", "family": "cuprate", "Tc_K": 125, "crystal_system": "tetragonal",
     "space_group": "I4/mmm", "a": 3.85, "c": 35.6},
    # Iron-based
    {"compound": "LaFeAsO0.9F0.1", "family": "iron-pnictide", "Tc_K": 26, "crystal_system": "tetragonal",
     "space_group": "P4/nmm", "a": 4.03, "c": 8.74},
    {"compound": "Ba0.6K0.4Fe2As2", "family": "iron-pnictide", "Tc_K": 38, "crystal_system": "tetragonal",
     "space_group": "I4/mmm", "a": 3.94, "c": 13.3},
    {"compound": "NdFeAsO0.86F0.14", "family": "iron-pnictide", "Tc_K": 52, "crystal_system": "tetragonal",
     "space_group": "P4/nmm", "a": 3.96, "c": 8.57},
    {"compound": "FeSe", "family": "iron-chalcogenide", "Tc_K": 8, "crystal_system": "tetragonal",
     "space_group": "P4/nmm", "a": 3.77, "c": 5.52},
    {"compound": "FeSe0.5Te0.5", "family": "iron-chalcogenide", "Tc_K": 14, "crystal_system": "tetragonal",
     "space_group": "P4/nmm", "a": 3.80, "c": 6.0},
    # Heavy fermion
    {"compound": "CeCoIn5", "family": "heavy-fermion", "Tc_K": 2.3, "crystal_system": "tetragonal",
     "space_group": "P4/mmm", "a": 4.62, "c": 7.56},
    {"compound": "CeRhIn5", "family": "heavy-fermion", "Tc_K": 2.1, "crystal_system": "tetragonal",
     "space_group": "P4/mmm", "a": 4.65, "c": 7.54},
    {"compound": "PuCoGa5", "family": "heavy-fermion", "Tc_K": 18.5, "crystal_system": "tetragonal",
     "space_group": "P4/mmm", "a": 4.24, "c": 6.79},
    # MgB2 family (including doping variants)
    {"compound": "MgB2", "family": "mgb2-type", "Tc_K": 39, "crystal_system": "hexagonal",
     "space_group": "P6/mmm", "a": 3.09, "c": 3.52},
    {"compound": "Mg0.9Al0.1B2", "family": "mgb2-type", "Tc_K": 32, "crystal_system": "hexagonal",
     "space_group": "P6/mmm", "a": 3.08, "c": 3.52},
    {"compound": "MgB1.8C0.2", "family": "mgb2-type", "Tc_K": 37, "crystal_system": "hexagonal",
     "space_group": "P6/mmm", "a": 3.08, "c": 3.51},
    # A15
    {"compound": "Nb3Sn", "family": "a15", "Tc_K": 18.3, "crystal_system": "cubic",
     "space_group": "Pm-3n", "a": 5.29, "c": 5.29},
    {"compound": "Nb3Ge", "family": "a15", "Tc_K": 23.2, "crystal_system": "cubic",
     "space_group": "Pm-3n", "a": 5.17, "c": 5.17},
    {"compound": "V3Si", "family": "a15", "Tc_K": 17.1, "crystal_system": "cubic",
     "space_group": "Pm-3n", "a": 4.72, "c": 4.72},
    # Hydrides
    {"compound": "H3S", "family": "hydride", "Tc_K": 203, "crystal_system": "cubic",
     "space_group": "Im-3m", "a": 3.09, "c": 3.09},
    {"compound": "LaH10", "family": "hydride", "Tc_K": 250, "crystal_system": "cubic",
     "space_group": "Fm-3m", "a": 5.10, "c": 5.10},
    # Nickelates
    {"compound": "Nd0.8Sr0.2NiO2", "family": "nickelate", "Tc_K": 15, "crystal_system": "tetragonal",
     "space_group": "P4/mmm", "a": 3.92, "c": 3.28},
    {"compound": "La3Ni2O7", "family": "nickelate", "Tc_K": 80, "crystal_system": "tetragonal",
     "space_group": "I4/mmm", "a": 3.83, "c": 20.5},
    # Chevrel
    {"compound": "PbMo6S8", "family": "chevrel", "Tc_K": 15, "crystal_system": "trigonal",
     "space_group": "R-3", "a": 6.54, "c": 6.54},
])

# Experimental pressure-Tc data for pressure component validation
EXPERIMENTAL_PRESSURE_TC = {
    "cuprate":            {"dTc_dP": -1.5, "Tc_0": 92},
    "mgb2-type":          {"dTc_dP": -1.6, "Tc_0": 39},
    "iron-chalcogenide":  {"dTc_dP": 9.0,  "Tc_0": 8},
    "hydride":            {"P_onset": 100, "Tc_at_150": 203},
    "nickelate":          {"P_onset": 14,  "Tc_at_14": 80},
    "a15":                {"dTc_dP": -0.8, "Tc_0": 18},
    "chevrel":            {"dTc_dP": -0.5, "Tc_0": 15},
}


def save_experimental_data():
    """Save embedded experimental data to CSV for reference."""
    path = EXPERIMENTAL_DIR / "supercon_reference.csv"
    EXPERIMENTAL_DATA.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Comparison metrics
# ---------------------------------------------------------------------------

def wasserstein_1d(p: np.ndarray, q: np.ndarray) -> float:
    """Compute 1D Wasserstein distance (earth mover's distance) between two samples."""
    p_sorted = np.sort(p)
    q_sorted = np.sort(q)

    # Resample to same length for comparison
    n = max(len(p_sorted), len(q_sorted))
    if n == 0:
        return 0.0

    p_interp = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(p_sorted)), p_sorted)
    q_interp = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(q_sorted)), q_sorted)

    return float(np.mean(np.abs(p_interp - q_interp)))


def compute_tc_distribution_score(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    """
    Compare Tc distributions between real and synthetic data.
    Score: 1 - normalized Wasserstein distance.
    """
    families = real_df["family"].unique()
    scores = []

    for family in families:
        real_tc = real_df[real_df["family"] == family]["Tc_K"].values
        # Map family to pattern_id prefix
        family_prefix = family.replace("-", "")
        synth_tc = synth_df[synth_df["pattern_id"].str.replace("-", "").str.startswith(family_prefix)]["predicted_Tc_K"].values

        if len(real_tc) == 0 or len(synth_tc) == 0:
            scores.append(0.5)  # No data to compare — neutral score
            continue

        # Normalize Wasserstein by the range of real Tc values
        # Use min 30K range so narrow-range families (MgB2, A15) aren't penalized
        tc_range = max(real_tc.max() - real_tc.min(), 30.0)
        wd = wasserstein_1d(real_tc, synth_tc)
        score = max(0, 1 - wd / tc_range)
        scores.append(score)
        logger.info(f"  Tc score for {family}: {score:.3f} (WD={wd:.2f}, range={tc_range:.1f})")

    return float(np.mean(scores)) if scores else 0.0


def compute_lattice_accuracy(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    """
    Compare lattice parameters between real and synthetic data.
    Score: mean (1 - |Δa/a|, 1 - |Δc/c|) per family.
    """
    families = real_df["family"].unique()
    scores = []

    for family in families:
        real = real_df[real_df["family"] == family]
        family_prefix = family.replace("-", "")
        synth = synth_df[synth_df["pattern_id"].str.replace("-", "").str.startswith(family_prefix)]

        if len(real) == 0 or len(synth) == 0:
            scores.append(0.5)
            continue

        # Compare mean lattice parameters
        real_a_mean = real["a"].mean()
        real_c_mean = real["c"].mean()
        synth_a_mean = synth["a"].mean()
        synth_c_mean = synth["c"].mean()

        da = abs(synth_a_mean - real_a_mean) / max(real_a_mean, 0.01)
        dc = abs(synth_c_mean - real_c_mean) / max(real_c_mean, 0.01)

        score = max(0, 1 - (da + dc) / 2)
        scores.append(score)
        logger.info(f"  Lattice score for {family}: {score:.3f} (Δa/a={da:.3f}, Δc/c={dc:.3f})")

    return float(np.mean(scores)) if scores else 0.0


def compute_space_group_score(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    """Fraction of synthetic structures in a correct space group for their family."""
    # Build map of acceptable space groups per family
    family_sg = {}
    for _, row in real_df.iterrows():
        family = row["family"]
        if family not in family_sg:
            family_sg[family] = set()
        family_sg[family].add(row["space_group"])

    correct = 0
    total = 0
    for _, row in synth_df.iterrows():
        pid = row["pattern_id"]
        # Find matching family
        for family, sgs in family_sg.items():
            family_prefix = family.replace("-", "")
            if family_prefix in pid.replace("-", ""):
                total += 1
                if row["space_group"] in sgs:
                    correct += 1
                break

    if total == 0:
        return 0.5
    score = correct / total
    logger.info(f"  Space group correctness: {correct}/{total} = {score:.3f}")
    return score


def compute_electronic_match(real_df: pd.DataFrame, synth_df: pd.DataFrame) -> float:
    """
    Compare electronic properties — primarily lambda correlation.
    For now, check that synthetic lambda values fall in physically reasonable ranges.
    """
    lambda_vals = synth_df["electron_phonon_lambda"].values
    if len(lambda_vals) == 0:
        return 0.0

    # Physically, lambda should be 0.1–3.0 for most superconductors
    in_range = np.sum((lambda_vals >= 0.1) & (lambda_vals <= 3.0))
    range_score = in_range / len(lambda_vals)

    # Check that lambda variance is reasonable (not all identical)
    if np.std(lambda_vals) < 0.01:
        variance_score = 0.5  # Too uniform
    else:
        variance_score = min(1.0, np.std(lambda_vals) / 0.5)

    score = 0.7 * range_score + 0.3 * variance_score
    logger.info(f"  Electronic match: range={range_score:.3f}, variance={variance_score:.3f}, total={score:.3f}")
    return score


def compute_composition_validity(synth_df: pd.DataFrame) -> float:
    """
    Check that generated compositions are chemically reasonable.
    Simple heuristic: compositions should parse and have known elements.
    """
    from src.agents.agent_cs import parse_composition, ELEMENT_DATA

    valid = 0
    total = len(synth_df)
    if total == 0:
        return 0.0

    for _, row in synth_df.iterrows():
        comp = parse_composition(row["composition"])
        if comp and all(e in ELEMENT_DATA for e in comp):
            valid += 1

    score = valid / total
    logger.info(f"  Composition validity: {valid}/{total} = {score:.3f}")
    return score


def compute_coordination_score(synth_df: pd.DataFrame) -> float:
    """
    Score based on lattice parameter plausibility.
    Lattice parameters should be 2–40 Å and angles 60–120°.
    """
    total = len(synth_df)
    if total == 0:
        return 0.0

    valid = 0
    for _, row in synth_df.iterrows():
        a_ok = 2 <= row["a"] <= 40
        c_ok = 2 <= row["c"] <= 40
        alpha_ok = 60 <= row.get("alpha", 90) <= 120
        beta_ok = 60 <= row.get("beta", 90) <= 120
        gamma_ok = 60 <= row.get("gamma", 90) <= 120
        if a_ok and c_ok and alpha_ok and beta_ok and gamma_ok:
            valid += 1

    score = valid / total
    logger.info(f"  Coordination/geometry plausibility: {valid}/{total} = {score:.3f}")
    return score


def compute_pressure_tc_accuracy(synth_df: pd.DataFrame) -> float:
    """
    Validate pressure-Tc consistency of synthetic data.

    Returns 1.0 (pass) if no pressure data is present — ambient-only runs
    should not be penalized by an inapplicable component.
    Otherwise checks:
    - Hydrides at low P should have Tc~0
    - Cuprates/MgB2/A15 Tc should decrease with pressure
    - FeSe Tc should increase with pressure
    """
    if "pressure_GPa" not in synth_df.columns:
        return 1.0

    pressures = synth_df["pressure_GPa"]
    if pressures.abs().sum() < 1e-6:
        # All at ambient pressure — no pressure data to validate
        return 1.0

    checks = []

    # Check hydrides: at P < 50 GPa, Tc should be near 0
    hydride_mask = synth_df["pattern_id"].str.contains("hydride")
    hydride_low_p = synth_df[hydride_mask & (pressures < 50)]
    if len(hydride_low_p) > 0:
        low_p_tc = hydride_low_p["predicted_Tc_K"].mean()
        # Good if Tc < 10K at low pressure for hydrides
        checks.append(max(0, 1.0 - low_p_tc / 50.0))

    # Check sign of dTc/dP for families with known behavior
    for family, data in EXPERIMENTAL_PRESSURE_TC.items():
        if "dTc_dP" not in data:
            continue
        family_prefix = family.replace("-", "")
        fam_mask = synth_df["pattern_id"].str.replace("-", "").str.startswith(family_prefix)
        fam_data = synth_df[fam_mask]
        if len(fam_data) < 5:
            continue

        # Check correlation between P and Tc
        p_vals = fam_data["pressure_GPa"].values
        tc_vals = fam_data["predicted_Tc_K"].values
        if np.std(p_vals) < 1e-6:
            continue  # All at same pressure, can't check trend

        corr = np.corrcoef(p_vals, tc_vals)[0, 1] if len(p_vals) > 1 else 0
        expected_sign = np.sign(data["dTc_dP"])
        actual_sign = np.sign(corr)
        # Score: 1.0 if sign matches, 0.5 if no correlation, 0.0 if wrong sign
        if expected_sign * actual_sign > 0:
            checks.append(1.0)
        elif abs(corr) < 0.1:
            checks.append(0.5)
        else:
            checks.append(0.0)

    if not checks:
        return 0.5

    score = float(np.mean(checks))
    logger.info(f"  Pressure-Tc accuracy: {score:.3f} ({len(checks)} checks)")
    return score


# ---------------------------------------------------------------------------
# Discrepancy analysis and refinement generation
# ---------------------------------------------------------------------------

def _load_model_state() -> dict:
    """Load Agent Sin's current model state to get actual parameter values."""
    from src.core.config import SYNTHETIC_DIR
    state_path = SYNTHETIC_DIR / "model_state.json"
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {}


def analyze_discrepancies(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    component_scores: ComponentScores,
    iteration: int,
) -> list[Refinement]:
    """Identify dominant failure modes and generate actionable refinements."""
    refinements = []
    model_state = _load_model_state()

    # 1. Check Tc distribution per family
    families = real_df["family"].unique()
    for family in families:
        real_tc = real_df[real_df["family"] == family]["Tc_K"].values
        family_prefix = family.replace("-", "")
        synth_mask = synth_df["pattern_id"].str.replace("-", "").str.startswith(family_prefix)
        synth_tc = synth_df[synth_mask]["predicted_Tc_K"].values

        if len(real_tc) == 0 or len(synth_tc) == 0:
            continue

        real_mean = real_tc.mean()
        synth_mean = synth_tc.mean()
        bias = synth_mean - real_mean

        bias_threshold = real_mean * 0.10 if component_scores.tc_distribution > 0.80 else real_mean * 0.15
        if abs(bias) > bias_threshold:
            direction = "overestimated" if bias > 0 else "underestimated"

            # Correction: scale lambda proportionally to close the Tc gap
            # If synth is too high, reduce lambda; if too low, increase it
            # Use ratio-based correction relative to current actual scaling
            family_key = family.replace("-", "_")
            param_name = f"lambda_scaling_{family_key}"
            actual_current = model_state.get(param_name, 1.0)
            if synth_mean > 0:
                ratio = real_mean / synth_mean
                correction = max(0.3, min(10.0, actual_current * ratio))
            elif bias > 0:
                correction = max(0.3, actual_current * 0.7)
            else:
                correction = min(10.0, actual_current * 1.3)

            pattern_id = None
            for _, row in synth_df[synth_mask].iterrows():
                pattern_id = row["pattern_id"]
                break

            refinements.append(Refinement(
                target_agent="Sin",
                action="adjust_model",
                parameter=param_name,
                current_value=actual_current,
                suggested_value=round(correction, 3),
                detail=f"Tc {direction} for {family} by {abs(bias):.1f}K (mean: real={real_mean:.1f}, synth={synth_mean:.1f})",
                pattern_id=pattern_id,
                priority="high" if abs(bias) > real_mean * 0.5 else "medium",
            ))

    # 1b. For families with Tc boost factors, also adjust the boost
    # All families with unconventional pairing or known Allen-Dynes mismatch
    boosted_families = {
        "cuprate": 2.5, "nickelate": 1.8, "heavy-fermion": 0.3,
        "iron-pnictide": 1.0, "iron-chalcogenide": 1.0,
        "mgb2-type": 1.0, "hydride": 1.0, "a15": 1.0, "chevrel": 1.0,
    }
    for family, default_boost in boosted_families.items():
        real_tc = real_df[real_df["family"] == family]["Tc_K"].values
        family_prefix = family.replace("-", "")
        synth_mask = synth_df["pattern_id"].str.replace("-", "").str.startswith(family_prefix)
        synth_tc = synth_df[synth_mask]["predicted_Tc_K"].values

        if len(real_tc) == 0 or len(synth_tc) == 0:
            continue

        real_mean = real_tc.mean()
        synth_mean = synth_tc.mean()
        boost_threshold = real_mean * 0.10 if component_scores.tc_distribution > 0.80 else real_mean * 0.15
        if synth_mean > 0 and abs(synth_mean - real_mean) > boost_threshold:
            family_key = family.replace("-", "_")
            boost_param = f"tc_boost_{family_key}"
            current_boost = model_state.get(boost_param, default_boost)
            suggested_boost = current_boost * (real_mean / synth_mean)
            suggested_boost = max(0.1, min(10.0, suggested_boost))
            refinements.append(Refinement(
                target_agent="Sin",
                action="adjust_model",
                parameter=boost_param,
                current_value=current_boost,
                suggested_value=round(suggested_boost, 3),
                detail=f"Tc boost for {family}: adjust from {current_boost:.2f} to match real mean={real_mean:.1f}K",
                priority="medium",
            ))

    # 2. Check lattice accuracy
    if component_scores.lattice_accuracy < 0.8:
        refinements.append(Refinement(
            target_agent="Sin",
            action="adjust_model",
            parameter="perturbation_scale",
            current_value=0.05,
            suggested_value=0.03,
            detail="Lattice parameters drifting too far from reference — reduce perturbation scale",
            priority="medium",
        ))

    # 3. Check space group correctness
    if component_scores.space_group_correctness < 0.7:
        refinements.append(Refinement(
            target_agent="CS",
            action="add_constraint",
            detail="Tighten space group constraints — many structures in incorrect space groups",
            priority="high",
        ))

    # 4. Check for missing families
    for family in families:
        family_prefix = family.replace("-", "")
        synth_count = synth_df["pattern_id"].str.replace("-", "").str.startswith(family_prefix).sum()
        if synth_count < 10:
            refinements.append(Refinement(
                target_agent="CS",
                action="expand_pattern",
                detail=f"Under-represented family {family} — only {synth_count} synthetic structures",
                priority="medium",
            ))

    return refinements


def flag_novel_candidates(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    tc_threshold: float = 10.0,
) -> pd.DataFrame:
    """
    Identify synthetic structures with high Tc that don't closely match
    any known experimental compound → potential novel superconductors.
    """
    novels = []
    known_compositions = set(real_df["compound"].str.replace(" ", ""))

    high_tc = synth_df[synth_df["predicted_Tc_K"] > tc_threshold].copy()

    for _, row in high_tc.iterrows():
        comp = row["composition"].replace(" ", "")
        # Check if composition is novel (not in known database)
        is_novel = comp not in known_compositions

        # Also check if Tc is unusually high for its family
        family_prefix = row["pattern_id"].split("-")[0]
        family_real = real_df[real_df["family"].str.startswith(family_prefix)]
        if len(family_real) > 0:
            max_known_tc = family_real["Tc_K"].max()
            is_exceptional = row["predicted_Tc_K"] > max_known_tc * 1.1
        else:
            is_exceptional = True

        if is_novel and is_exceptional and row["stability_confidence"] > 0.5:
            novels.append(row)

    if novels:
        novel_df = pd.DataFrame(novels)
        novel_df = novel_df.sort_values("predicted_Tc_K", ascending=False)
        logger.info(f"Flagged {len(novel_df)} novel candidates with Tc > {tc_threshold}K")
        return novel_df

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Convergence tracking
# ---------------------------------------------------------------------------

def detect_convergence_trend(history_path: Path, current_score: float) -> str:
    """Analyze convergence history to detect trends."""
    if not history_path.exists():
        return "improving"

    with open(history_path) as f:
        history = json.load(f)

    scores = [h["convergence_score"] for h in history]
    scores.append(current_score)

    if len(scores) < 3:
        return "improving" if scores[-1] > scores[0] else "stagnant"

    recent = scores[-3:]
    diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]

    if all(d > 0 for d in diffs):
        return "improving"
    elif all(abs(d) < 0.005 for d in diffs):
        return "stagnant"
    elif any(d > 0 for d in diffs) and any(d < 0 for d in diffs):
        return "oscillating"
    elif current_score >= CONVERGENCE_TARGET:
        return "converged"
    return "improving"


# ---------------------------------------------------------------------------
# RTAP Discovery-Mode Scoring Functions
# ---------------------------------------------------------------------------

RTAP_FAMILY_PREFIXES = {
    "kagome", "ternary-hydride", "infinite-layer", "topological",
    "2d-heterostructure", "carbon-based", "engineered-cuprate",
    "mof-sc", "flat-band",
}


def _is_rtap_pattern(pattern_id: str) -> bool:
    """Check if a pattern_id belongs to an RTAP family."""
    prefix = pattern_id.rsplit("-", 1)[0] if "-" in pattern_id else pattern_id
    # Check 2-part and 1-part prefixes
    return prefix in RTAP_FAMILY_PREFIXES or any(
        pattern_id.startswith(p) for p in RTAP_FAMILY_PREFIXES
    )


def compute_ambient_tc_score(synth_df: pd.DataFrame) -> float:
    """
    Discovery-oriented RTAP metric: measures progress toward RT-SC.

    Uses 4 complementary sub-metrics:
    1. Mean family Tc normalized to 273K (rewards systematic improvement)
    2. Fraction of RTAP families with mean Tc > 200K (breadth of progress)
    3. Quality of top candidates (best discoveries so far)
    4. Absolute RT candidate count (discovery output)

    Evaluates RTAP families only for family-level metrics.
    """
    if len(synth_df) == 0:
        return 0.0

    tc_col = "ambient_pressure_Tc_K" if "ambient_pressure_Tc_K" in synth_df.columns else "predicted_Tc_K"
    tc_vals = synth_df[tc_col].values

    # Filter to RTAP families
    rtap_df = synth_df
    if "pattern_id" in synth_df.columns:
        rtap_mask = synth_df["pattern_id"].apply(_is_rtap_pattern)
        rtap_df = synth_df[rtap_mask]

    n_rtap = len(rtap_df)
    if n_rtap == 0:
        rtap_df = synth_df
        n_rtap = len(synth_df)

    rtap_tc = rtap_df[tc_col].values

    # Sub-metric 1: Mean Tc across RTAP families, normalized to 273K
    if "pattern_id" in rtap_df.columns:
        family_means = rtap_df.groupby("pattern_id")[tc_col].mean()
        mean_family_tc = family_means.mean()
    else:
        mean_family_tc = rtap_tc.mean()
    family_tc_score = min(1.0, mean_family_tc / RTAP_TC_THRESHOLD_K)

    # Sub-metric 2: Fraction of RTAP families with mean Tc > 200K
    if "pattern_id" in rtap_df.columns:
        frac_families_above_200 = float((family_means >= 200.0).mean())
        n_families = len(family_means)
    else:
        frac_families_above_200 = float(np.mean(rtap_tc >= 200.0))
        n_families = 1

    # Sub-metric 3: Top-10 candidate quality
    top10 = np.sort(tc_vals)[-10:]
    mean_top10 = float(np.mean(top10)) if len(top10) > 0 else 0.0
    top10_score = min(1.0, mean_top10 / RTAP_TC_THRESHOLD_K)

    # Sub-metric 4: Absolute RT candidate count (capped at 300 for max score)
    n_rt = int(np.sum(rtap_tc >= RTAP_TC_THRESHOLD_K))
    rt_discovery = min(1.0, n_rt / 300.0)

    score = 0.30 * family_tc_score + 0.20 * frac_families_above_200 + 0.25 * top10_score + 0.25 * rt_discovery
    logger.info(
        f"  Ambient Tc score: family_mean={mean_family_tc:.1f}K ({n_families} families), "
        f"fam>200K={frac_families_above_200:.3f}, top10={mean_top10:.1f}K, "
        f"n_RT={n_rt}, total={score:.3f}"
    )
    return float(score)


def compute_ambient_stability_score(synth_df: pd.DataFrame) -> float:
    """
    Score based on thermodynamic stability at ambient conditions.
    Penalizes structures with high energy_above_hull or requiring high pressure.
    """
    if len(synth_df) == 0:
        return 0.0

    e_hull = synth_df["energy_above_hull_meV"].values
    # Fraction below 100 meV above hull (relaxed for metastable)
    frac_stable = np.sum(e_hull < 100.0) / len(e_hull)

    # Fraction below 50 meV (truly stable)
    frac_very_stable = np.sum(e_hull < 50.0) / len(e_hull)

    # Pressure penalty: penalize structures requiring high P
    if "pressure_GPa" in synth_df.columns:
        p_vals = synth_df["pressure_GPa"].values
        frac_ambient = np.sum(p_vals <= RTAP_MAX_PRESSURE_GPA) / len(p_vals)
    else:
        frac_ambient = 1.0

    score = 0.4 * frac_stable + 0.3 * frac_very_stable + 0.3 * frac_ambient
    logger.info(f"  Ambient stability: stable={frac_stable:.3f}, very_stable={frac_very_stable:.3f}, ambient_P={frac_ambient:.3f}, total={score:.3f}")
    return float(score)


def compute_synthesizability_score(synth_df: pd.DataFrame) -> float:
    """
    Practical synthesis assessment. Rewards:
    - Common, non-toxic, non-radioactive elements
    - Known crystal systems
    - Moderate stability confidence
    """
    from src.agents.agent_cs import parse_composition

    if len(synth_df) == 0:
        return 0.0

    # Forbidden/problematic elements
    TOXIC_HEAVY = {"Hg", "Tl", "Pb", "Cd"}
    RADIOACTIVE = {"Pu", "U", "Th", "Np", "Am"}
    EXPENSIVE_RARE = {"Os", "Ir", "Re", "Rh", "Ru"}

    scores = []
    for _, row in synth_df.iterrows():
        comp = parse_composition(row["composition"])
        elements = set(comp.keys())

        penalty = 0.0
        if elements & RADIOACTIVE:
            penalty += 0.5
        if elements & TOXIC_HEAVY:
            penalty += 0.2
        if elements & EXPENSIVE_RARE:
            penalty += 0.1

        elem_score = max(0.0, 1.0 - penalty)
        stability_bonus = row.get("stability_confidence", 0.5)
        scores.append(0.7 * elem_score + 0.3 * stability_bonus)

    score = float(np.mean(scores))
    logger.info(f"  Synthesizability: {score:.3f}")
    return score


def compute_electronic_indicator_score(synth_df: pd.DataFrame) -> float:
    """
    Score based on presence of favorable electronic structure signatures
    for room-temperature superconductivity.

    Evaluates RTAP families for lambda metric (legacy families have
    inherently low lambda, which would dilute the discovery signal).
    """
    if len(synth_df) == 0:
        return 0.0

    checks = []

    # High lambda — evaluate on RTAP families only
    if "pattern_id" in synth_df.columns:
        rtap_mask = synth_df["pattern_id"].apply(_is_rtap_pattern)
        rtap_lambda = synth_df.loc[rtap_mask, "electron_phonon_lambda"].values
        if len(rtap_lambda) > 0:
            moderate_lambda_frac = np.sum(rtap_lambda > 0.8) / len(rtap_lambda)
        else:
            moderate_lambda_frac = np.sum(synth_df["electron_phonon_lambda"].values > 0.8) / len(synth_df)
    else:
        lambda_vals = synth_df["electron_phonon_lambda"].values
        moderate_lambda_frac = np.sum(lambda_vals > 0.8) / len(lambda_vals)
    checks.append(moderate_lambda_frac)

    # Mechanism diversity: reward multiple active mechanisms (>= 4 ideal)
    if "primary_mechanism" in synth_df.columns:
        mechanisms = synth_df["primary_mechanism"].values
        unique_mechs = len(set(mechanisms))
        diversity = min(1.0, unique_mechs / 4.0)
        checks.append(diversity)

    # Mechanism confidence
    if "mechanism_confidence" in synth_df.columns:
        avg_conf = synth_df["mechanism_confidence"].mean()
        checks.append(avg_conf)

    # Tc spread: reward wide exploration (std > 50K is good)
    tc_col = "ambient_pressure_Tc_K" if "ambient_pressure_Tc_K" in synth_df.columns else "predicted_Tc_K"
    if tc_col in synth_df.columns:
        tc_std = synth_df[tc_col].std()
        spread_score = min(1.0, tc_std / 80.0)
        checks.append(spread_score)

    score = float(np.mean(checks)) if checks else 0.0
    logger.info(f"  Electronic indicators: {score:.3f}")
    return score


def compute_mechanism_plausibility_score(synth_df: pd.DataFrame) -> float:
    """
    Self-consistency check between claimed mechanism and properties.
    """
    if len(synth_df) == 0:
        return 0.0

    if "primary_mechanism" not in synth_df.columns:
        return 0.5  # No mechanism data — neutral

    plausible = 0
    total = 0
    for _, row in synth_df.iterrows():
        mech = row.get("primary_mechanism", "bcs")
        lam = row.get("electron_phonon_lambda", 0.5)
        tc = row.get("predicted_Tc_K", 0.0)
        total += 1

        if mech == "bcs":
            # BCS: lambda > 0.1, Tc < 500K
            if lam > 0.1 and tc < 500:
                plausible += 1
        elif "spin_fluctuation" in mech:
            # Spin-fluctuation: lambda > 0.3
            if lam > 0.3:
                plausible += 1
        elif "flat_band" in mech:
            # Flat-band: can have moderate lambda but high Tc
            if lam > 0.1:
                plausible += 1
        elif "hydride" in mech:
            # Hydride: should have high lambda and high omega
            if lam > 0.5:
                plausible += 1
        elif "excitonic" in mech:
            plausible += 1  # Hard to validate, give benefit of doubt
        elif "mixed" in mech:
            if lam > 0.1:
                plausible += 1
        else:
            plausible += 1  # Unknown mechanism — neutral

    score = plausible / max(total, 1)
    logger.info(f"  Mechanism plausibility: {plausible}/{total} = {score:.3f}")
    return float(score)


# ---------------------------------------------------------------------------
# Agent Ob main logic
# ---------------------------------------------------------------------------

class AgentOb:
    """Observator Agent — compares, scores, and refines."""

    def __init__(self):
        ensure_dirs()
        self.real_df = EXPERIMENTAL_DATA.copy()
        save_experimental_data()

    def load_synthetic_data(self, iteration: int) -> pd.DataFrame:
        """Load synthetic data from Agent Sin's output."""
        csv_path = SYNTHETIC_DIR / f"iteration_{iteration:03d}" / "properties.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Synthetic data not found: {csv_path}")

        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} synthetic structures from {csv_path}")
        return df

    def compute_convergence(self, synth_df: pd.DataFrame, mode: str = "v1") -> tuple[float, ComponentScores]:
        """
        Compute the multi-component convergence score.

        Args:
            synth_df: Synthetic data from Agent Sin
            mode: "v1" (match-to-experiment) or "rtap" (discovery-oriented)
        """
        logger.info(f"Computing convergence scores (mode={mode})...")

        if mode == "rtap":
            return self._compute_rtap_convergence(synth_df)

        scores = ComponentScores(
            tc_distribution=compute_tc_distribution_score(self.real_df, synth_df),
            lattice_accuracy=compute_lattice_accuracy(self.real_df, synth_df),
            space_group_correctness=compute_space_group_score(self.real_df, synth_df),
            electronic_property_match=compute_electronic_match(self.real_df, synth_df),
            composition_validity=compute_composition_validity(synth_df),
            coordination_geometry=compute_coordination_score(synth_df),
            pressure_tc_accuracy=compute_pressure_tc_accuracy(synth_df),
        )

        # Weighted aggregate — iterates over SCORE_WEIGHTS dict (handles 6 or 7 components)
        total = sum(
            SCORE_WEIGHTS[field] * getattr(scores, field)
            for field in SCORE_WEIGHTS
        )

        logger.info(f"Component scores: Tc={scores.tc_distribution:.3f}, "
                     f"Lattice={scores.lattice_accuracy:.3f}, SG={scores.space_group_correctness:.3f}, "
                     f"Electronic={scores.electronic_property_match:.3f}, "
                     f"Composition={scores.composition_validity:.3f}, "
                     f"Coordination={scores.coordination_geometry:.3f}, "
                     f"Pressure={scores.pressure_tc_accuracy:.3f}")
        logger.info(f"Weighted convergence score: {total:.4f}")

        return round(total, 4), scores

    def _compute_rtap_convergence(self, synth_df: pd.DataFrame) -> tuple[float, ComponentScores]:
        """RTAP discovery-oriented convergence scoring."""
        scores = ComponentScores(
            # Standard metrics still computed for reference
            composition_validity=compute_composition_validity(synth_df),
            coordination_geometry=compute_coordination_score(synth_df),
            # RTAP-specific scores
            ambient_tc_score=compute_ambient_tc_score(synth_df),
            ambient_stability_score=compute_ambient_stability_score(synth_df),
            synthesizability_score=compute_synthesizability_score(synth_df),
            electronic_indicator_score=compute_electronic_indicator_score(synth_df),
            mechanism_plausibility_score=compute_mechanism_plausibility_score(synth_df),
        )

        # Weighted aggregate using RTAP weights
        total = sum(
            RTAP_SCORE_WEIGHTS[field] * getattr(scores, field)
            for field in RTAP_SCORE_WEIGHTS
            if hasattr(scores, field)
        )

        logger.info(f"RTAP scores: ambient_tc={scores.ambient_tc_score:.3f}, "
                     f"stability={scores.ambient_stability_score:.3f}, "
                     f"synthesizability={scores.synthesizability_score:.3f}, "
                     f"electronic={scores.electronic_indicator_score:.3f}, "
                     f"mechanism={scores.mechanism_plausibility_score:.3f}, "
                     f"composition={scores.composition_validity:.3f}")
        logger.info(f"Weighted RTAP discovery score: {total:.4f}")

        return round(total, 4), scores

    def generate_report(
        self,
        iteration: int,
        synth_df: pd.DataFrame,
        convergence_score: float,
        component_scores: ComponentScores,
    ) -> RefinementReport:
        """Generate the full refinement report."""
        # Generate refinement instructions
        refinements = analyze_discrepancies(
            self.real_df, synth_df, component_scores, iteration
        )

        # Flag novel candidates
        novel_df = flag_novel_candidates(self.real_df, synth_df)
        if not novel_df.empty:
            novel_path = NOVEL_CANDIDATES_DIR / f"candidates_iteration_{iteration:03d}.csv"
            novel_df.to_csv(novel_path, index=False)
            logger.info(f"Saved {len(novel_df)} novel candidates to {novel_path}")

        # Detect convergence trend
        history_path = REPORTS_DIR / "convergence_history.json"
        trend = detect_convergence_trend(history_path, convergence_score)

        report = RefinementReport(
            iteration=iteration,
            convergence_score=convergence_score,
            component_scores=component_scores,
            refinements=refinements,
            novel_candidates_flagged=len(novel_df),
            convergence_trend=trend,
        )

        return report

    def update_convergence_history(self, iteration: int, score: float, component_scores: ComponentScores):
        """Append to convergence history for trend analysis."""
        history_path = REPORTS_DIR / "convergence_history.json"

        if history_path.exists():
            with open(history_path) as f:
                history = json.load(f)
        else:
            history = []

        history.append({
            "iteration": iteration,
            "convergence_score": score,
            "component_scores": {
                "tc_distribution": component_scores.tc_distribution,
                "lattice_accuracy": component_scores.lattice_accuracy,
                "space_group_correctness": component_scores.space_group_correctness,
                "electronic_property_match": component_scores.electronic_property_match,
                "composition_validity": component_scores.composition_validity,
                "coordination_geometry": component_scores.coordination_geometry,
                "pressure_tc_accuracy": component_scores.pressure_tc_accuracy,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)


def run_agent_ob(iteration: int, mode: str = "v1") -> tuple[float, Path]:
    """
    Main entry point for Agent Ob.
    Returns (convergence_score, refinement_report_path).
    mode: "v1" (default) or "rtap" for RTAP discovery scoring.
    """
    agent = AgentOb()

    # Load synthetic data
    synth_df = agent.load_synthetic_data(iteration)

    # Compute convergence
    convergence_score, component_scores = agent.compute_convergence(synth_df, mode=mode)

    # Generate refinement report
    report = agent.generate_report(iteration, synth_df, convergence_score, component_scores)

    # Save report
    report_path = REFINEMENTS_DIR / f"iteration_{iteration:03d}.json"
    report.save(report_path)
    logger.info(f"Saved refinement report to {report_path}")

    # Update history
    agent.update_convergence_history(iteration, convergence_score, component_scores)

    return convergence_score, report_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Requires synthetic data to exist (run agent_cs.py then agent_sin.py first)
    score, path = run_agent_ob(iteration=0)
    print(f"Convergence score: {score}")
    print(f"Report saved to: {path}")
