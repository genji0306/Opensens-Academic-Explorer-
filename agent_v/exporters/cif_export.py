"""
CIF export helper for Agent V.

Thin convenience wrapper around ``CIFGenerator`` that writes a pymatgen
Structure (or compatible duck-typed object) to a ``.cif`` file in the
project exports directory.
"""

import logging
from pathlib import Path
from typing import Any, Optional

from agent_v.cif.generator import CIFGenerator
from agent_v.config import EXPORTS_DIR

logger = logging.getLogger("AgentV.Exporters.CIF")


def export_cif(
    structure: Any,
    output_dir: Optional[Path | str] = None,
    filename: Optional[str] = None,
) -> Path:
    """Export a crystal structure to a CIF file.

    Parameters
    ----------
    structure :
        A ``pymatgen.core.Structure`` or any object accepted by
        ``CIFGenerator.from_pymatgen_structure``.
    output_dir : Path | str | None
        Directory for the output file.  Defaults to
        ``data/exports/``.
    filename : str | None
        Output filename (including ``.cif`` extension).  When ``None``
        a name is derived from the structure's reduced formula.

    Returns
    -------
    Path
        Resolved path to the written CIF file.

    Raises
    ------
    ValueError
        If the CIF string is empty (structure could not be serialised).
    """
    out_dir = Path(output_dir) if output_dir else EXPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Derive a sensible filename
    if filename is None:
        try:
            formula = structure.composition.reduced_formula
        except Exception:
            formula = "structure"
        # Sanitise for filesystem
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in formula)
        filename = f"{safe}.cif"

    cif_string = CIFGenerator.from_pymatgen_structure(structure)
    if not cif_string.strip():
        raise ValueError("CIFGenerator produced an empty CIF string — export aborted.")

    out_path = CIFGenerator.write(cif_string, out_dir / filename)
    logger.info("Exported CIF: %s", out_path)
    return out_path
