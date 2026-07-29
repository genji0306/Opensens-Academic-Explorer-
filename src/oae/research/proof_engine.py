"""Bounded proof-search engine over existing OAE orchestrators and tools.

This engine does not claim mathematical proof progress. It runs matched control
and intervention lanes, captures the resulting artifacts, and synthesizes
proof-obligation reports that can be reviewed across RH, RTAP, and sensing.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .harness import ResearchHarness, build_default_harnesses

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "research" / "proof_engine"
DEFAULT_MODULES = ("riemann", "rtap", "sensing-studio")
RIEMANN_RESEARCH_ROOT = PROJECT_ROOT / "data" / "riemann" / "research"

_REPORT_PATH_RE = re.compile(r"^\s*Report:\s+(?P<path>.+?)\s*$", re.MULTILINE)
_SENSOR_SCORE_RE = re.compile(r"^\s*Score:\s+(?P<score>\d+(?:\.\d+)?)\s*$", re.MULTILINE)
_BEST_SCORE_RE = re.compile(r"^\s*Best score:\s+(?P<score>\d+(?:\.\d+)?)", re.MULTILINE)


@dataclass(frozen=True)
class BudgetProfile:
    name: str
    riemann_max_rounds: int
    riemann_max_hypotheses_per_round: int
    riemann_max_worker_runs_per_round: int
    riemann_patience: int
    riemann_forecast_horizon: int
    rtap_max_iterations: int
    rtap_campaign_budget: int
    sensor_campaign_budget: int
    sensor_analyte: str


@dataclass
class LaneExecution:
    module_slug: str
    lane_id: str
    role: str
    command: list[str]
    returncode: int
    status: str
    started_at: str
    finished_at: str
    output_dir: str
    stdout_path: str
    stderr_path: str
    artifact_paths: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class ModuleExecution:
    module_slug: str
    question: str
    harness: dict[str, Any]
    lane_executions: list[LaneExecution]
    review_summary: dict[str, Any]


@dataclass
class ProofEngineResult:
    run_id: str
    profile: str
    output_dir: str
    started_at: str
    finished_at: str
    modules: list[ModuleExecution]
    summary_path: str
    report_path: str


def _profile(name: str, analyte: str) -> BudgetProfile:
    if name == "standard":
        return BudgetProfile(
            name=name,
            riemann_max_rounds=3,
            riemann_max_hypotheses_per_round=4,
            riemann_max_worker_runs_per_round=6,
            riemann_patience=2,
            riemann_forecast_horizon=2,
            rtap_max_iterations=2,
            rtap_campaign_budget=2,
            sensor_campaign_budget=2,
            sensor_analyte=analyte,
        )
    return BudgetProfile(
        name="smoke",
        riemann_max_rounds=1,
        riemann_max_hypotheses_per_round=2,
        riemann_max_worker_runs_per_round=2,
        riemann_patience=1,
        riemann_forecast_horizon=1,
        rtap_max_iterations=1,
        rtap_campaign_budget=1,
        sensor_campaign_budget=1,
        sensor_analyte=analyte,
    )


def available_modules() -> tuple[str, ...]:
    return tuple(build_default_harnesses())


def build_proof_engine_plan(
    *,
    run_id: str,
    modules: tuple[str, ...] = DEFAULT_MODULES,
    profile: str = "smoke",
    analyte: str = "glucose",
    include_frontier_tools: bool = True,
    include_promotion: bool = False,
) -> dict[str, Any]:
    harnesses = build_default_harnesses()
    budget = _profile(profile, analyte)
    plan_modules: list[dict[str, Any]] = []
    for module_slug in modules:
        harness = harnesses[module_slug]
        lanes = [
            {
                "lane_id": harness.control_lane.lane_id,
                "role": harness.control_lane.role,
                "entrypoint": harness.control_lane.entrypoint,
            },
            {
                "lane_id": harness.intervention_lane.lane_id,
                "role": harness.intervention_lane.role,
                "entrypoint": harness.intervention_lane.entrypoint,
            },
            {
                "lane_id": harness.review_lane.lane_id,
                "role": harness.review_lane.role,
                "entrypoint": harness.review_lane.entrypoint,
            },
        ]
        extras: list[dict[str, Any]] = []
        if module_slug == "riemann" and include_frontier_tools:
            extras.append(
                {
                    "lane_id": "external-frontier",
                    "role": "tool",
                    "entrypoint": "python3 -m src.oae.studios.timeguard.cli discover-external-frontier",
                }
            )
        if include_promotion and harness.promotion_lane is not None:
            extras.append(
                {
                    "lane_id": harness.promotion_lane.lane_id,
                    "role": harness.promotion_lane.role,
                    "entrypoint": harness.promotion_lane.entrypoint,
                }
            )
        plan_modules.append(
            {
                "module_slug": module_slug,
                "question": harness.question,
                "lanes": lanes,
                "extras": extras,
            }
        )
    return {
        "run_id": run_id,
        "profile": asdict(budget),
        "modules": plan_modules,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_modules(modules: tuple[str, ...] | None) -> tuple[str, ...]:
    selected = modules or DEFAULT_MODULES
    known = set(available_modules())
    unknown = [item for item in selected if item not in known]
    if unknown:
        raise ValueError(f"Unknown module(s): {', '.join(unknown)}")
    return tuple(dict.fromkeys(selected))


def _run_command(
    *,
    module_slug: str,
    lane_id: str,
    role: str,
    command: list[str],
    output_dir: Path,
    cwd: Path = PROJECT_ROOT,
    allowed_returncodes: tuple[int, ...] = (0, 1),
) -> LaneExecution:
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / "stdout.txt"
    stderr_path = output_dir / "stderr.txt"
    started_at = _now()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    finished_at = _now()
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode == 0:
        status = "completed"
    elif completed.returncode in allowed_returncodes:
        status = "completed_nonconverged"
    else:
        status = "failed"
    notes: list[str] = []
    if status == "completed_nonconverged":
        notes.append("Lane finished without reaching its target threshold.")
    if status == "failed":
        notes.append("Lane exited with an unexpected nonzero status.")
    return LaneExecution(
        module_slug=module_slug,
        lane_id=lane_id,
        role=role,
        command=command,
        returncode=completed.returncode,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        output_dir=str(output_dir),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        notes=notes,
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _extract_report_path(stdout_text: str) -> Path | None:
    match = _REPORT_PATH_RE.search(stdout_text)
    if not match:
        return None
    return Path(match.group("path").strip()).expanduser().resolve()


def _extract_sensor_score(stdout_text: str) -> float | None:
    match = _SENSOR_SCORE_RE.search(stdout_text)
    if match:
        return float(match.group("score"))
    return None


def _extract_best_score(stdout_text: str) -> float | None:
    match = _BEST_SCORE_RE.search(stdout_text)
    if match:
        return float(match.group("score"))
    return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_review_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _score_verdict(control_score: float | None, intervention_score: float | None) -> str:
    if control_score is None and intervention_score is None:
        return "insufficient_data"
    if control_score is None:
        return "intervention_only"
    if intervention_score is None:
        return "control_only"
    if intervention_score > control_score:
        return "intervention_leads"
    if intervention_score < control_score:
        return "control_leads"
    return "tie"


def _material_review_summary(
    *,
    module_slug: str,
    control_label: str,
    intervention_label: str,
    control_score: float | None,
    intervention_score: float | None,
    obligations: tuple[str, ...],
    notes: tuple[str, ...] = (),
) -> dict[str, Any]:
    verdict = _score_verdict(control_score, intervention_score)
    delta = None
    if control_score is not None and intervention_score is not None:
        delta = round(intervention_score - control_score, 4)
    summary = {
        "module_slug": module_slug,
        "verdict": verdict,
        "control_label": control_label,
        "control_score": control_score,
        "intervention_label": intervention_label,
        "intervention_score": intervention_score,
        "score_delta": delta,
        "obligations": list(obligations),
        "notes": list(notes),
    }
    return summary


def _run_riemann_module(
    *,
    run_id: str,
    module_dir: Path,
    harness: ResearchHarness,
    budget: BudgetProfile,
    include_frontier_tools: bool,
    include_promotion: bool,
) -> ModuleExecution:
    lane_executions: list[LaneExecution] = []
    baseline_campaign_id = f"{run_id}-rh-baseline"
    klein_campaign_id = f"{run_id}-rh-klein"
    baseline_dir = RIEMANN_RESEARCH_ROOT / baseline_campaign_id
    klein_dir = RIEMANN_RESEARCH_ROOT / klein_campaign_id

    baseline = _run_command(
        module_slug="riemann",
        lane_id=harness.control_lane.lane_id,
        role=harness.control_lane.role,
        command=[
            sys.executable,
            "oae.py",
            "--riemann-research",
            "--campaign-id",
            baseline_campaign_id,
            "--topology",
            "baseline",
            "--max-rounds",
            str(budget.riemann_max_rounds),
            "--max-hypotheses-per-round",
            str(budget.riemann_max_hypotheses_per_round),
            "--max-worker-runs-per-round",
            str(budget.riemann_max_worker_runs_per_round),
            "--patience",
            str(budget.riemann_patience),
        ],
        output_dir=module_dir / harness.control_lane.lane_id,
    )
    baseline_summary = _read_json(baseline_dir / "summary.json") or {}
    baseline.artifact_paths["summary"] = str((baseline_dir / "summary.json").resolve())
    baseline.metrics["best_score"] = _safe_float(baseline_summary.get("best_score"))
    lane_executions.append(baseline)

    klein = _run_command(
        module_slug="riemann",
        lane_id=harness.intervention_lane.lane_id,
        role=harness.intervention_lane.role,
        command=[
            sys.executable,
            "oae.py",
            "--riemann-research",
            "--campaign-id",
            klein_campaign_id,
            "--topology",
            "klein",
            "--max-rounds",
            str(budget.riemann_max_rounds),
            "--max-hypotheses-per-round",
            str(budget.riemann_max_hypotheses_per_round),
            "--max-worker-runs-per-round",
            str(budget.riemann_max_worker_runs_per_round),
            "--patience",
            str(budget.riemann_patience),
        ],
        output_dir=module_dir / harness.intervention_lane.lane_id,
    )
    klein_summary = _read_json(klein_dir / "summary.json") or {}
    klein.artifact_paths["summary"] = str((klein_dir / "summary.json").resolve())
    klein.metrics["best_score"] = _safe_float(klein_summary.get("best_score"))
    lane_executions.append(klein)

    timeguard_dir = module_dir / harness.review_lane.lane_id
    timeguard = _run_command(
        module_slug="riemann",
        lane_id=harness.review_lane.lane_id,
        role=harness.review_lane.role,
        command=[
            sys.executable,
            "-m",
            "src.oae.studios.timeguard.cli",
            "run",
            "--baseline-dir",
            str(baseline_dir),
            "--klein-dir",
            str(klein_dir),
            "--output-dir",
            str(timeguard_dir),
            "--forecast-horizon",
            str(budget.riemann_forecast_horizon),
            "--top-work-packages",
            "3",
        ],
        output_dir=timeguard_dir,
        allowed_returncodes=(0,),
    )
    timeguard.artifact_paths.update(
        {
            "report": str((timeguard_dir / "timeguard_report.md").resolve()),
            "scorecards": str((timeguard_dir / "timeguard_scorecards.json").resolve()),
            "forecast": str((timeguard_dir / "timeguard_forecast.json").resolve()),
        }
    )
    timeguard_forecast = _read_json(timeguard_dir / "timeguard_forecast.json") or {}
    work_packages = timeguard_forecast.get("work_packages", [])
    timeguard.metrics["work_package_count"] = len(work_packages)
    lane_executions.append(timeguard)

    frontier_seed_pack: Path | None = None
    if include_frontier_tools:
        frontier_dir = module_dir / "external-frontier"
        frontier = _run_command(
            module_slug="riemann",
            lane_id="external-frontier",
            role="tool",
            command=[
                sys.executable,
                "-m",
                "src.oae.studios.timeguard.cli",
                "discover-external-frontier",
                "--baseline-dir",
                str(baseline_dir),
                "--klein-dir",
                str(klein_dir),
                "--output-dir",
                str(frontier_dir),
                "--top-seed-packs",
                "2",
            ],
            output_dir=frontier_dir,
            allowed_returncodes=(0,),
        )
        frontier_seed_pack = frontier_dir / "orchestrator_seed_pack.json"
        frontier_payload = _read_json(frontier_seed_pack) or {}
        frontier.artifact_paths.update(
            {
                "report": str((frontier_dir / "external_frontier_report.md").resolve()),
                "seed_pack": str(frontier_seed_pack.resolve()),
            }
        )
        frontier.metrics["seed_pack_count"] = len(frontier_payload.get("seed_packs", []))
        lane_executions.append(frontier)

        if include_promotion and harness.promotion_lane is not None and frontier_payload.get("seed_packs"):
            promotion_dir = module_dir / harness.promotion_lane.lane_id
            promotion = _run_command(
                module_slug="riemann",
                lane_id=harness.promotion_lane.lane_id,
                role=harness.promotion_lane.role,
                command=[
                    sys.executable,
                    "-m",
                    "src.oae.studios.timeguard.cli",
                    "launch-external-seed-pack",
                    "--seed-pack-file",
                    str(frontier_seed_pack),
                    "--output-dir",
                    str(promotion_dir),
                    "--max-rounds",
                    str(budget.riemann_max_rounds),
                    "--max-hypotheses-per-round",
                    str(budget.riemann_max_hypotheses_per_round),
                    "--max-worker-runs-per-round",
                    str(budget.riemann_max_worker_runs_per_round),
                    "--patience",
                    str(budget.riemann_patience),
                ],
                output_dir=promotion_dir,
            )
            promotion.artifact_paths["report"] = str((promotion_dir / "external_seed_launch_report.md").resolve())
            lane_executions.append(promotion)

    review = _material_review_summary(
        module_slug="riemann",
        control_label=harness.control_lane.lane_id,
        intervention_label=harness.intervention_lane.lane_id,
        control_score=_safe_float(baseline_summary.get("best_score")),
        intervention_score=_safe_float(klein_summary.get("best_score")),
        obligations=harness.obligations,
        notes=harness.notes,
    )
    review["top_work_packages"] = [
        item.get("title", "")
        for item in work_packages[:3]
        if isinstance(item, dict)
    ]
    review["taboo_routes"] = list(harness.taboo_routes)
    review_json = module_dir / "review" / "review_summary.json"
    review_md = module_dir / "review" / "review_summary.md"
    _write_json(review_json, review)
    _write_review_markdown(
        review_md,
        [
            "# Riemann Proof-Obligation Review",
            "",
            f"- Verdict: {review['verdict']}",
            f"- Control `{review['control_label']}` score: {review['control_score']}",
            f"- Intervention `{review['intervention_label']}` score: {review['intervention_score']}",
            f"- Score delta: {review['score_delta']}",
            "- Obligations:",
            *[f"  - {item}" for item in review["obligations"]],
            "- Timeguard priorities:",
            *[f"  - {item}" for item in review["top_work_packages"]],
            "- Taboo routes:",
            *[f"  - {item}" for item in review["taboo_routes"]],
            "",
            "This is a proof-search control report, not a proof claim.",
        ],
    )
    review["artifacts"] = {
        "json": str(review_json.resolve()),
        "markdown": str(review_md.resolve()),
    }
    return ModuleExecution(
        module_slug="riemann",
        question=harness.question,
        harness=harness.to_dict(run_id),
        lane_executions=lane_executions,
        review_summary=review,
    )


def _run_rtap_module(
    *,
    run_id: str,
    module_dir: Path,
    harness: ResearchHarness,
    budget: BudgetProfile,
) -> ModuleExecution:
    lane_executions: list[LaneExecution] = []
    direct = _run_command(
        module_slug="rtap",
        lane_id=harness.control_lane.lane_id,
        role=harness.control_lane.role,
        command=[
            sys.executable,
            "oae.py",
            "--rtap",
            "--max-iterations",
            str(budget.rtap_max_iterations),
        ],
        output_dir=module_dir / harness.control_lane.lane_id,
    )
    direct_report = PROJECT_ROOT / "data" / "reports" / "final_report.json"
    direct_payload = _read_json(direct_report) or {}
    direct.artifact_paths["report"] = str(direct_report.resolve())
    direct.metrics["final_score"] = _safe_float(direct_payload.get("final_convergence_score"))
    lane_executions.append(direct)

    campaign = _run_command(
        module_slug="rtap",
        lane_id=harness.intervention_lane.lane_id,
        role=harness.intervention_lane.role,
        command=[
            sys.executable,
            "oae.py",
            "--campaign",
            "--rtap",
            "--goal",
            f"proof-engine-{run_id}",
            "--max-iterations",
            str(budget.rtap_campaign_budget),
        ],
        output_dir=module_dir / harness.intervention_lane.lane_id,
    )
    campaign_stdout = Path(campaign.stdout_path).read_text(encoding="utf-8")
    campaign_report = _extract_report_path(campaign_stdout)
    campaign_payload = _read_json(campaign_report) if campaign_report is not None else {}
    if campaign_report is not None:
        campaign.artifact_paths["report"] = str(campaign_report)
    campaign.metrics["final_score"] = _safe_float((campaign_payload or {}).get("final_score"))
    lane_executions.append(campaign)

    review = _material_review_summary(
        module_slug="rtap",
        control_label=harness.control_lane.lane_id,
        intervention_label=harness.intervention_lane.lane_id,
        control_score=_safe_float(direct_payload.get("final_convergence_score")),
        intervention_score=_safe_float((campaign_payload or {}).get("final_score")),
        obligations=harness.obligations,
    )
    review["termination_reason_control"] = direct_payload.get("termination_reason")
    review["termination_reason_intervention"] = (campaign_payload or {}).get("termination_reason")
    review_json = module_dir / "review" / "review_summary.json"
    review_md = module_dir / "review" / "review_summary.md"
    _write_json(review_json, review)
    _write_review_markdown(
        review_md,
        [
            "# RTAP Proof-Obligation Review",
            "",
            f"- Verdict: {review['verdict']}",
            f"- Control `{review['control_label']}` score: {review['control_score']}",
            f"- Intervention `{review['intervention_label']}` score: {review['intervention_score']}",
            f"- Score delta: {review['score_delta']}",
            f"- Control termination: {review['termination_reason_control']}",
            f"- Intervention termination: {review['termination_reason_intervention']}",
            "- Obligations:",
            *[f"  - {item}" for item in review["obligations"]],
        ],
    )
    review["artifacts"] = {
        "json": str(review_json.resolve()),
        "markdown": str(review_md.resolve()),
    }
    return ModuleExecution(
        module_slug="rtap",
        question=harness.question,
        harness=harness.to_dict(run_id),
        lane_executions=lane_executions,
        review_summary=review,
    )


def _run_sensing_module(
    *,
    run_id: str,
    module_dir: Path,
    harness: ResearchHarness,
    budget: BudgetProfile,
) -> ModuleExecution:
    lane_executions: list[LaneExecution] = []
    analyte = budget.sensor_analyte
    direct = _run_command(
        module_slug="sensing-studio",
        lane_id=harness.control_lane.lane_id,
        role=harness.control_lane.role,
        command=[
            sys.executable,
            "oae.py",
            "--sensor",
            "--analyte",
            analyte,
        ],
        output_dir=module_dir / harness.control_lane.lane_id,
        allowed_returncodes=(0,),
    )
    direct_stdout = Path(direct.stdout_path).read_text(encoding="utf-8")
    direct.metrics["sensor_score"] = _extract_sensor_score(direct_stdout)
    lane_executions.append(direct)

    campaign = _run_command(
        module_slug="sensing-studio",
        lane_id=harness.intervention_lane.lane_id,
        role=harness.intervention_lane.role,
        command=[
            sys.executable,
            "oae.py",
            "--campaign",
            "--sensor",
            "--analyte",
            analyte,
            "--goal",
            f"{analyte}-{run_id}",
            "--max-iterations",
            str(budget.sensor_campaign_budget),
        ],
        output_dir=module_dir / harness.intervention_lane.lane_id,
    )
    campaign_stdout = Path(campaign.stdout_path).read_text(encoding="utf-8")
    campaign_report = _extract_report_path(campaign_stdout)
    campaign_payload = _read_json(campaign_report) if campaign_report is not None else {}
    if campaign_report is not None:
        campaign.artifact_paths["report"] = str(campaign_report)
    campaign.metrics["final_score"] = _safe_float((campaign_payload or {}).get("final_score"))
    if campaign.metrics["final_score"] is None:
        campaign.metrics["final_score"] = _extract_best_score(campaign_stdout)
    lane_executions.append(campaign)

    review = _material_review_summary(
        module_slug="sensing-studio",
        control_label=harness.control_lane.lane_id,
        intervention_label=harness.intervention_lane.lane_id,
        control_score=_safe_float(direct.metrics.get("sensor_score")),
        intervention_score=_safe_float(campaign.metrics.get("final_score")),
        obligations=harness.obligations,
    )
    review["analyte"] = analyte
    review_json = module_dir / "review" / "review_summary.json"
    review_md = module_dir / "review" / "review_summary.md"
    _write_json(review_json, review)
    _write_review_markdown(
        review_md,
        [
            "# Sensing Studio Proof-Obligation Review",
            "",
            f"- Analyte: {analyte}",
            f"- Verdict: {review['verdict']}",
            f"- Control `{review['control_label']}` score: {review['control_score']}",
            f"- Intervention `{review['intervention_label']}` score: {review['intervention_score']}",
            f"- Score delta: {review['score_delta']}",
            "- Obligations:",
            *[f"  - {item}" for item in review["obligations"]],
        ],
    )
    review["artifacts"] = {
        "json": str(review_json.resolve()),
        "markdown": str(review_md.resolve()),
    }
    return ModuleExecution(
        module_slug="sensing-studio",
        question=harness.question,
        harness=harness.to_dict(run_id),
        lane_executions=lane_executions,
        review_summary=review,
    )


def _write_engine_summary(
    *,
    run_id: str,
    profile: str,
    output_dir: Path,
    started_at: str,
    finished_at: str,
    modules: list[ModuleExecution],
) -> tuple[Path, Path]:
    summary_path = output_dir / "proof_engine_summary.json"
    report_path = output_dir / "proof_engine_report.md"
    payload = {
        "run_id": run_id,
        "profile": profile,
        "started_at": started_at,
        "finished_at": finished_at,
        "output_dir": str(output_dir),
        "modules": [asdict(module) for module in modules],
    }
    _write_json(summary_path, payload)
    lines = [
        "# OAE Proof Engine Run",
        "",
        f"- Run id: `{run_id}`",
        f"- Profile: `{profile}`",
        f"- Output dir: `{output_dir}`",
        "",
        "## Modules",
        "",
    ]
    for module in modules:
        review = module.review_summary
        lines.extend(
            [
                f"### {module.module_slug}",
                "",
                f"- Verdict: {review.get('verdict', 'unknown')}",
                f"- Question: {module.question}",
                f"- Review summary: {review.get('artifacts', {}).get('markdown', '')}",
                "- Lane statuses:",
                *[
                    f"  - {lane.lane_id}: {lane.status} (rc={lane.returncode})"
                    for lane in module.lane_executions
                ],
                "",
            ]
        )
    lines.append("This engine records proof-search state and obligations; it does not certify proof.")
    _write_review_markdown(report_path, lines)
    return summary_path, report_path


def run_proof_engine(
    *,
    modules: tuple[str, ...] | None = None,
    profile: str = "smoke",
    run_id: str | None = None,
    analyte: str = "glucose",
    include_frontier_tools: bool = True,
    include_promotion: bool = False,
    dry_run: bool = False,
) -> ProofEngineResult:
    selected_modules = _normalize_modules(modules)
    budget = _profile(profile, analyte)
    run_tag = run_id or f"proof-engine-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    output_dir = DEFAULT_OUTPUT_ROOT / run_tag
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = _now()

    if dry_run:
        plan = build_proof_engine_plan(
            run_id=run_tag,
            modules=selected_modules,
            profile=profile,
            analyte=analyte,
            include_frontier_tools=include_frontier_tools,
            include_promotion=include_promotion,
        )
        summary_path = output_dir / "proof_engine_plan.json"
        report_path = output_dir / "proof_engine_plan.md"
        _write_json(summary_path, plan)
        _write_review_markdown(
            report_path,
            [
                "# OAE Proof Engine Plan",
                "",
                f"- Run id: `{run_tag}`",
                f"- Profile: `{profile}`",
                *[
                    f"- Module `{module['module_slug']}` lanes: "
                    + ", ".join(lane["lane_id"] for lane in module["lanes"] + module["extras"])
                    for module in plan["modules"]
                ],
            ],
        )
        finished_at = _now()
        return ProofEngineResult(
            run_id=run_tag,
            profile=budget.name,
            output_dir=str(output_dir),
            started_at=started_at,
            finished_at=finished_at,
            modules=[],
            summary_path=str(summary_path),
            report_path=str(report_path),
        )

    harnesses = build_default_harnesses()
    module_results: list[ModuleExecution] = []
    for module_slug in selected_modules:
        module_dir = output_dir / module_slug
        harness = harnesses[module_slug]
        if module_slug == "riemann":
            module_results.append(
                _run_riemann_module(
                    run_id=run_tag,
                    module_dir=module_dir,
                    harness=harness,
                    budget=budget,
                    include_frontier_tools=include_frontier_tools,
                    include_promotion=include_promotion,
                )
            )
        elif module_slug == "rtap":
            module_results.append(
                _run_rtap_module(
                    run_id=run_tag,
                    module_dir=module_dir,
                    harness=harness,
                    budget=budget,
                )
            )
        elif module_slug == "sensing-studio":
            module_results.append(
                _run_sensing_module(
                    run_id=run_tag,
                    module_dir=module_dir,
                    harness=harness,
                    budget=budget,
                )
            )
    finished_at = _now()
    summary_path, report_path = _write_engine_summary(
        run_id=run_tag,
        profile=budget.name,
        output_dir=output_dir,
        started_at=started_at,
        finished_at=finished_at,
        modules=module_results,
    )
    return ProofEngineResult(
        run_id=run_tag,
        profile=budget.name,
        output_dir=str(output_dir),
        started_at=started_at,
        finished_at=finished_at,
        modules=module_results,
        summary_path=str(summary_path),
        report_path=str(report_path),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proof-engine",
        description="Run bounded proof-search orchestration across RH, RTAP, and sensing.",
    )
    parser.add_argument("--list-modules", action="store_true", help="List available proof-engine modules and exit.")
    parser.add_argument("--module", action="append", dest="modules", default=None, help="Module slug. Repeatable.")
    parser.add_argument("--profile", choices=("smoke", "standard"), default="smoke")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--analyte", default="glucose")
    parser.add_argument("--skip-frontier-tools", action="store_true")
    parser.add_argument("--include-promotion", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list_modules:
        print("Available proof-engine modules")
        print("=" * 40)
        for module in available_modules():
            print(module)
        print("=" * 40)
        return 0

    result = run_proof_engine(
        modules=tuple(args.modules) if args.modules else None,
        profile=args.profile,
        run_id=args.run_id,
        analyte=args.analyte,
        include_frontier_tools=not args.skip_frontier_tools,
        include_promotion=args.include_promotion,
        dry_run=args.dry_run,
    )
    print()
    print("Proof Engine Outputs")
    print("=" * 60)
    print(f"run_id   : {result.run_id}")
    print(f"profile  : {result.profile}")
    print(f"output   : {result.output_dir}")
    print(f"summary  : {result.summary_path}")
    print(f"report   : {result.report_path}")
    for module in result.modules:
        print(f"module   : {module.module_slug} -> {module.review_summary.get('verdict', 'unknown')}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
