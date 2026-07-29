"""Tests for meta_agent.py (Phase 6)."""
from __future__ import annotations

from pathlib import Path

import pytest

from riemann.research.meta_agent import MetaAgent, MetaTheoremStatement


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEAN_RH_DIR = PROJECT_ROOT / "lean" / "RH"


# ---------------------------------------------------------------------------
# MT-α: Lean-Monotone Residue
# ---------------------------------------------------------------------------


def test_mt_alpha_applies_when_delta_zero_and_obstruction_present(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test-campaign",
        lean_delta_count=0,
        persistent_obstruction_count=3,
        failure_counts={},
    )
    # MT-α is always emitted; it applies when delta=0 AND obstruction>=1.
    mt_alpha = theorems[0]
    assert mt_alpha.theorem_id == "MT-α-001"
    assert mt_alpha.applies is True


def test_mt_alpha_does_not_apply_when_delta_positive(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test-campaign",
        lean_delta_count=1,
        persistent_obstruction_count=0,
        failure_counts={},
    )
    mt_alpha = theorems[0]
    assert mt_alpha.applies is False


def test_mt_alpha_does_not_apply_when_obstruction_zero(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test-campaign",
        lean_delta_count=0,
        persistent_obstruction_count=0,
        failure_counts={},
    )
    mt_alpha = theorems[0]
    assert mt_alpha.applies is False


# ---------------------------------------------------------------------------
# MT-β: Obstruction Closure
# ---------------------------------------------------------------------------


def test_mt_beta_fires_when_failure_count_meets_threshold(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=0,
        persistent_obstruction_count=0,
        failure_counts={"finite_window_only": 5},
    )
    mt_beta_list = [t for t in theorems if t.kind == "obstruction"]
    assert len(mt_beta_list) >= 1
    mt_beta = mt_beta_list[0]
    assert mt_beta.applies is True
    assert "finite_window_only" in mt_beta.predicate_obstruction_class


def test_mt_beta_does_not_apply_below_threshold(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=1,
        persistent_obstruction_count=0,
        failure_counts={"global_exclusion_gap": 2},
    )
    mt_beta_list = [t for t in theorems if t.kind == "obstruction"]
    assert len(mt_beta_list) == 1
    # count=2 < threshold=3 → does not apply.
    assert mt_beta_list[0].applies is False


# ---------------------------------------------------------------------------
# MT-γ: Reformulation Bound
# ---------------------------------------------------------------------------


def test_mt_gamma_fires_when_canonical_signature_appears_twice(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=1,
        persistent_obstruction_count=0,
        failure_counts={},
        canonical_signatures=("sig_abc", "sig_abc"),
    )
    mt_gamma_list = [t for t in theorems if t.kind == "reformulation"]
    # Second occurrence of "sig_abc" should fire applies=True.
    applies_list = [t for t in mt_gamma_list if t.applies]
    assert len(applies_list) >= 1


# ---------------------------------------------------------------------------
# write_lean_files
# ---------------------------------------------------------------------------


def test_write_lean_files_creates_files(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=0,
        persistent_obstruction_count=2,
        failure_counts={"finite_window_only": 4},
    )
    written = agent.write_lean_files(theorems)
    assert len(written) > 0
    for path in written:
        assert path.exists()
        assert path.suffix == ".lean"


def test_write_lean_files_does_not_write_non_applicable(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    # delta=1, obstruction=0 → MT-α does not apply; no failure_counts → no MT-β.
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=1,
        persistent_obstruction_count=0,
        failure_counts={},
    )
    written = agent.write_lean_files(theorems)
    # MT-α does not apply, so no files should be written.
    assert len(written) == 0


# ---------------------------------------------------------------------------
# MetaTheoremStatement structure
# ---------------------------------------------------------------------------


def test_meta_theorem_lean_skeleton_non_empty(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=0,
        persistent_obstruction_count=1,
        failure_counts={},
    )
    for theorem in theorems:
        assert isinstance(theorem.lean_skeleton, str)
        assert len(theorem.lean_skeleton) > 0


def test_meta_theorem_lean_skeleton_contains_sorry_or_trivial(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=0,
        persistent_obstruction_count=1,
        failure_counts={"some_class": 5},
    )
    for theorem in theorems:
        skeleton = theorem.lean_skeleton
        assert "sorry" in skeleton or "trivial" in skeleton, (
            f"Expected 'sorry' or 'trivial' in skeleton for {theorem.theorem_id}"
        )


def test_meta_theorem_id_starts_with_mt(tmp_path: Path) -> None:
    agent = MetaAgent(tmp_path)
    theorems = agent.run(
        campaign_id="test",
        lean_delta_count=0,
        persistent_obstruction_count=1,
        failure_counts={"obstruction_x": 3},
    )
    for theorem in theorems:
        assert theorem.theorem_id.startswith("MT-"), (
            f"Expected theorem_id to start with 'MT-', got: {theorem.theorem_id!r}"
        )
