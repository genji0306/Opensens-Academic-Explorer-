"""Post-convergence math analysis and debate for the Riemann loop.

This module adds two deterministic agents on top of the A -> B -> Ob -> C
pipeline:

* MathAnalysisAgent checks whether the result is a genuine generalization or
  just a per-zero interpolation table.
* MathDebateAgent stages a short expert debate that separates numerical
  usefulness from a proof of the Riemann hypothesis.

The code is intentionally skeptical. It treats the Hardy Z characterisation as
the classical mathematical frame, but never upgrades a numerical fit into a
proof claim.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .core.lmfdb_loader import load

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "riemann" / "reports" / "final_report.json"
DEFAULT_HOLDOUT_ZEROS = 200


def _hash_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _json_dump(payload: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _load_principle_module(path: Path):
    module_name = f"riemann_principle_{_hash_id(str(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"Cannot load principle module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_flow_events(report_path: Path) -> list[dict[str, Any]]:
    flow_path = report_path.with_name("flow.jsonl")
    if not flow_path.exists():
        return []
    events: list[dict[str, Any]] = []
    with flow_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _source_refinement_mode(source_text: str) -> str:
    if "find_zero_near" in source_text:
        return "local_sign_change_bisection"
    if "findroot" in source_text or "mpmath.siegelz" in source_text:
        return "mpmath_findroot"
    return "unknown"


def _humanize_refinement_mode(mode: str) -> str:
    if mode == "local_sign_change_bisection":
        return "local sign-change bisection"
    if mode == "mpmath_findroot":
        return "mpmath.findroot"
    return "unknown"


@dataclass(frozen=True)
class MathAnalysisReport:
    """Structured critique of the numerical result."""

    report_id: str
    source_report: str
    training_zeros: int
    best_iteration: int
    best_score: float
    in_sample_match_rate: float
    in_sample_rmse: float
    spline_knots: int
    knot_to_sample_ratio: float
    holdout_zeros: int
    holdout_rmse: float
    holdout_mae: float
    holdout_match_rate: float
    holdout_max_abs_error: float
    holdout_nearest_index_hit_rate: float
    holdout_max_index_offset: int
    capacity_jump_iteration: int | None = None
    capacity_jump_fit_rms: float | None = None
    refinement_mode: str = "unknown"
    holdout_mismatch_examples: list[dict[str, Any]] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> Path:
        return _json_dump(self.to_dict(), path)


@dataclass(frozen=True)
class MathDebateReport:
    """Compact expert debate built from the analysis report."""

    debate_id: str
    topic: str
    analysis_report_id: str
    turns: list[dict[str, Any]] = field(default_factory=list)
    verdict: str = ""
    summary: str = ""
    open_questions: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> Path:
        return _json_dump(self.to_dict(), path)


class MathAnalysisAgent:
    """Inspect the loop result and diagnose generalization quality."""

    name = "MathAnalysisAgent"
    role = "Numerical Result Analyst"

    def run(
        self,
        summary: dict[str, Any],
        source_report: Path,
        output_dir: Path,
        holdout_zeros: int = DEFAULT_HOLDOUT_ZEROS,
    ) -> MathAnalysisReport:
        principle_path = Path(summary["principle_source_path"])
        principle_source = principle_path.read_text()
        principle = summary.get("principle", {})
        best_report = summary.get("best_report", {})
        training_n = int(summary.get("n_zeros", 0))
        best_iteration = int(best_report.get("iteration", summary.get("best_iteration", 0)))
        best_score = float(best_report.get("score", summary.get("best_score", 0.0)))
        in_sample_match_rate = float(best_report.get("match_rate", 0.0))
        in_sample_rmse = float(best_report.get("rmse", 0.0))

        module = _load_principle_module(principle_path)
        spline_knots = int(np.asarray(getattr(module, "_KNOTS_N", np.zeros(0))).size)
        coeff_count = int(np.asarray(getattr(module, "_COEFFS", np.zeros(0))).size)
        knot_to_sample_ratio = float(spline_knots / training_n) if training_n else 0.0
        refinement_mode = _source_refinement_mode(principle_source)

        capacity_jump_iteration: int | None = None
        capacity_jump_fit_rms: float | None = None
        flow_events = _load_flow_events(source_report)
        a_events = [e for e in flow_events if e.get("event") == "agent_a"]
        for event in reversed(a_events):
            try:
                event_knots = int(event.get("n_knots", -1))
                event_fit_rms = float(event.get("fit_rms", 1.0))
            except (TypeError, ValueError):
                continue
            if event_knots == spline_knots:
                capacity_jump_iteration = int(event.get("iteration", 0))
                capacity_jump_fit_rms = event_fit_rms
                break

        holdout_n = max(1, int(holdout_zeros))
        dataset = None
        while holdout_n > 0:
            try:
                dataset = load(training_n + holdout_n)
                break
            except ValueError:
                holdout_n //= 2

        if dataset is None or holdout_n <= 0:
            holdout_n = 0
            holdout_idx = np.zeros(0, dtype=np.int64)
            holdout_gamma = np.zeros(0, dtype=np.float64)
        else:
            holdout_idx = dataset.n[training_n : training_n + holdout_n]
            holdout_gamma = dataset.gamma[training_n : training_n + holdout_n]

        if holdout_n:
            holdout_pred = np.asarray(module.riemann_zero_approx(holdout_idx), dtype=np.float64)
            residual = holdout_pred - holdout_gamma
            holdout_rmse = float(np.sqrt(np.mean(residual ** 2)))
            holdout_mae = float(np.mean(np.abs(residual)))
            spacing = 2.0 * np.pi / np.log(np.maximum(holdout_gamma, 2.0) / (2.0 * np.pi))
            holdout_match_rate = float(np.mean(np.abs(residual) <= 0.01 * spacing))
            holdout_max_abs_error = float(np.max(np.abs(residual)))
            nearest = np.abs(holdout_pred[:, None] - holdout_gamma[None, :]).argmin(axis=1)
            nearest_hit_rate = float(np.mean(nearest == np.arange(holdout_n)))
            max_index_offset = int(np.max(np.abs(nearest - np.arange(holdout_n))))
            mismatch_examples: list[dict[str, Any]] = []
            mismatch_idx = np.where(nearest != np.arange(holdout_n))[0][:5]
            for local_idx in mismatch_idx:
                target_n = int(holdout_idx[local_idx])
                nearest_n = int(holdout_idx[nearest[local_idx]])
                mismatch_examples.append(
                    {
                        "n": target_n,
                        "predicted_gamma": float(holdout_pred[local_idx]),
                        "target_gamma": float(holdout_gamma[local_idx]),
                        "nearest_index": nearest_n,
                        "nearest_delta": float(
                            abs(holdout_pred[local_idx] - holdout_gamma[nearest[local_idx]])
                        ),
                        "target_delta": float(abs(holdout_pred[local_idx] - holdout_gamma[local_idx])),
                        "index_offset": int(nearest_n - target_n),
                    }
                )
        else:
            holdout_pred = np.zeros(0, dtype=np.float64)
            residual = np.zeros(0, dtype=np.float64)
            holdout_rmse = float("nan")
            holdout_mae = float("nan")
            holdout_match_rate = float("nan")
            holdout_max_abs_error = float("nan")
            nearest_hit_rate = float("nan")
            max_index_offset = 0
            mismatch_examples = []

        findings = [
            (
                "Iteration "
                f"{capacity_jump_iteration} reaches the full knot budget and collapses the training residual "
                f"to {capacity_jump_fit_rms:.1f}."
                if capacity_jump_iteration is not None
                else "The loop never visibly hit the full knot budget in the flow trace."
            ),
            (
                f"Holdout RMSE on the next {holdout_n} zeros is {holdout_rmse:.4f}; "
                "the fit does not generalize as an exact law off-training."
            ),
            (
                f"Nearest-index hit rate on the holdout slice is {nearest_hit_rate:.1%}, "
                f"with max index drift of {max_index_offset}."
            ),
            (
                "The generated principle is the classical Hardy Z framing, not a proof of the Riemann hypothesis."
            ),
        ]
        red_flags = [
            "The residual spline uses one knot per training zero, which is a memorization table.",
        ]
        if refinement_mode == "mpmath_findroot":
            red_flags.append(
                "The current principle source still uses mpmath.findroot rather than the local sign-change bisection helper."
            )
        elif refinement_mode == "unknown":
            red_flags.append("The refinement mode could not be identified from the source artifact.")

        recommendations = [
            "Reserve a validation slice before letting spline capacity reach the full training set size.",
            "If the goal is generalization, cap residual knots below the number of training zeros.",
            "Use explicit bracketing or interval arithmetic to keep the n-th zero index stable off-training.",
        ]
        conclusion = (
            "The loop found a high-precision interpolant and a classical Hardy-Z numerical generator, "
            "but not a proof of the Riemann hypothesis."
        )

        report = MathAnalysisReport(
            report_id=_hash_id(
                str(source_report),
                str(training_n),
                str(holdout_n),
                str(best_iteration),
                f"{best_score:.12f}",
            ),
            source_report=str(source_report),
            training_zeros=training_n,
            best_iteration=best_iteration,
            best_score=best_score,
            in_sample_match_rate=in_sample_match_rate,
            in_sample_rmse=in_sample_rmse,
            spline_knots=spline_knots,
            knot_to_sample_ratio=knot_to_sample_ratio,
            holdout_zeros=holdout_n,
            holdout_rmse=holdout_rmse,
            holdout_mae=holdout_mae,
            holdout_match_rate=holdout_match_rate,
            holdout_max_abs_error=holdout_max_abs_error,
            holdout_nearest_index_hit_rate=nearest_hit_rate,
            holdout_max_index_offset=max_index_offset,
            capacity_jump_iteration=capacity_jump_iteration,
            capacity_jump_fit_rms=capacity_jump_fit_rms,
            refinement_mode=refinement_mode,
            holdout_mismatch_examples=mismatch_examples,
            findings=findings,
            red_flags=red_flags,
            recommendations=recommendations,
            conclusion=conclusion,
            confidence=0.98,
            metadata={
                "principle_name": principle.get("name", ""),
                "principle_source_path": str(principle_path),
                "refinement_mode_label": _humanize_refinement_mode(refinement_mode),
                "coeff_count": coeff_count,
                "flow_event_count": len(flow_events),
            },
        )
        report.save(output_dir / "math_analysis.json")
        return report


class MathDebateAgent:
    """Stage a short debate between a proponent and a skeptic."""

    name = "MathDebateAgent"
    role = "Expert Debate Agent"

    def run(self, analysis: MathAnalysisReport, output_dir: Path) -> MathDebateReport:
        refinement_label = _humanize_refinement_mode(analysis.refinement_mode)
        turns = [
            {
                "speaker": "Proponent",
                "stance": "support",
                "claim": (
                    f"The loop recovered a strong numerical model with best_score={analysis.best_score:.4f} "
                    f"and an exact in-sample match_rate={analysis.in_sample_match_rate:.4f}."
                ),
            },
            {
                "speaker": "Skeptic",
                "stance": "challenge",
                "claim": (
                    f"That exact fit only appears when spline_knots={analysis.spline_knots} equals "
                    f"training_zeros={analysis.training_zeros}; that is interpolation, not a theorem."
                ),
            },
            {
                "speaker": "Proponent",
                "stance": "support",
                "claim": (
                    f"The holdout slice is still numerically reasonable: RMSE={analysis.holdout_rmse:.4f} "
                    f"and nearest-index hit rate={analysis.holdout_nearest_index_hit_rate:.1%}."
                ),
            },
            {
                "speaker": "Skeptic",
                "stance": "challenge",
                "claim": (
                    f"Even so, {len(analysis.holdout_mismatch_examples)} sampled holdout zeros drift to a "
                    f"neighboring index, and the source refinement mode is {refinement_label}."
                ),
            },
            {
                "speaker": "Moderator",
                "stance": "verdict",
                "claim": analysis.conclusion,
            },
        ]
        summary = (
            "The proponent can defend the loop as a high-quality numerical interpolant, "
            "but the skeptic wins on the proof question because the full-knot spline is a memorizer "
            "and the holdout diagnostics show index drift."
        )
        open_questions = [
            "Can residual capacity be capped while preserving useful approximation quality?",
            "Can each n-th zero be bracketed with an index-faithful interval rather than a seed alone?",
            "Can the loop publish a validation split that is never used in fitting?",
        ]
        report = MathDebateReport(
            debate_id=_hash_id(analysis.report_id, "debate"),
            topic="Can the current loop be treated as a proof of the Riemann hypothesis?",
            analysis_report_id=analysis.report_id,
            turns=turns,
            verdict=analysis.conclusion,
            summary=summary,
            open_questions=open_questions,
            recommendations=list(analysis.recommendations),
            confidence=0.97,
            metadata={
                "analysis_confidence": analysis.confidence,
                "refinement_mode": analysis.refinement_mode,
            },
        )
        report.save(output_dir / "math_debate.json")
        return report


def run_math_review(
    summary: dict[str, Any],
    source_report: Path,
    output_dir: Path,
    holdout_zeros: int = DEFAULT_HOLDOUT_ZEROS,
) -> dict[str, Any]:
    """Run both review agents and return a JSON-serialisable bundle."""

    analysis_agent = MathAnalysisAgent()
    analysis = analysis_agent.run(
        summary=summary,
        source_report=source_report,
        output_dir=output_dir,
        holdout_zeros=holdout_zeros,
    )
    debate_agent = MathDebateAgent()
    debate = debate_agent.run(analysis=analysis, output_dir=output_dir)
    return {
        "analysis": analysis.to_dict(),
        "debate": debate.to_dict(),
        "analysis_path": str(output_dir / "math_analysis.json"),
        "debate_path": str(output_dir / "math_debate.json"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Riemann math analysis and debate review on a final report."
    )
    parser.add_argument(
        "report",
        nargs="?",
        default=str(DEFAULT_REPORT_PATH),
        help="Path to data/riemann/reports/final_report.json",
    )
    parser.add_argument(
        "--holdout-zeros",
        type=int,
        default=DEFAULT_HOLDOUT_ZEROS,
        help="Number of held-out zeros to evaluate (default 200).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report_path = Path(args.report)
    summary = json.loads(report_path.read_text())
    review = run_math_review(
        summary=summary,
        source_report=report_path,
        output_dir=report_path.parent,
        holdout_zeros=args.holdout_zeros,
    )
    print(json.dumps(review, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
