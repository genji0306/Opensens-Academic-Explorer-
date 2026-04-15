"""Dataclasses exchanged between Agent A, B, Ob, C.

Design note: we follow the OAE immutability convention -- every agent
returns a NEW dataclass rather than mutating the one handed in.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ZeroDataset:
    """Ground-truth non-trivial zeros (gamma_n = Im(rho_n) with Re = 1/2)."""

    n: np.ndarray            # zero index, shape (N,), int
    gamma: np.ndarray        # imaginary part, shape (N,), float64
    source: str              # provenance tag
    precision: float         # claimed numerical precision of the source

    @property
    def size(self) -> int:
        return int(self.n.shape[0])

    def head(self, k: int) -> "ZeroDataset":
        return ZeroDataset(
            n=self.n[:k].copy(),
            gamma=self.gamma[:k].copy(),
            source=self.source,
            precision=self.precision,
        )


@dataclass(frozen=True)
class ZeroRule:
    """Agent A output: an explicit ansatz for gamma_n = F(n; params).

    The ansatz is:
        gamma_n = F_asym(n) + R(n)
    where
        F_asym(n) -- solution of theta(t) = (n - 11/8) * pi via Newton
                     iteration, giving the Riemann-Siegel main term.
        R(n)      -- correction:
                     sum_{k=1..K} a_k * phi_k(n)   [parametric part]
                     + spline residual fit        [non-parametric part]
    """

    # parametric correction coefficients (a_1..a_K)
    correction_coeffs: np.ndarray
    # basis tag (so Agent B knows which phi_k to use)
    correction_basis: str = "log_inverse_powers"
    # non-parametric spline residual: knot indices + values (both shape (M,))
    spline_knots_n: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=np.float64)
    )
    spline_knots_r: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=np.float64)
    )
    # How the Riemann-Siegel theta solver is configured.
    theta_newton_tol: float = 1e-12
    theta_newton_max_iter: int = 60
    # Metadata for provenance / debugging.
    fitted_on_n_zeros: int = 0
    residual_rms_at_fit: float = float("nan")
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["correction_coeffs"] = self.correction_coeffs.tolist()
        d["spline_knots_n"] = self.spline_knots_n.tolist()
        d["spline_knots_r"] = self.spline_knots_r.tolist()
        return d


@dataclass(frozen=True)
class ZeroPrediction:
    """Agent B output: synthetic gamma_n values generated from a rule."""

    n: np.ndarray
    gamma_pred: np.ndarray
    rule_version: int
    generator: str = "riemann_siegel_inverse+correction"

    @property
    def size(self) -> int:
        return int(self.n.shape[0])


@dataclass(frozen=True)
class ComponentScores:
    match_rate: float
    rmse: float
    rel_error_median: float
    spacing_fit: float

    def composite(
        self,
        w_match: float,
        w_rmse: float,
        w_rel: float,
        w_space: float,
        rmse_scale: float,
    ) -> float:
        rmse_score = float(np.exp(-self.rmse / rmse_scale))
        rel_score = float(np.exp(-self.rel_error_median * 100.0))
        return (
            w_match * self.match_rate
            + w_rmse * rmse_score
            + w_rel * rel_score
            + w_space * self.spacing_fit
        )


@dataclass(frozen=True)
class ConvergenceReport:
    """Agent Ob output for one iteration."""

    iteration: int
    score: float
    components: ComponentScores
    residuals: np.ndarray         # gamma_pred - gamma_true
    suggestion: dict[str, Any]    # hints for Agent A / B to refine

    def to_summary(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "score": self.score,
            "match_rate": self.components.match_rate,
            "rmse": self.components.rmse,
            "rel_error_median": self.components.rel_error_median,
            "spacing_fit": self.components.spacing_fit,
            "residual_abs_max": float(np.max(np.abs(self.residuals))),
            "residual_abs_mean": float(np.mean(np.abs(self.residuals))),
        }


@dataclass(frozen=True)
class FunctionalPrinciple:
    """Agent C output: a closed-form (or near-closed-form) generator."""

    name: str
    description: str
    parameters: dict[str, Any]
    python_callable_src: str      # a string the caller can exec() to get f(n)
    validation_rmse: float
    validation_match_rate: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
