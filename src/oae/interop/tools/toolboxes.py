"""Curated Phase G toolboxes.

A toolbox is just a whitelisted subset of the tool catalogue grouped by
domain. Consumers configure the broker with a toolbox rather than
handing in raw tool objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base import Tool
from .offline_tools import (
    LiteratureSearchTool,
    MaterialsLookupTool,
    MechanismSummaryTool,
)


@dataclass(frozen=True)
class Toolbox:
    """Named bundle of tools for a specific discovery domain."""

    name: str
    tools: tuple[Tool, ...]
    tags: tuple[str, ...] = field(default_factory=tuple)

    def whitelist(self) -> frozenset[str]:
        return frozenset(tool.spec.name for tool in self.tools)


def materials_toolbox() -> Toolbox:
    return Toolbox(
        name="materials",
        tools=(
            LiteratureSearchTool(),
            MaterialsLookupTool(),
            MechanismSummaryTool(),
        ),
        tags=("materials", "mof", "rtap"),
    )


def sensing_toolbox() -> Toolbox:
    return Toolbox(
        name="sensing",
        tools=(
            LiteratureSearchTool(),
            MaterialsLookupTool(),
            MechanismSummaryTool(),
        ),
        tags=("sensing", "electrochem"),
    )
