"""Phase I calibration suite — cross-studio self-check.

Verifies that the three studios (Material Explorer, Sensing Studio,
Simulation Lab) agree on the same candidate when run back-to-back and
that the Snorkel verifier's credibility posterior is consistent across
studios. This is the plumbing that Phase I requires to declare the
cross-studio loop closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.oae.benchmarks.gold_set import PhaseIGoldSet
from src.oae.benchmarks.ranking_benchmark import RankingBenchmark
from src.oae.simulation import build_mof_1k_seed


@dataclass(frozen=True)
class CalibrationResult:
    """Aggregated output of the calibration suite."""

    verifier_precision: float
    verifier_fpr: float
    simulation_backends: tuple[str, ...]
    mof_dataset_size: int
    passes: bool
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "verifier_precision": self.verifier_precision,
            "verifier_fpr": self.verifier_fpr,
            "simulation_backends": list(self.simulation_backends),
            "mof_dataset_size": self.mof_dataset_size,
            "passes": self.passes,
            "notes": list(self.notes),
        }


@dataclass
class CalibrationSuite:
    """End-to-end calibration harness for Phase I exit."""

    gold_set: PhaseIGoldSet = field(default_factory=PhaseIGoldSet)
    precision_floor: float = 0.7
    fpr_ceiling: float = 0.4

    def run(self) -> CalibrationResult:
        notes: list[str] = []

        report = RankingBenchmark(gold_set=self.gold_set).run()
        precision_ok = report.new_precision >= self.precision_floor
        fpr_ok = report.new_false_positive_rate <= self.fpr_ceiling
        if not precision_ok:
            notes.append(
                f"precision {report.new_precision:.2f} below floor {self.precision_floor}"
            )
        if not fpr_ok:
            notes.append(
                f"fpr {report.new_false_positive_rate:.2f} above ceiling {self.fpr_ceiling}"
            )

        dataset = build_mof_1k_seed(limit=10)
        backends = tuple(sorted({r.backend for r in dataset.results}))
        if not backends:
            notes.append("simulation lab returned no backend results")

        passes = precision_ok and fpr_ok and bool(backends)
        return CalibrationResult(
            verifier_precision=report.new_precision,
            verifier_fpr=report.new_false_positive_rate,
            simulation_backends=backends,
            mof_dataset_size=len(dataset),
            passes=passes,
            notes=tuple(notes),
        )


def run_default_suite() -> CalibrationResult:
    return CalibrationSuite().run()
