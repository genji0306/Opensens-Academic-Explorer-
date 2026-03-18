"""Simulate powder XRD pattern from a crystal structure."""
import logging

import numpy as np

from agent_xc.preprocessing.xrd_reader import XRDPattern
from agent_xc.config import DEFAULT_WAVELENGTH, DEFAULT_TWO_THETA_RANGE

logger = logging.getLogger("AgentXC.PostProcessing.XRDSimulator")

try:
    from pymatgen.analysis.diffraction.xrd import XRDCalculator
    _XRD_CALC_AVAILABLE = True
except ImportError:
    _XRD_CALC_AVAILABLE = False
    logger.info("pymatgen XRDCalculator not available.")


def simulate_xrd(structure, wavelength: float = DEFAULT_WAVELENGTH,
                 two_theta_range: tuple = DEFAULT_TWO_THETA_RANGE) -> XRDPattern:
    """Simulate powder XRD pattern from a crystal structure.

    Args:
        structure: pymatgen Structure object.
        wavelength: X-ray wavelength in Angstrom (default: Cu K-alpha1).
        two_theta_range: (min, max) 2theta in degrees.

    Returns:
        Simulated XRDPattern.
    """
    if not _XRD_CALC_AVAILABLE:
        raise ImportError("pymatgen.analysis.diffraction.xrd required for XRD simulation.")

    # Map wavelength to radiation type
    if abs(wavelength - 1.5406) < 0.01:
        radiation = "CuKa"
    elif abs(wavelength - 0.7093) < 0.01:
        radiation = "MoKa"
    elif abs(wavelength - 1.7902) < 0.01:
        radiation = "CoKa"
    else:
        radiation = "CuKa"  # fallback

    calc = XRDCalculator(wavelength=radiation)
    pattern = calc.get_pattern(structure, two_theta_range=two_theta_range)

    # Convert to uniform grid for comparison
    grid_step = 0.02
    grid = np.arange(two_theta_range[0], two_theta_range[1] + grid_step / 2, grid_step)
    intensity = np.zeros_like(grid)

    # Place peaks with Gaussian broadening
    sigma = 0.1  # degrees FWHM ~ 0.24 deg
    for angle, peak_intensity in zip(pattern.x, pattern.y):
        intensity += peak_intensity * np.exp(-0.5 * ((grid - angle) / sigma) ** 2)

    # Normalize
    if np.max(intensity) > 0:
        intensity /= np.max(intensity)

    return XRDPattern(
        two_theta=grid,
        intensity=intensity,
        wavelength=wavelength,
    )
