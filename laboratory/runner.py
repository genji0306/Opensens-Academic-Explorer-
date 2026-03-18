"""
OAE Laboratory Runner — Protocol execution engine.

Executes protocol stages sequentially, with checkpointing and resume support.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from laboratory.protocol import LabProtocol, ProtocolStage, CheckpointData

logger = logging.getLogger("Laboratory.Runner")

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "data" / "laboratory"


# Agent action dispatch table
_AGENT_ACTIONS = {}


def _dispatch_agent(agent: str, action: str, params: dict) -> dict:
    """Dispatch to the appropriate agent function.

    Returns a result dict with at least {"status": "ok"|"skipped"|"error"}.
    """
    try:
        if agent == "agent_cs" and action == "build_catalog":
            from src.agents.agent_cs import run_agent_cs
            iteration = params.get("iteration", 0)
            path = run_agent_cs(iteration)
            return {"status": "ok", "catalog_path": str(path)}

        elif agent == "agent_sin" and action == "generate_structures":
            from src.agents.agent_sin import run_agent_sin
            iteration = params.get("iteration", 0)
            pressure = params.get("target_pressure_GPa", 0.0)
            path = run_agent_sin(iteration, target_pressure_GPa=pressure)
            return {"status": "ok", "synth_dir": str(path)}

        elif agent == "agent_ob" and action == "score":
            from src.agents.agent_ob import run_agent_ob
            iteration = params.get("iteration", 0)
            mode = params.get("mode", "standard")
            score, path = run_agent_ob(iteration, mode=mode)
            return {"status": "ok", "score": score, "report_path": str(path)}

        elif agent == "agent_pb" and action == "predict":
            from agent_pb.predict import AgentPB
            pb = AgentPB()
            formula = params.get("formula", "")
            results = pb.predict(formula,
                                 algorithm=params.get("algorithm", "hybrid"),
                                 top_k=params.get("top_k", 5))
            return {"status": "ok", "n_candidates": len(results)}

        elif agent == "agent_v" and action == "render":
            return {"status": "ok", "note": "Visualization available via dashboard"}

        elif agent == "nemad" and action == "load_data":
            from src.core.nemad_adapter import NemadAdapter
            adapter = NemadAdapter()
            counts = adapter.count()
            return {"status": "ok", "counts": counts}

        elif agent == "nemad" and action == "compare":
            from benchmarks.nemad_comparison import run_comparison
            max_compounds = params.get("max_compounds", 20)
            report = run_comparison(max_compounds=max_compounds)
            return {"status": "ok", "summary": report.get("summary", {})}

        elif agent == "agent_cb" and action == "build_structures":
            from src.agents.agent_cb import run_agent_cb
            path = run_agent_cb()
            return {"status": "ok", "structures_dir": str(path)}

        elif agent == "agent_p" and action == "pressure_scan":
            from src.agents.agent_p import run_agent_p
            target_p = params.get("target_pressure_GPa", 0.0)
            results = run_agent_p(target_pressure_GPa=target_p)
            return {"status": "ok", "n_scanned": results.get("n_scanned", 0),
                    "target_pressure_GPa": target_p}

        elif agent == "agent_xc" and action == "predict":
            from agent_xc.predict import AgentXC
            xc = AgentXC()
            xrd_path = params.get("xrd_path", "")
            if not xrd_path:
                return {"status": "skipped", "reason": "No xrd_path in params"}
            from pathlib import Path as _Path
            result = xc.predict(_Path(xrd_path),
                                composition_hint=params.get("composition_hint"),
                                num_candidates=params.get("num_candidates", 10))
            return {"status": "ok", "n_predictions": len(result.predictions)}

        elif agent == "agent_gcd" and action == "extrapolate":
            return {"status": "ok", "note": "GCD extrapolation runs within orchestrator"}

        else:
            logger.warning(f"Unknown agent/action: {agent}/{action}")
            return {"status": "skipped", "reason": f"Unknown: {agent}/{action}"}

    except Exception as e:
        logger.error(f"Agent {agent}/{action} failed: {e}")
        return {"status": "error", "error": str(e)}


class LabRunner:
    """Execute laboratory protocols with checkpointing."""

    def __init__(self):
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    def execute(self, protocol: LabProtocol, params: Optional[dict] = None,
                start_stage: int = 0) -> dict:
        """Execute a protocol from a given stage.

        Args:
            protocol: The LabProtocol to execute.
            params: Override params (merged with protocol defaults).
            start_stage: Stage index to start from (for resume).

        Returns:
            Dict with execution results.
        """
        merged_params = {**protocol.default_params, **(params or {})}
        results: list[dict] = []
        t_start = time.time()

        logger.info(f"Executing protocol: {protocol.name} ({protocol.protocol_id})")
        logger.info(f"  Stages: {protocol.stage_names()}")
        logger.info(f"  Starting from stage {start_stage}")

        for i, stage in enumerate(protocol.stages):
            if i < start_stage:
                results.append({"stage": stage.name, "status": "skipped_resume"})
                continue

            logger.info(f"  [{i+1}/{len(protocol.stages)}] {stage.name}")
            stage_params = {**merged_params, **stage.params}

            result = _dispatch_agent(stage.agent, stage.action, stage_params)
            result["stage"] = stage.name
            result["elapsed_s"] = round(time.time() - t_start, 2)
            results.append(result)

            # Save checkpoint if requested
            if stage.checkpoint:
                self._save_checkpoint(protocol, i, results, merged_params)

            # Skip on error unless optional
            if result["status"] == "error" and not stage.optional:
                logger.error(f"  Stage {stage.name} failed — stopping protocol")
                break

        total_elapsed = round(time.time() - t_start, 2)

        # Collect output paths from stage results
        output_paths = []
        for r in results:
            for key in ("catalog_path", "synth_dir", "report_path",
                        "structures_dir", "results_path"):
                if key in r and r[key]:
                    output_paths.append(r[key])

        execution_result = {
            "protocol_id": protocol.protocol_id,
            "protocol_name": protocol.name,
            "total_stages": len(protocol.stages),
            "completed_stages": sum(1 for r in results if r["status"] == "ok"),
            "elapsed_s": total_elapsed,
            "results": results,
            "output_paths": output_paths,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Protocol complete: {execution_result['completed_stages']}"
                     f"/{len(protocol.stages)} stages in {total_elapsed:.1f}s")
        return execution_result

    def resume(self, checkpoint_path: Path) -> dict:
        """Resume execution from a checkpoint."""
        with open(checkpoint_path) as f:
            cp_data = json.load(f)

        protocol_id = cp_data["protocol_id"]
        stage_index = cp_data["stage_index"]
        params = cp_data.get("params", {})

        from laboratory.registry import get_protocol
        protocol = get_protocol(protocol_id)
        if protocol is None:
            raise ValueError(f"Protocol {protocol_id} not found")

        logger.info(f"Resuming {protocol_id} from stage {stage_index + 1}")
        return self.execute(protocol, params=params, start_stage=stage_index + 1)

    def _save_checkpoint(self, protocol: LabProtocol, stage_index: int,
                         results: list[dict], params: dict):
        """Save checkpoint to disk."""
        cp = CheckpointData(
            protocol_id=protocol.protocol_id,
            stage_index=stage_index,
            stage_name=protocol.stages[stage_index].name,
            results={"stage_results": results},
            params=params,
        )
        path = CHECKPOINT_DIR / f"checkpoint_{protocol.protocol_id}_{stage_index}.json"
        with open(path, "w") as f:
            json.dump(cp.to_dict(), f, indent=2, default=str)
        logger.info(f"  Checkpoint saved: {path.name}")
