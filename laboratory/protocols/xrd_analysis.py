"""XRD Analysis Protocol — XC -> V -> Ob."""
from laboratory.protocol import LabProtocol, ProtocolStage
from laboratory.registry import register_protocol

PROTOCOL = LabProtocol(
    protocol_id="xrd_analysis",
    name="XRD Pattern Analysis",
    description="Analyze an XRD pattern to determine crystal structure using "
                "Agent XC, visualize the result, and score against reference.",
    material_type="crystal",
    default_params={},
    stages=[
        ProtocolStage(
            name="XRD to structure",
            agent="agent_xc",
            action="predict",
            optional=True,
        ),
        ProtocolStage(
            name="Visualize structure",
            agent="agent_v",
            action="render",
            optional=True,
        ),
        ProtocolStage(
            name="Score against reference",
            agent="agent_ob",
            action="score",
            optional=True,
        ),
    ],
)

register_protocol(PROTOCOL)
