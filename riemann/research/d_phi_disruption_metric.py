"""Mechanical metric for D_phi RH proof-gate frontier artifacts.

This module deliberately scores proof-gate *readiness*, not an RH proof.  A
high raw campaign score is capped until the artifact reduces the remaining
core theorem obligations: analytic xi bridge, global off-line exclusion, and
uniform tail recombination.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CORE_OPEN_OBLIGATIONS = frozenset(
    {
        "analytic_xi_bridge_theorem",
        "global_off_line_exclusion_theorem",
        "uniform_tail_recombination_theorem",
    }
)


@dataclass(frozen=True)
class DPhiMetric:
    score: float
    raw_score: float
    d_phi_gap: float
    d_phi_cleared: bool
    open_core_obligations: tuple[str, ...]
    reduced_core_obligations: tuple[str, ...]
    path: Path | None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _candidate_paths(research_dir: Path) -> list[Path]:
    return sorted(research_dir.glob("rh-*/summary.json"))


def _is_relevant(summary_path: Path, summary: dict[str, Any]) -> bool:
    campaign_id = str(summary.get("campaign_id") or summary_path.parent.name)
    return any(token in campaign_id for token in ("d-phi", "disrupt", "self-dual"))


def _repo_root_for_campaign(campaign_dir: Path) -> Path:
    try:
        return campaign_dir.parents[3]
    except IndexError:
        return Path.cwd()


def _lean_decl_present(lean_path: Path, decl_name: str) -> bool:
    try:
        from .lean_bridge import verify_file
    except Exception:
        return False
    result = verify_file(lean_path, backend="mock")
    return result.passed and decl_name in result.decls


def _evidence_backed_reductions(candidate: dict[str, Any], campaign_dir: Path) -> set[str]:
    """Return core obligations reduced by auditable, non-proof-claim evidence."""
    reduced: set[str] = set()
    repo_root = _repo_root_for_campaign(campaign_dir)
    open_core = set(candidate.get("open_obligation_classes", ())) & CORE_OPEN_OBLIGATIONS

    for item in candidate.get("core_obligation_reduction_evidence", []):
        if not isinstance(item, dict):
            continue
        obligation = str(item.get("core_obligation", ""))
        if obligation not in open_core:
            continue
        if bool(item.get("rh_proof_claim")):
            continue
        if item.get("mechanical_check") != "mock_lean_bridge_decl_present":
            continue
        if not item.get("reduced_to"):
            continue

        lean_path = Path(str(item.get("lean_path", "")))
        if not lean_path:
            continue
        if not lean_path.is_absolute():
            lean_path = repo_root / lean_path

        decl_name = str(item.get("lean_declaration", ""))
        if decl_name and _lean_decl_present(lean_path, decl_name):
            reduced.add(obligation)

    return reduced


def _certificate_metrics(campaign_dir: Path) -> tuple[float, bool, tuple[str, ...], tuple[str, ...]]:
    certificate = _read_json(campaign_dir / "certificate_report.json")
    best_gap = 1.0
    d_phi_cleared = False
    open_core: set[str] = set()
    reduced_core: set[str] = set()

    for candidate in certificate.get("candidate_reports", []):
        if isinstance(candidate, dict):
            for obligation in candidate.get("open_obligation_classes", []):
                if obligation in CORE_OPEN_OBLIGATIONS:
                    open_core.add(str(obligation))
            reduced_core.update(_evidence_backed_reductions(candidate, campaign_dir))
            for lane in candidate.get("lane_reports", []):
                if not isinstance(lane, dict):
                    continue
                if lane.get("check_id") != "d_phi_formalization":
                    continue
                metrics = lane.get("metrics", {})
                if isinstance(metrics, dict):
                    try:
                        best_gap = min(best_gap, float(metrics.get("threshold_gap", 1.0)))
                    except (TypeError, ValueError):
                        pass
                d_phi_cleared = d_phi_cleared or bool(lane.get("passed"))

    reduced_core &= open_core
    effective_open = open_core - reduced_core
    return best_gap, d_phi_cleared, tuple(sorted(effective_open)), tuple(sorted(reduced_core))


def score_research_dir(research_dir: Path) -> DPhiMetric:
    """Return the best gated D_phi disruption score under ``research_dir``."""
    best = DPhiMetric(
        score=0.0,
        raw_score=0.0,
        d_phi_gap=1.0,
        d_phi_cleared=False,
        open_core_obligations=tuple(sorted(CORE_OPEN_OBLIGATIONS)),
        reduced_core_obligations=(),
        path=None,
    )

    for summary_path in _candidate_paths(research_dir):
        summary = _read_json(summary_path)
        if not summary or not _is_relevant(summary_path, summary):
            continue
        try:
            raw_score = float(summary.get("best_score") or 0.0)
        except (TypeError, ValueError):
            raw_score = 0.0

        gap, d_phi_cleared, open_core, reduced_core = _certificate_metrics(summary_path.parent)
        open_count = len(open_core)
        closed_count = len(CORE_OPEN_OBLIGATIONS) - open_count

        # Cap scaffold-only artifacts below 0.95.  Each closed core obligation
        # earns promotion headroom while preserving the raw campaign ceiling.
        obligation_adjusted = 0.945 + 0.011 * closed_count
        if d_phi_cleared:
            obligation_adjusted += 0.004
        score = min(raw_score, obligation_adjusted)

        if score > best.score:
            best = DPhiMetric(
                score=score,
                raw_score=raw_score,
                d_phi_gap=gap,
                d_phi_cleared=d_phi_cleared,
                open_core_obligations=open_core,
                reduced_core_obligations=reduced_core,
                path=summary_path,
            )

    return best


def main() -> int:
    metric = score_research_dir(Path("data/riemann/research"))
    print(
        "score={score:.6f} raw_score={raw:.6f} d_phi_gap={gap:.6f} "
        "d_phi_cleared={cleared} open_core_obligations={open_count} "
        "reduced_core_obligations={reduced_count} path={path}".format(
            score=metric.score,
            raw=metric.raw_score,
            gap=metric.d_phi_gap,
            cleared=int(metric.d_phi_cleared),
            open_count=len(metric.open_core_obligations),
            reduced_count=len(metric.reduced_core_obligations),
            path=metric.path or "",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
