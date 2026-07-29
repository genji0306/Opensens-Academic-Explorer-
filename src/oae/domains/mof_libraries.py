"""Seed SBU and linker libraries for the MOF domain pack.

These libraries are intentionally small and curated. They cover the
SBU/linker combinations required by the 14 MOF families shipped in
:mod:`src.oae.domains.mof` plus a few common extras. Extending the
libraries is a matter of appending to the tuples — everything is
immutable, so concurrent readers can't be corrupted.
"""
from __future__ import annotations

from src.oae.kernel.schemas import Linker, LinkerLibrary, SBU, SBULibrary

# ---------------------------------------------------------------------------
# Inorganic secondary building units
# ---------------------------------------------------------------------------

_SBUS: tuple[SBU, ...] = (
    # Zn clusters
    SBU(
        sbu_id="zn4o",
        metal="Zn",
        geometry="zn4o",
        coordination_number=6,
        charge=-2,
        formula="Zn4O(-COO)6",
    ),
    SBU(
        sbu_id="zn_tetra",
        metal="Zn",
        geometry="single_metal",
        coordination_number=4,
        charge=2,
        formula="Zn(N-Im)4",
    ),
    # Zr clusters
    SBU(
        sbu_id="zr6",
        metal="Zr",
        geometry="zr6_cluster",
        coordination_number=12,
        charge=-4,
        formula="Zr6O4(OH)4(-COO)12",
    ),
    # Cu paddlewheel
    SBU(
        sbu_id="cu_paddlewheel",
        metal="Cu",
        geometry="cu2_paddlewheel",
        coordination_number=4,
        charge=-4,
        formula="Cu2(-COO)4",
    ),
    # Cr / Al / Fe trimer
    SBU(
        sbu_id="m_trimer",
        metal="Cr",
        geometry="oxo_trimer",
        coordination_number=6,
        charge=1,
        formula="M3O(-COO)6",
    ),
    # Co tetrahedral (ZIF-67)
    SBU(
        sbu_id="co_tetra",
        metal="Co",
        geometry="single_metal",
        coordination_number=4,
        charge=2,
        formula="Co(N-Im)4",
    ),
    # Porphyrin platform
    SBU(
        sbu_id="porphyrin",
        metal="Zn",
        geometry="porphyrin",
        coordination_number=4,
        charge=-2,
        formula="Zn-TCPP",
    ),
)

SBU_LIBRARY = SBULibrary(name="oae_seed_sbus", entries=_SBUS)


# ---------------------------------------------------------------------------
# Organic linkers
# ---------------------------------------------------------------------------

_LINKERS: tuple[Linker, ...] = (
    Linker(
        linker_id="bdc",
        smiles="O=C(O)c1ccc(C(=O)O)cc1",
        shape="ditopic",
        length_angstrom=6.8,
        functional_groups=("carboxylate",),
        charge=-2,
    ),
    Linker(
        linker_id="bdc_nh2",
        smiles="O=C(O)c1cc(N)ccc1C(=O)O",
        shape="ditopic",
        length_angstrom=6.9,
        functional_groups=("carboxylate", "amine"),
        charge=-2,
    ),
    Linker(
        linker_id="bpdc",
        smiles="O=C(O)c1ccc(-c2ccc(C(=O)O)cc2)cc1",
        shape="ditopic",
        length_angstrom=11.0,
        functional_groups=("carboxylate",),
        charge=-2,
    ),
    Linker(
        linker_id="btc",
        smiles="O=C(O)c1cc(C(=O)O)cc(C(=O)O)c1",
        shape="tritopic",
        length_angstrom=7.2,
        functional_groups=("carboxylate",),
        charge=-3,
    ),
    Linker(
        linker_id="btb",
        smiles="c1cc(-c2cc(-c3ccc(C(=O)O)cc3)cc(-c3ccc(C(=O)O)cc3)c2)ccc1C(=O)O",
        shape="tritopic",
        length_angstrom=15.0,
        functional_groups=("carboxylate",),
        charge=-3,
    ),
    Linker(
        linker_id="mim",
        smiles="Cc1ncc[nH]1",
        shape="ditopic",
        length_angstrom=6.0,
        functional_groups=("imidazolate",),
        charge=-1,
    ),
    Linker(
        linker_id="tcpp",
        smiles="porphyrin-tetracarboxyphenyl",
        shape="tetratopic",
        length_angstrom=19.0,
        functional_groups=("carboxylate", "porphyrin"),
        charge=-4,
    ),
    Linker(
        linker_id="bipy",
        smiles="c1ccc(-c2ccccn2)nc1",
        shape="ditopic",
        length_angstrom=7.0,
        functional_groups=("pyridine",),
        charge=0,
    ),
)

LINKER_LIBRARY = LinkerLibrary(name="oae_seed_linkers", entries=_LINKERS)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def sbu_by_id(sbu_id: str) -> SBU | None:
    for sbu in _SBUS:
        if sbu.sbu_id == sbu_id:
            return sbu
    return None


def linker_by_id(linker_id: str) -> Linker | None:
    for linker in _LINKERS:
        if linker.linker_id == linker_id:
            return linker
    return None
