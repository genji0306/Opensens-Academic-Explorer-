"""CLI entrypoint for the recursive RH research orchestrator."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_ALLOWLIST, RiemannResearchConfig
from .orchestrator import run_campaign
from .seed_pack import DEFAULT_SEED_PACKS, list_seed_packs, resolve_seed_inputs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="riemann-research",
        description="Recursive RH research campaign over literature, hypotheses, numeric tests, and novelty review.",
    )
    parser.add_argument("--list-seed-packs", action="store_true",
                        help="List curated RH seed packs and exit.")
    parser.add_argument("--campaign-id", default="latest")
    parser.add_argument("--seed-pack", action="append", dest="seed_packs", default=None,
                        help="Curated RH seed pack name. Repeatable.")
    parser.add_argument("--seed", action="append", dest="seeds", default=None,
                        help="Local file path or allowlisted URL to ingest. Repeatable.")
    parser.add_argument("--allow-domain", action="append", dest="allow_domains", default=None,
                        help="Additional or replacement allowlisted domains. Repeatable.")
    parser.add_argument("--max-sources", type=int, default=500)
    parser.add_argument("--max-rounds", type=int, default=50)
    parser.add_argument("--max-hypotheses-per-round", type=int, default=8)
    parser.add_argument("--max-worker-runs-per-round", type=int, default=16)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--proof-target", type=float, default=0.92)
    parser.add_argument("--topology", choices=("baseline", "klein", "hyperloop"), default="baseline")
    parser.add_argument("--crawl-depth", type=int, default=1)
    parser.add_argument("--numeric-worker-n-zeros", type=int, default=512)
    parser.add_argument("--numeric-worker-max-iterations", type=int, default=6)
    parser.add_argument("--no-use-saved-report", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="Resume an existing campaign from its last checkpoint.")
    parser.add_argument("--report", type=Path, default=None,
                        help="Optional saved Riemann numeric report path for reuse.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _print_summary(summary: dict) -> None:
    print()
    print("=" * 60)
    print("  Riemann Recursive Research Campaign")
    print("=" * 60)
    print(f"  campaign_id      : {summary['campaign_id']}")
    print(f"  source_count     : {summary['source_count']}")
    print(f"  approach_count   : {summary['approach_count']}")
    print(f"  rounds_run       : {summary['rounds_run']}")
    print(f"  total_hypotheses : {summary['total_hypotheses']}")
    print(f"  best_score       : {summary['best_score']:.4f}")
    print(f"  best_candidate   : {summary['best_candidate_id'] or 'n/a'}")
    print(f"  converged        : {summary['converged']}")
    print(f"  termination      : {summary['termination_reason']}")
    print(f"  topology         : {summary.get('topology_mode', 'baseline')}")
    if summary.get("benchmark_mode"):
        print(f"  benchmark mode   : {summary['benchmark_mode']}")
    print(f"  resumed          : {summary.get('resumed', False)}")
    print(f"  summary          : {summary['paths']['summary']}")
    if summary.get("paths", {}).get("seed_manifest"):
        print(f"  seed manifest    : {summary['paths']['seed_manifest']}")
    if summary.get("paths", {}).get("operator_language"):
        print(f"  operator spec    : {summary['paths']['operator_language']}")
    if summary.get("paths", {}).get("operator_calibration"):
        print(f"  calibration      : {summary['paths']['operator_calibration']}")
    if summary.get("paths", {}).get("failure_atlas"):
        print(f"  failure atlas    : {summary['paths']['failure_atlas']}")
    if summary.get("paths", {}).get("certificate_report"):
        print(f"  certificates     : {summary['paths']['certificate_report']}")
    if summary.get("paths", {}).get("obligation_ledger"):
        print(f"  obligation ledger: {summary['paths']['obligation_ledger']}")
    if summary.get("paths", {}).get("dead_end_library"):
        print(f"  dead-end library : {summary['paths']['dead_end_library']}")
    if summary.get("paths", {}).get("campaign_benchmark"):
        print(f"  benchmark        : {summary['paths']['campaign_benchmark']}")
    if summary.get("paths", {}).get("dashboard"):
        print(f"  dashboard        : {summary['paths']['dashboard']}")
    if summary.get("paths", {}).get("literature_connection_map"):
        print(f"  literature map   : {summary['paths']['literature_connection_map']}")
    if summary.get("paths", {}).get("literature_connection_dashboard"):
        print(f"  literature html  : {summary['paths']['literature_connection_dashboard']}")
    if summary.get("paths", {}).get("all_results_dashboard"):
        print(f"  all results      : {summary['paths']['all_results_dashboard']}")
    if summary.get("best_dossier_path"):
        print(f"  best dossier     : {summary['best_dossier_path']}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list_seed_packs:
        packs = list_seed_packs()
        print()
        print("Available Riemann Seed Packs")
        print("=" * 60)
        for pack in packs:
            print(f"{pack['name']:<14} seeds={pack['seed_count']:<3} bibliography={pack['bibliography_count']:<3} {pack['description']}")
        print("=" * 60)
        return 0

    pack_names = tuple(args.seed_packs) if args.seed_packs else DEFAULT_SEED_PACKS
    seeds, allow_domains, _manifest = resolve_seed_inputs(
        pack_names,
        extra_seeds=tuple(args.seeds or ()),
        extra_domains=tuple(args.allow_domains or ()),
    )
    if not allow_domains:
        allow_domains = DEFAULT_ALLOWLIST
    report_path = args.report if args.report is not None else RiemannResearchConfig().riemann_report_path

    cfg = RiemannResearchConfig(
        campaign_id=args.campaign_id,
        seed_pack_names=pack_names,
        crawl_seeds=seeds,
        allowlisted_domains=allow_domains,
        max_sources=args.max_sources,
        max_rounds=args.max_rounds,
        max_crawl_depth=args.crawl_depth,
        max_hypotheses_per_round=args.max_hypotheses_per_round,
        max_worker_runs_per_round=args.max_worker_runs_per_round,
        patience=args.patience,
        proof_target=args.proof_target,
        topology_mode=args.topology,
        use_saved_riemann_report=not args.no_use_saved_report,
        riemann_report_path=report_path,
        numeric_worker_n_zeros=args.numeric_worker_n_zeros,
        numeric_worker_max_iterations=args.numeric_worker_max_iterations,
        resume=args.resume,
    )
    summary = run_campaign(cfg, verbose=args.verbose)
    _print_summary(summary)
    return 0 if summary["converged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
