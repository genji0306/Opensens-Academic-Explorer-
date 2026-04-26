"""Predictive sensing model — the orchestrator core.

The model turns signal features and scientific priors into a
concentration estimate per sample plus an uncertainty estimate. Phase
F ships a deterministic ordinary-least-squares linear model in
``log10(abs(i_peak))`` space — this is the textbook voltammetric
calibration relationship and keeps CI dependency-free.

The model is intentionally "repairable": :meth:`redesign` returns a
new model with a different feature selection strategy, which is what
the Observer invokes when it routes a failure to ``"model"``. Feature
strategies ship in Phase F:

* ``"peak"``  — default, uses ``abs(i_peak_a)``.
* ``"peak_theory"`` — adds the ``theory_alignment`` prior as a soft
  offset on predictions.
* ``"peak_linear"`` — uses both peak height and linear drift slope.

Each strategy corresponds to a different hypothesis about *why* the
previous model failed, making the redesign path auditable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Sequence

from src.oae.studios.sensing_studio.signal.analyzer import SignalFeatures

FeatureStrategy = Literal["peak", "peak_theory", "peak_linear"]


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictiveOutput:
    """Per-sample prediction + uncertainty."""

    sample_id: str
    predicted_concentration_uM: float
    uncertainty_uM: float
    feature_strategy: str


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class PredictiveModel:
    """Deterministic linear predictive model with explicit strategies.

    The model is fit per round using samples whose true concentration
    is supplied (via the Observer's calibration slice — the model
    itself never touches the hidden vault directly). Parameters are a
    slope and intercept in log-log space; uncertainty is the RMSE of
    the fit multiplied by a strategy-specific inflation factor.
    """

    feature_strategy: FeatureStrategy = "peak"
    slope: float = 0.0
    intercept: float = 0.0
    rmse_log: float = 0.0
    theory_offset: float = 0.0
    fitted: bool = field(default=False, init=False)

    # --- fit / predict -----------------------------------------------

    def fit(
        self,
        features: Sequence[SignalFeatures],
        true_concentrations_uM: Sequence[float],
        prior_summary: dict[str, float] | None = None,
    ) -> "PredictiveModel":
        """Fit the model on ``(features, concentrations)`` pairs.

        Returns ``self`` so callers can chain a fit into a predict.
        """
        if len(features) != len(true_concentrations_uM):
            raise ValueError("features/concentration length mismatch")
        if len(features) < 2:
            # Not enough data to fit; fall back to a zero model.
            self.slope = 0.0
            self.intercept = 0.0
            self.rmse_log = 1.0
            self.fitted = True
            return self

        xs: list[float] = []
        ys: list[float] = []
        for feat, conc in zip(features, true_concentrations_uM):
            x = self._feature_value(feat)
            if x <= 0 or conc <= 0:
                continue
            xs.append(math.log10(x))
            ys.append(math.log10(conc))
        if len(xs) < 2:
            self.slope = 0.0
            self.intercept = 0.0
            self.rmse_log = 1.0
            self.fitted = True
            return self

        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        if den == 0:
            self.slope = 0.0
        else:
            self.slope = num / den
        self.intercept = mean_y - self.slope * mean_x
        residuals = [
            (y - (self.slope * x + self.intercept)) ** 2
            for x, y in zip(xs, ys)
        ]
        self.rmse_log = math.sqrt(sum(residuals) / len(residuals))

        if self.feature_strategy == "peak_theory" and prior_summary:
            # A small additive offset proportional to theory alignment.
            self.theory_offset = 0.1 * float(
                prior_summary.get("theory_alignment", 0.0)
            )
        else:
            self.theory_offset = 0.0

        self.fitted = True
        return self

    def predict(
        self,
        features: Sequence[SignalFeatures],
    ) -> tuple[PredictiveOutput, ...]:
        if not self.fitted:
            raise RuntimeError(
                "PredictiveModel.predict called before fit()"
            )
        out: list[PredictiveOutput] = []
        for feat in features:
            x = self._feature_value(feat)
            if x <= 0:
                predicted = 0.0
            else:
                log_pred = (
                    self.slope * math.log10(x)
                    + self.intercept
                    + self.theory_offset
                )
                predicted = max(0.0, 10 ** log_pred)
            # Uncertainty in linear units is asymmetric in log space;
            # use a first-order expansion: σ_lin ≈ predicted × ln(10) × rmse_log.
            uncertainty = predicted * math.log(10) * self.rmse_log
            out.append(
                PredictiveOutput(
                    sample_id=feat.sample_id,
                    predicted_concentration_uM=predicted,
                    uncertainty_uM=max(0.0, uncertainty),
                    feature_strategy=self.feature_strategy,
                )
            )
        return tuple(out)

    # --- redesign -----------------------------------------------------

    def redesign(self, next_strategy: FeatureStrategy) -> "PredictiveModel":
        """Return a new model configured with ``next_strategy``.

        The Observer calls this when it routes failure to ``"model"``.
        """
        return PredictiveModel(feature_strategy=next_strategy)

    # --- internals ----------------------------------------------------

    def _feature_value(self, feat: SignalFeatures) -> float:
        if self.feature_strategy == "peak_linear":
            # Combine peak magnitude with the absolute drift slope —
            # useful when a monotonic baseline carries signal info.
            return abs(feat.i_peak_a) + 0.25 * abs(feat.drift_per_point_a)
        return abs(feat.i_peak_a)


__all__ = ["FeatureStrategy", "PredictiveModel", "PredictiveOutput"]
