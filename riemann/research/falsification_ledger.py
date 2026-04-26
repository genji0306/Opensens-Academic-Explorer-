"""Phase 4: cross-round falsification feedback for the hyperloop.

The Odlyzko external benchmark falsifies a fraction of auto-generated claim
windows per round. Without this module those falsifications evaporate —
Agent A re-generates the same family at the same height region next round
and gets contradicted again.

This ledger records every (family_signature, height_band) that has been
falsified in a campaign, then exposes a penalty function Agent A consults
during hypothesis ranking. The campaign LEARNS to avoid contradicting
combinations.

Honest scope:
    - It does not learn anything about why a claim was wrong, only that
      the family-mix at this height band failed empirical adjudication.
    - The height band is coarse (1.0 wide).
    - Penalty caps at 0.50 per family-mix.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

_HEIGHT_BAND_WIDTH = 1.0
_FALSIFICATION_PENALTY_PER_HIT = 0.10
_FALSIFICATION_PENALTY_CAP = 0.50


@dataclass(frozen=True)
class FalsifiedClaim:
    """Record of one falsified claim — for audit and penalty lookup."""
    round_index: int
    candidate_id: str
    family_signature: str
    contradicted_window: tuple[float, float]


@dataclass
class FalsificationLedger:
    """Tracks falsifications per (family_signature, height_band) across rounds.

    Mutable on purpose — the campaign loop appends each round and Agent A
    reads it for the next round.
    """
    falsifications: list[FalsifiedClaim] = field(default_factory=list)
    _index: dict[tuple[str, int], int] = field(default_factory=lambda: defaultdict(int))

    def family_signature(self, ingredient_families: Iterable[str]) -> str:
        return "+".join(sorted(set(ingredient_families)))

    def band_index(self, t: float) -> int:
        return int(t // _HEIGHT_BAND_WIDTH)

    def record(
        self,
        *,
        round_index: int,
        candidate_id: str,
        ingredient_families: Iterable[str],
        contradicted_window: tuple[float, float],
    ) -> None:
        sig = self.family_signature(ingredient_families)
        t_lo, t_hi = contradicted_window
        # Register at the window's center band only — one falsification = one
        # ledger increment, so penalty queries don't double-count when both
        # the recorded window and the query window straddle the same two bands.
        center_band = self.band_index((t_lo + t_hi) / 2.0)
        self._index[(sig, center_band)] += 1
        self.falsifications.append(
            FalsifiedClaim(
                round_index=round_index,
                candidate_id=candidate_id,
                family_signature=sig,
                contradicted_window=contradicted_window,
            )
        )

    def penalty_for(
        self,
        ingredient_families: Iterable[str],
        candidate_window: tuple[float, float] | None,
    ) -> float:
        """Penalty in [0, 0.50] for a candidate whose family+window matches
        previously-falsified combinations. Returns 0 if no hit."""
        if candidate_window is None:
            return 0.0
        sig = self.family_signature(ingredient_families)
        t_lo, t_hi = candidate_window
        bands = {self.band_index(t_lo), self.band_index(t_hi)}
        hits = sum(self._index.get((sig, b), 0) for b in bands)
        if hits == 0:
            return 0.0
        return min(_FALSIFICATION_PENALTY_CAP, _FALSIFICATION_PENALTY_PER_HIT * hits)

    def family_falsification_count(self) -> dict[str, int]:
        """Per-individual-family count (multi-family signatures contribute to all)."""
        counts: dict[str, int] = {}
        for c in self.falsifications:
            for fam in c.family_signature.split("+"):
                counts[fam] = counts.get(fam, 0) + 1
        return counts

    def summary(self) -> dict[str, object]:
        per_signature: dict[str, int] = defaultdict(int)
        per_band: dict[int, int] = defaultdict(int)
        for c in self.falsifications:
            per_signature[c.family_signature] += 1
            center_band = self.band_index(
                (c.contradicted_window[0] + c.contradicted_window[1]) / 2.0
            )
            per_band[center_band] += 1
        return {
            "total_falsifications": len(self.falsifications),
            "per_family_signature": dict(per_signature),
            "per_band": dict(per_band),
            "rounds_with_falsifications": sorted({c.round_index for c in self.falsifications}),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "falsifications": [
                {
                    "round_index": c.round_index,
                    "candidate_id": c.candidate_id,
                    "family_signature": c.family_signature,
                    "contradicted_window": list(c.contradicted_window),
                }
                for c in self.falsifications
            ],
            "summary": self.summary(),
        }
