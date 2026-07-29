"""Offline mechanism library for Agent R.

Phase C ships Agent R as an *offline-first* reviewer backed by a curated
mechanism library. No external tool calls, no LLM calls. This lets the
loop, schemas, and memory persistence be exercised end-to-end before
ToolUniverse (Phase G) lands.

Each entry declares which candidate families it applies to, the
mechanism claim, a support score derived from literature consensus, a
contradiction score for known failure modes, and one or more citations.
The library is deliberately small — it only needs to be dense enough to
exercise Agent R's scoring and ranking paths for the domains we care
about: RTAP superconductors, MOF porous materials, and electrochemical
sensing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.oae.kernel.schemas import Citation, TheoryCard


@dataclass(frozen=True)
class LibraryEntry:
    """A single offline mechanism entry keyed by candidate family."""

    families: tuple[str, ...]
    mechanism: str
    claim: str
    conditions: str
    support_level: str
    contradiction_level: str
    support_score: float
    contradiction_score: float
    citations: tuple[Citation, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, family: str) -> bool:
        """Case-insensitive family match."""
        family_lc = family.lower()
        return any(f.lower() == family_lc for f in self.families)

    def to_theory_card(self) -> TheoryCard:
        """Materialise this entry as an immutable ``TheoryCard``."""
        return TheoryCard(
            claim=self.claim,
            mechanism=self.mechanism,
            conditions=self.conditions,
            support_level=self.support_level,  # type: ignore[arg-type]
            contradiction_level=self.contradiction_level,  # type: ignore[arg-type]
            support_score=self.support_score,
            contradiction_score=self.contradiction_score,
            citations=self.citations,
            tags=self.tags,
        )


# ---------------------------------------------------------------------------
# Seed library — intentionally curated, not exhaustive
# ---------------------------------------------------------------------------

_SEED: tuple[LibraryEntry, ...] = (
    # ----- RTAP superconductor families -----
    LibraryEntry(
        families=("cuprate", "engineered-cuprate", "infinite-layer"),
        mechanism="d_wave_singlet_pairing",
        claim="Cuprate-like d-wave pairing supported by CuO2 plane chemistry",
        conditions="hole-doped CuO2 planes, apical oxygen present",
        support_level="strong",
        contradiction_level="minor",
        support_score=0.85,
        contradiction_score=0.15,
        citations=(
            Citation(source="doi:10.1103/RevModPhys.78.17",
                     title="Doping a Mott insulator", year=2006,
                     confidence=0.95),
        ),
        tags=("rtap", "superconductor", "d-wave"),
    ),
    LibraryEntry(
        families=("hydride", "ternary-hydride"),
        mechanism="bcs_hydride_ep_coupling",
        claim="BCS electron-phonon coupling in hydrogen-rich superhydrides",
        conditions="requires high pressure (>100 GPa) for known members",
        support_level="strong",
        contradiction_level="major",
        support_score=0.80,
        contradiction_score=0.55,
        citations=(
            Citation(source="doi:10.1038/s41586-019-1201-8",
                     title="Superconductivity at 250 K in LaH10",
                     year=2019, confidence=0.9),
        ),
        tags=("rtap", "bcs", "pressure-required"),
    ),
    LibraryEntry(
        families=("nickelate",),
        mechanism="nickelate_superexchange",
        claim="Infinite-layer nickelate superconductivity via Ni-d9 analogue",
        conditions="oxygen reduction to d9 Ni1+",
        support_level="moderate",
        contradiction_level="minor",
        support_score=0.55,
        contradiction_score=0.20,
        citations=(
            Citation(source="doi:10.1038/s41586-019-1496-5",
                     title="Superconductivity in infinite-layer nickelate",
                     year=2019, confidence=0.85),
        ),
        tags=("rtap", "nickelate"),
    ),
    LibraryEntry(
        families=("kagome", "flat-band"),
        mechanism="flat_band_correlations",
        claim="Flat-band van Hove enhancement in kagome lattices",
        conditions="Fermi level near flat band",
        support_level="moderate",
        contradiction_level="none",
        support_score=0.50,
        contradiction_score=0.05,
        citations=(
            Citation(source="arxiv:2104.05671",
                     title="Kagome superconductivity", year=2021,
                     confidence=0.7),
        ),
        tags=("rtap", "kagome", "flat-band"),
    ),
    LibraryEntry(
        families=("mof-sc",),
        mechanism="mof_linker_conductivity",
        claim="MOF conductivity via through-bond pi pathways in linkers",
        conditions="pi-conjugated ditopic linkers, redox-active nodes",
        support_level="weak",
        contradiction_level="minor",
        support_score=0.30,
        contradiction_score=0.25,
        citations=(
            Citation(source="doi:10.1021/jacs.8b04092",
                     title="Electrically conductive MOFs",
                     year=2018, confidence=0.8),
        ),
        tags=("rtap", "mof", "speculative"),
    ),
    # ----- MOF discovery families -----
    LibraryEntry(
        families=("zif",),
        mechanism="imidazolate_tetrahedral_framework",
        claim="ZIFs form sod-net zeolitic frameworks with Zn2+/Co2+ tetrahedra",
        conditions="imidazolate linkers, solvothermal synthesis",
        support_level="strong",
        contradiction_level="none",
        support_score=0.90,
        contradiction_score=0.05,
        citations=(
            Citation(source="doi:10.1126/science.1152516",
                     title="High-throughput ZIF synthesis", year=2008,
                     confidence=0.95),
        ),
        tags=("mof", "zif", "zeolitic"),
    ),
    LibraryEntry(
        families=("uio", "pcn"),
        mechanism="zr6_cluster_fcu_framework",
        claim="Zr6 oxo-cluster + ditopic carboxylate yields fcu net with high stability",
        conditions="Zr/ditopic linker, modulator-assisted synthesis",
        support_level="strong",
        contradiction_level="none",
        support_score=0.88,
        contradiction_score=0.05,
        citations=(
            Citation(source="doi:10.1021/ja8057953",
                     title="UiO-66 Zr MOF", year=2008, confidence=0.95),
        ),
        tags=("mof", "uio", "fcu"),
    ),
    LibraryEntry(
        families=("mil",),
        mechanism="carboxylate_chain_sbu",
        claim="MIL series built on chain or trimer SBUs with aromatic dicarboxylates",
        conditions="Fe/Cr/Al + BDC-family linkers",
        support_level="strong",
        contradiction_level="minor",
        support_score=0.80,
        contradiction_score=0.15,
        citations=(
            Citation(source="doi:10.1002/anie.200460592",
                     title="MIL-53 flexible MOF", year=2004, confidence=0.9),
        ),
        tags=("mof", "mil"),
    ),
    LibraryEntry(
        families=("hkust", "cu-paddlewheel"),
        mechanism="cu_paddlewheel_tbo_framework",
        claim="Cu2 paddlewheels with tritopic carboxylates assemble tbo net",
        conditions="Cu2+ + BTC under solvothermal",
        support_level="strong",
        contradiction_level="minor",
        support_score=0.82,
        contradiction_score=0.18,
        citations=(
            Citation(source="doi:10.1126/science.283.5405.1148",
                     title="HKUST-1", year=1999, confidence=0.95),
        ),
        tags=("mof", "hkust", "paddlewheel"),
    ),
    # ----- Electrochemical sensing families -----
    LibraryEntry(
        families=("electrochemical-voltammetric", "electrochemical-amperometric"),
        mechanism="diffusion_controlled_faradaic",
        claim="Reversible redox couple with Randles-Sevcik linearity",
        conditions="scan rate 10-500 mV/s, supporting electrolyte",
        support_level="strong",
        contradiction_level="minor",
        support_score=0.85,
        contradiction_score=0.15,
        citations=(
            Citation(source="doi:10.1021/ac60210a007",
                     title="Randles-Sevcik equation", year=1948,
                     confidence=0.98),
        ),
        tags=("sensor", "voltammetry", "faradaic"),
    ),
    LibraryEntry(
        families=("electrochemical-impedimetric",),
        mechanism="charge_transfer_resistance_shift",
        claim="Target binding modulates Rct in Randles equivalent circuit",
        conditions="label-free, 1-100 kHz EIS frequency window",
        support_level="strong",
        contradiction_level="minor",
        support_score=0.82,
        contradiction_score=0.18,
        citations=(
            Citation(source="doi:10.1021/cr068105t",
                     title="EIS biosensors review", year=2008,
                     confidence=0.9),
        ),
        tags=("sensor", "eis", "label-free"),
    ),
)


def library_entries() -> tuple[LibraryEntry, ...]:
    """Return the immutable tuple of seeded library entries."""
    return _SEED


def entries_for_family(family: str) -> tuple[LibraryEntry, ...]:
    """Return every library entry that matches ``family``."""
    if not family:
        return ()
    return tuple(entry for entry in _SEED if entry.matches(family))


def theory_cards_for_family(family: str) -> tuple[TheoryCard, ...]:
    """Return ``TheoryCard`` objects built from entries matching ``family``."""
    return tuple(e.to_theory_card() for e in entries_for_family(family))


def theory_cards_for_families(families: Iterable[str]) -> tuple[TheoryCard, ...]:
    """Return theory cards for any of the provided family names."""
    seen_mechanisms: set[str] = set()
    cards: list[TheoryCard] = []
    for family in families:
        for card in theory_cards_for_family(family):
            if card.mechanism in seen_mechanisms:
                continue
            seen_mechanisms.add(card.mechanism)
            cards.append(card)
    return tuple(cards)
