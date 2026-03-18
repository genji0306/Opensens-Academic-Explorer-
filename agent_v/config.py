"""
Agent V configuration — paths, colour maps, dashboard settings.

All filesystem paths are resolved relative to PROJECT_ROOT so the package
works regardless of the caller's working directory.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project layout
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = PROJECT_ROOT / "data"
EXPORTS_DIR: Path = DATA_DIR / "exports"
STRUCTURES_WATCH_DIR: Path = DATA_DIR / "crystal_structures"
PREDICTIONS_WATCH_DIR: Path = DATA_DIR / "predictions"
REPORTS_DIR: Path = DATA_DIR / "reports"
SYNTHETIC_DIR: Path = DATA_DIR / "synthetic"
REFINEMENTS_DIR: Path = DATA_DIR / "refinements"
NOVEL_CANDIDATES_DIR: Path = DATA_DIR / "novel_candidates"

# ---------------------------------------------------------------------------
# Dash server defaults
# ---------------------------------------------------------------------------
DASH_HOST: str = "127.0.0.1"
DASH_PORT: int = 8050
EDITOR_PORT: int = 8052

# ---------------------------------------------------------------------------
# CPK atom colours  (rgb strings for both matplotlib and plotly)
# Covers the most common elements in superconductor crystal structures.
# ---------------------------------------------------------------------------
CPK_COLORS: dict[str, str] = {
    "H":  "#FFFFFF",
    "He": "#D9FFFF",
    "Li": "#CC80FF",
    "Be": "#C2FF00",
    "B":  "#FFB5B5",
    "C":  "#909090",
    "N":  "#3050F8",
    "O":  "#FF0D0D",
    "F":  "#90E050",
    "Ne": "#B3E3F5",
    "Na": "#AB5CF2",
    "Mg": "#8AFF00",
    "Al": "#BFA6A6",
    "Si": "#F0C8A0",
    "P":  "#FF8000",
    "S":  "#FFFF30",
    "Cl": "#1FF01F",
    "Ar": "#80D1E3",
    "K":  "#8F40D4",
    "Ca": "#3DFF00",
    "Ti": "#BFC2C7",
    "V":  "#A6A6AB",
    "Cr": "#8A99C7",
    "Mn": "#9C7AC7",
    "Fe": "#E06633",
    "Co": "#F090A0",
    "Ni": "#50D050",
    "Cu": "#C88033",
    "Zn": "#7D80B0",
    "Ga": "#C28F8F",
    "Ge": "#668F8F",
    "As": "#BD80E3",
    "Se": "#FFA100",
    "Br": "#A62929",
    "Sr": "#00FF00",
    "Y":  "#94FFFF",
    "Zr": "#94E0E0",
    "Nb": "#73C2C9",
    "Mo": "#54B5B5",
    "Ru": "#248F8F",
    "Rh": "#0A7D8C",
    "Pd": "#006985",
    "Ag": "#C0C0C0",
    "Cd": "#FFD98F",
    "In": "#A67573",
    "Sn": "#668080",
    "Sb": "#9E63B5",
    "Te": "#D47A00",
    "Ba": "#00C900",
    "La": "#70D4FF",
    "Ce": "#FFFFC7",
    "Hf": "#4DC2FF",
    "Ta": "#4DA6FF",
    "W":  "#2194D6",
    "Re": "#267DAB",
    "Os": "#266696",
    "Ir": "#175487",
    "Pt": "#D0D0E0",
    "Au": "#FFD123",
    "Hg": "#B8B8D0",
    "Tl": "#A6544D",
    "Pb": "#575961",
    "Bi": "#9E4FB5",
}

# Fallback for elements not listed above
CPK_DEFAULT_COLOR: str = "#FF1493"

# ---------------------------------------------------------------------------
# Van der Waals radii (Angstrom)
# Used by the crystal viewer for ball-and-stick and space-filling modes.
# ---------------------------------------------------------------------------
VDW_RADII: dict[str, float] = {
    "H": 1.20, "He": 1.40, "Li": 1.82, "Be": 1.53, "B": 1.92,
    "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "Ne": 1.54,
    "Na": 2.27, "Mg": 1.73, "Al": 1.84, "Si": 2.10, "P": 1.80,
    "S": 1.80, "Cl": 1.75, "Ar": 1.88, "K": 2.75, "Ca": 2.31,
    "Ti": 2.11, "V": 2.07, "Cr": 2.06, "Mn": 2.05, "Fe": 2.04,
    "Co": 2.00, "Ni": 1.97, "Cu": 1.96, "Zn": 2.01, "Ga": 1.87,
    "Ge": 2.11, "As": 1.85, "Se": 1.90, "Br": 1.85, "Sr": 2.49,
    "Y": 2.32, "Zr": 2.23, "Nb": 2.18, "Mo": 2.17, "Ru": 2.13,
    "Rh": 2.10, "Pd": 2.10, "Ag": 2.11, "Cd": 2.18, "In": 1.93,
    "Sn": 2.17, "Sb": 2.06, "Te": 2.06, "Ba": 2.68, "La": 2.43,
    "Ce": 2.42, "Hf": 2.23, "Ta": 2.22, "W": 2.18, "Re": 2.16,
    "Os": 2.16, "Ir": 2.13, "Pt": 2.13, "Au": 2.14, "Hg": 2.23,
    "Tl": 1.96, "Pb": 2.02, "Bi": 2.07,
}

# Covalent radii (Angstrom) for bond distance detection
COVALENT_RADII: dict[str, float] = {
    "H": 0.31, "Li": 1.28, "Be": 0.96, "B": 0.84, "C": 0.76,
    "N": 0.71, "O": 0.66, "F": 0.57, "Na": 1.66, "Mg": 1.41,
    "Al": 1.21, "Si": 1.11, "P": 1.07, "S": 1.05, "Cl": 1.02,
    "K": 2.03, "Ca": 1.76, "Ti": 1.60, "V": 1.53, "Cr": 1.39,
    "Mn": 1.39, "Fe": 1.32, "Co": 1.26, "Ni": 1.24, "Cu": 1.32,
    "Zn": 1.22, "Ga": 1.22, "Ge": 1.20, "As": 1.19, "Se": 1.20,
    "Br": 1.20, "Sr": 1.95, "Y": 1.90, "Zr": 1.75, "Nb": 1.64,
    "Mo": 1.54, "Ru": 1.46, "Rh": 1.42, "Pd": 1.39, "Ag": 1.45,
    "Cd": 1.44, "In": 1.42, "Sn": 1.39, "Sb": 1.39, "Te": 1.38,
    "Ba": 2.15, "La": 2.07, "Ce": 2.04, "Hf": 1.75, "Ta": 1.70,
    "W": 1.62, "Re": 1.51, "Os": 1.44, "Ir": 1.41, "Pt": 1.36,
    "Au": 1.36, "Hg": 1.32, "Tl": 1.45, "Pb": 1.46, "Bi": 1.48,
}

# ---------------------------------------------------------------------------
# Superconductor family colour palette
# Matches SC_FAMILIES from src/core/config.py so the dashboard can colour
# data points per-family consistently.
# ---------------------------------------------------------------------------
FAMILY_COLORS: dict[str, str] = {
    "cuprate":            "#E63946",
    "iron-pnictide":      "#457B9D",
    "iron-chalcogenide":  "#1D3557",
    "heavy-fermion":      "#A8DADC",
    "mgb2-type":          "#2A9D8F",
    "hydride":            "#E9C46A",
    "nickelate":          "#F4A261",
    "a15":                "#264653",
    "chevrel":            "#606C38",
    "organic":            "#DDA15E",
    "other":              "#BC6C25",
}


def ensure_dirs() -> None:
    """Create export and watch directories if they do not exist."""
    for d in (EXPORTS_DIR, STRUCTURES_WATCH_DIR, PREDICTIONS_WATCH_DIR,
              REPORTS_DIR, SYNTHETIC_DIR, REFINEMENTS_DIR, NOVEL_CANDIDATES_DIR):
        d.mkdir(parents=True, exist_ok=True)
