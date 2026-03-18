#!/usr/bin/env python3
"""
Opensens Academic Explorer (OAE) — Launcher
============================================
Multi-agent crystal structure prediction and material discovery platform.
Runs the CS → Sin → Ob feedback loop for convergence-driven exploration.

Usage:
    python run.py                          # Default: 20 iterations, 95% target
    python run.py --max-iterations 5       # Quick test run
    python run.py --target 0.90 -v         # Lower target, verbose
    python run.py --v2                     # v2 mode: 99% target, rebalanced weights
    python run.py --rtap                   # RTAP discovery mode
"""
import sys
import os

# Ensure project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run():
    """Entry point with v2 and --rtap flag support."""
    if "--rtap" in sys.argv:
        sys.argv.remove("--rtap")
        from src.core import config
        config.ensure_dirs_rtap()
        print("=" * 60)
        print("  RTAP DISCOVERY MODE — Room-Temperature Ambient-Pressure")
        print(f"  Target: Tc >= {config.RTAP_TC_THRESHOLD_K} K at P <= {config.RTAP_MAX_PRESSURE_GPA} GPa")
        print(f"  Convergence target: {config.RTAP_CONVERGENCE_TARGET}")
        print(f"  Families: {len(config.RTAP_FAMILIES)} ({', '.join(config.RTAP_FAMILIES[:5])}...)")
        print("=" * 60)

        # Parse --max-iterations from remaining argv if present
        import argparse
        import logging
        parser = argparse.ArgumentParser()
        parser.add_argument("--max-iterations", type=int, default=config.RTAP_MAX_ITERATIONS)
        parser.add_argument("--target", type=float, default=config.RTAP_CONVERGENCE_TARGET)
        parser.add_argument("--verbose", "-v", action="store_true")
        args, _ = parser.parse_known_args()

        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        )

        from src.orchestrator import run_rtap_loop
        final_score, report_path = run_rtap_loop(
            max_iterations=args.max_iterations,
            target=args.target,
        )
        print(f"\nRTAP final score: {final_score:.4f}")
        print(f"\n  Result folders:")
        print(f"    {report_path}")
        print(f"    {config.DATA_DIR / 'novel_candidates'}")
        print(f"    {config.DATA_DIR / 'synthetic'}")
        print(f"    {config.DATA_DIR / 'crystal_structures'}")
        print(f"    {config.DATA_DIR / 'reports'}")
        return 0 if final_score >= args.target else 1

    if "--v2" in sys.argv:
        sys.argv.remove("--v2")
        from src.core import config
        config.CONVERGENCE_TARGET = config.V2_CONVERGENCE_TARGET
        config.SCORE_WEIGHTS = config.V2_SCORE_WEIGHTS
        config.ensure_dirs_v2()
        print("[v2] Convergence target: 0.99, rebalanced weights active")

    from src.orchestrator import main
    return main()


if __name__ == "__main__":
    sys.exit(run())
