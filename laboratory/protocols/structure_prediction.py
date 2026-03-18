"""Structure Prediction Protocol — PB -> CB -> V."""
from laboratory.protocol import LabProtocol, ProtocolStage
from laboratory.registry import register_protocol

PROTOCOL = LabProtocol(
    protocol_id="structure_prediction",
    name="Crystal Structure Prediction",
    description="Predict crystal structure from chemical formula using Agent PB, "
                "then render and export CIF.",
    material_type="crystal",
    default_params={"algorithm": "hybrid", "top_k": 10},
    stages=[
        ProtocolStage(
            name="Predict structure",
            agent="agent_pb",
            action="predict",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Render structure",
            agent="agent_v",
            action="render",
            optional=True,
        ),
    ],
)

register_protocol(PROTOCOL)
