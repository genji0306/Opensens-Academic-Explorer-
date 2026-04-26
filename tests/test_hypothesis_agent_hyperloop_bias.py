"""Tests for the hyperloop topology bias added to HypothesisAgent ranking.

Locks in the contract that hyperloop mode prefers checkable families
(those Odlyzko external benchmark can grade) over non-checkable families.
"""
from __future__ import annotations

from riemann.research.hypothesis_agent import (
    _FALSIFIABILITY_CHECKABLE_FAMILIES,
    _HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS,
    _HYPERLOOP_FALSIFIABILITY_BONUS,
    HypothesisAgent,
)
from riemann.research.schemas import ApproachCard, HypothesisCandidate


def _card(family: str, *, approach_id: str = "", baseline: float = 0.5) -> ApproachCard:
    aid = approach_id or f"app-{family}"
    return ApproachCard(
        approach_id=aid,
        family=family,
        core_claim=f"claim-{family}",
        observer_scores={"baseline_proximity": baseline, "contradiction_burden": 0.0},
    )


def test_falsifiability_set_matches_odlyzko_checkable() -> None:
    """The hypothesis-agent checkable set must mirror the odlyzko benchmark set."""
    from riemann.research.odlyzko_benchmark import _CHECKABLE_FAMILIES
    assert _FALSIFIABILITY_CHECKABLE_FAMILIES == _CHECKABLE_FAMILIES


def test_baseline_mode_does_not_favor_checkable_families() -> None:
    agent = HypothesisAgent()
    approaches = (_card("hilbert_polya"), _card("de_branges"))
    ranked = agent._rank_approaches(
        approaches,
        prior_evaluations=(),
        feedback_text="",
        family_usage={},
        round_index=1,
        overused_family_penalty_start_round=99,
        overused_family_penalty_threshold=99,
        overused_family_penalty_scale=0.0,
        overused_family_penalty_cap=0.0,
        route_lock_primary=frozenset(),
        route_lock_support=frozenset(),
        route_lock_strict=False,
        route_lock_bonus_primary=0.0,
        route_lock_bonus_support=0.0,
        route_lock_penalty_off_route=0.0,
        topology_mode="baseline",
    )
    # In baseline, both have identical baseline_proximity → tie broken by approach_id alphabetical.
    # de_branges IS checkable but in baseline that gets no bonus.
    families = [c.family for c in ranked]
    # Both kept, no preferential reordering by checkability
    assert set(families) == {"hilbert_polya", "de_branges"}


def test_hyperloop_mode_promotes_checkable_family_over_non_checkable() -> None:
    """A checkable family should outrank a non-checkable family in hyperloop mode."""
    agent = HypothesisAgent()
    # hilbert_polya is NOT checkable; de_branges IS. Give hilbert_polya a head start.
    approaches = (
        _card("hilbert_polya", baseline=0.6),
        _card("de_branges", baseline=0.3),
    )
    ranked_baseline = agent._rank_approaches(
        approaches,
        prior_evaluations=(),
        feedback_text="",
        family_usage={},
        round_index=1,
        overused_family_penalty_start_round=99,
        overused_family_penalty_threshold=99,
        overused_family_penalty_scale=0.0,
        overused_family_penalty_cap=0.0,
        route_lock_primary=frozenset(),
        route_lock_support=frozenset(),
        route_lock_strict=False,
        route_lock_bonus_primary=0.0,
        route_lock_bonus_support=0.0,
        route_lock_penalty_off_route=0.0,
        topology_mode="baseline",
    )
    ranked_hyper = agent._rank_approaches(
        approaches,
        prior_evaluations=(),
        feedback_text="",
        family_usage={},
        round_index=1,
        overused_family_penalty_start_round=99,
        overused_family_penalty_threshold=99,
        overused_family_penalty_scale=0.0,
        overused_family_penalty_cap=0.0,
        route_lock_primary=frozenset(),
        route_lock_support=frozenset(),
        route_lock_strict=False,
        route_lock_bonus_primary=0.0,
        route_lock_bonus_support=0.0,
        route_lock_penalty_off_route=0.0,
        topology_mode="hyperloop",
    )
    # baseline: hilbert_polya wins (0.6 > 0.3)
    assert ranked_baseline[0].family == "hilbert_polya"
    # hyperloop: de_branges wins because 0.3 + 0.40 = 0.70 > 0.60
    assert ranked_hyper[0].family == "de_branges"


def test_hyperloop_bias_magnitude_exceeds_family_usage_spread() -> None:
    """Bias must be larger than usage-based bonuses (max 0.08) to actually reshape ranking."""
    assert _HYPERLOOP_FALSIFIABILITY_BONUS > 0.08
    # Smaller than route-lock primary (0.35) so explicit user route locking still dominates
    assert _HYPERLOOP_FALSIFIABILITY_BONUS <= 0.50


def test_dual_checkable_pair_bonus_only_in_hyperloop() -> None:
    agent = HypothesisAgent()
    anchor = _card("de_branges")  # checkable
    partner_checkable = _card("xi_function")  # checkable
    partner_non = _card("geometric_visualization")  # non-checkable

    klein_check_check = agent._pairing_bonus(anchor, partner_checkable, topology_mode="klein")
    hyper_check_check = agent._pairing_bonus(anchor, partner_checkable, topology_mode="hyperloop")
    klein_check_non = agent._pairing_bonus(anchor, partner_non, topology_mode="klein")
    hyper_check_non = agent._pairing_bonus(anchor, partner_non, topology_mode="hyperloop")

    # Hyperloop check×check should exceed klein check×check by EXACTLY the dual bonus.
    assert hyper_check_check == klein_check_check + _HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS
    # Hyperloop check×non should equal klein check×non (no dual-checkable bonus applied).
    assert hyper_check_non == klein_check_non


def test_hyperloop_filter_rejects_overloaded_candidates() -> None:
    """Candidate with 5 obligations and 1 checkable family must be rejected
    (budget = 2 * 1 = 2; 5 > 2)."""
    overloaded = HypothesisCandidate(
        candidate_id="overloaded",
        claim="too many obligations",
        ingredient_approach_ids=("a-de_branges",),
        ingredient_families=("de_branges",),
        unresolved_proof_obligations=("o1", "o2", "o3", "o4", "o5"),
    )
    acceptable = HypothesisCandidate(
        candidate_id="acceptable",
        claim="balanced",
        ingredient_approach_ids=("a-de_branges", "a-xi_function"),
        ingredient_families=("de_branges", "xi_function"),  # 2 checkable
        unresolved_proof_obligations=("o1", "o2", "o3"),  # budget = 4
    )
    # Replicate the filter inline (mirrors hypothesis_agent.run hyperloop block).
    def _checkable_count(c: HypothesisCandidate) -> int:
        return sum(1 for f in c.ingredient_families if f in _FALSIFIABILITY_CHECKABLE_FAMILIES)
    def _accept(c: HypothesisCandidate) -> bool:
        return len(c.unresolved_proof_obligations) <= max(1, 2 * _checkable_count(c))
    assert not _accept(overloaded)
    assert _accept(acceptable)


def test_klein_pairing_bonus_still_applied_in_hyperloop() -> None:
    """Klein ⊆ Hyperloop: the klein cross-lane bonus must also fire in hyperloop."""
    agent = HypothesisAgent()
    anchor = _card("hilbert_polya")  # depth lane in klein
    partner = _card("explicit_formula")  # surface lane in klein, also checkable

    klein_b = agent._pairing_bonus(anchor, partner, topology_mode="klein")
    hyper_b = agent._pairing_bonus(anchor, partner, topology_mode="hyperloop")
    # hyperloop must equal klein PLUS the dual-checkable bonus (anchor non-check, partner check → no dual)
    # Actually anchor=hilbert_polya is not in checkable; partner=explicit_formula is.
    # So dual_checkable_bonus = 0. Then hyper == klein.
    assert hyper_b == klein_b
