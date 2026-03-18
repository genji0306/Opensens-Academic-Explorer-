"""Evaluation metrics for crystal structure prediction."""
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("AgentPB.Evaluation.Metrics")

try:
    from pymatgen.analysis.structure_matcher import StructureMatcher
    _MATCHER_AVAILABLE = True
except ImportError:
    _MATCHER_AVAILABLE = False


def structure_match_rate(predicted: list, reference: list,
                         ltol: float = 0.2, stol: float = 0.3,
                         angle_tol: float = 5.0) -> float:
    """Fraction of predicted structures matched by StructureMatcher.

    Args:
        predicted: List of pymatgen Structure objects.
        reference: List of pymatgen Structure objects (same order).
        ltol: Fractional length tolerance.
        stol: Site tolerance.
        angle_tol: Angle tolerance in degrees.

    Returns:
        Match rate in [0, 1].
    """
    if not _MATCHER_AVAILABLE:
        logger.warning("pymatgen StructureMatcher not available.")
        return 0.0

    if not predicted or not reference:
        return 0.0

    matcher = StructureMatcher(ltol=ltol, stol=stol, angle_tol=angle_tol)
    matches = 0
    n = min(len(predicted), len(reference))
    for i in range(n):
        try:
            if matcher.fit(predicted[i], reference[i]):
                matches += 1
        except Exception:
            pass
    return matches / n if n > 0 else 0.0


def atomic_rmsd(predicted, reference) -> float:
    """Root mean square displacement after optimal alignment.

    Returns RMSD in Angstrom, or -1.0 on failure.
    """
    if not _MATCHER_AVAILABLE:
        return -1.0
    try:
        matcher = StructureMatcher()
        rms = matcher.get_rms_dist(predicted, reference)
        if rms is None:
            return -1.0
        return float(rms[0])  # (rms_dist, max_dist)
    except Exception:
        return -1.0


def fingerprint_distance(predicted, reference) -> float:
    """CrystalNN structure fingerprint cosine distance.

    Returns distance in [0, 2], or -1.0 if unavailable.
    """
    try:
        from matminer.featurizers.site import CrystalNNFingerprint
        cnnf = CrystalNNFingerprint.from_preset("ops")

        fp_pred = np.mean([cnnf.featurize(predicted, i)
                           for i in range(len(predicted))], axis=0)
        fp_ref = np.mean([cnnf.featurize(reference, i)
                          for i in range(len(reference))], axis=0)

        cos_sim = np.dot(fp_pred, fp_ref) / (np.linalg.norm(fp_pred) * np.linalg.norm(fp_ref))
        return float(1 - cos_sim)
    except Exception as e:
        logger.debug(f"Fingerprint distance failed: {e}")
        return -1.0


def energy_mae(predicted_energies: list, reference_energies: list) -> float:
    """Mean absolute error of formation energies (eV/atom)."""
    if not predicted_energies or not reference_energies:
        return -1.0
    n = min(len(predicted_energies), len(reference_energies))
    return float(np.mean(np.abs(
        np.array(predicted_energies[:n]) - np.array(reference_energies[:n]))))


def space_group_accuracy(predicted_sgs: list, reference_sgs: list) -> float:
    """Fraction with exact space group match."""
    if not predicted_sgs or not reference_sgs:
        return 0.0
    n = min(len(predicted_sgs), len(reference_sgs))
    matches = sum(1 for p, r in zip(predicted_sgs[:n], reference_sgs[:n]) if p == r)
    return matches / n
