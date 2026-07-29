"""Agent AR — scientific priors engine for Sensing Studio.

Agent AR wraps :class:`AgentR` (Phase C) and the curated mechanism
library. Given a :class:`TargetAnalyte`, it retrieves family-specific
theory cards, compiles them into a :class:`ReviewBundle`, and emits a
compact ``prior_summary`` dict the predictive model can ingest:

* ``theory_alignment`` — Agent R's additive score for how well the
  candidate family is supported by literature.
* ``contradiction_penalty`` — how much known contradictions should
  down-weight predictions.
* ``expected_peak_v`` — pulled from the analyte's known redox window,
  used as a prior for the predictive model.

Phase F intentionally does not call ToolUniverse. Phase G (external
tool broker) plugs into this class as an additional retrieval source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from src.oae.agents.r import AgentR
from src.oae.kernel.schemas import ReviewBundle, TargetAnalyte


@dataclass
class _PriorCandidate:
    """Minimal duck-typed candidate Agent R accepts."""

    candidate_id: str
    family: str = "electrochemical-voltammetric"
    composition: str = ""
    mechanism: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ScientificPriors:
    """Scientific priors engine.

    Parameters
    ----------
    agent_r:
        Injected Agent R instance; defaults to a no-arg
        :class:`AgentR`.
    default_family:
        Family used when the caller does not specify one. Keeps the
        sensing-studio loop deterministic across analytes.
    """

    agent_r: AgentR = field(default_factory=AgentR)
    default_family: str = "electrochemical-voltammetric"

    def build_for_analyte(
        self,
        analyte: TargetAnalyte,
        families: Sequence[str] | None = None,
    ) -> ReviewBundle:
        """Return a :class:`ReviewBundle` for ``analyte``.

        The bundle is keyed on the analyte name and is built by
        invoking Agent R over one synthetic candidate per requested
        family. The returned bundle is the first / most-supported one
        with theory cards attached; if nothing matches, an empty
        bundle is returned so downstream scoring still runs.
        """
        family_list = list(families) if families else [self.default_family]
        synthetic = [
            _PriorCandidate(
                candidate_id=f"{analyte.name.lower()}__{fam}",
                family=fam,
            )
            for fam in family_list
        ]
        bundles = self.agent_r.run(synthetic)
        # Pick the bundle with the highest theory alignment as the
        # canonical prior. Fall back to an empty bundle if none have
        # theory cards (e.g. unknown family).
        chosen: ReviewBundle | None = None
        best = -1.0
        for b in bundles.values():
            score = b.theory_alignment_score()
            if score > best:
                best = score
                chosen = b
        if chosen is None or not chosen.theory_cards:
            return ReviewBundle(candidate_id=analyte.name)
        return chosen

    def summarise(
        self,
        bundle: ReviewBundle,
        analyte: TargetAnalyte,
    ) -> dict[str, float]:
        """Compact summary consumed by the predictive model."""
        return {
            "theory_alignment": bundle.theory_alignment_score(),
            "contradiction_penalty": bundle.contradiction_penalty(),
            "experiment_readiness": bundle.experiment_readiness_score(),
            "review_confidence": bundle.review_confidence,
            "n_theory_cards": float(len(bundle.theory_cards)),
            "expected_peak_v": float(analyte.expected_redox_potential_v),
            "expected_lod_uM": float(analyte.expected_lod_uM),
        }


__all__ = ["ScientificPriors"]
