"""Round-level verifier gate: reject rounds that produce no Lean residue (Phase 3).

This module exposes the :class:`GateDecision` dataclass and the
:func:`apply_verifier_gate` function used by the orchestrator to block
campaign rounds that advance no Lean proof content.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GateDecision:
    """Decision produced by :func:`apply_verifier_gate` for one campaign round."""

    round_index: int
    passed: bool
    reason: str
    lean_delta_count: int  # new Lean declarations added this round
    ensemble_rejection_rate: float  # fraction of candidates rejected by ensemble

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "passed": self.passed,
            "reason": self.reason,
            "lean_delta_count": self.lean_delta_count,
            "ensemble_rejection_rate": self.ensemble_rejection_rate,
        }


def apply_verifier_gate(
    round_index: int,
    *,
    lean_delta_decls: int,
    ensemble_results: list[dict[str, Any]],
    obstruction_count: int,
) -> GateDecision:
    """Decide whether a round passes the Lean-residue gate.

    Gate logic:
    - ``passed = True`` when ``lean_delta_decls > 0`` OR ``obstruction_count == 0``.
    - If both ``lean_delta_decls == 0`` and ``obstruction_count > 0``:
      ``passed = False``, ``reason = "RESIDUE_GATE_FAIL"``.

    ``ensemble_rejection_rate`` is computed from the ``accepted`` field of
    each dict in ``ensemble_results``.
    """
    if lean_delta_decls > 0 or obstruction_count == 0:
        passed = True
        reason = "ok"
    else:
        passed = False
        reason = "RESIDUE_GATE_FAIL"

    if ensemble_results:
        rejected = sum(1 for r in ensemble_results if not r.get("accepted", True))
        rejection_rate = rejected / len(ensemble_results)
    else:
        rejection_rate = 0.0

    return GateDecision(
        round_index=round_index,
        passed=passed,
        reason=reason,
        lean_delta_count=lean_delta_decls,
        ensemble_rejection_rate=rejection_rate,
    )


# ---------------------------------------------------------------------------
# Proposal ensemble (Phase 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnsembleResult:
    """Aggregated result of verifying a batch of Lean proposal sources."""

    accepted: tuple[str, ...]
    rejected: tuple[str, ...]
    consensus: int
    total: int

    def rejection_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.rejected) / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": list(self.accepted),
            "rejected": list(self.rejected),
            "consensus": self.consensus,
            "total": self.total,
            "rejection_rate": self.rejection_rate(),
        }


class ProposalEnsemble:
    """Verifies a collection of Lean source strings and tracks acceptance.

    Uses the mock lean_bridge backend (no AXLE API key required).
    """

    def __init__(self) -> None:
        self._results: list[dict[str, Any]] = []

    def run(self, sources: list[str]) -> EnsembleResult:
        """Verify each source string and build an EnsembleResult."""
        from . import lean_bridge

        accepted: list[str] = []
        rejected: list[str] = []
        results: list[dict[str, Any]] = []

        for source in sources:
            result = lean_bridge.verify(source, backend="mock")
            if result.passed and result.decls:
                accepted.append(source)
                results.append({"accepted": True})
            else:
                rejected.append(source)
                results.append({"accepted": False})

        self._results = results
        return EnsembleResult(
            accepted=tuple(accepted),
            rejected=tuple(rejected),
            consensus=len(accepted),
            total=len(sources),
        )

    def rejection_rate(self) -> float:
        total = len(self._results)
        if total == 0:
            return 0.0
        return sum(1 for r in self._results if not r.get("accepted", True)) / total
