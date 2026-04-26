"""External benchmark evaluator: FrontierMath / IMProofBench / LemmaBench / gdm-formal-conjectures (Phase 4)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


EXTERNAL_BENCHMARKS: dict[str, dict[str, str]] = {
    "frontier_math": {
        "url": "https://api.frontiermath.ai/v1/evaluate",
        "kind": "problem_set",
    },
    "improofbench": {
        "url": "https://api.improofbench.org/v1/check",
        "kind": "proof_check",
    },
    "lemmabench": {
        "url": "https://api.lemmabench.org/v1/lemma",
        "kind": "lemma_check",
    },
    "gdm_conjectures": {
        "url": "https://github.com/AxiomMath/gdm-formal-conjectures",
        "kind": "conjecture",
    },
}

_UNAVAILABLE_ERROR = "EXTERNAL_EVAL_ENABLED not set"


@dataclass(frozen=True)
class ExternalBenchmarkResult:
    benchmark_id: str
    score: float
    available: bool
    details: dict[str, Any]
    error: str


@dataclass(frozen=True)
class ExternalEvalReport:
    campaign_id: str
    internal_score: float
    external_scores: tuple[ExternalBenchmarkResult, ...]
    mean_external: float
    replan_triggered: bool
    replan_reason: str


class ExternalEvaluator:
    """Queries external math benchmarks and detects internal/external score divergence."""

    def __init__(self, *, timeout_s: float = 30.0) -> None:
        self._timeout_s = timeout_s

    def _query_benchmark(
        self, benchmark_id: str, payload: dict[str, Any]
    ) -> ExternalBenchmarkResult:
        if not os.environ.get("EXTERNAL_EVAL_ENABLED"):
            return ExternalBenchmarkResult(
                benchmark_id=benchmark_id,
                score=0.0,
                available=False,
                details={},
                error=_UNAVAILABLE_ERROR,
            )

        meta = EXTERNAL_BENCHMARKS.get(benchmark_id, {})
        url = meta.get("url", "")

        try:
            import requests  # noqa: PLC0415

            response = requests.post(url, json=payload, timeout=self._timeout_s)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return ExternalBenchmarkResult(
                benchmark_id=benchmark_id,
                score=float(data.get("score", 0.0)),
                available=True,
                details=data,
                error="",
            )
        except Exception as exc:  # noqa: BLE001
            return ExternalBenchmarkResult(
                benchmark_id=benchmark_id,
                score=0.0,
                available=False,
                details={},
                error=str(exc),
            )

    def run(
        self,
        campaign_id: str,
        internal_score: float,
        lean_candidates: list[dict[str, Any]],
    ) -> ExternalEvalReport:
        """Query all 4 benchmarks and return a structured report.

        Triggers REPLAN when internal_score exceeds mean_external by more than
        0.10 and at least one benchmark returned a live score.
        """
        payload = {
            "campaign_id": campaign_id,
            "candidates": lean_candidates,
        }

        results: list[ExternalBenchmarkResult] = [
            self._query_benchmark(bid, payload) for bid in EXTERNAL_BENCHMARKS
        ]

        available = [r for r in results if r.available]
        mean_external = (
            sum(r.score for r in available) / len(available) if available else 0.0
        )

        gap = internal_score - mean_external
        replan_triggered = bool(available) and gap > 0.10
        replan_reason = (
            f"internal_score={internal_score:.3f} mean_external={mean_external:.3f} "
            f"gap={gap:.3f} > 0.10 — external benchmarks are not keeping pace with internal progress"
            if replan_triggered
            else ""
        )

        return ExternalEvalReport(
            campaign_id=campaign_id,
            internal_score=internal_score,
            external_scores=tuple(results),
            mean_external=mean_external,
            replan_triggered=replan_triggered,
            replan_reason=replan_reason,
        )
