"""
OAE Laboratory Protocol — Base dataclasses for experimental protocols.

A LabProtocol defines a sequence of stages, each invoking an agent action.
Stages can be checkpointed and resumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ProtocolStage:
    """A single stage in a laboratory protocol."""
    name: str
    agent: str       # agent_cs|agent_sin|agent_ob|agent_pb|agent_xc|agent_v|agent_gcd|nemad
    action: str      # e.g., "build_catalog", "generate_structures", "score"
    params: dict = field(default_factory=dict)
    checkpoint: bool = False  # Save state after this stage
    optional: bool = False    # Skip if agent unavailable

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LabProtocol:
    """A named experimental protocol with defined stages."""
    protocol_id: str
    name: str
    description: str
    stages: list[ProtocolStage] = field(default_factory=list)
    default_params: dict = field(default_factory=dict)
    material_type: str = "superconductor"  # superconductor|magnetic|crystal|general

    def to_dict(self) -> dict:
        return {
            "protocol_id": self.protocol_id,
            "name": self.name,
            "description": self.description,
            "material_type": self.material_type,
            "default_params": self.default_params,
            "stages": [s.to_dict() for s in self.stages],
        }

    def stage_names(self) -> list[str]:
        """Return list of stage names."""
        return [s.name for s in self.stages]


@dataclass
class CheckpointData:
    """Saved state at a protocol checkpoint."""
    protocol_id: str
    stage_index: int
    stage_name: str
    results: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
