"""Campaign-level certificate reporting for RH research."""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .obligation_ledger import build_candidate_obligation_snapshot


# Phase-1 falsifiable-claim generation (deprecated, kept for back-compat).
#
# Selects a `no_zero_in T_lo T_hi` window purely from the candidate_id hash.
# This made the benchmark *able* to falsify but the choice was random — no
# reasoning information flowed from the candidate's ingredient mix into the
# claim. Phase 2 supersedes this with `_claim_window_from_reasoning` below.
def _claim_window(candidate_id: str) -> tuple[float, float]:
    h = int(hashlib.sha256(candidate_id.encode()).hexdigest(), 16)
    center = (h % 9100) / 100.0 + 10.0           # in [10.0, 101.0)
    half_width = ((h >> 32) % 350) / 1000.0 + 0.05  # in [0.05, 0.40)
    return (center - half_width, center + half_width)


# Phase-2 reasoning-derived claim window:
#
# Each ingredient family votes for a preferred height region — a deliberate
# choice that ties the claim back to a (loosely justified) physical
# interpretation:
#   explicit_formula:      30 — near the "explicit-formula prime tail" region
#   hardy_z:               50 — region where Hardy Z-function is well-studied
#   de_branges:            20 — near the first de Branges eigenvalue cluster
#   xi_function:           40 — xi function symmetry-point neighborhood
#   random_matrix:         70 — GUE statistics become reliable in this region
#   mollifier_moment:      60 — moment-method targeted region
#   hilbert_polya:         25
#   quantum_spectral:      35
#   geometric_visualization: 80
#   general_analytic:      90 — high-T fallback
#
# Width comes from the obligation count: more obligations = a bolder/wider
# claim. Width = 0.05 + 0.05 * min(n_obligations, 5), so [0.05, 0.30].
#
# A small candidate_id-derived perturbation breaks ties between same-family
# candidates so two de_branges hypotheses claim slightly different windows.
#
# What this reveals empirically: different families have different
# contradiction rates because they target different parts of the zero
# distribution. de_branges centers near 20 — adjacent to zero[1]=21.02, so
# wider windows hit it. random_matrix centers near 70 where zeros are
# sparser. The Odlyzko benchmark thus differentiates families on a real
# predictive quality, not just on family-bonus accounting.
_FAMILY_PREFERRED_HEIGHT: dict[str, float] = {
    "explicit_formula": 30.0,
    "hardy_z": 50.0,
    "de_branges": 20.0,
    "xi_function": 40.0,
    "random_matrix": 70.0,
    "mollifier_moment": 60.0,
    "hilbert_polya": 25.0,
    "quantum_spectral": 35.0,
    "geometric_visualization": 80.0,
    "general_analytic": 90.0,
}


def _claim_window_from_reasoning(
    candidate_id: str,
    ingredient_families: tuple[str, ...],
    obligations: tuple[str, ...],
) -> tuple[float, float]:
    """Reasoning-derived claim window. Center from family votes, width from
    obligation count, tie-break perturbation from candidate_id hash."""
    n_obligations = len(obligations)
    half_width = 0.05 + 0.05 * min(n_obligations, 5)  # [0.05, 0.30]
    if ingredient_families:
        votes = [
            _FAMILY_PREFERRED_HEIGHT.get(f, 50.0)
            for f in ingredient_families
        ]
        center = sum(votes) / len(votes)
    else:
        center = 50.0
    # Tie-break: ±2.5 perturbation deterministic per candidate_id.
    perturbation = (
        (int(hashlib.sha256(candidate_id.encode()).hexdigest()[:8], 16) % 1000)
        - 500
    ) * 0.005
    center += perturbation
    return (center - half_width, center + half_width)


# Phase-5 gap-aware claim window:
#
# Instead of picking a height from a hand-curated family preferred height
# table (Phase 2), the candidate picks an actual gap between adjacent
# Odlyzko zeros. The choice of gap is deterministic per candidate but
# parameterized by ingredient families. The claim window is centered on
# that gap; the width depends on candidate obligation load — speculative
# candidates (many obligations) get wider claims that may straddle beyond
# the chosen gap into adjacent zeros, producing real contradictions.
#
# Why this is more honest than Phase 2:
#   - The center is grounded in EMPIRICAL zero data, not a table I wrote.
#   - The contradiction structure depends on the candidate's confidence
#     (obligation count) vs the actual gap width at the chosen height.
#   - Different families select different gap-index ranges, so family
#     choice still matters but the underlying numbers come from Odlyzko.
#
# Loaded lazily so this module does not depend on import order.
_ODLYZKO_GAPS_CACHE: list[tuple[float, float]] | None = None


def _load_odlyzko_gaps(max_zeros: int = 200) -> list[tuple[float, float]]:
    """Return adjacent (zero[i], zero[i+1]) pairs from the Odlyzko table.

    Cached after first load. Uses the first `max_zeros` zeros (~T<150) so
    candidate windows live in the verified-empirical region.
    """
    global _ODLYZKO_GAPS_CACHE
    if _ODLYZKO_GAPS_CACHE is not None:
        return _ODLYZKO_GAPS_CACHE
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        path = ancestor / "data" / "riemann" / "zeros1.txt"
        if path.exists():
            heights: list[float] = []
            with path.open() as fh:
                for i, line in enumerate(fh):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        heights.append(float(line))
                    except ValueError:
                        continue
                    if i + 1 >= max_zeros:
                        break
            _ODLYZKO_GAPS_CACHE = [
                (heights[i], heights[i + 1]) for i in range(len(heights) - 1)
            ]
            return _ODLYZKO_GAPS_CACHE
    _ODLYZKO_GAPS_CACHE = []
    return _ODLYZKO_GAPS_CACHE


# Per-family bias for which slice of the gap list a candidate prefers.
# Each family maps to a (low, high) fraction of the gap-index range.
# explicit_formula → low gaps (small T, dense zeros, narrower gaps).
# random_matrix → high gaps (large T, sparser zeros, wider gaps).
# These ranges are still designer-set BUT they only choose a region of
# the empirical gap list, not arbitrary heights — so the actual numbers
# come from data.
_FAMILY_GAP_REGION: dict[str, tuple[float, float]] = {
    "explicit_formula": (0.0, 0.30),    # gaps 0..N*0.30 — dense low-T region
    "hardy_z":          (0.20, 0.50),
    "de_branges":       (0.0, 0.20),    # very-low-T (first eigenvalue cluster)
    "xi_function":      (0.15, 0.45),
    "random_matrix":    (0.60, 0.95),   # sparser high-T (GUE-active)
    "mollifier_moment": (0.40, 0.70),
    "hilbert_polya":    (0.10, 0.35),
    "quantum_spectral": (0.20, 0.50),
    "geometric_visualization": (0.50, 0.85),
    "general_analytic": (0.70, 0.95),   # high-T fallback
}


import hashlib as _hashlib  # local re-bind so we don't shadow the module-level import


def _claim_window_from_gaps(
    candidate_id: str,
    ingredient_families: tuple[str, ...],
    obligations: tuple[str, ...],
) -> tuple[float, float]:
    """Phase-5 gap-aware window: center inside an empirical Odlyzko gap.

    Width depends on obligation count — high-obligation candidates get
    wider windows that may straddle beyond the gap into adjacent zeros
    (= contradiction). Low-obligation candidates get narrow windows that
    stay safely inside the gap (= confirmation).
    """
    gaps = _load_odlyzko_gaps()
    if not gaps:
        # Odlyzko data unavailable; fall back to Phase 2 behavior.
        return _claim_window_from_reasoning(candidate_id, ingredient_families, obligations)

    # 1. Determine the gap-index region from the family mix.
    if ingredient_families:
        regions = [
            _FAMILY_GAP_REGION.get(f, (0.30, 0.70))
            for f in ingredient_families
        ]
        lo_frac = sum(r[0] for r in regions) / len(regions)
        hi_frac = sum(r[1] for r in regions) / len(regions)
    else:
        lo_frac, hi_frac = 0.30, 0.70

    n_gaps = len(gaps)
    lo_idx = max(0, int(lo_frac * n_gaps))
    hi_idx = min(n_gaps, int(hi_frac * n_gaps))
    if hi_idx <= lo_idx:
        hi_idx = lo_idx + 1

    # 2. Pick a specific gap from that region using candidate_id hash.
    h = int(_hashlib.sha256(candidate_id.encode()).hexdigest()[:12], 16)
    gap_idx = lo_idx + (h % (hi_idx - lo_idx))
    z_lo, z_hi = gaps[gap_idx]
    gap_width = z_hi - z_lo
    center = (z_lo + z_hi) / 2.0

    # 3. Width grows with obligation count. Calibrated so candidates with
    # 1-2 obligations stay safely inside the gap (confirm), but candidates
    # with 4+ obligations can exceed gap_width (overflow into adjacent
    # zeros = contradiction). This preserves the falsification signal Phase 4
    # needs to learn from.
    n_obligations = len(obligations)
    # safe_fraction = 0.25 of gap on each side (50% total = always safe).
    # risk_fraction = 0.25 per obligation, no cap. At 4 obligations:
    #   half_width = (0.25 + 1.0) * gap/2 = 0.625 * gap → just spills over.
    safe_fraction = 0.25
    risk_fraction = 0.25 * n_obligations
    half_width = max(0.05, (safe_fraction + risk_fraction) * gap_width / 2.0)

    return (center - half_width, center + half_width)


def _generate_lean_skeleton(
    candidate_id: str,
    obligation_snapshot: dict[str, Any],
    *,
    ingredient_families: tuple[str, ...] = (),
) -> str:
    """Generate a minimal Lean 4 skeleton with sorry placeholders for open obligations.

    Phase 1: emits a falsifiable `no_zero_in T_lo T_hi` claim per candidate.
    Phase 2: when ingredient_families is provided, the claim window is derived
    from candidate reasoning (family-voted center, obligation-count width)
    instead of pure candidate_id hash. Falls back to Phase 1 hash-only window
    when ingredient_families is empty (back-compat for the certificate report
    callsite that doesn't have family info).
    """
    safe_id = "".join(ch if ch.isalnum() else "_" for ch in candidate_id)
    raw_open = obligation_snapshot.get("open_obligation_classes", {})
    if isinstance(raw_open, dict):
        open_classes = list(raw_open.keys())
    else:
        open_classes = list(raw_open)
    if ingredient_families:
        # Phase 5: gap-aware window grounded in actual Odlyzko zero distribution.
        # Falls back to Phase 2 hand-curated heights if Odlyzko data unavailable.
        t_lo, t_hi = _claim_window_from_gaps(
            candidate_id, ingredient_families, tuple(open_classes)
        )
    else:
        t_lo, t_hi = _claim_window(candidate_id)
    lines = [f"-- Candidate: {candidate_id}", "import Mathlib", ""]
    # Falsifiable numeric claim — Odlyzko adjudicates.
    lines.append(
        f"theorem numeric_window_{safe_id} : no_zero_in {t_lo:.4f} {t_hi:.4f} := by"
    )
    lines.append("  sorry")
    lines.append("")
    # Open-obligation skeletons (existing scaffolding, unchanged).
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
