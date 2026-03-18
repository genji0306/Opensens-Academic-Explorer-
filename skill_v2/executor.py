"""Plan executor — dispatches execution steps to agent run functions."""
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from skill_v2.schemas import ExecutionPlan, ExecutionResult, StepResult

logger = logging.getLogger("Skill.Executor")


class PlanExecutor:
    """Execute an ExecutionPlan by dispatching steps to agent entry points."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute all steps in order, respecting dependencies.

        Args:
            plan: The ExecutionPlan to execute.

        Returns:
            ExecutionResult with per-step results.
        """
        result = ExecutionResult(plan=plan)

        for i, step in enumerate(plan.steps):
            # Check dependencies
            for dep_idx in step.depends_on:
                if dep_idx < len(result.step_results):
                    dep_result = result.step_results[dep_idx]
                    if not dep_result.success:
                        logger.warning(
                            f"Skipping step {i} ({step.agent}.{step.action}) — "
                            f"dependency step {dep_idx} failed")
                        result.step_results.append(StepResult(
                            step_index=i, agent=step.agent, action=step.action,
                            success=False,
                            error=f"Dependency step {dep_idx} failed",
                        ))
                        continue

            step_result = self._execute_step(i, step)
            result.step_results.append(step_result)

        result.completed_at = datetime.now().isoformat()
        return result

    def _execute_step(self, index: int, step) -> StepResult:
        """Execute a single step."""
        logger.info(f"Step {index}: {step.agent}.{step.action} "
                     f"params={step.params}")

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would execute {step.agent}.{step.action}")
            return StepResult(
                step_index=index, agent=step.agent, action=step.action,
                success=True, details={"dry_run": True},
            )

        start = time.time()
        try:
            output_path = self._dispatch(step.agent, step.action, step.params)
            elapsed = round(time.time() - start, 2)
            return StepResult(
                step_index=index, agent=step.agent, action=step.action,
                success=True, output_path=output_path,
                wall_time_seconds=elapsed,
            )
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error(f"Step {index} failed: {e}")
            return StepResult(
                step_index=index, agent=step.agent, action=step.action,
                success=False, error=str(e),
                wall_time_seconds=elapsed,
            )

    def _dispatch(self, agent: str, action: str, params: dict) -> Optional[Path]:
        """Dispatch to the appropriate agent entry point.

        Returns:
            Output path if applicable.
        """
        if agent == "agent_pb" and action == "predict":
            return self._run_agent_pb(params)
        elif agent == "agent_xc" and action == "predict":
            return self._run_agent_xc(params)
        elif agent == "agent_v":
            return self._run_agent_v(action, params)
        elif agent == "orchestrator":
            return self._run_orchestrator(params)
        elif agent == "benchmarks":
            return self._run_benchmarks(params)
        else:
            raise ValueError(f"Unknown dispatch target: {agent}.{action}")

    def _run_agent_pb(self, params: dict) -> Path:
        from agent_pb.predict import run_agent_pb
        return run_agent_pb(
            formula=params.get("formula", ""),
            space_group_range=params.get("space_group_range"),
            algorithm=params.get("algorithm", "hybrid"),
            top_k=params.get("top_k", 10),
        )

    def _run_agent_xc(self, params: dict) -> Path:
        from agent_xc.predict import run_agent_xc
        return run_agent_xc(
            xrd_path=params.get("xrd_path", ""),
            composition_hint=params.get("composition_hint"),
            num_candidates=params.get("num_candidates", 10),
        )

    def _run_agent_v(self, action: str, params: dict) -> Optional[Path]:
        if action == "launch_dashboard":
            from agent_v.dashboard import AgentVDashboard
            dash = AgentVDashboard()
            port = params.get("port", 8050)
            logger.info(f"Launching Agent V dashboard on port {port}")
            dash.run(port=port)
            return None
        elif action == "generate_cif":
            from agent_v.cif.generator import CIFGenerator
            gen = CIFGenerator()
            logger.info("CIF generator ready")
            return None
        elif action == "view_structure":
            from agent_v.viewers.structure_viewer import StructureViewer
            viewer = StructureViewer()
            cif_path = params.get("cif_path", "")
            if cif_path:
                html = viewer.view_from_cif(Path(cif_path))
                logger.info(f"Generated structure view ({len(html)} chars)")
            return None
        elif action in ("export_cif", "update_dashboard"):
            logger.info(f"Agent V action '{action}' — no-op in batch mode")
            return None
        else:
            raise ValueError(f"Unknown Agent V action: {action}")

    def _run_orchestrator(self, params: dict) -> Optional[Path]:
        from src.orchestrator import main as orchestrator_main
        import sys
        max_iter = params.get("max_iterations", 20)
        target = params.get("target", 0.95)
        sys.argv = ["run.py",
                     "--max-iterations", str(max_iter),
                     "--target", str(target)]
        orchestrator_main()
        return None

    def _run_benchmarks(self, params: dict) -> Optional[Path]:
        from benchmarks.compare_agents import AgentBenchmark
        bm = AgentBenchmark(
            dataset=params.get("dataset", "supercon_24"),
            agents=params.get("agents", ["crystal_agent", "agent_pb", "agent_xc"]),
        )
        results = bm.run()
        path = bm.save_results(results)
        return path
