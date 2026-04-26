"""Compose workflows — canned multi-tool sequences for Phase G.

A ``ComposeWorkflow`` is a deterministic list of steps. Each step calls
one tool via the broker, optionally transforming the arguments from the
previous step's output. Workflows are the unit Agent R and the Sensing
Studio Scientific Reasoning module will consume in later phases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .base import ToolResult
from .broker import ToolBroker


ArgsResolver = Callable[[dict[str, ToolResult], Mapping[str, Any]], Mapping[str, Any]]


def _static(args: Mapping[str, Any]) -> ArgsResolver:
    def _resolve(_state: dict[str, ToolResult], context: Mapping[str, Any]) -> Mapping[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in args.items():
            if isinstance(value, str) and value.startswith("$"):
                resolved[key] = context.get(value[1:], value)
            else:
                resolved[key] = value
        return resolved
    return _resolve


@dataclass(frozen=True)
class WorkflowStep:
    """Single invocation within a workflow."""

    name: str
    tool: str
    args: ArgsResolver


@dataclass(frozen=True)
class ComposeWorkflow:
    """A named, deterministic sequence of ``WorkflowStep``s."""

    name: str
    steps: tuple[WorkflowStep, ...]
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def run(
        self,
        broker: ToolBroker,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, ToolResult]:
        """Execute the workflow end-to-end.

        ``context`` is a bag of variables the steps may reference via
        ``$name`` placeholders. Step results are keyed by ``step.name``.
        """
        ctx = dict(context or {})
        state: dict[str, ToolResult] = {}
        for step in self.steps:
            args = step.args(state, ctx)
            result = broker.call(step.tool, **args)
            state[step.name] = result
        return state


# ---------------------------------------------------------------------------
# Built-in workflows
# ---------------------------------------------------------------------------


def mof_mechanism_review() -> ComposeWorkflow:
    return ComposeWorkflow(
        name="mof_mechanism_review",
        description="Look up curated MOF mechanism entries for a family.",
        tags=("mof", "review"),
        steps=(
            WorkflowStep(
                name="summary",
                tool="mechanism_summary",
                args=_static({"family": "$family"}),
            ),
            WorkflowStep(
                name="literature",
                tool="literature_search",
                args=_static({"family": "$family"}),
            ),
        ),
    )


def sensor_literature_review() -> ComposeWorkflow:
    return ComposeWorkflow(
        name="sensor_literature_review",
        description="Literature + mechanism summary for a sensing family.",
        tags=("sensing", "review"),
        steps=(
            WorkflowStep(
                name="literature",
                tool="literature_search",
                args=_static({"family": "$family"}),
            ),
            WorkflowStep(
                name="summary",
                tool="mechanism_summary",
                args=_static({"family": "$family"}),
            ),
        ),
    )


def interferent_profile() -> ComposeWorkflow:
    return ComposeWorkflow(
        name="interferent_profile",
        description="Pull interferent-tagged materials knowledge.",
        tags=("sensing",),
        steps=(
            WorkflowStep(
                name="lookup",
                tool="materials_lookup",
                args=_static({"tag": "interferent"}),
            ),
        ),
    )


def electrode_material_background() -> ComposeWorkflow:
    return ComposeWorkflow(
        name="electrode_material_background",
        description="Electrode-material background for a sensor family.",
        tags=("sensing", "materials"),
        steps=(
            WorkflowStep(
                name="materials",
                tool="materials_lookup",
                args=_static({"tag": "electrode"}),
            ),
            WorkflowStep(
                name="summary",
                tool="mechanism_summary",
                args=_static({"family": "$family"}),
            ),
        ),
    )


def assay_design_brief() -> ComposeWorkflow:
    return ComposeWorkflow(
        name="assay_design_brief",
        description="Compose a sensing assay design brief.",
        tags=("sensing",),
        steps=(
            WorkflowStep(
                name="literature",
                tool="literature_search",
                args=_static({"family": "$family"}),
            ),
            WorkflowStep(
                name="mechanism",
                tool="mechanism_summary",
                args=_static({"family": "$family"}),
            ),
            WorkflowStep(
                name="interferents",
                tool="materials_lookup",
                args=_static({"tag": "interferent"}),
            ),
        ),
    )


def sensor_evidence_pack() -> ComposeWorkflow:
    return ComposeWorkflow(
        name="sensor_evidence_pack",
        description="Cross-source sensing evidence bundle.",
        tags=("sensing", "review"),
        steps=(
            WorkflowStep(
                name="literature",
                tool="literature_search",
                args=_static({"family": "$family"}),
            ),
            WorkflowStep(
                name="materials",
                tool="materials_lookup",
                args=_static({"tag": "$tag"}),
            ),
        ),
    )
