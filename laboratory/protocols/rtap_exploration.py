"""RTAP Exploration Protocol — CS -> MC3D -> Sin -> Ob -> GCD."""
from laboratory.protocol import LabProtocol, ProtocolStage
from laboratory.registry import register_protocol

PROTOCOL = LabProtocol(
    protocol_id="rtap_exploration",
    name="RTAP Discovery Exploration",
    description="Room-Temperature Ambient-Pressure superconductor search: "
                "build patterns, calibrate with MC3D, generate multi-mechanism "
                "candidates, score with RTAP weights, extrapolate.",
    material_type="superconductor",
    default_params={"target": 0.85, "max_iterations": 50,
                    "target_pressure_GPa": 0.0},
    stages=[
        ProtocolStage(
            name="Build RTAP patterns",
            agent="agent_cs",
            action="build_catalog",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Generate RTAP structures",
            agent="agent_sin",
            action="generate_structures",
            params={"target_pressure_GPa": 0.0},
        ),
        ProtocolStage(
            name="RTAP scoring",
            agent="agent_ob",
            action="score",
            params={"mode": "rtap"},
            checkpoint=True,
        ),
        ProtocolStage(
            name="Compositional extrapolation",
            agent="agent_gcd",
            action="extrapolate",
            optional=True,
        ),
        ProtocolStage(
            name="Visualize RTAP results",
            agent="agent_v",
            action="render",
            optional=True,
        ),
    ],
)

register_protocol(PROTOCOL)
