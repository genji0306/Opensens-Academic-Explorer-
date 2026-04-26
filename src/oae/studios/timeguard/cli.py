"""CLI for Timeguard."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.oae.studios.timeguard.engine import (
    run_external_frontier_discovery,
    run_external_seed_pack_launch,
    run_klein_effort_discovery,
    run_oasis_frontier_offline,
    run_oasis_frontier_review,
    run_oasis_frontier_scaffold,
    run_timeguard,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timeguard",
        description="Run Opensens Timeguard over RH baseline vs Klein campaign artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser(
        "run",
        help="Run Timeguard against two RH orchestrator campaign directories.",
    )
    run.add_argument("--baseline-dir", type=Path, required=True)
    run.add_argument("--klein-dir", type=Path, required=True)
    run.add_argument("--support-doc", type=Path, action="append", default=[])
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--forecast-horizon", type=int, default=2)
    run.add_argument("--top-work-packages", type=int, default=3)

    discover = subparsers.add_parser(
        "discover-klein-effort",
        help="Run a MiroFish-style discovery debate over all RH Klein checkpoint effort so far.",
    )
    discover.add_argument("--klein-dir", type=Path, required=True)
    discover.add_argument("--support-doc", type=Path, action="append", default=[])
    discover.add_argument("--output-dir", type=Path, required=True)

    external = subparsers.add_parser(
        "discover-external-frontier",
        help="Screen harvested external RH claims against the current Timeguard and MiroFish map, then emit orchestrator-ready seed packs.",
    )
    external.add_argument("--baseline-dir", type=Path, required=True)
    external.add_argument("--klein-dir", type=Path, required=True)
    external.add_argument("--support-doc", type=Path, action="append", default=[])
    external.add_argument("--claim-doc", type=Path, action="append", default=[])
    external.add_argument("--oasis-db", type=Path, action="append", default=[],
                         help="CAMEL-AI OASIS SQLite database path. Repeatable.")
    external.add_argument("--output-dir", type=Path, required=True)
    external.add_argument("--top-seed-packs", type=int, default=3)

    launch = subparsers.add_parser(
        "launch-external-seed-pack",
        help="Materialize a reviewed external frontier pack into real RH seeds and run the orchestrator on it.",
    )
    launch.add_argument("--seed-pack-file", type=Path, required=True)
    launch.add_argument("--output-dir", type=Path, required=True)
    launch.add_argument("--pack-name", type=str, default=None)
    launch.add_argument("--pack-index", type=int, default=1)
    launch.add_argument("--campaign-id", type=str, default=None)
    launch.add_argument("--research-root", type=Path, default=None)
    launch.add_argument("--max-sources", type=int, default=64)
    launch.add_argument("--max-rounds", type=int, default=3)
    launch.add_argument("--max-hypotheses-per-round", type=int, default=6)
    launch.add_argument("--max-worker-runs-per-round", type=int, default=12)
    launch.add_argument("--patience", type=int, default=2)
    launch.add_argument("--proof-target", type=float, default=0.92)

    scaffold = subparsers.add_parser(
        "scaffold-oasis-frontier",
        help="Generate a CAMEL-AI OASIS Reddit simulation scaffold from the current RH frontier map.",
    )
    scaffold.add_argument("--baseline-dir", type=Path, required=True)
    scaffold.add_argument("--klein-dir", type=Path, required=True)
    scaffold.add_argument("--support-doc", type=Path, action="append", default=[])
    scaffold.add_argument("--claim-doc", type=Path, action="append", default=[])
    scaffold.add_argument("--oasis-db", type=Path, action="append", default=[],
                         help="Optional OASIS SQLite database path for claim harvesting. Repeatable.")
    scaffold.add_argument("--output-dir", type=Path, required=True)
    scaffold.add_argument("--agent-count", type=int, default=12)
    scaffold.add_argument("--top-seed-packs", type=int, default=3)

    review = subparsers.add_parser(
        "review-oasis-frontier",
        help="Re-ingest an OASIS simulation database back into Timeguard using a saved scaffold manifest.",
    )
    review.add_argument("--manifest", type=Path, required=True)
    review.add_argument("--oasis-db", type=Path, action="append", default=[],
                        help="OASIS SQLite database path. Repeatable.")
    review.add_argument("--output-dir", type=Path, required=True)
    review.add_argument("--top-seed-packs", type=int, default=3)

    offline = subparsers.add_parser(
        "simulate-oasis-frontier-offline",
        help="Run a deterministic no-key OASIS-style Reddit simulation from a saved frontier scaffold manifest.",
    )
    offline.add_argument("--manifest", type=Path, required=True)
    offline.add_argument("--output-dir", type=Path, required=True)
    offline.add_argument("--cycles", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        _report, outputs = run_timeguard(
            baseline_dir=args.baseline_dir,
            klein_dir=args.klein_dir,
            support_docs=tuple(args.support_doc),
            output_dir=args.output_dir,
            forecast_horizon=args.forecast_horizon,
            top_work_packages=args.top_work_packages,
        )
    elif args.command == "discover-klein-effort":
        _report, outputs = run_klein_effort_discovery(
            klein_dir=args.klein_dir,
            support_docs=tuple(args.support_doc),
            output_dir=args.output_dir,
        )
    elif args.command == "discover-external-frontier":
        _report, outputs = run_external_frontier_discovery(
            baseline_dir=args.baseline_dir,
            klein_dir=args.klein_dir,
            support_docs=tuple(args.support_doc),
            claim_docs=tuple(args.claim_doc),
            oasis_dbs=tuple(args.oasis_db),
            output_dir=args.output_dir,
            top_seed_packs=args.top_seed_packs,
        )
    elif args.command == "launch-external-seed-pack":
        _report, outputs = run_external_seed_pack_launch(
            seed_pack_file=args.seed_pack_file,
            output_dir=args.output_dir,
            pack_name=args.pack_name,
            pack_index=args.pack_index,
            campaign_id=args.campaign_id,
            research_root=args.research_root,
            max_sources=args.max_sources,
            max_rounds=args.max_rounds,
            max_hypotheses_per_round=args.max_hypotheses_per_round,
            max_worker_runs_per_round=args.max_worker_runs_per_round,
            patience=args.patience,
            proof_target=args.proof_target,
        )
    elif args.command == "scaffold-oasis-frontier":
        _report, outputs = run_oasis_frontier_scaffold(
            baseline_dir=args.baseline_dir,
            klein_dir=args.klein_dir,
            support_docs=tuple(args.support_doc),
            claim_docs=tuple(args.claim_doc),
            oasis_dbs=tuple(args.oasis_db),
            output_dir=args.output_dir,
            agent_count=args.agent_count,
            top_seed_packs=args.top_seed_packs,
        )
    elif args.command == "review-oasis-frontier":
        _report, outputs = run_oasis_frontier_review(
            manifest_path=args.manifest,
            oasis_dbs=tuple(args.oasis_db),
            output_dir=args.output_dir,
            top_seed_packs=args.top_seed_packs,
        )
    elif args.command == "simulate-oasis-frontier-offline":
        _report, outputs = run_oasis_frontier_offline(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            cycles=args.cycles,
        )
    else:
        return 2
    assert outputs is not None
    print()
    print("Timeguard Outputs")
    print("=" * 60)
    for key, value in outputs.items():
        print(f"{key:<10}: {value}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
