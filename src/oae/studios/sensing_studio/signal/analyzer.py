"""Agent ER — measurement signal feature extractor.

Phase F ships a lightweight, dependency-free analyzer that is correct
enough for voltammetric traces (DPV / SWV / CV) in CI and the
offline replay scenarios. The analyzer produces:

* Peak current (``i_peak``) — the maximum of ``abs(current)`` within
  the electrochemical window.
* Peak potential (``e_peak``) — the voltage at the peak.
* Baseline current — median of the first/last fractions of the trace.
* SNR proxy — peak height divided by baseline noise RMS.
* Drift — linear slope of the trace's baseline.
* Linearity R² — goodness of a linear fit to the raw trace (used as a
  crude interference / saturation warning).

These features are deterministic and rely only on Python's stdlib.
Higher-order analysis (e.g. full peak deconvolution) belongs in a
future phase where numpy / scipy are acceptable heavy dependencies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from src.oae.studios.sensing_studio.ingest.bridge import MeasurementRecord


# ---------------------------------------------------------------------------
# Feature dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalFeatures:
    """Per-sample feature vector produced by the analyzer."""

    sample_id: str
    i_peak_a: float
    e_peak_v: float
    baseline_a: float
    noise_rms_a: float
    snr_db: float
    drift_per_point_a: float
    linearity_r2: float
    anomaly_flag: bool = False

    def to_dict(self) -> dict[str, float]:
        return {
            "i_peak_a": self.i_peak_a,
            "e_peak_v": self.e_peak_v,
            "baseline_a": self.baseline_a,
            "noise_rms_a": self.noise_rms_a,
            "snr_db": self.snr_db,
            "drift_per_point_a": self.drift_per_point_a,
            "linearity_r2": self.linearity_r2,
            "anomaly": 1.0 if self.anomaly_flag else 0.0,
        }


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


@dataclass
class SignalAnalyzer:
    """Deterministic feature extractor.

    Parameters
    ----------
    baseline_fraction:
        Fraction of trace points (from each end) used to estimate the
        baseline. 0.2 means the first 20 % and last 20 % of points are
        pooled.
    anomaly_snr_threshold_db:
        SNR below which the sample is flagged as anomalous.
    """

    baseline_fraction: float = 0.2
    anomaly_snr_threshold_db: float = 3.0

    # --- public API ---------------------------------------------------

    def analyze(self, record: MeasurementRecord) -> SignalFeatures:
        voltage = record.voltage_v
        current = record.current_a
        if record.n_points < 4:
            return _empty_features(record.sample_id)

        baseline = self._baseline(current)
        noise_rms = self._noise_rms(current, baseline)
        centred = tuple(c - baseline for c in current)

        peak_idx = max(range(len(centred)), key=lambda i: abs(centred[i]))
        i_peak = centred[peak_idx]
        e_peak = voltage[peak_idx]

        snr_db = (
            20.0 * math.log10(abs(i_peak) / noise_rms)
            if noise_rms > 0 and i_peak != 0
            else 0.0
        )
        drift = self._linear_slope(current)
        r2 = self._linearity_r2(voltage, current)
        anomaly = snr_db < self.anomaly_snr_threshold_db

        return SignalFeatures(
            sample_id=record.sample_id,
            i_peak_a=i_peak,
            e_peak_v=e_peak,
            baseline_a=baseline,
            noise_rms_a=noise_rms,
            snr_db=snr_db,
            drift_per_point_a=drift,
            linearity_r2=r2,
            anomaly_flag=anomaly,
        )

    def analyze_batch(
        self,
        records: Iterable[MeasurementRecord],
    ) -> tuple[SignalFeatures, ...]:
        return tuple(self.analyze(r) for r in records)

    def summarise(
        self,
        features: Sequence[SignalFeatures],
    ) -> dict[str, float]:
        """Return aggregate statistics across a batch.

        Used as the ``signal_feature_summary`` on :class:`RoundState`.
        """
        if not features:
            return {}
        n = float(len(features))
        peaks = [f.i_peak_a for f in features]
        snr = [f.snr_db for f in features]
        return {
            "n": n,
            "mean_i_peak_a": sum(peaks) / n,
            "max_abs_i_peak_a": max(abs(p) for p in peaks),
            "mean_snr_db": sum(snr) / n,
            "mean_linearity_r2": sum(f.linearity_r2 for f in features) / n,
            "anomaly_fraction": sum(1 for f in features if f.anomaly_flag) / n,
        }

    # --- internals ----------------------------------------------------

    def _baseline(self, current: Sequence[float]) -> float:
        k = max(2, int(len(current) * self.baseline_fraction))
        pooled = sorted(list(current[:k]) + list(current[-k:]))
        mid = len(pooled) // 2
        if len(pooled) % 2 == 0:
            return 0.5 * (pooled[mid - 1] + pooled[mid])
        return pooled[mid]

    def _noise_rms(
        self,
        current: Sequence[float],
        baseline: float,
    ) -> float:
        k = max(2, int(len(current) * self.baseline_fraction))
        samples = list(current[:k]) + list(current[-k:])
        if not samples:
            return 0.0
        sq = sum((s - baseline) ** 2 for s in samples)
        return math.sqrt(sq / len(samples))

    def _linear_slope(self, current: Sequence[float]) -> float:
        n = len(current)
        if n < 2:
            return 0.0
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(current) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, current))
        den = sum((x - mean_x) ** 2 for x in xs)
        return num / den if den > 0 else 0.0

    def _linearity_r2(
        self,
        voltage: Sequence[float],
        current: Sequence[float],
    ) -> float:
        n = len(voltage)
        if n < 3:
            return 0.0
        mean_x = sum(voltage) / n
        mean_y = sum(current) / n
        var_x = sum((x - mean_x) ** 2 for x in voltage)
        var_y = sum((y - mean_y) ** 2 for y in current)
        if var_x == 0 or var_y == 0:
            return 0.0
        cov = sum(
            (x - mean_x) * (y - mean_y) for x, y in zip(voltage, current)
        )
        r = cov / math.sqrt(var_x * var_y)
        return max(0.0, min(1.0, r * r))


def _empty_features(sample_id: str) -> SignalFeatures:
    return SignalFeatures(
        sample_id=sample_id,
        i_peak_a=0.0,
        e_peak_v=0.0,
        baseline_a=0.0,
        noise_rms_a=0.0,
        snr_db=0.0,
        drift_per_point_a=0.0,
        linearity_r2=0.0,
        anomaly_flag=True,
    )


__all__ = ["SignalAnalyzer", "SignalFeatures"]
