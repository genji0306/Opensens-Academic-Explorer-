"""Execution plan and result dataclasses for Skill v2.0 router."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("Skill.Schemas")


@dataclass
class ExecutionStep:
    """Single step in an execution plan."""

    agent: str  # e.g. "agent_pb", "agent_xc", "agent_v"
    action: str  # e.g. "predict", "visualize", "benchmark"
    params: dict = field(default_factory=dict)
    depends_on: list = field(default_factory=list)  # indices of prior steps


@dataclass
class ExecutionPlan:
    """Multi-step execution plan produced by IntentRouter."""

    intent: str  # classified intent name
    steps: list = field(default_factory=list)  # list of ExecutionStep
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def n_steps(self) -> int:
        return len(self.steps)

    @property
    def agents_involved(self) -> list:
        return list(dict.fromkeys(s.agent for s in self.steps))

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "n_steps": self.n_steps,
            "agents": self.agents_involved,
            "steps": [
                {"agent": s.agent, "action": s.action, "params": s.params,
                 "depends_on": s.depends_on}
                for s in self.steps
            ],
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_index: int
    agent: str
    action: str
    success: bool
    output_path: Optional[Path] = None
    error: Optional[str] = None
    wall_time_seconds: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Aggregate result of executing an entire plan."""

    plan: ExecutionPlan
    step_results: list = field(default_factory=list)  # list of StepResult
    completed_at: str = ""

    @property
    def success(self) -> bool:
        return all(r.success for r in self.step_results)

    @property
    def total_time(self) -> float:
        return sum(r.wall_time_seconds for r in self.step_results)

    @property
    def failed_steps(self) -> list:
        return [r for r in self.step_results if not r.success]

    def summary(self) -> dict:
        return {
            "intent": self.plan.intent,
            "success": self.success,
            "n_steps": self.plan.n_steps,
            "n_completed": sum(1 for r in self.step_results if r.success),
            "n_failed": len(self.failed_steps),
            "total_time_seconds": round(self.total_time, 2),
            "completed_at": self.completed_at,
        }
