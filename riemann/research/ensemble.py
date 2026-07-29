"""Multi-proposer -> cheap-verifier rejection ensemble (Phase 3, Putnam2025 pattern)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import lean_bridge


@dataclass(frozen=True)
class EnsembleResult:
    """Result for a single candidate evaluated by the ensemble."""

    candidate_id: str
    accepted: bool
    verifier_scores: tuple[float, ...]  # one score per verifier signal
    consensus: float  # mean of verifier_scores
    rejection_reason: str  # empty string when accepted
    lean_check_result: dict[str, Any]  # serialized LeanCheckResult


class ProposalEnsemble:
    """Run candidates through a lightweight verifier and accept/reject by consensus.

    The ensemble uses two verifier signals derived from :func:`lean_bridge.verify`:

    1. ``passed`` — structural check: at least one declaration present.
    2. ``sorry_fraction`` — fraction of decls that are NOT backed by sorry
       (higher is better; fully sorry-filled skeleton scores 0).

    ``consensus = 0.6 * float(passed) + 0.4 * sorry_fraction``

    A candidate is accepted when ``consensus >= rejection_threshold``.
    """

    def __init__(self, *, rejection_threshold: float = 0.70) -> None:
        self._threshold = rejection_threshold

    def run(
        self,
        candidates: list[dict[str, Any]],
        *,
        lean_skeleton_key: str = "lean_skeleton",
    ) -> list[EnsembleResult]:
        """Evaluate each candidate dict and return :class:`EnsembleResult` list."""
        results: list[EnsembleResult] = []
        for candidate in candidates:
            candidate_id = str(candidate.get("candidate_id", ""))
            lean_source = candidate.get(lean_skeleton_key, "")

            if not lean_source:
                results.append(
                    EnsembleResult(
                        candidate_id=candidate_id,
                        accepted=False,
                        verifier_scores=(0.0,),
                        consensus=0.0,
                        rejection_reason="no_lean_skeleton",
                        lean_check_result={},
                    )
                )
                continue

            check = lean_bridge.verify(lean_source, backend="mock")

            # sorry_fraction: proportion of decls NOT covered by sorry
            # Capped to [0, 1].
            decl_count = max(len(check.decls), 1)
            sorry_frac = max(0.0, min(1.0, 1.0 - (check.sorry_count / decl_count)))

            passed_signal = float(check.passed)
            consensus = 0.6 * passed_signal + 0.4 * sorry_frac

            accepted = consensus >= self._threshold
            rejection_reason = "" if accepted else "consensus_below_threshold"

            results.append(
                EnsembleResult(
                    candidate_id=candidate_id,
                    accepted=accepted,
                    verifier_scores=(passed_signal, sorry_frac),
                    consensus=consensus,
                    rejection_reason=rejection_reason,
                    lean_check_result=check.to_dict(),
                )
            )
        return results

    def rejection_rate(self, results: list[EnsembleResult]) -> float:
        """Return fraction of results that were rejected (0.0 when list is empty)."""
        if not results:
            return 0.0
        rejected = sum(1 for r in results if not r.accepted)
        return rejected / len(results)
