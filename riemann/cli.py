"""CLI entrypoint for the Riemann discovery and review workflow."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.config import LoopConfig
from .math_review import run_math_review
from .orchestrator import run

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "data" / "riemann" / "reports" / "final_report.json"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="riemann",
        description="Multi-agent discovery of Riemann zeta non-trivial zeros.",
    )
    p.add_argument("--n-zeros", type=int, default=10_000,
                   help="Number of zeros to fit against (default 10000).")
    p.add_argument("--target", type=float, default=0.95,
                   help="Ob composite score target (default 0.95).")
    p.add_argument("--max-iterations", type=int, default=200,
                   help="Maximum A->B->Ob iterations (default 200).")
    p.add_argument("--patience", type=int, default=40,
                   help="Stop if no improvement for this many iterations.")
    p.add_argument("--damping", type=float, default=0.35,
                   help="Damping for coefficient updates (default 0.35).")
    p.add_argument("--initial-terms", type=int, default=3,
                   help="Initial parametric correction terms.")
    p.add_argument("--initial-knots", type=int, default=24,
                   help="Initial spline knots for residual.")
    p.add_argument("--run-until-converged", action="store_true",
                   help="Ignore --max-iterations and loop until score >= target.")
    p.add_argument("--review-only", action="store_true",
                   help="Skip the loop and only run the analysis/debate review on a report.")
    p.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Report path used with --review-only (default data/riemann/reports/final_report.json).",
    )
    p.add_argument("--holdout-zeros", type=int, default=200,
                   help="Holdout slice size for the review agents.")
    p.add_argument(
        "--visualize",
        action="store_true",
        help="Render a self-contained HTML dashboard for the saved result.",
    )
    p.add_argument(
        "--visualization-output",
        type=Path,
        default=None,
        help="Optional output path for the visualization HTML.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def _print_summary(summary: dict, cfg: LoopConfig | None = None) -> None:
    if cfg is not None:
        print()
        print("=" * 60)
        print(f"  Riemann zero discovery -- {cfg.n_zeros} zeros")
        print("=" * 60)
        print(f"  iterations_run    : {summary['iterations_run']}")
        print(f"  best_iteration    : {summary['best_iteration']}")
        print(f"  best_score        : {summary['best_score']:.6f}")
        print(f"  converged         : {summary['converged']}")
        print(f"  elapsed_seconds   : {summary['elapsed_seconds']:.2f}")
        if summary["converged"]:
            p = summary["principle"]
            print(f"  principle         : {p['name']}")
            print(f"    validation RMSE : {p['validation_rmse']:.4e}")
            print(f"    match_rate      : {p['validation_match_rate']:.4f}")
            print(f"    source saved to : {summary['principle_source_path']}")
    else:
        print()
        print("=" * 60)
        print("  Riemann review")
        print("=" * 60)

    review = summary.get("math_review")
    if review:
        analysis = review["analysis"]
        debate = review["debate"]
        print(f"  math analysis     : {analysis['conclusion']}")
        print(f"    holdout RMSE    : {analysis['holdout_rmse']:.4e}")
        print(f"    index hit rate  : {analysis['holdout_nearest_index_hit_rate']:.1%}")
        print(f"    saved to        : {review['analysis_path']}")
        print(f"  math debate       : {debate['verdict']}")
        print(f"    saved to        : {review['debate_path']}")
    elif "math_review_error" in summary:
        print(f"  math review error : {summary['math_review_error']}")

    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    visualization_report_path: Path | None = None

    if args.review_only:
        summary = json.loads(args.report.read_text())
        summary["math_review"] = run_math_review(
            summary=summary,
            source_report=args.report,
            output_dir=args.report.parent,
            holdout_zeros=args.holdout_zeros,
        )
        _print_summary(summary, cfg=None)
        visualization_report_path = args.report
        if args.visualize:
            from .visualization import write_dashboard

            viz_path = write_dashboard(
                report_path=visualization_report_path,
                output_path=args.visualization_output,
            )
            print(f"  visualization   : {viz_path}")
        return 0

    max_iter = args.max_iterations
    if args.run_until_converged:
        max_iter = 10_000
    cfg = LoopConfig(
        n_zeros=args.n_zeros,
        target_score=args.target,
        max_iterations=max_iter,
        damping=args.damping,
        patience=args.patience,
        n_correction_terms=args.initial_terms,
        residual_spline_knots=args.initial_knots,
        run_until_converged=args.run_until_converged,
    )
    summary = run(cfg, verbose=args.verbose)

    # When the loop converges, the orchestrator now persists a review bundle;
    # if that failed for any reason, we can still generate one here.
    if summary.get("converged") and "math_review" not in summary and "math_review_error" not in summary:
        summary["math_review"] = run_math_review(
            summary=summary,
            source_report=cfg.final_report,
            output_dir=cfg.final_report.parent,
            holdout_zeros=args.holdout_zeros,
        )

    _print_summary(summary, cfg=cfg)
    visualization_report_path = cfg.final_report
    if args.visualize:
        from .visualization import write_dashboard

        viz_path = write_dashboard(
            report_path=visualization_report_path,
            output_path=args.visualization_output,
        )
        print(f"  visualization   : {viz_path}")
    return 0 if summary["converged"] else 1
