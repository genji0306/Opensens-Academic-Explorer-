"""
PNG image export of crystal structures for Agent V.

Renders a 2D orthographic projection of the unit cell using matplotlib
and saves it as a PNG file.  Supports pymatgen ``Structure`` objects and
falls back to a simple scatter plot for raw coordinate lists.
"""

import logging
import math
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentV.Exporters.PNG")

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch
    import numpy as np

    _MPL = True
except ImportError:
    _MPL = False
    logger.info("matplotlib not installed — PNG export unavailable.")

from agent_v.config import CPK_COLORS, CPK_DEFAULT_COLOR, EXPORTS_DIR


def _color_for(elem: str) -> str:
    clean = "".join(c for c in elem if c.isalpha())
    return CPK_COLORS.get(clean, CPK_DEFAULT_COLOR)


def _covalent_radius(elem: str) -> float:
    """Approximate covalent radius in angstroms for marker sizing."""
    radii = {
        "H": 0.31, "He": 0.28, "Li": 1.28, "Be": 0.96, "B": 0.84,
        "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "Na": 1.66,
        "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07, "S": 1.05,
        "Cl": 1.02, "K": 2.03, "Ca": 1.76, "Ti": 1.60, "V": 1.53,
        "Cr": 1.39, "Mn": 1.39, "Fe": 1.32, "Co": 1.26, "Ni": 1.24,
        "Cu": 1.32, "Zn": 1.22, "Ga": 1.22, "Ge": 1.20, "As": 1.19,
        "Se": 1.20, "Br": 1.20, "Sr": 2.15, "Y": 1.90, "Zr": 1.75,
        "Nb": 1.64, "Mo": 1.54, "Ru": 1.46, "Rh": 1.42, "Pd": 1.39,
        "Ag": 1.45, "In": 1.42, "Sn": 1.39, "Sb": 1.39, "Te": 1.38,
        "Ba": 2.15, "La": 2.07, "Ce": 2.04, "Hf": 1.75, "Ta": 1.70,
        "W": 1.62, "Re": 1.51, "Os": 1.44, "Ir": 1.41, "Pt": 1.36,
        "Au": 1.36, "Pb": 1.46, "Bi": 1.48,
    }
    clean = "".join(c for c in elem if c.isalpha())
    return radii.get(clean, 1.0)


def export_structure_image(
    structure: Any,
    output_path: Optional[Path | str] = None,
    width: int = 800,
    height: int = 800,
) -> Path:
    """Render a unit cell as a 2D PNG image.

    The image shows an XY orthographic projection with depth-cued atom
    sizes (atoms further in z are drawn smaller and more transparent).

    Parameters
    ----------
    structure :
        A ``pymatgen.core.Structure`` or compatible duck type with
        ``.sites`` and ``.lattice``.
    output_path : Path | str | None
        Full path for the output PNG.  Defaults to
        ``data/exports/<formula>.png``.
    width, height : int
        Figure size in pixels (at 100 dpi).

    Returns
    -------
    Path
        Resolved path to the written PNG.

    Raises
    ------
    ImportError
        If matplotlib is not available.
    """
    if not _MPL:
        raise ImportError("matplotlib is required for PNG export.")

    # --- Extract data from structure ---
    try:
        species = [str(s.specie) for s in structure.sites]
        cart_coords = [tuple(s.coords) for s in structure.sites]
        formula = structure.composition.reduced_formula
        lattice = structure.lattice
    except Exception as exc:
        raise TypeError(f"Cannot extract sites/lattice from structure: {exc}") from exc

    # --- Output path ---
    if output_path is None:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in formula)
        output_path = EXPORTS_DIR / f"{safe}.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Figure setup ---
    dpi = 100
    fig_w = width / dpi
    fig_h = height / dpi
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_aspect("equal")
    ax.set_title(f"{formula} — unit cell XY projection", fontsize=12)
    ax.set_xlabel("x (\u00c5)", fontsize=10)
    ax.set_ylabel("y (\u00c5)", fontsize=10)

    # --- Draw unit cell outline (XY projection of lattice vectors) ---
    a_vec = lattice.matrix[0]
    b_vec = lattice.matrix[1]

    corners_xy = [
        (0, 0),
        (a_vec[0], a_vec[1]),
        (a_vec[0] + b_vec[0], a_vec[1] + b_vec[1]),
        (b_vec[0], b_vec[1]),
        (0, 0),
    ]
    xs_cell = [c[0] for c in corners_xy]
    ys_cell = [c[1] for c in corners_xy]
    ax.plot(xs_cell, ys_cell, color="gray", linewidth=1.0, linestyle="--", zorder=1)

    # --- Depth sort (draw far atoms first) ---
    if cart_coords:
        z_vals = [c[2] for c in cart_coords]
        z_min = min(z_vals)
        z_max = max(z_vals)
        z_range = max(z_max - z_min, 0.01)

        # Sort back-to-front
        order = sorted(range(len(cart_coords)), key=lambda i: cart_coords[i][2])

        for idx in order:
            elem = species[idx]
            x, y, z = cart_coords[idx]
            color = _color_for(elem)
            r = _covalent_radius(elem)

            # Normalised depth 0..1
            depth = (z - z_min) / z_range

            # Size scaling: back atoms smaller, front atoms bigger
            marker_size = (0.4 + 0.6 * depth) * r * 120
            alpha = 0.5 + 0.5 * depth

            ax.scatter(
                x, y,
                s=marker_size,
                c=color,
                alpha=alpha,
                edgecolors="black",
                linewidths=0.5,
                zorder=2 + int(depth * 100),
            )
            ax.annotate(
                elem, (x, y),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=7,
                color="black",
                alpha=alpha,
                zorder=3 + int(depth * 100),
            )

    # --- Lattice vector arrows ---
    origin = (0.0, 0.0)
    for vec, label in [(a_vec, "a"), (b_vec, "b")]:
        ax.annotate(
            "",
            xy=(vec[0], vec[1]),
            xytext=origin,
            arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
            zorder=10,
        )
        ax.text(
            vec[0] * 1.05, vec[1] * 1.05, label,
            fontsize=9, color="red", fontweight="bold", zorder=10,
        )

    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    logger.info("Structure image exported to %s (%dx%d)", output_path, width, height)
    return output_path.resolve()
