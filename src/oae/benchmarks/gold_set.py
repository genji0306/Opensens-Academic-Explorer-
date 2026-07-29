"""Phase I gold set — hand-labelled credibility truth for benchmarks.

A small offline set of candidates with known ground-truth credibility
labels drawn from the curated Phase C mechanism library. Every entry
carries a binary ``credible`` flag plus the metadata the Snorkel
verifier and Agent R consume. The set is deliberately small (twenty
entries) so benchmarks run in milliseconds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GoldEntry:
    """One hand-labelled candidate with its expected credibility."""

    candidate_id: str
    family: str
    composition: str
    mechanism: str
    credible: bool
    metadata: dict = field(default_factory=dict)
    connector_agreement: dict[str, float] = field(default_factory=dict)


GOLD_SET: tuple[GoldEntry, ...] = (
    # --- Credible, well-understood superconductors -------------------
    GoldEntry(
        candidate_id="gold-001",
        family="cuprate",
        composition="YBa2Cu3O7",
        mechanism="d-wave",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.9,
            "formation_energy_per_atom": -2.85,
            "is_novel": False,
        },
        connector_agreement={"materials_project": 0.95, "cod": 0.9},
    ),
    GoldEntry(
        candidate_id="gold-002",
        family="hydride",
        composition="H3S",
        mechanism="bcs",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.7,
            "formation_energy_per_atom": -1.2,
            "is_novel": False,
        },
        connector_agreement={"materials_project": 0.8},
    ),
    GoldEntry(
        candidate_id="gold-003",
        family="cuprate",
        composition="Bi2Sr2CaCu2O8",
        mechanism="d-wave",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.85,
            "formation_energy_per_atom": -2.9,
        },
        connector_agreement={"materials_project": 0.9},
    ),
    GoldEntry(
        candidate_id="gold-004",
        family="nickelate",
        composition="Nd0.8Sr0.2NiO2",
        mechanism="d-wave",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.65,
            "formation_energy_per_atom": -2.3,
        },
        connector_agreement={"materials_project": 0.8},
    ),
    GoldEntry(
        candidate_id="gold-005",
        family="ZIF",
        composition="ZIF-8",
        mechanism="porous-coordination",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.95,
            "formation_energy_per_atom": -1.2,
        },
        connector_agreement={"materials_project": 0.85, "cod": 0.85},
    ),
    GoldEntry(
        candidate_id="gold-006",
        family="UiO",
        composition="UiO-66",
        mechanism="porous-coordination",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.9,
            "formation_energy_per_atom": -1.82,
        },
        connector_agreement={"materials_project": 0.88, "cod": 0.82},
    ),
    GoldEntry(
        candidate_id="gold-007",
        family="HKUST",
        composition="HKUST-1",
        mechanism="porous-coordination",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.88,
            "formation_energy_per_atom": -1.45,
        },
        connector_agreement={"materials_project": 0.87},
    ),
    GoldEntry(
        candidate_id="gold-008",
        family="voltammetric",
        composition="Au-SPE/dopamine",
        mechanism="redox",
        credible=True,
        metadata={
            "synthesizability": 0.95,
            "selectivity": 0.85,
            "robustness": 0.8,
        },
    ),
    GoldEntry(
        candidate_id="gold-009",
        family="aptasensor",
        composition="Au-SPE/aptamer",
        mechanism="conformational",
        credible=True,
        metadata={
            "selectivity": 0.9,
            "robustness": 0.75,
        },
    ),
    GoldEntry(
        candidate_id="gold-010",
        family="impedimetric",
        composition="Au-SPE/ssDNA",
        mechanism="rct_change",
        credible=True,
        metadata={
            "selectivity": 0.82,
            "robustness": 0.7,
        },
    ),
    # --- Non-credible / contradicted candidates ----------------------
    GoldEntry(
        candidate_id="gold-101",
        family="ambient-rtsc",
        composition="LK-99",
        mechanism="flat-band",
        credible=False,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.2,
            "formation_energy_per_atom": 2.1,
            "is_novel": True,
        },
        connector_agreement={"materials_project": 0.1},
    ),
    GoldEntry(
        candidate_id="gold-102",
        family="speculative",
        composition="UnknownPhase",
        mechanism="exciton",
        credible=False,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.15,
            "formation_energy_per_atom": 4.0,
            "is_novel": True,
        },
        connector_agreement={"materials_project": 0.05},
    ),
    GoldEntry(
        candidate_id="gold-103",
        family="ambient-rtsc",
        composition="Fantasy223",
        mechanism="bcs",
        credible=False,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.1,
            "formation_energy_per_atom": 5.5,
            "is_novel": True,
        },
    ),
    GoldEntry(
        candidate_id="gold-104",
        family="speculative",
        composition="InvalidMOF",
        mechanism="porous-coordination",
        credible=False,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.1,
            "formation_energy_per_atom": 3.0,
            "is_novel": True,
        },
    ),
    GoldEntry(
        candidate_id="gold-105",
        family="voltammetric",
        composition="BadSensor-01",
        mechanism="redox",
        credible=False,
        metadata={
            "selectivity": 0.1,
            "robustness": 0.1,
        },
    ),
    GoldEntry(
        candidate_id="gold-106",
        family="aptasensor",
        composition="NoisySensor",
        mechanism="conformational",
        credible=False,
        metadata={
            "selectivity": 0.2,
            "robustness": 0.15,
        },
    ),
    # --- Borderline credible ----------------------------------------
    GoldEntry(
        candidate_id="gold-201",
        family="iron-pnictide",
        composition="BaFe2As2",
        mechanism="s±",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.75,
            "formation_energy_per_atom": -1.1,
        },
        connector_agreement={"materials_project": 0.75},
    ),
    GoldEntry(
        candidate_id="gold-202",
        family="PCN",
        composition="PCN-224",
        mechanism="porous-coordination",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.7,
            "formation_energy_per_atom": -1.55,
        },
        connector_agreement={"materials_project": 0.78},
    ),
    GoldEntry(
        candidate_id="gold-203",
        family="MIL",
        composition="MIL-101",
        mechanism="porous-coordination",
        credible=True,
        metadata={
            "has_energy_estimate": True,
            "synthesizability": 0.8,
            "formation_energy_per_atom": -1.5,
        },
        connector_agreement={"materials_project": 0.82},
    ),
    GoldEntry(
        candidate_id="gold-204",
        family="voltammetric",
        composition="Au-SPE/glucose",
        mechanism="enzymatic",
        credible=True,
        metadata={
            "selectivity": 0.78,
            "robustness": 0.7,
        },
    ),
)


@dataclass(frozen=True)
class PhaseIGoldSet:
    """Wrapper exposing the gold set with filtering helpers."""

    entries: tuple[GoldEntry, ...] = GOLD_SET

    def __len__(self) -> int:
        return len(self.entries)

    def positives(self) -> tuple[GoldEntry, ...]:
        return tuple(e for e in self.entries if e.credible)

    def negatives(self) -> tuple[GoldEntry, ...]:
        return tuple(e for e in self.entries if not e.credible)

    def by_family(self, family: str) -> tuple[GoldEntry, ...]:
        return tuple(e for e in self.entries if e.family == family)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "candidate_id": e.candidate_id,
                "family": e.family,
                "composition": e.composition,
                "mechanism": e.mechanism,
                "credible": e.credible,
                "metadata": dict(e.metadata),
                "connector_agreement": dict(e.connector_agreement),
            }
            for e in self.entries
        ]
