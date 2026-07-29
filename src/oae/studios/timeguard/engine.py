"""Execution pipeline for the Timeguard studio."""
from __future__ import annotations

from pathlib import Path

from src.oae.studios.timeguard.adapters.riemann import build_scorecards, build_timeguard_context
from src.oae.studios.timeguard.debate import TimeguardDebate
from src.oae.studios.timeguard.external_frontier import run_external_frontier_discovery
from src.oae.studios.timeguard.external_seed_launch import run_external_seed_pack_launch
from src.oae.studios.timeguard.forecast.timesfm_adapter import TimesFMAdapter
from src.oae.studios.timeguard.mirofish_discovery import run_klein_effort_discovery
from src.oae.studios.timeguard.oasis_offline import run_oasis_frontier_offline
from src.oae.studios.timeguard.oasis_scaffold import (
    run_oasis_frontier_review,
    run_oasis_frontier_scaffold,
)
from src.oae.studios.timeguard.ranking import rank_work_packages
from src.oae.studios.timeguard.reporting import build_report, write_outputs
from src.oae.studios.timeguard.schemas import (
    ExternalFrontierReport,
    ExternalSeedPackLaunchReport,
    KleinEffortDiscoveryReport,
    OasisFrontierScaffoldReport,
    TimeguardReport,
)


def run_timeguard(
    *,
    baseline_dir: str | Path,
    klein_dir: str | Path,
    support_docs: tuple[str | Path, ...] = (),
    output_dir: str | Path | None = None,
    forecast_horizon: int = 2,
    top_work_packages: int = 3,
) -> tuple[TimeguardReport, dict[str, str] | None]:
    context = build_timeguard_context(
        baseline_dir,
        klein_dir,
        support_docs=support_docs,
    )
    scorecards = build_scorecards(context)
    adapter = TimesFMAdapter()
    forecasts = (
        adapter.forecast_campaign(context.baseline, horizon=forecast_horizon),
        adapter.forecast_campaign(context.klein, horizon=forecast_horizon),
    )
    work_packages = rank_work_packages(
        context,
        forecasts,
        top_k=top_work_packages,
    )
    debate = TimeguardDebate().run(
        context,
        baseline_scorecard=scorecards[0],
        klein_scorecard=scorecards[1],
        forecasts=forecasts,
        work_packages=work_packages,
    )
    report = build_report(
        context,
        scorecards=scorecards,
        debate_turns=debate,
        forecasts=forecasts,
        work_packages=work_packages,
    )
    if output_dir is None:
        return report, None
    return report, write_outputs(report, output_dir)


__all__ = [
    "ExternalFrontierReport",
    "ExternalSeedPackLaunchReport",
    "KleinEffortDiscoveryReport",
    "OasisFrontierScaffoldReport",
    "run_external_frontier_discovery",
    "run_external_seed_pack_launch",
    "run_klein_effort_discovery",
    "run_oasis_frontier_offline",
    "run_oasis_frontier_review",
    "run_oasis_frontier_scaffold",
    "run_timeguard",
]
