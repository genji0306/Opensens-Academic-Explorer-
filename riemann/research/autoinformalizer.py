"""Lean 4 statement -> NL description (Phase 2, round-trip canonicality check)."""
from __future__ import annotations

import re
from dataclasses import dataclass

_DECL_RE = re.compile(
    r"\b(theorem|lemma|def|example|instance)\s+([A-Za-z_][\w']*)",
    re.MULTILINE,
)
_SORRY_RE = re.compile(r"\bsorry\b")
_BLOCK_COMMENT_RE = re.compile(r"/-[!-]?.*?-/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")


def _strip_comments(source: str) -> str:
    no_block = _BLOCK_COMMENT_RE.sub("", source)
    return _LINE_COMMENT_RE.sub("", no_block)


@dataclass(frozen=True)
class InformalizationResult:
    """Output of :func:`informalize`."""

    natural_language: str
    decl_names: tuple[str, ...]
    sorry_count: int
    round_trip_ok: bool  # True when sorry density is below threshold


def informalize(lean_source: str) -> InformalizationResult:
    """Parse Lean 4 source and produce a natural-language description.

    For each declaration found, the output includes a one-line stub:
    ``"Theorem <name>: <stub description>"``.

    ``round_trip_ok`` is a heuristic: fewer than 3 sorries per declaration
    means the skeleton is not entirely hollow.
    """
    stripped = _strip_comments(lean_source)
    decl_names = tuple(name for _kind, name in _DECL_RE.findall(stripped))
    sorry_count = len(_SORRY_RE.findall(stripped))

    if not decl_names:
        nl = "No declarations found in the provided Lean source."
    else:
        stub_lines: list[str] = []
        for name in decl_names:
            readable = name.replace("_", " ").strip()
            stub_lines.append(f"Theorem {name}: {readable}.")
        nl = "\n".join(stub_lines)

    # Heuristic: too many sorries relative to declarations means not really proven
    threshold = len(decl_names) * 3
    round_trip_ok = sorry_count < threshold if decl_names else False

    return InformalizationResult(
        natural_language=nl,
        decl_names=decl_names,
        sorry_count=sorry_count,
        round_trip_ok=round_trip_ok,
    )


def check_round_trip(original_claim: str, lean_source: str) -> bool:  # noqa: ARG001
    """Shorthand: returns ``informalize(lean_source).round_trip_ok``.

    The ``original_claim`` parameter is reserved for future LLM-based
    semantic comparison (Phase 3+).
    """
    return informalize(lean_source).round_trip_ok
