"""Metric forecasting adapter for Timeguard.

This module prefers a TimesFM-backed path when the package is installed and
explicitly enabled, but it always supports a deterministic local fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from statistics import median
from typing import Iterable

from src.oae.studios.timeguard.schemas import CampaignEvidence, MetricForecast, RoundSignal

try:  # pragma: no cover - optional dependency path
    import timesfm as _timesfm  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    _timesfm = None

_CORE_METRICS = (
    "best_score",
    "certificate_pass_rate",
    "global_exclusion_gap",
    "tail_control_gap",
    "translation_gap",
)
_BOUND_METRICS = {"best_score", "certificate_pass_rate"}
_GAP_METRICS = {"global_exclusion_gap", "tail_control_gap", "translation_gap"}


@dataclass(frozen=True)
class AuxiliarySnapshot:
    campaign_id: str
    metrics: dict[str, float]


class TimesFMAdapter:
    """Forecast per-round RH campaign metrics with a safe local fallback."""

    def __init__(self) -> None:
        self.timesfm_enabled = bool(_timesfm is not None and os.getenv("TIMEGUARD_ENABLE_TIMESFM") == "1")

    def forecast_campaign(
        self,
        campaign: CampaignEvidence,
        *,
        horizon: int = 2,
    ) -> MetricForecast:
        dead_end_metrics = _select_dead_end_metrics(campaign)
        primary_series = _primary_metric_series(campaign, dead_end_metrics)
        auxiliary = _auxiliary_snapshots(campaign, dead_end_metrics)
        point_forecast, quantile_forecast = self._forecast_metrics(
            primary_series,
            auxiliary,
            horizon=horizon,
        )
        confidence = _forecast_confidence(primary_series, auxiliary, backend=self.backend_name)
        evidence_refs = (
            campaign.campaign_benchmark_path,
            campaign.failure_atlas_path,
            campaign.summary_path,
        )
        return MetricForecast(
            orchestrator_id=campaign.orchestrator_id,
            topology_mode=campaign.topology_mode,
            backend=self.backend_name,
            horizon=horizon,
            confidence=confidence,
            point_forecast=point_forecast,
            quantile_forecast=quantile_forecast,
            selected_dead_end_metrics=dead_end_metrics,
            auxiliary_campaign_ids=tuple(item.campaign_id for item in auxiliary),
            evidence_refs=evidence_refs,
        )

    @property
    def backend_name(self) -> str:
        if self.timesfm_enabled:
            return "timesfm_requested_fallback_bridge"
        return "heuristic_fallback"

    def _forecast_metrics(
        self,
        primary_series: dict[str, list[float]],
        auxiliary: list[AuxiliarySnapshot],
        *,
        horizon: int,
    ) -> tuple[dict[str, tuple[float, ...]], dict[str, dict[str, tuple[float, ...]]]]:
        points: dict[str, tuple[float, ...]] = {}
        quantiles: dict[str, dict[str, tuple[float, ...]]] = {}
        auxiliary_lookup = {item.campaign_id: item.metrics for item in auxiliary}
        for metric, history in primary_series.items():
            aux_values = [values[metric] for values in auxiliary_lookup.values() if metric in values]
            forecast = _heuristic_forecast(metric, history, aux_values=aux_values, horizon=horizon)
            points[metric] = tuple(forecast["point"])
            quantiles[metric] = {
                "q10": tuple(forecast["q10"]),
                "q50": tuple(forecast["q50"]),
                "q90": tuple(forecast["q90"]),
            }
        return points, quantiles


def _primary_metric_series(
    campaign: CampaignEvidence,
    dead_end_metrics: tuple[str, ...],
) -> dict[str, list[float]]:
    series = {metric: [] for metric in (*_CORE_METRICS, *dead_end_metrics)}
    for signal in campaign.round_signals:
        series["best_score"].append(signal.best_score)
        series["certificate_pass_rate"].append(signal.certificate_pass_rate)
        series["global_exclusion_gap"].append(_gap_signal_value(signal, "global_exclusion_gap"))
        series["tail_control_gap"].append(_gap_signal_value(signal, "tail_control_gap"))
        series["translation_gap"].append(_gap_signal_value(signal, "translation_gap"))
        for metric in dead_end_metrics:
            series[metric].append(float(signal.repeated_dead_end_counts.get(metric, 0)))
    return series


def _auxiliary_snapshots(
    campaign: CampaignEvidence,
    dead_end_metrics: tuple[str, ...],
) -> list[AuxiliarySnapshot]:
    snapshots: list[AuxiliarySnapshot] = []
    for comparable in campaign.comparable_campaigns:
        metrics = {
            "best_score": comparable.best_score,
            "certificate_pass_rate": 0.0,
            "global_exclusion_gap": float("global_exclusion_gap" in comparable.dominant_failures),
            "tail_control_gap": float("tail_control_gap" in comparable.dominant_failures),
            "translation_gap": float("translation_gap" in comparable.dominant_failures),
        }
        failure_atlas_path = Path(comparable.campaign_dir) / "failure_atlas.json" if comparable.campaign_dir else None
        if failure_atlas_path and failure_atlas_path.exists():
            payload = _read_json(failure_atlas_path)
            failure_counts = dict(payload.get("failure_counts", {}))
            metrics["global_exclusion_gap"] = float(failure_counts.get("global_exclusion_gap", metrics["global_exclusion_gap"]))
            metrics["tail_control_gap"] = float(failure_counts.get("tail_control_gap", metrics["tail_control_gap"]))
            metrics["translation_gap"] = float(failure_counts.get("translation_gap", metrics["translation_gap"]))
            for metric in dead_end_metrics:
                metrics[metric] = float(failure_counts.get(metric, 0))
        else:
            for metric in dead_end_metrics:
                metrics[metric] = 0.0
        snapshots.append(AuxiliarySnapshot(campaign_id=comparable.campaign_id, metrics=metrics))
    return snapshots


def _select_dead_end_metrics(campaign: CampaignEvidence) -> tuple[str, ...]:
    ordered = sorted(
        campaign.repeated_dead_ends.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return tuple(key for key, _value in ordered[:3])


def _gap_signal_value(signal: RoundSignal, metric: str) -> float:
    direct = float(signal.failure_counts.get(metric, 0))
    if direct > 0:
        return direct

    unresolved = _normalize_gap_text(*signal.unresolved_obligations)
    failures = _normalize_gap_text(*signal.dominant_failures, *signal.failure_counts.keys())
    dead_ends = _normalize_gap_text(*signal.dead_end_patterns)

    if metric == "global_exclusion_gap":
        score = 0.0
        if _contains_any(
            unresolved,
            (
                "off line zero exclusion",
                "zero location exclusion",
                "proof that no off line zeros exist",
            ),
        ):
            score += 1.0
        if _contains_any(
            failures,
            (
                "global exclusion gap",
                "off line",
                "do not exclude off line zeros",
                "zero location exclusion",
                "proof that no off line zeros exist",
                "prime oscillations are incompatible with off line zeros",
            ),
        ):
            score += 1.0
        if _contains_any(dead_ends, ("classical critical line reuse",)):
            score += 0.5
        return score

    if metric == "tail_control_gap":
        score = 0.0
        if _contains_any(
            unresolved,
            (
                "explicit formula tail control",
                "tail control",
            ),
        ):
            score += 1.0
        if _contains_any(
            failures,
            (
                "tail control gap",
                "tail budget needs decay bound",
                "bound all error terms in the explicit formula",
                "zero sum relation needs tail control",
                "tail",
            ),
        ):
            score += 1.0
        if _contains_any(dead_ends, ("generic explicit formula restatement",)):
            score += 0.5
        return score

    if metric == "translation_gap":
        score = 0.0
        if _contains_any(
            unresolved,
            (
                "translation",
                "translate",
                "visual or surrogate translation",
            ),
        ):
            score += 1.0
        if _contains_any(
            failures,
            (
                "translation gap",
                "translation",
                "novelty requires translation",
            ),
        ):
            score += 1.0
        if _contains_any(dead_ends, ("translation",)):
            score += 0.5
        return score

    return 0.0


def _heuristic_forecast(
    metric: str,
    history: list[float],
    *,
    aux_values: Iterable[float],
    horizon: int,
) -> dict[str, list[float]]:
    aux_values = list(aux_values)
    last = float(history[-1]) if history else 0.0
    if len(history) >= 2:
        slopes = [float(next_value - current) for current, next_value in zip(history[:-1], history[1:])]
    else:
        slopes = []
    aux_pull = 0.0
    if aux_values:
        aux_pull = 0.25 * (median(aux_values) - last)
    slope = median(slopes) if slopes else aux_pull
    spread = _spread_from_history(history, slopes=slopes, aux_values=aux_values)
    point: list[float] = []
    q10: list[float] = []
    q50: list[float] = []
    q90: list[float] = []
    floor = _forecast_floor(metric, history)
    current = last
    for step in range(1, horizon + 1):
        current = _clamp_metric(metric, current + slope)
        if floor > 0.0:
            current = max(current, floor)
        point.append(current)
        margin = spread * math.sqrt(step)
        low = _clamp_metric(metric, current - margin)
        if floor > 0.0:
            low = max(low, floor * 0.5)
        q10.append(low)
        q50.append(current)
        q90.append(_clamp_metric(metric, current + margin))
    return {"point": point, "q10": q10, "q50": q50, "q90": q90}


def _forecast_floor(metric: str, history: list[float]) -> float:
    if metric not in _GAP_METRICS or not history:
        return 0.0
    positive = [value for value in history if value > 0.0]
    if not positive:
        return 0.0
    recent = history[-min(2, len(history)) :]
    if not any(value > 0.0 for value in recent):
        return 0.0
    return max(0.5, 0.5 * median(positive))


def _spread_from_history(history: list[float], *, slopes: list[float], aux_values: list[float]) -> float:
    if slopes:
        center = median(slopes)
        deviation = median(abs(value - center) for value in slopes)
        return max(0.05, deviation + 0.05 * max(1.0, abs(history[-1])))
    if aux_values:
        deviation = median(abs(value - median(aux_values)) for value in aux_values)
        return max(0.05, deviation + 0.05 * max(1.0, abs(history[-1] if history else 1.0)))
    if not history:
        return 0.1
    return max(0.05, 0.10 * max(1.0, abs(history[-1])))


def _clamp_metric(metric: str, value: float) -> float:
    if metric in _BOUND_METRICS:
        return max(0.0, min(1.0, float(value)))
    return max(0.0, float(value))


def _normalize_gap_text(*parts: str) -> str:
    return " ".join(str(part).lower().replace("_", " ").replace("-", " ") for part in parts if part)


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _forecast_confidence(
    primary_series: dict[str, list[float]],
    auxiliary: list[AuxiliarySnapshot],
    *,
    backend: str,
) -> float:
    primary_points = len(primary_series.get("best_score", []))
    auxiliary_points = len(auxiliary)
    confidence = 0.25 + min(0.30, 0.08 * primary_points) + min(0.20, 0.03 * auxiliary_points)
    if primary_points < 4:
        confidence -= 0.10
    if backend != "timesfm_native":
        confidence -= 0.05
    return max(0.20, min(0.85, confidence))


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload)
