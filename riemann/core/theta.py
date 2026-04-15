"""Riemann-Siegel theta function and its numerical inverse.

    theta(t) = arg Gamma(1/4 + i t / 2) - (t/2) log(pi)

theta is strictly increasing for t > ~6.3, so it has a well-defined inverse.
The n-th non-trivial zero satisfies, to leading order,

    theta(gamma_n) = (n - a) * pi

for some near-constant offset a (Gram's law: a = 11/8 is a common choice;
we keep it as a fittable parameter).

Implementation notes
--------------------
* `scipy.special.loggamma` handles complex arguments with full precision;
  we use its imaginary part for theta.
* For the inverse we seed with the Riemann--von Mangoldt asymptotic
    t ~ 2 pi x / W(x / e),   x = n - a
  where W is the Lambert W function, then Newton iterate on theta.
"""
from __future__ import annotations

import numpy as np
from scipy.special import loggamma, lambertw

_LOG_PI = float(np.log(np.pi))
_TWO_PI = 2.0 * float(np.pi)


def theta(t: np.ndarray) -> np.ndarray:
    """Exact theta via complex log-Gamma (vectorised)."""
    t = np.asarray(t, dtype=np.float64)
    z = 0.25 + 0.5j * t
    return np.imag(loggamma(z)) - 0.5 * t * _LOG_PI


def theta_prime(t: np.ndarray) -> np.ndarray:
    """d theta / d t.  Asymptotic = 0.5 log(t / 2 pi); we refine with
    the next Stirling correction for tiny t."""
    t = np.asarray(t, dtype=np.float64)
    safe = np.where(t > 1e-6, t, 1e-6)
    return 0.5 * np.log(safe / _TWO_PI) - 1.0 / (24.0 * safe * safe)


def _seed_asymptotic(x: np.ndarray) -> np.ndarray:
    """Seed for theta(t) = x * pi via the Lambert-W inversion of the
    Riemann--von Mangoldt asymptotic N(T) ~ (T/2 pi) log(T / 2 pi e).

    Valid for x >= 1; the first few zeros need a minimum floor.
    """
    x = np.asarray(x, dtype=np.float64)
    # Riemann--von Mangoldt inverse: t = 2 pi x / W(x / e)
    xe = np.maximum(x / np.e, 1e-6)
    w = np.real(lambertw(xe))
    t = _TWO_PI * np.maximum(x, 0.5) / np.maximum(w, 1e-6)
    return np.maximum(t, 10.0)


def invert(
    target: np.ndarray,
    tol: float = 1e-12,
    max_iter: int = 80,
) -> np.ndarray:
    """Solve theta(t) = target for t, element-wise.

    Parameters
    ----------
    target : ndarray of target theta values (any real).
    tol    : absolute Newton tolerance on theta.
    max_iter : Newton budget.

    Returns
    -------
    t : ndarray of solutions, same shape as target.
    """
    target = np.asarray(target, dtype=np.float64)
    # Seed from the scaled Lambert-W inverse.  target = theta(t) ~ x * pi
    # with x = (t/2 pi) log(t/2 pi e).  We use target/pi as x.
    t = _seed_asymptotic(target / np.pi + 1.0)
    for _ in range(max_iter):
        f = theta(t) - target
        # Newton step with clipped derivative (theta is monotone for t > 6).
        fp = np.maximum(theta_prime(t), 1e-6)
        dt = f / fp
        # Damp to avoid jumping across branches near very small t.
        dt = np.clip(dt, -0.5 * np.abs(t) - 1.0, 0.5 * np.abs(t) + 1.0)
        t = t - dt
        if np.max(np.abs(f)) < tol:
            break
    return t


def asymptotic_zero(
    n: np.ndarray,
    offset_a: float = 11.0 / 8.0,
    tol: float = 1e-12,
    max_iter: int = 80,
) -> np.ndarray:
    """Asymptotic estimate of gamma_n via theta(gamma_n) = (n - a) pi."""
    n = np.asarray(n, dtype=np.float64)
    return invert(np.pi * (n - offset_a), tol=tol, max_iter=max_iter)
