"""Crystallographic symmetry constraints — Wyckoff positions and space groups."""
import sys
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from agent_pb.config import LEGACY_PB_ROOT, WYCKOFF_DIR

logger = logging.getLogger("AgentPB.Constraints.Symmetry")

# Import legacy Wyckoff utilities
_legacy_path = str(LEGACY_PB_ROOT)
if _legacy_path not in sys.path:
    sys.path.insert(0, _legacy_path)

try:
    from utils.wyckoff_position.get_wyckoff_position import get_all_wyckoff_combination
    _WYCKOFF_AVAILABLE = True
except ImportError:
    _WYCKOFF_AVAILABLE = False
    logger.warning("Legacy Wyckoff utilities not found. Symmetry constraints limited.")

try:
    from pymatgen.core import Structure, Lattice
except ImportError:
    try:
        from pymatgen import Structure, Lattice
    except ImportError:
        Structure = None
        Lattice = None
        logger.warning("pymatgen not installed. Structure building unavailable.")


# Crystal system -> space group number ranges
CRYSTAL_SYSTEMS = {
    "triclinic": (1, 2),
    "monoclinic": (3, 15),
    "orthorhombic": (16, 74),
    "tetragonal": (75, 142),
    "trigonal": (143, 167),
    "hexagonal": (168, 194),
    "cubic": (195, 230),
}


class SymmetryConstraint:
    """Enforce crystallographic symmetry via Wyckoff position combinatorics."""

    def __init__(self, space_groups: list, element_counts):
        """Initialize with space group range and element counts.

        Args:
            space_groups: [min_sg, max_sg] range, e.g. [1, 230].
            element_counts: Dict {element: count} or list [count1, count2, ...].
        """
        self.space_groups = list(range(space_groups[0], space_groups[1] + 1))
        self.element_counts = element_counts
        self._wyckoffs_dict = {}
        self._max_wyckoffs_count = 0

        if _WYCKOFF_AVAILABLE:
            # Legacy get_all_wyckoff_combination expects atom_num as a list of ints
            if isinstance(element_counts, dict):
                atom_num_list = list(element_counts.values())
            else:
                atom_num_list = list(element_counts)
            try:
                self._wyckoffs_dict, self._max_wyckoffs_count = \
                    get_all_wyckoff_combination(self.space_groups, atom_num_list)
                logger.info(f"Loaded Wyckoff combinations for SG {space_groups[0]}-{space_groups[1]}, "
                            f"max combinations: {self._max_wyckoffs_count}")
            except Exception as e:
                logger.warning(f"Wyckoff enumeration failed: {e}. Proceeding without.")

    @property
    def max_wyckoff_count(self) -> int:
        return self._max_wyckoffs_count

    def get_wyckoff_combinations(self, sg: int) -> list:
        """Get valid Wyckoff site combinations for a space group."""
        return self._wyckoffs_dict.get(sg, [])

    def lattice_from_sg(self, sg: int, params: dict):
        """Create Lattice respecting crystal system constraints.

        Extracts the lattice parameter constraints from the space group number,
        matching the logic from the original predict_structure.py.
        """
        if Lattice is None:
            raise ImportError("pymatgen is required for lattice construction.")

        a = params.get("a", 5.0)
        b = params.get("b", 5.0)
        c = params.get("c", 5.0)
        alpha = params.get("alpha", 90.0)
        beta = params.get("beta", 90.0)
        gamma = params.get("gamma", 90.0)

        if sg <= 2:
            # Triclinic: all parameters free
            return Lattice.from_parameters(a, b, c, alpha, beta, gamma)
        elif sg <= 15:
            # Monoclinic: alpha=gamma=90
            return Lattice.from_parameters(a, b, c, 90, beta, 90)
        elif sg <= 74:
            # Orthorhombic: alpha=beta=gamma=90
            return Lattice.from_parameters(a, b, c, 90, 90, 90)
        elif sg <= 142:
            # Tetragonal: a=b, alpha=beta=gamma=90
            return Lattice.from_parameters(a, a, c, 90, 90, 90)
        elif sg <= 194:
            # Trigonal/Hexagonal: a=b, alpha=beta=90, gamma=120
            return Lattice.from_parameters(a, a, c, 90, 90, 120)
        else:
            # Cubic: a=b=c, alpha=beta=gamma=90
            return Lattice.from_parameters(a, a, a, 90, 90, 90)

    def build_structure(self, params: dict, elements: list,
                        element_counts: list) -> Optional["Structure"]:
        """Build pymatgen Structure from optimization parameters + Wyckoff sites.

        Args:
            params: Dict with keys: a, b, c, alpha, beta, gamma, sg, wp,
                    x1, y1, z1, x2, y2, z2, ...
            elements: List of element symbols, e.g., ["Ca", "S"]
            element_counts: Atoms per element, e.g., [4, 4]

        Returns:
            pymatgen Structure or None on failure.
        """
        if Structure is None:
            raise ImportError("pymatgen is required for structure building.")

        try:
            sg = int(params["sg"])
            lattice = self.lattice_from_sg(sg, params)

            # Get Wyckoff positions for this SG
            wp_list = self._wyckoffs_dict.get(sg, [])
            if not wp_list:
                return None

            wp_idx = int(params.get("wp", 0) * len(wp_list) / max(self._max_wyckoffs_count, 1))
            wp_idx = min(wp_idx, len(wp_list) - 1)
            wp = wp_list[wp_idx]

            # Build atom list and coordinates
            total_atoms = sum(element_counts)
            all_atoms = []
            compound_times = total_atoms / sum(element_counts)
            for j, elem in enumerate(elements):
                for _ in range(int(compound_times * element_counts[j])):
                    all_atoms.append(elem)

            atoms = []
            atom_positions = []
            count = 0
            for i, wp_i in enumerate(wp):
                for wp_i_j in wp_i:
                    atoms += [elements[i]] * len(wp_i_j)
                    for wp_i_j_k in wp_i_j:
                        count += 1
                        pos_str = str(wp_i_j_k)
                        if "x" in pos_str:
                            pos_str = pos_str.replace("x", str(params.get(f"x{count}", 0.0)))
                        if "y" in pos_str:
                            pos_str = pos_str.replace("y", str(params.get(f"y{count}", 0.0)))
                        if "z" in pos_str:
                            pos_str = pos_str.replace("z", str(params.get(f"z{count}", 0.0)))
                        atom_positions.append(list(eval(pos_str)))

            structure = Structure(lattice, atoms, atom_positions)
            return structure
        except Exception as e:
            logger.debug(f"Structure build failed: {e}")
            return None

    @staticmethod
    def crystal_system_for_sg(sg: int) -> str:
        """Return crystal system name for a space group number."""
        for system, (low, high) in CRYSTAL_SYSTEMS.items():
            if low <= sg <= high:
                return system
        return "unknown"
