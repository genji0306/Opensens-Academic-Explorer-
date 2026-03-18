"""
Orchestrator — Multi-Agent Feedback Loop Controller
=====================================================
Manages the iterative cycle:
  1. Agent CS → build/update crystal pattern catalog
  2. Agent Sin → generate synthetic superconductor data
  3. Agent Ob → compare, score, and generate refinements
  4. Check convergence → loop or terminate

Can run in two modes:
  - Direct mode: runs all agents in-process (default)
  - Claude Code mode: spawns each agent as a separate Claude Code CLI session
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from src.core.config import (
    CONVERGENCE_TARGET,
    MAX_ITERATIONS,
    DEFAULT_TARGET_PRESSURE_GPA,
    PLATEAU_WINDOW,
    PLATEAU_THRESHOLD,
    REPORTS_DIR,
    REFINEMENTS_DIR,
    NOVEL_CANDIDATES_DIR,
    CRYSTAL_PATTERNS_DIR,
    ensure_dirs,
    # RTAP imports
    RTAP_CONVERGENCE_TARGET,
    RTAP_MAX_ITERATIONS,
    RTAP_DAMPING_FACTOR,
    RTAP_SCORE_WEIGHTS,
    RTAP_TC_THRESHOLD_K,
    RTAP_CANDIDATES_DIR,
    RTAP_REPORTS_DIR,
    ensure_dirs_rtap,
)
from src.agents.agent_cs import run_agent_cs
from src.agents.agent_sin import run_agent_sin
from src.agents.agent_ob import run_agent_ob

logger = logging.getLogger("Orchestrator")


def check_plateau(history: list[float], window: int = PLATEAU_WINDOW, threshold: float = PLATEAU_THRESHOLD) -> bool:
    """Detect if convergence has plateaued (< threshold change over window iterations)."""
    if len(history) < window:
        return False
    recent = history[-window:]
    max_delta = max(abs(recent[i + 1] - recent[i]) for i in range(len(recent) - 1))
    return max_delta < threshold


def generate_final_report(convergence_history: list[dict], reason: str):
    """Generate the final summary report when the loop terminates."""
    report_path = REPORTS_DIR / "final_report.json"

    # Collect novel candidates across all iterations
    novel_files = sorted(NOVEL_CANDIDATES_DIR.glob("candidates_iteration_*.csv"))
    total_novels = 0
    for f in novel_files:
        import pandas as pd
        df = pd.read_csv(f)
        total_novels += len(df)

    final = {
        "termination_reason": reason,
        "total_iterations": len(convergence_history),
        "final_convergence_score": convergence_history[-1]["score"] if convergence_history else 0,
        "convergence_history": convergence_history,
        "total_novel_candidates": total_novels,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with open(report_path, "w") as f:
        json.dump(final, f, indent=2)

    logger.info(f"Final report saved to {report_path}")
    return report_path


def run_loop(max_iterations: int = MAX_ITERATIONS, target: float = CONVERGENCE_TARGET,
             target_pressure_GPa: float = DEFAULT_TARGET_PRESSURE_GPA):
    """
    Main feedback loop.
    Iterates until convergence target is met, plateau detected, or max iterations reached.
    """
    ensure_dirs()

    # Clean stale pattern catalogs from previous runs to avoid version conflicts
    for old_catalog in CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"):
        old_catalog.unlink()

    convergence_history: list[dict] = []
    score_history: list[float] = []

    logger.info("=" * 70)
    logger.info("OAE — Starting feedback loop")
    logger.info(f"Target convergence: {target:.0%}")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info(f"Target pressure: {target_pressure_GPa} GPa")
    logger.info("=" * 70)

    for iteration in range(max_iterations):
        logger.info("")
        logger.info(f"{'='*70}")
        logger.info(f"ITERATION {iteration}")
        logger.info(f"{'='*70}")

        t_start = time.time()

        # --- Agent CS: Build/update crystal patterns ---
        logger.info("[Agent CS] Building crystal pattern catalog...")
        try:
            catalog_path = run_agent_cs(iteration)
            logger.info(f"[Agent CS] Catalog saved: {catalog_path}")
        except Exception as e:
            logger.error(f"[Agent CS] FAILED: {e}")
            raise

        # --- Agent Sin: Generate synthetic data ---
        logger.info("[Agent Sin] Generating synthetic structures...")
        try:
            synth_dir = run_agent_sin(iteration, target_pressure_GPa=target_pressure_GPa)
            logger.info(f"[Agent Sin] Output saved: {synth_dir}")
        except Exception as e:
            logger.error(f"[Agent Sin] FAILED: {e}")
            raise

        # --- Agent Ob: Compare and score ---
        logger.info("[Agent Ob] Comparing synthetic vs experimental data...")
        try:
            convergence_score, report_path = run_agent_ob(iteration)
            logger.info(f"[Agent Ob] Convergence score: {convergence_score:.4f}")
            logger.info(f"[Agent Ob] Report saved: {report_path}")
        except Exception as e:
            logger.error(f"[Agent Ob] FAILED: {e}")
            raise

        elapsed = time.time() - t_start

        # Record history
        convergence_history.append({
            "iteration": iteration,
            "score": convergence_score,
            "elapsed_seconds": round(elapsed, 2),
        })
        score_history.append(convergence_score)

        # --- Print iteration summary ---
        logger.info("")
        logger.info(f"  Iteration {iteration} complete in {elapsed:.1f}s")
        logger.info(f"  Convergence: {convergence_score:.4f} / {target:.4f}")
        if len(score_history) > 1:
            delta = score_history[-1] - score_history[-2]
            logger.info(f"  Delta from previous: {delta:+.4f}")

        # --- Check termination conditions ---

        # 1. Convergence reached
        if convergence_score >= target:
            logger.info("")
            logger.info(f"*** CONVERGED at iteration {iteration} with score {convergence_score:.4f} ***")
            report = generate_final_report(convergence_history, reason="convergence_reached")
            return convergence_score, report

        # 2. Plateau detected
        if check_plateau(score_history):
            logger.info("")
            logger.info(f"*** PLATEAU detected at iteration {iteration} (score ~{convergence_score:.4f}) ***")
            report = generate_final_report(convergence_history, reason="plateau_detected")
            return convergence_score, report

    # 3. Max iterations reached
    logger.info("")
    logger.info(f"*** MAX ITERATIONS ({max_iterations}) reached. Final score: {score_history[-1]:.4f} ***")
    report = generate_final_report(convergence_history, reason="max_iterations")
    return score_history[-1], report


def run_rtap_loop(max_iterations: int = RTAP_MAX_ITERATIONS,
                   target: float = RTAP_CONVERGENCE_TARGET):
    """
    RTAP Discovery Loop — Room-Temperature Ambient-Pressure superconductor search.

    Same CS → Sin → Ob core loop but with:
    - RTAP scoring weights (ambient Tc, stability, synthesizability)
    - GCD extrapolation every 5 iterations for compositional crossover
    - Agent CB structural feasibility for top candidates
    - Candidates above 273 K flagged to RTAP_CANDIDATES_DIR
    """
    ensure_dirs_rtap()

    # Clean stale catalogs
    for old_catalog in CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"):
        old_catalog.unlink()

    convergence_history: list[dict] = []
    score_history: list[float] = []
    rtap_candidates_total = 0

    logger.info("=" * 70)
    logger.info("RTAP DISCOVERY MODE — Room-Temperature Ambient-Pressure")
    logger.info(f"Target convergence: {target:.0%}")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info(f"Tc threshold: {RTAP_TC_THRESHOLD_K} K | Max pressure: 1.0 GPa")
    logger.info(f"Score weights: {RTAP_SCORE_WEIGHTS}")
    logger.info("=" * 70)

    for iteration in range(max_iterations):
        logger.info("")
        logger.info(f"{'='*70}")
        logger.info(f"RTAP ITERATION {iteration}")
        logger.info(f"{'='*70}")

        t_start = time.time()

        # --- Agent CS: Build/update crystal patterns (includes RTAP families) ---
        logger.info("[Agent CS] Building RTAP pattern catalog...")
        try:
            catalog_path = run_agent_cs(iteration)
            logger.info(f"[Agent CS] Catalog saved: {catalog_path}")
        except Exception as e:
            logger.error(f"[Agent CS] FAILED: {e}")
            raise

        # --- MC3D calibration (first iteration only) ---
        if iteration == 0:
            logger.info("[MC3D] Fetching reference structures for calibration...")
            try:
                from src.agents.agent_sin import AgentSin as _SinCls
                _sin_cal = _SinCls()
                mc3d_cal = _sin_cal.calibrate_from_mc3d()
                mc3d_refs = sum(
                    d.get("count", 0)
                    for d in mc3d_cal.get("families", {}).values()
                )
                logger.info(f"[MC3D] Calibrated with {mc3d_refs} reference structures")
            except Exception as e:
                logger.warning(f"[MC3D] Calibration skipped: {e}")

        # --- Agent Sin: Generate synthetic structures ---
        logger.info("[Agent Sin] Generating RTAP synthetic structures...")
        try:
            synth_dir = run_agent_sin(iteration, target_pressure_GPa=0.0)
            logger.info(f"[Agent Sin] Output saved: {synth_dir}")
        except Exception as e:
            logger.error(f"[Agent Sin] FAILED: {e}")
            raise

        # --- Agent Ob: RTAP scoring ---
        logger.info("[Agent Ob] RTAP discovery scoring...")
        try:
            convergence_score, report_path = run_agent_ob(iteration, mode="rtap")
            logger.info(f"[Agent Ob] RTAP score: {convergence_score:.4f}")
        except Exception as e:
            logger.error(f"[Agent Ob] FAILED: {e}")
            raise

        # --- GCD extrapolation every 5 iterations ---
        if iteration > 0 and iteration % 5 == 0:
            logger.info("[Agent GCD] Running RTAP compositional extrapolation...")
            try:
                from src.agents.agent_gcd import AgentGCD
                from src.core.schemas import load_pattern_catalog
                gcd = AgentGCD()
                patterns = load_pattern_catalog(catalog_path)
                gcd.load_candidates(synth_dir)
                rtap_extra = gcd.extrapolate_rtap_candidates(patterns)
                logger.info(f"[Agent GCD] Generated {len(rtap_extra)} extrapolated RTAP candidates")
            except Exception as e:
                logger.warning(f"[Agent GCD] Extrapolation skipped: {e}")

        # --- Flag RT candidates ---
        try:
            import pandas as pd
            synth_csv = sorted(Path(synth_dir).glob("synthetic_structures_*.csv"))
            if synth_csv:
                df = pd.read_csv(synth_csv[-1])
                if "ambient_pressure_Tc_K" in df.columns:
                    rt_hits = df[df["ambient_pressure_Tc_K"] >= RTAP_TC_THRESHOLD_K]
                elif "predicted_Tc_K" in df.columns:
                    rt_hits = df[df["predicted_Tc_K"] >= RTAP_TC_THRESHOLD_K]
                else:
                    rt_hits = pd.DataFrame()

                if len(rt_hits) > 0:
                    rt_path = RTAP_CANDIDATES_DIR / f"rt_candidates_iter_{iteration}.csv"
                    rt_hits.to_csv(rt_path, index=False)
                    rtap_candidates_total += len(rt_hits)
                    logger.info(f"  *** {len(rt_hits)} candidates above {RTAP_TC_THRESHOLD_K} K! ***")
        except Exception as e:
            logger.warning(f"  RT candidate flagging skipped: {e}")

        elapsed = time.time() - t_start

        convergence_history.append({
            "iteration": iteration,
            "score": convergence_score,
            "elapsed_seconds": round(elapsed, 2),
            "rtap_candidates_flagged": rtap_candidates_total,
        })
        score_history.append(convergence_score)

        logger.info(f"  Iteration {iteration} complete in {elapsed:.1f}s")
        logger.info(f"  RTAP score: {convergence_score:.4f} / {target:.4f}")
        logger.info(f"  Total RT candidates flagged: {rtap_candidates_total}")

        if len(score_history) > 1:
            delta = score_history[-1] - score_history[-2]
            logger.info(f"  Delta: {delta:+.4f}")

        # Convergence check
        if convergence_score >= target:
            logger.info(f"*** RTAP CONVERGED at iteration {iteration} ***")
            report = generate_final_report(convergence_history, reason="rtap_convergence_reached")
            return convergence_score, report

        # Plateau (use wider window for RTAP — 8 iterations)
        if check_plateau(score_history, window=8, threshold=PLATEAU_THRESHOLD):
            logger.info(f"*** RTAP PLATEAU at iteration {iteration} ***")
            report = generate_final_report(convergence_history, reason="rtap_plateau_detected")
            return convergence_score, report

    logger.info(f"*** RTAP MAX ITERATIONS ({max_iterations}). Final: {score_history[-1]:.4f} ***")
    report = generate_final_report(convergence_history, reason="rtap_max_iterations")
    return score_history[-1], report


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Opensens Academic Explorer (OAE) — Orchestrator"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=MAX_ITERATIONS,
        help=f"Maximum number of iterations (default: {MAX_ITERATIONS})"
    )
    parser.add_argument(
        "--target", type=float, default=CONVERGENCE_TARGET,
        help=f"Convergence target 0-1 (default: {CONVERGENCE_TARGET})"
    )
    parser.add_argument(
        "--pressure", type=float, default=DEFAULT_TARGET_PRESSURE_GPA,
        help=f"Target external pressure in GPa (default: {DEFAULT_TARGET_PRESSURE_GPA})"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    final_score, report_path = run_loop(
        max_iterations=args.max_iterations,
        target=args.target,
        target_pressure_GPa=args.pressure,
    )

    print(f"\nFinal convergence score: {final_score:.4f}")
    print(f"Report: {report_path}")

    return 0 if final_score >= args.target else 1


if __name__ == "__main__":
    sys.exit(main())
