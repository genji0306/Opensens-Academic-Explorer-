"""XRD intensity normalization and grid resampling."""
import logging

import numpy as np

from agent_xc.preprocessing.xrd_reader import XRDPattern
from agent_xc.config import DEFAULT_TWO_THETA_RANGE, DEFAULT_STEP

logger = logging.getLogger("AgentXC.Preprocessing.Normalizer")


def normalize_intensity(pattern: XRDPattern) -> XRDPattern:
    """Normalize intensity to [0, 1] range (min-max normalization)."""
    i_min = np.min(pattern.intensity)
    i_max = np.max(pattern.intensity)

    if i_max - i_min < 1e-10:
        logger.warning("Flat intensity pattern detected. Returning zeros.")
        normalized = np.zeros_like(pattern.intensity)
    else:
        normalized = (pattern.intensity - i_min) / (i_max - i_min)

    return XRDPattern(
        two_theta=pattern.two_theta.copy(),
        intensity=normalized,
        wavelength=pattern.wavelength,
        source_file=pattern.source_file,
    )


def resample_to_grid(pattern: XRDPattern,
                     two_theta_range: tuple = DEFAULT_TWO_THETA_RANGE,
                     step: float = DEFAULT_STEP) -> XRDPattern:
    """Resample pattern to fixed 2theta grid using linear interpolation.

    Args:
        pattern: Input XRD pattern.
        two_theta_range: (min, max) degrees.
        step: Grid step in degrees.

    Returns:
        Resampled XRDPattern on uniform grid.
    """
    grid = np.arange(two_theta_range[0], two_theta_range[1] + step / 2, step)
    resampled_intensity = np.interp(grid, pattern.two_theta, pattern.intensity,
                                     left=0.0, right=0.0)

    logger.info(f"Resampled to {len(grid)} points "
                f"({two_theta_range[0]}-{two_theta_range[1]} deg, step={step})")

    return XRDPattern(
        two_theta=grid,
        intensity=resampled_intensity,
        wavelength=pattern.wavelength,
        source_file=pattern.source_file,
    )


def preprocess_pattern(pattern: XRDPattern,
                       two_theta_range: tuple = DEFAULT_TWO_THETA_RANGE,
                       step: float = DEFAULT_STEP) -> XRDPattern:
    """Full preprocessing: normalize -> resample to grid."""
    pattern = normalize_intensity(pattern)
    pattern = resample_to_grid(pattern, two_theta_range, step)
    return pattern
