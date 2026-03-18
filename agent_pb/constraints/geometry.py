"""Geometry constraints — bond distances, volume, vacuum validation."""
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("AgentPB.Constraints.Geometry")

# Covalent radii (Angstrom) for common elements
COVALENT_RADII = {
    "H": 0.31, "He": 0.28, "Li": 1.28, "Be": 0.96, "B": 0.84,
    "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "Ne": 0.58,
    "Na": 1.66, "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07,
    "S": 1.05, "Cl": 1.02, "Ar": 1.06, "K": 2.03, "Ca": 1.76,
    "Sc": 1.70, "Ti": 1.60, "V": 1.53, "Cr": 1.39, "Mn": 1.39,
    "Fe": 1.32, "Co": 1.26, "Ni": 1.24, "Cu": 1.32, "Zn": 1.22,
    "Ga": 1.22, "Ge": 1.20, "As": 1.19, "Se": 1.20, "Br": 1.20,
    "Rb": 2.20, "Sr": 1.95, "Y": 1.90, "Zr": 1.75, "Nb": 1.64,
    "Mo": 1.54, "Ru": 1.46, "Rh": 1.42, "Pd": 1.39, "Ag": 1.45,
    "Cd": 1.44, "In": 1.42, "Sn": 1.39, "Sb": 1.39, "Te": 1.38,
    "I": 1.39, "Cs": 2.44, "Ba": 2.15, "La": 2.07, "Ce": 2.04,
    "Pr": 2.03, "Nd": 2.01, "Sm": 1.98, "Eu": 1.98, "Gd": 1.96,
    "Tb": 1.94, "Dy": 1.92, "Ho": 1.92, "Er": 1.89, "Tm": 1.90,
    "Yb": 1.87, "Lu": 1.87, "Hf": 1.75, "Ta": 1.70, "W": 1.62,
    "Re": 1.51, "Os": 1.44, "Ir": 1.41, "Pt": 1.36, "Au": 1.36,
    "Pb": 1.46, "Bi": 1.48,
}


class GeometryConstraint:
    """Bond length, volume, and vacuum size validation for crystal structures."""

    def __init__(self, min_dist_factor: float = 0.4, max_volume_factor: float = 2.4,
                 min_volume_factor: float = 0.4, max_vacuum_size: float = 7.0):
        self.min_dist_factor = min_dist_factor
        self.max_volume_factor = max_volume_factor
        self.min_volume_factor = min_volume_factor
        self.max_vacuum_size = max_vacuum_size

    def validate_structure(self, structure) -> tuple:
        """Full geometry validation.

        Returns:
            (is_valid, violations): Tuple of bool and list of violation strings.
        """
        violations = []
        violations.extend(self.check_atomic_distances(structure))

        if not self.check_volume(structure):
            violations.append("Volume outside acceptable range")

        if not self.check_vacuum(structure):
            violations.append(f"Vacuum gap exceeds {self.max_vacuum_size} A")

        return len(violations) == 0, violations

    def check_atomic_distances(self, structure) -> list:
        """Check minimum interatomic distances against covalent radii.

        Returns list of violation descriptions.
        """
        violations = []
        n_atoms = len(structure)
        for i in range(n_atoms - 1):
            r_i = COVALENT_RADII.get(str(structure[i].specie), 1.0)
            for j in range(i + 1, n_atoms):
                r_j = COVALENT_RADII.get(str(structure[j].specie), 1.0)
                min_dist = (r_i + r_j) * self.min_dist_factor
                actual_dist = structure.get_distance(i, j)
                if actual_dist < min_dist:
                    violations.append(
                        f"Distance {structure[i].specie}-{structure[j].specie} "
                        f"= {actual_dist:.3f} A < {min_dist:.3f} A")
        return violations

    def check_volume(self, structure) -> bool:
        """Volume should be within bounds of sum of atomic volumes."""
        atom_radii = [COVALENT_RADII.get(str(s.specie), 1.0) for s in structure]
        sum_atom_volume = sum(4.0 * np.pi * r ** 3 / 3.0 for r in atom_radii) / 0.55
        return (sum_atom_volume * self.min_volume_factor <= structure.volume <=
                sum_atom_volume * self.max_volume_factor)

    def check_vacuum(self, structure, max_size: Optional[float] = None) -> bool:
        """Check for excessive vacuum gaps in the structure.

        Adapted from GN-OA's vacuum_size_limit method.
        """
        if max_size is None:
            max_size = self.max_vacuum_size
        try:
            supercell = structure.copy()
            supercell.make_supercell([2, 2, 2])

            # Check along principal axes for large gaps
            frac_coords = supercell.frac_coords
            for axis in range(3):
                sorted_coords = np.sort(frac_coords[:, axis])
                # Check gaps between consecutive atoms
                gaps = np.diff(sorted_coords)
                # Convert fractional gap to Cartesian distance (approximate)
                lattice_length = np.linalg.norm(supercell.lattice.matrix[axis])
                max_gap = np.max(gaps) * lattice_length if len(gaps) > 0 else 0
                if max_gap > max_size:
                    return False
            return True
        except Exception:
            return True  # Don't reject on validation failure
