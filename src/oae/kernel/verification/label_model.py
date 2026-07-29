"""Majority-vote label model for Phase E.

The label model takes the LF outputs for a single candidate and produces
a posterior credibility distribution over ``{credible, not_credible}``.

This implementation is an intentionally-simple confidence-weighted
majority vote. A matrix-completion upgrade (Snorkel's standard label
model) is deferred until a gold-set has accumulated — the verifier
slot-swaps it through the ``LabelModel`` protocol below.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from src.oae.kernel.schemas import LabelModelPosterior, LFOutput


class LabelModel(Protocol):
    """Structural type for any Phase-E label model."""

    name: str

    def fit(self, lf_outputs: Iterable[Iterable[LFOutput]]) -> None: ...

    def predict(self, lf_outputs: Iterable[LFOutput]) -> LabelModelPosterior: ...


@dataclass
class MajorityVoteLabelModel:
    """Confidence-weighted majority vote over LF outputs.

    Parameters
    ----------
    prior:
        Prior credibility when every LF abstains. Defaults to 0.5.
    epsilon:
        Smoothing constant that prevents zero-width confidence intervals.
    """

    prior: float = 0.5
    epsilon: float = 0.05
    name: str = "majority_vote"

    def fit(self, lf_outputs: Iterable[Iterable[LFOutput]]) -> None:
        """No-op — majority vote is parameter-free.

        Present so the class satisfies the :class:`LabelModel` protocol
        and the matrix-completion upgrade can drop in without touching
        call sites.
        """
        return None

    def predict(self, lf_outputs: Iterable[LFOutput]) -> LabelModelPosterior:
        outputs = [lf for lf in lf_outputs if lf.vote != 0]
        if not outputs:
            return LabelModelPosterior(
                credibility_prob=self.prior,
                confidence_interval=(max(0.0, self.prior - self.epsilon),
                                     min(1.0, self.prior + self.epsilon)),
                source_disagreement=0.0,
                model=self.name,
            )

        pos_weight = sum(lf.confidence for lf in outputs if lf.vote == 1)
        neg_weight = sum(lf.confidence for lf in outputs if lf.vote == -1)
        total = pos_weight + neg_weight

        if total <= 0.0:
            # Non-zero votes but every LF reported zero confidence: fall
            # back to raw counts so the signal is not discarded.
            pos_weight = float(sum(1 for lf in outputs if lf.vote == 1))
            neg_weight = float(sum(1 for lf in outputs if lf.vote == -1))
            total = pos_weight + neg_weight

        credibility = pos_weight / total if total > 0 else self.prior
        credibility = max(0.0, min(1.0, credibility))

        minority = min(pos_weight, neg_weight)
        source_disagreement = (2.0 * minority) / total if total > 0 else 0.0

        width = self.epsilon + 0.5 * source_disagreement
        lower = max(0.0, credibility - width)
        upper = min(1.0, credibility + width)

        return LabelModelPosterior(
            credibility_prob=credibility,
            confidence_interval=(lower, upper),
            source_disagreement=source_disagreement,
            model=self.name,
        )
