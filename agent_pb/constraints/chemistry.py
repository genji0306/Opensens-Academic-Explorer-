"""Chemistry constraints — charge neutrality and composition validation."""
import re
import logging

logger = logging.getLogger("AgentPB.Constraints.Chemistry")

# Common oxidation states for elements frequently appearing in crystals
COMMON_OXIDATION_STATES = {
    "H": [1, -1], "Li": [1], "Be": [2], "B": [3], "C": [4, -4, 2],
    "N": [-3, 3, 5], "O": [-2], "F": [-1], "Na": [1], "Mg": [2],
    "Al": [3], "Si": [4, -4], "P": [5, 3, -3], "S": [-2, 4, 6],
    "Cl": [-1, 1, 3, 5, 7], "K": [1], "Ca": [2], "Sc": [3],
    "Ti": [4, 3, 2], "V": [5, 4, 3, 2], "Cr": [3, 6, 2],
    "Mn": [2, 4, 7, 3], "Fe": [3, 2], "Co": [2, 3], "Ni": [2, 3],
    "Cu": [2, 1], "Zn": [2], "Ga": [3], "Ge": [4, 2],
    "As": [5, 3, -3], "Se": [-2, 4, 6], "Br": [-1], "Rb": [1],
    "Sr": [2], "Y": [3], "Zr": [4], "Nb": [5, 3], "Mo": [6, 4],
    "Ru": [4, 3], "Rh": [3], "Pd": [2, 4], "Ag": [1],
    "Cd": [2], "In": [3], "Sn": [4, 2], "Sb": [5, 3, -3],
    "Te": [-2, 4, 6], "I": [-1], "Cs": [1], "Ba": [2],
    "La": [3], "Ce": [3, 4], "Pr": [3], "Nd": [3],
    "Sm": [3, 2], "Eu": [3, 2], "Gd": [3], "Tb": [3, 4],
    "Dy": [3], "Ho": [3], "Er": [3], "Tm": [3],
    "Yb": [3, 2], "Lu": [3], "Hf": [4], "Ta": [5],
    "W": [6, 4], "Re": [7, 4], "Os": [4], "Ir": [4, 3],
    "Pt": [4, 2], "Au": [3, 1], "Hg": [2, 1], "Tl": [3, 1],
    "Pb": [2, 4], "Bi": [3, 5],
}


def parse_formula(formula: str) -> dict:
    """Parse chemical formula to element:count dict.

    Examples:
        "Ca4S4" -> {"Ca": 4, "S": 4}
        "YBa2Cu3O7" -> {"Y": 1, "Ba": 2, "Cu": 3, "O": 7}
    """
    pattern = r"([A-Z][a-z]?)(\d*\.?\d*)"
    matches = re.findall(pattern, formula.replace(" ", ""))
    result = {}
    for elem, count in matches:
        if elem:
            result[elem] = result.get(elem, 0) + (float(count) if count else 1.0)
    return result


class ChemistryConstraint:
    """Charge neutrality and oxidation state validation."""

    def validate_composition(self, formula: str) -> bool:
        """Check if composition has valid element symbols."""
        comp = parse_formula(formula)
        if not comp:
            return False
        for elem in comp:
            if elem not in COMMON_OXIDATION_STATES:
                logger.debug(f"Unknown element: {elem}")
                return False
        return True

    def check_charge_neutrality(self, formula: str) -> tuple:
        """Check if any combination of common oxidation states sums to zero.

        Returns (is_balanced, best_residual).
        """
        comp = parse_formula(formula)
        if not comp:
            return False, 999.0

        elements = list(comp.keys())
        counts = [comp[e] for e in elements]

        # Get oxidation state options per element
        ox_options = []
        for elem in elements:
            states = COMMON_OXIDATION_STATES.get(elem, [0])
            ox_options.append(states)

        # Try all combinations (brute-force for small formulas)
        best_residual = float("inf")
        from itertools import product
        for combo in product(*ox_options):
            total_charge = sum(ox * count for ox, count in zip(combo, counts))
            residual = abs(total_charge)
            best_residual = min(best_residual, residual)
            if residual < 0.01:
                return True, 0.0

        return best_residual < 1.0, best_residual

    def get_common_oxidation_states(self, element: str) -> list:
        """Return common oxidation states for an element."""
        return COMMON_OXIDATION_STATES.get(element, [])
