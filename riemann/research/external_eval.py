"""External benchmark evaluator: FrontierMath / IMProofBench / LemmaBench / gdm-formal-conjectures / Odlyzko (Phase 4)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .odlyzko_benchmark import OdlyzkoTable, evaluate_round


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
    "odlyzko_zero_consistency": {
        "url": "local:data/riemann/zeros1.txt",
        "kind": "empirical_ground_truth",
    },
}

_UNAVAILABLE_ERROR = "EXTERNAL_EVAL_ENABLED not set"

# Cache for Odlyzko table — loading 100k zeros takes ~50ms.
_ODLYZKO_CACHE: OdlyzkoTable | None = None


def _load_odlyzko(max_zeros: int = 10_000) -> OdlyzkoTable | None:
    global _ODLYZKO_CACHE
    if _ODLYZKO_CACHE is not None:
        return _ODLYZKO_CACHE
    # Search up from this file for data/riemann/zeros1.txt.
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        candidate = ancestor / "data" / "riemann" / "zeros1.txt"
        if candidate.exists():
            _ODLYZKO_CACHE = OdlyzkoTable.load(candidate, max_zeros=max_zeros)
            return _ODLYZKO_CACHE
    return None


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
        # Odlyzko is local-data-backed and always available — it does NOT require
        # EXTERNAL_EVAL_ENABLED because there is no network call. It is 'external'
        # in the relevant sense: the zero table is empirical mathematical truth
        # that no orchestrator paraphrase can change.
        if benchmark_id == "odlyzko_zero_consistency":
            return self._query_odlyzko(payload)

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

    def _query_odlyzko(self, payload: dict[str, Any]) -> ExternalBenchmarkResult:
        """Score candidates against the Odlyzko zero table (local, always available)."""
        odlyzko = _load_odlyzko()
        if odlyzko is None:
            return ExternalBenchmarkResult(
                benchmark_id="odlyzko_zero_consistency",
                score=0.0,
                available=False,
                details={},
                error="data/riemann/zeros1.txt not found in any ancestor of external_eval.py",
            )
        candidates = payload.get("candidates", [])
        round_index = int(payload.get("round_index", 0))
        result = evaluate_round(
            round_index=round_index,
            candidate_records=candidates,
            odlyzko=odlyzko,
        )
        return ExternalBenchmarkResult(
            benchmark_id="odlyzko_zero_consistency",
            score=result.mean_score,
            available=True,
            details={
                "candidate_count": result.candidate_count,
                "mean_score": result.mean_score,
                "contradicted_count": result.contradicted_count,
                "confirmed_count": result.confirmed_count,
                "untestable_count": result.untestable_count,
                "table_size": len(odlyzko.heights),
                "table_t_max": odlyzko.t_max,
            },
            error="",
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
