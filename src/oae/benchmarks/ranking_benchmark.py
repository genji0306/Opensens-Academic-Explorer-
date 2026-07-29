"""Ranking benchmark — new Snorkel verifier vs legacy heuristic.

Runs the Phase E ``SnorkelVerifier`` over the Phase I gold set and
computes precision / recall / false-positive rate. A trivial heuristic
baseline (composition synthesizability only) is included so the phase-I
exit metric "≥15 % precision uplift over the pre-phase-1 baseline" can
be measured directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.oae.benchmarks.gold_set import GoldEntry, PhaseIGoldSet
from src.oae.kernel.verification import SnorkelVerifier


@dataclass(frozen=True)
class BenchmarkReport:
    """Comparison report emitted by :class:`RankingBenchmark`."""

    n_entries: int
    new_precision: float
    new_recall: float
    new_false_positive_rate: float
    baseline_precision: float
    baseline_recall: float
    baseline_false_positive_rate: float
    precision_uplift: float
    false_positive_reduction: float
    details: tuple[dict, ...] = field(default_factory=tuple)

    def meets_phase_i_targets(self) -> bool:
        """Phase I exit: ≥15 % precision uplift, ≥30 % FP reduction."""
        return (
            self.precision_uplift >= 0.15
            and self.false_positive_reduction >= 0.30
        )


@dataclass
class _Candidate:
    """Lightweight duck-type of ``LoopCandidate`` for the verifier."""

    candidate_id: str
    family: str
    composition: str
    mechanism: str
    predicted_property: float = 0.0
    energy_above_hull_meV: float = 0.0
    confidence: float = 0.5
    metadata: dict = field(default_factory=dict)


@dataclass
class _ScoredBatch:
    candidates: list[_Candidate] = field(default_factory=list)


def _baseline_score(entry: GoldEntry) -> float:
    """Legacy heuristic: synthesizability only, everything else ignored."""
    meta = entry.metadata
    return float(meta.get("synthesizability", 0.5))


@dataclass
class RankingBenchmark:
    """Benchmark harness for the Phase E verifier against the gold set."""

    gold_set: PhaseIGoldSet = field(default_factory=PhaseIGoldSet)
    verifier: SnorkelVerifier = field(default_factory=SnorkelVerifier)
    threshold: float = 0.5

    # ------------------------------------------------------------------

    def run(self) -> BenchmarkReport:
        entries = self.gold_set.entries
        candidates = [
            _Candidate(
                candidate_id=e.candidate_id,
                family=e.family,
                composition=e.composition,
                mechanism=e.mechanism,
                metadata=dict(e.metadata),
            )
            for e in entries
        ]
        bundles, _ = self.verifier.verify_batch(
            _ScoredBatch(candidates=candidates),
            domain="benchmark",
            connector_agreements={
                e.candidate_id: dict(e.connector_agreement) for e in entries
            },
        )

        new_predictions = {
            cid: bundle.posterior.credibility_prob >= self.threshold
            for cid, bundle in bundles.items()
        }
        baseline_predictions = {
            e.candidate_id: _baseline_score(e) >= self.threshold for e in entries
        }

        new_metrics = _classification_metrics(entries, new_predictions)
        baseline_metrics = _classification_metrics(entries, baseline_predictions)

        precision_uplift = new_metrics["precision"] - baseline_metrics["precision"]
        fp_reduction = (
            (baseline_metrics["fpr"] - new_metrics["fpr"]) / baseline_metrics["fpr"]
            if baseline_metrics["fpr"] > 0
            else 1.0
        )

        details = tuple(
            {
                "candidate_id": e.candidate_id,
                "credible": e.credible,
                "new_credibility": bundles[e.candidate_id].posterior.credibility_prob,
                "new_prediction": new_predictions[e.candidate_id],
                "baseline_prediction": baseline_predictions[e.candidate_id],
            }
            for e in entries
        )

        return BenchmarkReport(
            n_entries=len(entries),
            new_precision=new_metrics["precision"],
            new_recall=new_metrics["recall"],
            new_false_positive_rate=new_metrics["fpr"],
            baseline_precision=baseline_metrics["precision"],
            baseline_recall=baseline_metrics["recall"],
            baseline_false_positive_rate=baseline_metrics["fpr"],
            precision_uplift=precision_uplift,
            false_positive_reduction=fp_reduction,
            details=details,
        )


def _classification_metrics(
    entries: Iterable[GoldEntry],
    predictions: dict[str, bool],
) -> dict[str, float]:
    tp = fp = tn = fn = 0
    for entry in entries:
        predicted = predictions.get(entry.candidate_id, False)
        if entry.credible and predicted:
            tp += 1
        elif entry.credible and not predicted:
            fn += 1
        elif not entry.credible and predicted:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": precision, "recall": recall, "fpr": fpr}


def run_ranking_benchmark() -> BenchmarkReport:
    """Convenience entry point for CLI / examples / CI."""
    return RankingBenchmark().run()
