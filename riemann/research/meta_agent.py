"""Gödel meta-loop agent — generates meta-theorems about the orchestrator itself (Phase 6)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class MetaTheoremStatement:
    theorem_id: str
    kind: Literal["residue", "obstruction", "reformulation"]
    natural_language: str
    lean_skeleton: str
    predicate_obstruction_class: str
    historical_count: int
    applies: bool


# ---------------------------------------------------------------------------
# Lean skeleton templates
# ---------------------------------------------------------------------------

_MT_ALPHA_SKELETON = """\
-- {theorem_id}: Lean-Monotone Residue (MT-α)
-- Campaign {campaign_id}: lean_delta={lean_delta_count}, persistent_obstructions={persistent_obstruction_count}
theorem mt_alpha_{safe_id} :
    ∀ (campaign : RHCampaign),
    campaign.lean_delta_count = 0 →
    campaign.persistent_obstruction_count ≥ 1 →
    ¬campaign.is_productive := by
  sorry
"""

_MT_BETA_SKELETON = """\
-- {theorem_id}: Obstruction Closure (MT-β)
-- Obstruction class '{obstruction_class}' survived {historical_count} campaigns (threshold {threshold}).
theorem mt_beta_{safe_id} :
    ∀ (campaign : RHCampaign) (proposer : CandidateFamily),
    campaign.obstruction_class = "{obstruction_class}" →
    campaign.historical_count ≥ {historical_count} →
    ¬proposer.promoted_without_lean_exclusion_certificate := by
  sorry
"""

_MT_GAMMA_SKELETON = """\
-- {theorem_id}: Reformulation Bound (MT-γ)
-- Canonical signature '{canonical_signature}' has been seen before — reformulation rejected.
theorem mt_gamma_{safe_id} :
    ∀ (r : Reformulation),
    r.canonical_signature = "{canonical_signature}" →
    r.reduces_to_tracked_reformulation = True →
    r.is_rejected := by
  sorry
"""


def _safe_id(raw: str) -> str:
    """Convert an arbitrary string into a valid Lean identifier fragment."""
    return "".join(c if c.isalnum() or c == "_" else "_" for c in raw)


class MetaAgent:
    """Emits MT-α, MT-β, and MT-γ meta-theorems about the campaign orchestrator."""

    name = "meta"

    def __init__(self, lean_rh_root: Path) -> None:
        self.lean_dir = lean_rh_root / "MetaTheorems"
        self.lean_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Individual theorem generators
    # ------------------------------------------------------------------

    def _mt_alpha(
        self,
        campaign_id: str,
        lean_delta_count: int,
        persistent_obstruction_count: int,
    ) -> MetaTheoremStatement:
        applies = lean_delta_count == 0 and persistent_obstruction_count >= 1
        theorem_id = "MT-α-001"
        skeleton = _MT_ALPHA_SKELETON.format(
            theorem_id=theorem_id,
            campaign_id=campaign_id,
            lean_delta_count=lean_delta_count,
            persistent_obstruction_count=persistent_obstruction_count,
            safe_id=_safe_id(campaign_id),
        )
        natural_language = (
            f"Any campaign with empty Lean delta (got {lean_delta_count}) "
            f"and at least one persistent obstruction (got {persistent_obstruction_count}) "
            "is unproductive."
        )
        return MetaTheoremStatement(
            theorem_id=theorem_id,
            kind="residue",
            natural_language=natural_language,
            lean_skeleton=skeleton,
            predicate_obstruction_class="",
            historical_count=persistent_obstruction_count,
            applies=applies,
        )

    def _mt_beta(
        self,
        obstruction_class: str,
        historical_count: int,
        threshold: int = 3,
    ) -> MetaTheoremStatement:
        applies = historical_count >= threshold
        seq = historical_count
        theorem_id = f"MT-β-{_safe_id(obstruction_class)[:24]}-{seq:03d}"
        skeleton = _MT_BETA_SKELETON.format(
            theorem_id=theorem_id,
            obstruction_class=obstruction_class,
            historical_count=historical_count,
            threshold=threshold,
            safe_id=_safe_id(obstruction_class),
        )
        natural_language = (
            f"Obstruction class '{obstruction_class}' survived {historical_count} campaigns "
            f"(threshold {threshold}): no proposer in the associated family is promoted "
            "without a Lean exclusion certificate against this obstruction."
        )
        return MetaTheoremStatement(
            theorem_id=theorem_id,
            kind="obstruction",
            natural_language=natural_language,
            lean_skeleton=skeleton,
            predicate_obstruction_class=obstruction_class,
            historical_count=historical_count,
            applies=applies,
        )

    def _mt_gamma(
        self,
        canonical_signature: str,
        seen_signatures: set[str],
    ) -> MetaTheoremStatement:
        applies = canonical_signature in seen_signatures
        theorem_id = f"MT-γ-{_safe_id(canonical_signature)[:32]}"
        skeleton = _MT_GAMMA_SKELETON.format(
            theorem_id=theorem_id,
            canonical_signature=canonical_signature,
            safe_id=_safe_id(canonical_signature),
        )
        natural_language = (
            f"Reformulation with canonical signature '{canonical_signature}' "
            "reduces to a previously-tracked reformulation under the canonical "
            "operator signature and is therefore rejected."
        )
        return MetaTheoremStatement(
            theorem_id=theorem_id,
            kind="reformulation",
            natural_language=natural_language,
            lean_skeleton=skeleton,
            predicate_obstruction_class="",
            historical_count=int(applies),
            applies=applies,
        )

    # ------------------------------------------------------------------
    # Orchestration entry point
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        campaign_id: str,
        lean_delta_count: int,
        persistent_obstruction_count: int,
        failure_counts: dict[str, int],
        canonical_signatures: tuple[str, ...] = (),
    ) -> tuple[MetaTheoremStatement, ...]:
        """Emit all applicable meta-theorems for the current campaign state."""
        emitted: list[MetaTheoremStatement] = []

        # MT-α — always emitted (descriptive even when not triggered)
        emitted.append(
            self._mt_alpha(campaign_id, lean_delta_count, persistent_obstruction_count)
        )

        # MT-β — one per failure_count entry that meets the threshold
        for obstruction_class, count in failure_counts.items():
            emitted.append(self._mt_beta(obstruction_class, count))

        # MT-γ — track which signatures have been seen and emit for duplicates
        seen: set[str] = set()
        for sig in canonical_signatures:
            emitted.append(self._mt_gamma(sig, seen))
            seen.add(sig)

        return tuple(emitted)

    # ------------------------------------------------------------------
    # File writer
    # ------------------------------------------------------------------

    def write_lean_files(
        self, theorems: tuple[MetaTheoremStatement, ...]
    ) -> list[Path]:
        """Write each applicable theorem's Lean skeleton to lean_dir."""
        written: list[Path] = []
        for theorem in theorems:
            if not theorem.applies:
                continue
            dest = self.lean_dir / f"{theorem.theorem_id}.lean"
            dest.write_text(theorem.lean_skeleton, encoding="utf-8")
            written.append(dest)
        return written
