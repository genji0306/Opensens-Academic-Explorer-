"""
CIF file generator for Agent V.

Generates Crystallographic Information Files from pymatgen Structure objects,
crystal-card dictionaries (Agent CB output), or raw lattice parameters.
Falls back to manual CIF string construction when pymatgen is unavailable.
"""

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentV.CIF.Generator")

# ---------------------------------------------------------------------------
# Optional pymatgen import
# ---------------------------------------------------------------------------
try:
    from pymatgen.core import Structure, Lattice
    from pymatgen.io.cif import CifWriter

    _PYMATGEN = True
except ImportError:
    try:
        from pymatgen import Structure, Lattice
        from pymatgen.io.cif import CifWriter

        _PYMATGEN = True
    except ImportError:
        _PYMATGEN = False
        logger.info("pymatgen not installed — CIF generation will use manual fallback.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deg(rad: float) -> float:
    """Radians to degrees."""
    return rad * 180.0 / math.pi


def _rad(deg: float) -> float:
    """Degrees to radians."""
    return deg * math.pi / 180.0


def compute_volume(
    a: float, b: float, c: float,
    alpha: float, beta: float, gamma: float,
) -> float:
    """Compute the unit-cell volume from lattice parameters.

    Parameters
    ----------
    a, b, c : float
        Lattice lengths in angstroms.
    alpha, beta, gamma : float
        Lattice angles in **degrees**.

    Returns
    -------
    float
        Volume in cubic angstroms.
    """
    ca = math.cos(_rad(alpha))
    cb = math.cos(_rad(beta))
    cg = math.cos(_rad(gamma))
    volume = a * b * c * math.sqrt(
        1.0 - ca ** 2 - cb ** 2 - cg ** 2 + 2.0 * ca * cb * cg
    )
    return abs(volume)


# ---------------------------------------------------------------------------
# CIF string builder (manual fallback)
# ---------------------------------------------------------------------------

def _get_symmetry_operations(space_group: str, space_group_number: int = 0) -> list[str]:
    """Get symmetry-equivalent position strings for a space group.

    Tries symbol-based lookup first, falls back to number-based, then identity.

    Returns
    -------
    list[str]
        XYZ strings like ``'x, y, z'``, ``'-x, -y, z'``, etc.
    """
    if not _PYMATGEN:
        return ["x, y, z"]

    try:
        from pymatgen.symmetry.groups import SpaceGroup
        # Prefer symbol lookup (works for all our space groups)
        if space_group and space_group != "P 1":
            sg = SpaceGroup(space_group)
        elif space_group_number > 1:
            sg = SpaceGroup.from_int_number(space_group_number)
        else:
            return ["x, y, z"]
        return [op.as_xyz_str() for op in sg.symmetry_ops]
    except Exception as exc:
        logger.debug("Could not generate symmetry ops for %s: %s", space_group, exc)
        return ["x, y, z"]


def _resolve_space_group_number(space_group: str) -> int:
    """Resolve a Hermann-Mauguin symbol to an International Tables number."""
    if not _PYMATGEN:
        return 1
    try:
        from pymatgen.symmetry.groups import SpaceGroup
        return SpaceGroup(space_group).int_number
    except Exception:
        return 1


def _manual_cif_string(
    lattice_params: dict[str, float],
    species: list[str],
    frac_coords: list[tuple[float, float, float]],
    structure_id: str = "",
    space_group: str = "P 1",
    space_group_number: int = 1,
    properties: Optional[dict[str, Any]] = None,
    wyckoff_labels: Optional[list[str]] = None,
    occupancies: Optional[list[float]] = None,
    bond_lengths: Optional[dict[str, float]] = None,
    composition: Optional[str] = None,
    include_symmetry_ops: bool = True,
) -> str:
    """Build an enhanced CIF string with symmetry ops, Wyckoff labels, and bonds.

    Parameters
    ----------
    lattice_params : dict
        Keys ``a, b, c, alpha, beta, gamma``.
    species : list[str]
        Element symbols per site.
    frac_coords : list[tuple]
        Fractional coordinates per site, each (x, y, z).
    structure_id : str
        Optional block name.
    space_group : str
        Hermann-Mauguin symbol, default ``"P 1"``.
    space_group_number : int
        International Tables number, default 1.
    properties : dict or None
        Extra key-value pairs written as CIF comments.
    wyckoff_labels : list[str] or None
        Wyckoff position labels per site (e.g. ``["4d", "4e", "2a"]``).
    occupancies : list[float] or None
        Site occupancy factors per site.
    bond_lengths : dict or None
        Bond pair to distance mapping (e.g. ``{"Fe-As": 2.391}``).
    composition : str or None
        Chemical formula string.
    include_symmetry_ops : bool
        If True, generate ``_symmetry_equiv_pos_as_xyz`` loop.

    Returns
    -------
    str
        CIF-formatted text.
    """
    block_name = structure_id or "agent_v_structure"
    a = lattice_params["a"]
    b = lattice_params["b"]
    c = lattice_params["c"]
    alpha = lattice_params["alpha"]
    beta = lattice_params["beta"]
    gamma = lattice_params["gamma"]
    vol = compute_volume(a, b, c, alpha, beta, gamma)

    lines: list[str] = []
    lines.append(f"data_{block_name}")
    lines.append(f"_audit_creation_date   '{datetime.now(timezone.utc).strftime('%Y-%m-%d')}'")
    lines.append("_audit_creation_method  'OAE Agent V — CIF Generator v2'")
    lines.append("")

    # Properties as comments
    if properties:
        for k, v in properties.items():
            lines.append(f"# {k}: {v}")
        lines.append("")

    # Chemical formula
    if composition:
        lines.append(f"_chemical_formula_sum   '{composition}'")
        lines.append("")

    lines.append(f"_cell_length_a    {a:.6f}")
    lines.append(f"_cell_length_b    {b:.6f}")
    lines.append(f"_cell_length_c    {c:.6f}")
    lines.append(f"_cell_angle_alpha {alpha:.4f}")
    lines.append(f"_cell_angle_beta  {beta:.4f}")
    lines.append(f"_cell_angle_gamma {gamma:.4f}")
    lines.append(f"_cell_volume      {vol:.4f}")
    lines.append("")
    lines.append(f"_symmetry_space_group_name_H-M   '{space_group}'")
    lines.append(f"_symmetry_Int_Tables_number       {space_group_number}")
    lines.append("")

    # Symmetry operations loop
    if include_symmetry_ops:
        sym_ops = _get_symmetry_operations(space_group, space_group_number)
        if sym_ops:
            lines.append("loop_")
            lines.append("_symmetry_equiv_pos_site_id")
            lines.append("_symmetry_equiv_pos_as_xyz")
            for idx, op in enumerate(sym_ops, 1):
                lines.append(f"  {idx}  '{op}'")
            lines.append("")

    # Atom site loop with occupancy and Wyckoff
    lines.append("loop_")
    lines.append("_atom_site_label")
    lines.append("_atom_site_type_symbol")
    lines.append("_atom_site_fract_x")
    lines.append("_atom_site_fract_y")
    lines.append("_atom_site_fract_z")
    lines.append("_atom_site_occupancy")
    if wyckoff_labels:
        lines.append("_atom_site_Wyckoff_symbol")

    label_counts: dict[str, int] = {}
    for i, (sp, (fx, fy, fz)) in enumerate(zip(species, frac_coords)):
        label_counts[sp] = label_counts.get(sp, 0) + 1
        wl = wyckoff_labels[i] if wyckoff_labels and i < len(wyckoff_labels) else ""
        label = f"{sp}{wl}" if wl else f"{sp}{label_counts[sp]}"
        occ = occupancies[i] if occupancies and i < len(occupancies) else 1.00
        line = f"  {label:<8s} {sp:<4s} {fx:10.6f} {fy:10.6f} {fz:10.6f}  {occ:.2f}"
        if wyckoff_labels:
            line += f"  {wl}"
        lines.append(line)

    lines.append("")

    # Bond geometry loop
    if bond_lengths:
        lines.append("loop_")
        lines.append("_geom_bond_atom_site_label_1")
        lines.append("_geom_bond_atom_site_label_2")
        lines.append("_geom_bond_distance")
        for pair, dist in sorted(bond_lengths.items()):
            atoms = pair.split("-")
            if len(atoms) == 2:
                lines.append(f"  {atoms[0]:<6s} {atoms[1]:<6s} {dist:.4f}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CIFGenerator:
    """Generate CIF files from various crystal-structure representations."""

    # ---- from pymatgen Structure ----

    @staticmethod
    def from_pymatgen_structure(
        structure: Any,
        structure_id: str = "",
        properties: Optional[dict[str, Any]] = None,
    ) -> str:
        """Convert a *pymatgen* ``Structure`` to a CIF string.

        If pymatgen's ``CifWriter`` is available it is used directly.
        Otherwise, the structure's lattice and sites are extracted and the
        manual builder is invoked.

        Parameters
        ----------
        structure :
            A ``pymatgen.core.Structure`` instance.
        structure_id : str
            Block name written into the CIF header.
        properties : dict | None
            Arbitrary metadata to embed as CIF comments.

        Returns
        -------
        str
            Complete CIF file content.
        """
        if _PYMATGEN:
            try:
                writer = CifWriter(structure)
                cif_text = str(writer)
                # Prepend property comments if provided
                if properties:
                    header_lines = [f"# {k}: {v}" for k, v in properties.items()]
                    cif_text = "\n".join(header_lines) + "\n" + cif_text
                return cif_text
            except Exception as exc:
                logger.warning("CifWriter failed (%s), using manual fallback", exc)

        # Manual fallback — works even without pymatgen if the caller passes
        # a duck-typed object with .lattice and .sites.
        try:
            lat = structure.lattice
            lattice_params = {
                "a": lat.a, "b": lat.b, "c": lat.c,
                "alpha": lat.alpha, "beta": lat.beta, "gamma": lat.gamma,
            }
            species = [str(site.specie) for site in structure.sites]
            frac_coords = [tuple(site.frac_coords) for site in structure.sites]
            sg = getattr(structure, "get_space_group_info", lambda: ("P 1", 1))()
            sg_symbol = sg[0] if isinstance(sg, tuple) else "P 1"
            sg_number = sg[1] if isinstance(sg, tuple) and len(sg) > 1 else 1
        except Exception as exc:
            logger.error("Cannot extract lattice/sites from structure: %s", exc)
            return ""

        return _manual_cif_string(
            lattice_params, species, frac_coords,
            structure_id=structure_id,
            space_group=sg_symbol,
            space_group_number=sg_number,
            properties=properties,
        )

    # ---- from Agent CB crystal card ----

    @staticmethod
    def from_crystal_card(card_dict: dict[str, Any], enhanced: bool = True) -> str:
        """Build CIF text from an Agent CB *crystal card* dictionary.

        Expected keys (all optional with defaults):

        - ``formula`` or ``composition`` : str
        - ``lattice`` or ``lattice_params`` : dict with a, b, c, alpha, beta, gamma
        - ``space_group`` : str  (e.g. ``"Fm-3m"``)
        - ``space_group_number`` : int
        - ``sites`` : list[dict] each with ``element``, ``x``, ``y``, ``z``,
          optionally ``label`` (Wyckoff) and ``occupancy``
        - ``bond_lengths`` : dict (e.g. ``{"Fe-As": 2.391}``)
        - ``properties`` : dict of arbitrary metadata

        Parameters
        ----------
        card_dict : dict
            Crystal card data.
        enhanced : bool
            If True (default), include symmetry operations, Wyckoff labels,
            occupancies, bond geometry, and composition in the CIF output.

        Returns
        -------
        str
            CIF string, or empty string on failure.
        """
        try:
            lattice_raw = card_dict.get("lattice", card_dict.get("lattice_params", {}))
            lattice_params = {
                "a":     float(lattice_raw.get("a", 5.0)),
                "b":     float(lattice_raw.get("b", 5.0)),
                "c":     float(lattice_raw.get("c", 5.0)),
                "alpha": float(lattice_raw.get("alpha", 90.0)),
                "beta":  float(lattice_raw.get("beta", 90.0)),
                "gamma": float(lattice_raw.get("gamma", 90.0)),
            }

            sites = card_dict.get("sites", [])
            species = [s.get("element", "X") for s in sites]
            frac_coords = [
                (float(s.get("x", 0.0)),
                 float(s.get("y", 0.0)),
                 float(s.get("z", 0.0)))
                for s in sites
            ]

            sg_symbol = card_dict.get("space_group", "P 1")
            sg_number = int(card_dict.get("space_group_number", 1))
            sid = card_dict.get("candidate_id",
                                card_dict.get("formula", "crystal_card"))
            props = card_dict.get("properties", None)

            # Extract enhanced data from crystal card
            composition = card_dict.get("composition",
                                        card_dict.get("formula", None))
            wyckoff_labels = [s.get("label", "") for s in sites] if enhanced else None
            occupancies = [float(s.get("occupancy", 1.0)) for s in sites] if enhanced else None
            bond_lengths = card_dict.get("bond_lengths", None) if enhanced else None

            # If pymatgen is available, build a proper Structure first
            if _PYMATGEN and species and frac_coords:
                try:
                    lat = Lattice.from_parameters(**lattice_params)
                    struct = Structure(lat, species, frac_coords)
                    return CIFGenerator.from_pymatgen_structure(
                        struct, structure_id=sid, properties=props
                    )
                except Exception as exc:
                    logger.warning(
                        "pymatgen Structure from card failed (%s), using manual builder",
                        exc,
                    )

            return _manual_cif_string(
                lattice_params, species, frac_coords,
                structure_id=sid,
                space_group=sg_symbol,
                space_group_number=sg_number,
                properties=props,
                wyckoff_labels=wyckoff_labels,
                occupancies=occupancies,
                bond_lengths=bond_lengths,
                composition=composition,
                include_symmetry_ops=enhanced,
            )
        except Exception as exc:
            logger.error("from_crystal_card failed: %s", exc)
            return ""

    # ---- Batch enhance existing CIF files ----

    @staticmethod
    def enhance_from_crystal_card(
        cif_path: Path | str,
        card_dict: dict[str, Any],
    ) -> str:
        """Re-generate an enhanced CIF from a crystal card, preserving the
        original structure ID and predicted properties.

        Parameters
        ----------
        cif_path : Path or str
            Path to the original CIF file (used for structure ID extraction).
        card_dict : dict
            Crystal card JSON data.

        Returns
        -------
        str
            Enhanced CIF string.
        """
        cif_path = Path(cif_path)
        # Extract structure ID from existing CIF filename or card
        sid = card_dict.get("candidate_id", cif_path.parent.name)

        lattice_raw = card_dict.get("lattice_params", card_dict.get("lattice", {}))
        lattice_params = {
            "a":     float(lattice_raw.get("a", 5.0)),
            "b":     float(lattice_raw.get("b", 5.0)),
            "c":     float(lattice_raw.get("c", 5.0)),
            "alpha": float(lattice_raw.get("alpha", 90.0)),
            "beta":  float(lattice_raw.get("beta", 90.0)),
            "gamma": float(lattice_raw.get("gamma", 90.0)),
        }

        sites = card_dict.get("sites", [])
        species = [s.get("element", "X") for s in sites]
        frac_coords = [
            (float(s.get("x", 0.0)),
             float(s.get("y", 0.0)),
             float(s.get("z", 0.0)))
            for s in sites
        ]
        wyckoff_labels = [s.get("label", "") for s in sites]
        occupancies = [float(s.get("occupancy", 1.0)) for s in sites]

        sg_symbol = card_dict.get("space_group", "P 1")
        sg_number = int(card_dict.get("space_group_number", 0))
        if sg_number == 0:
            sg_number = _resolve_space_group_number(sg_symbol)
        composition = card_dict.get("composition", None)
        bond_lengths = card_dict.get("bond_lengths", None)

        # Build properties from predicted Tc
        props = {}
        if "predicted_Tc_K" in card_dict:
            props["predicted_Tc_K"] = card_dict["predicted_Tc_K"]
        if "pressure_GPa" in card_dict:
            props["pressure_GPa"] = card_dict["pressure_GPa"]

        return _manual_cif_string(
            lattice_params, species, frac_coords,
            structure_id=sid,
            space_group=sg_symbol,
            space_group_number=sg_number,
            properties=props if props else None,
            wyckoff_labels=wyckoff_labels,
            occupancies=occupancies,
            bond_lengths=bond_lengths,
            composition=composition,
            include_symmetry_ops=True,
        )

    # ---- Validation ----

    @staticmethod
    def validate_cif(cif_string: str) -> tuple[bool, list[str]]:
        """Run basic validation checks on a CIF string.

        Returns
        -------
        (bool, list[str])
            ``(is_valid, list_of_error_messages)``.
        """
        errors: list[str] = []

        if not cif_string or not cif_string.strip():
            errors.append("CIF string is empty.")
            return False, errors

        has_data_block = False
        has_cell_a = False
        has_atom_site = False

        for line in cif_string.splitlines():
            stripped = line.strip()
            if stripped.startswith("data_"):
                has_data_block = True
            if stripped.startswith("_cell_length_a"):
                has_cell_a = True
            if stripped.startswith("_atom_site_"):
                has_atom_site = True

        if not has_data_block:
            errors.append("Missing data_ block header.")
        if not has_cell_a:
            errors.append("Missing _cell_length_a — lattice parameters absent.")
        if not has_atom_site:
            errors.append("No _atom_site_ entries found — no atomic positions.")

        # If pymatgen available, try a round-trip parse
        if _PYMATGEN and not errors:
            import tempfile
            import os
            tmp_path = None
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".cif")
                os.close(fd)
                with open(tmp_path, "w") as fh:
                    fh.write(cif_string)
                from pymatgen.io.cif import CifParser
                parser = CifParser(tmp_path)
                structures = parser.get_structures()
                if not structures:
                    errors.append("pymatgen could not parse any structures from CIF.")
            except Exception as exc:
                errors.append(f"pymatgen round-trip parse failed: {exc}")
            finally:
                if tmp_path and Path(tmp_path).exists():
                    Path(tmp_path).unlink()

        is_valid = len(errors) == 0
        return is_valid, errors

    # ---- Write to disk ----

    @staticmethod
    def write(cif_string: str, path: Path | str) -> Path:
        """Write a CIF string to *path*, creating parent directories.

        Returns
        -------
        Path
            The resolved path that was written.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cif_string, encoding="utf-8")
        logger.info("CIF written to %s (%d bytes)", path, len(cif_string))
        return path.resolve()
