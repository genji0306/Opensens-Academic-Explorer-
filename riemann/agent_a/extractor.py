"""Agent A -- pattern / rule extractor.

Fits

    gamma_n = theta^{-1}((n - a) pi)           # Riemann-Siegel main term
            + sum_k c_k  P_k(u(n))             # smooth parametric part
            + spline_residual(n)               # per-zero fluctuation table

where u(n) = 2 * (n-1)/(N-1) - 1 is a normalised index and {P_k} is the
orthonormal Legendre basis.  Two architectural decisions matter:

1. The parametric coefficients are fit by *ridge* regression on the
   Legendre basis -- this prevents the collinearity that wrecks a naive
   log-inverse-power LSQ.
2. The residuals of zeta zeros are genuinely oscillatory (they encode
   the Riemann-Siegel S(t) fluctuations), not a smooth function of n.
   We therefore skip classical smoothing and use a *binned-interpolation*
   spline: a cubic through knot-centred bin means.  Adding more knots is
   the only reliable way to drive these residuals down.
"""
from __future__ import annotations

import numpy as np

from ..core.schemas import ZeroDataset, ZeroRule
from ..core.theta import asymptotic_zero

_OFFSET_A_KEY = "__offset_a__"


# -------- basis --------------------------------------------------------

def _normalised_u(n: np.ndarray) -> np.ndarray:
    n = np.asarray(n, dtype=np.float64)
    N = n.size
    if N <= 1:
        return np.zeros_like(n)
    return 2.0 * (n - n[0]) / (n[-1] - n[0]) - 1.0


def _legendre_basis(u: np.ndarray, k_terms: int) -> np.ndarray:
    """Return an (N, k) matrix of orthonormal Legendre polynomials P_1..P_k
    (P_0 is the constant term -- we omit it so the residual mean isn't
    double-counted by the spline offset).
    """
    if k_terms <= 0:
        return np.zeros((u.size, 0))
    # Recurrence: (l+1) P_{l+1}(u) = (2l+1) u P_l - l P_{l-1}.
    cols: list[np.ndarray] = []
    p_prev = np.ones_like(u)      # P_0
    p_curr = u.copy()              # P_1
    cols.append(p_curr / np.sqrt(2.0 / 3.0))
    for l in range(1, k_terms):
        p_next = ((2 * l + 1) * u * p_curr - l * p_prev) / (l + 1)
        p_prev, p_curr = p_curr, p_next
        cols.append(p_curr / np.sqrt(2.0 / (2 * (l + 1) + 1)))
    return np.column_stack(cols)


def _ridge(X: np.ndarray, y: np.ndarray, alpha: float = 1e-3) -> np.ndarray:
    if X.size == 0:
        return np.zeros(0, dtype=np.float64)
    n, k = X.shape
    A = X.T @ X + alpha * np.eye(k)
    b = X.T @ y
    return np.linalg.solve(A, b)


# -------- offset a -----------------------------------------------------

def _fit_offset_a(n: np.ndarray, gamma: np.ndarray) -> float:
    """Coarse-to-fine 1-D search for Gram offset minimising pre-correction RMS."""
    # coarse
    coarse = np.linspace(0.5, 2.0, 31)
    best_a, best_rms = 11.0 / 8.0, float("inf")
    for a in coarse:
        pred = asymptotic_zero(n, offset_a=float(a))
        rms = float(np.sqrt(np.mean((pred - gamma) ** 2)))
        if rms < best_rms:
            best_rms, best_a = rms, float(a)
    # fine
    fine = np.linspace(best_a - 0.05, best_a + 0.05, 51)
    for a in fine:
        pred = asymptotic_zero(n, offset_a=float(a))
        rms = float(np.sqrt(np.mean((pred - gamma) ** 2)))
        if rms < best_rms:
            best_rms, best_a = rms, float(a)
    return best_a


# -------- spline residual ---------------------------------------------

def _fit_spline(
    n: np.ndarray,
    residual: np.ndarray,
    knots: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Bin-mean cubic spline: partition n into `knots` contiguous bins,
    place a knot at each bin's centre with value = bin-mean residual.

    Linear interpolation between knots is stored (we cast back to np.interp
    in the predictor to avoid a scipy dependency at predict time).
    """
    if knots <= 0 or n.size < 8:
        empty = np.zeros(0, dtype=np.float64)
        return empty, empty
    N = n.size
    knots = int(min(knots, N))
    edges = np.linspace(0, N, knots + 1, dtype=int)
    knots_n = np.zeros(knots, dtype=np.float64)
    knots_r = np.zeros(knots, dtype=np.float64)
    for i in range(knots):
        lo, hi = edges[i], max(edges[i + 1], edges[i] + 1)
        sl = residual[lo:hi]
        nl = n[lo:hi].astype(np.float64)
        knots_n[i] = float(np.mean(nl))
        knots_r[i] = float(np.mean(sl))
    return knots_n, knots_r


# -------- public API --------------------------------------------------

def extract_rule(
    dataset: ZeroDataset,
    prev_rule: ZeroRule | None,
    n_correction_terms: int,
    spline_knots: int,
) -> ZeroRule:
    n = dataset.n.astype(np.float64)
    gamma = dataset.gamma

    if prev_rule is None or _OFFSET_A_KEY not in prev_rule.notes:
        offset_a = _fit_offset_a(n, gamma)
    else:
        offset_a = float(
            prev_rule.notes.split(_OFFSET_A_KEY + "=", 1)[1].split(";", 1)[0]
        )

    base = asymptotic_zero(n, offset_a=float(offset_a))
    residual = gamma - base

    u = _normalised_u(n)
    X = _legendre_basis(u, n_correction_terms)
    coeffs = _ridge(X, residual, alpha=1e-3)
    residual_after_param = residual - (X @ coeffs if X.size else 0.0)

    knots_n, knots_r = _fit_spline(n, residual_after_param, spline_knots)
    if knots_n.size >= 2:
        spline_eval = np.interp(n, knots_n, knots_r)
        residual_final = residual_after_param - spline_eval
    else:
        residual_final = residual_after_param

    rms_fit = float(np.sqrt(np.mean(residual_final ** 2)))
    notes = f"{_OFFSET_A_KEY}={offset_a};rms_fit={rms_fit:.6e};"

    return ZeroRule(
        correction_coeffs=coeffs,
        correction_basis="legendre_on_normalised_n",
        spline_knots_n=knots_n,
        spline_knots_r=knots_r,
        fitted_on_n_zeros=int(n.size),
        residual_rms_at_fit=rms_fit,
        notes=notes,
    )


class AgentA:
    name = "A"
    role = "Pattern / Rule Extractor"

    def run(
        self,
        dataset: ZeroDataset,
        prev_rule: ZeroRule | None,
        n_correction_terms: int,
        spline_knots: int,
    ) -> ZeroRule:
        return extract_rule(dataset, prev_rule, n_correction_terms, spline_knots)


def parse_offset_a(rule: ZeroRule) -> float:
    if _OFFSET_A_KEY not in rule.notes:
        return 11.0 / 8.0
    return float(rule.notes.split(_OFFSET_A_KEY + "=", 1)[1].split(";", 1)[0])


# Exposed for Agent B / Agent C so they use the same basis as Agent A.
def legendre_basis_for(n: np.ndarray, n_total: int, k_terms: int) -> np.ndarray:
    """Build the Legendre basis for arbitrary n given the training range
    (1 .. n_total).  Agent B at predict-time must use the SAME normalisation
    as Agent A used at fit time, hence this helper."""
    if k_terms <= 0:
        return np.zeros((np.size(n), 0))
    n_arr = np.asarray(n, dtype=np.float64)
    u = 2.0 * (n_arr - 1.0) / max(n_total - 1, 1) - 1.0
    return _legendre_basis(u, k_terms)
