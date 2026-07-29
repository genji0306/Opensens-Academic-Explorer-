"""Phase G — ToolUniverse-compatible tool broker.

The broker exposes a curated, whitelisted, provenance-logging interface
over any collection of ``Tool`` objects. Real ToolUniverse / LLM tool
calls can be registered as :class:`Tool` instances, and the broker
handles whitelist enforcement, two-tier caching, compact-mode context
truncation, and append-only provenance logging.

Phase G intentionally ships with offline deterministic tools only so
the discovery loop, dossier writer, and Agent R can run end-to-end in
CI without any external dependency.
"""
from __future__ import annotations

from .base import Tool, ToolCall, ToolResult, ToolSpec
from .broker import BrokerConfig, ToolBroker, ToolBrokerError
from .cache import ToolCache
from .offline_tools import (
    LiteratureSearchTool,
    MaterialsLookupTool,
    MechanismSummaryTool,
    build_default_tools,
)
from .toolboxes import materials_toolbox, sensing_toolbox
from .workflows import (
    ComposeWorkflow,
    WorkflowStep,
    assay_design_brief,
    electrode_material_background,
    interferent_profile,
    mof_mechanism_review,
    sensor_evidence_pack,
    sensor_literature_review,
)

__all__ = [
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "BrokerConfig",
    "ToolBroker",
    "ToolBrokerError",
    "ToolCache",
    "LiteratureSearchTool",
    "MaterialsLookupTool",
    "MechanismSummaryTool",
    "build_default_tools",
    "materials_toolbox",
    "sensing_toolbox",
    "ComposeWorkflow",
    "WorkflowStep",
    "assay_design_brief",
    "electrode_material_background",
    "interferent_profile",
    "mof_mechanism_review",
    "sensor_evidence_pack",
    "sensor_literature_review",
]
