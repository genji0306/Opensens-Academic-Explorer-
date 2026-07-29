"""Reporting and artifact writing for Timeguard."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from src.oae.studios.timeguard.schemas import (
    DebateTurn,
    MetricForecast,
    OrchestratorScorecard,
    TimeguardContext,
    TimeguardReport,
    WorkPackagePrediction,
)

_PHASE_LABEL_PATTERN = re.compile(r"\bphase\s+([a-z]{1,2})\b", re.IGNORECASE)
_PHASE_ROADMAP_PATTERN = re.compile(r"^(Phase\s+[A-Za-z]{1,2})\s*[:\-\u2014]\s*(.+)$")
_ROADMAP_KEYWORDS = (
    "analyze",
    "examine",
    "investigate",
    "pursue",
    "compute",
    "program",
    "verify",
    "attempt",
    "proving",
    "study",
    "extend",
    "increase",
    "use",
    "target",
    "next step",
    "direction",
    "explore",
    "search",
    "test whether",
    "frontier",
    "highest-priority",
    "priority",
    "route",
    "progress",
)
_PHASE_AV_REPORT_NAME = "RH_AV_PHASE_REPORT.md"


def build_report(
    context: TimeguardContext,
    *,
    scorecards: tuple[OrchestratorScorecard, ...],
    debate_turns: tuple[DebateTurn, ...],
    forecasts: tuple[MetricForecast, ...],
    work_packages: tuple[WorkPackagePrediction, ...],
) -> TimeguardReport:
    warnings = []
    for forecast in forecasts:
        if forecast.confidence < 0.55:
            warnings.append(
                f"{forecast.orchestrator_id}: forecast confidence is low; ranking downweights forecast guidance."
            )
    phase_roadmap = _extract_phase_roadmap(context)
    return TimeguardReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        context=context,
        scorecards=scorecards,
        debate_turns=debate_turns,
        forecasts=forecasts,
        work_packages=work_packages,
        phase_roadmap=phase_roadmap,
        warnings=tuple(warnings),
    )


def write_outputs(report: TimeguardReport, output_dir: str | Path) -> dict[str, str]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    context_path = target / "timeguard_context.json"
    scorecards_path = target / "timeguard_scorecards.json"
    debate_path = target / "timeguard_debate.json"
    forecast_path = target / "timeguard_forecast.json"
    report_path = target / "timeguard_report.md"

    _write_json(
        context_path,
        {
            "generated_at": report.generated_at,
            "context": report.context.to_dict(),
            "phase_roadmap": list(report.phase_roadmap),
            "warnings": list(report.warnings),
        },
    )
    _write_json(
        scorecards_path,
        {
            "generated_at": report.generated_at,
            "scorecards": [item.to_dict() for item in report.scorecards],
        },
    )
    _write_json(
        debate_path,
        {
            "generated_at": report.generated_at,
            "debate": [item.to_dict() for item in report.debate_turns],
        },
    )
    _write_json(
        forecast_path,
        {
            "generated_at": report.generated_at,
            "forecasts": [item.to_dict() for item in report.forecasts],
            "work_packages": [item.to_dict() for item in report.work_packages],
        },
    )
    report_path.write_text(render_report_markdown(report), encoding="utf-8")
    return {
        "context": str(context_path),
        "scorecards": str(scorecards_path),
        "debate": str(debate_path),
        "forecast": str(forecast_path),
        "report": str(report_path),
    }


def render_report_markdown(report: TimeguardReport) -> str:
    lines = [
        "# Opensens Timeguard Report",
        "",
        f"Generated: {report.generated_at}",
        "",
        "## Benchmark",
        "",
        f"- Baseline: [{report.context.baseline.orchestrator_id}]({report.context.baseline.summary_path})",
        f"- Klein: [{report.context.klein.orchestrator_id}]({report.context.klein.summary_path})",
        "",
        "## Scorecards",
        "",
    ]
    for scorecard in report.scorecards:
        lines.extend(
            [
                f"### {scorecard.orchestrator_id} ({scorecard.topology_mode})",
                "",
                f"- Best score: {scorecard.best_score:.3f}",
                f"- Rounds: {scorecard.rounds}",
                f"- Dominant failures: {', '.join(scorecard.dominant_failures)}",
                "- Achievements:",
                *[f"  - {item}" for item in scorecard.achievements],
                "- Remaining work:",
                *[f"  - {item}" for item in scorecard.remaining_work],
                "- Pros:",
                *[f"  - {item}" for item in scorecard.pros],
                "- Cons:",
                *[f"  - {item}" for item in scorecard.cons],
                "- Evidence:",
                *[f"  - [{Path(ref).name}]({ref})" for ref in scorecard.evidence_refs],
                "",
            ]
        )

    lines.extend(["## Debate", ""])
    for turn in report.debate_turns:
        lines.extend(
            [
                f"### {turn.role}",
                "",
                f"- Target: {turn.target}",
            ]
        )
        if turn.achievements:
            lines.extend(["- Achievements:", *[f"  - {item}" for item in turn.achievements]])
        if turn.remaining_work:
            lines.extend(["- Remaining work:", *[f"  - {item}" for item in turn.remaining_work]])
        if turn.pros:
            lines.extend(["- Pros:", *[f"  - {item}" for item in turn.pros]])
        if turn.cons:
            lines.extend(["- Cons:", *[f"  - {item}" for item in turn.cons]])
        if turn.verdict:
            lines.append(f"- Verdict: {turn.verdict}")
        if turn.next_work_packages:
            lines.extend(["- Next work packages:", *[f"  - {item}" for item in turn.next_work_packages]])
        if turn.trajectory_forecast:
            lines.extend(["- Trajectory forecast:", *[f"  - {item}" for item in turn.trajectory_forecast]])
        lines.extend(["- Evidence:", *[f"  - [{Path(ref).name}]({ref})" for ref in turn.evidence_refs], ""])

    lines.extend(["## Forecasts", ""])
    for forecast in report.forecasts:
        lines.extend(
            [
                f"### {forecast.orchestrator_id}",
                "",
                f"- Backend: `{forecast.backend}`",
                f"- Confidence: {forecast.confidence:.2f}",
                "- Point forecast:",
            ]
        )
        for metric, values in forecast.point_forecast.items():
            lines.append(f"  - {metric}: {', '.join(f'{value:.3f}' for value in values)}")
        lines.extend(
            [
                "- Evidence:",
                *[f"  - [{Path(ref).name}]({ref})" for ref in forecast.evidence_refs],
                "",
            ]
        )

    lines.extend(["## Ranked Work Packages", ""])
    for index, package in enumerate(report.work_packages, start=1):
        lines.extend(
            [
                f"### {index}. {package.title}",
                "",
                f"- Target orchestrator: {package.target_orchestrator}",
                f"- Why now: {package.why_now}",
                f"- Ranking score: {package.ranking_score:.3f}",
                f"- Confidence: {package.confidence:.2f}",
                "- Expected metric delta:",
            ]
        )
        for metric, delta in package.expected_metric_delta.items():
            lines.append(f"  - {metric}: {delta:+.3f}")
        lines.extend(
            [
                "- Blocking obligations:",
                *[f"  - {item}" for item in package.blocking_obligations],
                "- Evidence:",
                *[f"  - [{Path(ref).name}]({ref})" for ref in package.evidence_refs],
                "",
            ]
        )

    if report.phase_roadmap:
        lines.extend(["## Forward Roadmap", ""])
        for item in report.phase_roadmap:
            lines.append(f"- {item}")
        lines.append("")

    if report.context.support_docs:
        lines.extend(["## Support Documents", ""])
        for doc in report.context.support_docs:
            lines.extend(
                [
                    f"- [{doc.title}]({doc.path})",
                    *[f"  - {item}" for item in doc.highlights],
                ]
            )
        lines.append("")

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _extract_phase_roadmap(context: TimeguardContext) -> tuple[str, ...]:
    completed_phases = _completed_phase_labels(context)
    roadmap: list[str] = []
    seen: set[str] = set()
    for doc in reversed(context.support_docs):
        token_space = " ".join((doc.title, doc.path, *doc.highlights)).lower().replace("-", " ").replace("_", " ")
        if "phase " not in token_space:
            continue
        for highlight in doc.highlights:
            match = _PHASE_ROADMAP_PATTERN.match(highlight.strip())
            if not match:
                if Path(doc.path).name == _PHASE_AV_REPORT_NAME and _looks_like_future_direction(highlight):
                    normalized = highlight.strip()
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        roadmap.append(normalized)
                continue
            phase_label = match.group(1).lower()
            normalized_label = phase_label.replace("-", " ").replace("_", " ")
            phase_code_match = _PHASE_LABEL_PATTERN.search(normalized_label)
            if not phase_code_match:
                continue
            if not _looks_like_future_direction(match.group(2)):
                continue
            phase_code = phase_code_match.group(1).lower()
            if phase_code in completed_phases or phase_code in seen:
                continue
            seen.add(phase_code)
            roadmap.append(highlight.strip())
    return tuple(roadmap)


def _completed_phase_labels(context: TimeguardContext) -> set[str]:
    labels: set[str] = set()
    for doc in context.support_docs:
        token_space = f"{doc.title} {doc.path}".lower().replace("-", " ").replace("_", " ")
        for match in _PHASE_LABEL_PATTERN.finditer(token_space):
            labels.add(match.group(1).lower())
    return labels


def _looks_like_future_direction(body: str) -> bool:
    lowered = body.lower()
    return any(keyword in lowered for keyword in _ROADMAP_KEYWORDS)
