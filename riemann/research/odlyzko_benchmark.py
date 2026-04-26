"""Odlyzko zero-consistency external benchmark for RH research campaigns.

This is the FIRST real (non-stub) external evaluator wired into the hyperloop.

Why Odlyzko qualifies as 'external':
    The Odlyzko zero tables are empirical mathematical ground truth — they
    pre-exist any orchestrator and cannot be moved by paraphrase, novelty
    artifacts, or self-grading. A hypothesis that makes a numeric claim about
    zero locations either matches the table or doesn't. This is the
    'moving-target evaluation' the hyperloop plan §3 specifies, with the table
    itself as the immovable target.

Scoring:
    empirical_consistency in [0, 1] for each candidate:
        - +0.30 base (well-formed candidate)
        - +0.10 per ingredient family with mechanically checkable semantics
                (hardy_z, explicit_formula, de_branges, xi_function,
                 random_matrix, mollifier_moment)
        - +0.05 per closed obligation class (resolved progress)
        - -0.20 per uncontradicted-but-untestable obligation class
                (unresolved AND not in the checkable family list)
        - -0.50 if any explicit numeric prediction in the lean_skeleton
                contradicts the Odlyzko table (cap floor at 0.0)

Campaign external_score = mean of per-candidate empirical_consistency over
                          all evaluations in the round.

The scoring is intentionally biased to penalize:
    * candidates that orbit on abstract restatement (no checkable families)
    * candidates that pile up obligations they can't discharge
    * candidates whose claims contradict empirical zeros

And to reward:
    * candidates that commit to checkable predictions
    * candidates that close obligations
    * candidates whose ingredient mix spans falsifiable territory
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Ingredient families whose claims are mechanically checkable against zero tables.
_CHECKABLE_FAMILIES = frozenset({
    "hardy_z",
    "explicit_formula",
    "de_branges",
    "xi_function",
    "random_matrix",
    "mollifier_moment",
})

# Numeric pattern: matches floats/ints inside lean source likely to be height claims.
_NUMERIC_HEIGHT_RE = re.compile(r"\b(\d+\.\d+|\d{2,})\b")

# Phase 1: structured `no_zero_in T_lo T_hi` claim parser.
_NO_ZERO_IN_RE = re.compile(r"no_zero_in\s+(\d+\.\d+)\s+(\d+\.\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class OdlyzkoTable:
    """Cached, sorted Odlyzko zero heights (imaginary parts on critical line)."""

    heights: tuple[float, ...]

    @classmethod
    def load(cls, path: Path, *, max_zeros: int | None = None) -> "OdlyzkoTable":
        heights: list[float] = []
        with path.open() as fh:
            for i, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    heights.append(float(line))
                except ValueError:
                    continue
                if max_zeros is not None and i + 1 >= max_zeros:
                    break
        return cls(heights=tuple(heights))

    @property
    def t_max(self) -> float:
        return self.heights[-1] if self.heights else 0.0

    def count_in_window(self, t_lo: float, t_hi: float) -> int:
        """Count zeros with t_lo <= t <= t_hi (linear scan; tables are small)."""
        return sum(1 for t in self.heights if t_lo <= t <= t_hi)

    def contradicts_no_zero_claim(self, t_lo: float, t_hi: float) -> bool:
        """A 'no zero in (t_lo, t_hi)' claim is contradicted if any zero falls inside."""
        return self.count_in_window(t_lo, t_hi) > 0


@dataclass(frozen=True)
class CandidateConsistencyScore:
    candidate_id: str
    score: float
    base: float
    family_bonus: float
    closed_obligation_bonus: float
    untestable_penalty: float
    contradiction_penalty: float
    correct_claim_bonus: float
    contradicted_window: tuple[float, float] | None
    confirmed_window: tuple[float, float] | None
    breakdown: dict[str, float]


@dataclass(frozen=True)
class OdlyzkoBenchmarkResult:
    """Round-level result for one campaign × one round."""

    round_index: int
    candidate_count: int
    mean_score: float
    contradicted_count: int
    confirmed_count: int
    untestable_count: int
    per_candidate: tuple[CandidateConsistencyScore, ...]


def score_candidate(
    *,
    candidate_id: str,
    ingredient_families: tuple[str, ...],
    closed_obligation_count: int,
    open_obligation_count: int,
    lean_skeleton: str,
    odlyzko: OdlyzkoTable,
) -> CandidateConsistencyScore:
    base = 0.30
    checkable = [fam for fam in ingredient_families if fam in _CHECKABLE_FAMILIES]
    family_bonus = 0.10 * len(checkable)
    closed_bonus = 0.05 * closed_obligation_count
    untestable_penalty = -0.20 * max(
        0,
        open_obligation_count - len(checkable),
    )

    # Phase 1: parse the falsifiable `no_zero_in T_lo T_hi` claim from the
    # skeleton and let the Odlyzko table adjudicate.
    #   - Contradicted (any zero in the window): -0.50
    #   - Confirmed (no zero in the window, window inside table range): +0.20
    #   - No claim: 0
    contradiction_penalty = 0.0
    correct_claim_bonus = 0.0
    contradicted_window: tuple[float, float] | None = None
    confirmed_window: tuple[float, float] | None = None
    if lean_skeleton and "no_zero_in" in lean_skeleton.lower():
        # Find all "no_zero_in T_lo T_hi" patterns. Use the first if multiple.
        match = _NO_ZERO_IN_RE.search(lean_skeleton)
        if match:
            t_lo = float(match.group(1))
            t_hi = float(match.group(2))
            if t_lo > t_hi:
                t_lo, t_hi = t_hi, t_lo
            if odlyzko.contradicts_no_zero_claim(t_lo, t_hi):
                contradiction_penalty = -0.50
                contradicted_window = (t_lo, t_hi)
            elif t_hi <= odlyzko.t_max and odlyzko.heights:
                # Window is inside the verified Odlyzko range AND empty → real prediction confirmed.
                correct_claim_bonus = 0.20
                confirmed_window = (t_lo, t_hi)
            # If t_hi > t_max we cannot confirm; treat as no signal (0).

    raw = (
        base + family_bonus + closed_bonus + untestable_penalty
        + contradiction_penalty + correct_claim_bonus
    )
    score = max(0.0, min(1.0, raw))
    breakdown = {
        "base": base,
        "family_bonus": family_bonus,
        "closed_bonus": closed_bonus,
        "untestable_penalty": untestable_penalty,
        "contradiction_penalty": contradiction_penalty,
        "correct_claim_bonus": correct_claim_bonus,
        "raw": raw,
        "clamped": score,
    }
    return CandidateConsistencyScore(
        candidate_id=candidate_id,
        score=score,
        base=base,
        family_bonus=family_bonus,
        closed_obligation_bonus=closed_bonus,
        untestable_penalty=untestable_penalty,
        contradiction_penalty=contradiction_penalty,
        correct_claim_bonus=correct_claim_bonus,
        contradicted_window=contradicted_window,
        confirmed_window=confirmed_window,
        breakdown=breakdown,
    )


def evaluate_round(
    *,
    round_index: int,
    candidate_records: list[dict],
    odlyzko: OdlyzkoTable,
) -> OdlyzkoBenchmarkResult:
    """candidate_records: list of dicts with keys candidate_id, ingredient_families,
    closed_obligation_count, open_obligation_count, lean_skeleton."""
    per_candidate: list[CandidateConsistencyScore] = []
    for rec in candidate_records:
        per_candidate.append(
            score_candidate(
                candidate_id=rec.get("candidate_id", "?"),
                ingredient_families=tuple(rec.get("ingredient_families", ())),
                closed_obligation_count=int(rec.get("closed_obligation_count", 0)),
                open_obligation_count=int(rec.get("open_obligation_count", 0)),
                lean_skeleton=str(rec.get("lean_skeleton", "")),
                odlyzko=odlyzko,
            )
        )
    if per_candidate:
        mean = sum(c.score for c in per_candidate) / len(per_candidate)
    else:
        mean = 0.0
    contradicted = sum(1 for c in per_candidate if c.contradiction_penalty < 0)
    confirmed = sum(1 for c in per_candidate if c.correct_claim_bonus > 0)
    untestable = sum(1 for c in per_candidate if c.untestable_penalty < 0)
    return OdlyzkoBenchmarkResult(
        round_index=round_index,
        candidate_count=len(per_candidate),
        mean_score=mean,
        contradicted_count=contradicted,
        confirmed_count=confirmed,
        untestable_count=untestable,
        per_candidate=tuple(per_candidate),
    )
