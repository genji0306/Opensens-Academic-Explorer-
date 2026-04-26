"""MOF discovery pipeline — AlphaFold-style recycling (Phase D).

The pipeline composes existing pieces instead of inventing new engines:

* :class:`~src.oae.domains.mof.MOFPack` provides families, scoring, and
  seed structures.
* :class:`~src.oae.agents.r.AgentR` provides the review stage — each
  candidate gets a :class:`ReviewBundle` built from the curated
  mechanism library.
* The AlphaFold analogue lives in :class:`MOFPipeline.recycle`. A
  "pass" is one refinement sweep that perturbs the pore descriptors
  toward the family ideal, re-scores, and optionally snapshots a
  :class:`MOFStructure` copy into the recycle history. N passes
  ≡ AlphaFold recycling.

Phase D intentionally does not touch the legacy discovery loop. The
pipeline runs standalone, emits :class:`MOFRunResult`, and registers
dossiers with :class:`ResearchMemory` when one is supplied. Wiring into
``MaterialDiscoveryLoop`` happens in a later phase.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Iterable

from src.oae.agents.r import AgentR
from src.oae.domains.mof import MOFPack
from src.oae.kernel.schemas import (
    MOFStructure,
    PoreDescriptor,
    ReviewBundle,
)
from src.oae.research import (
    DossierWriter,
    ResearchMemory,
    ResearchTrace,
    ingest_bundles,
)

logger = logging.getLogger("MOFPipeline")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MOFCandidateResult:
    """Score + review outcome for a single MOF structure."""

    structure: MOFStructure
    scores: dict[str, float]
    review: ReviewBundle
    recycle_history: tuple[float, ...] = ()

    @property
    def total_score(self) -> float:
        return float(self.scores.get("total_score", 0.0))

    @property
    def combined_score(self) -> float:
        """Domain score blended with Agent R's theory alignment.

        Uses a fixed 0.85/0.15 split — domain heuristics stay the core,
        theory alignment is an additive bonus. Contradiction penalty is
        subtracted so high-contradiction mechanisms down-weight the
        candidate even if their support is strong.
        """
        base = self.total_score
        theory = self.review.theory_alignment_score()
        penalty = self.review.contradiction_penalty()
        return max(
            0.0,
            min(1.0, 0.85 * base + 0.15 * theory - 0.05 * penalty),
        )


@dataclass
class MOFRunResult:
    """Result bundle for a :meth:`MOFPipeline.run` invocation."""

    candidates: list[MOFCandidateResult] = field(default_factory=list)
    dossier_paths: list[str] = field(default_factory=list)
    recycle_passes: int = 0

    def top_k(self, k: int = 5) -> list[MOFCandidateResult]:
        return sorted(
            self.candidates,
            key=lambda c: c.combined_score,
            reverse=True,
        )[:k]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@dataclass
class MOFPipeline:
    """AlphaFold-style MOF discovery pipeline.

    Parameters
    ----------
    pack:
        Injected MOF domain pack. Defaults to a fresh :class:`MOFPack`.
    agent_r:
        Review agent. Defaults to a no-arg :class:`AgentR`.
    recycle_passes:
        Number of AlphaFold-style recycling passes. Each pass nudges
        pore descriptors toward the family ideal (0.5 damping) and
        re-scores. A value of 0 disables recycling.
    """

    pack: MOFPack = field(default_factory=MOFPack)
    agent_r: AgentR = field(default_factory=AgentR)
    recycle_passes: int = 2
    damping: float = 0.5

    # --- public API ---------------------------------------------------

    def run(
        self,
        family_names: Iterable[str] | None = None,
        *,
        target_affinity: float = 0.0,
        memory: ResearchMemory | None = None,
        dossier_writer: DossierWriter | None = None,
        trace: ResearchTrace | None = None,
        campaign_id: str = "mof_v1",
    ) -> MOFRunResult:
        """Run the MOF pipeline end-to-end."""
        families = (
            tuple(family_names)
            if family_names is not None
            else tuple(f.name for f in self.pack.families)
        )
        seeds = self.pack.seeds_for_families(families)
        if not seeds:
            logger.warning("MOFPipeline.run received no usable families")
            return MOFRunResult(recycle_passes=self.recycle_passes)

        # Phase 1 — Agent R review (feeds recycling and final scoring).
        review_candidates = [
            _CandidateForReview(
                candidate_id=struct.mof_id,
                family=struct.family,
            )
            for struct in seeds
        ]
        bundles = self.agent_r.run(review_candidates)

        # Phase 2 — AlphaFold-style recycling + scoring.
        results: list[MOFCandidateResult] = []
        for struct in seeds:
            bundle = bundles.get(struct.mof_id) or _empty_bundle_for(struct.mof_id)
            refined, history = self.recycle(struct, target_affinity=target_affinity)
            scores = self.pack.score_structure(
                refined, target_affinity=target_affinity
            )
            results.append(
                MOFCandidateResult(
                    structure=refined,
                    scores=scores,
                    review=bundle,
                    recycle_history=history,
                )
            )
            if trace is not None:
                trace.log_rationale(
                    struct.mof_id,
                    f"recycled {self.recycle_passes} passes, "
                    f"total={scores['total_score']:.3f}",
                )

        # Phase 3 — optional persistence.
        dossier_paths: list[str] = []
        if memory is not None:
            ingest_bundles(memory, (r.review for r in results))
        if dossier_writer is not None:
            for r in results:
                pointer = dossier_writer.write(
                    r.review,
                    campaign_id=campaign_id,
                    family=r.structure.family,
                    trace=trace,
                    memory=memory,
                )
                dossier_paths.append(pointer.path)

        return MOFRunResult(
            candidates=results,
            dossier_paths=dossier_paths,
            recycle_passes=self.recycle_passes,
        )

    # --- recycling ----------------------------------------------------

    def recycle(
        self,
        structure: MOFStructure,
        *,
        target_affinity: float = 0.0,
    ) -> tuple[MOFStructure, tuple[float, ...]]:
        """Apply AlphaFold-style recycling passes to a structure.

        Each pass:
          1. Reads the family ideal pore descriptor from the pack.
          2. Linearly interpolates the current descriptor toward the
             ideal using ``self.damping``.
          3. Re-scores and records the total score.

        Returns the final refined structure plus the per-pass score
        history.
        """
        if self.recycle_passes <= 0:
            base_scores = self.pack.score_structure(
                structure, target_affinity=target_affinity
            )
            return structure, (base_scores["total_score"],)

        family = self.pack.families_by_name(structure.family)
        if family is None:
            logger.debug("recycle: unknown family %r", structure.family)
            return structure, ()

        ideal = family.typical_pore
        current = structure
        history: list[float] = []
        for _ in range(self.recycle_passes):
            current = replace(
                current,
                pore=_interpolate_pore(current.pore, ideal, self.damping),
            )
            scores = self.pack.score_structure(
                current, target_affinity=target_affinity
            )
            history.append(scores["total_score"])
        return current, tuple(history)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _CandidateForReview:
    """Minimal duck-typed candidate Agent R can consume."""

    candidate_id: str
    family: str = ""
    composition: str = ""
    mechanism: str = ""
    metadata: dict = field(default_factory=dict)


def _interpolate_pore(
    current: PoreDescriptor,
    ideal: PoreDescriptor,
    damping: float,
) -> PoreDescriptor:
    """Blend the current pore descriptor toward the family ideal."""
    alpha = max(0.0, min(1.0, damping))

    def blend(a: float, b: float) -> float:
        return a + alpha * (b - a)

    return PoreDescriptor(
        pore_volume_cm3_g=blend(current.pore_volume_cm3_g, ideal.pore_volume_cm3_g),
        surface_area_m2_g=blend(current.surface_area_m2_g, ideal.surface_area_m2_g),
        pld_angstrom=blend(current.pld_angstrom, ideal.pld_angstrom),
        lcd_angstrom=blend(current.lcd_angstrom, ideal.lcd_angstrom),
        asa_m2_g=blend(current.asa_m2_g, ideal.asa_m2_g),
        density_g_cm3=blend(current.density_g_cm3, ideal.density_g_cm3),
    )


def _empty_bundle_for(candidate_id: str) -> ReviewBundle:
    return ReviewBundle(candidate_id=candidate_id)


__all__ = [
    "MOFCandidateResult",
    "MOFPipeline",
    "MOFRunResult",
]
