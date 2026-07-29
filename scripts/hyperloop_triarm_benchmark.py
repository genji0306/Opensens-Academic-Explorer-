"""Gate 7 — tri-arm benchmark: baseline vs klein vs hyperloop on the same seed pack."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from riemann.research.config import RiemannResearchConfig  # noqa: E402
from riemann.research.lean_residue_writer import cleanup_campaign_residue  # noqa: E402
from riemann.research.meta_agent import MetaAgent  # noqa: E402
from riemann.research.orchestrator import run_campaign  # noqa: E402

ARMS = ("baseline", "klein", "hyperloop")
LEAN_RH_ROOT = PROJECT_ROOT / "lean" / "RH"
REPORT_PATH = PROJECT_ROOT / "data" / "riemann" / "research" / "gate7_triarm_report.json"


def _run_arm(mode: str) -> dict[str, object]:
    campaign_id = f"triarm_{mode}"
    cleanup_campaign_residue(LEAN_RH_ROOT, campaign_id)
    cfg = RiemannResearchConfig(
        campaign_id=campaign_id,
        max_rounds=2,
        max_hypotheses_per_round=2,
        proof_target=2.0,  # Force termination at max_rounds for fair comparison.
        topology_mode=mode,
    )
    summary = run_campaign(cfg, verbose=False)
    residue_log = summary.get("lean_residue_log", []) or []
    total_added = sum(len(entry.get("delta", {}).get("added", [])) for entry in residue_log)

    failure_counts = _extract_failure_counts(summary)
    persistent = sum(1 for v in failure_counts.values() if v >= 2)
    meta_total, meta_applies = _meta_metrics(
        campaign_id=campaign_id,
        lean_delta_count=total_added,
        persistent_obstruction_count=persistent,
        failure_counts=failure_counts,
        run_meta=(mode == "hyperloop"),
    )

    return {
        "topology_mode": mode,
        "campaign_id": campaign_id,
        "rounds_run": int(summary.get("rounds_run", 0) or 0),
        "best_score": float(summary.get("best_score", 0.0) or 0.0),
        "lean_residue_gate_failures": int(summary.get("lean_residue_gate_failures", 0) or 0),
        "total_lean_decls_added": int(total_added),
        "persistent_obstruction_count": int(persistent),
        "meta_theorem_count": int(meta_total),
        "meta_theorem_applies_count": int(meta_applies),
        "termination_reason": str(summary.get("termination_reason", "")),
    }


def _extract_failure_counts(summary: dict) -> dict[str, int]:
    failure_history = summary.get("failure_history") or []
    counts: dict[str, int] = {}
    for entry in failure_history:
        for key, value in (entry.get("failure_counts", {}) or {}).items():
            counts[key] = counts.get(key, 0) + int(value)
    return counts


def _meta_metrics(
    *,
    campaign_id: str,
    lean_delta_count: int,
    persistent_obstruction_count: int,
    failure_counts: dict[str, int],
    run_meta: bool,
) -> tuple[int, int]:
    if not run_meta:
        return (0, 0)
    agent = MetaAgent(LEAN_RH_ROOT)
    theorems = agent.run(
        campaign_id=campaign_id,
        lean_delta_count=lean_delta_count,
        persistent_obstruction_count=persistent_obstruction_count,
        failure_counts=failure_counts,
        canonical_signatures=(),
    )
    applies = sum(1 for t in theorems if t.applies)
    return (len(theorems), applies)


def _print_summary(report: dict) -> None:
    print()
    print("=" * 78)
    print("GATE 7 — TRI-ARM HYPERLOOP BENCHMARK")
    print("=" * 78)
    header = f"{'mode':<12}{'rounds':>7}{'best_score':>12}{'lean_added':>12}{'gate_fail':>11}{'meta_apply':>12}"
    print(header)
    print("-" * len(header))
    for arm in report["arms"]:
        print(
            f"{arm['topology_mode']:<12}"
            f"{arm['rounds_run']:>7}"
            f"{arm['best_score']:>12.4f}"
            f"{arm['total_lean_decls_added']:>12}"
            f"{arm['lean_residue_gate_failures']:>11}"
            f"{arm['meta_theorem_applies_count']:>12}"
        )
    print()
    print(f"Report written to: {report['report_path']}")


def _cleanup_all_arms() -> None:
    for mode in ARMS:
        cleanup_campaign_residue(LEAN_RH_ROOT, f"triarm_{mode}")


def main() -> int:
    # Ensure each arm starts from an identical residue baseline.
    _cleanup_all_arms()

    arms_results = []
    for mode in ARMS:
        print(f"[triarm] running arm: {mode}")
        try:
            arms_results.append(_run_arm(mode))
        except Exception as exc:  # pragma: no cover - benchmark is best-effort
            arms_results.append({"topology_mode": mode, "error": repr(exc)})
        # Strip this arm's residue so the next arm begins with the same baseline state.
        cleanup_campaign_residue(LEAN_RH_ROOT, f"triarm_{mode}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "report_path": str(REPORT_PATH),
        "arms": arms_results,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
