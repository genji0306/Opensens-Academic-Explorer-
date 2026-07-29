"""Known dead-end pattern library for RH research campaigns."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .obligation_ledger import normalize_obligation


_PATTERNS = (
    {
        "pattern_id": "classical_critical_line_reuse",
        "title": "Classical critical-line reuse",
        "rejection_reason": "Critical-line identities alone do not exclude off-line zeros.",
        "penalty": 0.08,
    },
    {
        "pattern_id": "finite_window_well_depth",
        "title": "Finite-window well-depth claim",
        "rejection_reason": "Finite-window or sampled depth evidence must be upgraded into a global tail-control argument.",
        "penalty": 0.10,
    },
    {
        "pattern_id": "spectral_matching_surrogate",
        "title": "Spectral-matching surrogate",
        "rejection_reason": "Spectral agreement is not enough without a rigorous, non-surrogate operator argument.",
        "penalty": 0.09,
    },
    {
        "pattern_id": "generic_explicit_formula_restatement",
        "title": "Generic explicit-formula restatement",
        "rejection_reason": "Restating the explicit formula without new exclusion or tail control does not reduce the proof burden.",
        "penalty": 0.07,
    },
    {
        "pattern_id": "descriptive_visualization_only",
        "title": "Descriptive visualization only",
        "rejection_reason": "Visualization or geometric intuition must be translated into a falsifiable invariant.",
        "penalty": 0.06,
    },
    {
        "pattern_id": "quantum_analogy_without_rigor",
        "title": "Quantum analogy without rigor",
        "rejection_reason": "Quantum analogies are advisory unless they produce a rigorous operator or exclusion certificate.",
        "penalty": 0.08,
    },
    {
        "pattern_id": "statistical_constancy_without_exclusion",
        "title": "Statistical constancy without exclusion",
        "rejection_reason": "Sample concentration on the critical line does not exclude a rare off-line zero.",
        "penalty": 0.08,
    },
    {
        "pattern_id": "lp_equivalent_reformulation",
        "title": "LP-equivalent reformulation loop",
        "rejection_reason": "Restating RH as LP/de Branges/Hermite-Biehler membership without an independent exclusion or dissipation certificate does not break the proof loop.",
        "penalty": 0.10,
    },
    {
        "pattern_id": "conditional_heat_flow_monotonicity",
        "title": "Conditional heat-flow monotonicity",
        "rejection_reason": "Backward heat-flow or zero-trajectory monotonicity is not enough if it only holds on the real-zero locus or under LP-class assumptions.",
        "penalty": 0.10,
    },
)

_PATTERN_MAP = {item["pattern_id"]: item for item in _PATTERNS}


def dead_end_definitions() -> list[dict[str, Any]]:
    return [dict(item) for item in _PATTERNS]


def dead_end_penalty(pattern_ids: Iterable[str]) -> float:
    total = sum(float(_PATTERN_MAP.get(pattern_id, {}).get("penalty", 0.0)) for pattern_id in pattern_ids)
    return min(0.24, total)


def classify_dead_end_patterns(
    *,
    ingredient_families: Iterable[str],
    raw_obligations: Iterable[str],
    risk_flags: Iterable[str] = (),
    novelty_failure_modes: Iterable[str] = (),
    failed_certificate_checks: Iterable[str] = (),
    passed_certificate_checks: Iterable[str] = (),
    claim_text: str = "",
    approach_text: Iterable[str] = (),
) -> tuple[str, ...]:
    families = {str(item) for item in ingredient_families}
    raw_obligation_text = [str(item).lower() for item in raw_obligations]
    normalized_classes = {normalize_obligation(str(item))["obligation_class"] for item in raw_obligations}
    risk_text = " ".join(str(item) for item in risk_flags).lower()
    context_text = " ".join(
        [
            str(claim_text),
            *(str(item) for item in approach_text),
            *(str(item) for item in risk_flags),
            *(str(item) for item in raw_obligations),
        ]
    ).lower()
    failure_modes = {str(item) for item in novelty_failure_modes}
    failed_checks = {str(item) for item in failed_certificate_checks}
    passed_checks = {str(item) for item in passed_certificate_checks}
    atlas_exclusion_cleared = "zero_atlas_exclusion" in passed_checks
    strong_progress_checks = {
        "certificate_search",
        "explicit_formula_tail_control",
        "zero_atlas_exclusion",
        "surface_return_certificate",
    }
    has_non_circular_anchor = bool(strong_progress_checks & passed_checks)

    patterns: set[str] = set()
    if (
        "hardy_z" in families
        and "critical_line_to_global_exclusion" in normalized_classes
    ) or "critical_line_identity_is_classical" in risk_text or (
        "hardy_z" in families
        and any("critical-line" in item or "critical line" in item for item in raw_obligation_text)
    ):
        patterns.add("classical_critical_line_reuse")

    if (
        "finite_window_only" in failure_modes
        or "explicit_formula_tail_control" in normalized_classes
        or "certificate_search" in failed_checks
        or "explicit_formula_tail_control" in failed_checks
    ):
        patterns.add("finite_window_well_depth")

    if families & {"hilbert_polya", "quantum_spectral", "random_matrix"} and (
        {"operator_non_surrogate_rigor", "operator_uniqueness"} & normalized_classes
        or "operator_non_surrogate_rigor" in failed_checks
    ):
        patterns.add("spectral_matching_surrogate")

    if "explicit_formula" in families and (
        {"explicit_formula_tail_control", "off_line_zero_exclusion"} & normalized_classes
    ) and "xi_tail_bridge" not in passed_checks:
        patterns.add("generic_explicit_formula_restatement")

    if (
        "geometric_visualization" in families
        and "visual_or_surrogate_translation" in normalized_classes
        and not atlas_exclusion_cleared
    ):
        patterns.add("descriptive_visualization_only")
    if (
        "geometric_visualization" in families
        and not atlas_exclusion_cleared
        and (
            "zero_atlas_xi_bridge" in failed_checks
            or "counting_law_needs_explicit_error_bound" in failure_modes
            or "zero_sum_relation_needs_tail_control" in failure_modes
        )
    ):
        patterns.add("descriptive_visualization_only")

    if "quantum_spectral" in families and (
        "operator_non_surrogate_rigor" in normalized_classes or "operator_non_surrogate_rigor" in failed_checks
    ):
        patterns.add("quantum_analogy_without_rigor")
    if (
        "statistical_to_theorem_upgrade" in normalized_classes
        or "variance_collapse_exclusion" in failed_checks
        or "theorem-level critical-line confinement" in risk_text
    ):
        patterns.add("statistical_constancy_without_exclusion")
    if (
        not has_non_circular_anchor
        and families & {"de_branges", "xi_function", "hardy_z", "general_analytic"}
        and any(
            token in context_text
            for token in (
                "laguerre-polya",
                "laguerre polya",
                "lp class",
                "lp membership",
                "hermite-biehler",
                "hermite biehler",
                "de branges",
                "sturm-polya",
                "sturm polya",
                "turan-cramer",
                "turán-cramér",
            )
        )
    ):
        patterns.add("lp_equivalent_reformulation")
    if (
        not has_non_circular_anchor
        and any(
            token in context_text
            for token in (
                "rodgers-tao",
                "de bruijn-newman",
                "newman lambda",
                "backward heat flow",
                "heat-flow",
                "heat flow",
                "zero ode",
                "zero trajectory",
                "anti-herglotz",
            )
        )
        and not any(
            token in context_text
            for token in (
                "unconditional",
                "lyapunov",
                "wasserstein",
                "entropy",
                "dissipation",
                "transport",
                "pair interaction",
            )
        )
    ):
        patterns.add("conditional_heat_flow_monotonicity")
    return tuple(sorted(patterns))


def build_dead_end_library_artifact(
    *,
    campaign_id: str,
    rounds: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    campaign_hits: list[dict[str, Any]] = []
    hit_counts: Counter[str] = Counter()

    for round_payload in rounds:
        round_index = int(round_payload.get("round_index", 0))
        hypotheses = {
            str(item.get("candidate_id", "")): item
            for item in round_payload.get("hypotheses", [])
        }
        novelty = {}
        for item in round_payload.get("novelty", []):
            novelty.setdefault(str(item.get("linked_hypothesis_id", "")), []).append(item)
        for evaluation in round_payload.get("evaluations", []):
            candidate_id = str(evaluation.get("candidate_id", ""))
            hypothesis = hypotheses.get(candidate_id, {})
            failure_modes = [
                str(mode)
                for artifact in novelty.get(candidate_id, [])
                for mode in artifact.get("failure_modes", ())
            ]
            failed_checks = [
                str(check.get("check_id", ""))
                for check in evaluation.get("check_results", [])
                if str(check.get("category", "")) == "certificate" and not bool(check.get("passed", False))
            ]
            pattern_ids = classify_dead_end_patterns(
                ingredient_families=hypothesis.get("ingredient_families", ()),
                raw_obligations=hypothesis.get("unresolved_proof_obligations", ()),
                risk_flags=hypothesis.get("risk_flags", ()),
                novelty_failure_modes=failure_modes,
                failed_certificate_checks=failed_checks,
                passed_certificate_checks=[
                    str(check.get("check_id", ""))
                    for check in evaluation.get("check_results", [])
                    if str(check.get("category", "")) == "certificate" and bool(check.get("passed", False))
                ],
                claim_text=str(hypothesis.get("claim", "")),
            )
            if not pattern_ids:
                continue
            hit_counts.update(pattern_ids)
            campaign_hits.append(
                {
                    "candidate_id": candidate_id,
                    "round_index": round_index,
                    "score": float(evaluation.get("score", 0.0)),
                    "pattern_ids": pattern_ids,
                }
            )

    return {
        "campaign_id": campaign_id,
        "patterns": dead_end_definitions(),
        "campaign_hits": campaign_hits,
        "hit_counts": dict(sorted(hit_counts.items())),
        "summary": {
            "top_patterns": [
                {"pattern_id": name, "count": count, "rejection_reason": _PATTERN_MAP[name]["rejection_reason"]}
                for name, count in sorted(hit_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
            ],
        },
    }


def score_candidate_dead_end_risk(
    candidate_id: str,
    ingredient_families: tuple[str, ...],
    failure_classes: tuple[str, ...],
    *,
    dead_end_history: dict[str, int] | None = None,
) -> tuple[float, list[str]]:
    """Compute dead-end risk score for a candidate (Phase 5 predictive vaccination).

    Returns (risk_score, blocking_pattern_ids) where risk_score in [0, 1].
    If risk_score > 0.85, the candidate should be blocked unless it cites
    a lemma that nullifies the blocker.
    """
    history = dead_end_history or {}
    risk_score = 0.0
    blocking_pattern_ids: list[str] = []

    for pattern in _PATTERNS:
        pattern_id: str = pattern["pattern_id"]
        if pattern_id not in failure_classes:
            continue
        base_penalty = float(pattern["penalty"])
        multiplier = 1.5 if history.get(pattern_id, 0) >= 5 else 1.0
        risk_score += base_penalty * multiplier
        blocking_pattern_ids.append(pattern_id)

    return min(1.0, risk_score), blocking_pattern_ids


def should_block_candidate(
    candidate_id: str,
    ingredient_families: tuple[str, ...],
    failure_classes: tuple[str, ...],
    nullifying_lemma_ids: tuple[str, ...] = (),
    *,
    dead_end_history: dict[str, int] | None = None,
    risk_threshold: float = 0.85,
) -> tuple[bool, str]:
    """Returns (should_block, reason). A candidate with risk > 0.85 is blocked
    unless it cites a nullifying lemma for each blocker.
    """
    risk, blockers = score_candidate_dead_end_risk(
        candidate_id, ingredient_families, failure_classes,
        dead_end_history=dead_end_history,
    )
    if risk <= risk_threshold:
        return False, ""
    unmitigated = [b for b in blockers if not any(lemma_id in b for lemma_id in nullifying_lemma_ids)]
    if not unmitigated:
        return False, ""
    return True, f"risk={risk:.2f} blockers={','.join(unmitigated)}"
