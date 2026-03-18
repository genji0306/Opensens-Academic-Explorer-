"""XRD pattern match scoring — Rwp and Rp calculation."""
import logging

import numpy as np

from agent_xc.preprocessing.xrd_reader import XRDPattern
from agent_xc.preprocessing.normalizer import resample_to_grid

logger = logging.getLogger("AgentXC.PostProcessing.MatchScorer")


def compute_rwp(observed: XRDPattern, calculated: XRDPattern) -> float:
    """Compute weighted profile R-factor (Rwp).

    Rwp = sqrt( sum[w*(y_obs - y_calc)^2] / sum[w*y_obs^2] )

    Lower Rwp indicates better match. Values < 0.10 (10%) are good.
    """
    # Resample both to same grid
    obs = resample_to_grid(observed)
    calc = resample_to_grid(calculated,
                            two_theta_range=obs.two_theta_range,
                            step=obs.two_theta[1] - obs.two_theta[0] if obs.n_points > 1 else 0.02)

    n = min(obs.n_points, calc.n_points)
    y_obs = obs.intensity[:n]
    y_calc = calc.intensity[:n]

    # Weights: 1/y_obs for standard weighting, uniform as fallback
    w = np.ones_like(y_obs)
    mask = y_obs > 1e-6
    w[mask] = 1.0 / y_obs[mask]

    numerator = np.sum(w * (y_obs - y_calc) ** 2)
    denominator = np.sum(w * y_obs ** 2)

    if denominator < 1e-10:
        return 1.0  # Undefined, return worst

    rwp = np.sqrt(numerator / denominator)
    return float(rwp)


def compute_rp(observed: XRDPattern, calculated: XRDPattern) -> float:
    """Compute unweighted profile R-factor (Rp).

    Rp = sum|y_obs - y_calc| / sum|y_obs|
    """
    obs = resample_to_grid(observed)
    calc = resample_to_grid(calculated,
                            two_theta_range=obs.two_theta_range,
                            step=obs.two_theta[1] - obs.two_theta[0] if obs.n_points > 1 else 0.02)

    n = min(obs.n_points, calc.n_points)
    y_obs = obs.intensity[:n]
    y_calc = calc.intensity[:n]

    denom = np.sum(np.abs(y_obs))
    if denom < 1e-10:
        return 1.0

    rp = np.sum(np.abs(y_obs - y_calc)) / denom
    return float(rp)


def compute_pattern_similarity(observed: XRDPattern, calculated: XRDPattern) -> float:
    """Compute normalized cross-correlation between patterns.

    Returns value in [0, 1], where 1 is perfect match.
    """
    obs = resample_to_grid(observed)
    calc = resample_to_grid(calculated,
                            two_theta_range=obs.two_theta_range,
                            step=obs.two_theta[1] - obs.two_theta[0] if obs.n_points > 1 else 0.02)

    n = min(obs.n_points, calc.n_points)
    y_obs = obs.intensity[:n]
    y_calc = calc.intensity[:n]

    norm_obs = np.linalg.norm(y_obs)
    norm_calc = np.linalg.norm(y_calc)

    if norm_obs < 1e-10 or norm_calc < 1e-10:
        return 0.0

    return float(np.dot(y_obs, y_calc) / (norm_obs * norm_calc))
