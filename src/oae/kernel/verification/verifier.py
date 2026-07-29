"""Snorkel verifier entry point — Phase E.

The verifier glues the labeling functions, the label model, and the
slicing diagnostics together. It consumes a ``ScoredBatch``-like object
and returns both a per-candidate mapping of :class:`VerificationBundle`
(what Agent Ob and the ``OAEResultPackage`` want) and a
:class:`VerifierReport` summarising slice metrics for the run.

The verifier is intentionally duck-typed: it never imports
``src.core.discovery_loop`` so the ``src/oae/`` tree stays import-clean.
Callers pass any object with a ``candidates`` iterable and each
candidate exposes the attributes described in
``labeling_functions._CandidateLike``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence

from src.oae.kernel.schemas import (
    ReviewBundle,
    SliceReport,
    VerificationBundle,
    empty_verification_bundle,
)

from .label_model import LabelModel, MajorityVoteLabelModel
from .labeling_functions import (
    CandidateContext,
    DEFAULT_LABELING_FUNCTIONS,
    LabelingFunction,
)
from .slices import SliceDefinition, build_slice_reports, default_slice_definitions

logger = logging.getLogger("SnorkelVerifier")


class _ScoredBatchLike(Protocol):
    candidates: Sequence[Any]


@dataclass(frozen=True)
class VerifierReport:
    """Run-level report emitted alongside the per-candidate bundles."""

    n_candidates: int
    coverage: float
    conflict: float
    avg_credibility: float
    slices: tuple[SliceReport, ...] = field(default_factory=tuple)
    label_model: str = "majority_vote"


@dataclass
class SnorkelVerifier:
    """End-to-end Snorkel-style verifier wired to the ``verify`` hook.

    Usage::

        verifier = SnorkelVerifier()
        bundles, report = verifier.verify_batch(
            scored_batch,
            domain="crystal",
            reviews=agent_r_output,
            connector_agreements=mp_agreements,
        )
    """

    labeling_functions: tuple[LabelingFunction, ...] = DEFAULT_LABELING_FUNCTIONS
    label_model: LabelModel = field(default_factory=MajorityVoteLabelModel)
    slice_definitions: tuple[SliceDefinition, ...] = field(
        default_factory=default_slice_definitions
    )

    # ---- public API -------------------------------------------------------

    def verify_batch(
        self,
        scored: _ScoredBatchLike,
        *,
        domain: str = "",
        reviews: Mapping[str, ReviewBundle] | None = None,
        connector_agreements: Mapping[str, Mapping[str, float]] | None = None,
        extra: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> tuple[dict[str, VerificationBundle], VerifierReport]:
        """Verify every candidate in a scored batch.

        Parameters mirror what the discovery loop has available at the
        ``verify`` stage. Missing context is handled gracefully: LFs
        abstain and the verifier still emits neutral bundles.
        """
        candidates = list(getattr(scored, "candidates", []) or [])
        if not candidates:
            empty_report = VerifierReport(
                n_candidates=0,
                coverage=0.0,
                conflict=0.0,
                avg_credibility=self.label_model.predict([]).credibility_prob,
                slices=tuple(),
                label_model=self.label_model.name,
            )
            return {}, empty_report

        reviews = reviews or {}
        connector_agreements = connector_agreements or {}
        extra = extra or {}

        bundles: dict[str, VerificationBundle] = {}
        pairs: list[tuple[CandidateContext, VerificationBundle]] = []

        for candidate in candidates:
            cid = getattr(candidate, "candidate_id", "") or ""
            if not cid:
                logger.debug("skipping candidate without candidate_id")
                continue

            ctx = CandidateContext(
                candidate=candidate,
                domain=domain,
                review=reviews.get(cid),
                connector_agreement=connector_agreements.get(cid, {}),
                extra=extra.get(cid, {}),
            )

            bundle = self.verify_candidate(ctx)
            bundles[cid] = bundle
            pairs.append((ctx, bundle))

        slice_reports = build_slice_reports(
            pairs,
            list(self.slice_definitions) + self._family_slices(pairs),
        )
        report = self._build_run_report(pairs, slice_reports)
        return bundles, report

    def verify_candidate(self, ctx: CandidateContext) -> VerificationBundle:
        """Apply all labeling functions to a single candidate."""
        lf_outputs = []
        for lf in self.labeling_functions:
            try:
                lf_outputs.append(lf(ctx))
            except Exception as exc:
                logger.warning("LF %s crashed: %s", getattr(lf, "__name__", "?"), exc)

        posterior = self.label_model.predict(lf_outputs)

        return VerificationBundle(
            candidate_id=ctx.candidate.candidate_id,
            lf_outputs=tuple(lf_outputs),
            posterior=posterior,
            provenance={
                "label_model": self.label_model.name,
                "n_labeling_functions": str(len(self.labeling_functions)),
                "domain": ctx.domain,
            },
        )

    # ---- helpers ----------------------------------------------------------

    def _family_slices(
        self,
        pairs: Sequence[tuple[CandidateContext, VerificationBundle]],
    ) -> list[SliceDefinition]:
        families = {
            getattr(ctx.candidate, "family", "")
            for ctx, _ in pairs
            if getattr(ctx.candidate, "family", "")
        }
        return [
            SliceDefinition(
                name=f"family={family}",
                predicate=lambda ctx, target=family: getattr(ctx.candidate, "family", "") == target,
            )
            for family in sorted(families)
        ]

    def _build_run_report(
        self,
        pairs: Sequence[tuple[CandidateContext, VerificationBundle]],
        slice_reports: Iterable[SliceReport],
    ) -> VerifierReport:
        n = len(pairs)
        if n == 0:
            return VerifierReport(
                n_candidates=0,
                coverage=0.0,
                conflict=0.0,
                avg_credibility=0.0,
                slices=tuple(slice_reports),
                label_model=self.label_model.name,
            )

        coverage = sum(bundle.coverage() for _, bundle in pairs) / n
        conflict = sum(bundle.conflict() for _, bundle in pairs) / n
        credibility = sum(
            bundle.posterior.credibility_prob for _, bundle in pairs
        ) / n

        return VerifierReport(
            n_candidates=n,
            coverage=coverage,
            conflict=conflict,
            avg_credibility=credibility,
            slices=tuple(slice_reports),
            label_model=self.label_model.name,
        )


def empty_bundle_map(
    scored: _ScoredBatchLike,
) -> dict[str, VerificationBundle]:
    """Return a neutral bundle map — used when verification is disabled."""
    result: dict[str, VerificationBundle] = {}
    for candidate in getattr(scored, "candidates", []) or []:
        cid = getattr(candidate, "candidate_id", "") or ""
        if cid:
            result[cid] = empty_verification_bundle(cid)
    return result
