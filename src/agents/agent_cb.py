"""
Agent CB — Crystal Building Agent
====================================
Responsible for:
  1. Loading top predictions from Agent GCD
  2. Constructing detailed crystal structure models with Wyckoff positions
  3. Evaluating structural feasibility (Goldschmidt, BVS, distances)
  4. Generating CIF files and synthesis recommendations
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict

import numpy as np
import pandas as pd

from src.core.config import (
    DATA_DIR,
    CRYSTAL_PATTERNS_DIR,
    ensure_dirs,
)
from src.core.schemas import (
    PatternCard,
    LatticeParams,
    WyckoffSite,
    CrystalModel,
    FeasibilityReport,
    load_pattern_catalog,
)
from src.agents.agent_cs import parse_composition, ELEMENT_DATA
from src.agents.agent_sin import get_family_key

logger = logging.getLogger("AgentCB")

PREDICTIONS_DIR = DATA_DIR / "predictions"
STRUCTURES_DIR = DATA_DIR / "crystal_structures"

# ---------------------------------------------------------------------------
# Shannon effective ionic radii (Angstroms) for common oxidation states
# Source: Shannon, Acta Cryst. A32, 751 (1976)
# ---------------------------------------------------------------------------
SHANNON_RADII = {
    # Element: {coordination_number: radius}
    "H": {1: 0.38, 4: -0.04},  # H- in hydrides
    "Li": {4: 0.59, 6: 0.76},
    "Be": {4: 0.27, 6: 0.45},
    "B": {3: 0.01, 4: 0.11},
    "C": {4: 0.15, 6: 0.16},
    "N": {4: 0.146},
    "O": {2: 1.35, 3: 1.36, 4: 1.38, 6: 1.40},
    "F": {2: 1.285, 4: 1.31, 6: 1.33},
    "Na": {4: 0.99, 6: 1.02, 8: 1.18},
    "Mg": {4: 0.57, 6: 0.72, 8: 0.89},
    "Al": {4: 0.39, 6: 0.535},
    "Si": {4: 0.26, 6: 0.40},
    "P": {4: 0.17, 6: 0.38},
    "S": {4: 0.12, 6: 1.84},
    "K": {6: 1.38, 8: 1.51, 12: 1.64},
    "Ca": {6: 1.00, 8: 1.12, 12: 1.34},
    "Sc": {6: 0.745, 8: 0.87},
    "Ti": {4: 0.42, 6: 0.605},
    "V": {4: 0.355, 6: 0.54},
    "Cr": {4: 0.41, 6: 0.615},
    "Mn": {4: 0.66, 6: 0.83},
    "Fe": {4: 0.63, 6: 0.78},
    "Co": {4: 0.58, 6: 0.745},
    "Ni": {4: 0.55, 6: 0.69},
    "Cu": {4: 0.57, 6: 0.73},
    "Zn": {4: 0.60, 6: 0.74},
    "Ga": {4: 0.47, 6: 0.62},
    "Ge": {4: 0.39, 6: 0.53},
    "As": {4: 0.335, 6: 0.46},
    "Se": {4: 0.28, 6: 1.98},
    "Rb": {6: 1.52, 8: 1.61},
    "Sr": {6: 1.18, 8: 1.26, 12: 1.44},
    "Y": {6: 0.90, 8: 1.019},
    "Zr": {4: 0.59, 6: 0.72, 8: 0.84},
    "Nb": {4: 0.48, 6: 0.64, 8: 0.79},
    "Mo": {4: 0.41, 6: 0.59},
    "Ru": {6: 0.62},
    "Rh": {6: 0.665},
    "Pd": {4: 0.64, 6: 0.86},
    "Ag": {4: 1.00, 6: 1.15},
    "Cd": {4: 0.78, 6: 0.95},
    "In": {4: 0.62, 6: 0.80},
    "Sn": {4: 0.55, 6: 0.69},
    "Sb": {4: 0.76, 6: 0.60},
    "Te": {4: 0.66, 6: 2.21},
    "Cs": {6: 1.67, 8: 1.74},
    "Ba": {6: 1.35, 8: 1.42, 12: 1.61},
    "La": {6: 1.032, 8: 1.16, 9: 1.216, 12: 1.36},
    "Ce": {6: 1.01, 8: 1.143, 12: 1.34},
    "Nd": {6: 0.983, 8: 1.109, 9: 1.163},
    "Sm": {6: 0.958, 8: 1.079},
    "Eu": {6: 0.947, 8: 1.066},
    "Gd": {6: 0.938, 8: 1.053},
    "Yb": {6: 0.868, 8: 0.985},
    "Hf": {4: 0.58, 6: 0.71, 8: 0.83},
    "Ta": {6: 0.64},
    "W": {4: 0.42, 6: 0.60},
    "Re": {6: 0.55},
    "Os": {6: 0.545},
    "Ir": {6: 0.625},
    "Pt": {4: 0.60, 6: 0.625},
    "Au": {4: 0.64, 6: 0.85},
    "Hg": {4: 0.96, 6: 1.02},
    "Tl": {6: 0.885, 8: 1.00},
    "Pb": {4: 0.65, 6: 0.775, 8: 0.94},
    "Bi": {6: 1.03, 8: 1.17},
    "Pu": {6: 1.00, 8: 0.96},
}

# Covalent radii for minimum distance check (Angstroms)
COVALENT_RADII = {
    "H": 0.31, "Li": 1.28, "Be": 0.96, "B": 0.84, "C": 0.76, "N": 0.71, "O": 0.66,
    "F": 0.57, "Na": 1.66, "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07, "S": 1.05,
    "K": 2.03, "Ca": 1.76, "Sc": 1.70, "Ti": 1.60, "V": 1.53, "Cr": 1.39, "Mn": 1.39,
    "Fe": 1.32, "Co": 1.26, "Ni": 1.24, "Cu": 1.32, "Zn": 1.22, "Ga": 1.22, "Ge": 1.20,
    "As": 1.19, "Se": 1.20, "Rb": 2.20, "Sr": 1.95, "Y": 1.90, "Zr": 1.75, "Nb": 1.64,
    "Mo": 1.54, "Sn": 1.39, "Sb": 1.39, "Te": 1.38, "Cs": 2.44, "Ba": 2.15, "La": 2.07,
    "Ce": 2.04, "Nd": 2.01, "Sm": 1.98, "Eu": 1.98, "Gd": 1.96, "Yb": 1.87,
    "Hf": 1.75, "Ta": 1.70, "W": 1.62, "Pb": 1.46, "Bi": 1.48, "Pu": 1.87,
    "In": 1.42, "Tl": 1.45, "Hg": 1.32, "Ru": 1.46, "Rh": 1.42, "Pd": 1.39,
    "Ag": 1.45, "Cd": 1.44,
}

# ---------------------------------------------------------------------------
# Wyckoff position templates by space group
# ---------------------------------------------------------------------------
WYCKOFF_TEMPLATES = {
    "I4/mmm": {
        "cuprate": [
            WyckoffSite(label="2a", element="Cu", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="4e", element="O", x=0.0, y=0.0, z=0.379),
            WyckoffSite(label="2b", element="RESERVOIR_A", x=0.0, y=0.0, z=0.5),
            WyckoffSite(label="4e", element="O", x=0.5, y=0.0, z=0.0),
            WyckoffSite(label="4d", element="RESERVOIR_B", x=0.0, y=0.5, z=0.25),
        ],
        "iron_pnictide": [
            WyckoffSite(label="4d", element="Fe", x=0.0, y=0.5, z=0.25),
            WyckoffSite(label="4e", element="As", x=0.0, y=0.0, z=0.354),
            WyckoffSite(label="2a", element="SPACER_A", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="2b", element="SPACER_B", x=0.0, y=0.0, z=0.5),
        ],
        "iron_chalcogenide": [
            WyckoffSite(label="2a", element="Fe", x=0.75, y=0.25, z=0.0),
            WyckoffSite(label="2c", element="Se", x=0.25, y=0.25, z=0.268),
        ],
        "nickelate": [
            WyckoffSite(label="2a", element="Ni", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="4e", element="O", x=0.0, y=0.0, z=0.379),
            WyckoffSite(label="2b", element="RARE_EARTH", x=0.0, y=0.0, z=0.5),
            WyckoffSite(label="4e", element="O", x=0.5, y=0.0, z=0.0),
        ],
    },
    "Pmmm": {
        "cuprate": [
            WyckoffSite(label="1a", element="Cu", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="1e", element="O", x=0.5, y=0.0, z=0.0),
            WyckoffSite(label="1b", element="O", x=0.0, y=0.5, z=0.0),
            WyckoffSite(label="2t", element="Ba", x=0.5, y=0.5, z=0.184),
            WyckoffSite(label="1h", element="Y", x=0.5, y=0.5, z=0.5),
        ],
    },
    "P4/nmm": {
        "iron_chalcogenide": [
            WyckoffSite(label="2a", element="Fe", x=0.75, y=0.25, z=0.0),
            WyckoffSite(label="2c", element="Se", x=0.25, y=0.25, z=0.268),
        ],
        "iron_pnictide": [
            WyckoffSite(label="2c", element="Fe", x=0.25, y=0.25, z=0.5),
            WyckoffSite(label="2c", element="As", x=0.25, y=0.25, z=0.151),
            WyckoffSite(label="2c", element="SPACER", x=0.25, y=0.25, z=0.857),
            WyckoffSite(label="2a", element="O", x=0.75, y=0.25, z=0.0),
        ],
    },
    "P4/mmm": {
        "heavy_fermion": [
            WyckoffSite(label="1a", element="Ce", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="1b", element="Co", x=0.0, y=0.0, z=0.5),
            WyckoffSite(label="4i", element="In", x=0.0, y=0.5, z=0.306),
            WyckoffSite(label="1c", element="In", x=0.5, y=0.5, z=0.0),
        ],
        "nickelate": [
            WyckoffSite(label="1a", element="Ni", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="1b", element="RARE_EARTH", x=0.0, y=0.0, z=0.5),
            WyckoffSite(label="2f", element="O", x=0.5, y=0.0, z=0.0),
        ],
    },
    "P6/mmm": {
        "mgb2_type": [
            WyckoffSite(label="1a", element="Mg", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="2d", element="B", x=0.3333, y=0.6667, z=0.5),
        ],
        "kagome": [
            WyckoffSite(label="3g", element="TRANSITION_METAL", x=0.5, y=0.0, z=0.5, occupancy=1.0),
            WyckoffSite(label="1a", element="PNICTOGEN_A", x=0.0, y=0.0, z=0.0, occupancy=1.0),
            WyckoffSite(label="2c", element="PNICTOGEN_B", x=0.333, y=0.667, z=0.0, occupancy=1.0),
            WyckoffSite(label="1b", element="ALKALI", x=0.0, y=0.0, z=0.5, occupancy=1.0),
        ],
    },
    "Pm-3n": {
        "a15": [
            WyckoffSite(label="2a", element="CHAIN_B", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="6c", element="CHAIN_A", x=0.25, y=0.0, z=0.5),
        ],
    },
    "Im-3m": {
        "hydride": [
            WyckoffSite(label="2a", element="METAL", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="6b", element="H", x=0.0, y=0.5, z=0.5),
            WyckoffSite(label="12d", element="H", x=0.25, y=0.0, z=0.5),
        ],
    },
    "Fm-3m": {
        "hydride": [
            WyckoffSite(label="4a", element="METAL", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="8c", element="H", x=0.25, y=0.25, z=0.25),
            WyckoffSite(label="32f", element="H", x=0.12, y=0.12, z=0.12),
        ],
    },
    "R-3": {
        "chevrel": [
            WyckoffSite(label="3a", element="INTERCALANT", x=0.0, y=0.0, z=0.0),
            WyckoffSite(label="18f", element="Mo", x=0.167, y=0.167, z=0.167),
            WyckoffSite(label="18f", element="S", x=0.333, y=0.333, z=0.05),
        ],
    },
    "Pm-3m": {
        "ternary_hydride": [
            WyckoffSite(label="1a", element="METAL_A", x=0.0, y=0.0, z=0.0, occupancy=1.0),
            WyckoffSite(label="1b", element="STABILIZER", x=0.5, y=0.5, z=0.5, occupancy=1.0),
            WyckoffSite(label="3c", element="H", x=0.5, y=0.5, z=0.0, occupancy=1.0),
            WyckoffSite(label="3d", element="H", x=0.5, y=0.0, z=0.0, occupancy=1.0),
            WyckoffSite(label="6e", element="H", x=0.25, y=0.0, z=0.0, occupancy=1.0),
        ],
    },
}

# Bond valence parameters R0 (Angstroms) — Brown & Altermatt, Acta Cryst. B41, 244 (1985)
BOND_VALENCE_R0 = {
    ("Cu", "O"): 1.679, ("Fe", "As"): 2.26, ("Fe", "Se"): 2.328,
    ("Ni", "O"): 1.654, ("Mg", "B"): 1.90, ("Nb", "Sn"): 2.56,
    ("La", "O"): 2.172, ("Ba", "O"): 2.285, ("Sr", "O"): 2.118,
    ("Y", "O"): 2.019, ("Ce", "In"): 2.85, ("Co", "In"): 2.45,
    ("Nd", "O"): 2.105, ("Mo", "S"): 2.33, ("Pb", "S"): 2.55,
    ("H", "H"): 0.74, ("La", "H"): 2.08,
}

# Synthesis method recommendations by family
SYNTHESIS_METHODS = {
    "cuprate": {"method": "solid-state", "conditions": "900-950C in O2, slow cooling"},
    "iron_pnictide": {"method": "solid-state", "conditions": "800-1000C in sealed quartz tube"},
    "iron_chalcogenide": {"method": "vapor-transport", "conditions": "400-700C, Se/Te flux"},
    "heavy_fermion": {"method": "flux-growth", "conditions": "In flux, 800-1100C, slow cool"},
    "mgb2_type": {"method": "solid-state", "conditions": "850C under Ar, 2h sintering"},
    "a15": {"method": "arc-melting", "conditions": "Ar atmosphere, annealing 700-1000C"},
    "hydride": {"method": "high-pressure", "conditions": "150-200 GPa in diamond anvil cell"},
    "nickelate": {"method": "high-pressure", "conditions": "15-30 GPa, 1000-1800C, oxygen control"},
    "chevrel": {"method": "solid-state", "conditions": "1000-1200C in sealed Mo tube"},
    "kagome": {"method": "flux-growth", "conditions": "Sb self-flux 800-1000C slow cool to 500C", "difficulty": "moderate"},
    "ternary_hydride": {"method": "high-pressure-quench", "conditions": "5-20 GPa synthesis then rapid quench to metastable ambient", "difficulty": "difficult"},
    "infinite_layer": {"method": "topotactic-reduction", "conditions": "CaH2 reduction of perovskite precursor 280C", "difficulty": "difficult"},
    "topological": {"method": "MBE", "conditions": "molecular beam epitaxy on SrTiO3 substrate", "difficulty": "difficult"},
    "2d_heterostructure": {"method": "exfoliation-stacking", "conditions": "mechanical exfoliation and deterministic transfer", "difficulty": "moderate"},
    "carbon_based": {"method": "vapor-intercalation", "conditions": "alkali vapor 200-400C sealed ampoule", "difficulty": "moderate"},
    "engineered_cuprate": {"method": "PLD", "conditions": "pulsed laser deposition on SrTiO3 780C in O2", "difficulty": "difficult"},
    "mof_sc": {"method": "solvothermal", "conditions": "DMF solvent 85C 72h activation under vacuum", "difficulty": "moderate"},
    "flat_band": {"method": "arc-melting", "conditions": "arc melting under Ar followed by annealing 800C", "difficulty": "moderate"},
}


class AgentCB:
    """Crystal Building Agent — constructs and evaluates crystal structures."""

    def __init__(self):
        ensure_dirs()
        STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)

    def load_predictions(self) -> pd.DataFrame:
        """Load GCD top candidates."""
        top_path = PREDICTIONS_DIR / "gcd_top_candidates.csv"
        if not top_path.exists():
            # Fall back to all ranked
            top_path = PREDICTIONS_DIR / "gcd_all_ranked.csv"
        if not top_path.exists():
            raise FileNotFoundError("No GCD predictions found. Run Agent GCD first.")
        df = pd.read_csv(top_path)
        logger.info(f"Loaded {len(df)} predictions from {top_path.name}")
        return df

    def load_patterns(self) -> dict[str, PatternCard]:
        """Load latest pattern catalog as dict keyed by pattern_id."""
        catalogs = sorted(CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"))
        if not catalogs:
            raise FileNotFoundError("No pattern catalogs found")
        patterns = load_pattern_catalog(catalogs[-1])
        return {p.pattern_id: p for p in patterns}

    def _resolve_element(self, template_element: str, composition: dict[str, float],
                         family: str) -> str:
        """Resolve placeholder elements (RESERVOIR_A, METAL, etc.) to actual elements."""
        placeholders = {
            "RESERVOIR_A": ["Ba", "Sr", "La", "Bi", "Hg", "Tl", "Nd"],
            "RESERVOIR_B": ["Y", "Ca", "Sr", "Ba"],
            "SPACER_A": ["La", "Nd", "Ce", "Ba", "Na", "Li"],
            "SPACER_B": ["O", "F"],
            "SPACER": ["La", "Nd", "Ce", "Na"],
            "RARE_EARTH": ["Nd", "La", "Ce", "Sm", "Gd"],
            "METAL": ["La", "Y", "Ca", "Ce", "Sr", "H", "S"],
            "INTERCALANT": ["Pb", "Sn", "Cu", "Ag"],
            "CHAIN_A": ["Nb", "V", "Ta"],
            "CHAIN_B": ["Sn", "Ge", "Si", "Al"],
            "TRANSITION_METAL": ["V", "Mn", "Fe", "Co", "Ni", "Ti", "Cr"],
            "PNICTOGEN_A": ["Sb", "As", "P", "Bi"],
            "PNICTOGEN_B": ["Sb", "As", "P", "Bi"],
            "ALKALI": ["K", "Rb", "Cs", "Na"],
            "METAL_A": ["La", "Y", "Ca", "Sr", "Ba"],
            "STABILIZER": ["B", "N", "C", "Si"],
        }

        if template_element not in placeholders:
            return template_element

        candidates = placeholders[template_element]
        # Prefer elements present in the composition
        for elem in candidates:
            if elem in composition:
                return elem
        # Default to first candidate
        return candidates[0]

    def build_crystal_model(self, row: pd.Series, pattern: PatternCard) -> CrystalModel:
        """Construct a complete crystal structure model."""
        composition = parse_composition(row["composition"])
        family = get_family_key(row["pattern_id"])
        space_group = row.get("space_group", pattern.space_group)

        # Find matching Wyckoff template
        sg_templates = WYCKOFF_TEMPLATES.get(space_group, {})
        template_sites = sg_templates.get(family, [])

        # If no exact match, try first available template for this space group
        if not template_sites and sg_templates:
            template_sites = list(sg_templates.values())[0]

        # Build sites with resolved elements
        sites = []
        for tmpl in template_sites:
            elem = self._resolve_element(tmpl.element, composition, family)
            sites.append(WyckoffSite(
                label=tmpl.label,
                element=elem,
                x=tmpl.x,
                y=tmpl.y,
                z=tmpl.z,
                occupancy=1.0,
            ))

        # If no template available, create generic sites from composition
        if not sites and composition:
            z_pos = 0.0
            for elem, count in composition.items():
                n_sites = max(1, int(round(count)))
                for i in range(min(n_sites, 4)):  # Max 4 sites per element
                    sites.append(WyckoffSite(
                        label=f"{n_sites}a",
                        element=elem,
                        x=0.0 if i % 2 == 0 else 0.5,
                        y=0.0 if i < 2 else 0.5,
                        z=round(z_pos, 4),
                        occupancy=1.0,
                    ))
                    z_pos += 1.0 / (sum(min(int(round(c)), 4) for c in composition.values()) or 1)

        # Compute bond lengths from lattice parameters
        a = row.get("a", pattern.lattice_params.a)
        c = row.get("c", pattern.lattice_params.c)
        b = row.get("b", pattern.lattice_params.b or a)

        # Pressure-aware lattice scaling: compress if P > 0 and pattern has pressure_params
        pressure_GPa = row.get("pressure_GPa", 0.0) if hasattr(row, "get") else 0.0
        if pressure_GPa > 0 and pattern.pressure_params is not None:
            from src.agents.agent_p import volume_at_pressure
            pp = pattern.pressure_params
            try:
                V_P = volume_at_pressure(pressure_GPa, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
                scale = (V_P / pp.V0_per_atom_A3) ** (1.0 / 3.0)  # isotropic compression
                a *= scale
                b *= scale
                c *= scale
            except Exception:
                pass  # Fall back to unscaled lattice

        lp = LatticeParams(a=a, c=c, b=b)

        bond_lengths = self._compute_bond_lengths(sites, lp)
        coord_numbers = self._compute_coordination_numbers(sites, lp)

        return CrystalModel(
            candidate_id=row.get("structure_id", "unknown"),
            composition=row["composition"],
            space_group=space_group,
            crystal_system=row.get("crystal_system", pattern.crystal_system),
            lattice_params=lp,
            sites=sites,
            predicted_Tc_K=row.get("predicted_Tc_K", 0.0),
            bond_lengths=bond_lengths,
            coordination_numbers=coord_numbers,
        )

    def _compute_bond_lengths(self, sites: list[WyckoffSite], lp: LatticeParams) -> dict[str, float]:
        """Compute nearest-neighbor bond lengths between sites."""
        bonds = {}
        a, b, c = lp.a, lp.b or lp.a, lp.c

        for i, s1 in enumerate(sites):
            for j, s2 in enumerate(sites):
                if j <= i:
                    continue
                if s1.element == s2.element:
                    continue

                # Fractional to Cartesian (orthorhombic approximation)
                dx = (s1.x - s2.x) * a
                dy = (s1.y - s2.y) * b
                dz = (s1.z - s2.z) * c

                # Apply minimum image convention
                dx = min(abs(dx), abs(abs(dx) - a))
                dy = min(abs(dy), abs(abs(dy) - b))
                dz = min(abs(dz), abs(abs(dz) - c))

                dist = math.sqrt(dx**2 + dy**2 + dz**2)
                if 0.5 < dist < 6.0:  # Physically relevant range
                    pair_key = f"{s1.element}-{s2.element}"
                    if pair_key not in bonds or dist < bonds[pair_key]:
                        bonds[pair_key] = round(dist, 3)

        return bonds

    def _compute_coordination_numbers(self, sites: list[WyckoffSite],
                                       lp: LatticeParams) -> dict[str, int]:
        """Estimate coordination numbers from site geometry."""
        a, b, c = lp.a, lp.b or lp.a, lp.c
        coord = {}

        for i, s1 in enumerate(sites):
            nn_count = 0
            for j, s2 in enumerate(sites):
                if j == i:
                    continue
                dx = (s1.x - s2.x) * a
                dy = (s1.y - s2.y) * b
                dz = (s1.z - s2.z) * c
                dx = min(abs(dx), abs(abs(dx) - a))
                dy = min(abs(dy), abs(abs(dy) - b))
                dz = min(abs(dz), abs(abs(dz) - c))
                dist = math.sqrt(dx**2 + dy**2 + dz**2)
                # Count neighbors within reasonable bonding distance
                r1 = COVALENT_RADII.get(s1.element, 1.5)
                r2 = COVALENT_RADII.get(s2.element, 1.5)
                if 0.5 < dist < (r1 + r2) * 1.5:
                    nn_count += 1
            key = f"{s1.element}({s1.label})"
            coord[key] = nn_count

        return coord

    def evaluate_feasibility(self, model: CrystalModel) -> FeasibilityReport:
        """Evaluate structural feasibility with multiple criteria."""
        composition = parse_composition(model.composition)
        family = get_family_key(model.candidate_id) if "-" in model.candidate_id else "unknown"

        # 1. Goldschmidt tolerance (for perovskite-like structures)
        goldschmidt = None
        if model.crystal_system in ("tetragonal", "orthorhombic", "cubic"):
            goldschmidt = self._compute_goldschmidt(composition, model.sites)

        # 2. Bond valence sums
        bvs = self._compute_bond_valence(model)

        # 3. Minimum interatomic distance check
        min_dist, violations = self._check_distances(model)

        # 4. Composite feasibility score
        scores = []

        # Distance score: 1.0 if no violations, penalize for each
        dist_score = max(0, 1.0 - 0.2 * len(violations))
        scores.append(dist_score)

        # Goldschmidt score (if applicable): peak at t=0.9-1.0
        if goldschmidt is not None and goldschmidt > 0:
            t_score = max(0, 1.0 - abs(goldschmidt - 0.95) / 0.3)
            scores.append(t_score)

        # BVS score: closer to integer formal valences = better
        if bvs:
            bvs_deviations = [abs(v - round(v)) for v in bvs.values() if v > 0]
            if bvs_deviations:
                bvs_score = max(0, 1.0 - np.mean(bvs_deviations) / 0.5)
                scores.append(bvs_score)

        # Stability confidence from original prediction
        stability_score = 0.8  # Default if not available

        feasibility_score = float(np.mean(scores)) if scores else 0.5

        # Determine synthesis difficulty and method
        family_from_sg = self._guess_family_from_model(model)
        synth_info = SYNTHESIS_METHODS.get(family_from_sg, {"method": "solid-state", "conditions": "TBD"})

        # Difficulty based on conditions
        if "high-pressure" in synth_info["method"]:
            difficulty = "extreme" if "200 GPa" in synth_info["conditions"] else "hard"
        elif "flux" in synth_info["method"]:
            difficulty = "moderate"
        else:
            difficulty = "easy" if feasibility_score > 0.8 else "moderate"

        return FeasibilityReport(
            candidate_id=model.candidate_id,
            goldschmidt_tolerance=round(goldschmidt, 4) if goldschmidt else None,
            bond_valence_sums={k: round(v, 3) for k, v in bvs.items()},
            min_interatomic_distance_A=round(min_dist, 3),
            distance_violations=violations,
            feasibility_score=round(feasibility_score, 4),
            synthesis_difficulty=difficulty,
            recommended_method=synth_info["method"],
        )

    def evaluate_rtap_feasibility(self, model: CrystalModel) -> FeasibilityReport:
        """Enhanced feasibility for RTAP candidates with ambient-condition checks."""
        # Start with standard feasibility
        report = self.evaluate_feasibility(model)

        # Additional RTAP checks
        comp = parse_composition(model.composition)
        elements = set(comp.keys())

        # Air stability heuristic
        MOISTURE_SENSITIVE = {"Li", "Na", "K", "Rb", "Cs", "Ca", "Sr", "Ba"}
        AIR_REACTIVE = {"Li", "Na", "K", "Rb", "Cs"}

        moisture_frac = sum(comp.get(e, 0) for e in elements & MOISTURE_SENSITIVE) / max(sum(comp.values()), 1)
        air_frac = sum(comp.get(e, 0) for e in elements & AIR_REACTIVE) / max(sum(comp.values()), 1)

        # Penalize air/moisture sensitivity
        air_penalty = min(0.3, air_frac * 0.5)
        moisture_penalty = min(0.2, moisture_frac * 0.3)

        report.feasibility_score = max(0, report.feasibility_score - air_penalty - moisture_penalty)

        # Toxic element check
        TOXIC = {"Hg", "Tl", "Pb", "Cd", "Pu"}
        if elements & TOXIC:
            report.feasibility_score *= 0.7

        return report

    def _guess_family_from_model(self, model: CrystalModel) -> str:
        """Guess family from model properties for synthesis recommendations."""
        comp = parse_composition(model.composition)
        elements = set(comp.keys()) if comp else set()

        if "Cu" in elements and "O" in elements:
            return "cuprate"
        if "Fe" in elements and ("As" in elements or "P" in elements):
            return "iron_pnictide"
        if "Fe" in elements and ("Se" in elements or "Te" in elements):
            return "iron_chalcogenide"
        if "Ce" in elements or "Pu" in elements:
            return "heavy_fermion"
        if "Mg" in elements and "B" in elements:
            return "mgb2_type"
        if "Nb" in elements and model.space_group == "Pm-3n":
            return "a15"
        if "H" in elements and model.predicted_Tc_K > 100:
            return "hydride"
        if "Ni" in elements and "O" in elements:
            return "nickelate"
        if "Mo" in elements and "S" in elements:
            return "chevrel"
        return "unknown"

    def _compute_goldschmidt(self, composition: dict[str, float],
                             sites: list[WyckoffSite]) -> float:
        """Compute Goldschmidt tolerance factor for perovskite-like structures."""
        if not composition or len(composition) < 2:
            return 0.0

        # Find A-site and B-site ions (larger = A, smaller = B)
        radii = {}
        for elem in composition:
            r = SHANNON_RADII.get(elem, {})
            # Default to 6-coordination
            radii[elem] = r.get(6, r.get(4, r.get(8, 1.0)))

        # O is the anion
        r_O = radii.get("O", 1.40)

        cations = {e: r for e, r in radii.items() if e not in ("O", "F", "S", "Se", "Te", "H")}
        if len(cations) < 2:
            return 0.0

        sorted_cations = sorted(cations.items(), key=lambda x: x[1], reverse=True)
        r_A = sorted_cations[0][1]
        r_B = sorted_cations[1][1]

        # t = (r_A + r_O) / (sqrt(2) * (r_B + r_O))
        denominator = math.sqrt(2) * (r_B + r_O)
        if denominator == 0:
            return 0.0
        return (r_A + r_O) / denominator

    def _compute_bond_valence(self, model: CrystalModel) -> dict[str, float]:
        """Compute bond valence sums for sites."""
        bvs = {}
        b_param = 0.37  # Universal BVS parameter

        for site in model.sites:
            total_valence = 0.0
            for pair_key, dist in model.bond_lengths.items():
                elems = pair_key.split("-")
                if site.element in elems:
                    # Find R0 for this pair
                    pair_tuple = (elems[0], elems[1])
                    r0 = BOND_VALENCE_R0.get(pair_tuple,
                          BOND_VALENCE_R0.get((elems[1], elems[0]), 2.0))
                    if dist > 0:
                        valence = math.exp((r0 - dist) / b_param)
                        total_valence += valence

            key = f"{site.element}({site.label})"
            bvs[key] = total_valence

        return bvs

    def _check_distances(self, model: CrystalModel) -> tuple[float, list[str]]:
        """Check minimum interatomic distances for atom overlap."""
        min_dist = float("inf")
        violations = []

        for pair_key, dist in model.bond_lengths.items():
            elems = pair_key.split("-")
            r1 = COVALENT_RADII.get(elems[0], 1.0)
            r2 = COVALENT_RADII.get(elems[1], 1.0)
            min_allowed = (r1 + r2) * 0.5  # 50% of sum of covalent radii

            if dist < min_dist:
                min_dist = dist

            if dist < min_allowed:
                violations.append(
                    f"{pair_key}: {dist:.3f} A < minimum {min_allowed:.3f} A"
                )

        if min_dist == float("inf"):
            min_dist = 0.0

        return min_dist, violations

    def generate_cif_string(self, model: CrystalModel, pressure_GPa: float = 0.0) -> str:
        """Generate CIF (Crystallographic Information File) format."""
        a = model.lattice_params.a
        b = model.lattice_params.b or a
        c = model.lattice_params.c

        cif = f"""data_{model.candidate_id}
_symmetry_space_group_name_H-M   '{model.space_group}'
_cell_length_a   {a:.4f}
_cell_length_b   {b:.4f}
_cell_length_c   {c:.4f}
_cell_angle_alpha   {model.lattice_params.alpha:.2f}
_cell_angle_beta    {model.lattice_params.beta:.2f}
_cell_angle_gamma   {model.lattice_params.gamma:.2f}
_chemical_formula_sum   '{model.composition}'
_cell_formula_units_Z   1

# Predicted superconducting properties
# _predicted_Tc_K   {model.predicted_Tc_K:.2f}
# _pressure_GPa   {pressure_GPa:.1f}

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
"""
        for site in model.sites:
            cif += f"  {site.element}{site.label}  {site.element}  "
            cif += f"{site.x:.4f}  {site.y:.4f}  {site.z:.4f}  {site.occupancy:.2f}\n"

        return cif

    def run(self) -> Path:
        """Main: load predictions -> build models -> evaluate -> rank -> save."""
        logger.info("=== Agent CB: Crystal Building Agent Starting ===")

        # 1. Load data
        predictions_df = self.load_predictions()
        pattern_map = self.load_patterns()

        results = []
        all_models = []

        for idx, row in predictions_df.iterrows():
            pid = row.get("pattern_id", "")
            pattern = pattern_map.get(pid)
            if pattern is None:
                # Try to find a matching pattern by family
                family = get_family_key(pid) if pid else "unknown"
                for p in pattern_map.values():
                    if get_family_key(p.pattern_id) == family:
                        pattern = p
                        break

            if pattern is None:
                logger.warning(f"No pattern found for {pid}, skipping")
                continue

            # 2. Build crystal model
            model = self.build_crystal_model(row, pattern)
            all_models.append(model)

            # 3. Evaluate feasibility
            feasibility = self.evaluate_feasibility(model)

            # 4. Save per-candidate files
            candidate_dir = STRUCTURES_DIR / model.candidate_id
            candidate_dir.mkdir(parents=True, exist_ok=True)

            # CIF file
            p_gpa = row.get("pressure_GPa", 0.0) if hasattr(row, "get") else 0.0
            cif_path = candidate_dir / "structure.cif"
            with open(cif_path, "w") as f:
                f.write(self.generate_cif_string(model, pressure_GPa=p_gpa))

            # Crystal model JSON
            model_path = candidate_dir / "crystal_card.json"
            with open(model_path, "w") as f:
                f.write(model.to_json())

            # Feasibility report
            feas_path = candidate_dir / "feasibility.json"
            with open(feas_path, "w") as f:
                f.write(feasibility.to_json())

            results.append({
                "candidate_id": model.candidate_id,
                "composition": model.composition,
                "space_group": model.space_group,
                "crystal_system": model.crystal_system,
                "predicted_Tc_K": model.predicted_Tc_K,
                "num_sites": len(model.sites),
                "num_bonds": len(model.bond_lengths),
                "feasibility_score": feasibility.feasibility_score,
                "goldschmidt_tolerance": feasibility.goldschmidt_tolerance,
                "min_distance_A": feasibility.min_interatomic_distance_A,
                "distance_violations": len(feasibility.distance_violations),
                "synthesis_difficulty": feasibility.synthesis_difficulty,
                "recommended_method": feasibility.recommended_method,
            })

            logger.info(
                f"  {model.candidate_id}: {model.composition} | "
                f"Tc={model.predicted_Tc_K:.1f}K | "
                f"feasibility={feasibility.feasibility_score:.3f} | "
                f"{feasibility.synthesis_difficulty}"
            )

        # 5. Save summary CSV
        if results:
            summary_df = pd.DataFrame(results)
            summary_df = summary_df.sort_values("feasibility_score", ascending=False)
            summary_path = STRUCTURES_DIR / "summary.csv"
            summary_df.to_csv(summary_path, index=False)
            logger.info(f"Saved summary of {len(results)} structures to {summary_path}")

            # 6. Synthesis recommendations grouped by method
            synth_recs = {}
            for r in results:
                method = r["recommended_method"]
                if method not in synth_recs:
                    synth_recs[method] = []
                synth_recs[method].append({
                    "candidate_id": r["candidate_id"],
                    "composition": r["composition"],
                    "predicted_Tc_K": r["predicted_Tc_K"],
                    "feasibility_score": r["feasibility_score"],
                    "synthesis_difficulty": r["synthesis_difficulty"],
                })

            # Sort each group by feasibility
            for method in synth_recs:
                synth_recs[method] = sorted(
                    synth_recs[method], key=lambda x: x["feasibility_score"], reverse=True
                )

            synth_path = STRUCTURES_DIR / "synthesis_recommendations.json"
            with open(synth_path, "w") as f:
                json.dump({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_candidates": len(results),
                    "methods": synth_recs,
                }, f, indent=2)
            logger.info(f"Saved synthesis recommendations to {synth_path}")

        logger.info("=== Agent CB: Complete ===")
        return STRUCTURES_DIR


def run_agent_cb() -> Path:
    """Main entry point for Agent CB."""
    agent = AgentCB()
    return agent.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    path = run_agent_cb()
    print(f"Crystal structures saved to: {path}")
