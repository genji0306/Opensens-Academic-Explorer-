"""Verification Protocol — CS -> Sin -> Ob -> CB -> P (pressure scan) -> V."""
from laboratory.protocol import LabProtocol, ProtocolStage
from laboratory.registry import register_protocol

PROTOCOL = LabProtocol(
    protocol_id="verification",
    name="Candidate Verification",
    description="Verify a set of candidate structures: generate candidates, "
                "score them, build detailed crystal models with feasibility "
                "evaluation, run pressure scan, and generate report.",
    material_type="superconductor",
    default_params={"target_pressure_GPa": 200.0},
    stages=[
        ProtocolStage(
            name="Build crystal patterns",
            agent="agent_cs",
            action="build_catalog",
        ),
        ProtocolStage(
            name="Generate structures",
            agent="agent_sin",
            action="generate_structures",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Score candidates",
            agent="agent_ob",
            action="score",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Build crystal models",
            agent="agent_cb",
            action="build_structures",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Pressure scan",
            agent="agent_p",
            action="pressure_scan",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Visualize results",
            agent="agent_v",
            action="render",
            optional=True,
        ),
    ],
)

register_protocol(PROTOCOL)
