"""Aristotle-style 3-component agent: lean_search + informal lemma gen + dedicated solver (Phase 3)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import autoformalizer
from .lean_search_agent import LeanSearchAgent


@dataclass(frozen=True)
class AristotleResult:
    """Result produced by :class:`AristotleStyleAgent` for a single hypothesis."""

    candidate_id: str
    lean_matches: tuple[str, ...]  # declaration names found by lean_search
    informal_lemma: str  # generated informal lemma statement
    lean_skeleton: str  # Lean formalization of the informal lemma
    solver_verdict: str  # "promoted", "blocked", or "deferred"
    solver_reason: str


class AristotleStyleAgent:
    """3-component agent: Lean library search, informal lemma generation, solver verdict.

    Workflow per hypothesis:
    1. Search ``lean_rh_root`` for declarations relevant to the claim.
    2. Generate an informal lemma from the first unresolved obligation (or the main claim).
    3. Formalize the informal lemma into a Lean 4 skeleton via :func:`autoformalizer.formalize`.
    4. Determine solver verdict:
       - "promoted"  — at least one matching Lean decl found.
       - "blocked"   — more than 3 unresolved proof obligations.
       - "deferred"  — otherwise.
    """

    name = "aristotle"

    def __init__(self, lean_rh_root: Path) -> None:
        self._searcher = LeanSearchAgent(Path(lean_rh_root))

    def run(self, hypotheses: list[dict[str, Any]]) -> list[AristotleResult]:
        """Process a list of hypothesis dicts and return :class:`AristotleResult` list.

        Each dict must contain:
        - ``candidate_id`` (str)
        - ``claim`` (str)
        - ``unresolved_proof_obligations`` (list[str] or tuple[str, ...])
        """
        results: list[AristotleResult] = []
        for hyp in hypotheses:
            candidate_id = str(hyp.get("candidate_id", ""))
            claim = str(hyp.get("claim", ""))
            obligations = list(hyp.get("unresolved_proof_obligations", []))

            # Step 1: Lean library search
            search_result = self._searcher.search(claim)
            lean_matches = search_result.matches

            # Step 2: Generate informal lemma
            if obligations:
                informal_lemma = obligations[0]
            else:
                informal_lemma = claim

            # Step 3: Formalize the informal lemma
            formal = autoformalizer.formalize(
                informal_lemma,
                obligations=tuple(obligations),
                candidate_id=candidate_id,
            )
            lean_skeleton = formal.lean_source

            # Step 4: Solver verdict
            if lean_matches:
                verdict = "promoted"
                reason = f"{len(lean_matches)} matching Lean declaration(s) found"
            elif len(obligations) > 3:
                verdict = "blocked"
                reason = f"{len(obligations)} unresolved obligations exceed threshold (3)"
            else:
                verdict = "deferred"
                reason = "no Lean matches; obligation count within tolerated range"

            results.append(
                AristotleResult(
                    candidate_id=candidate_id,
                    lean_matches=lean_matches,
                    informal_lemma=informal_lemma,
                    lean_skeleton=lean_skeleton,
                    solver_verdict=verdict,
                    solver_reason=reason,
                )
            )
        return results
