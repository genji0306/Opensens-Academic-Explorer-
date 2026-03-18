"""CIF I/O utilities — read/write crystal structures via pymatgen."""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AgentPB.IO.CIF")

try:
    from pymatgen.core import Structure
    from pymatgen.io.cif import CifParser, CifWriter
    _PYMATGEN_AVAILABLE = True
except ImportError:
    try:
        from pymatgen import Structure
        from pymatgen.io.cif import CifParser, CifWriter
        _PYMATGEN_AVAILABLE = True
    except ImportError:
        _PYMATGEN_AVAILABLE = False
        logger.warning("pymatgen not installed. CIF I/O unavailable.")


def read_cif(path: Path) -> Optional["Structure"]:
    """Read CIF file to pymatgen Structure.

    Returns None on failure.
    """
    if not _PYMATGEN_AVAILABLE:
        raise ImportError("pymatgen is required for CIF reading.")
    try:
        parser = CifParser(str(path))
        structures = parser.get_structures()
        return structures[0] if structures else None
    except Exception as e:
        logger.error(f"Failed to read CIF {path}: {e}")
        return None


def write_cif(structure, path: Path, comment: str = "") -> Path:
    """Write pymatgen Structure to CIF file.

    Returns the path written to.
    """
    if not _PYMATGEN_AVAILABLE:
        raise ImportError("pymatgen is required for CIF writing.")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        writer = CifWriter(structure)
        writer.write_file(str(path))
        logger.info(f"CIF written to {path}")
    except Exception:
        # Fallback: use Structure.to() method
        structure.to(filename=str(path))
        logger.info(f"CIF written via Structure.to() to {path}")

    return path


def structure_to_cif_string(structure, structure_id: str = "",
                            properties: dict = None) -> str:
    """Convert pymatgen Structure to CIF format string."""
    if not _PYMATGEN_AVAILABLE:
        raise ImportError("pymatgen is required for CIF generation.")

    try:
        writer = CifWriter(structure)
        return str(writer)
    except Exception as e:
        logger.error(f"CIF string generation failed: {e}")
        return ""
