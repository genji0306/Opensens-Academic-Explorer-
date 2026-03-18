"""
CIF file parser / validator for Agent V.

Wraps pymatgen's ``CifParser`` with graceful fallback when pymatgen is
not installed.  Provides validation, metadata extraction, and conversion
to ``pymatgen.core.Structure``.
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentV.CIF.Parser")

# ---------------------------------------------------------------------------
# Optional pymatgen
# ---------------------------------------------------------------------------
try:
    from pymatgen.core import Structure
    from pymatgen.io.cif import CifParser as _PmgCifParser

    _PYMATGEN = True
except ImportError:
    try:
        from pymatgen import Structure
        from pymatgen.io.cif import CifParser as _PmgCifParser

        _PYMATGEN = True
    except ImportError:
        _PYMATGEN = False
        Structure = None  # type: ignore[assignment,misc]
        logger.info("pymatgen not installed — CIF parsing limited to regex fallback.")


# ---------------------------------------------------------------------------
# Regex helpers for the manual fallback
# ---------------------------------------------------------------------------
_RE_CELL_A = re.compile(r"_cell_length_a\s+([\d.]+)")
_RE_CELL_B = re.compile(r"_cell_length_b\s+([\d.]+)")
_RE_CELL_C = re.compile(r"_cell_length_c\s+([\d.]+)")
_RE_ALPHA  = re.compile(r"_cell_angle_alpha\s+([\d.]+)")
_RE_BETA   = re.compile(r"_cell_angle_beta\s+([\d.]+)")
_RE_GAMMA  = re.compile(r"_cell_angle_gamma\s+([\d.]+)")
_RE_SG_HM  = re.compile(r"_symmetry_space_group_name_H-M\s+'([^']+)'")
_RE_SG_NUM = re.compile(r"_symmetry_Int_Tables_number\s+(\d+)")
_RE_DATA   = re.compile(r"^data_(.+)", re.MULTILINE)


def _safe_float(text: str) -> Optional[float]:
    """Parse a CIF numeric field, stripping parenthetical uncertainties."""
    try:
        cleaned = text.split("(")[0].strip()
        return float(cleaned)
    except (ValueError, IndexError):
        return None


def _extract_composition_from_sites(cif_text: str) -> str:
    """Crude composition string extracted by counting element occurrences
    in the ``_atom_site_type_symbol`` column."""
    counts: dict[str, int] = {}
    in_loop = False
    type_symbol_col: Optional[int] = None
    col_index = 0

    for line in cif_text.splitlines():
        stripped = line.strip()

        if stripped == "loop_":
            in_loop = True
            type_symbol_col = None
            col_index = 0
            continue

        if in_loop and stripped.startswith("_atom_site_"):
            if stripped == "_atom_site_type_symbol":
                type_symbol_col = col_index
            col_index += 1
            continue

        if in_loop and type_symbol_col is not None and stripped and not stripped.startswith("_"):
            if stripped.startswith("loop_") or stripped.startswith("data_"):
                in_loop = False
                continue
            tokens = stripped.split()
            if len(tokens) > type_symbol_col:
                elem = tokens[type_symbol_col]
                # Strip trailing charge like Fe3+
                elem_clean = re.sub(r"[^A-Za-z]", "", elem)
                if elem_clean:
                    counts[elem_clean] = counts.get(elem_clean, 0) + 1

    if not counts:
        return "Unknown"
    parts = []
    for elem in sorted(counts):
        n = counts[elem]
        parts.append(f"{elem}{n}" if n > 1 else elem)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CIFValidator:
    """Parse, validate, and extract metadata from CIF files."""

    # ------------------------------------------------------------------ #
    # validate
    # ------------------------------------------------------------------ #

    @staticmethod
    def validate(path: Path | str) -> tuple[bool, list[str]]:
        """Validate a CIF file on disk.

        Parameters
        ----------
        path : Path or str
            Path to a ``.cif`` file.

        Returns
        -------
        (bool, list[str])
            ``(is_valid, error_messages)``.
        """
        path = Path(path)
        errors: list[str] = []

        if not path.exists():
            errors.append(f"File not found: {path}")
            return False, errors

        if not path.is_file():
            errors.append(f"Not a regular file: {path}")
            return False, errors

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            errors.append(f"Cannot read file: {exc}")
            return False, errors

        if not text.strip():
            errors.append("File is empty.")
            return False, errors

        # Structural checks
        if not _RE_DATA.search(text):
            errors.append("Missing data_ block header.")
        if not _RE_CELL_A.search(text):
            errors.append("Missing _cell_length_a (lattice undefined).")
        if "_atom_site_" not in text:
            errors.append("No _atom_site_ entries (no atomic positions).")

        # pymatgen deep validation
        if _PYMATGEN and not errors:
            try:
                parser = _PmgCifParser(str(path))
                structures = parser.get_structures()
                if not structures:
                    errors.append("pymatgen parsed zero structures from CIF.")
            except Exception as exc:
                errors.append(f"pymatgen parse error: {exc}")

        return len(errors) == 0, errors

    # ------------------------------------------------------------------ #
    # parse_to_structure
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse_to_structure(path: Path | str) -> Optional[Any]:
        """Parse a CIF file into a ``pymatgen.core.Structure``.

        Returns ``None`` when pymatgen is unavailable or the file cannot
        be parsed.
        """
        path = Path(path)
        if not _PYMATGEN:
            logger.error("pymatgen is required for parse_to_structure.")
            return None

        if not path.exists():
            logger.error("CIF file not found: %s", path)
            return None

        try:
            parser = _PmgCifParser(str(path))
            structures = parser.get_structures()
            if structures:
                logger.info(
                    "Parsed structure from %s: %s (%d sites)",
                    path.name,
                    structures[0].composition.reduced_formula,
                    len(structures[0]),
                )
                return structures[0]
            logger.warning("No structures parsed from %s", path)
            return None
        except Exception as exc:
            logger.error("Failed to parse %s: %s", path, exc)
            return None

    # ------------------------------------------------------------------ #
    # extract_metadata
    # ------------------------------------------------------------------ #

    @staticmethod
    def extract_metadata(path: Path | str) -> dict[str, Any]:
        """Extract lightweight metadata from a CIF without building a
        full ``Structure``.

        Returns a dict with keys:
            ``space_group``, ``space_group_number``, ``composition``,
            ``lattice`` (sub-dict with a, b, c, alpha, beta, gamma),
            ``source_file``.
        Falls back to regex parsing when pymatgen is unavailable.
        """
        path = Path(path)
        meta: dict[str, Any] = {
            "source_file": str(path),
            "space_group": None,
            "space_group_number": None,
            "composition": None,
            "lattice": {
                "a": None, "b": None, "c": None,
                "alpha": None, "beta": None, "gamma": None,
            },
        }

        if not path.exists():
            logger.warning("CIF file not found for metadata: %s", path)
            return meta

        # --- Try pymatgen first (most reliable) ---
        if _PYMATGEN:
            try:
                parser = _PmgCifParser(str(path))
                structures = parser.get_structures()
                if structures:
                    s = structures[0]
                    lat = s.lattice
                    meta["lattice"] = {
                        "a": round(lat.a, 6),
                        "b": round(lat.b, 6),
                        "c": round(lat.c, 6),
                        "alpha": round(lat.alpha, 4),
                        "beta": round(lat.beta, 4),
                        "gamma": round(lat.gamma, 4),
                    }
                    meta["composition"] = s.composition.reduced_formula
                    try:
                        sg_info = s.get_space_group_info()
                        meta["space_group"] = sg_info[0]
                        meta["space_group_number"] = sg_info[1]
                    except Exception:
                        pass
                    return meta
            except Exception as exc:
                logger.debug("pymatgen metadata extraction failed (%s), using regex", exc)

        # --- Regex fallback ---
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return meta

        for pattern, key in [
            (_RE_CELL_A, "a"), (_RE_CELL_B, "b"), (_RE_CELL_C, "c"),
            (_RE_ALPHA, "alpha"), (_RE_BETA, "beta"), (_RE_GAMMA, "gamma"),
        ]:
            m = pattern.search(text)
            if m:
                meta["lattice"][key] = _safe_float(m.group(1))

        m = _RE_SG_HM.search(text)
        if m:
            meta["space_group"] = m.group(1).strip()

        m = _RE_SG_NUM.search(text)
        if m:
            meta["space_group_number"] = int(m.group(1))

        meta["composition"] = _extract_composition_from_sites(text)

        return meta
