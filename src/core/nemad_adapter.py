"""
OAE NEMAD Adapter — Wraps NEMAD-MagneticML CSV datasets into MaterialEntry format.

Provides access to 58K+ magnetic material entries:
  - FM_with_curie.csv:  ~15,577 ferromagnetic compounds with Curie temperature
  - AFM_with_Neel.csv:  ~7,893 antiferromagnetic compounds with Neel temperature
  - Classification_FM_AFM_NM.csv: ~35,037 compounds classified as FM/AFM/NM
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False

from src.core.config import NEMAD_DATASET_DIR


# Element symbols from the NEMAD CSV column headers (H through Pu)
_ELEMENT_COLUMNS = [
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu",
]


def _formula_to_readable(norm_comp: str) -> str:
    """Convert NEMAD normalised composition to readable formula.

    E.g. 'Fe3.0O4.0' -> 'Fe3O4'
    """
    if not isinstance(norm_comp, str):
        return str(norm_comp)
    return re.sub(r"\.0(?=[A-Z]|$)", "", norm_comp)


def _extract_elements(norm_comp: str) -> list[str]:
    """Extract element symbols from a normalised composition string."""
    return re.findall(r"[A-Z][a-z]?", str(norm_comp))


class NemadAdapter:
    """Adapter to load NEMAD datasets as OAE material entry dicts."""

    def __init__(self, dataset_dir: Optional[Path] = None):
        self._dir = dataset_dir or NEMAD_DATASET_DIR
        self._fm_cache: Optional[list[dict]] = None
        self._afm_cache: Optional[list[dict]] = None
        self._cls_cache: Optional[list[dict]] = None

    # ------------------------------------------------------------------
    # Public loaders
    # ------------------------------------------------------------------

    def load_fm_curie(self) -> list[dict]:
        """Load ferromagnetic compounds with Curie temperature."""
        if self._fm_cache is not None:
            return self._fm_cache
        self._fm_cache = self._load_csv(
            self._dir / "FM_with_curie.csv",
            material_type="magnetic",
            magnetic_class="FM",
            temp_column="Mean_TC_K",
            temp_label="curie_temp_K",
        )
        return self._fm_cache

    def load_afm_neel(self) -> list[dict]:
        """Load antiferromagnetic compounds with Neel temperature."""
        if self._afm_cache is not None:
            return self._afm_cache
        self._afm_cache = self._load_csv(
            self._dir / "AFM_with_Neel.csv",
            material_type="magnetic",
            magnetic_class="AFM",
            temp_column="Mean_TN_K",
            temp_label="neel_temp_K",
        )
        return self._afm_cache

    def load_classification(self) -> list[dict]:
        """Load FM/AFM/NM classification dataset."""
        if self._cls_cache is not None:
            return self._cls_cache
        self._cls_cache = self._load_classification_csv(
            self._dir / "Classification_FM_AFM_NM.csv",
        )
        return self._cls_cache

    def load_all(self) -> list[dict]:
        """Load and merge all NEMAD entries (deduplicated by composition)."""
        seen: set[str] = set()
        combined: list[dict] = []
        for entries in [self.load_fm_curie(), self.load_afm_neel(), self.load_classification()]:
            for e in entries:
                comp = e.get("composition", "")
                if comp not in seen:
                    seen.add(comp)
                    combined.append(e)
        return combined

    def count(self) -> dict[str, int]:
        """Return counts for each dataset (without loading full data)."""
        counts = {}
        for name, fname in [
            ("fm_curie", "FM_with_curie.csv"),
            ("afm_neel", "AFM_with_Neel.csv"),
            ("classification", "Classification_FM_AFM_NM.csv"),
        ]:
            p = self._dir / fname
            if p.exists():
                try:
                    with open(p) as f:
                        counts[name] = sum(1 for _ in f) - 1  # subtract header
                except Exception:
                    counts[name] = 0
            else:
                counts[name] = 0
        return counts

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_csv(
        self,
        path: Path,
        material_type: str,
        magnetic_class: str,
        temp_column: str,
        temp_label: str,
    ) -> list[dict]:
        if not path.exists():
            logger.warning("NEMAD file not found: %s", path)
            return []

        if not _PANDAS:
            logger.warning("pandas not available — NEMAD adapter disabled")
            return []

        try:
            df = pd.read_csv(path)
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)
            return []

        entries: list[dict] = []
        for _, row in df.iterrows():
            comp = _formula_to_readable(row.get("Normalized_Composition", ""))
            elements = _extract_elements(comp)
            elem_fractions = {}
            for el in _ELEMENT_COLUMNS:
                val = row.get(el, 0.0)
                if isinstance(val, (int, float)) and val > 0:
                    elem_fractions[el] = float(val)

            entry = {
                "material_id": f"nemad-{magnetic_class.lower()}-{len(entries):05d}",
                "material_type": material_type,
                "composition": comp,
                "source": "nemad",
                "properties": {
                    temp_label: float(row.get(temp_column, 0.0)),
                    "magnetic_class": magnetic_class,
                    "element_fractions": elem_fractions,
                },
                "tags": [f"nemad-{magnetic_class.lower()}", "magnetic"],
                "data_paths": {},
            }
            entries.append(entry)

        logger.info("Loaded %d %s entries from NEMAD", len(entries), magnetic_class)
        return entries

    def _load_classification_csv(self, path: Path) -> list[dict]:
        if not path.exists():
            logger.warning("NEMAD classification file not found: %s", path)
            return []

        if not _PANDAS:
            logger.warning("pandas not available — NEMAD adapter disabled")
            return []

        try:
            df = pd.read_csv(path)
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)
            return []

        type_map = {0: "AFM", 1: "FM", 2: "NM"}
        entries: list[dict] = []
        for _, row in df.iterrows():
            comp = _formula_to_readable(row.get("Normalized_Composition", ""))
            cls_val = row.get("Type", 2)
            magnetic_class = type_map.get(int(cls_val), "NM")

            entry = {
                "material_id": f"nemad-cls-{len(entries):05d}",
                "material_type": "magnetic" if magnetic_class != "NM" else "general",
                "composition": comp,
                "source": "nemad",
                "properties": {
                    "magnetic_class": magnetic_class,
                    "type_code": int(cls_val),
                },
                "tags": [f"nemad-{magnetic_class.lower()}", "classification"],
                "data_paths": {},
            }
            entries.append(entry)

        logger.info("Loaded %d classification entries from NEMAD", len(entries))
        return entries


def get_default_adapter() -> NemadAdapter:
    """Factory returning a NemadAdapter with default dataset directory."""
    return NemadAdapter()
