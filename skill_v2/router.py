"""Intent router — classifies user requests and builds execution plans.

Supports 6 intents:
  1. predict_structure  — GNN-based crystal structure prediction (Agent PB)
  2. predict_from_xrd   — XRD pattern → structure (Agent XC)
  3. discover_material   — Full convergence loop (CS → Sin → Ob)
  4. visualize           — Generate CIF / dashboard / images (Agent V)
  5. benchmark           — Compare agents on standardized datasets
  6. discover_rtsc       — RTAP discovery loop (Room-Temperature Ambient-Pressure SC)
"""
import logging
import re
from pathlib import Path
from typing import Optional

from skill_v2.schemas import ExecutionPlan, ExecutionStep

logger = logging.getLogger("Skill.Router")

# Keyword patterns for intent classification (order matters — first match wins)
INTENT_PATTERNS = {
    "predict_from_xrd": [
        r"\bxrd\b", r"\bx-ray diffraction\b", r"\bpowder pattern\b",
        r"\bdiffraction pattern\b", r"\b\.xy\b", r"\bpxrd\b",
        r"\bagent.?xc\b",
    ],
    "predict_structure": [
        r"\bpredict\b.*\bstructure\b", r"\bcrystal\b.*\bpredict\b",
        r"\bgnn\b", r"\boptimiz\b", r"\bspace.?group\b",
        r"\blattice\b.*\bparam\b", r"\bagent.?pb\b",
        r"\bchemical.?formula\b", r"\bcomposition\b",
    ],
    "discover_rtsc": [
        r"\broom.?temp\b", r"\brtsc\b", r"\brt.?sc\b",
        r"\bambient.?pressure\b.*\bsc\b", r"\b273\s*k\b", r"\brtap\b",
        r"\broom.?temperature\b.*\bsuperconduct\b",
    ],
    "discover_material": [
        r"\bdiscover\b", r"\bsuperconduct\b", r"\bnovel\b.*\bmaterial\b",
        r"\bconvergence\b", r"\bfeedback.?loop\b", r"\bcs.*sin.*ob\b",
        r"\bmulti.?agent\b", r"\bnew\b.*\bcompound\b",
    ],
    "visualize": [
        r"\bvisuali[sz]\b", r"\bdashboard\b", r"\bcif\b.*\bgenerat\b",
        r"\b3d\b.*\bview\b", r"\bplot\b", r"\bimage\b.*\bstructure\b",
        r"\bexport\b.*\b(png|cif)\b", r"\bagent.?v\b",
    ],
    "benchmark": [
        r"\bbenchmark\b", r"\bcompar\b.*\bagent\b", r"\bevaluat\b",
        r"\bmetric\b", r"\bmatch.?rate\b", r"\brmsd\b",
    ],
}


class IntentRouter:
    """Classify user intent and build multi-step execution plans."""

    def classify_intent(self, request: dict) -> str:
        """Classify request into one of 6 intents.

        Args:
            request: Dict with optional keys: text, chemical_formula, xrd_path,
                     action, agent, dataset.

        Returns:
            Intent name string.
        """
        # Explicit agent or action override
        if request.get("action") == "discover_rtsc":
            return "discover_rtsc"
        if request.get("agent") == "agent_xc" or request.get("xrd_path"):
            return "predict_from_xrd"
        if request.get("agent") == "agent_pb" or request.get("chemical_formula"):
            return "predict_structure"
        if request.get("agent") == "agent_v":
            return "visualize"
        if request.get("action") == "benchmark" or request.get("dataset"):
            return "benchmark"
        if request.get("action") == "discover":
            return "discover_material"

        # Free-text classification via keyword matching
        text = " ".join(str(v) for v in request.values()).lower()
        for intent, patterns in INTENT_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    logger.debug(f"Matched intent '{intent}' via pattern '{pat}'")
                    return intent

        # Default
        logger.info("No intent matched — defaulting to predict_structure")
        return "predict_structure"

    def build_plan(self, request: dict) -> ExecutionPlan:
        """Build execution plan from request.

        Args:
            request: Dict with user parameters (formula, xrd_path, etc.).

        Returns:
            ExecutionPlan with ordered steps.
        """
        intent = self.classify_intent(request)
        builder = getattr(self, f"_plan_{intent}", None)
        if builder is None:
            logger.error(f"No plan builder for intent: {intent}")
            return ExecutionPlan(intent=intent, metadata={"error": "no builder"})

        plan = builder(request)
        logger.info(f"Built plan: {intent} with {plan.n_steps} steps "
                     f"involving {plan.agents_involved}")
        return plan

    # --- Plan builders per intent ---

    def _plan_predict_structure(self, request: dict) -> ExecutionPlan:
        formula = request.get("chemical_formula", request.get("formula", ""))
        sg_range = request.get("space_group_range", (1, 230))
        algorithm = request.get("algorithm", "hybrid")
        top_k = request.get("top_k", 10)

        steps = [
            ExecutionStep(
                agent="agent_pb", action="predict",
                params={"formula": formula, "space_group_range": sg_range,
                        "algorithm": algorithm, "top_k": top_k},
            ),
        ]

        # Optionally add visualization
        if request.get("visualize", False):
            steps.append(ExecutionStep(
                agent="agent_v", action="export_cif",
                params={"source": "agent_pb"},
                depends_on=[0],
            ))

        return ExecutionPlan(
            intent="predict_structure", steps=steps,
            metadata={"formula": formula},
        )

    def _plan_predict_from_xrd(self, request: dict) -> ExecutionPlan:
        xrd_path = request.get("xrd_path", "")
        composition = request.get("composition_hint", "")
        num_candidates = request.get("num_candidates", 10)

        steps = [
            ExecutionStep(
                agent="agent_xc", action="predict",
                params={"xrd_path": xrd_path, "composition_hint": composition,
                        "num_candidates": num_candidates},
            ),
        ]

        if request.get("visualize", False):
            steps.append(ExecutionStep(
                agent="agent_v", action="export_cif",
                params={"source": "agent_xc"},
                depends_on=[0],
            ))

        return ExecutionPlan(
            intent="predict_from_xrd", steps=steps,
            metadata={"xrd_path": str(xrd_path)},
        )

    def _plan_discover_material(self, request: dict) -> ExecutionPlan:
        max_iterations = request.get("max_iterations", 20)
        target = request.get("convergence_target", 0.95)

        steps = [
            ExecutionStep(
                agent="orchestrator", action="run_convergence_loop",
                params={"max_iterations": max_iterations, "target": target},
            ),
            ExecutionStep(
                agent="agent_v", action="update_dashboard",
                params={},
                depends_on=[0],
            ),
        ]

        return ExecutionPlan(
            intent="discover_material", steps=steps,
            metadata={"max_iterations": max_iterations, "target": target},
        )

    def _plan_discover_rtsc(self, request: dict) -> ExecutionPlan:
        max_iterations = request.get("max_iterations", 50)
        target = request.get("convergence_target", 0.85)

        steps = [
            ExecutionStep(
                agent="orchestrator", action="run_rtap_loop",
                params={"max_iterations": max_iterations, "target": target},
            ),
            ExecutionStep(
                agent="agent_v", action="update_dashboard",
                params={"mode": "rtap"},
                depends_on=[0],
            ),
        ]

        return ExecutionPlan(
            intent="discover_rtsc", steps=steps,
            metadata={"max_iterations": max_iterations, "target": target, "mode": "rtap"},
        )

    def _plan_visualize(self, request: dict) -> ExecutionPlan:
        viz_type = request.get("viz_type", "dashboard")
        source = request.get("source", "")
        cif_path = request.get("cif_path", "")

        if viz_type == "cif_generate":
            steps = [ExecutionStep(
                agent="agent_v", action="generate_cif",
                params={"source": source},
            )]
        elif viz_type == "structure_view":
            steps = [ExecutionStep(
                agent="agent_v", action="view_structure",
                params={"cif_path": cif_path},
            )]
        else:
            steps = [ExecutionStep(
                agent="agent_v", action="launch_dashboard",
                params={"port": request.get("port", 8050)},
            )]

        return ExecutionPlan(
            intent="visualize", steps=steps,
            metadata={"viz_type": viz_type},
        )

    def _plan_benchmark(self, request: dict) -> ExecutionPlan:
        dataset = request.get("dataset", "supercon_24")
        agents = request.get("agents", ["crystal_agent", "agent_pb", "agent_xc"])

        steps = [
            ExecutionStep(
                agent="benchmarks", action="compare",
                params={"dataset": dataset, "agents": agents},
            ),
        ]

        return ExecutionPlan(
            intent="benchmark", steps=steps,
            metadata={"dataset": dataset, "agents": agents},
        )
