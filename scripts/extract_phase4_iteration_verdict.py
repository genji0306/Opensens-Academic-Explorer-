"""Extract Phase 4 tri-arm metrics for one iteration of the learning loop.

Reads the latest g7_* campaign artifacts and appends a structured verdict
row to the running verdict file. Called by run_phase4_learning_loop.sh.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def extract_arm(campaign_dir: Path) -> dict:
    summary_path = campaign_dir / "summary.json"
    if not summary_path.exists():
        return {"missing": True}
    s = json.loads(summary_path.read_text())
    es = s.get("external_eval_summary", {})
    log = s.get("external_eval_log", [])
    n = s.get("total_hypotheses", 0)
    contradicted = sum(e.get("odlyzko_details", {}).get("contradicted_count", 0) for e in log)
    confirmed = sum(e.get("odlyzko_details", {}).get("confirmed_count", 0) for e in log)
    early = sum(e.get("odlyzko_details", {}).get("contradicted_count", 0) for e in log[:5])
    late = sum(e.get("odlyzko_details", {}).get("contradicted_count", 0) for e in log[5:])
    flog = s.get("falsification_ledger", {})
    return {
        "internal_score": s.get("best_score"),
        "odlyzko_mean": es.get("mean_odlyzko_score", 0.0),
        "odlyzko_max": es.get("max_odlyzko_score", 0.0),
        "total_hypotheses": n,
        "contradictions": contradicted,
        "confirmations": confirmed,
        "wrongness_pct": (100.0 * contradicted / n) if n else 0.0,
        "early_contradictions": early,
        "late_contradictions": late,
        "delta": late - early,
        "ledger_falsifications_recorded": flog.get("summary", {}).get("total_falsifications", 0),
        "per_round_odlyzko_score": [e.get("odlyzko_score", 0.0) for e in log],
        "per_round_contradictions": [e.get("odlyzko_details", {}).get("contradicted_count", 0) for e in log],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--verdict-path", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    base = repo_root / "data" / "riemann" / "research"
    row = {
        "iteration": args.iteration,
        "baseline":  extract_arm(base / "g7_baseline"),
        "klein":     extract_arm(base / "g7_klein"),
        "hyperloop": extract_arm(base / "g7_hyperloop"),
    }

    if args.verdict_path.exists():
        data = json.loads(args.verdict_path.read_text())
    else:
        data = []
    data.append(row)
    args.verdict_path.write_text(json.dumps(data, indent=2))

    print(
        f"[iter {args.iteration}] "
        f"baseline odl={row['baseline'].get('odlyzko_mean', 0):.4f} | "
        f"klein odl={row['klein'].get('odlyzko_mean', 0):.4f} | "
        f"hyperloop odl={row['hyperloop'].get('odlyzko_mean', 0):.4f} | "
        f"hyper late_contr={row['hyperloop'].get('late_contradictions', '?')}"
    )


if __name__ == "__main__":
    main()
