"""Agent Ob -- matcher / scorer.

Compares synthetic gamma_n (from Agent B) against the real LMFDB gamma_n
and emits a `ConvergenceReport` whose `score` drives the outer loop:

    score >= target  -> hand off to Agent C (synthesize principle)
    score <  target  -> request refinement (more correction terms /
                                            more spline knots / refit a).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from ..core.config import LoopConfig
from ..core.schemas import (
    ComponentScores,
    ConvergenceReport,
    ZeroDataset,
    ZeroPrediction,
)


def _local_spacing(gamma: np.ndarray) -> np.ndarray:
    """Mean local spacing 2 pi / log(gamma/2 pi) (Riemann--von Mangoldt)."""
    return 2.0 * np.pi / np.log(np.maximum(gamma, 2.0) / (2.0 * np.pi))


def _match_rate(gamma_true: np.ndarray, gamma_pred: np.ndarray, tol_rel: float) -> float:
    spacing = _local_spacing(gamma_true)
    tol = tol_rel * spacing
    hits = np.abs(gamma_pred - gamma_true) <= tol
    return float(np.mean(hits))


def _spacing_fit(gamma_true: np.ndarray, gamma_pred: np.ndarray) -> float:
    """GUE-like check: how similar are the nearest-neighbour spacings?

    We compute normalised spacings for both series (mean 1) and take the
    1 - KS-style max gap between sorted distributions.  Pure zero spacing
    agreement -> 1.0; random -> 0.
    """
    if gamma_true.size < 4:
        return 0.0
    st = np.diff(gamma_true) * np.log(gamma_true[:-1] / (2 * np.pi)) / (2 * np.pi)
    sp = np.diff(gamma_pred) * np.log(np.maximum(gamma_pred[:-1], 2.0) / (2 * np.pi)) / (2 * np.pi)
    # empirical CDFs on a shared grid
    grid = np.linspace(0, 4.0, 128)
    c_t = np.searchsorted(np.sort(st), grid, side="right") / st.size
    c_p = np.searchsorted(np.sort(sp), grid, side="right") / sp.size
    ks = float(np.max(np.abs(c_t - c_p)))
    return max(0.0, 1.0 - ks)


def score(
    dataset: ZeroDataset,
    prediction: ZeroPrediction,
    cfg: LoopConfig,
    iteration: int,
) -> ConvergenceReport:
    gamma_true = dataset.gamma
    gamma_pred = prediction.gamma_pred

    residual = gamma_pred - gamma_true
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    # Relative error per-zero, median (robust).
    rel = np.abs(residual) / _local_spacing(gamma_true)
    rel_median = float(np.median(rel))
    mr = _match_rate(gamma_true, gamma_pred, cfg.match_tol_rel)
    sf = _spacing_fit(gamma_true, gamma_pred)

    components = ComponentScores(
        match_rate=mr,
        rmse=rmse,
        rel_error_median=rel_median,
        spacing_fit=sf,
    )
    composite = components.composite(
        cfg.weight_match_rate,
        cfg.weight_rmse,
        cfg.weight_rel_error,
        cfg.weight_spacing_fit,
        cfg.rmse_scale,
    )

    # Suggestion for the outer loop.
    suggestion: dict[str, Any] = {}
    if composite < cfg.target_score:
        # Which component is weakest?
        worst = min(
            ("match_rate", mr),
            ("rmse_score", float(np.exp(-rmse / cfg.rmse_scale))),
            ("rel_error", float(np.exp(-rel_median * 100.0))),
            ("spacing_fit", sf),
            key=lambda kv: kv[1],
        )[0]
        if worst in ("rmse_score", "rel_error"):
            suggestion["add_correction_term"] = True
            suggestion["add_spline_knots"] = 4
        elif worst == "match_rate":
            suggestion["add_spline_knots"] = 8
            suggestion["refit_offset_a"] = True
        else:  # spacing fit
            suggestion["add_correction_term"] = True
        suggestion["reason"] = f"weakest_component={worst}"
    else:
        suggestion["converged"] = True

    return ConvergenceReport(
        iteration=iteration,
        score=composite,
        components=components,
        residuals=residual,
        suggestion=suggestion,
    )


class AgentOb:
    name = "Ob"
    role = "Matcher / Scorer"

    def run(
        self,
        dataset: ZeroDataset,
        prediction: ZeroPrediction,
        cfg: LoopConfig,
        iteration: int,
    ) -> ConvergenceReport:
        return score(dataset, prediction, cfg, iteration)
