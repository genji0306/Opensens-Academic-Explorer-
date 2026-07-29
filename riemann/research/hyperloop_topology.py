"""Hyperloop topology: Klein ⊗ Lean ⊗ Gödel — tri-arm feedback with monotone residue (Phase 7)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Signals and Decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HyperloopSignals:
    """Input signals for a single hyperloop evaluation round."""

    klein_score: float
    """[0, 1] — soft tiebreaker from the Klein topology observer."""

    lean_residue_delta: int
    """Number of new Lean declarations added this round (Phase 1 gate)."""

    meta_closure_count: int
    """Number of meta-theorems that fired (applies=True) this round (Phase 6 gate)."""

    ensemble_rejection_rate: float
    """[0, 1] — fraction of proposals rejected by the Phase 3 ensemble."""

    external_score: float
    """[0, 1] — score from Phase 4 external evaluator; 0.0 if unavailable."""


@dataclass(frozen=True)
class HyperloopDecision:
    """Output decision from a single hyperloop evaluation round."""

    proceed: bool
    dominant_axis: str
    """One of 'klein', 'lean', 'meta', or 'external'."""

    hard_gate_passed: bool
    reason: str
    recommended_action: str
    """One of 'continue', 'replan', 'escalate', 'halt'."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proceed": self.proceed,
            "dominant_axis": self.dominant_axis,
            "hard_gate_passed": self.hard_gate_passed,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
        }


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

_VALID_AXES = frozenset({"klein", "lean", "meta", "external"})
_VALID_ACTIONS = frozenset({"continue", "replan", "escalate", "halt"})


class HyperloopTopology:
    """Three-axis feedback controller replacing the single-axis Klein loop.

    Axis 1: Klein score (soft tiebreaker).
    Axis 2: Lean residue delta (hard gate — Phase 1).
    Axis 3: Gödel meta-closure signal (hard gate — Phase 6).
    """

    name = "hyperloop"

    def __init__(
        self,
        *,
        klein_weight: float = 0.20,
        lean_gate_required: bool = True,
        meta_gate_threshold: int = 2,
    ) -> None:
        self._klein_weight = klein_weight
        self._lean_gate_required = lean_gate_required
        self._meta_gate_threshold = meta_gate_threshold

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        signals: HyperloopSignals,
        *,
        obstruction_count: int,
    ) -> HyperloopDecision:
        """Apply tri-arm gate logic and produce a HyperloopDecision.

        Priority order:
          1. Hard gate 2 (meta): meta_closure_count >= threshold → escalate.
          2. Hard gate 1 (lean): lean_delta==0 AND obstruction_count>=1 → halt.
          3. External falsification: external_score > 0 AND external_score < klein_score - 0.10 → replan.
          4. Klein tiebreaker: klein_score >= 0.5 → continue, else → replan.
        """
        # --- Hard gate 2: Gödel meta-closure ---
        if signals.meta_closure_count >= self._meta_gate_threshold:
            reason = (
                f"META_GATE_TRIGGER: {signals.meta_closure_count} meta-theorem(s) fired "
                f"(threshold {self._meta_gate_threshold}) — campaign structure is problematic"
            )
            return HyperloopDecision(
                proceed=False,
                dominant_axis="meta",
                hard_gate_passed=False,
                reason=reason,
                recommended_action="escalate",
            )

        # --- Hard gate 1: Lean residue ---
        lean_gate_failed = (
            self._lean_gate_required
            and signals.lean_residue_delta == 0
            and obstruction_count >= 1
        )
        if lean_gate_failed:
            reason = (
                f"LEAN_GATE_FAIL: no new Lean declarations this round "
                f"({obstruction_count} persistent obstruction class(es) open)"
            )
            return HyperloopDecision(
                proceed=False,
                dominant_axis="lean",
                hard_gate_passed=False,
                reason=reason,
                recommended_action="halt",
            )

        # Hard gates passed — determine dominant axis for soft decisions.
        hard_gate_passed = True

        # --- External falsification ---
        if signals.external_score > 0.0 and signals.external_score < (signals.klein_score - 0.10):
            reason = (
                f"EXTERNAL_FALSIFY: external_score={signals.external_score:.3f} < "
                f"klein_score={signals.klein_score:.3f} - 0.10 — external evidence falsifies "
                "internal perception"
            )
            return HyperloopDecision(
                proceed=True,
                dominant_axis="external",
                hard_gate_passed=hard_gate_passed,
                reason=reason,
                recommended_action="replan",
            )

        # --- Klein tiebreaker ---
        if signals.klein_score >= 0.5:
            reason = (
                f"KLEIN_CONTINUE: klein_score={signals.klein_score:.3f} >= 0.50 "
                "and all hard gates passed"
            )
            return HyperloopDecision(
                proceed=True,
                dominant_axis="klein",
                hard_gate_passed=hard_gate_passed,
                reason=reason,
                recommended_action="continue",
            )

        reason = (
            f"KLEIN_REPLAN: klein_score={signals.klein_score:.3f} < 0.50 "
            "— soft signal below threshold, replan round"
        )
        return HyperloopDecision(
            proceed=True,
            dominant_axis="klein",
            hard_gate_passed=hard_gate_passed,
            reason=reason,
            recommended_action="replan",
        )

    def to_dict(self, decision: HyperloopDecision) -> dict[str, Any]:
        return decision.to_dict()


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def run_hyperloop_round(
    signals: HyperloopSignals,
    *,
    obstruction_count: int,
    topology: HyperloopTopology | None = None,
) -> HyperloopDecision:
    """Evaluate a single hyperloop round using default (or provided) topology."""
    topo = topology if topology is not None else HyperloopTopology()
    return topo.evaluate(signals, obstruction_count=obstruction_count)


# ---------------------------------------------------------------------------
# Benchmark record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HyperloopBenchmark:
    """Structured record of a multi-round hyperloop campaign benchmark."""

    campaign_id: str
    topology_mode: str
    """One of 'baseline', 'klein', or 'hyperloop'."""

    rounds: tuple[dict[str, Any], ...]
    lean_residue_advances: int
    meta_closure_total: int
    hard_gate_failures: int
    final_decision: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "topology_mode": self.topology_mode,
            "rounds": list(self.rounds),
            "lean_residue_advances": self.lean_residue_advances,
            "meta_closure_total": self.meta_closure_total,
            "hard_gate_failures": self.hard_gate_failures,
            "final_decision": self.final_decision,
        }
