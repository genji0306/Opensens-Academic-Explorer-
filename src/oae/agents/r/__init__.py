"""Agent R — offline-first review and theory agent (Phase C)."""
from __future__ import annotations

from .agent_r import AgentR, AgentRConfig, run_agent_r
from .mechanism_library import (
    LibraryEntry,
    entries_for_family,
    library_entries,
    theory_cards_for_families,
    theory_cards_for_family,
)

__all__ = [
    "AgentR",
    "AgentRConfig",
    "run_agent_r",
    "LibraryEntry",
    "library_entries",
    "entries_for_family",
    "theory_cards_for_family",
    "theory_cards_for_families",
]
