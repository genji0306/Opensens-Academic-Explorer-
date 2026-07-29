"""Agent R — offline-first review and theory agent (Phase C MVP).

Agent R sits between ``predict`` and ``score`` in the discovery loop. It
consumes the candidate batch, retrieves relevant mechanism entries from
the seeded mechanism library, ranks them, and emits one
:class:`ReviewBundle` per candidate.

Phase C intentionally does **not** call ToolUniverse or any LLM. The
review stage must run deterministically for the discovery loop,
research memory, and dossier writer to be exercised end-to-end. Phase G
wires in the external tool broker as an additional retrieval source.

Integration contract with ``MaterialDiscoveryLoop``::

    loop.review(candidates) -> dict[candidate_id, ReviewBundle]

The returned mapping is stored on ``loop._last_review`` and can be
consumed by subclasses during scoring. Agent Ob integration is deferred
to Phase C.2 — this module only produces bundles, it never mutates
``ScoredBatch``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from src.oae.agents.r.mechanism_library import (
    LibraryEntry,
    library_entries,
    theory_cards_for_family,
)
from src.oae.kernel.schemas import (
    Citation,
    RankedMechanism,
    ReviewBundle,
    TheoryCard,
    empty_review_bundle,
)

logger = logging.getLogger("AgentR")


class _CandidateLike(Protocol):
    """Duck-type of ``LoopCandidate`` — avoids importing from src.core."""

    candidate_id: str
    family: str
    composition: str
    mechanism: str
    metadata: dict


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentRConfig:
    """Static configuration for an Agent R instance.

    Defaults produce deterministic behaviour suitable for tests and
    Phase C integration runs.
    """

    max_mechanisms_per_candidate: int = 3
    default_recommended_checks: tuple[str, ...] = (
        "literature cross-check",
        "baseline property measurement",
        "synthesizability sanity check",
    )
    novelty_support_threshold: float = 0.50
    min_review_confidence: float = 0.10


# ---------------------------------------------------------------------------
# Agent R
# ---------------------------------------------------------------------------


@dataclass
class AgentR:
    """Produce :class:`ReviewBundle` objects for a batch of candidates.

    This is Phase C's offline MVP: one entrypoint, no side effects other
    than logging. Consumers drive persistence via the research memory
    and dossier writer in ``src.oae.research``.
    """

    config: AgentRConfig = field(default_factory=AgentRConfig)
    name: str = "agent_r"

    # --- public API ---------------------------------------------------

    def run(
        self,
        candidates: Iterable[_CandidateLike],
    ) -> dict[str, ReviewBundle]:
        """Return a mapping of candidate_id → :class:`ReviewBundle`."""
        bundles: dict[str, ReviewBundle] = {}
        for candidate in candidates:
            bundle = self.review_candidate(candidate)
            bundles[bundle.candidate_id] = bundle
        logger.info("AgentR produced %d review bundle(s)", len(bundles))
        return bundles

    def review_candidate(self, candidate: _CandidateLike) -> ReviewBundle:
        """Build the review bundle for a single candidate."""
        candidate_id = getattr(candidate, "candidate_id", "") or "unknown"
        family = getattr(candidate, "family", "") or ""

        cards = theory_cards_for_family(family)
        if not cards:
            return self._empty_but_traced_bundle(candidate_id, family)

        # Keep only the top-N by net support, deterministic order.
        ranked_cards = tuple(
            sorted(cards, key=lambda c: c.net_support(), reverse=True)
        )[: self.config.max_mechanisms_per_candidate]

        ranked_mechanisms = self._rank_mechanisms(ranked_cards)
        support, contradiction = self._aggregate_scores(ranked_cards)
        novelty = self._novelty_score(support, contradiction)
        review_confidence = max(
            self.config.min_review_confidence,
            min(1.0, support * (1.0 - 0.5 * contradiction)),
        )

        citations = self._flatten_citations(ranked_cards)
        recommended = self._recommended_checks(ranked_cards)

        return ReviewBundle(
            candidate_id=candidate_id,
            theory_cards=ranked_cards,
            ranked_mechanisms=ranked_mechanisms,
            support_score=support,
            contradiction_score=contradiction,
            novelty_with_support_score=novelty,
            review_confidence=review_confidence,
            recommended_checks=recommended,
            citations=citations,
            provenance={
                "agent": self.name,
                "source": "mechanism_library",
                "family": family,
            },
        )

    # --- internals ----------------------------------------------------

    def _empty_but_traced_bundle(
        self,
        candidate_id: str,
        family: str,
    ) -> ReviewBundle:
        """Return an empty bundle tagged with provenance for unknown families."""
        base = empty_review_bundle(candidate_id)
        return ReviewBundle(
            candidate_id=base.candidate_id,
            provenance={
                "agent": self.name,
                "source": "mechanism_library",
                "family": family,
                "status": "no_match",
            },
        )

    def _rank_mechanisms(
        self,
        cards: tuple[TheoryCard, ...],
    ) -> tuple[RankedMechanism, ...]:
        """Rank unique mechanisms by net support probability."""
        seen: set[str] = set()
        unique: list[TheoryCard] = []
        for card in cards:
            if card.mechanism in seen:
                continue
            seen.add(card.mechanism)
            unique.append(card)

        if not unique:
            return ()

        probs = [max(0.0, card.net_support()) for card in unique]
        total = sum(probs) or 1.0
        normalised = [p / total for p in probs]

        return tuple(
            RankedMechanism(
                mechanism=card.mechanism,
                rank=i + 1,
                probability=prob,
                discriminating_experiment=self._discriminating_experiment(card),
                theory_cards=(card,),
            )
            for i, (card, prob) in enumerate(zip(unique, normalised))
        )

    def _aggregate_scores(
        self,
        cards: tuple[TheoryCard, ...],
    ) -> tuple[float, float]:
        """Mean support and contradiction across the top-ranked cards."""
        if not cards:
            return (0.0, 0.0)
        support = sum(c.support_score for c in cards) / len(cards)
        contradiction = sum(c.contradiction_score for c in cards) / len(cards)
        return (max(0.0, min(1.0, support)), max(0.0, min(1.0, contradiction)))

    def _novelty_score(self, support: float, contradiction: float) -> float:
        """Novelty × backed-by-theory signal.

        Novelty here means "supported above a threshold but with some
        contradiction" — a signal that the candidate is interesting but
        not a cliché. Returns a score in [0.0, 1.0].
        """
        if support < self.config.novelty_support_threshold:
            return 0.0
        interesting = min(1.0, contradiction * 2.0)
        return max(0.0, min(1.0, support * interesting))

    def _flatten_citations(
        self,
        cards: tuple[TheoryCard, ...],
    ) -> tuple[Citation, ...]:
        """Deduplicate citations by source field."""
        seen: set[str] = set()
        ordered: list[Citation] = []
        for card in cards:
            for cite in card.citations:
                if cite.source in seen:
                    continue
                seen.add(cite.source)
                ordered.append(cite)
        return tuple(ordered)

    def _recommended_checks(
        self,
        cards: tuple[TheoryCard, ...],
    ) -> tuple[str, ...]:
        """Emit checks tailored to the contradiction level of the top cards."""
        if not cards:
            return self.config.default_recommended_checks
        checks = list(self.config.default_recommended_checks)
        for card in cards:
            if card.contradiction_level in ("major", "blocking"):
                checks.append(
                    f"investigate contradiction for {card.mechanism}"
                )
        # Preserve order, drop duplicates.
        seen: set[str] = set()
        unique: list[str] = []
        for item in checks:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return tuple(unique)

    def _discriminating_experiment(self, card: TheoryCard) -> str:
        """Suggest a cheap next experiment for a given mechanism card."""
        tag_lc = {tag.lower() for tag in card.tags}
        if "eis" in tag_lc:
            return "EIS Rct sweep across frequency window"
        if "voltammetry" in tag_lc:
            return "CV scan-rate study for Randles-Sevcik linearity"
        if "bcs" in tag_lc or "pressure-required" in tag_lc:
            return "ambient-pressure Tc verification via susceptibility"
        if "flat-band" in tag_lc:
            return "ARPES near Fermi level"
        if "mof" in tag_lc:
            return "PXRD phase identification + N2 isotherm"
        return "property measurement matching mechanism conditions"


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def run_agent_r(candidates: Iterable[_CandidateLike]) -> dict[str, ReviewBundle]:
    """One-shot helper to run Agent R with default configuration."""
    return AgentR().run(candidates)


__all__ = [
    "AgentR",
    "AgentRConfig",
    "run_agent_r",
    "library_entries",
    "LibraryEntry",
]
