"""Lean search agent: find relevant Lean lemmas in lean/RH/ for a given claim (Phase 3, Aristotle-style)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import lean_bridge


@dataclass(frozen=True)
class LeanSearchResult:
    """Result from :class:`LeanSearchAgent` for a single query."""

    query: str
    matches: tuple[str, ...]  # matched declaration names
    source_files: tuple[str, ...]  # paths of files containing matches
    match_count: int


class LeanSearchAgent:
    """Search ``lean_rh_root`` for Lean declarations relevant to a given query.

    The search uses a simple keyword match: any word from the lowercase query
    that appears in a declaration name triggers a match.
    """

    name = "lean_search"

    def __init__(self, lean_rh_root: Path) -> None:
        self._root = Path(lean_rh_root)

    def search(self, query: str) -> LeanSearchResult:
        """Walk ``lean_rh_root`` for ``.lean`` files and return matching decls.

        Each ``.lean`` file is verified with ``backend="mock"`` to extract
        declaration names.  Declarations are matched when at least one word
        from the lowercase query appears as a substring of the lowercase
        declaration name.
        """
        keywords = [w for w in query.lower().split() if w]
        matched_decls: list[str] = []
        matched_files: list[str] = []

        if self._root.exists():
            lean_files = sorted(self._root.rglob("*.lean"))
        else:
            lean_files = []

        for lean_file in lean_files:
            try:
                result = lean_bridge.verify_file(lean_file, backend="mock")
            except Exception:  # noqa: BLE001
                continue
            file_matched = False
            for decl in result.decls:
                decl_lower = decl.lower()
                if any(kw in decl_lower for kw in keywords):
                    matched_decls.append(decl)
                    file_matched = True
            if file_matched:
                matched_files.append(str(lean_file))

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_decls: list[str] = []
        for d in matched_decls:
            if d not in seen:
                seen.add(d)
                unique_decls.append(d)
        unique_decls.sort()

        return LeanSearchResult(
            query=query,
            matches=tuple(unique_decls),
            source_files=tuple(sorted(set(matched_files))),
            match_count=len(unique_decls),
        )

    def run(self, claims: list[str]) -> list[LeanSearchResult]:
        """Batch version: search for each claim independently."""
        return [self.search(claim) for claim in claims]
