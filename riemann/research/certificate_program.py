"""Campaign-level certificate reporting for RH research."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .obligation_ledger import build_candidate_obligation_snapshot


def _generate_lean_skeleton(candidate_id: str, obligation_snapshot: dict[str, Any]) -> str:
    """Generate a minimal Lean 4 skeleton with sorry placeholders for open obligations."""
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in candidate_id)
    open_classes = list(obligation_snapshot.get("open_obligation_classes", {}).keys())
    lines = [f"-- Candidate: {candidate_id}", "import Mathlib", ""]
    for i, cls in enumerate(open_classes[:4]):
        safe_cls = "".join(ch if ch.isalnum() else "_" for ch in cls)
        lines.append(f"theorem obligation_{safe_id}_{i} : sorry_obligation_{safe_cls} := by")
        lines.append("  sorry")
        lines.append("")
    if not open_classes:
        lines.append(f"theorem candidate_{safe_id}_placeholder : True := by")
        lines.append("  trivial")
        lines.append("")
    return "\n".join(lines)


def build_certificate_report(
    *,
    campaign_id: str,
    rounds: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_reports: list[dict[str, Any]] = []
    class_open_counts: Counter[str] = Counter()
    class_resolved_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    lane_passed_counts: Counter[str] = Counter()
    lane_best_scores: dict[str, tuple[float, str, int]] = {}

    for round_payload in rounds:
        round_index = int(round_payload.get("round_index", 0))
        hypotheses = {
            str(item.get("candidate_id", "")): item
            for item in round_payload.get("hypotheses", [])
        }
        for evaluation in round_payload.get("evaluations", []):
            candidate_id = str(evaluation.get("candidate_id", ""))
            hypothesis = hypotheses.get(candidate_id, {})
            checks = [
                dict(item)
                for item in evaluation.get("check_results", [])
                if str(item.get("category", "")) == "certificate"
            ]
            if not checks and not hypothesis.get("unresolved_proof_obligations"):
                continue
            snapshot = build_candidate_obligation_snapshot(
                candidate_id=candidate_id,
                round_index=round_index,
                raw_obligations=hypothesis.get("unresolved_proof_obligations", ()),
                check_results=checks,
                score=float(evaluation.get("score", 0.0)),
                dead_end_patterns=evaluation.get("dead_end_patterns", ()),
            )
            lane_reports = []
            for check in checks:
                metrics = {
                    str(key): float(value)
                    for key, value in dict(check.get("metrics", {}) or {}).items()
                    if isinstance(value, (int, float))
                }
                lane = str(check.get("check_id", ""))
                score = float(metrics.get("score", 0.0))
                lane_counts[lane] += 1
                if bool(check.get("passed", False)):
                    lane_passed_counts[lane] += 1
                current = lane_best_scores.get(lane)
                if current is None or score >= current[0]:
                    lane_best_scores[lane] = (score, candidate_id, round_index)
                lane_reports.append(
                    {
                        "check_id": lane,
                        "passed": bool(check.get("passed", False)),
                        "summary": str(check.get("summary", "")),
                        "detail_path": str(check.get("detail_path", "")),
                        "metrics": metrics,
                    }
                )

            class_open_counts.update(snapshot["open_obligation_classes"])
            class_resolved_counts.update(snapshot["resolved_obligation_classes"])
            margins = [float(item.get("metrics", {}).get("score", 0.0)) for item in lane_reports]
            candidate_reports.append(
                {
                    "candidate_id": candidate_id,
                    "round_index": round_index,
                    "score": float(evaluation.get("score", 0.0)),
                    "families": tuple(str(item) for item in hypothesis.get("ingredient_families", ())),
                    "lane_reports": lane_reports,
                    "obligation_reports": snapshot["obligation_reports"],
                    "resolved_obligation_classes": snapshot["resolved_obligation_classes"],
                    "open_obligation_classes": snapshot["open_obligation_classes"],
                    "proof_obligation_reduction": snapshot["proof_obligation_reduction"],
                    "lean_skeleton": _generate_lean_skeleton(candidate_id, snapshot),
                    "margin_summary": {
                        "checks_run": len(lane_reports),
                        "checks_passed": sum(1 for item in lane_reports if item["passed"]),
                        "best_margin": max(margins, default=0.0),
                        "average_margin": sum(margins) / max(len(margins), 1),
                    },
                }
            )

    class_summary = []
    all_classes = sorted({*class_open_counts, *class_resolved_counts})
    for obligation_class in all_classes:
        resolved = int(class_resolved_counts.get(obligation_class, 0))
        open_count = int(class_open_counts.get(obligation_class, 0))
        class_summary.append(
            {
                "obligation_class": obligation_class,
                "resolved_count": resolved,
                "open_count": open_count,
                "net_reduction": resolved - open_count,
            }
        )
    class_summary.sort(key=lambda item: (-item["open_count"], item["obligation_class"]))

    lane_summary = []
    for lane in sorted(lane_counts):
        best_score, best_candidate_id, best_round = lane_best_scores.get(lane, (0.0, "", 0))
        lane_summary.append(
            {
                "check_id": lane,
                "count": int(lane_counts[lane]),
                "passed_count": int(lane_passed_counts.get(lane, 0)),
                "best_score": float(best_score),
                "best_candidate_id": str(best_candidate_id),
                "best_round_index": int(best_round),
            }
        )
    lane_summary.sort(key=lambda item: (-item["best_score"], item["check_id"]))

    return {
        "campaign_id": campaign_id,
        "candidate_reports": candidate_reports,
        "summary": {
            "candidate_count": len(candidate_reports),
            "total_certificate_checks": sum(int(item["count"]) for item in lane_summary),
            "passed_certificate_checks": sum(int(item["passed_count"]) for item in lane_summary),
            "obligation_class_summary": class_summary,
            "lane_summary": lane_summary,
        },
    }
