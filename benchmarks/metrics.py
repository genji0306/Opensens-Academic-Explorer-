"""Standardized metrics for cross-agent benchmarking."""
import logging

import numpy as np

logger = logging.getLogger("Benchmarks.Metrics")


def match_rate(predicted_structures: list, reference_structures: list,
               ltol: float = 0.2, stol: float = 0.3, angle_tol: float = 5.0) -> float:
    """Structure match rate using pymatgen StructureMatcher."""
    try:
        from pymatgen.analysis.structure_matcher import StructureMatcher
    except ImportError:
        logger.warning("pymatgen StructureMatcher not available.")
        return -1.0

    if not predicted_structures or not reference_structures:
        return 0.0

    matcher = StructureMatcher(ltol=ltol, stol=stol, angle_tol=angle_tol)
    matches = 0
    n = min(len(predicted_structures), len(reference_structures))
    for i in range(n):
        try:
            if matcher.fit(predicted_structures[i], reference_structures[i]):
                matches += 1
        except Exception:
            pass
    return matches / n if n > 0 else 0.0


def rmsd(predicted, reference) -> float:
    """Atomic RMSD after alignment (Angstrom)."""
    try:
        from pymatgen.analysis.structure_matcher import StructureMatcher
        matcher = StructureMatcher()
        result = matcher.get_rms_dist(predicted, reference)
        return float(result[0]) if result else -1.0
    except Exception:
        return -1.0


def energy_mae(predicted: list, reference: list) -> float:
    """Mean absolute error of formation energies (eV/atom)."""
    if not predicted or not reference:
        return -1.0
    n = min(len(predicted), len(reference))
    return float(np.mean(np.abs(np.array(predicted[:n]) - np.array(reference[:n]))))


def rwp(observed: np.ndarray, calculated: np.ndarray) -> float:
    """Weighted profile R-factor for XRD patterns."""
    if len(observed) == 0 or len(calculated) == 0:
        return 1.0
    n = min(len(observed), len(calculated))
    y_obs = observed[:n]
    y_calc = calculated[:n]

    w = np.ones_like(y_obs)
    mask = y_obs > 1e-6
    w[mask] = 1.0 / y_obs[mask]

    num = np.sum(w * (y_obs - y_calc) ** 2)
    den = np.sum(w * y_obs ** 2)
    return float(np.sqrt(num / den)) if den > 0 else 1.0


def convergence_score(history_path=None) -> float:
    """Read the latest convergence score from Agent Ob's output."""
    import json
    from pathlib import Path

    if history_path is None:
        project_root = Path(__file__).resolve().parent.parent
        history_path = project_root / "data" / "reports" / "convergence_history.json"

    try:
        data = json.loads(history_path.read_text())
        if isinstance(data, list) and data:
            last = data[-1]
            return float(last.get("convergence_score", last.get("score", 0)))
        return 0.0
    except Exception:
        return 0.0


def rtap_discovery_score(structures: list) -> float:
    """Fraction of structures predicted to be room-temperature ambient-pressure SC.

    A structure qualifies if Tc >= 273 K and pressure <= 1 GPa.

    Args:
        structures: List of dicts, each with "predicted_Tc_K" or
            "ambient_pressure_Tc_K" (float) and optionally "pressure_GPa" (float).

    Returns:
        Float in [0, 1]. Returns 0.0 if structures is empty.
    """
    if not structures:
        return 0.0

    hits = 0
    for s in structures:
        tc = s.get("predicted_Tc_K", s.get("ambient_pressure_Tc_K", 0))
        pressure = s.get("pressure_GPa", 0)
        if tc >= 273 and pressure <= 1:
            hits += 1

    return hits / len(structures)


def pressure_reduction_factor(structures: list) -> float:
    """Average pressure reduction factor rewarding lower required pressure.

    Computes mean of (1 - P_required / 200) across structures, where
    P_required is clamped to [0, 200] GPa. A score of 1.0 means all
    structures are ambient pressure; 0.0 means all at 200 GPa.

    Args:
        structures: List of dicts with "pressure_GPa" (float) key.

    Returns:
        Float in [0, 1]. Returns 0.0 if structures is empty.
    """
    if not structures:
        return 0.0

    factors = []
    for s in structures:
        p = s.get("pressure_GPa", 0)
        p_clamped = max(0.0, min(float(p), 200.0))
        factors.append(1.0 - p_clamped / 200.0)

    return float(np.mean(factors))


def classification_agreement(labels_a: list, labels_b: list) -> float:
    """Simple accuracy between two label lists (for FM/AFM/NM classification)."""
    n = min(len(labels_a), len(labels_b))
    if n == 0:
        return 0.0
    return sum(1 for i in range(n) if labels_a[i] == labels_b[i]) / n


def temperature_correlation(temps_a: list, temps_b: list) -> float:
    """Pearson r between two temperature lists (filtering zero pairs)."""
    n = min(len(temps_a), len(temps_b))
    if n < 2:
        return 0.0
    a = np.array(temps_a[:n], dtype=float)
    b = np.array(temps_b[:n], dtype=float)
    mask = (a > 0) & (b > 0)
    if mask.sum() < 2:
        return 0.0
    r = np.corrcoef(a[mask], b[mask])[0, 1]
    return float(r) if not np.isnan(r) else 0.0


def mechanism_diversity_score(structures: list) -> float:
    """Shannon entropy of mechanism distribution, normalized to [0, 1].

    Measures how diverse the primary pairing mechanisms are across a set
    of candidate structures. A uniform distribution scores 1.0; a single
    mechanism scores 0.0.

    Args:
        structures: List of dicts with "primary_mechanism" (str) key.

    Returns:
        Float in [0, 1]. Returns 0.0 if structures is empty or has
        only one mechanism type.
    """
    if not structures:
        return 0.0

    from collections import Counter

    mechanisms = [s.get("primary_mechanism", "unknown") for s in structures]
    counts = Counter(mechanisms)
    n_mechanisms = len(counts)

    if n_mechanisms <= 1:
        return 0.0

    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * np.log(p)

    max_entropy = np.log(n_mechanisms)
    return float(entropy / max_entropy) if max_entropy > 0 else 0.0
