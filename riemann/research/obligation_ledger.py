"""Normalization and ledger helpers for RH proof obligations."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


_VOCABULARY = (
    {
        "obligation_class": "off_line_zero_exclusion",
        "label": "Off-line-zero exclusion",
        "description": "The branch must exclude zeros away from the critical line, not just describe on-line structure.",
        "keywords": (
            "off-line zero",
            "off line zero",
            "zero-location exclusion",
            "exclude off-line",
            "exclude off line",
            "incompatible with off-line zeros",
        ),
        "resolution_threshold": 0.68,
    },
    {
        "obligation_class": "explicit_formula_tail_control",
        "label": "Explicit-formula tail control",
        "description": "Any explicit-formula argument must control error terms or tails globally.",
        "keywords": (
            "explicit formula",
            "error terms",
            "tail control",
            "tail bound",
            "prime oscillations",
        ),
        "resolution_threshold": 0.64,
    },
    {
        "obligation_class": "xi_coefficient_exclusion_bridge",
        "label": "Xi/coefficient exclusion bridge",
        "description": "Xi-function regularity or coefficient stability must be turned into an exclusion statement.",
        "keywords": (
            "xi-function",
            "xi function",
            "li/keiper",
            "jensen",
            "coefficient",
            "regularity into zero-location exclusion",
            "entire-function",
            "entire function",
        ),
        "resolution_threshold": 0.66,
    },
    {
        "obligation_class": "operator_non_surrogate_rigor",
        "label": "Operator rigor",
        "description": "Spectral or operator proposals must become rigorous constructions rather than surrogates.",
        "keywords": (
            "construct the operator rigorously",
            "self-adjoint operator construction",
            "promote any surrogate",
            "survive exact analysis",
            "rigorous self-adjoint",
        ),
        "resolution_threshold": 0.64,
    },
    {
        "obligation_class": "operator_uniqueness",
        "label": "Operator uniqueness",
        "description": "An operator-style program must rule out non-unique spectral surrogates.",
        "keywords": (
            "spectrum matches every non-trivial zero",
            "surrogate is not unique",
            "uniqueness",
            "matches every non-trivial zero",
        ),
        "resolution_threshold": 0.64,
    },
    {
        "obligation_class": "critical_line_to_global_exclusion",
        "label": "Critical-line to global exclusion",
        "description": "Local critical-line control must return as a global exclusion argument.",
        "keywords": (
            "critical-line control",
            "critical line control",
            "critical-line",
            "critical line",
            "surface-return",
            "surface return",
        ),
        "resolution_threshold": 0.65,
    },
    {
        "obligation_class": "space_construction_and_positivity",
        "label": "Space construction and positivity",
        "description": "Function-space approaches must close the space construction and positivity obligations.",
        "keywords": (
            "de branges",
            "space",
            "positivity",
            "closure conditions",
            "hermite-biehler",
        ),
        "resolution_threshold": 0.66,
    },
    {
        "obligation_class": "visual_or_surrogate_translation",
        "label": "Visual/surrogate translation",
        "description": "Descriptive intuition must be restated as a falsifiable invariant or exact operator claim.",
        "keywords": (
            "visual intuition",
            "rigorous invariant",
            "operator claim",
            "invariant excludes",
            "novelty requires translation",
            "translate",
        ),
        "resolution_threshold": 0.60,
    },
    {
        "obligation_class": "statistical_to_theorem_upgrade",
        "label": "Statistical-to-theorem upgrade",
        "description": "Statistical or density evidence must be upgraded into a theorem.",
        "keywords": (
            "probabilistic",
            "statistical evidence",
            "density results",
            "100 percent",
            "fractional-on-line",
            "fractional on-line",
        ),
        "resolution_threshold": 0.68,
    },
    {
        "obligation_class": "generic_obligation_formalization",
        "label": "Generic obligation formalization",
        "description": "A too-generic approach must be normalized into explicit proof obligations first.",
        "keywords": (
            "explicit proof obligations",
            "turn the approach into explicit proof obligations",
            "approach family is too generic",
        ),
        "resolution_threshold": 0.55,
    },
)

_VOCAB_BY_CLASS = {item["obligation_class"]: item for item in _VOCABULARY}


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in cleaned.split("_") if part)


def obligation_vocabulary() -> list[dict[str, Any]]:
    return [
        {
            "obligation_class": item["obligation_class"],
            "label": item["label"],
            "description": item["description"],
            "resolution_threshold": float(item["resolution_threshold"]),
        }
        for item in _VOCABULARY
    ]


def normalize_obligation(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if (
        any(token in lowered for token in ("xi-function", "xi function", "li/keiper", "li-keiper", "jensen"))
        and any(token in lowered for token in ("zero-location exclusion", "zero location exclusion", "regularity into zero-location exclusion"))
    ):
        item = _VOCAB_BY_CLASS["xi_coefficient_exclusion_bridge"]
        return {
            "obligation_id": _slug(text),
            "raw_text": text,
            "obligation_class": item["obligation_class"],
            "label": item["label"],
            "description": item["description"],
            "resolution_threshold": float(item["resolution_threshold"]),
        }
    for item in _VOCABULARY:
        if any(keyword in lowered for keyword in item["keywords"]):
            return {
                "obligation_id": _slug(text),
                "raw_text": text,
                "obligation_class": item["obligation_class"],
                "label": item["label"],
                "description": item["description"],
                "resolution_threshold": float(item["resolution_threshold"]),
            }
    fallback = _VOCAB_BY_CLASS["generic_obligation_formalization"]
    return {
        "obligation_id": _slug(text),
        "raw_text": text,
        "obligation_class": fallback["obligation_class"],
        "label": fallback["label"],
        "description": fallback["description"],
        "resolution_threshold": float(fallback["resolution_threshold"]),
    }


def certificate_progress_from_checks(check_results: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    progress: dict[str, dict[str, Any]] = {}
    for check in check_results:
        if str(check.get("category", "")) != "certificate":
            continue
        check_id = str(check.get("check_id", ""))
        metrics = {
            str(key): float(value)
            for key, value in dict(check.get("metrics", {}) or {}).items()
            if isinstance(value, (int, float))
        }
        contributions: list[tuple[str, float, str]] = []
        if check_id == "certificate_search":
            contributions.append(
                (
                    "off_line_zero_exclusion",
                    float(metrics.get("off_line_exclusion_margin", metrics.get("score", 0.0))),
                    "Measured explicit-formula exclusion margin against off-line zeros.",
                )
            )
        elif check_id == "explicit_formula_tail_control":
            contributions.append(
                (
                    "explicit_formula_tail_control",
                    float(
                        min(
                            metrics.get("tail_decay_margin", metrics.get("score", 0.0)),
                            metrics.get("error_budget_margin", metrics.get("score", 0.0)),
                            metrics.get("window_escape_margin", metrics.get("score", 0.0)),
                        )
                    ),
                    "Measured whether explicit-formula decay, error-budget, and window-escape margins support global tail control.",
                )
            )
        elif check_id == "variance_collapse_exclusion":
            contributions.append(
                (
                    "statistical_to_theorem_upgrade",
                    float(
                        min(
                            metrics.get("concentration_margin", metrics.get("score", 0.0)),
                            metrics.get("coverage_margin", metrics.get("score", 0.0)),
                            metrics.get("exclusion_link_margin", metrics.get("score", 0.0)),
                        )
                    ),
                    "Measured whether critical-line concentration survives the exceptional-zero burden strongly enough to support theorem-level upgrade.",
                )
            )
        elif check_id == "xi_coefficient_bridge":
            contributions.append(
                (
                    "xi_coefficient_exclusion_bridge",
                    float(
                        min(
                            metrics.get("li_keiper_margin", metrics.get("score", 0.0)),
                            metrics.get("jensen_margin", metrics.get("score", 0.0)),
                        )
                    ),
                    "Measured whether xi/coefficient stability can support an exclusion bridge.",
                )
            )
        elif check_id == "xi_tail_bridge":
            contributions.extend(
                (
                    (
                        "explicit_formula_tail_control",
                        float(metrics.get("tail_redeployment_margin", metrics.get("score", 0.0))),
                        "Measured whether the explicit-formula remainder budget can be redeployed through the xi-function lane strongly enough to clear the tail-control burden.",
                    ),
                    (
                        "xi_coefficient_exclusion_bridge",
                        float(metrics.get("coefficient_escape_margin", metrics.get("score", 0.0))),
                        "Measured whether the xi-function lane turns the remainder budget into a stronger coefficient/exclusion bridge.",
                    ),
                )
            )
        elif check_id == "zero_atlas_xi_bridge":
            contributions.extend(
                (
                    (
                        "xi_coefficient_exclusion_bridge",
                        float(
                            min(
                                metrics.get("counting_law_margin", metrics.get("score", 0.0)),
                                metrics.get("zero_sum_margin", metrics.get("score", 0.0)),
                                metrics.get("xi_bridge_margin", metrics.get("score", 0.0)),
                            )
                        ),
                        "Measured whether pi-normalized atlas structure can be converted into a xi-based exclusion bridge.",
                    ),
                    (
                        "visual_or_surrogate_translation",
                        float(
                            min(
                                metrics.get("contour_alignment_margin", metrics.get("score", 0.0)),
                                metrics.get("translation_margin", metrics.get("score", 0.0)),
                            )
                        ),
                        "Measured whether the zero atlas escaped descriptive visualization and became a calibrated invariant.",
                    ),
                )
            )
        elif check_id == "zero_atlas_exclusion":
            contributions.append(
                (
                    "off_line_zero_exclusion",
                    float(
                        min(
                            metrics.get("exclusion_link_margin", metrics.get("score", 0.0)),
                            metrics.get("theorem_upgrade_margin", metrics.get("score", 0.0)),
                        )
                    ),
                    "Measured whether the xi-facing zero atlas supports an actual off-line-zero exclusion step.",
                )
            )
        elif check_id == "surface_return_certificate":
            contributions.extend(
                (
                    (
                        "off_line_zero_exclusion",
                        float(metrics.get("return_margin", metrics.get("score", 0.0))),
                        "Measured whether the branch returns from local support to an exclusion claim.",
                    ),
                    (
                        "critical_line_to_global_exclusion",
                        float(metrics.get("obstruction_margin", metrics.get("score", 0.0))),
                        "Measured whether local critical-line structure reintegrates into a global exclusion obligation.",
                    ),
                )
            )
        elif check_id == "operator_non_surrogate_rigor":
            contributions.extend(
                (
                    (
                        "operator_non_surrogate_rigor",
                        float(metrics.get("rigor_margin", metrics.get("score", 0.0))),
                        "Measured whether the operator lane escaped surrogate-only reasoning.",
                    ),
                    (
                        "operator_uniqueness",
                        float(metrics.get("uniqueness_margin", metrics.get("score", 0.0))),
                        "Measured whether the operator lane shows enough uniqueness pressure.",
                    ),
                )
            )
        for obligation_class, margin, note in contributions:
            current = progress.get(obligation_class)
            threshold = float(_VOCAB_BY_CLASS[obligation_class]["resolution_threshold"])
            if current is not None and float(current.get("best_margin", 0.0)) >= margin:
                continue
            progress[obligation_class] = {
                "obligation_class": obligation_class,
                "best_margin": max(0.0, min(1.0, margin)),
                "resolution_threshold": threshold,
                "driver_check": check_id,
                "passed": max(0.0, min(1.0, margin)) >= threshold,
                "note": note,
            }
    return progress


def build_candidate_obligation_snapshot(
    *,
    candidate_id: str,
    round_index: int,
    raw_obligations: Iterable[str],
    check_results: Iterable[Mapping[str, Any]],
    score: float = 0.0,
    dead_end_patterns: Iterable[str] = (),
) -> dict[str, Any]:
    normalized = [normalize_obligation(item) for item in raw_obligations]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in normalized:
        grouped.setdefault(str(item["obligation_class"]), []).append(item)
    progress = certificate_progress_from_checks(check_results)

    obligation_reports: list[dict[str, Any]] = []
    resolved_classes: list[str] = []
    open_classes: list[str] = []
    for obligation_class, items in sorted(grouped.items()):
        progress_entry = progress.get(obligation_class)
        threshold = float(items[0]["resolution_threshold"])
        best_margin = float(progress_entry.get("best_margin", 0.0)) if progress_entry else 0.0
        if progress_entry is None:
            status = "open"
            reason = "No certificate check in this candidate addressed this obligation class directly."
        elif best_margin >= threshold:
            status = "resolved"
            reason = (
                f"{progress_entry['driver_check']} reached margin {best_margin:.3f}, "
                f"clearing the {threshold:.3f} resolution threshold."
            )
        else:
            status = "open"
            reason = (
                f"{progress_entry['driver_check']} only reached margin {best_margin:.3f}, "
                f"below the {threshold:.3f} resolution threshold."
            )
        record = {
            "obligation_class": obligation_class,
            "label": str(items[0]["label"]),
            "description": str(items[0]["description"]),
            "status": status,
            "best_margin": best_margin,
            "resolution_threshold": threshold,
            "driver_check": str(progress_entry.get("driver_check", "")) if progress_entry else "",
            "reason": reason,
            "raw_obligations": [str(item["raw_text"]) for item in items],
        }
        obligation_reports.append(record)
        if status == "resolved":
            resolved_classes.append(obligation_class)
        else:
            open_classes.append(obligation_class)

    reduction = len(resolved_classes) / max(len(grouped), 1)
    return {
        "candidate_id": candidate_id,
        "round_index": round_index,
        "score": float(score),
        "introduced_obligations": normalized,
        "obligation_reports": obligation_reports,
        "introduced_obligation_classes": sorted(grouped),
        "resolved_obligation_classes": tuple(sorted(resolved_classes)),
        "open_obligation_classes": tuple(sorted(open_classes)),
        "proof_obligation_reduction": reduction,
        "certificate_progress": progress,
        "dead_end_patterns": tuple(sorted(set(str(item) for item in dead_end_patterns))),
    }


def build_campaign_obligation_ledger(
    *,
    campaign_id: str,
    rounds: Iterable[Mapping[str, Any]],
    research_root: Path | None = None,
    campaign_dir: Path | None = None,
) -> dict[str, Any]:
    candidate_rows: list[dict[str, Any]] = []
    introduced_counts: Counter[str] = Counter()
    resolved_counts: Counter[str] = Counter()
    open_counts: Counter[str] = Counter()
    dead_end_counts: Counter[str] = Counter()

    for round_payload in rounds:
        round_index = int(round_payload.get("round_index", 0))
        hypotheses = {
            str(item.get("candidate_id", "")): item
            for item in round_payload.get("hypotheses", [])
        }
        for evaluation in round_payload.get("evaluations", []):
            candidate_id = str(evaluation.get("candidate_id", ""))
            hypothesis = hypotheses.get(candidate_id, {})
            snapshot = build_candidate_obligation_snapshot(
                candidate_id=candidate_id,
                round_index=round_index,
                raw_obligations=hypothesis.get("unresolved_proof_obligations", ()),
                check_results=evaluation.get("check_results", ()),
                score=float(evaluation.get("score", 0.0)),
                dead_end_patterns=evaluation.get("dead_end_patterns", ()),
            )
            candidate_rows.append(snapshot)
            introduced_counts.update(snapshot["introduced_obligation_classes"])
            resolved_counts.update(snapshot["resolved_obligation_classes"])
            open_counts.update(snapshot["open_obligation_classes"])
            dead_end_counts.update(snapshot["dead_end_patterns"])

    best_snapshot = max(
        candidate_rows,
        key=lambda item: (float(item.get("score", 0.0)), float(item.get("proof_obligation_reduction", 0.0))),
        default={},
    )
    summary = {
        "candidate_count": len(candidate_rows),
        "average_obligation_reduction": (
            sum(float(item.get("proof_obligation_reduction", 0.0)) for item in candidate_rows) / max(len(candidate_rows), 1)
        ),
        "introduced_counts": dict(sorted(introduced_counts.items())),
        "resolved_counts": dict(sorted(resolved_counts.items())),
        "open_counts": dict(sorted(open_counts.items())),
        "top_unresolved_obligations": [
            {"obligation_class": name, "count": count}
            for name, count in sorted(open_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
        "repeated_dead_end_patterns": [
            {"pattern_id": name, "count": count}
            for name, count in sorted(dead_end_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
        "best_candidate_id": str(best_snapshot.get("candidate_id", "")),
        "best_candidate_reduction": float(best_snapshot.get("proof_obligation_reduction", 0.0)),
    }
    ledger = {
        "campaign_id": campaign_id,
        "vocabulary": obligation_vocabulary(),
        "candidates": candidate_rows,
        "summary": summary,
    }
    if research_root is not None:
        ledger["research_root_rollup"] = build_research_root_rollup(
            research_root=research_root,
            current_ledger=ledger,
            current_campaign_dir=campaign_dir,
        )
    return ledger


def build_research_root_rollup(
    *,
    research_root: Path,
    current_ledger: Mapping[str, Any],
    current_campaign_dir: Path | None = None,
) -> dict[str, Any]:
    open_counts: Counter[str] = Counter()
    resolved_counts: Counter[str] = Counter()
    campaign_count = 0

    for path in sorted(research_root.glob("*/obligation_ledger.json")):
        if current_campaign_dir is not None and path.parent == current_campaign_dir:
            continue
        try:
            payload = json.loads(path.read_text())
        except Exception:
            continue
        campaign_count += 1
        open_counts.update(dict(payload.get("summary", {}).get("open_counts", {})))
        resolved_counts.update(dict(payload.get("summary", {}).get("resolved_counts", {})))

    campaign_count += 1
    open_counts.update(dict(current_ledger.get("summary", {}).get("open_counts", {})))
    resolved_counts.update(dict(current_ledger.get("summary", {}).get("resolved_counts", {})))
    return {
        "campaign_count": campaign_count,
        "open_counts": dict(sorted(open_counts.items())),
        "resolved_counts": dict(sorted(resolved_counts.items())),
        "top_open_obligations": [
            {"obligation_class": name, "count": count}
            for name, count in sorted(open_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }
