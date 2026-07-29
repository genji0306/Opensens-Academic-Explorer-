"""Verification schemas — Snorkel-style weak-supervision artifacts (Phase B).

Produced by the verifier stage in ``MaterialDiscoveryLoop``. Each
evidence source contributes a labeling function (LF) output. A label
model aggregates them into a posterior credibility probability that
feeds Agent Ob as a separate sub-score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LFVote = Literal[-1, 0, 1]
# -1 = contradict, 0 = abstain, 1 = support


@dataclass(frozen=True)
class LFOutput:
    """Result of one labeling function applied to one candidate."""

    lf_name: str
    vote: LFVote = 0
    confidence: float = 0.0            # LF self-confidence 0.0–1.0
    rationale: str = ""
    source: str = ""                   # connector / tool / heuristic id


@dataclass(frozen=True)
class LabelModelPosterior:
    """Posterior over {credible, not_credible} from the label model."""

    credibility_prob: float = 0.5      # 0.0–1.0
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    source_disagreement: float = 0.0   # 0.0–1.0, 1 = maximum conflict
    model: str = "majority_vote"       # "majority_vote" | "matrix_completion" | ...


@dataclass(frozen=True)
class SliceReport:
    """Per-slice verification diagnostics (Snorkel slicing)."""

    slice_name: str                    # e.g. "family=cuprate", "novelty=high"
    n_candidates: int = 0
    coverage: float = 0.0              # fraction of candidates with >=1 LF vote
    overlap: float = 0.0               # fraction of candidates with >=2 LF votes
    conflict: float = 0.0              # fraction where LFs disagree
    avg_credibility: float = 0.0


@dataclass(frozen=True)
class VerificationBundle:
    """Full verification output for one candidate.

    Emitted into the OAEResultPackage and consumed by Agent Ob as the
    ``verification_confidence`` sub-score.
    """

    candidate_id: str
    lf_outputs: tuple[LFOutput, ...] = field(default_factory=tuple)
    posterior: LabelModelPosterior = field(default_factory=LabelModelPosterior)
    slices: tuple[SliceReport, ...] = field(default_factory=tuple)
    provenance: dict[str, str] = field(default_factory=dict)

    def coverage(self) -> float:
        """Fraction of non-abstain LF votes."""
        if not self.lf_outputs:
            return 0.0
        active = sum(1 for lf in self.lf_outputs if lf.vote != 0)
        return active / len(self.lf_outputs)

    def conflict(self) -> float:
        """Fraction measuring how split the non-abstain LFs are.

        Returns 0.0 when LFs agree unanimously, 1.0 at a perfect 50/50
        split. Abstentions are excluded from the denominator.
        """
        votes = [lf.vote for lf in self.lf_outputs if lf.vote != 0]
        if len(votes) < 2:
            return 0.0
        supports = sum(1 for v in votes if v == 1)
        contradicts = len(votes) - supports
        minority = min(supports, contradicts)
        return (2.0 * minority) / len(votes)

    def verification_confidence(self) -> float:
        """Score in [0.0, 1.0] consumed by Agent Ob as a sub-score.

        Combines posterior credibility with a disagreement penalty so
        high-credibility-but-high-conflict candidates are down-weighted.
        """
        return max(
            0.0,
            min(1.0, self.posterior.credibility_prob * (1.0 - self.conflict())),
        )


def empty_verification_bundle(candidate_id: str) -> VerificationBundle:
    """Return a neutral VerificationBundle when verification is disabled."""
    return VerificationBundle(candidate_id=candidate_id)
