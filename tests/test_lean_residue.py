"""Tests for lean_residue.py — LeanResidueLedger (Phase 1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from riemann.research.lean_residue import (
    LeanResidueLedger,
    ResidueSnapshot,
    ResidueDelta,
    scan_lean_rh_dir,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEAN_RH_DIR = PROJECT_ROOT / "lean" / "RH"


# ---------------------------------------------------------------------------
# scan_lean_rh_dir — real directory
# ---------------------------------------------------------------------------


def test_scan_lean_rh_dir_returns_snapshot() -> None:
    snapshot = scan_lean_rh_dir(LEAN_RH_DIR)
    assert isinstance(snapshot, ResidueSnapshot)


def test_snapshot_file_count_at_least_one() -> None:
    snapshot = scan_lean_rh_dir(LEAN_RH_DIR)
    assert snapshot.file_count >= 1, (
        f"Expected at least one .lean file under {LEAN_RH_DIR}; "
        f"got {snapshot.file_count}"
    )


def test_snapshot_decls_non_empty() -> None:
    snapshot = scan_lean_rh_dir(LEAN_RH_DIR)
    assert len(snapshot.decls) > 0, "Expected at least one declaration in lean/RH/"


def test_snapshot_timestamp_iso_format() -> None:
    snapshot = scan_lean_rh_dir(LEAN_RH_DIR)
    # Should be an ISO 8601 string (contains 'T' separator and timezone info).
    assert "T" in snapshot.timestamp_iso


def test_snapshot_sorry_count_non_negative() -> None:
    snapshot = scan_lean_rh_dir(LEAN_RH_DIR)
    assert snapshot.sorry_count >= 0


# ---------------------------------------------------------------------------
# LeanResidueLedger.diff — monotone advance detection
# ---------------------------------------------------------------------------


def test_diff_monotone_advance_when_decls_added() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    before = ResidueSnapshot(
        decls=("decl_a",),
        file_count=1,
        sorry_count=0,
        timestamp_iso="2026-01-01T00:00:00+00:00",
    )
    after = ResidueSnapshot(
        decls=("decl_a", "decl_b"),
        file_count=1,
        sorry_count=0,
        timestamp_iso="2026-01-01T01:00:00+00:00",
    )
    delta = ledger.diff(before, after)
    assert delta.is_monotone_advance is True
    assert "decl_b" in delta.added
    assert delta.removed == ()


def test_diff_not_monotone_when_decls_removed() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    before = ResidueSnapshot(
        decls=("decl_a", "decl_b"),
        file_count=1,
        sorry_count=0,
        timestamp_iso="2026-01-01T00:00:00+00:00",
    )
    after = ResidueSnapshot(
        decls=("decl_a",),
        file_count=1,
        sorry_count=0,
        timestamp_iso="2026-01-01T01:00:00+00:00",
    )
    delta = ledger.diff(before, after)
    assert delta.is_monotone_advance is False
    assert "decl_b" in delta.removed


def test_diff_zero_delta_not_monotone_advance() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    snap = ResidueSnapshot(
        decls=("decl_a",),
        file_count=1,
        sorry_count=0,
        timestamp_iso="2026-01-01T00:00:00+00:00",
    )
    delta = ledger.diff(snap, snap)
    assert delta.is_monotone_advance is False
    assert delta.added == ()
    assert delta.removed == ()


# ---------------------------------------------------------------------------
# LeanResidueLedger.gate — pass/fail logic
# ---------------------------------------------------------------------------


def test_gate_passes_when_delta_positive() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    delta = ResidueDelta(
        added=("new_decl",),
        removed=(),
        before_count=1,
        after_count=2,
        sorry_delta=0,
        is_monotone_advance=True,
    )
    passed, msg = ledger.gate(delta, persistent_obstruction_count=5)
    assert passed is True
    assert "PASS" in msg


def test_gate_fails_when_delta_zero_and_obstruction_present() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    delta = ResidueDelta(
        added=(),
        removed=(),
        before_count=3,
        after_count=3,
        sorry_delta=0,
        is_monotone_advance=False,
    )
    passed, msg = ledger.gate(delta, persistent_obstruction_count=2)
    assert passed is False
    assert "FAIL" in msg


def test_gate_passes_when_obstruction_count_zero_even_with_no_delta() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    delta = ResidueDelta(
        added=(),
        removed=(),
        before_count=2,
        after_count=2,
        sorry_delta=0,
        is_monotone_advance=False,
    )
    passed, msg = ledger.gate(delta, persistent_obstruction_count=0)
    assert passed is True
    assert "PASS" in msg


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_to_dict_is_json_serializable() -> None:
    ledger = LeanResidueLedger(LEAN_RH_DIR)
    delta = ResidueDelta(
        added=("d1",),
        removed=(),
        before_count=0,
        after_count=1,
        sorry_delta=0,
        is_monotone_advance=True,
    )
    data = ledger.to_dict(delta)
    # Must be JSON-serializable (no exception).
    serialized = json.dumps(data)
    parsed = json.loads(serialized)
    assert parsed["is_monotone_advance"] is True
    assert parsed["added"] == ["d1"]


# ---------------------------------------------------------------------------
# Edge case: empty directory
# ---------------------------------------------------------------------------


def test_snapshot_empty_directory(tmp_path: Path) -> None:
    ledger = LeanResidueLedger(tmp_path)
    snapshot = ledger.snapshot()
    assert isinstance(snapshot, ResidueSnapshot)
    assert snapshot.file_count == 0
    assert snapshot.decls == ()
    assert snapshot.sorry_count == 0
