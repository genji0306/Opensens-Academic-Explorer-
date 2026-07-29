"""Tests for Phase 5 gap-aware claim windows."""
from __future__ import annotations

import pytest

from riemann.research.certificate_program import (
    _claim_window_from_gaps,
    _generate_lean_skeleton,
    _load_odlyzko_gaps,
)


def test_odlyzko_gaps_loaded() -> None:
    gaps = _load_odlyzko_gaps()
    assert len(gaps) > 100
    # First gap is between zero[0]=14.1347 and zero[1]=21.0220
    assert gaps[0][0] == pytest.approx(14.1347, abs=1e-3)
    assert gaps[0][1] == pytest.approx(21.0220, abs=1e-3)


def test_window_is_centered_on_a_real_gap() -> None:
    """The window center must be the midpoint of an actual Odlyzko gap."""
    gaps = _load_odlyzko_gaps()
    if not gaps:
        pytest.skip("Odlyzko data not available")
    t_lo, t_hi = _claim_window_from_gaps(
        "test-cand-1", ("explicit_formula",), ("o1",)
    )
    center = (t_lo + t_hi) / 2.0
    # Center must match some gap's midpoint exactly.
    midpoints = [(g[0] + g[1]) / 2.0 for g in gaps]
    assert any(abs(center - m) < 1e-6 for m in midpoints)


def test_different_families_pick_different_gap_regions() -> None:
    """explicit_formula targets low-T gaps; random_matrix targets high-T."""
    cid = "stable-cand-1"
    obs = ("o1",)
    ef_lo, ef_hi = _claim_window_from_gaps(cid, ("explicit_formula",), obs)
    rm_lo, rm_hi = _claim_window_from_gaps(cid, ("random_matrix",), obs)
    ef_center = (ef_lo + ef_hi) / 2.0
    rm_center = (rm_lo + rm_hi) / 2.0
    assert rm_center > ef_center


def test_more_obligations_widens_the_window() -> None:
    """Speculative candidates (many obligations) get wider claims that may straddle the gap."""
    cid = "test-cand"
    fam = ("explicit_formula",)
    narrow = _claim_window_from_gaps(cid, fam, ("o1",))
    wide = _claim_window_from_gaps(cid, fam, tuple(f"o{i}" for i in range(8)))
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_same_candidate_id_same_family_deterministic() -> None:
    """Reproducibility: same inputs → same window."""
    a = _claim_window_from_gaps("cand-x", ("hardy_z",), ("o1", "o2"))
    b = _claim_window_from_gaps("cand-x", ("hardy_z",), ("o1", "o2"))
    assert a == b


def test_lean_skeleton_uses_phase5_window_when_families_provided() -> None:
    """Generated skeleton's no_zero_in claim must use the gap-aware window."""
    cid = "rh-hyp-99-deadbeef"
    obl_snapshot = {"open_obligation_classes": {"o1": 1, "o2": 1}}
    skel = _generate_lean_skeleton(
        cid, obl_snapshot, ingredient_families=("random_matrix",)
    )
    expected_lo, expected_hi = _claim_window_from_gaps(
        cid, ("random_matrix",), ("o1", "o2")
    )
    assert f"{expected_lo:.4f}" in skel
    assert f"{expected_hi:.4f}" in skel
