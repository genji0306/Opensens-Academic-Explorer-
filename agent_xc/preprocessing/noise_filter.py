"""Noise filtering for XRD patterns."""
import logging

import numpy as np

from agent_xc.preprocessing.xrd_reader import XRDPattern
from agent_xc.config import DEFAULT_SG_WINDOW, DEFAULT_SG_POLYORDER

logger = logging.getLogger("AgentXC.Preprocessing.NoiseFilter")

try:
    from scipy.signal import savgol_filter
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False
    logger.info("scipy not installed. Noise filtering unavailable.")


def savitzky_golay_filter(pattern: XRDPattern,
                          window_length: int = DEFAULT_SG_WINDOW,
                          polyorder: int = DEFAULT_SG_POLYORDER) -> XRDPattern:
    """Apply Savitzky-Golay smoothing to reduce noise.

    Args:
        pattern: Input XRD pattern.
        window_length: Window size (must be odd). Default: 11.
        polyorder: Polynomial order. Default: 3.

    Returns:
        Smoothed XRDPattern.
    """
    if not _SCIPY_AVAILABLE:
        logger.warning("scipy not available. Returning unfiltered pattern.")
        return pattern

    if pattern.n_points < window_length:
        logger.warning(f"Pattern too short ({pattern.n_points} points) "
                       f"for window={window_length}. Skipping filter.")
        return pattern

    # Ensure window_length is odd
    if window_length % 2 == 0:
        window_length += 1

    smoothed = savgol_filter(pattern.intensity, window_length, polyorder)
    # Ensure non-negative
    smoothed = np.maximum(smoothed, 0.0)

    logger.info(f"Applied Savitzky-Golay filter (window={window_length}, order={polyorder})")

    return XRDPattern(
        two_theta=pattern.two_theta.copy(),
        intensity=smoothed,
        wavelength=pattern.wavelength,
        source_file=pattern.source_file,
    )
