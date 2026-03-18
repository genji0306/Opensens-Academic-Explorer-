"""Discovery Protocol — CS -> Sin -> Ob -> GCD -> V convergence loop."""
from laboratory.protocol import LabProtocol, ProtocolStage
from laboratory.registry import register_protocol

PROTOCOL = LabProtocol(
    protocol_id="discovery",
    name="Material Discovery",
    description="Full convergence loop: build patterns, generate structures, "
                "score against experiment, extrapolate new compositions.",
    material_type="superconductor",
    default_params={"target": 0.95, "max_iterations": 20,
                    "target_pressure_GPa": 0.0},
    stages=[
        ProtocolStage(
            name="Build crystal patterns",
            agent="agent_cs",
            action="build_catalog",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Generate synthetic structures",
            agent="agent_sin",
            action="generate_structures",
        ),
        ProtocolStage(
            name="Score and compare",
            agent="agent_ob",
            action="score",
            checkpoint=True,
        ),
        ProtocolStage(
            name="Compositional extrapolation",
            agent="agent_gcd",
            action="extrapolate",
            optional=True,
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
