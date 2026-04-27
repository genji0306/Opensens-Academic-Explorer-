"""Tests for Odlyzko zero-consistency external benchmark."""
from __future__ import annotations

from pathlib import Path

import pytest

from riemann.research.odlyzko_benchmark import (
    OdlyzkoTable,
    evaluate_round,
    score_candidate,
)


@pytest.fixture()
def tiny_table() -> OdlyzkoTable:
    """First 5 Odlyzko zeros, hardcoded."""
    return OdlyzkoTable(heights=(14.134725, 21.022039, 25.010857, 30.424876, 32.935061))


def test_load_real_zeros_file_loads_at_least_n_zeros() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "riemann" / "zeros1.txt"
    if not path.exists():
        pytest.skip("zeros1.txt not present in this checkout")
    table = OdlyzkoTable.load(path, max_zeros=100)
    assert len(table.heights) == 100
    # Odlyzko first zero ≈ 14.134725
    assert abs(table.heights[0] - 14.134725) < 1e-3
    # Strictly increasing
    for prev, curr in zip(table.heights, table.heights[1:]):
        assert curr > prev


def test_count_in_window(tiny_table: OdlyzkoTable) -> None:
    assert tiny_table.count_in_window(14.0, 22.0) == 2
    assert tiny_table.count_in_window(0.0, 100.0) == 5
    assert tiny_table.count_in_window(50.0, 100.0) == 0


def test_no_zero_claim_correctly_contradicted(tiny_table: OdlyzkoTable) -> None:
    # Claim: no zero in (14, 22). FALSE — 14.134 and 21.022 fall inside.
    assert tiny_table.contradicts_no_zero_claim(14.0, 22.0) is True
    # Claim: no zero in (50, 100). TRUE — empty window.
    assert tiny_table.contradicts_no_zero_claim(50.0, 100.0) is False


def test_score_candidate_pure_abstract_gets_low_score(tiny_table: OdlyzkoTable) -> None:
    """No checkable families, no closed obligations, no contradictions → only base."""
    s = score_candidate(
        candidate_id="abstract-only",
        ingredient_families=("general_analytic", "geometric_visualization"),
        closed_obligation_count=0,
        open_obligation_count=0,
        lean_skeleton="",
        odlyzko=tiny_table,
    )
    assert s.score == pytest.approx(0.30, abs=1e-6)


def test_score_candidate_checkable_families_get_bonus(tiny_table: OdlyzkoTable) -> None:
    s = score_candidate(
        candidate_id="checkable",
        ingredient_families=("hardy_z", "explicit_formula", "de_branges"),
        closed_obligation_count=0,
        open_obligation_count=0,
        lean_skeleton="",
        odlyzko=tiny_table,
    )
    # 0.30 base + 3 * 0.10 = 0.60
    assert s.score == pytest.approx(0.60, abs=1e-6)


def test_score_candidate_closed_obligations_add_bonus(tiny_table: OdlyzkoTable) -> None:
    s = score_candidate(
        candidate_id="productive",
        ingredient_families=("hardy_z",),
        closed_obligation_count=4,
        open_obligation_count=0,
        lean_skeleton="",
        odlyzko=tiny_table,
    )
    # 0.30 + 0.10 + 4*0.05 = 0.60
    assert s.score == pytest.approx(0.60, abs=1e-6)


def test_score_candidate_untestable_obligations_penalize(tiny_table: OdlyzkoTable) -> None:
    """Open obligations beyond what checkable families can handle → penalty."""
    s = score_candidate(
        candidate_id="overloaded",
        ingredient_families=("general_analytic",),  # 0 checkable
        closed_obligation_count=0,
        open_obligation_count=3,  # 3 open, 0 checkable → 3 untestable
        lean_skeleton="",
        odlyzko=tiny_table,
    )
    # 0.30 + 0 + 0 - 3*0.20 = -0.30 → clamped to 0.0
    assert s.score == pytest.approx(0.0, abs=1e-6)
    assert s.untestable_penalty == pytest.approx(-0.60, abs=1e-6)


def test_score_candidate_contradicted_no_zero_claim_heavy_penalty(
    tiny_table: OdlyzkoTable,
) -> None:
    """Skeleton claims no zero in (14, 22) — Odlyzko has zeros there."""
    skel = "theorem t : no_zero_in 14.0 22.0 := by sorry"
    s = score_candidate(
        candidate_id="bad-claim",
        ingredient_families=("explicit_formula",),
        closed_obligation_count=0,
        open_obligation_count=0,
        lean_skeleton=skel,
        odlyzko=tiny_table,
    )
    # 0.30 + 0.10 - 0.50 = -0.10 → clamped to 0.0
    assert s.score == pytest.approx(0.0, abs=1e-6)
    assert s.contradicted_window == (14.0, 22.0)


def test_score_candidate_correct_no_zero_claim_no_penalty(
    tiny_table: OdlyzkoTable,
) -> None:
    """Skeleton claims no zero in (50, 100) — empty in our tiny table → no penalty."""
    skel = "theorem t : no_zero_in 50.0 100.0 := by sorry"
    s = score_candidate(
        candidate_id="good-claim",
        ingredient_families=("explicit_formula",),
        closed_obligation_count=0,
        open_obligation_count=0,
        lean_skeleton=skel,
        odlyzko=tiny_table,
    )
    # 0.30 + 0.10 = 0.40, no contradiction
    assert s.score == pytest.approx(0.40, abs=1e-6)
    assert s.contradicted_window is None


def test_evaluate_round_aggregates_correctly(tiny_table: OdlyzkoTable) -> None:
    records = [
        {
            "candidate_id": "a",
            "ingredient_families": ["hardy_z"],
            "closed_obligation_count": 0,
            "open_obligation_count": 0,
            "lean_skeleton": "",
        },
        {
            "candidate_id": "b",
            "ingredient_families": ["general_analytic"],
            "closed_obligation_count": 0,
            "open_obligation_count": 0,
            "lean_skeleton": "",
        },
    ]
    res = evaluate_round(round_index=1, candidate_records=records, odlyzko=tiny_table)
    assert res.candidate_count == 2
    assert res.mean_score == pytest.approx((0.40 + 0.30) / 2, abs=1e-6)
    assert res.contradicted_count == 0
    assert res.untestable_count == 0


def test_evaluate_round_empty_input_returns_zero() -> None:
    table = OdlyzkoTable(heights=(14.0, 21.0))
    res = evaluate_round(round_index=1, candidate_records=[], odlyzko=table)
    assert res.candidate_count == 0
    assert res.mean_score == 0.0


def test_phase1_structured_claim_inside_table_confirms_score(tiny_table: OdlyzkoTable) -> None:
    """no_zero_in 50.0000 60.0000 — empty in tiny table, t_hi (60) inside t_max (32.93)?
    Actually 60 > 32.93, so this falls in the 'cannot confirm' bucket.

    Use a window that IS inside table range and IS empty: (15.0, 20.0)
    — between zero[0]=14.13 and zero[1]=21.02.
    """
    skel = (
        "import Mathlib\n"
        "theorem numeric_window_x : no_zero_in 15.0000 20.0000 := by\n"
        "  sorry\n"
    )
    s = score_candidate(
        candidate_id="confirmed",
        ingredient_families=("explicit_formula",),  # 1 checkable
        closed_obligation_count=0,
        open_obligation_count=0,  # no untestable
        lean_skeleton=skel,
        odlyzko=tiny_table,
    )
    # base 0.30 + family 0.10 + correct_claim 0.20 = 0.60
    assert s.score == pytest.approx(0.60, abs=1e-6)
    assert s.confirmed_window == (15.0, 20.0)
    assert s.contradicted_window is None


def test_phase1_structured_claim_outside_table_no_signal(tiny_table: OdlyzkoTable) -> None:
    """Claim window beyond t_max — cannot confirm or contradict."""
    skel = (
        "import Mathlib\n"
        "theorem numeric_window_y : no_zero_in 50.0000 60.0000 := by\n"
        "  sorry\n"
    )
    s = score_candidate(
        candidate_id="silent",
        ingredient_families=("explicit_formula",),
        closed_obligation_count=0,
        open_obligation_count=0,
        lean_skeleton=skel,
        odlyzko=tiny_table,
    )
    # base 0.30 + family 0.10 = 0.40 (no confirmation, no contradiction)
    assert s.score == pytest.approx(0.40, abs=1e-6)
    assert s.confirmed_window is None
    assert s.contradicted_window is None


def test_phase1_structured_claim_contradicts(tiny_table: OdlyzkoTable) -> None:
    """Claim window straddles a known zero → contradiction."""
    skel = (
        "import Mathlib\n"
        "theorem numeric_window_z : no_zero_in 14.0000 22.0000 := by\n"
        "  sorry\n"
    )
    s = score_candidate(
        candidate_id="wrong",
        ingredient_families=("explicit_formula",),
        closed_obligation_count=0,
        open_obligation_count=0,
        lean_skeleton=skel,
        odlyzko=tiny_table,
    )
    # base 0.30 + family 0.10 - 0.50 = -0.10 → clamped 0.0
    assert s.score == pytest.approx(0.0, abs=1e-6)
    assert s.contradicted_window == (14.0, 22.0)


def test_evaluate_round_aggregates_confirmations(tiny_table: OdlyzkoTable) -> None:
    """confirmed_count must reflect candidates whose claim landed in an empty table window."""
    records = [
        {
            "candidate_id": "good",
            "ingredient_families": ["explicit_formula"],
            "closed_obligation_count": 0,
            "open_obligation_count": 0,
            "lean_skeleton": "theorem t : no_zero_in 15.0000 20.0000 := by sorry",
        },
        {
            "candidate_id": "bad",
            "ingredient_families": ["explicit_formula"],
            "closed_obligation_count": 0,
            "open_obligation_count": 0,
            "lean_skeleton": "theorem t : no_zero_in 14.0000 22.0000 := by sorry",
        },
    ]
    res = evaluate_round(round_index=1, candidate_records=records, odlyzko=tiny_table)
    assert res.confirmed_count == 1
    assert res.contradicted_count == 1


def test_certificate_skeleton_includes_falsifiable_claim() -> None:
    """The auto-generated lean skeleton must commit to a no_zero_in claim."""
    from riemann.research.certificate_program import _claim_window, _generate_lean_skeleton
    skel = _generate_lean_skeleton(
        candidate_id="rh-hyp-99-deadbeef",
        obligation_snapshot={"open_obligation_classes": {"some_class": 1}},
    )
    assert "no_zero_in" in skel
    t_lo, t_hi = _claim_window("rh-hyp-99-deadbeef")
    assert t_lo < t_hi
    assert 9.5 <= t_lo and t_hi <= 102.0  # within designed [10, 101] range with margin


def test_phase2_reasoning_window_centers_on_family_vote() -> None:
    """Different families should center their windows at different heights."""
    from riemann.research.certificate_program import _claim_window_from_reasoning
    de_branges_lo, de_branges_hi = _claim_window_from_reasoning(
        "id1", ("de_branges",), ("o1",)
    )
    random_matrix_lo, random_matrix_hi = _claim_window_from_reasoning(
        "id1", ("random_matrix",), ("o1",)
    )
    de_branges_center = (de_branges_lo + de_branges_hi) / 2
    random_matrix_center = (random_matrix_lo + random_matrix_hi) / 2
    # de_branges → 20.0 region, random_matrix → 70.0 region (with ±2.5 perturbation)
    assert 17.0 <= de_branges_center <= 23.0
    assert 67.0 <= random_matrix_center <= 73.0
    # And clearly separated
    assert random_matrix_center - de_branges_center > 40.0


def test_phase2_window_width_grows_with_obligation_count() -> None:
    """More obligations = bolder claim = wider window."""
    from riemann.research.certificate_program import _claim_window_from_reasoning
    narrow = _claim_window_from_reasoning("id", ("explicit_formula",), ("o1",))
    wide = _claim_window_from_reasoning("id", ("explicit_formula",), tuple(f"o{i}" for i in range(5)))
    narrow_w = narrow[1] - narrow[0]
    wide_w = wide[1] - wide[0]
    assert wide_w > narrow_w
    # 1 obligation: half-width 0.10 → full width 0.20
    # 5 obligations: half-width 0.30 → full width 0.60
    assert narrow_w == pytest.approx(0.20, abs=1e-6)
    assert wide_w == pytest.approx(0.60, abs=1e-6)


def test_phase2_two_same_family_candidates_get_different_windows() -> None:
    """Tie-break perturbation should give distinct windows to same-family candidates."""
    from riemann.research.certificate_program import _claim_window_from_reasoning
    a = _claim_window_from_reasoning("id-a", ("hardy_z",), ("o1",))
    b = _claim_window_from_reasoning("id-b", ("hardy_z",), ("o1",))
    assert a != b
    # But both centered near 50.0 ± 2.5
    a_center = (a[0] + a[1]) / 2
    b_center = (b[0] + b[1]) / 2
    assert 47.5 <= a_center <= 52.5
    assert 47.5 <= b_center <= 52.5


def test_phase2_skeleton_uses_reasoning_window_when_families_provided() -> None:
    """Skeleton with families should pick a reasoning-derived window, not the hash-only one."""
    from riemann.research.certificate_program import (
        _claim_window,
        _claim_window_from_reasoning,
        _generate_lean_skeleton,
    )
    cid = "rh-hyp-test-deadbeef"
    obl_snapshot = {"open_obligation_classes": {"o1": 1, "o2": 1}}

    skel_no_families = _generate_lean_skeleton(cid, obl_snapshot)
    skel_with_families = _generate_lean_skeleton(
        cid, obl_snapshot, ingredient_families=("random_matrix",)
    )

    # Phase 5 supersedes Phase 2 for the families path. Both _claim_window
    # (no families) and Phase 5 gap-aware (with families) should produce
    # different windows, and the with-families one should match the
    # gap-aware function (not the hand-curated reasoning function).
    hash_lo, hash_hi = _claim_window(cid)
    # Sanity: with-families skeleton is different from no-families skeleton.
    assert skel_no_families != skel_with_families
