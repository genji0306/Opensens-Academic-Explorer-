"""Orchestrator for the A -> B -> Ob -> (refine | C) convergence loop.

Mirrors the OAE CS -> Sin -> Ob pattern but over Riemann zeros.

Loop invariants
---------------
* Each iteration produces an immutable (rule, prediction, report) triple.
* Refinement is monotone in capacity: correction-term count only grows,
  spline-knot count only grows, offset `a` refit when Ob asks for it.
* A best-so-far snapshot is kept so convergence can only move forward.
* The loop runs until `score >= target_score` or until `max_iterations`
  or `patience` (no-improvement budget) is exhausted.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from .agent_a.extractor import AgentA, _OFFSET_A_KEY
from .agent_b.predictor import AgentB
from .agent_c.synthesizer import AgentC
from .agent_ob.scorer import AgentOb
from .core.config import LoopConfig, ensure_dirs
from .core.lmfdb_loader import load
from .core.schemas import (
    ConvergenceReport,
    FunctionalPrinciple,
    ZeroDataset,
    ZeroPrediction,
    ZeroRule,
)
from .math_review import run_math_review


@dataclass
class LoopState:
    cfg: LoopConfig
    dataset: ZeroDataset
    n_terms: int
    n_knots: int
    rule: ZeroRule | None = None
    best_score: float = -1.0
    best_iteration: int = -1
    best_rule: ZeroRule | None = None
    best_report: ConvergenceReport | None = None
    history: list[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = []


def _emit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, default=_json_default) + "\n")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not JSON serialisable: {type(obj)}")


def _bump_capacity(state: LoopState, suggestion: dict[str, Any]) -> tuple[int, int]:
    """Capacity schedule: terms grow +1 per refine, knots grow geometrically
    toward the dataset size (so we can resolve the S(gamma) fluctuations).
    """
    n_terms = state.n_terms
    n_knots = state.n_knots
    knots_cap = state.dataset.size
    if suggestion.get("add_correction_term"):
        n_terms = min(n_terms + 1, 16)
    if suggestion.get("add_spline_knots"):
        # suggestion-driven linear bump
        n_knots = min(n_knots + int(suggestion["add_spline_knots"]) * 4, knots_cap)
    # geometric growth: at least +25% per iter below target
    n_knots = min(max(n_knots, int(state.n_knots * 1.5) + 8), knots_cap)
    return n_terms, n_knots


def _damped_rule(prev: ZeroRule | None, new: ZeroRule, damping: float) -> ZeroRule:
    """Blend new parameters toward the previous ones to avoid oscillation.

    Only applies once `prev` has coefficients of the same length; spline
    knots are always the new ones (they can change in size).
    """
    if prev is None or prev.correction_coeffs.shape != new.correction_coeffs.shape:
        return new
    alpha = 1.0 - damping
    blended = alpha * new.correction_coeffs + damping * prev.correction_coeffs
    return replace(new, correction_coeffs=blended)


def run(cfg: LoopConfig, verbose: bool = True) -> dict[str, Any]:
    ensure_dirs()
    # Reset logs for this run.
    for p in (cfg.flow_log, cfg.convergence_log):
        if p.exists():
            p.unlink()

    dataset = load(cfg.n_zeros)
    state = LoopState(
        cfg=cfg,
        dataset=dataset,
        n_terms=cfg.n_correction_terms,
        n_knots=cfg.residual_spline_knots,
    )
    agent_a, agent_b, agent_ob, agent_c = AgentA(), AgentB(), AgentOb(), AgentC()
    _emit(cfg.flow_log, {"event": "loop_start", "n_zeros": cfg.n_zeros,
                          "target": cfg.target_score, "max_iter": cfg.max_iterations})

    final_principle: FunctionalPrinciple | None = None
    no_improve = 0
    t0 = time.time()

    for it in range(1, cfg.max_iterations + 1):
        # Agent A -- fit / refine rule.
        new_rule = agent_a.run(
            dataset=dataset,
            prev_rule=state.rule,
            n_correction_terms=state.n_terms,
            spline_knots=state.n_knots,
        )
        rule = _damped_rule(state.rule, new_rule, cfg.damping)
        _emit(cfg.flow_log, {"event": "agent_a", "iteration": it,
                              "n_terms": state.n_terms, "n_knots": state.n_knots,
                              "fit_rms": rule.residual_rms_at_fit})

        # Agent B -- synthesise predicted zeros.
        pred: ZeroPrediction = agent_b.run(rule, dataset.n, rule_version=it)
        _emit(cfg.flow_log, {"event": "agent_b", "iteration": it,
                              "n_predicted": pred.size})

        # Agent Ob -- score.
        report: ConvergenceReport = agent_ob.run(dataset, pred, cfg, iteration=it)
        _emit(cfg.convergence_log, report.to_summary())
        _emit(cfg.flow_log, {"event": "agent_ob", "iteration": it,
                              **report.to_summary()})

        if verbose:
            c = report.components
            print(
                f"iter {it:>3}  score={report.score:.4f}  "
                f"match={c.match_rate:.4f}  rmse={c.rmse:.3e}  "
                f"rel_med={c.rel_error_median:.3e}  spacing={c.spacing_fit:.3f}  "
                f"[terms={state.n_terms} knots={state.n_knots}]"
            )

        # Track best.
        if report.score > state.best_score + 1e-6:
            state.best_score = report.score
            state.best_iteration = it
            state.best_rule = rule
            state.best_report = report
            no_improve = 0
        else:
            no_improve += 1

        state.rule = rule
        state.history.append({"iteration": it, **report.to_summary()})

        # Converged?
        if report.score >= cfg.target_score:
            _emit(cfg.flow_log, {"event": "converged", "iteration": it,
                                  "score": report.score})
            final_principle = agent_c.run(rule, dataset, report)
            break

        # Apply Ob's suggestion for next iteration.
        new_terms, new_knots = _bump_capacity(state, report.suggestion)
        state.n_terms, state.n_knots = new_terms, new_knots

        if no_improve >= cfg.patience:
            _emit(cfg.flow_log, {"event": "patience_exhausted", "iteration": it})
            if verbose:
                print(f"patience exhausted at iter {it} (no improvement)")
            break

    elapsed = time.time() - t0
    summary: dict[str, Any] = {
        "n_zeros": cfg.n_zeros,
        "target_score": cfg.target_score,
        "iterations_run": len(state.history),
        "best_iteration": state.best_iteration,
        "best_score": state.best_score,
        "converged": final_principle is not None,
        "elapsed_seconds": elapsed,
        "history": state.history,
    }
    if state.best_report is not None:
        summary["best_report"] = state.best_report.to_summary()
    if final_principle is not None:
        summary["principle"] = {
            "name": final_principle.name,
            "description": final_principle.description,
            "parameters_n_coeffs": len(final_principle.parameters["correction_coeffs"]),
            "parameters_offset_a": final_principle.parameters["offset_a"],
            "validation_rmse": final_principle.validation_rmse,
            "validation_match_rate": final_principle.validation_match_rate,
            "notes": final_principle.notes,
        }
        # Persist generated Python source so the user can reuse it.
        principle_py = cfg.final_report.with_name("principle.py")
        principle_py.write_text(final_principle.python_callable_src)
        summary["principle_source_path"] = str(principle_py)
        try:
            summary["math_review"] = run_math_review(
                summary=summary,
                source_report=cfg.final_report,
                output_dir=cfg.final_report.parent,
            )
        except Exception as exc:
            summary["math_review_error"] = str(exc)

    cfg.final_report.parent.mkdir(parents=True, exist_ok=True)
    cfg.final_report.write_text(json.dumps(summary, default=_json_default, indent=2))
    _emit(cfg.flow_log, {"event": "loop_end", "elapsed": elapsed,
                          "converged": final_principle is not None})
    return summary
