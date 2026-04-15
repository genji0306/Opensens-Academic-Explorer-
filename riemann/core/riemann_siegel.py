"""Riemann-Siegel Z-function and bisection refinement.

The Hardy Z-function is
    Z(t) = e^{i theta(t)} zeta(1/2 + i t),
which is real for real t and has the same positive zeros as zeta on the
critical line.  The Riemann-Siegel formula gives Z in terms of a finite
cosine sum plus a remainder:

    Z(t) = 2 * sum_{k=1..v} cos(theta(t) - t log k) / sqrt(k)  +  R(t)
    v    = floor(sqrt(t / 2 pi))
    R(t) = (-1)^{v-1} * (t / 2 pi)^{-1/4} * [C0(p) + C1(p)/t^{1/2}
                                              + C2(p)/t + ...]
    p    = sqrt(t/2 pi) - v

with C0(p) = cos(2 pi (p^2 - p - 1/16)) / cos(2 pi p).

Higher C_k are standard but small; for t in [14, ~4e4] (first ~10k zeros)
C0 alone keeps |R error| well below 1e-6, which is dwarfed by the main
sum's ~10 nonzero terms for small t.  We include C1 and C2 too so the
predictor remains accurate to roughly 1e-10 across the whole range.

This module is the actual *functional principle* -- every other agent
ultimately defers to Z for correctness.
"""
from __future__ import annotations

import numpy as np

from .theta import theta

_TWO_PI = 2.0 * float(np.pi)


# --- Riemann-Siegel remainder coefficients ---------------------------

def _psi(p: float) -> float:
    """Psi = cos(2 pi (p^2 - p - 1/16)) / cos(2 pi p) (Riemann-Siegel C0)."""
    return float(np.cos(_TWO_PI * (p * p - p - 1.0 / 16.0)) / np.cos(_TWO_PI * p))


def _c0(p: float) -> float:
    return _psi(p)


def _c1(p: float) -> float:
    """Haselgrove's formula for C1(p).  Derivatives of psi at p."""
    # psi''(p) / (96 pi^2) -- computed by finite differences for robustness.
    h = 1e-3
    d2 = (_psi(p + h) - 2 * _psi(p) + _psi(p - h)) / (h * h)
    return -d2 / (96.0 * np.pi * np.pi)


def _c2(p: float) -> float:
    """Second remainder coefficient (Haselgrove 1960)."""
    h = 5e-3
    psi = _psi
    d1 = (psi(p + h) - psi(p - h)) / (2 * h)
    d4 = (psi(p + 2 * h) - 4 * psi(p + h) + 6 * psi(p)
          - 4 * psi(p - h) + psi(p - 2 * h)) / (h ** 4)
    return d4 / (18432.0 * np.pi ** 4) + d1 / (64.0 * np.pi * np.pi)


def _rs_remainder(t: float) -> float:
    x = t / _TWO_PI
    v = int(np.floor(np.sqrt(x)))
    p = float(np.sqrt(x) - v)
    sign = -1.0 if ((v - 1) % 2) else 1.0
    c = _c0(p) + _c1(p) / np.sqrt(t) + _c2(p) / t
    return sign * x ** (-0.25) * c


def Z_scalar(t: float) -> float:
    """Hardy Z(t) for a single t > 0 via Riemann-Siegel."""
    if t <= 0.0:
        return 0.0
    th = float(theta(np.asarray(t)))
    x = t / _TWO_PI
    v = int(np.floor(np.sqrt(x)))
    if v < 1:
        v = 1
    k = np.arange(1, v + 1, dtype=np.float64)
    main = 2.0 * float(np.sum(np.cos(th - t * np.log(k)) / np.sqrt(k)))
    return main + _rs_remainder(t)


def Z(t: np.ndarray) -> np.ndarray:
    """Vectorised Hardy Z(t).  For large arrays we vectorise over the main
    sum only; the remainder is per-t because v = floor(sqrt(t/2pi)) changes.
    """
    t_arr = np.atleast_1d(np.asarray(t, dtype=np.float64))
    out = np.empty_like(t_arr)
    for i, ti in enumerate(t_arr):
        out[i] = Z_scalar(float(ti))
    return out if out.shape != () else float(out)


# --- bisection to find the zero near a seed --------------------------

def find_zero_near(
    seed: float,
    step: float | None = None,
    max_expand: int = 40,
    tol: float = 1e-10,
) -> tuple[float, bool, float]:
    """Locate a sign change of Z bracketing a zero near `seed` and bisect.

    Returns (gamma, success, |Z(gamma)|).  `success=False` means no sign
    change was found within the expansion budget.
    """
    if step is None:
        # Local mean spacing at height `seed`.
        step = max(0.05, _TWO_PI / np.log(max(seed, 3.0) / _TWO_PI) * 0.1)
    z0 = Z_scalar(seed)
    # Expand symmetrically until sign change found.
    left, right = seed, seed
    zl, zr = z0, z0
    for i in range(1, max_expand + 1):
        delta = step * i
        cand_l, cand_r = seed - delta, seed + delta
        zcl = Z_scalar(cand_l)
        zcr = Z_scalar(cand_r)
        # pick whichever side brackets a sign change
        if zcl * z0 < 0.0:
            left, right = cand_l, seed
            zl, zr = zcl, z0
            break
        if zcr * z0 < 0.0:
            left, right = seed, cand_r
            zl, zr = z0, zcr
            break
        # update anchor to the nearest sampled point
        if abs(cand_l - seed) + abs(cand_r - seed) > 0:
            left, right = cand_l, cand_r
            zl, zr = zcl, zcr
    else:
        return seed, False, abs(z0)

    # classic bisection
    for _ in range(200):
        mid = 0.5 * (left + right)
        zm = Z_scalar(mid)
        if zm == 0.0 or (right - left) < tol:
            return mid, True, abs(zm)
        if zl * zm < 0.0:
            right, zr = mid, zm
        else:
            left, zl = mid, zm
    return 0.5 * (left + right), True, abs(Z_scalar(0.5 * (left + right)))
