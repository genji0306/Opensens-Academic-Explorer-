"""Lean monotone-residue ledger for the RH Hyperloop orbit-breaker (Phase 1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import lean_bridge


@dataclass(frozen=True)
class ResidueSnapshot:
    """Point-in-time snapshot of all .lean declarations in lean/RH/."""

    decls: tuple[str, ...]
    file_count: int
    sorry_count: int
    timestamp_iso: str


@dataclass(frozen=True)
class ResidueDelta:
    """Difference between two ResidueSnapshots."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    before_count: int
    after_count: int
    sorry_delta: int
    is_monotone_advance: bool


class LeanResidueLedger:
    """Tracks .lean declaration monotone growth across campaign rounds."""

    def __init__(self, lean_rh_root: Path) -> None:
        self._root = lean_rh_root

    def snapshot(self) -> ResidueSnapshot:
        lean_files = sorted(self._root.rglob("*.lean")) if self._root.exists() else []
        all_decls: list[str] = []
        total_sorry = 0
        for lean_file in lean_files:
            result = lean_bridge.verify_file(lean_file, backend="mock")
            all_decls.extend(result.decls)
            total_sorry += result.sorry_count
        unique_decls = tuple(sorted(set(all_decls)))
        return ResidueSnapshot(
            decls=unique_decls,
            file_count=len(lean_files),
            sorry_count=total_sorry,
            timestamp_iso=datetime.now(tz=timezone.utc).isoformat(),
        )

    def diff(self, before: ResidueSnapshot, after: ResidueSnapshot) -> ResidueDelta:
        before_set = set(before.decls)
        after_set = set(after.decls)
        added = tuple(sorted(after_set - before_set))
        removed = tuple(sorted(before_set - after_set))
        return ResidueDelta(
            added=added,
            removed=removed,
            before_count=len(before.decls),
            after_count=len(after.decls),
            sorry_delta=after.sorry_count - before.sorry_count,
            is_monotone_advance=bool(added) and not bool(removed),
        )

    def gate(
        self,
        delta: ResidueDelta,
        *,
        persistent_obstruction_count: int,
    ) -> tuple[bool, str]:
        if delta.is_monotone_advance:
            return (
                True,
                f"RESIDUE_GATE_PASS: {len(delta.added)} new declaration(s) added, none removed",
            )
        if persistent_obstruction_count == 0:
            return (
                True,
                "RESIDUE_GATE_PASS: no persistent obstructions — zero-delta round tolerated",
            )
        return (
            False,
            (
                f"RESIDUE_GATE_FAIL: no new Lean declarations this round "
                f"({persistent_obstruction_count} persistent obstruction class(es) open)"
            ),
        )

    def to_dict(self, delta: ResidueDelta) -> dict[str, Any]:
        return {
            "added": list(delta.added),
            "removed": list(delta.removed),
            "before_count": delta.before_count,
            "after_count": delta.after_count,
            "sorry_delta": delta.sorry_delta,
            "is_monotone_advance": delta.is_monotone_advance,
        }


def scan_lean_rh_dir(lean_rh_root: Path) -> ResidueSnapshot:
    """Convenience wrapper: snapshot the lean/RH/ directory."""
    return LeanResidueLedger(lean_rh_root).snapshot()
