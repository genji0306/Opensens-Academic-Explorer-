"""XRD pattern file reader — supports .xy, .csv, .dat formats."""
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from agent_xc.config import DEFAULT_WAVELENGTH

logger = logging.getLogger("AgentXC.Preprocessing.Reader")


@dataclass
class XRDPattern:
    """Powder X-ray diffraction pattern data."""
    two_theta: np.ndarray = field(default_factory=lambda: np.array([]))
    intensity: np.ndarray = field(default_factory=lambda: np.array([]))
    wavelength: float = DEFAULT_WAVELENGTH
    source_file: str = ""

    @property
    def n_points(self) -> int:
        return len(self.two_theta)

    @property
    def two_theta_range(self) -> tuple:
        if self.n_points == 0:
            return (0.0, 0.0)
        return (float(self.two_theta[0]), float(self.two_theta[-1]))

    def is_valid(self) -> bool:
        return (self.n_points > 0 and
                len(self.two_theta) == len(self.intensity) and
                np.all(np.diff(self.two_theta) > 0))  # monotonically increasing


def read_xy(path: Path) -> XRDPattern:
    """Read two-column .xy/.dat format (2theta intensity)."""
    path = Path(path)
    data = np.loadtxt(str(path), comments=("#", "!"))
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"Expected 2-column data in {path}, got shape {data.shape}")

    return XRDPattern(
        two_theta=data[:, 0].astype(np.float64),
        intensity=data[:, 1].astype(np.float64),
        source_file=str(path),
    )


def read_csv(path: Path) -> XRDPattern:
    """Read CSV with header (auto-detect 2theta and intensity columns)."""
    path = Path(path)
    df = pd.read_csv(path)

    # Try common column name patterns
    theta_cols = [c for c in df.columns if any(k in c.lower()
                  for k in ("2theta", "two_theta", "angle", "2th"))]
    intensity_cols = [c for c in df.columns if any(k in c.lower()
                      for k in ("intensity", "counts", "int", "i("))]

    if not theta_cols or not intensity_cols:
        # Fallback: assume first two numeric columns
        numeric = df.select_dtypes(include=[np.number]).columns
        if len(numeric) >= 2:
            theta_cols = [numeric[0]]
            intensity_cols = [numeric[1]]
        else:
            raise ValueError(f"Cannot identify 2theta/intensity columns in {path}")

    return XRDPattern(
        two_theta=df[theta_cols[0]].values.astype(np.float64),
        intensity=df[intensity_cols[0]].values.astype(np.float64),
        source_file=str(path),
    )


def read_xrd(path: Path) -> XRDPattern:
    """Auto-detect format and read XRD pattern file."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".xy", ".dat"):
        pattern = read_xy(path)
    elif suffix == ".csv":
        pattern = read_csv(path)
    elif suffix == ".txt":
        # Try XY format first, fall back to CSV
        try:
            pattern = read_xy(path)
        except Exception:
            pattern = read_csv(path)
    else:
        raise ValueError(f"Unsupported XRD format: {suffix}. "
                         "Supported: .xy, .dat, .csv, .txt")

    if not pattern.is_valid():
        raise ValueError(f"Invalid XRD pattern from {path}: "
                         f"{pattern.n_points} points, range {pattern.two_theta_range}")

    logger.info(f"Read XRD pattern from {path.name}: {pattern.n_points} points, "
                f"range {pattern.two_theta_range[0]:.1f}-{pattern.two_theta_range[1]:.1f} deg")
    return pattern
