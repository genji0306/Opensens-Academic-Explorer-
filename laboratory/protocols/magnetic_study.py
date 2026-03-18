"""Magnetic Study Protocol — NemadAdapter -> CS -> PB -> comparison."""
from laboratory.protocol import LabProtocol, ProtocolStage
from laboratory.registry import register_protocol

PROTOCOL = LabProtocol(
    protocol_id="magnetic_study",
    name="Magnetic Material Study",
    description="Load NEMAD magnetic material data, extract crystal patterns, "
                "predict structures, and compare with NEMAD approach.",
    material_type="magnetic",
    default_params={"max_compounds": 20},
    stages=[
        ProtocolStage(
            name="Load NEMAD data",
            agent="nemad",
            action="load_data",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Build crystal patterns",
            agent="agent_cs",
            action="build_catalog",
        ),
        ProtocolStage(
            name="Predict structures",
            agent="agent_pb",
            action="predict",
            optional=True,
        ),
        ProtocolStage(
            name="NEMAD comparison",
            agent="nemad",
            action="compare",
            checkpoint=True,
        ),
    ],
)

register_protocol(PROTOCOL)
