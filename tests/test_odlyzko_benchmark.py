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
