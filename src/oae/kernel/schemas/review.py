"""Review schemas — Theory cards and review bundles (Phase B).

Data classes produced by Agent R (the review/theory agent) and consumed
by Agent Ob. These are additive layers over existing heuristic scoring;
they never replace domain-specific sub-scores.

All dataclasses are frozen to preserve immutability across the loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SupportLevel = Literal["strong", "moderate", "weak", "unsupported"]
ContradictionLevel = Literal["none", "minor", "major", "blocking"]


@dataclass(frozen=True)
class Citation:
    """A single bibliographic or tool-output reference.

    ``source`` uses a URI-like scheme: ``doi:10...``, ``arxiv:...``,
    ``tool:tooluniverse/literature_search``, ``connector:materials_project``.
    """

    source: str
    title: str = ""
    year: int | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    excerpt: str = ""
    confidence: float = 0.0  # 0.0–1.0, retrieval confidence


@dataclass(frozen=True)
class TheoryCard:
    """Structured claim about a candidate's mechanism or behaviour.

    Produced by Agent R per candidate or family. Prose is secondary — the
    ranking-critical fields are ``support_level``, ``contradiction_level``,
    and ``support_score``.
    """

    claim: str
    mechanism: str
    conditions: str = ""
    support_level: SupportLevel = "weak"
    contradiction_level: ContradictionLevel = "none"
    support_score: float = 0.0         # 0.0–1.0
    contradiction_score: float = 0.0   # 0.0–1.0
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def net_support(self) -> float:
        """Return support minus contradiction, clamped to [-1, 1]."""
        return max(-1.0, min(1.0, self.support_score - self.contradiction_score))


@dataclass(frozen=True)
class RankedMechanism:
    """A mechanism hypothesis with its relative ranking among alternatives."""

    mechanism: str
    rank: int                          # 1 = most likely
    probability: float = 0.0           # 0.0–1.0
    discriminating_experiment: str = ""
    theory_cards: tuple[TheoryCard, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReviewBundle:
    """Complete review output for a candidate or batch.

    Consumed by Agent Ob as four additive sub-scores:
    theory_alignment, evidence_consistency, contradiction_penalty,
    experiment_readiness.
    """

    candidate_id: str
    theory_cards: tuple[TheoryCard, ...] = field(default_factory=tuple)
    ranked_mechanisms: tuple[RankedMechanism, ...] = field(default_factory=tuple)
    support_score: float = 0.0         # aggregate 0.0–1.0
    contradiction_score: float = 0.0   # aggregate 0.0–1.0
    novelty_with_support_score: float = 0.0
    review_confidence: float = 0.0     # Agent R self-confidence 0.0–1.0
    recommended_checks: tuple[str, ...] = field(default_factory=tuple)
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    provenance: dict[str, str] = field(default_factory=dict)

    def theory_alignment_score(self) -> float:
        """Aggregate theory alignment for Agent Ob.

        Combines support, inverse contradiction, and review confidence.
        Result is clamped to [0.0, 1.0].
        """
        base = self.support_score - self.contradiction_score
        weighted = 0.5 * base + 0.5 * self.review_confidence * self.support_score
        return max(0.0, min(1.0, weighted))

    def contradiction_penalty(self) -> float:
        """Penalty in [0.0, 1.0] applied to the final ranking score."""
        return max(0.0, min(1.0, self.contradiction_score))

    def experiment_readiness_score(self) -> float:
        """Readiness in [0.0, 1.0] based on recommended checks and support."""
        if not self.recommended_checks:
            return self.support_score
        coverage = min(1.0, len(self.recommended_checks) / 3.0)
        return 0.5 * self.support_score + 0.5 * coverage


def empty_review_bundle(candidate_id: str) -> ReviewBundle:
    """Return a no-op ReviewBundle for candidates that skipped review.

    Used by the loop's ``_maybe_review`` hook when review is disabled.
    """
    return ReviewBundle(candidate_id=candidate_id)
