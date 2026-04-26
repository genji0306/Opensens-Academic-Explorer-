"""Comparative benchmark harness for RH research campaigns."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def infer_benchmark_mode(
    *,
    summary: dict[str, Any],
    certificate_report: dict[str, Any] | None = None,
) -> str:
    topology_mode = str(summary.get("topology_mode", "baseline"))
    if topology_mode == "klein":
        return "klein"

    seed_pack_names = [str(item).lower() for item in summary.get("seed_pack_names", ())]
    if any("proof-attempt" in item or "proof_attempt" in item for item in seed_pack_names):
        return "proof_attempt_corpus"

    family_usage = {str(key): int(value) for key, value in dict(summary.get("family_usage", {})).items()}
    operator_weight = sum(
        family_usage.get(name, 0)
        for name in ("hilbert_polya", "quantum_spectral", "random_matrix", "de_branges")
    )
    total_weight = sum(family_usage.values()) or 1
    if operator_weight / total_weight >= 0.45:
        return "spectral_operator_heavy"

    total_checks = int((certificate_report or {}).get("summary", {}).get("total_certificate_checks", 0))
    if total_checks >= max(4, int(summary.get("rounds_run", 0))):
        return "certificate_heavy"
    return "baseline"


def build_campaign_benchmark(
    *,
    research_root: Path,
    current_campaign_dir: Path,
    current_summary: dict[str, Any],
    current_certificate_report: dict[str, Any],
    current_obligation_ledger: dict[str, Any],
    current_failure_atlas: dict[str, Any],
) -> dict[str, Any]:
    current_id = str(current_summary.get("campaign_id", current_campaign_dir.name))
    records_by_campaign: dict[str, dict[str, Any]] = {}

    def _record_from_payloads(
        *,
        campaign_dir: Path,
        summary: dict[str, Any],
        certificate_report: dict[str, Any],
        obligation_ledger: dict[str, Any],
        failure_atlas: dict[str, Any],
    ) -> dict[str, Any]:
        best_review = dict(summary.get("best_candidate_review", {}))
        return {
            "campaign_id": str(summary.get("campaign_id", campaign_dir.name)),
            "campaign_dir": str(campaign_dir),
            "benchmark_mode": infer_benchmark_mode(summary=summary, certificate_report=certificate_report),
            "seed_pack_names": tuple(summary.get("seed_pack_names", ())),
            "topology_mode": str(summary.get("topology_mode", "baseline")),
            "best_score": float(summary.get("best_score", 0.0)),
            "best_candidate_id": str(summary.get("best_candidate_id", "")),
            "top_family_mix": tuple(best_review.get("ingredient_families", ())),
            "obligation_reduction": float(
                best_review.get(
                    "proof_obligation_reduction",
                    obligation_ledger.get("summary", {}).get("best_candidate_reduction", 0.0),
                )
            ),
            "dominant_failures": [
                str(item[0])
                for item in sorted(
                    dict(failure_atlas.get("failure_counts", {})).items(),
                    key=lambda item: (-item[1], item[0]),
                )[:3]
            ],
            "artifact_quality": float(best_review.get("artifact_quality", 0.0)),
        }

    for campaign_dir in sorted(path for path in research_root.glob("*") if path.is_dir()):
        summary_path = campaign_dir / "summary.json"
        if not summary_path.exists():
            continue
        summary = _read_json(summary_path)
        certificate_report = _read_json(campaign_dir / "certificate_report.json")
        obligation_ledger = _read_json(campaign_dir / "obligation_ledger.json")
        failure_atlas = _read_json(campaign_dir / "failure_atlas.json")
        record = _record_from_payloads(
            campaign_dir=campaign_dir,
            summary=summary,
            certificate_report=certificate_report,
            obligation_ledger=obligation_ledger,
            failure_atlas=failure_atlas,
        )
        records_by_campaign[str(record["campaign_id"])] = record

    records_by_campaign[current_id] = _record_from_payloads(
        campaign_dir=current_campaign_dir,
        summary=current_summary,
        certificate_report=current_certificate_report,
        obligation_ledger=current_obligation_ledger,
        failure_atlas=current_failure_atlas,
    )
    records = list(records_by_campaign.values())
    current_group = tuple(current_summary.get("seed_pack_names", ()))
    for record in records:
        record["comparable_to_current"] = tuple(record["seed_pack_names"]) == current_group

    records.sort(key=lambda item: (-float(item["best_score"]), item["campaign_id"]))
    mode_rows = {}
    for record in records:
        mode = str(record["benchmark_mode"])
        entry = mode_rows.setdefault(
            mode,
            {
                "benchmark_mode": mode,
                "campaign_count": 0,
                "score_total": 0.0,
                "obligation_reduction_total": 0.0,
                "best_score": 0.0,
                "best_campaign_id": "",
            },
        )
        entry["campaign_count"] += 1
        entry["score_total"] += float(record["best_score"])
        entry["obligation_reduction_total"] += float(record["obligation_reduction"])
        if float(record["best_score"]) >= float(entry["best_score"]):
            entry["best_score"] = float(record["best_score"])
            entry["best_campaign_id"] = str(record["campaign_id"])

    mode_summary = []
    for entry in mode_rows.values():
        count = max(1, int(entry["campaign_count"]))
        mode_summary.append(
            {
                "benchmark_mode": entry["benchmark_mode"],
                "campaign_count": int(entry["campaign_count"]),
                "average_best_score": float(entry["score_total"]) / count,
                "average_obligation_reduction": float(entry["obligation_reduction_total"]) / count,
                "best_score": float(entry["best_score"]),
                "best_campaign_id": str(entry["best_campaign_id"]),
            }
        )
    mode_summary.sort(key=lambda item: (-item["best_score"], item["benchmark_mode"]))

    current_index = next((idx for idx, item in enumerate(records, start=1) if item["campaign_id"] == current_id), 0)
    comparable_records = [item for item in records if item["comparable_to_current"]]
    group_rank = next((idx for idx, item in enumerate(comparable_records, start=1) if item["campaign_id"] == current_id), 0)
    group_best_score = max((float(item["best_score"]) for item in comparable_records), default=0.0)

    return {
        "campaign_id": current_id,
        "benchmark_mode": infer_benchmark_mode(
            summary=current_summary,
            certificate_report=current_certificate_report,
        ),
        "leaderboard": records,
        "mode_summary": mode_summary,
        "current_vs_comparable": {
            "current_rank_overall": current_index,
            "current_rank_in_group": group_rank,
            "comparison_group_size": len(comparable_records),
            "delta_vs_group_best_score": float(current_summary.get("best_score", 0.0)) - group_best_score,
            "current_best_obligation_reduction": float(
                current_summary.get("best_candidate_review", {}).get(
                    "proof_obligation_reduction",
                    current_obligation_ledger.get("summary", {}).get("best_candidate_reduction", 0.0),
                )
            ),
            "current_dominant_failures": [
                str(item[0])
                for item in sorted(
                    dict(current_failure_atlas.get("failure_counts", {})).items(),
                    key=lambda item: (-item[1], item[0]),
                )[:3]
            ],
        },
    }
