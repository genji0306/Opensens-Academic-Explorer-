"""Agent B -- zero predictor / synthesizer."""
from __future__ import annotations

import numpy as np

from ..agent_a.extractor import legendre_basis_for, parse_offset_a
from ..core.schemas import ZeroPrediction, ZeroRule
from ..core.theta import asymptotic_zero


def predict(
    rule: ZeroRule,
    n: np.ndarray,
    rule_version: int = 0,
    n_total: int | None = None,
) -> ZeroPrediction:
    n_arr = np.asarray(n, dtype=np.int64)
    n_f = n_arr.astype(np.float64)
    n_total = int(n_total if n_total is not None else rule.fitted_on_n_zeros)

    base = asymptotic_zero(n_f, offset_a=parse_offset_a(rule))

    k = rule.correction_coeffs.size
    if k > 0:
        X = legendre_basis_for(n_f, n_total=n_total, k_terms=k)
        base = base + X @ rule.correction_coeffs

    if rule.spline_knots_n.size >= 2:
        base = base + np.interp(n_f, rule.spline_knots_n, rule.spline_knots_r)

    return ZeroPrediction(
        n=n_arr,
        gamma_pred=base,
        rule_version=rule_version,
        generator="theta_inverse+legendre_ridge+bin_spline",
    )


class AgentB:
    name = "B"
    role = "Zero Predictor"

    def run(
        self,
        rule: ZeroRule,
        n: np.ndarray,
        rule_version: int = 0,
        n_total: int | None = None,
    ) -> ZeroPrediction:
        return predict(rule, n, rule_version=rule_version, n_total=n_total)
