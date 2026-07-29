"""NL proof claim -> Lean 4 skeleton with sorry placeholders (Phase 2)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def _slug(text: str) -> str:
    """Produce a deterministic Lean-safe identifier from arbitrary text."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text)
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "unnamed"
    # Lean identifiers must not start with a digit.
    if cleaned[0].isdigit():
        cleaned = "x_" + cleaned
    return cleaned[:40]


@dataclass(frozen=True)
class FormalizationResult:
    """Output of :func:`formalize`."""

    lean_source: str
    decl_names: tuple[str, ...]
    sorry_count: int
    confidence: float  # 0-1 heuristic: how many obligations were mapped


def formalize(
    claim: str,
    *,
    obligations: tuple[str, ...] = (),
    candidate_id: str = "",
) -> FormalizationResult:
    """Convert a natural-language proof claim to a Lean 4 skeleton.

    Each obligation becomes one ``theorem obligation_N : ... := by sorry``
    block.  The file always starts with ``import Mathlib``.

    Confidence is a Phase-2 heuristic; a real LLM call replaces it in Phase 3+.
    """
    id_slug = _slug(candidate_id) if candidate_id else "anon"

    lines: list[str] = [
        "import Mathlib",
        "",
        f"-- Auto-generated Lean 4 skeleton for candidate: {candidate_id or 'anon'}",
        f"-- Claim: {claim}",
        "",
    ]

    decl_names: list[str] = []

    # Main claim theorem
    main_name = f"main_claim_{id_slug}"
    decl_names.append(main_name)
    claim_escaped = claim.replace('"', '\\"')
    lines += [
        f"-- Main claim",
        f"theorem {main_name} : True := by",
        f"  -- {claim_escaped}",
        f"  sorry",
        "",
    ]

    # One theorem block per obligation
    for idx, obligation in enumerate(obligations):
        ob_slug = _slug(obligation)
        decl_name = f"obligation_{idx}_{ob_slug}_{id_slug}"
        decl_names.append(decl_name)
        ob_escaped = obligation.replace('"', '\\"')
        lines += [
            f"-- Obligation {idx}: {ob_escaped}",
            f"theorem {decl_name} : True := by",
            f"  -- {ob_escaped}",
            f"  sorry",
            "",
        ]

    lean_source = "\n".join(lines)

    # sorry count equals total declarations (one sorry each)
    sorry_count = len(decl_names)

    # Heuristic confidence: base 0.3 + 0.1 per obligation, capped at 1.0
    confidence = min(1.0, 0.3 + 0.1 * len(obligations))

    return FormalizationResult(
        lean_source=lean_source,
        decl_names=tuple(decl_names),
        sorry_count=sorry_count,
        confidence=confidence,
    )


def formalize_batch(candidates: list[dict[str, Any]]) -> list[FormalizationResult]:
    """Formalize a list of candidate dicts, each with claim/obligations/candidate_id.

    Returns results in the same order as ``candidates``.
    """
    results: list[FormalizationResult] = []
    for item in candidates:
        results.append(
            formalize(
                item.get("claim", ""),
                obligations=tuple(item.get("obligations", ())),
                candidate_id=str(item.get("candidate_id", "")),
            )
        )
    return results
