"""Tests for the Phase 3 strict Lean bridge backend."""
from __future__ import annotations

from riemann.research.lean_bridge import verify


def test_strict_passes_real_proof() -> None:
    src = "theorem p : True := trivial\n"
    r = verify(src, backend="strict")
    assert r.passed
    assert r.backend == "strict"
    assert r.sorry_count == 0


def test_strict_rejects_single_sorry() -> None:
    src = "theorem p : True := by sorry\n"
    r = verify(src, backend="strict")
    assert not r.passed
    assert r.backend == "strict"
    assert r.sorry_count == 1
    assert any("sorry" in e for e in r.errors)


def test_strict_rejects_multiple_sorries() -> None:
    src = (
        "theorem p : True := by sorry\n"
        "theorem q : True := by sorry\n"
        "theorem r : True := by trivial\n"
    )
    r = verify(src, backend="strict")
    assert not r.passed
    assert r.sorry_count == 2


def test_strict_rejects_no_decl_source() -> None:
    src = "import Mathlib\n"
    r = verify(src, backend="strict")
    assert not r.passed


def test_mock_still_accepts_sorry() -> None:
    """Mock backend (existing behavior) accepts sorry — strict is the new strict path."""
    src = "theorem p : True := by sorry\n"
    r = verify(src, backend="mock")
    assert r.passed  # mock accepts well-formed sorry source
    assert r.sorry_count == 1
