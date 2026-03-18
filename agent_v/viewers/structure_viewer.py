"""
Crystal structure viewer for Agent V.

Generates interactive 3D HTML using the 3Dmol.js CDN (runs in the
browser via an iframe) or static 2D projection images (matplotlib fallback).

The 3D viewer does NOT require the ``py3Dmol`` Python package — it writes
a self-contained HTML page that loads ``3Dmol-min.js`` from the CDN.  Only
**pymatgen** is needed to parse CIF files into Structure objects.

View modes:
  - ball-and-stick (default): spheres at scaled VdW radii + stick bonds
  - space-filling: full VdW-radius spheres, no sticks
  - polyhedral: coordination polyhedra around metal centers
  - unit-cell: sticks + labeled a/b/c lattice vectors

Legacy style names (stick, sphere, line, cross) remain supported.
"""

import logging
import math
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentV.Viewers.Structure")

# ---------------------------------------------------------------------------
# Optional dependency probes
# ---------------------------------------------------------------------------

# py3Dmol Python package is NOT required.  We generate 3Dmol.js HTML
# that runs entirely in the browser.  Only pymatgen is needed for CIF parsing.

try:
    import matplotlib

    matplotlib.use("Agg")  # headless backend
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    _MPL = True
except ImportError:
    _MPL = False

try:
    from pymatgen.core import Structure
    from pymatgen.io.cif import CifParser

    _PYMATGEN = True
except ImportError:
    try:
        from pymatgen import Structure
        from pymatgen.io.cif import CifParser

        _PYMATGEN = True
    except ImportError:
        _PYMATGEN = False

from agent_v.config import CPK_COLORS, CPK_DEFAULT_COLOR, VDW_RADII, COVALENT_RADII


# ---------------------------------------------------------------------------
# Metal elements for polyhedral detection
# ---------------------------------------------------------------------------
_METALS = {
    "Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba",
    "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Y", "Zr", "Nb", "Mo", "Ru", "Rh", "Pd", "Ag", "Cd",
    "La", "Ce", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au",
    "Al", "Ga", "In", "Sn", "Tl", "Pb", "Bi",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _structure_to_xyz(structure: Any) -> str:
    """Convert a pymatgen Structure to an XYZ-format string with
    Cartesian coordinates (for py3Dmol)."""
    sites = structure.sites
    lines = [str(len(sites)), structure.composition.reduced_formula]
    for site in sites:
        elem = str(site.specie)
        x, y, z = site.coords
        lines.append(f"{elem} {x:.6f} {y:.6f} {z:.6f}")
    return "\n".join(lines)


def _color_for_element(elem: str) -> str:
    """Return a hex colour for *elem*, with fallback."""
    # Strip charge annotations like Fe3+
    clean = "".join(c for c in elem if c.isalpha())
    return CPK_COLORS.get(clean, CPK_DEFAULT_COLOR)


def _unit_cell_lines_js(structure: Any) -> str:
    """Generate py3Dmol JavaScript to draw the unit cell edges."""
    lat = structure.lattice
    a_vec = lat.matrix[0]
    b_vec = lat.matrix[1]
    c_vec = lat.matrix[2]

    # 8 corners of the parallelepiped
    origin = [0.0, 0.0, 0.0]
    corners = [
        origin,
        list(a_vec),
        list(b_vec),
        list(c_vec),
        list(a_vec + b_vec),
        list(a_vec + c_vec),
        list(b_vec + c_vec),
        list(a_vec + b_vec + c_vec),
    ]

    # 12 edges
    edges = [
        (0, 1), (0, 2), (0, 3),
        (1, 4), (1, 5),
        (2, 4), (2, 6),
        (3, 5), (3, 6),
        (4, 7), (5, 7), (6, 7),
    ]

    js_lines = []
    for i, j in edges:
        c1, c2 = corners[i], corners[j]
        js_lines.append(
            f"viewer.addCylinder({{start:{{x:{c1[0]:.4f},y:{c1[1]:.4f},z:{c1[2]:.4f}}},"
            f"end:{{x:{c2[0]:.4f},y:{c2[1]:.4f},z:{c2[2]:.4f}}},"
            f"radius:0.04,fromCap:1,toCap:1,color:'gray'}});"
        )
    return "\n".join(js_lines)


def _unit_cell_labeled_js(structure: Any) -> str:
    """Unit cell edges + color-coded a/b/c axis arrows with labels."""
    lat = structure.lattice
    a_vec = lat.matrix[0]
    b_vec = lat.matrix[1]
    c_vec = lat.matrix[2]

    origin = [0.0, 0.0, 0.0]
    corners = [
        origin, list(a_vec), list(b_vec), list(c_vec),
        list(a_vec + b_vec), list(a_vec + c_vec),
        list(b_vec + c_vec), list(a_vec + b_vec + c_vec),
    ]

    # Color-coded axis edges (a=red, b=green, c=blue)
    axis_edges = [
        (0, 1, "#E63946"),  # a-axis
        (0, 2, "#2A9D8F"),  # b-axis
        (0, 3, "#457B9D"),  # c-axis
    ]
    # Remaining edges in grey
    other_edges = [
        (1, 4), (1, 5), (2, 4), (2, 6),
        (3, 5), (3, 6), (4, 7), (5, 7), (6, 7),
    ]

    js_lines = []

    # Axis edges (thicker)
    for i, j, color in axis_edges:
        c1, c2 = corners[i], corners[j]
        js_lines.append(
            f"viewer.addCylinder({{start:{{x:{c1[0]:.4f},y:{c1[1]:.4f},z:{c1[2]:.4f}}},"
            f"end:{{x:{c2[0]:.4f},y:{c2[1]:.4f},z:{c2[2]:.4f}}},"
            f"radius:0.08,fromCap:1,toCap:1,color:'{color}'}});"
        )

    # Other edges (thin grey)
    for i, j in other_edges:
        c1, c2 = corners[i], corners[j]
        js_lines.append(
            f"viewer.addCylinder({{start:{{x:{c1[0]:.4f},y:{c1[1]:.4f},z:{c1[2]:.4f}}},"
            f"end:{{x:{c2[0]:.4f},y:{c2[1]:.4f},z:{c2[2]:.4f}}},"
            f"radius:0.04,fromCap:1,toCap:1,color:'gray'}});"
        )

    # Axis labels at endpoints
    a_len = f"{lat.a:.2f}"
    b_len = f"{lat.b:.2f}"
    c_len = f"{lat.c:.2f}"

    labels = [
        (a_vec, f"a={a_len}\u00c5", "#E63946"),
        (b_vec, f"b={b_len}\u00c5", "#2A9D8F"),
        (c_vec, f"c={c_len}\u00c5", "#457B9D"),
    ]
    for vec, text, color in labels:
        js_lines.append(
            f"viewer.addLabel(\"{text}\", {{position:{{x:{vec[0]:.4f},y:{vec[1]:.4f},z:{vec[2]:.4f}}},"
            f"fontSize:13,fontColor:'{color}',backgroundColor:'rgba(255,255,255,0.8)',"
            f"borderColor:'{color}',borderThickness:1,backgroundOpacity:0.85}});"
        )

    # Origin label
    js_lines.append(
        "viewer.addLabel(\"O\", {position:{x:0,y:0,z:0},"
        "fontSize:11,fontColor:'gray',backgroundColor:'rgba(255,255,255,0.7)',"
        "borderColor:'gray',borderThickness:1,backgroundOpacity:0.7});"
    )

    return "\n".join(js_lines)


# ---------------------------------------------------------------------------
# 2D matplotlib fallback
# ---------------------------------------------------------------------------

def _render_2d_projection(
    species: list[str],
    coords: list[tuple[float, float, float]],
    title: str = "Unit Cell — XY projection",
) -> str:
    """Render a 2D scatter plot (XY projection) and return an HTML <img>
    tag with the image base64-encoded inline.

    Works without py3Dmol — only needs matplotlib.
    """
    if not _MPL:
        return (
            "<p style='color:red;'>Neither py3Dmol nor matplotlib installed. "
            "Cannot render structure.</p>"
        )

    import io
    import base64

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("x (ang.)")
    ax.set_ylabel("y (ang.)")

    for elem, (x, y, z) in zip(species, coords):
        colour = _color_for_element(elem)
        # Use z for marker size scaling (depth cue)
        size = max(80, 200 - abs(z) * 10)
        ax.scatter(x, y, s=size, c=colour, edgecolors="black", linewidths=0.5, zorder=2)
        ax.annotate(elem, (x, y), textcoords="offset points", xytext=(4, 4),
                    fontsize=7, color="black", zorder=3)

    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{title}" />'


# ---------------------------------------------------------------------------
# HTML template for py3Dmol viewer
# ---------------------------------------------------------------------------

_VIEWER_HTML = """<!DOCTYPE html>
<html><head>
<style>
  body {{ margin:0; background:#FAFBFC; font-family:'Inter',sans-serif; }}
  #viewer-container {{
    width:100%; height:100%; display:flex; flex-direction:column;
    align-items:center; justify-content:center;
  }}
  #{viewer_id} {{
    width:{width}px; height:{height}px; position:relative;
    border-radius:8px; overflow:hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }}
  .legend {{
    margin-top:8px; display:flex; flex-wrap:wrap; gap:8px;
    justify-content:center; font-size:11px; color:#4A5568;
  }}
  .legend-item {{
    display:flex; align-items:center; gap:4px;
  }}
  .legend-dot {{
    width:10px; height:10px; border-radius:50%; border:1px solid #ccc;
  }}
</style>
</head><body>
<div id="viewer-container">
  <div id="{viewer_id}"></div>
  <div class="legend">{legend_html}</div>
</div>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
<script>
(function() {{
    var viewer = $3Dmol.createViewer("{viewer_id}",
        {{backgroundColor: "{bg_color}"}});
    var xyz = `{xyz}`;
    viewer.addModel(xyz, "xyz");
    {style_js}
    {cell_js}
    {extra_js}
    viewer.zoomTo();
    viewer.render();
}})();
</script>
</body></html>"""


def _build_legend_html(elements: set[str]) -> str:
    """Build an element colour legend strip."""
    items = []
    for elem in sorted(elements):
        c = _color_for_element(elem)
        items.append(
            f'<span class="legend-item">'
            f'<span class="legend-dot" style="background:{c}"></span>'
            f'{elem}</span>'
        )
    return "".join(items)


# ---------------------------------------------------------------------------
# StructureViewer
# ---------------------------------------------------------------------------

class StructureViewer:
    """Render crystal structures as interactive 3D HTML or 2D images."""

    @property
    def is_available(self) -> bool:
        """``True`` if at least one visualisation backend is installed.

        The 3D viewer only needs pymatgen (for CIF parsing); the actual
        3Dmol.js rendering happens in the browser via the CDN script.
        """
        return _PYMATGEN or _MPL

    # ------------------------------------------------------------------ #
    # render_structure  (from pymatgen Structure)
    # ------------------------------------------------------------------ #

    def render_structure(
        self,
        structure: Any,
        style: str = "ball-and-stick",
    ) -> str:
        """Render a ``pymatgen.core.Structure`` to an HTML string.

        Parameters
        ----------
        structure :
            A pymatgen ``Structure`` object.
        style : str
            View mode. One of ``"ball-and-stick"``, ``"space-filling"``,
            ``"polyhedral"``, ``"unit-cell"``.
            Legacy names ``"stick"``, ``"sphere"``, ``"line"``, ``"cross"``
            are also accepted.

        Returns
        -------
        str
            Self-contained HTML page (loads 3Dmol.js from CDN).
        """
        # Map legacy single-style names
        mode_map = {
            "stick": "ball-and-stick",
            "sphere": "space-filling",
            "line": "ball-and-stick",
            "cross": "ball-and-stick",
        }
        mode = mode_map.get(style, style)

        # 3D rendering via 3Dmol.js (all modes)
        if mode == "ball-and-stick":
            return self._render_ball_and_stick(structure)
        elif mode == "space-filling":
            return self._render_space_filling(structure)
        elif mode == "polyhedral":
            return self._render_polyhedral(structure)
        elif mode == "unit-cell":
            return self._render_unit_cell(structure)
        else:
            return self._render_ball_and_stick(structure)

    # ------------------------------------------------------------------ #
    # render_cif  (from file path)
    # ------------------------------------------------------------------ #

    def render_cif(self, cif_path: Path | str, style: str = "ball-and-stick") -> str:
        """Parse a CIF file and render it.

        Returns an HTML fragment, or an error message if parsing fails.
        """
        cif_path = Path(cif_path)

        if _PYMATGEN:
            try:
                parser = CifParser(str(cif_path))
                structures = parser.get_structures()
                if structures:
                    return self.render_structure(structures[0], style=style)
                return "<p style='color:red;'>No structures found in CIF.</p>"
            except Exception as exc:
                logger.error("CIF parsing failed for %s: %s", cif_path, exc)
                return f"<p style='color:red;'>CIF parse error: {exc}</p>"

        # Without pymatgen, try a very simple regex parse for coordinates
        return self._render_cif_regex(cif_path)

    # ------------------------------------------------------------------ #
    # Ball-and-stick mode
    # ------------------------------------------------------------------ #

    def _render_ball_and_stick(self, structure: Any) -> str:
        """Ball-and-stick: spheres at scaled VdW radii + thin stick bonds."""
        xyz = _structure_to_xyz(structure)
        cell_js = _unit_cell_lines_js(structure)
        elements: set[str] = set()

        style_lines = []
        for site in structure.sites:
            elem = str(site.specie)
            elements.add(elem)

        for elem in sorted(elements):
            c = _color_for_element(elem)
            r = VDW_RADII.get(elem, 1.5) * 0.25  # scaled down
            style_lines.append(
                f"viewer.setStyle({{elem:'{elem}'}}, "
                f"{{stick: {{radius: 0.12, color:'{c}'}}, "
                f"sphere: {{radius: {r:.3f}, color:'{c}'}}}});"
            )

        return _VIEWER_HTML.format(
            viewer_id=f"viewer_{id(structure) & 0xFFFFFF:06x}",
            width=600, height=420,
            bg_color="white",
            xyz=xyz,
            style_js="\n    ".join(style_lines),
            cell_js=cell_js,
            extra_js="",
            legend_html=_build_legend_html(elements),
        )

    # ------------------------------------------------------------------ #
    # Space-filling mode
    # ------------------------------------------------------------------ #

    def _render_space_filling(self, structure: Any) -> str:
        """Space-filling: full VdW-radius spheres, no sticks."""
        xyz = _structure_to_xyz(structure)
        cell_js = _unit_cell_lines_js(structure)
        elements: set[str] = set()

        style_lines = []
        for site in structure.sites:
            elem = str(site.specie)
            elements.add(elem)

        for elem in sorted(elements):
            c = _color_for_element(elem)
            r = VDW_RADII.get(elem, 1.5) * 0.45  # somewhat scaled for visual clarity
            style_lines.append(
                f"viewer.setStyle({{elem:'{elem}'}}, "
                f"{{sphere: {{radius: {r:.3f}, color:'{c}'}}}});"
            )

        return _VIEWER_HTML.format(
            viewer_id=f"viewer_{id(structure) & 0xFFFFFF:06x}",
            width=600, height=420,
            bg_color="white",
            xyz=xyz,
            style_js="\n    ".join(style_lines),
            cell_js=cell_js,
            extra_js="",
            legend_html=_build_legend_html(elements),
        )

    # ------------------------------------------------------------------ #
    # Polyhedral mode
    # ------------------------------------------------------------------ #

    def _render_polyhedral(self, structure: Any) -> str:
        """Polyhedral view: coordination polyhedra around metal centres.

        Metal atoms get translucent polyhedra drawn from their nearest
        coordinating anion neighbours. Non-metals are small spheres.
        Falls back to ball-and-stick if neighbour finding fails.
        """
        xyz = _structure_to_xyz(structure)
        cell_js = _unit_cell_lines_js(structure)
        elements: set[str] = set()

        for site in structure.sites:
            elements.add(str(site.specie))

        # Style: metals as medium spheres, non-metals as small spheres
        style_lines = []
        for elem in sorted(elements):
            c = _color_for_element(elem)
            if elem in _METALS:
                r = VDW_RADII.get(elem, 1.5) * 0.30
                style_lines.append(
                    f"viewer.setStyle({{elem:'{elem}'}}, "
                    f"{{sphere: {{radius: {r:.3f}, color:'{c}'}}, "
                    f"stick: {{radius: 0.08, color:'{c}'}}}});"
                )
            else:
                r = VDW_RADII.get(elem, 1.5) * 0.18
                style_lines.append(
                    f"viewer.setStyle({{elem:'{elem}'}}, "
                    f"{{sphere: {{radius: {r:.3f}, color:'{c}'}}}});"
                )

        # Build coordination polyhedra
        polyhedra_js_parts = []
        try:
            for i, site in enumerate(structure.sites):
                elem = str(site.specie)
                if elem not in _METALS:
                    continue

                # Get nearest neighbors within bonding distance
                cov_r = COVALENT_RADII.get(elem, 1.5)
                cutoff = cov_r * 2.8  # generous cutoff for coordination shell
                neighbors = structure.get_neighbors(site, cutoff)

                # Filter to anions/ligands (O, N, F, Cl, S, Se, etc.)
                ligands = []
                for nb in neighbors:
                    nb_elem = str(nb.specie)
                    if nb_elem not in _METALS:
                        ligands.append(nb)

                if len(ligands) < 3:
                    continue  # need at least 3 for a polygon

                # Sort by distance and take coordination shell
                ligands.sort(key=lambda n: n.nn_distance)
                coord_shell = ligands[:min(len(ligands), 8)]  # cap at 8

                # Get Cartesian coordinates of coordinating atoms
                coords = [list(nb.coords) for nb in coord_shell]
                center = list(site.coords)
                c = _color_for_element(elem)

                # Draw triangulated polyhedron faces (center to each edge pair)
                for j in range(len(coords)):
                    k = (j + 1) % len(coords)
                    v1, v2 = coords[j], coords[k]
                    polyhedra_js_parts.append(
                        f"viewer.addCustom({{vertexArr:[{{"
                        f"x:{center[0]:.4f},y:{center[1]:.4f},z:{center[2]:.4f}}},"
                        f"{{x:{v1[0]:.4f},y:{v1[1]:.4f},z:{v1[2]:.4f}}},"
                        f"{{x:{v2[0]:.4f},y:{v2[1]:.4f},z:{v2[2]:.4f}}}],"
                        f"faceArr:[0,1,2],normalArr:[{{x:0,y:0,z:1}},{{x:0,y:0,z:1}},{{x:0,y:0,z:1}}],"
                        f"color:'{c}'}});"
                    )

        except Exception as exc:
            logger.warning("Polyhedral rendering failed, using ball-and-stick: %s", exc)
            return self._render_ball_and_stick(structure)

        # Add surface opacity via custom shapes
        extra_js = "\n    ".join(polyhedra_js_parts) if polyhedra_js_parts else ""

        return _VIEWER_HTML.format(
            viewer_id=f"viewer_{id(structure) & 0xFFFFFF:06x}",
            width=600, height=420,
            bg_color="white",
            xyz=xyz,
            style_js="\n    ".join(style_lines),
            cell_js=cell_js,
            extra_js=extra_js,
            legend_html=_build_legend_html(elements),
        )

    # ------------------------------------------------------------------ #
    # Unit-cell mode (labeled lattice vectors)
    # ------------------------------------------------------------------ #

    def _render_unit_cell(self, structure: Any) -> str:
        """Unit cell: sticks + labeled a/b/c lattice vectors."""
        xyz = _structure_to_xyz(structure)
        cell_js = _unit_cell_labeled_js(structure)
        elements: set[str] = set()

        style_lines = []
        for site in structure.sites:
            elem = str(site.specie)
            elements.add(elem)

        for elem in sorted(elements):
            c = _color_for_element(elem)
            style_lines.append(
                f"viewer.setStyle({{elem:'{elem}'}}, "
                f"{{stick: {{radius: 0.15, color:'{c}'}}, "
                f"sphere: {{radius: 0.3, color:'{c}'}}}});"
            )

        return _VIEWER_HTML.format(
            viewer_id=f"viewer_{id(structure) & 0xFFFFFF:06x}",
            width=600, height=420,
            bg_color="white",
            xyz=xyz,
            style_js="\n    ".join(style_lines),
            cell_js=cell_js,
            extra_js="",
            legend_html=_build_legend_html(elements),
        )

    # ------------------------------------------------------------------ #
    # private — regex CIF → 2D fallback
    # ------------------------------------------------------------------ #

    def _render_cif_regex(self, cif_path: Path) -> str:
        """Best-effort rendering from a CIF file without pymatgen.

        Extracts Cartesian-ish coordinates from fractional + lattice
        parameters found via regex, then draws a 2D projection.
        """
        import re

        try:
            text = cif_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"<p style='color:red;'>Cannot read CIF: {exc}</p>"

        # Lattice parameters
        def _grab(pattern: str) -> float:
            m = re.search(pattern + r"\s+([\d.]+)", text)
            return float(m.group(1)) if m else 5.0

        a = _grab("_cell_length_a")
        b = _grab("_cell_length_b")
        c = _grab("_cell_length_c")

        # Find atom sites (label, type_symbol, frac_x, frac_y, frac_z)
        species: list[str] = []
        coords: list[tuple[float, float, float]] = []

        in_loop = False
        header_cols: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "loop_":
                in_loop = True
                header_cols = []
                continue
            if in_loop and stripped.startswith("_atom_site_"):
                header_cols.append(stripped)
                continue
            if in_loop and header_cols and stripped and not stripped.startswith("_"):
                if stripped.startswith("loop_") or stripped.startswith("data_"):
                    in_loop = False
                    header_cols = []
                    continue
                tokens = stripped.split()
                # need type_symbol and frac_x/y/z
                try:
                    sym_idx = header_cols.index("_atom_site_type_symbol")
                except ValueError:
                    try:
                        sym_idx = header_cols.index("_atom_site_label")
                    except ValueError:
                        continue
                try:
                    fx_idx = header_cols.index("_atom_site_fract_x")
                    fy_idx = header_cols.index("_atom_site_fract_y")
                    fz_idx = header_cols.index("_atom_site_fract_z")
                except ValueError:
                    continue
                if len(tokens) > max(sym_idx, fx_idx, fy_idx, fz_idx):
                    elem = re.sub(r"[^A-Za-z]", "", tokens[sym_idx])
                    fx = float(tokens[fx_idx].split("(")[0])
                    fy = float(tokens[fy_idx].split("(")[0])
                    fz = float(tokens[fz_idx].split("(")[0])
                    # crude Cartesian approximation (orthorhombic)
                    species.append(elem)
                    coords.append((fx * a, fy * b, fz * c))

        if not species:
            return "<p style='color:red;'>Could not extract atom positions from CIF (no pymatgen).</p>"

        return _render_2d_projection(species, coords, title=f"{cif_path.stem} — XY projection")
