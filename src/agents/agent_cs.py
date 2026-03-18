"""
Agent CS — Crystal Structure Agent
===================================
Responsible for:
  1. Ingesting and mapping known superconductor crystal structures
  2. Extracting crystal pattern cards for each superconductor family
  3. Generating NEMAD-style feature vectors for compositions
  4. Updating patterns based on refinement feedback from Agent Ob
"""
from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.core.config import (
    NEMAD_DATASET_DIR,
    CRYSTAL_PATTERNS_DIR,
    EXPERIMENTAL_DIR,
    REFINEMENTS_DIR,
    SC_FAMILIES,
    RTAP_FAMILIES,
    ensure_dirs,
)
from src.core.schemas import (
    PatternCard,
    LatticeParams,
    ElectronicFeatures,
    PressureParams,
    RefinementReport,
    save_pattern_catalog,
    load_pattern_catalog,
)

logger = logging.getLogger("AgentCS")


# ---------------------------------------------------------------------------
# Known superconductor seed data (bootstrap knowledge base)
# ---------------------------------------------------------------------------

SEED_PATTERNS = [
    PatternCard(
        pattern_id="cuprate-layered-001",
        crystal_system="tetragonal",
        space_group="I4/mmm",
        lattice_params=LatticeParams(a=3.78, c=13.2),
        key_motifs=["CuO2 planes", "charge reservoir layers", "apical oxygen"],
        typical_Tc_range_K=[30, 135],
        source_compounds=["YBa2Cu3O7", "La2-xSrxCuO4", "Bi2Sr2CaCu2O8", "HgBa2Ca2Cu3O8"],
        dopant_sites=["La/Sr", "Ba/Y", "Ca"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.85,
            Fermi_surface="nested",
            electron_phonon_lambda=2.0,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=11.5, B0_GPa=120, B0_prime=4.5,
            gruneisen_gamma=2.0, eta_lambda=3.3, thermal_gruneisen=1.8,
            debye_T_K=410, dTc_dP_exp_K_per_GPa=-1.5,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=200.0,
            notes="Generic layered cuprate; dTc/dP ~ -1.5 K/GPa",
        ),
    ),
    PatternCard(
        pattern_id="cuprate-layered-002",
        crystal_system="orthorhombic",
        space_group="Pmmm",
        lattice_params=LatticeParams(a=3.82, b=3.89, c=11.68),
        key_motifs=["CuO2 planes", "CuO chains", "BaO layers"],
        typical_Tc_range_K=[89, 93],
        source_compounds=["YBa2Cu3O7-d"],
        dopant_sites=["O-chain"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.83,
            Fermi_surface="nested",
            electron_phonon_lambda=1.8,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=11.8, B0_GPa=115, B0_prime=4.5,
            gruneisen_gamma=2.0, eta_lambda=3.3, thermal_gruneisen=1.8,
            debye_T_K=400, dTc_dP_exp_K_per_GPa=-1.5,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=200.0,
            notes="YBCO orthorhombic; chains give slight anisotropy",
        ),
    ),
    PatternCard(
        pattern_id="iron-pnictide-001",
        crystal_system="tetragonal",
        space_group="I4/mmm",
        lattice_params=LatticeParams(a=3.96, c=13.0),
        key_motifs=["FeAs layers", "spacer layers", "tetrahedral Fe coordination"],
        typical_Tc_range_K=[26, 56],
        source_compounds=["LaFeAsO1-xFx", "BaFe2As2", "NaFeAs", "LiFeAs"],
        dopant_sites=["La/Ce", "O/F", "Ba/K"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.60,
            Fermi_surface="multi-band",
            electron_phonon_lambda=0.6,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=12.5, B0_GPa=85, B0_prime=4.0,
            gruneisen_gamma=1.5, eta_lambda=2.3, thermal_gruneisen=1.4,
            debye_T_K=300, dTc_dP_exp_K_per_GPa=2.0,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=80.0,
            notes="Iron pnictide 122; Tc increases under moderate P",
        ),
    ),
    PatternCard(
        pattern_id="iron-chalcogenide-001",
        crystal_system="tetragonal",
        space_group="P4/nmm",
        lattice_params=LatticeParams(a=3.77, c=5.52),
        key_motifs=["FeSe layers", "van der Waals gap"],
        typical_Tc_range_K=[8, 65],
        source_compounds=["FeSe", "FeSe0.5Te0.5", "FeSe/SrTiO3 monolayer"],
        dopant_sites=["Se/Te", "intercalation"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.58,
            Fermi_surface="multi-band",
            electron_phonon_lambda=0.5,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=13.5, B0_GPa=40, B0_prime=5.0,
            gruneisen_gamma=1.8, eta_lambda=-1.0, thermal_gruneisen=1.5,
            debye_T_K=230, dTc_dP_exp_K_per_GPa=9.0,
            P_min_GPa=0.0, P_max_GPa=15.0, Tc_ceiling_K=80.0,
            notes="FeSe: negative eta — spin-fluctuation enhancement under P",
        ),
    ),
    PatternCard(
        pattern_id="heavy-fermion-001",
        crystal_system="tetragonal",
        space_group="P4/mmm",
        lattice_params=LatticeParams(a=4.62, c=7.56),
        key_motifs=["CeIn3 layers", "CoIn2 layers", "f-electron hybridization"],
        typical_Tc_range_K=[0.5, 2.3],
        source_compounds=["CeCoIn5", "CeRhIn5", "CeIrIn5", "PuCoGa5"],
        dopant_sites=["Ce/Pu", "Co/Rh/Ir"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.45,
            Fermi_surface="heavy",
            electron_phonon_lambda=0.3,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=15.0, B0_GPa=80, B0_prime=4.5,
            gruneisen_gamma=2.2, eta_lambda=3.7, thermal_gruneisen=2.0,
            debye_T_K=180, dTc_dP_exp_K_per_GPa=None,
            P_min_GPa=0.0, P_max_GPa=10.0, Tc_ceiling_K=10.0,
            notes="Heavy fermion CeCoIn5; complex f-electron physics",
        ),
    ),
    PatternCard(
        pattern_id="mgb2-type-001",
        crystal_system="hexagonal",
        space_group="P6/mmm",
        lattice_params=LatticeParams(a=3.09, c=3.52),
        key_motifs=["graphene-like B layers", "Mg intercalation", "sigma bond phonons"],
        typical_Tc_range_K=[39, 39],
        source_compounds=["MgB2"],
        dopant_sites=["Mg/Al", "B/C"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="two-gap",
            electron_phonon_lambda=0.87,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=8.8, B0_GPa=150, B0_prime=3.8,
            gruneisen_gamma=2.3, eta_lambda=3.9, thermal_gruneisen=2.0,
            debye_T_K=750, dTc_dP_exp_K_per_GPa=-1.6,
            P_min_GPa=0.0, P_max_GPa=40.0, Tc_ceiling_K=80.0,
            notes="MgB2; sigma-bond phonons harden rapidly under P",
        ),
    ),
    PatternCard(
        pattern_id="a15-001",
        crystal_system="cubic",
        space_group="Pm-3n",
        lattice_params=LatticeParams(a=5.29, c=5.29),
        key_motifs=["A15 chain structure", "transition metal chains", "high DOS at Ef"],
        typical_Tc_range_K=[15, 23],
        source_compounds=["Nb3Sn", "Nb3Ge", "V3Si", "Nb3Al"],
        dopant_sites=["Nb/V", "Sn/Ge/Si"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.70,
            Fermi_surface="chain-like",
            electron_phonon_lambda=1.6,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=12.0, B0_GPa=170, B0_prime=4.2,
            gruneisen_gamma=1.9, eta_lambda=3.1, thermal_gruneisen=1.7,
            debye_T_K=350, dTc_dP_exp_K_per_GPa=-0.8,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=40.0,
            notes="A15 Nb3Sn; stiff lattice, Tc decreases slowly with P",
        ),
    ),
    PatternCard(
        pattern_id="hydride-001",
        crystal_system="cubic",
        space_group="Im-3m",
        lattice_params=LatticeParams(a=3.54, c=3.54),
        key_motifs=["H3S clathrate cage", "high-pressure stabilized", "hydrogen sublattice"],
        typical_Tc_range_K=[200, 288],
        source_compounds=["H3S", "LaH10", "YH6", "CaH6"],
        dopant_sites=["La/Y/Ca", "H content"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="isotropic",
            electron_phonon_lambda=2.2,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=4.0, B0_GPa=160, B0_prime=4.0,
            gruneisen_gamma=2.5, eta_lambda=1.5, thermal_gruneisen=2.2,
            debye_T_K=1500, dTc_dP_exp_K_per_GPa=None,
            P_min_GPa=100.0, P_max_GPa=300.0, Tc_ceiling_K=300.0,
            notes="H3S clathrate; only stable at extreme pressure",
        ),
    ),
    PatternCard(
        pattern_id="nickelate-001",
        crystal_system="tetragonal",
        space_group="I4/mmm",
        lattice_params=LatticeParams(a=3.92, c=12.7),
        key_motifs=["NiO2 planes", "rare-earth spacer", "infinite-layer analog"],
        typical_Tc_range_K=[9, 80],
        source_compounds=["Nd0.8Sr0.2NiO2", "La3Ni2O7", "La4Ni3O10"],
        dopant_sites=["Nd/La", "Sr doping", "O stoichiometry"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.78,
            Fermi_surface="cuprate-like",
            electron_phonon_lambda=1.0,
        ),
        nemad_magnetic_class="mixed",
        pressure_params=PressureParams(
            V0_per_atom_A3=10.5, B0_GPa=200, B0_prime=4.0,
            gruneisen_gamma=1.7, eta_lambda=2.7, thermal_gruneisen=1.5,
            debye_T_K=380, dTc_dP_exp_K_per_GPa=5.0,
            P_min_GPa=10.0, P_max_GPa=50.0, Tc_ceiling_K=120.0,
            notes="La3Ni2O7; SC onset at ~14 GPa",
        ),
    ),
    PatternCard(
        pattern_id="chevrel-001",
        crystal_system="trigonal",
        space_group="R-3",
        lattice_params=LatticeParams(a=6.54, c=6.54),
        key_motifs=["Mo6S8 clusters", "intercalant cavities", "cluster superconductivity"],
        typical_Tc_range_K=[1, 15],
        source_compounds=["PbMo6S8", "SnMo6S8", "Cu1.8Mo6S8"],
        dopant_sites=["Pb/Sn/Cu intercalant"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.55,
            Fermi_surface="cluster",
            electron_phonon_lambda=1.2,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=16.0, B0_GPa=90, B0_prime=5.0,
            gruneisen_gamma=1.6, eta_lambda=2.5, thermal_gruneisen=1.4,
            debye_T_K=250, dTc_dP_exp_K_per_GPa=-0.5,
            P_min_GPa=0.0, P_max_GPa=20.0, Tc_ceiling_K=20.0,
            notes="Chevrel PbMo6S8; soft cluster lattice",
        ),
    ),
    # --- Additional patterns for family diversity ---
    PatternCard(
        pattern_id="cuprate-multilayer-001",
        crystal_system="tetragonal",
        space_group="I4/mmm",
        lattice_params=LatticeParams(a=3.81, c=30.6),
        key_motifs=["CuO2-planes", "BiO-layers", "SrO-layers", "multi-layer-stacking"],
        typical_Tc_range_K=[85, 133],
        source_compounds=["Bi2Sr2CaCu2O8", "HgBa2Ca2Cu3O8", "Tl2Ba2Ca2Cu3O10"],
        dopant_sites=["Ca/Sr", "O stoichiometry"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.85,
            Fermi_surface="nested",
            electron_phonon_lambda=1.5,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=11.2, B0_GPa=125, B0_prime=4.5,
            gruneisen_gamma=2.0, eta_lambda=3.3, thermal_gruneisen=1.8,
            debye_T_K=420, dTc_dP_exp_K_per_GPa=-1.2,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=200.0,
            notes="Multi-layer cuprate; Hg-1223 has highest ambient Tc",
        ),
    ),
    PatternCard(
        pattern_id="hydride-lah10-001",
        crystal_system="cubic",
        space_group="Fm-3m",
        lattice_params=LatticeParams(a=5.10, c=5.10),
        key_motifs=["H-cage", "La-center", "clathrate", "sodalite-like"],
        typical_Tc_range_K=[240, 260],
        source_compounds=["LaH10"],
        dopant_sites=["La/Y/Ce", "H content"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="isotropic",
            electron_phonon_lambda=2.5,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=5.5, B0_GPa=180, B0_prime=4.0,
            gruneisen_gamma=2.5, eta_lambda=1.5, thermal_gruneisen=2.2,
            debye_T_K=1600, dTc_dP_exp_K_per_GPa=None,
            P_min_GPa=130.0, P_max_GPa=250.0, Tc_ceiling_K=300.0,
            notes="LaH10 sodalite cage; requires >130 GPa",
        ),
    ),
    # =======================================================================
    # RTAP-TARGETED SEED PATTERNS — New families for RT-SC discovery
    # =======================================================================
    PatternCard(
        pattern_id="kagome-001",
        crystal_system="hexagonal",
        space_group="P6/mmm",
        lattice_params=LatticeParams(a=5.50, c=9.31),
        key_motifs=["V3Sb5 kagome net", "van Hove singularity", "charge density wave",
                    "sublattice frustration", "flat band near Ef"],
        typical_Tc_range_K=[0.9, 2.5],
        source_compounds=["CsV3Sb5", "KV3Sb5", "RbV3Sb5"],
        dopant_sites=["Cs/K/Rb", "Sb/Sn/Bi", "V/Ti/Nb"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.50,
            Fermi_surface="kagome-flat-band",
            electron_phonon_lambda=0.6,
            pairing_mechanism="mixed",
            flat_band_width_eV=0.02,
            nesting_strength=0.85,
            van_hove_distance_eV=0.01,
            dos_at_ef_states_eV=5.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=18.0, B0_GPa=50, B0_prime=5.0,
            gruneisen_gamma=1.5, eta_lambda=2.0, thermal_gruneisen=1.3,
            debye_T_K=250, dTc_dP_exp_K_per_GPa=4.0,
            P_min_GPa=0.0, P_max_GPa=10.0, Tc_ceiling_K=80.0,
            notes="CsV3Sb5 kagome; Tc increases with P, CDW suppressed",
        ),
    ),
    PatternCard(
        pattern_id="kagome-002",
        crystal_system="hexagonal",
        space_group="P6/mmm",
        lattice_params=LatticeParams(a=5.47, c=9.15),
        key_motifs=["kagome net", "Nb d-band", "enhanced flat band", "CDW competitor"],
        typical_Tc_range_K=[1.0, 5.0],
        source_compounds=["CsNb3Sb5", "RbNb3Bi5"],
        dopant_sites=["Cs/Rb", "Nb/Ta", "Sb/Bi"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.45,
            Fermi_surface="kagome-flat-band",
            electron_phonon_lambda=0.8,
            pairing_mechanism="mixed",
            flat_band_width_eV=0.015,
            nesting_strength=0.80,
            van_hove_distance_eV=0.02,
            dos_at_ef_states_eV=6.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=17.5, B0_GPa=55, B0_prime=5.0,
            gruneisen_gamma=1.6, eta_lambda=2.1, thermal_gruneisen=1.4,
            debye_T_K=260, dTc_dP_exp_K_per_GPa=3.5,
            P_min_GPa=0.0, P_max_GPa=10.0, Tc_ceiling_K=80.0,
            notes="Nb-kagome variant; heavier d-electrons may enhance pairing",
        ),
    ),
    PatternCard(
        pattern_id="ternary-hydride-001",
        crystal_system="cubic",
        space_group="Pm-3m",
        lattice_params=LatticeParams(a=4.80, c=4.80),
        key_motifs=["H-cage clathrate", "chemical pre-compression",
                    "light-element stabilizer", "ambient-metastable H sublattice"],
        typical_Tc_range_K=[50, 200],
        source_compounds=["LaBH8", "CaBeH8", "SrSiH8", "BaSiH8"],
        dopant_sites=["La/Ca/Sr/Ba", "B/Be/Si", "H content"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="isotropic",
            electron_phonon_lambda=2.2,
            pairing_mechanism="hydride_cage",
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=6.0, B0_GPa=100, B0_prime=4.5,
            gruneisen_gamma=2.3, eta_lambda=2.0, thermal_gruneisen=2.0,
            debye_T_K=1200, dTc_dP_exp_K_per_GPa=None,
            P_min_GPa=0.0, P_max_GPa=50.0, Tc_ceiling_K=350.0,
            notes="Target: ternary hydrides at <10 GPa via strong chemical pre-compression",
        ),
    ),
    PatternCard(
        pattern_id="ternary-hydride-002",
        crystal_system="cubic",
        space_group="Fm-3m",
        lattice_params=LatticeParams(a=5.20, c=5.20),
        key_motifs=["sodalite H-cage", "covalent B-H network", "clathrate-like",
                    "electronegativity-driven pre-compression"],
        typical_Tc_range_K=[80, 250],
        source_compounds=["YBH8", "ScBH8", "LaCH8"],
        dopant_sites=["Y/Sc/La", "B/C/N", "H stoichiometry"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="isotropic",
            electron_phonon_lambda=2.0,
            pairing_mechanism="hydride_cage",
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=5.5, B0_GPa=120, B0_prime=4.5,
            gruneisen_gamma=2.4, eta_lambda=1.8, thermal_gruneisen=2.1,
            debye_T_K=1400, dTc_dP_exp_K_per_GPa=None,
            P_min_GPa=0.0, P_max_GPa=80.0, Tc_ceiling_K=280.0,
            notes="Sodalite-type ternary hydride; B-H covalent cage aids stability",
        ),
    ),
    PatternCard(
        pattern_id="infinite-layer-001",
        crystal_system="tetragonal",
        space_group="P4/mmm",
        lattice_params=LatticeParams(a=3.92, c=3.37),
        key_motifs=["NiO2 square-planar planes", "R-site charge reservoir",
                    "d^(9-delta) filling", "cuprate-analog electronic structure"],
        typical_Tc_range_K=[9, 30],
        source_compounds=["Nd0.8Sr0.2NiO2", "La0.8Sr0.2NiO2", "Pr0.8Sr0.2NiO2"],
        dopant_sites=["Nd/La/Pr", "Sr/Ca doping level"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.82,
            Fermi_surface="cuprate-like",
            electron_phonon_lambda=1.2,
            pairing_mechanism="spin_fluctuation",
            spin_fluctuation_T_K=450,
            nesting_strength=0.82,
            dos_at_ef_states_eV=5.0,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=9.0, B0_GPa=180, B0_prime=4.0,
            gruneisen_gamma=1.8, eta_lambda=2.8, thermal_gruneisen=1.6,
            debye_T_K=350, dTc_dP_exp_K_per_GPa=2.0,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=500.0,
            notes="Infinite-layer nickelate; cuprate analog with 3d9 config",
        ),
    ),
    PatternCard(
        pattern_id="topological-001",
        crystal_system="trigonal",
        space_group="R-3m",
        lattice_params=LatticeParams(a=4.14, c=28.6),
        key_motifs=["topological surface states", "Dirac cone at Gamma",
                    "bulk-boundary correspondence", "strong spin-orbit coupling"],
        typical_Tc_range_K=[0.5, 4.0],
        source_compounds=["Bi2Se3-Cux", "Bi2Te3-Srx", "FeTe0.55Se0.45"],
        dopant_sites=["Cu/Sr intercalant", "Se/Te ratio"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.40,
            Fermi_surface="topological-surface",
            electron_phonon_lambda=0.9,
            pairing_mechanism="spin_fluctuation",
            topological_index=1,
            nesting_strength=0.75,
            spin_fluctuation_T_K=350.0,
            dos_at_ef_states_eV=5.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=22.0, B0_GPa=35, B0_prime=5.5,
            gruneisen_gamma=1.8, eta_lambda=2.5, thermal_gruneisen=1.5,
            debye_T_K=160, dTc_dP_exp_K_per_GPa=1.5,
            P_min_GPa=0.0, P_max_GPa=10.0, Tc_ceiling_K=500.0,
            notes="Topological SC with spin-fluctuation pairing; SOC + surface states",
        ),
    ),
    PatternCard(
        pattern_id="2d-heterostructure-001",
        crystal_system="hexagonal",
        space_group="P6/mmm",
        lattice_params=LatticeParams(a=2.46, c=6.70),
        key_motifs=["twisted bilayer", "moire flat bands", "van Hove proximity",
                    "correlated insulator neighbor", "twist-angle tunable"],
        typical_Tc_range_K=[1.0, 3.0],
        source_compounds=["TBLG-1.1deg", "TBG-WSe2", "TTG-1.6deg"],
        dopant_sites=["twist angle", "dielectric environment", "gate voltage"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.50,
            Fermi_surface="moire-flat",
            electron_phonon_lambda=1.0,
            pairing_mechanism="flat_band",
            flat_band_width_eV=0.003,
            nesting_strength=0.80,
            van_hove_distance_eV=0.002,
            dos_at_ef_states_eV=10.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=8.8, B0_GPa=30, B0_prime=8.0,
            gruneisen_gamma=1.0, eta_lambda=1.5, thermal_gruneisen=1.0,
            debye_T_K=200, dTc_dP_exp_K_per_GPa=0.5,
            P_min_GPa=0.0, P_max_GPa=5.0, Tc_ceiling_K=500.0,
            notes="Twisted bilayer graphene; ultra-flat bands at magic angle",
        ),
    ),
    PatternCard(
        pattern_id="carbon-based-001",
        crystal_system="cubic",
        space_group="Fm-3m",
        lattice_params=LatticeParams(a=14.04, c=14.04),
        key_motifs=["C60 cage", "alkali intercalation", "t1u LUMO band",
                    "Jahn-Teller phonons", "molecular superconductor"],
        typical_Tc_range_K=[18, 38],
        source_compounds=["Cs3C60", "K3C60", "Rb3C60"],
        dopant_sites=["Cs/K/Rb intercalant", "C60 substitution"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="molecular-t1u",
            electron_phonon_lambda=0.9,
            pairing_mechanism="flat_band",
            flat_band_width_eV=0.04,
            dos_at_ef_states_eV=4.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=12.0, B0_GPa=20, B0_prime=8.0,
            gruneisen_gamma=2.0, eta_lambda=3.0, thermal_gruneisen=1.5,
            debye_T_K=500, dTc_dP_exp_K_per_GPa=-0.3,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=60.0,
            notes="Alkali-doped fullerides; Jahn-Teller + s-wave BCS",
        ),
    ),
    PatternCard(
        pattern_id="carbon-based-002",
        crystal_system="hexagonal",
        space_group="P6/mmm",
        lattice_params=LatticeParams(a=2.50, c=5.40),
        key_motifs=["graphite intercalation", "alkali-earth donor layers",
                    "pi-band metallization", "phonon-mediated"],
        typical_Tc_range_K=[6, 12],
        source_compounds=["CaC6", "YbC6", "BaC6"],
        dopant_sites=["Ca/Yb/Ba intercalant", "graphene layers"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.0,
            Fermi_surface="pi-band",
            electron_phonon_lambda=1.0,
            pairing_mechanism="flat_band",
            flat_band_width_eV=0.03,
            dos_at_ef_states_eV=5.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=10.0, B0_GPa=40, B0_prime=6.0,
            gruneisen_gamma=1.8, eta_lambda=2.8, thermal_gruneisen=1.4,
            debye_T_K=400, dTc_dP_exp_K_per_GPa=0.5,
            P_min_GPa=0.0, P_max_GPa=20.0, Tc_ceiling_K=500.0,
            notes="Graphite intercalation with flat-band enhancement; pi-band + interlayer phonons",
        ),
    ),
    PatternCard(
        pattern_id="engineered-cuprate-001",
        crystal_system="tetragonal",
        space_group="I4/mmm",
        lattice_params=LatticeParams(a=3.84, c=40.0),
        key_motifs=["5+ CuO2 planes", "optimized charge reservoir",
                    "interface-enhanced pairing", "strain-tuned c/a ratio",
                    "Hg-based multilayer architecture"],
        typical_Tc_range_K=[130, 180],
        source_compounds=["HgBa2Ca4Cu5O12+d", "TlBa2Ca4Cu5O13"],
        dopant_sites=["Ca count", "Hg/Tl reservoir", "O stoichiometry", "CuO2 layer count"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.84,
            Fermi_surface="nested",
            electron_phonon_lambda=2.2,
            pairing_mechanism="spin_fluctuation",
            spin_fluctuation_T_K=500,
            nesting_strength=0.85,
            dos_at_ef_states_eV=4.5,
        ),
        nemad_magnetic_class="AFM",
        pressure_params=PressureParams(
            V0_per_atom_A3=10.8, B0_GPa=130, B0_prime=4.5,
            gruneisen_gamma=2.0, eta_lambda=3.2, thermal_gruneisen=1.8,
            debye_T_K=430, dTc_dP_exp_K_per_GPa=-1.0,
            P_min_GPa=0.0, P_max_GPa=30.0, Tc_ceiling_K=250.0,
            notes="Engineered 5-layer cuprate; pushing beyond Hg-1223 record",
        ),
    ),
    PatternCard(
        pattern_id="mof-sc-001",
        crystal_system="hexagonal",
        space_group="P6/mmm",
        lattice_params=LatticeParams(a=8.76, c=3.39),
        key_motifs=["metal-organic framework", "kagome-like Cu lattice",
                    "BHT organic linker", "designed Fermi surface topology",
                    "excitonic pairing mediator"],
        typical_Tc_range_K=[1.0, 30.0],
        source_compounds=["Cu3(BHT)2", "Ni3(HITP)2", "Fe3(THT)2"],
        dopant_sites=["Cu/Ni/Fe metal node", "organic linker choice", "guest molecules"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.50,
            Fermi_surface="kagome-derived",
            electron_phonon_lambda=0.4,
            pairing_mechanism="excitonic",
            flat_band_width_eV=0.05,
            exciton_energy_eV=0.5,
            excitonic_coupling_V=0.3,
            dos_at_ef_states_eV=3.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=20.0, B0_GPa=15, B0_prime=10.0,
            gruneisen_gamma=1.0, eta_lambda=1.5, thermal_gruneisen=0.8,
            debye_T_K=150, dTc_dP_exp_K_per_GPa=0.5,
            P_min_GPa=0.0, P_max_GPa=5.0, Tc_ceiling_K=100.0,
            notes="Cu3(BHT)2 MOF; designed electronic topology with organic linkers",
        ),
    ),
    PatternCard(
        pattern_id="flat-band-001",
        crystal_system="tetragonal",
        space_group="P4/mmm",
        lattice_params=LatticeParams(a=4.20, c=6.80),
        key_motifs=["Lieb lattice analog", "flat band at Ef",
                    "singular DOS", "geometric frustration", "orbital selectivity"],
        typical_Tc_range_K=[5, 100],
        source_compounds=["LaRu3Si2", "CeRu2", "ScV6Sn6"],
        dopant_sites=["La/Ce/Sc", "Ru/V metal", "Si/Sn"],
        electronic_features=ElectronicFeatures(
            d_band_filling=0.55,
            Fermi_surface="flat-band-singular",
            electron_phonon_lambda=1.0,
            pairing_mechanism="flat_band",
            flat_band_width_eV=0.03,
            nesting_strength=0.65,
            van_hove_distance_eV=0.005,
            dos_at_ef_states_eV=7.0,
        ),
        nemad_magnetic_class="NM",
        pressure_params=PressureParams(
            V0_per_atom_A3=14.0, B0_GPa=80, B0_prime=4.5,
            gruneisen_gamma=1.5, eta_lambda=2.2, thermal_gruneisen=1.3,
            debye_T_K=300, dTc_dP_exp_K_per_GPa=1.0,
            P_min_GPa=0.0, P_max_GPa=20.0, Tc_ceiling_K=200.0,
            notes="Generic flat-band SC; Tc enhanced by singular DOS at Ef",
        ),
    ),
]


# ---------------------------------------------------------------------------
# NEMAD feature engineering
# ---------------------------------------------------------------------------

# Element properties for feature generation (subset of periodic table)
ELEMENT_DATA = {
    "H": {"Z": 1, "weight": 1.008, "electronegativity": 2.20, "period": 1, "group": 1},
    "Li": {"Z": 3, "weight": 6.941, "electronegativity": 0.98, "period": 2, "group": 1},
    "B": {"Z": 5, "weight": 10.81, "electronegativity": 2.04, "period": 2, "group": 13},
    "C": {"Z": 6, "weight": 12.01, "electronegativity": 2.55, "period": 2, "group": 14},
    "N": {"Z": 7, "weight": 14.01, "electronegativity": 3.04, "period": 2, "group": 15},
    "O": {"Z": 8, "weight": 16.00, "electronegativity": 3.44, "period": 2, "group": 16},
    "F": {"Z": 9, "weight": 19.00, "electronegativity": 3.98, "period": 2, "group": 17},
    "Na": {"Z": 11, "weight": 22.99, "electronegativity": 0.93, "period": 3, "group": 1},
    "Mg": {"Z": 12, "weight": 24.31, "electronegativity": 1.31, "period": 3, "group": 2},
    "Al": {"Z": 13, "weight": 26.98, "electronegativity": 1.61, "period": 3, "group": 13},
    "Si": {"Z": 14, "weight": 28.09, "electronegativity": 1.90, "period": 3, "group": 14},
    "P": {"Z": 15, "weight": 30.97, "electronegativity": 2.19, "period": 3, "group": 15},
    "S": {"Z": 16, "weight": 32.07, "electronegativity": 2.58, "period": 3, "group": 16},
    "K": {"Z": 19, "weight": 39.10, "electronegativity": 0.82, "period": 4, "group": 1},
    "Ca": {"Z": 20, "weight": 40.08, "electronegativity": 1.00, "period": 4, "group": 2},
    "Sc": {"Z": 21, "weight": 44.96, "electronegativity": 1.36, "period": 4, "group": 3},
    "Ti": {"Z": 22, "weight": 47.87, "electronegativity": 1.54, "period": 4, "group": 4},
    "V": {"Z": 23, "weight": 50.94, "electronegativity": 1.63, "period": 4, "group": 5},
    "Cr": {"Z": 24, "weight": 52.00, "electronegativity": 1.66, "period": 4, "group": 6},
    "Mn": {"Z": 25, "weight": 54.94, "electronegativity": 1.55, "period": 4, "group": 7},
    "Fe": {"Z": 26, "weight": 55.85, "electronegativity": 1.83, "period": 4, "group": 8},
    "Co": {"Z": 27, "weight": 58.93, "electronegativity": 1.88, "period": 4, "group": 9},
    "Ni": {"Z": 28, "weight": 58.69, "electronegativity": 1.91, "period": 4, "group": 10},
    "Cu": {"Z": 29, "weight": 63.55, "electronegativity": 1.90, "period": 4, "group": 11},
    "Zn": {"Z": 30, "weight": 65.38, "electronegativity": 1.65, "period": 4, "group": 12},
    "Ga": {"Z": 31, "weight": 69.72, "electronegativity": 1.81, "period": 4, "group": 13},
    "Ge": {"Z": 32, "weight": 72.63, "electronegativity": 2.01, "period": 4, "group": 14},
    "As": {"Z": 33, "weight": 74.92, "electronegativity": 2.18, "period": 4, "group": 15},
    "Se": {"Z": 34, "weight": 78.97, "electronegativity": 2.55, "period": 4, "group": 16},
    "Sr": {"Z": 38, "weight": 87.62, "electronegativity": 0.95, "period": 5, "group": 2},
    "Y": {"Z": 39, "weight": 88.91, "electronegativity": 1.22, "period": 5, "group": 3},
    "Zr": {"Z": 40, "weight": 91.22, "electronegativity": 1.33, "period": 5, "group": 4},
    "Nb": {"Z": 41, "weight": 92.91, "electronegativity": 1.60, "period": 5, "group": 5},
    "Mo": {"Z": 42, "weight": 95.95, "electronegativity": 2.16, "period": 5, "group": 6},
    "Ru": {"Z": 44, "weight": 101.1, "electronegativity": 2.20, "period": 5, "group": 8},
    "Rh": {"Z": 45, "weight": 102.9, "electronegativity": 2.28, "period": 5, "group": 9},
    "Pd": {"Z": 46, "weight": 106.4, "electronegativity": 2.20, "period": 5, "group": 10},
    "Sn": {"Z": 50, "weight": 118.7, "electronegativity": 1.96, "period": 5, "group": 14},
    "Te": {"Z": 52, "weight": 127.6, "electronegativity": 2.10, "period": 5, "group": 16},
    "Ba": {"Z": 56, "weight": 137.3, "electronegativity": 0.89, "period": 6, "group": 2},
    "La": {"Z": 57, "weight": 138.9, "electronegativity": 1.10, "period": 6, "group": 3},
    "Ce": {"Z": 58, "weight": 140.1, "electronegativity": 1.12, "period": 6, "group": 3},
    "Nd": {"Z": 60, "weight": 144.2, "electronegativity": 1.14, "period": 6, "group": 3},
    "Sm": {"Z": 62, "weight": 150.4, "electronegativity": 1.17, "period": 6, "group": 3},
    "Eu": {"Z": 63, "weight": 152.0, "electronegativity": 1.20, "period": 6, "group": 3},
    "Gd": {"Z": 64, "weight": 157.3, "electronegativity": 1.20, "period": 6, "group": 3},
    "Yb": {"Z": 70, "weight": 173.0, "electronegativity": 1.10, "period": 6, "group": 3},
    "Hf": {"Z": 72, "weight": 178.5, "electronegativity": 1.30, "period": 6, "group": 4},
    "Ta": {"Z": 73, "weight": 180.9, "electronegativity": 1.50, "period": 6, "group": 5},
    "W": {"Z": 74, "weight": 183.8, "electronegativity": 2.36, "period": 6, "group": 6},
    "Ir": {"Z": 77, "weight": 192.2, "electronegativity": 2.20, "period": 6, "group": 9},
    "Pt": {"Z": 78, "weight": 195.1, "electronegativity": 2.28, "period": 6, "group": 10},
    "Hg": {"Z": 80, "weight": 200.6, "electronegativity": 2.00, "period": 6, "group": 12},
    "Tl": {"Z": 81, "weight": 204.4, "electronegativity": 1.62, "period": 6, "group": 13},
    "Pb": {"Z": 82, "weight": 207.2, "electronegativity": 2.33, "period": 6, "group": 14},
    "Bi": {"Z": 83, "weight": 209.0, "electronegativity": 2.02, "period": 6, "group": 15},
    "Pu": {"Z": 94, "weight": 244.0, "electronegativity": 1.28, "period": 7, "group": 3},
    "In": {"Z": 49, "weight": 114.8, "electronegativity": 1.78, "period": 5, "group": 13},
    # Additional elements for RTAP families
    "Be": {"Z": 4, "weight": 9.012, "electronegativity": 1.57, "period": 2, "group": 2},
    "Cs": {"Z": 55, "weight": 132.9, "electronegativity": 0.79, "period": 6, "group": 1},
    "Rb": {"Z": 37, "weight": 85.47, "electronegativity": 0.82, "period": 5, "group": 1},
    "Sb": {"Z": 51, "weight": 121.8, "electronegativity": 2.05, "period": 5, "group": 15},
    "Ag": {"Z": 47, "weight": 107.9, "electronegativity": 1.93, "period": 5, "group": 11},
    "Cd": {"Z": 48, "weight": 112.4, "electronegativity": 1.69, "period": 5, "group": 12},
    "Pr": {"Z": 59, "weight": 140.9, "electronegativity": 1.13, "period": 6, "group": 3},
    "Tb": {"Z": 65, "weight": 158.9, "electronegativity": 1.20, "period": 6, "group": 3},
    "Dy": {"Z": 66, "weight": 162.5, "electronegativity": 1.22, "period": 6, "group": 3},
    "Er": {"Z": 68, "weight": 167.3, "electronegativity": 1.24, "period": 6, "group": 3},
    "Lu": {"Z": 71, "weight": 175.0, "electronegativity": 1.27, "period": 6, "group": 3},
    "Tc": {"Z": 43, "weight": 98.0, "electronegativity": 1.90, "period": 5, "group": 7},
    "Re": {"Z": 75, "weight": 186.2, "electronegativity": 1.90, "period": 6, "group": 7},
    "Os": {"Z": 76, "weight": 190.2, "electronegativity": 2.20, "period": 6, "group": 8},
    "Au": {"Z": 79, "weight": 197.0, "electronegativity": 2.54, "period": 6, "group": 11},
}

MAGNETIC_ELEMENTS = {"Cr", "Mn", "Fe", "Co", "Ni", "Gd", "Eu", "Nd", "Sm", "Ce", "Yb", "Pu"}
RARE_EARTH = {"La", "Ce", "Nd", "Sm", "Eu", "Gd", "Yb"}


def parse_composition(formula: str) -> dict[str, float]:
    """Parse simple formulas like 'YBa2Cu3O7' into {element: count}."""
    import re

    pattern = r"([A-Z][a-z]?)(\d*\.?\d*)"
    matches = re.findall(pattern, formula)
    comp = {}
    for elem, count in matches:
        if elem:
            comp[elem] = float(count) if count else 1.0
    return comp


def compute_feature_vector(composition: dict[str, float]) -> list[float]:
    """
    Generate a NEMAD-compatible feature vector from an element:count composition.
    Returns: [avg_weight, avg_electronegativity, total_electrons, num_atoms,
              avg_atomic_number, avg_period, avg_magnetic_moment_proxy,
              avg_group, entropy, magnetic_proportion, rare_earth_proportion]
    """
    total_atoms = sum(composition.values())
    if total_atoms == 0:
        return [0.0] * 11

    avg_weight = 0.0
    avg_en = 0.0
    total_electrons = 0.0
    avg_Z = 0.0
    avg_period = 0.0
    avg_group = 0.0
    magnetic_count = 0.0
    re_count = 0.0

    for elem, count in composition.items():
        props = ELEMENT_DATA.get(elem, {})
        frac = count / total_atoms
        avg_weight += props.get("weight", 0) * frac
        avg_en += props.get("electronegativity", 0) * frac
        total_electrons += props.get("Z", 0) * count
        avg_Z += props.get("Z", 0) * frac
        avg_period += props.get("period", 0) * frac
        avg_group += props.get("group", 0) * frac
        if elem in MAGNETIC_ELEMENTS:
            magnetic_count += count
        if elem in RARE_EARTH:
            re_count += count

    # Compositional entropy
    fracs = [c / total_atoms for c in composition.values() if c > 0]
    entropy = -sum(f * np.log(f) for f in fracs if f > 0)

    return [
        round(avg_weight, 4),
        round(avg_en, 4),
        round(total_electrons, 1),
        round(total_atoms, 1),
        round(avg_Z, 4),
        round(avg_period, 4),
        round(magnetic_count / total_atoms, 4),  # proxy for magnetic moment
        round(avg_group, 4),
        round(entropy, 5),
        round(magnetic_count / total_atoms, 5),
        round(re_count / total_atoms, 5),
    ]


# ---------------------------------------------------------------------------
# NEMAD data loading
# ---------------------------------------------------------------------------

def load_nemad_classification_data() -> Optional[pd.DataFrame]:
    """Load the NEMAD classification dataset if available."""
    csv_path = NEMAD_DATASET_DIR / "Classification_FM_AFM_NM.csv"
    if csv_path.exists():
        logger.info(f"Loading NEMAD classification data from {csv_path}")
        return pd.read_csv(csv_path)
    logger.warning(f"NEMAD classification data not found at {csv_path}")
    return None


def load_nemad_curie_data() -> Optional[pd.DataFrame]:
    """Load NEMAD Curie temperature dataset."""
    csv_path = NEMAD_DATASET_DIR / "FM_with_curie.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None


def load_nemad_neel_data() -> Optional[pd.DataFrame]:
    """Load NEMAD Néel temperature dataset."""
    csv_path = NEMAD_DATASET_DIR / "AFM_with_Neel.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None


# ---------------------------------------------------------------------------
# Agent CS main logic
# ---------------------------------------------------------------------------

class AgentCS:
    """Crystal Structure Agent — curates pattern catalog."""

    def __init__(self):
        ensure_dirs()
        self.patterns: list[PatternCard] = []
        self.nemad_df: Optional[pd.DataFrame] = None

    def bootstrap(self) -> list[PatternCard]:
        """Initialize patterns from seed knowledge + NEMAD data."""
        logger.info("Bootstrapping crystal pattern catalog from seeds...")
        self.patterns = list(SEED_PATTERNS)

        # Enrich with NEMAD feature vectors
        for p in self.patterns:
            if p.source_compounds:
                comp = parse_composition(p.source_compounds[0])
                p.feature_vector = compute_feature_vector(comp)

        # Load NEMAD for cross-referencing
        self.nemad_df = load_nemad_classification_data()
        if self.nemad_df is not None:
            logger.info(f"Loaded NEMAD with {len(self.nemad_df)} entries for cross-reference")

        return self.patterns

    def apply_refinements(self, report: RefinementReport) -> list[PatternCard]:
        """Apply refinements from Agent Ob that target Agent CS."""
        cs_refinements = [r for r in report.refinements if r.target_agent == "CS"]
        if not cs_refinements:
            logger.info("No refinements targeting Agent CS this iteration.")
            return self.patterns

        for ref in cs_refinements:
            logger.info(f"Applying refinement: {ref.action} — {ref.detail}")

            if ref.action == "expand_pattern" and ref.pattern_id:
                self._expand_pattern(ref.pattern_id, ref.detail)
            elif ref.action == "add_constraint" and ref.pattern_id:
                self._add_constraint(ref.pattern_id, ref.detail)
            elif ref.action == "remove_pattern" and ref.pattern_id:
                self.patterns = [p for p in self.patterns if p.pattern_id != ref.pattern_id]
                logger.info(f"Removed pattern {ref.pattern_id}")

        return self.patterns

    def _expand_pattern(self, pattern_id: str, detail: str):
        """Add new source compounds or motifs to an existing pattern."""
        for p in self.patterns:
            if p.pattern_id == pattern_id:
                # Parse detail for new compounds or dopants
                p.key_motifs.append(f"[expanded] {detail}")
                logger.info(f"Expanded pattern {pattern_id}: {detail}")
                return
        logger.warning(f"Pattern {pattern_id} not found for expansion")

    def _add_constraint(self, pattern_id: str, detail: str):
        """Add tighter constraints to a pattern based on discrepancy analysis."""
        for p in self.patterns:
            if p.pattern_id == pattern_id:
                p.key_motifs.append(f"[constraint] {detail}")
                logger.info(f"Added constraint to {pattern_id}: {detail}")
                return

    def save_catalog(self, version: int) -> Path:
        """Save current patterns to versioned catalog file."""
        filename = f"pattern_catalog_v{version:03d}.json"
        path = CRYSTAL_PATTERNS_DIR / filename
        save_pattern_catalog(self.patterns, path, version)
        logger.info(f"Saved pattern catalog v{version:03d} with {len(self.patterns)} patterns to {path}")
        return path

    def get_latest_catalog_path(self) -> Optional[Path]:
        """Find the most recent pattern catalog file."""
        catalogs = sorted(CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"))
        return catalogs[-1] if catalogs else None

    def classify_magnetic_phase(self, composition: dict[str, float]) -> str:
        """Use NEMAD-style heuristic to classify magnetic phase."""
        mag_frac = sum(
            count for elem, count in composition.items() if elem in MAGNETIC_ELEMENTS
        ) / max(sum(composition.values()), 1)

        if mag_frac > 0.3:
            return "FM"  # Likely ferromagnetic
        elif mag_frac > 0.1:
            return "AFM"  # Likely antiferromagnetic
        return "NM"

    def identify_gaps(self) -> list[dict]:
        """Identify underexplored regions of crystal-chemistry space."""
        gaps = []

        # Check which families have few patterns
        family_counts = {}
        for p in self.patterns:
            family = p.pattern_id.split("-")[0]
            family_counts[family] = family_counts.get(family, 0) + 1

        for family in SC_FAMILIES:
            base = family.replace("-", "")
            count = sum(v for k, v in family_counts.items() if base in k.replace("-", ""))
            if count < 2:
                gaps.append({
                    "family": family,
                    "current_patterns": count,
                    "suggestion": f"Expand {family} family with additional structural variants",
                })

        return gaps

    def identify_rtap_gaps(self) -> list[dict]:
        """Identify underexplored families for RTAP (room-temperature ambient-pressure) discovery."""
        gaps = []

        # High-priority RTAP families
        HIGH_RTAP_POTENTIAL = {"ternary-hydride", "engineered-cuprate", "flat-band", "kagome"}
        MEDIUM_RTAP_POTENTIAL = {"infinite-layer", "mof-sc", "carbon-based"}

        family_counts = {}
        for p in self.patterns:
            # Match pattern_id prefix to RTAP family names
            pid = p.pattern_id
            for fam in RTAP_FAMILIES:
                fam_prefix = fam.replace("-", "")
                pid_prefix = pid.split("-")[0].replace("-", "")
                # Also match multi-word: "ternary-hydride" -> "ternaryhydride" vs "ternary"
                if pid_prefix == fam_prefix or pid.startswith(fam):
                    family_counts[fam] = family_counts.get(fam, 0) + 1

        for family in RTAP_FAMILIES:
            count = family_counts.get(family, 0)
            if count < 2:
                if family in HIGH_RTAP_POTENTIAL:
                    potential = "high"
                elif family in MEDIUM_RTAP_POTENTIAL:
                    potential = "medium"
                else:
                    potential = "low"
                gaps.append({
                    "family": family,
                    "current_patterns": count,
                    "rtap_potential": potential,
                    "suggestion": f"Expand {family} with composition variants targeting ambient-P stability",
                })

        return gaps


def run_agent_cs(iteration: int) -> Path:
    """
    Main entry point for Agent CS.
    Called by the orchestrator each iteration.
    Returns path to the saved pattern catalog.
    """
    agent = AgentCS()

    if iteration == 0:
        agent.bootstrap()
    else:
        # Load previous iteration's catalog (not "latest" which may be stale)
        prev_catalog = CRYSTAL_PATTERNS_DIR / f"pattern_catalog_v{iteration - 1:03d}.json"
        if not prev_catalog.exists():
            prev_catalog = agent.get_latest_catalog_path()
        if prev_catalog:
            agent.patterns = load_pattern_catalog(prev_catalog)
            logger.info(f"Loaded {len(agent.patterns)} patterns from {prev_catalog}")

        # Load and apply refinements
        ref_path = REFINEMENTS_DIR / f"iteration_{iteration - 1:03d}.json"
        if ref_path.exists():
            report = RefinementReport.load(ref_path)
            agent.apply_refinements(report)

    catalog_path = agent.save_catalog(iteration)

    # Log gap analysis
    gaps = agent.identify_gaps()
    if gaps:
        logger.info(f"Identified {len(gaps)} gaps in crystal-chemistry space")
        for g in gaps:
            logger.info(f"  Gap: {g['family']} ({g['current_patterns']} patterns) — {g['suggestion']}")

    return catalog_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = run_agent_cs(iteration=0)
    print(f"Catalog saved to: {path}")
