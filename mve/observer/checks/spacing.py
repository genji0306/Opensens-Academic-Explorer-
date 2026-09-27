"""Spacing laws and marginal composite diagnostics (not joint likelihoods).

Numerical kernels follow the pinned card001 v2 algorithms for regression continuity.
Gaudin is a sine-kernel Fredholm determinant with Gauss-Legendre quadrature;
CUE uses circular gaps of Haar unitary spectra, including a random cyclic origin.
"""

from functools import lru_cache
import math
import numpy as np
from scipy import optimize, special

PX = np.linspace(0, 12, 48001)
LAMBDA = 1.57314


def gaudin_table(smax=6.0, h=0.002, m=40):
    """E2(0;s) = det(I - K_sine|[0,s]) by Gauss-Legendre (Bornemann 2010); F = 1 + E', p = E''."""
    x0, w0 = np.polynomial.legendre.leggauss(m)
    grid = np.arange(0, smax + h / 2, h)
    E = np.empty_like(grid)
    for i, s in enumerate(grid):
        if s == 0:
            E[i] = 1.0
            continue
        x = (x0 + 1) * s / 2
        w = w0 * s / 2
        K = np.sinc(x[:, None] - x[None, :])
        E[i] = np.linalg.det(np.eye(m) - np.sqrt(w)[:, None] * K * np.sqrt(w)[None, :])
    dE = np.gradient(E, h, edge_order=2)
    p = np.gradient(dE, h, edge_order=2)
    return grid, np.clip(1 + dE, 0, 1), np.clip(p, 1e-300, None)


def wigner_logpdf(x):
    return math.log(32 / math.pi**2) + 2 * np.log(x) - 4 * x**2 / math.pi


def wigner_cdf(x):
    return special.erf(2 * x / math.sqrt(math.pi)) - 4 * x / math.pi * np.exp(
        -4 * x**2 / math.pi
    )


def cue_gaps(n, count, rng):
    """Gap sequence from concatenated Haar-CUE(n) spectra, circular gaps, scaled to mean 1."""
    if type(n) is not int or n < 2 or type(count) is not int or count < 1:
        raise ValueError("CUE needs integer N>=2 and positive count")
    out, have = [], 0
    batch = max(1, min(4000, 200_000 // (n * n)))
    while have < count:
        Z = (
            rng.standard_normal((batch, n, n)) + 1j * rng.standard_normal((batch, n, n))
        ) / math.sqrt(2)
        Q, R = np.linalg.qr(Z)
        d = np.diagonal(R, axis1=1, axis2=2)
        Q = Q * (d / np.abs(d))[:, None, :]
        ph = np.sort(np.angle(np.linalg.eigvals(Q)), axis=1)
        g = (
            np.diff(np.concatenate([ph, ph[:, :1] + 2 * np.pi], axis=1), axis=1)
            * n
            / (2 * np.pi)
        )
        # random cyclic start per matrix: otherwise a thinning stride dividing n always picks the
        # same positions relative to the angle cut at -pi, whose neighbours are size-biased
        roll = (np.arange(n)[None, :] + rng.integers(0, n, batch)[:, None]) % n
        g = np.take_along_axis(g, roll, axis=1)
        out.append(g.ravel())
        have += g.size
    return np.concatenate(out)[:count]


def logexpm1(z):
    return np.where(
        z > 30,
        z + np.log1p(-np.exp(-np.minimum(z, 700))),
        np.log(np.expm1(np.minimum(z, 30))),
    )


def planck_logpdf(x, a, T):
    if not math.isfinite(a) or not math.isfinite(T) or a <= 0 or T <= 0:
        raise ValueError("Planck requires a>0 and T>0")
    # normaliser: int_0^inf y^a/(e^{y/T}-1) dy = T^{a+1} Gamma(a+1) zeta(a+1)
    lz = (a + 1) * math.log(T) + special.gammaln(a + 1) + math.log(special.zeta(a + 1))
    return a * np.log(x) - logexpm1(x / T) - lz


def planck_fit(s, start=(4.5, 0.18)):
    s = positive_sample(s)
    lx = np.log(s)

    def nll(p):
        a, T = p
        if a <= 0.2 or T <= 0.01 or a > 40:
            return 1e18
        lz = (
            (a + 1) * math.log(T)
            + special.gammaln(a + 1)
            + math.log(special.zeta(a + 1))
        )
        return -float(np.sum(a * lx - logexpm1(s / T) - lz))

    r = optimize.minimize(
        nll,
        list(start),
        method="Nelder-Mead",
        options={"xatol": 1e-5, "fatol": 1e-4, "maxiter": 2000},
    )
    if not r.success or r.fun >= 1e18:
        raise ValueError("Planck fit failed within declared numerical bounds")
    return float(r.x[0]), float(r.x[1]), float(-r.fun)


def planck_cdf_table(a, T):
    pdf = np.zeros_like(PX)
    pdf[1:] = np.exp(planck_logpdf(PX[1:], a, T))
    c = np.concatenate([[0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(PX))])
    if not 0.999 <= c[-1] <= 1.001:
        raise ValueError(
            "Planck CDF grid does not resolve analytic normaliser; unsupported fit scale"
        )
    return c / c[-1], float(c[-1])


def ks_d(x_sorted, cdf_vals):
    n = x_sorted.size
    i = np.arange(1, n + 1)
    return float(max(np.max(i / n - cdf_vals), np.max(cdf_vals - (i - 1) / n)))


def exp_mle(s, c):
    small = s[s <= c]
    return small.size / float(np.sum(np.log(c / small))) if small.size else float(
        "nan"
    ), int(small.size)


def exp_implied_from_cdf(xgrid, F, c):
    """Population value of the conditional MLE: b* = F(c) / int_0^c F(s)/s ds."""
    m = (xgrid > 0) & (xgrid <= c)
    xs, Fs = xgrid[m], F[m]
    integral = float(np.sum(0.5 * (Fs[1:] / xs[1:] + Fs[:-1] / xs[:-1]) * np.diff(xs)))
    return float(np.interp(c, xgrid, F)) / integral


def exp_block_ci(s, c, L, B, rng):
    n = s.size
    nb = int(math.ceil(n / L))
    vals = np.empty(B)
    for b in range(B):
        starts = rng.integers(0, n - L + 1, nb)
        idx = (starts[:, None] + np.arange(L)[None, :]).ravel()[:n]
        vals[b] = exp_mle(s[idx], c)[0]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))], float(
        np.std(vals)
    )


def acf(x, lags=(1, 2, 3)):
    x = x - x.mean()
    v = float(np.dot(x, x))
    return {str(k): round(float(np.dot(x[:-k], x[k:]) / v), 4) for k in lags}


def ecdf_fn(sample):
    srt = np.sort(sample)
    return lambda x: np.searchsorted(srt, x, side="right") / srt.size


@lru_cache(maxsize=1)
def _gaudin():
    return gaudin_table()


def gaudin_cdf(x):
    grid, cdf, _ = _gaudin()
    return np.interp(x, grid, cdf, left=0, right=1)


def gaudin_logpdf(x):
    grid, _, pdf = _gaudin()
    return np.log(np.interp(x, grid, pdf))


def n_eff(height, lam=LAMBDA):
    if (
        not math.isfinite(height)
        or height <= 2 * math.pi
        or not math.isfinite(lam)
        or lam <= 0
    ):
        raise ValueError("positive Lambda and height > 2 pi required")
    return math.log(height / (2 * math.pi)) / math.sqrt(12 * lam)


def effective_cue(height, lam=LAMBDA):
    n = n_eff(height, lam)
    return dict(
        N_eff=n,
        N=max(2, round(n)),
        lambda_bogomolny=lam,
        rounding="nearest integer, ties to even, minimum 2",
        approximation="asymptotic large height; unreliable near N_eff=2",
    )


def positive_sample(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.all(np.isfinite(x)) or np.any(x <= 0):
        raise ValueError("at least two finite positive gaps required")
    return x


def composite_scores(x):
    x = positive_sample(x)
    a, t, lp = planck_fit(x)
    scores = {
        "planck": (lp, 2),
        "gaudin": (float(gaudin_logpdf(x).sum()), 0),
        "wigner_secondary": (float(wigner_logpdf(x).sum()), 0),
    }
    return {
        name: dict(
            marginal_composite_score=score,
            parameters=k,
            aic_composite=-2 * score + 2 * k,
            bic_composite=-2 * score + k * math.log(len(x)),
        )
        for name, (score, k) in scores.items()
    }
