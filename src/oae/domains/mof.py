"""MOF domain pack (Phase D).

A pluggable :class:`DomainPack` for Metal-Organic Frameworks. Provides:

* 14 curated MOF families (ZIF, UiO, MIL, HKUST, IRMOF, PCN, NU, CAU,
  Zr-porphyrin, MOF-74, ZIF-derivatives, CPL, IL-MOF, mixed-linker).
* Score weights aligned with the Phase D plan:
  porosity, surface area, thermal stability, water stability,
  target affinity, synthesizability, composition validity.
* Seed patterns that combine SBUs, linkers, and RCSR topologies from
  :mod:`src.oae.domains.mof_libraries`.
* Validation criteria for the downstream verifier and Agent R.

The pack self-registers with the legacy domain-pack registry on import
via :func:`register_mof_pack`, so both ``src.domains.get_domain_pack``
and ``src.oae.domains.get_domain_pack`` see ``"mof"`` once this module
is imported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.oae.domains.mof_libraries import (
    LINKER_LIBRARY,
    SBU_LIBRARY,
    linker_by_id,
    sbu_by_id,
)
from src.oae.kernel.schemas import (
    Linker,
    LinkerLibrary,
    MOFStructure,
    PoreDescriptor,
    RCSRTopology,
    SBU,
    SBULibrary,
)


# ---------------------------------------------------------------------------
# Family specifications — drive seeding and scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MOFFamilySpec:
    """Static description of one MOF family.

    A family binds a preferred topology to SBU and linker choices plus
    heuristic property targets. ``typical_pore`` encodes literature-
    average pore descriptors used during seed generation and scoring.
    """

    name: str
    topology: RCSRTopology
    sbu_ids: tuple[str, ...]
    linker_ids: tuple[str, ...]
    typical_pore: PoreDescriptor
    thermal_stability_c: float
    water_stability_score: float
    description: str


_MOF_FAMILIES: tuple[MOFFamilySpec, ...] = (
    MOFFamilySpec(
        name="zif",
        topology=RCSRTopology(net="sod", rcsr_symbol="sod"),
        sbu_ids=("zn_tetra",),
        linker_ids=("mim",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.66, surface_area_m2_g=1630.0,
            pld_angstrom=3.4, lcd_angstrom=11.6, density_g_cm3=0.95,
        ),
        thermal_stability_c=550.0,
        water_stability_score=0.75,
        description="Zeolitic imidazolate frameworks (ZIF-8 family)",
    ),
    MOFFamilySpec(
        name="zif_derivative",
        topology=RCSRTopology(net="sod", rcsr_symbol="sod"),
        sbu_ids=("co_tetra",),
        linker_ids=("mim",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.50, surface_area_m2_g=1400.0,
            pld_angstrom=3.4, lcd_angstrom=11.0, density_g_cm3=1.05,
        ),
        thermal_stability_c=520.0,
        water_stability_score=0.65,
        description="ZIF-67 and related Co-based zeolitic frameworks",
    ),
    MOFFamilySpec(
        name="uio",
        topology=RCSRTopology(net="fcu", rcsr_symbol="fcu"),
        sbu_ids=("zr6",),
        linker_ids=("bdc", "bdc_nh2"),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.48, surface_area_m2_g=1200.0,
            pld_angstrom=6.0, lcd_angstrom=8.0, density_g_cm3=1.23,
        ),
        thermal_stability_c=500.0,
        water_stability_score=0.90,
        description="UiO-66 family (Zr6 + BDC) with outstanding stability",
    ),
    MOFFamilySpec(
        name="pcn",
        topology=RCSRTopology(net="fcu", rcsr_symbol="fcu"),
        sbu_ids=("zr6",),
        linker_ids=("bpdc", "tcpp"),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=1.10, surface_area_m2_g=2800.0,
            pld_angstrom=11.0, lcd_angstrom=16.0, density_g_cm3=0.58,
        ),
        thermal_stability_c=480.0,
        water_stability_score=0.82,
        description="PCN series built on Zr6 clusters with extended linkers",
    ),
    MOFFamilySpec(
        name="mil",
        topology=RCSRTopology(net="acs", rcsr_symbol="acs"),
        sbu_ids=("m_trimer",),
        linker_ids=("bdc", "bpdc"),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.75, surface_area_m2_g=1500.0,
            pld_angstrom=8.5, lcd_angstrom=13.0, density_g_cm3=0.85,
        ),
        thermal_stability_c=450.0,
        water_stability_score=0.60,
        description="MIL series with chain or trimer SBUs (Cr/Fe/Al)",
    ),
    MOFFamilySpec(
        name="hkust",
        topology=RCSRTopology(net="tbo", rcsr_symbol="tbo"),
        sbu_ids=("cu_paddlewheel",),
        linker_ids=("btc",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.82, surface_area_m2_g=1800.0,
            pld_angstrom=9.0, lcd_angstrom=13.5, density_g_cm3=0.88,
        ),
        thermal_stability_c=350.0,
        water_stability_score=0.35,
        description="HKUST-1 (Cu paddlewheel + BTC, tbo net)",
    ),
    MOFFamilySpec(
        name="irmof",
        topology=RCSRTopology(net="pcu", rcsr_symbol="pcu"),
        sbu_ids=("zn4o",),
        linker_ids=("bdc", "bpdc"),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=1.04, surface_area_m2_g=2900.0,
            pld_angstrom=12.0, lcd_angstrom=15.0, density_g_cm3=0.61,
        ),
        thermal_stability_c=410.0,
        water_stability_score=0.25,
        description="IRMOF series (Zn4O nodes) — prototype MOF-5",
    ),
    MOFFamilySpec(
        name="mof_74",
        topology=RCSRTopology(net="srs", rcsr_symbol="etb"),
        sbu_ids=("m_trimer",),
        linker_ids=("bdc",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.55, surface_area_m2_g=1200.0,
            pld_angstrom=11.0, lcd_angstrom=11.0, density_g_cm3=1.20,
        ),
        thermal_stability_c=430.0,
        water_stability_score=0.55,
        description="MOF-74 honeycomb with open metal sites",
    ),
    MOFFamilySpec(
        name="nu",
        topology=RCSRTopology(net="ftw", rcsr_symbol="ftw"),
        sbu_ids=("zr6",),
        linker_ids=("tcpp",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=2.00, surface_area_m2_g=5000.0,
            pld_angstrom=20.0, lcd_angstrom=30.0, density_g_cm3=0.30,
        ),
        thermal_stability_c=460.0,
        water_stability_score=0.78,
        description="NU series with ultra-high surface area",
    ),
    MOFFamilySpec(
        name="cau",
        topology=RCSRTopology(net="dia", rcsr_symbol="dia"),
        sbu_ids=("zr6", "m_trimer"),
        linker_ids=("bdc_nh2",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.42, surface_area_m2_g=1100.0,
            pld_angstrom=5.5, lcd_angstrom=7.5, density_g_cm3=1.30,
        ),
        thermal_stability_c=380.0,
        water_stability_score=0.70,
        description="CAU (Al/Zr mixed) functionalised frameworks",
    ),
    MOFFamilySpec(
        name="porphyrin_mof",
        topology=RCSRTopology(net="ftw", rcsr_symbol="ftw"),
        sbu_ids=("porphyrin", "zr6"),
        linker_ids=("tcpp",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=1.40, surface_area_m2_g=3000.0,
            pld_angstrom=15.0, lcd_angstrom=22.0, density_g_cm3=0.48,
        ),
        thermal_stability_c=440.0,
        water_stability_score=0.72,
        description="Zr-porphyrin MOFs (PCN-222/224 etc.)",
    ),
    MOFFamilySpec(
        name="cpl",
        topology=RCSRTopology(net="bcu", rcsr_symbol="bcu"),
        sbu_ids=("cu_paddlewheel",),
        linker_ids=("bipy",),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.30, surface_area_m2_g=700.0,
            pld_angstrom=4.0, lcd_angstrom=6.0, density_g_cm3=1.35,
        ),
        thermal_stability_c=300.0,
        water_stability_score=0.40,
        description="Coordination polymers with bipyridine pillars",
    ),
    MOFFamilySpec(
        name="il_mof",
        topology=RCSRTopology(net="pcu", rcsr_symbol="pcu"),
        sbu_ids=("zn4o",),
        linker_ids=("bdc", "bipy"),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.90, surface_area_m2_g=2200.0,
            pld_angstrom=10.0, lcd_angstrom=13.0, density_g_cm3=0.75,
        ),
        thermal_stability_c=380.0,
        water_stability_score=0.45,
        description="Interpenetrated/interlocked MOFs",
    ),
    MOFFamilySpec(
        name="mixed_linker",
        topology=RCSRTopology(net="fcu", rcsr_symbol="fcu"),
        sbu_ids=("zr6",),
        linker_ids=("bdc", "bdc_nh2", "bpdc"),
        typical_pore=PoreDescriptor(
            pore_volume_cm3_g=0.70, surface_area_m2_g=1700.0,
            pld_angstrom=7.5, lcd_angstrom=11.0, density_g_cm3=0.95,
        ),
        thermal_stability_c=480.0,
        water_stability_score=0.80,
        description="Multi-variate UiO-style frameworks with mixed linkers",
    ),
)


# ---------------------------------------------------------------------------
# MOF domain pack
# ---------------------------------------------------------------------------


@dataclass
class MOFPack:
    """MOF :class:`DomainPack` implementation.

    Exposes scoring weights, seed patterns, and validation criteria to
    the discovery loop without requiring any changes to legacy code.
    """

    sbu_library: SBULibrary = field(default_factory=lambda: SBU_LIBRARY)
    linker_library: LinkerLibrary = field(default_factory=lambda: LINKER_LIBRARY)
    families: tuple[MOFFamilySpec, ...] = field(default_factory=lambda: _MOF_FAMILIES)

    # --- DomainPack protocol ------------------------------------------

    @property
    def name(self) -> str:
        return "mof"

    @property
    def description(self) -> str:
        return "Metal-Organic Framework discovery pack (14 families)"

    @property
    def scoring_weights(self) -> dict[str, float]:
        return {
            "porosity_score": 0.20,
            "surface_area_score": 0.18,
            "thermal_stability_score": 0.14,
            "water_stability_score": 0.13,
            "target_affinity_score": 0.20,
            "synthesizability_score": 0.10,
            "composition_validity": 0.05,
        }

    @property
    def loop_preset(self) -> str:
        return "mof_v1"

    @property
    def protocols(self) -> list[dict]:
        return [
            {
                "id": "mof_discovery",
                "agents": ["agent_cs", "agent_sin", "agent_r", "agent_ob"],
                "description": "Baseline MOF discovery loop",
            },
            {
                "id": "mof_alphafold",
                "agents": [
                    "agent_cs",
                    "agent_pb",
                    "agent_r",
                    "agent_ob",
                    "verifier",
                ],
                "description": "AlphaFold-style MOF pipeline with recycling",
            },
        ]

    @property
    def validation_criteria(self) -> dict:
        return {
            "min_surface_area_m2_g": 500.0,
            "min_pore_volume_cm3_g": 0.20,
            "min_thermal_stability_c": 300.0,
            "min_water_stability_score": 0.30,
            "max_interpenetration": 2,
        }

    @property
    def target_properties(self) -> list[str]:
        return [
            "co2_uptake_mmol_g",
            "ch4_uptake_mmol_g",
            "h2_uptake_wt_pct",
            "analyte_affinity",
            "thermal_stability_c",
        ]

    def get_seed_patterns(self) -> list[dict]:
        """Enumerate every (family, SBU, linker) combination as a seed."""
        seeds: list[dict] = []
        for family in self.families:
            for sbu_id in family.sbu_ids:
                for linker_id in family.linker_ids:
                    sbu = sbu_by_id(sbu_id)
                    linker = linker_by_id(linker_id)
                    if sbu is None or linker is None:
                        continue
                    seeds.append(
                        {
                            "family": family.name,
                            "topology_net": family.topology.net,
                            "sbu_id": sbu.sbu_id,
                            "linker_id": linker.linker_id,
                            "metal": sbu.metal,
                            "linker_shape": linker.shape,
                            "description": family.description,
                        }
                    )
        return seeds

    # --- MOF-specific helpers -----------------------------------------

    def families_by_name(self, name: str) -> MOFFamilySpec | None:
        for family in self.families:
            if family.name == name:
                return family
        return None

    def build_seed_structure(
        self,
        family_name: str,
        *,
        mof_id: str | None = None,
    ) -> MOFStructure | None:
        """Construct a :class:`MOFStructure` stub from a family name.

        This is *not* a full crystal builder — it produces a metadata
        skeleton suitable for downstream scoring, review, and CIF
        generation later in the pipeline.
        """
        family = self.families_by_name(family_name)
        if family is None:
            return None
        sbus = tuple(
            s for s in (sbu_by_id(sid) for sid in family.sbu_ids) if s is not None
        )
        linkers = tuple(
            linker_by_id(lid) for lid in family.linker_ids if linker_by_id(lid)
        )
        linkers = tuple(linker for linker in linkers if linker is not None)
        return MOFStructure(
            mof_id=mof_id or f"{family_name}-seed",
            family=family_name,
            topology=family.topology,
            sbus=sbus,
            linkers=linkers,
            pore=family.typical_pore,
            thermal_stability_c=family.thermal_stability_c,
            water_stability_score=family.water_stability_score,
            provenance={"pack": "mof", "source": "family_spec"},
        )

    def score_structure(
        self,
        structure: MOFStructure,
        *,
        target_affinity: float = 0.0,
    ) -> dict[str, float]:
        """Score a single :class:`MOFStructure` against pack weights.

        Returns a mapping of component name → score in [0.0, 1.0] plus
        a ``total_score`` key computed as the weight-sum across
        components. The formula is deliberately simple and reproducible
        so unit tests can pin its behaviour.
        """
        criteria = self.validation_criteria
        pore = structure.pore

        porosity_score = _normalise(
            pore.pore_volume_cm3_g,
            criteria["min_pore_volume_cm3_g"],
            2.0,
        )
        surface_area_score = _normalise(
            pore.surface_area_m2_g,
            criteria["min_surface_area_m2_g"],
            5000.0,
        )
        thermal_score = _normalise(
            structure.thermal_stability_c,
            criteria["min_thermal_stability_c"],
            600.0,
        )
        water_score = max(
            0.0, min(1.0, structure.water_stability_score)
        )
        target_score = max(0.0, min(1.0, target_affinity))
        synth_score = _synth_heuristic(structure)
        composition_score = 1.0 if structure.sbus and structure.linkers else 0.0

        components = {
            "porosity_score": porosity_score,
            "surface_area_score": surface_area_score,
            "thermal_stability_score": thermal_score,
            "water_stability_score": water_score,
            "target_affinity_score": target_score,
            "synthesizability_score": synth_score,
            "composition_validity": composition_score,
        }
        weights = self.scoring_weights
        total = sum(weights[k] * components[k] for k in components)
        return {**components, "total_score": total}

    def seeds_for_families(
        self,
        family_names: Iterable[str],
    ) -> list[MOFStructure]:
        """Return seed ``MOFStructure`` objects for the given families."""
        out: list[MOFStructure] = []
        for family_name in family_names:
            struct = self.build_seed_structure(family_name)
            if struct is not None:
                out.append(struct)
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into [0.0, 1.0] via linear scaling between low/high."""
    if high <= low:
        return 0.0 if value < low else 1.0
    scaled = (value - low) / (high - low)
    return max(0.0, min(1.0, scaled))


def _synth_heuristic(structure: MOFStructure) -> float:
    """Rough synthesizability heuristic in [0.0, 1.0].

    * Prefers water-stable frameworks (correlated with synthesis success).
    * Penalises giant pores (hard to crystallise) and vanishingly small
      pores (rarely useful).
    """
    water_bonus = structure.water_stability_score
    pld = structure.pore.pld_angstrom
    pore_term = 1.0 - min(1.0, abs(pld - 10.0) / 15.0) if pld > 0 else 0.5
    score = 0.6 * water_bonus + 0.4 * pore_term
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_mof_pack() -> MOFPack:
    """Register the MOF pack with the legacy registry and return it.

    Calling this is idempotent — re-registering simply replaces the
    previous entry with a fresh instance.
    """
    from src.domains.base import register_domain_pack

    pack = MOFPack()
    register_domain_pack(pack)
    return pack


__all__ = [
    "MOFFamilySpec",
    "MOFPack",
    "register_mof_pack",
]
