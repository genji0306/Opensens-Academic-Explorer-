"""Offline deterministic tool implementations for Phase G.

These tools simulate what ToolUniverse / literature APIs would return,
but do so entirely from the curated Phase C mechanism library. They
exist so Agent R, the broker, and the compose workflows can be
exercised end-to-end in CI without any network dependency.

When a real ToolUniverse adapter lands, it plugs in behind the same
:class:`Tool` protocol and the broker swaps backends transparently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.oae.agents.r.mechanism_library import (
    LibraryEntry,
    entries_for_family,
    library_entries,
)

from .base import Tool, ToolResult, ToolSpec


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _format_entry(entry: LibraryEntry) -> str:
    citations = ", ".join(c.source for c in entry.citations[:3])
    return (
        f"- [{entry.mechanism}] {entry.claim} "
        f"(support={entry.support_score:.2f}, "
        f"contradiction={entry.contradiction_score:.2f}) "
        f"citations: {citations or 'n/a'}"
    )


def _citations_for(entries: list[LibraryEntry]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        for citation in entry.citations:
            if citation.source not in seen:
                seen.add(citation.source)
                out.append(citation.source)
    return tuple(out)


# ---------------------------------------------------------------------------
# Literature search
# ---------------------------------------------------------------------------


@dataclass
class LiteratureSearchTool:
    """Offline 'literature search' — returns entries matching a family."""

    spec: ToolSpec = ToolSpec(
        name="literature_search",
        description="Retrieve curated literature for a candidate family.",
        tags=("literature", "review", "offline"),
    )

    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        family = str(arguments.get("family", "")).strip()
        if not family:
            return ToolResult(
                tool=self.spec.name,
                ok=False,
                content="missing 'family' argument",
                error="missing_argument",
            )
        entries = list(entries_for_family(family))
        if not entries:
            return ToolResult(
                tool=self.spec.name,
                ok=True,
                content=f"no curated literature for family={family!r}",
                data={"family": family, "entries": 0},
                tokens_estimated=10,
            )
        lines = [f"# Literature matches for {family}"]
        lines.extend(_format_entry(e) for e in entries)
        content = "\n".join(lines)
        return ToolResult(
            tool=self.spec.name,
            ok=True,
            content=content,
            data={"family": family, "entries": len(entries)},
            citations=_citations_for(entries),
            tokens_estimated=_estimate_tokens(content),
        )


# ---------------------------------------------------------------------------
# Materials lookup
# ---------------------------------------------------------------------------


@dataclass
class MaterialsLookupTool:
    """Offline 'materials lookup' — filters entries by tag."""

    spec: ToolSpec = ToolSpec(
        name="materials_lookup",
        description="Look up curated materials knowledge by tag.",
        tags=("materials", "offline"),
    )

    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        tag = str(arguments.get("tag", "")).strip().lower()
        if not tag:
            return ToolResult(
                tool=self.spec.name,
                ok=False,
                content="missing 'tag' argument",
                error="missing_argument",
            )
        matches = [
            entry for entry in library_entries()
            if any(t.lower() == tag for t in entry.tags)
        ]
        if not matches:
            return ToolResult(
                tool=self.spec.name,
                ok=True,
                content=f"no entries tagged {tag!r}",
                data={"tag": tag, "entries": 0},
                tokens_estimated=10,
            )
        lines = [f"# Materials tagged {tag}"]
        lines.extend(_format_entry(e) for e in matches)
        content = "\n".join(lines)
        return ToolResult(
            tool=self.spec.name,
            ok=True,
            content=content,
            data={"tag": tag, "entries": len(matches)},
            citations=_citations_for(matches),
            tokens_estimated=_estimate_tokens(content),
        )


# ---------------------------------------------------------------------------
# Mechanism summary
# ---------------------------------------------------------------------------


@dataclass
class MechanismSummaryTool:
    """Produce a compact mechanism summary for a candidate family."""

    spec: ToolSpec = ToolSpec(
        name="mechanism_summary",
        description="Summarise dominant mechanism(s) for a family.",
        tags=("theory", "review", "offline"),
        compact_token_budget=1_000,
    )

    def run(self, arguments: Mapping[str, Any]) -> ToolResult:
        family = str(arguments.get("family", "")).strip()
        if not family:
            return ToolResult(
                tool=self.spec.name,
                ok=False,
                content="missing 'family' argument",
                error="missing_argument",
            )
        entries = list(entries_for_family(family))
        if not entries:
            return ToolResult(
                tool=self.spec.name,
                ok=True,
                content=f"no mechanism entries for {family}",
                tokens_estimated=10,
            )
        ranked = sorted(
            entries,
            key=lambda e: e.support_score - e.contradiction_score,
            reverse=True,
        )
        top = ranked[0]
        content = (
            f"Top mechanism for {family}: {top.mechanism}\n"
            f"Claim: {top.claim}\n"
            f"Support={top.support_score:.2f}, "
            f"contradiction={top.contradiction_score:.2f}\n"
            f"Conditions: {top.conditions}"
        )
        return ToolResult(
            tool=self.spec.name,
            ok=True,
            content=content,
            data={
                "family": family,
                "top_mechanism": top.mechanism,
                "support": top.support_score,
                "contradiction": top.contradiction_score,
                "n_entries": len(entries),
            },
            citations=_citations_for([top]),
            tokens_estimated=_estimate_tokens(content),
        )


def build_default_tools() -> tuple[Tool, ...]:
    """Return the default offline tool set for Phase G."""
    return (
        LiteratureSearchTool(),
        MaterialsLookupTool(),
        MechanismSummaryTool(),
    )
