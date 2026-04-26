"""Labeling functions for the Snorkel verifier (Phase E).

A labeling function (LF) inspects a single candidate in its surrounding
context and emits one :class:`LFOutput`. Votes follow the Snorkel
convention::

    +1 = support / credible
     0 = abstain
    -1 = contradict / not credible

Every LF is a pure function over a :class:`CandidateContext` so the
verifier, tests, and slice diagnostics stay deterministic. LFs never
raise — on missing data they abstain.

The library intentionally ships twelve diverse LFs covering theory
alignment, structure plausibility, synthesis feasibility, connector
agreement, sensor-specific heuristics, and simulation hooks (DFT/CFD)
that Phase H will populate. The final list is exported as
``DEFAULT_LABELING_FUNCTIONS``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from src.oae.kernel.schemas import LFOutput, ReviewBundle


# ---------------------------------------------------------------------------
# Candidate context
# ---------------------------------------------------------------------------


class _CandidateLike(Protocol):
    """Duck type matching ``src.core.discovery_loop.LoopCandidate``."""

    candidate_id: str
    family: str
    composition: str
    mechanism: str
    predicted_property: float
    energy_above_hull_meV: float
    confidence: float
    metadata: dict


@dataclass(frozen=True)
class CandidateContext:
    """Everything an LF may inspect for one candidate.

    The verifier assembles this from the ``ScoredBatch`` and optional
    review bundles. LFs should never reach outside the context.
    """

    candidate: _CandidateLike
    domain: str = ""                               # "crystal" | "sensing" | "mof" | ...
    review: ReviewBundle | None = None
    connector_agreement: Mapping[str, float] = field(default_factory=dict)
    extra: Mapping[str, Any] = field(default_factory=dict)

    # ---- convenience accessors -------------------------------------------------
    @property
    def metadata(self) -> dict:
        return getattr(self.candidate, "metadata", {}) or {}

    def meta(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)


# A labeling function is any callable taking a CandidateContext → LFOutput.
LabelingFunction = Callable[[CandidateContext], LFOutput]


def _abstain(name: str, reason: str = "", source: str = "") -> LFOutput:
    return LFOutput(lf_name=name, vote=0, confidence=0.0, rationale=reason, source=source)


# ---------------------------------------------------------------------------
# 1. Connector agreement
# ---------------------------------------------------------------------------


def lf_connector_agreement(ctx: CandidateContext) -> LFOutput:
    """Vote +1 when external connectors agree on the candidate.

    ``connector_agreement`` is a mapping of connector name → agreement
    score in [0, 1] (e.g. Materials Project, SuperCon, COD).
    """
    name = "connector_agreement"
    scores = list(ctx.connector_agreement.values())
    if not scores:
        return _abstain(name, "no connector evidence available")

    avg = sum(scores) / len(scores)
    if avg >= 0.7:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=min(1.0, avg),
            rationale=f"{len(scores)} connectors agree (avg={avg:.2f})",
            source="connectors",
        )
    if avg <= 0.3:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=min(1.0, 1.0 - avg),
            rationale=f"{len(scores)} connectors disagree (avg={avg:.2f})",
            source="connectors",
        )
    return _abstain(name, f"connector signal inconclusive (avg={avg:.2f})", "connectors")


# ---------------------------------------------------------------------------
# 2. Theory support
# ---------------------------------------------------------------------------


def lf_theory_support(ctx: CandidateContext) -> LFOutput:
    """Vote +1 when Agent R's review bundle shows strong positive support."""
    name = "theory_support"
    review = ctx.review
    if review is None or not review.theory_cards:
        return _abstain(name, "no review bundle")

    support = review.support_score
    confidence = review.review_confidence
    if support >= 0.6 and support > review.contradiction_score:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=min(1.0, 0.5 * support + 0.5 * confidence),
            rationale=f"theory_support={support:.2f}, cards={len(review.theory_cards)}",
            source="agent_r",
        )
    return _abstain(name, f"weak support ({support:.2f})", "agent_r")


# ---------------------------------------------------------------------------
# 3. Theory contradiction
# ---------------------------------------------------------------------------


def lf_theory_contradiction(ctx: CandidateContext) -> LFOutput:
    """Vote -1 when Agent R flags significant contradiction evidence."""
    name = "theory_contradiction"
    review = ctx.review
    if review is None:
        return _abstain(name, "no review bundle")

    contradiction = review.contradiction_score
    if contradiction >= 0.5:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=min(1.0, contradiction),
            rationale=f"contradiction={contradiction:.2f}",
            source="agent_r",
        )
    return _abstain(name, f"contradiction below threshold ({contradiction:.2f})", "agent_r")


# ---------------------------------------------------------------------------
# 4. Structure plausibility (energy above hull)
# ---------------------------------------------------------------------------


def lf_structure_plausibility(ctx: CandidateContext) -> LFOutput:
    """Vote +1 when the candidate sits close to the convex hull."""
    name = "structure_plausibility"
    e_hull = float(getattr(ctx.candidate, "energy_above_hull_meV", 0.0) or 0.0)

    if e_hull <= 0.0 and not ctx.meta("has_energy_estimate", False):
        return _abstain(name, "no hull energy reported")

    if e_hull <= 50.0:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=1.0 - min(1.0, e_hull / 50.0),
            rationale=f"e_hull={e_hull:.1f} meV",
            source="heuristic",
        )
    if e_hull >= 200.0:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=min(1.0, (e_hull - 200.0) / 300.0 + 0.3),
            rationale=f"e_hull={e_hull:.1f} meV",
            source="heuristic",
        )
    return _abstain(name, f"e_hull={e_hull:.1f} meV (borderline)", "heuristic")


# ---------------------------------------------------------------------------
# 5. Synthesis feasibility
# ---------------------------------------------------------------------------


def lf_synthesis_feasibility(ctx: CandidateContext) -> LFOutput:
    """Vote on candidate synthesizability metadata flag."""
    name = "synthesis_feasibility"
    score = ctx.meta("synthesizability")
    if score is None:
        return _abstain(name, "no synthesizability score")

    value = float(score)
    if value >= 0.6:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=value,
            rationale=f"synthesizability={value:.2f}",
            source="heuristic",
        )
    if value <= 0.3:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=1.0 - value,
            rationale=f"synthesizability={value:.2f}",
            source="heuristic",
        )
    return _abstain(name, f"synthesizability borderline ({value:.2f})")


# ---------------------------------------------------------------------------
# 6. MP energy sanity
# ---------------------------------------------------------------------------


def lf_mp_energy_sanity(ctx: CandidateContext) -> LFOutput:
    """Vote -1 when the MP-reported formation energy is absurd."""
    name = "mp_energy_sanity"
    formation_eV = ctx.meta("formation_energy_per_atom")
    if formation_eV is None:
        return _abstain(name, "no MP formation energy")

    value = float(formation_eV)
    if -5.0 <= value <= 1.0:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=0.6,
            rationale=f"formation_energy={value:.2f} eV/atom",
            source="materials_project",
        )
    return LFOutput(
        lf_name=name,
        vote=-1,
        confidence=0.8,
        rationale=f"formation_energy out of range ({value:.2f} eV/atom)",
        source="materials_project",
    )


# ---------------------------------------------------------------------------
# 7. Sensor selectivity
# ---------------------------------------------------------------------------


def lf_sensor_selectivity(ctx: CandidateContext) -> LFOutput:
    """Sensing-domain LF: penalise candidates with weak selectivity."""
    name = "sensor_selectivity"
    if ctx.domain and ctx.domain not in ("sensing", "sensor"):
        return _abstain(name, f"not a sensing domain ({ctx.domain})")

    selectivity = ctx.meta("selectivity")
    if selectivity is None:
        return _abstain(name, "no selectivity metric")

    value = float(selectivity)
    if value >= 0.7:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=value,
            rationale=f"selectivity={value:.2f}",
            source="sensor_ob",
        )
    if value <= 0.3:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=1.0 - value,
            rationale=f"selectivity={value:.2f}",
            source="sensor_ob",
        )
    return _abstain(name, f"selectivity borderline ({value:.2f})")


# ---------------------------------------------------------------------------
# 8. Sensor robustness
# ---------------------------------------------------------------------------


def lf_sensor_robustness(ctx: CandidateContext) -> LFOutput:
    """Sensing-domain LF: reject candidates unstable across conditions."""
    name = "sensor_robustness"
    if ctx.domain and ctx.domain not in ("sensing", "sensor"):
        return _abstain(name, f"not a sensing domain ({ctx.domain})")

    robustness = ctx.meta("robustness")
    if robustness is None:
        return _abstain(name, "no robustness metric")

    value = float(robustness)
    if value >= 0.6:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=value,
            rationale=f"robustness={value:.2f}",
            source="agent_e",
        )
    if value <= 0.25:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=1.0 - value,
            rationale=f"robustness={value:.2f}",
            source="agent_e",
        )
    return _abstain(name, f"robustness borderline ({value:.2f})")


# ---------------------------------------------------------------------------
# 9. Novel but unbacked
# ---------------------------------------------------------------------------


def lf_novel_but_unbacked(ctx: CandidateContext) -> LFOutput:
    """Vote -1 when a candidate is flagged novel but lacks any citations."""
    name = "novel_but_unbacked"
    if not ctx.meta("is_novel", False):
        return _abstain(name, "not flagged novel")

    review = ctx.review
    if review is not None and (review.citations or any(tc.citations for tc in review.theory_cards)):
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=0.5,
            rationale="novel with citations",
            source="review",
        )
    return LFOutput(
        lf_name=name,
        vote=-1,
        confidence=0.7,
        rationale="novel but no citations in review bundle",
        source="review",
    )


# ---------------------------------------------------------------------------
# 10. Cross-source consensus
# ---------------------------------------------------------------------------


def lf_cross_source_consensus(ctx: CandidateContext) -> LFOutput:
    """Vote +1 when at least two independent sources back the candidate.

    Sources are counted from: (a) connector_agreement keys with positive
    score, (b) review-bundle citations grouped by their URI scheme.
    """
    name = "cross_source_consensus"
    connectors = {k for k, v in ctx.connector_agreement.items() if v >= 0.5}

    schemes: set[str] = set()
    if ctx.review is not None:
        for citation in ctx.review.citations:
            if ":" in citation.source:
                schemes.add(citation.source.split(":", 1)[0])
            elif citation.source:
                schemes.add(citation.source)
        for card in ctx.review.theory_cards:
            for citation in card.citations:
                if ":" in citation.source:
                    schemes.add(citation.source.split(":", 1)[0])

    sources = connectors | schemes
    if len(sources) >= 2:
        return LFOutput(
            lf_name=name,
            vote=1,
            confidence=min(1.0, 0.3 + 0.2 * len(sources)),
            rationale=f"{len(sources)} independent sources: {sorted(sources)}",
            source="consensus",
        )
    if len(sources) == 0:
        return LFOutput(
            lf_name=name,
            vote=-1,
            confidence=0.5,
            rationale="no independent sources",
            source="consensus",
        )
    return _abstain(name, "single source only")


# ---------------------------------------------------------------------------
# 11. DFT agreement hook (Phase H stub)
# ---------------------------------------------------------------------------


def lf_dft_agreement(ctx: CandidateContext) -> LFOutput:
    """Vote on DFT verification when Simulation Lab results are present."""
    name = "dft_agreement"
    dft = ctx.meta("dft_agreement")
    if dft is None:
        return _abstain(name, "Phase H: no DFT result yet")

    value = float(dft)
    if value >= 0.7:
        return LFOutput(lf_name=name, vote=1, confidence=value,
                        rationale=f"dft_agreement={value:.2f}", source="simulation_lab")
    if value <= 0.3:
        return LFOutput(lf_name=name, vote=-1, confidence=1.0 - value,
                        rationale=f"dft_agreement={value:.2f}", source="simulation_lab")
    return _abstain(name, f"dft borderline ({value:.2f})", "simulation_lab")


# ---------------------------------------------------------------------------
# 12. CFD agreement hook (Phase H stub)
# ---------------------------------------------------------------------------


def lf_cfd_agreement(ctx: CandidateContext) -> LFOutput:
    """Vote on CFD verification — sensing-domain Phase H hook."""
    name = "cfd_agreement"
    cfd = ctx.meta("cfd_agreement")
    if cfd is None:
        return _abstain(name, "Phase H: no CFD result yet")

    value = float(cfd)
    if value >= 0.7:
        return LFOutput(lf_name=name, vote=1, confidence=value,
                        rationale=f"cfd_agreement={value:.2f}", source="simulation_lab")
    if value <= 0.3:
        return LFOutput(lf_name=name, vote=-1, confidence=1.0 - value,
                        rationale=f"cfd_agreement={value:.2f}", source="simulation_lab")
    return _abstain(name, f"cfd borderline ({value:.2f})", "simulation_lab")


DEFAULT_LABELING_FUNCTIONS: tuple[LabelingFunction, ...] = (
    lf_connector_agreement,
    lf_theory_support,
    lf_theory_contradiction,
    lf_structure_plausibility,
    lf_synthesis_feasibility,
    lf_mp_energy_sanity,
    lf_sensor_selectivity,
    lf_sensor_robustness,
    lf_novel_but_unbacked,
    lf_cross_source_consensus,
    lf_dft_agreement,
    lf_cfd_agreement,
)
