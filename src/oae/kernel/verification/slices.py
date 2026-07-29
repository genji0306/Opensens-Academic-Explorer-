"""Snorkel-style slicing diagnostics for Phase E.

Slicing partitions the verified batch along axes that typically hide
systematic failure modes (family, domain, novelty, evidence sparsity).
Each slice contributes a :class:`SliceReport` so downstream dashboards
can surface coverage/conflict drift before it corrupts ranking.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from src.oae.kernel.schemas import SliceReport, VerificationBundle

from .labeling_functions import CandidateContext


SlicePredicate = Callable[[CandidateContext], bool]


@dataclass(frozen=True)
class SliceDefinition:
    """A named predicate partitioning candidates for reporting."""

    name: str
    predicate: SlicePredicate


def default_slice_definitions() -> tuple[SliceDefinition, ...]:
    """Return the built-in slicing axes used by ``SnorkelVerifier``."""

    def _by_family(value: str) -> SlicePredicate:
        return lambda ctx: getattr(ctx.candidate, "family", "") == value

    def _novelty_high(ctx: CandidateContext) -> bool:
        return bool(ctx.meta("is_novel", False))

    def _evidence_sparse(ctx: CandidateContext) -> bool:
        if ctx.review is None:
            return True
        return not ctx.review.citations and not any(
            card.citations for card in ctx.review.theory_cards
        )

    def _domain_sensing(ctx: CandidateContext) -> bool:
        return ctx.domain in ("sensing", "sensor")

    def _domain_crystal(ctx: CandidateContext) -> bool:
        return ctx.domain in ("crystal", "mof", "rtap")

    return (
        SliceDefinition("novelty=high", _novelty_high),
        SliceDefinition("evidence=sparse", _evidence_sparse),
        SliceDefinition("domain=sensing", _domain_sensing),
        SliceDefinition("domain=crystal", _domain_crystal),
        # Dynamic family slices are appended by the verifier based on the
        # batch. The defaults above cover the axes required by Phase E.
    )


def build_slice_reports(
    pairs: Sequence[tuple[CandidateContext, VerificationBundle]],
    definitions: Iterable[SliceDefinition],
) -> tuple[SliceReport, ...]:
    """Aggregate per-slice coverage / overlap / conflict diagnostics."""
    reports: list[SliceReport] = []
    for definition in definitions:
        members = [
            (ctx, bundle) for ctx, bundle in pairs if definition.predicate(ctx)
        ]
        if not members:
            reports.append(SliceReport(slice_name=definition.name, n_candidates=0))
            continue

        coverages: list[float] = []
        overlaps: list[float] = []
        conflicts: list[float] = []
        credibilities: list[float] = []
        for _, bundle in members:
            coverages.append(bundle.coverage())
            non_abstain = sum(1 for lf in bundle.lf_outputs if lf.vote != 0)
            overlaps.append(1.0 if non_abstain >= 2 else 0.0)
            conflicts.append(bundle.conflict())
            credibilities.append(bundle.posterior.credibility_prob)

        n = len(members)
        reports.append(
            SliceReport(
                slice_name=definition.name,
                n_candidates=n,
                coverage=sum(coverages) / n,
                overlap=sum(overlaps) / n,
                conflict=sum(conflicts) / n,
                avg_credibility=sum(credibilities) / n,
            )
        )
    return tuple(reports)
