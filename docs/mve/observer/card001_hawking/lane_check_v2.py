"""Card #1 (Hawking / Planck gaps), corrected lane check v2 (r6.1, after Astra r6 BLOCK).

Retrospective and exploratory: this specification was written AFTER v1 results were seen.
It is a corrected re-analysis, not a prospective pre-registered test.

Changes from v1 (lane_check.py, kept as the historical record):
  * blocks labelled by zero INDEX; heights reported (Odlyzko headers give the base);
  * unfolding by the smooth counting function, no mean normalisation (mean reported);
  * N_eff = log(H/2pi)/sqrt(12*Lambda), Lambda = 1.57314 (Bogomolny et al. 2006, math/0602270);
  * GUE limit = exact Gaudin law via the sine-kernel Fredholm determinant (Bornemann quadrature);
  * key tests on thinned gaps (every THIN-th gap) to weaken adjacent-gap dependence;
  * fitted-Planck KS calibrated by parametric bootstrap WITH refitting;
  * GUE / CUE(N_eff) KS calibrated by CUE surrogate sequences carrying the same dependence and
    the same thinning;
  * small-gap CDF exponent: conditional power-law MLE on a pre-declared interval (0, S_MAX],
    moving-block bootstrap CI, compared with Planck's CDF exponent a and with the value the same
    estimator returns under each fitted model.
Usage: python3 lane_check_v2.py > lane_check_v2.json
"""
import gzip, hashlib, json, math, os, platform, sys, time
import numpy as np
import scipy
import mpmath
mpmath.mp.dps = 40
from scipy import optimize, special, stats

SPEC = {
    "lambda_bogomolny": 1.57314,
    "thin": 3,                       # key tests use gaps s[0], s[3], s[6], ...
    "s_max_exponent": 0.30,          # exponent interval (0, 0.30], declared before running v2
    "exp_block_len": 100, "exp_boot": 2000,
    "planck_boot": 200, "cue_surrogates": 200,
    "cue_limit_proxy_n": 50,         # CUE(50) surrogates calibrate the GUE-limit KS null
    "cue_reference_gaps": 1_000_000,
    "calibration_n_thinned": 3333,   # null of sqrt(n)*D computed at this n; transferred to low block
    "alpha": 0.01,
    "seed": 20260928,
    "low_skip": 1000,
}
SPEC_SHA = hashlib.sha256(json.dumps(SPEC, sort_keys=True).encode()).hexdigest()
D = os.path.expanduser("~/Developer/Opensens/cache/odlyzko_zeros")
SS = np.random.SeedSequence(SPEC["seed"])
RNG_CUE, RNG_PLANCK, RNG_BOOT = (np.random.default_rng(s) for s in SS.spawn(3))
T0 = time.time()


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- data
def load_high(name):
    lines = open(os.path.join(D, name)).read().splitlines()
    head = " ".join(lines[:4])
    base = int(head.split("gamma - ")[1].split(",")[0])
    vals = []
    for ln in lines:
        try:
            vals.append(float(ln.strip()))
        except ValueError:
            pass
    return base, np.array(vals)


def block_high(name, first_index, tag):
    base, off = load_high(name)
    mid = 0.5 * (off[1:] + off[:-1])
    dens = np.log((float(base) + mid) / (2 * math.pi)) / (2 * math.pi)
    s = np.diff(off) * dens
    h = float(base) + float(np.median(off))
    return {"label": f"zeros #{tag}+1..#{tag}+{off.size}",
            "first_zero_index": first_index, "zeros": int(off.size), "height_median": h,
            "height_range": [mpmath.nstr(mpmath.mpf(base) + mpmath.mpf(repr(float(off[0]))), 25),
                             mpmath.nstr(mpmath.mpf(base) + mpmath.mpf(repr(float(off[-1]))), 25)], "s": s}


def block_low():
    t = np.array([float(x) for x in gzip.open(os.path.join(D, "zeros1.gz"), "rt").read().split()])
    u = t / (2 * np.pi) * np.log(t / (2 * np.pi * np.e)) + 7 / 8 + 1 / (48 * np.pi * t)
    k = SPEC["low_skip"]
    s = np.diff(u)[k:]
    tb = t[k:]
    return {"label": f"zeros #{k + 1}..#{t.size}", "first_zero_index": k + 1,
            "zeros": int(tb.size), "height_median": float(np.median(tb)),
            "height_range": [float(tb[0]), float(tb[-1])], "s": s}


def n_eff(h):
    return math.log(h / (2 * math.pi)) / math.sqrt(12 * SPEC["lambda_bogomolny"])


# ---------------------------------------------------------------- baselines
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


G_GRID, G_CDF, G_PDF = gaudin_table()


def gaudin_cdf(x):
    return np.interp(x, G_GRID, G_CDF, right=1.0)


def gaudin_logpdf(x):
    return np.log(np.interp(x, G_GRID, G_PDF))


def wigner_logpdf(x):
    return math.log(32 / math.pi**2) + 2 * np.log(x) - 4 * x**2 / math.pi


def wigner_cdf(x):
    return special.erf(2 * x / math.sqrt(math.pi)) - 4 * x / math.pi * np.exp(-4 * x**2 / math.pi)


def cue_gaps(n, count, rng):
    """Gap sequence from concatenated Haar-CUE(n) spectra, circular gaps, scaled to mean 1."""
    out, have = [], 0
    batch = max(1, min(4000, 200_000 // (n * n)))
    while have < count:
        Z = (rng.standard_normal((batch, n, n)) + 1j * rng.standard_normal((batch, n, n))) / math.sqrt(2)
        Q, R = np.linalg.qr(Z)
        d = np.diagonal(R, axis1=1, axis2=2)
        Q = Q * (d / np.abs(d))[:, None, :]
        ph = np.sort(np.angle(np.linalg.eigvals(Q)), axis=1)
        g = np.diff(np.concatenate([ph, ph[:, :1] + 2 * np.pi], axis=1), axis=1) * n / (2 * np.pi)
        # random cyclic start per matrix: otherwise a thinning stride dividing n always picks the
        # same positions relative to the angle cut at -pi, whose neighbours are size-biased
        roll = (np.arange(n)[None, :] + rng.integers(0, n, batch)[:, None]) % n
        g = np.take_along_axis(g, roll, axis=1)
        out.append(g.ravel())
        have += g.size
    return np.concatenate(out)[:count]


# ---------------------------------------------------------------- Planck family
def logexpm1(z):
    return np.where(z > 30, z + np.log1p(-np.exp(-np.minimum(z, 700))), np.log(np.expm1(np.minimum(z, 30))))


def planck_logpdf(x, a, T):
    # normaliser: int_0^inf y^a/(e^{y/T}-1) dy = T^{a+1} Gamma(a+1) zeta(a+1)
    lz = (a + 1) * math.log(T) + special.gammaln(a + 1) + math.log(special.zeta(a + 1))
    return a * np.log(x) - logexpm1(x / T) - lz


def planck_fit(s, start=(4.5, 0.18)):
    lx = np.log(s)

    def nll(p):
        a, T = p
        if a <= 0.2 or T <= 0.01 or a > 40:
            return 1e18
        lz = (a + 1) * math.log(T) + special.gammaln(a + 1) + math.log(special.zeta(a + 1))
        return -float(np.sum(a * lx - logexpm1(s / T) - lz))

    r = optimize.minimize(nll, list(start), method="Nelder-Mead",
                          options={"xatol": 1e-5, "fatol": 1e-4, "maxiter": 2000})
    return float(r.x[0]), float(r.x[1]), float(-r.fun)


PX = np.linspace(0, 12, 48001)


def planck_cdf_table(a, T):
    pdf = np.zeros_like(PX)
    pdf[1:] = np.exp(planck_logpdf(PX[1:], a, T))
    c = np.concatenate([[0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(PX))])
    return c / c[-1], float(c[-1])


def ks_d(x_sorted, cdf_vals):
    n = x_sorted.size
    i = np.arange(1, n + 1)
    return float(max(np.max(i / n - cdf_vals), np.max(cdf_vals - (i - 1) / n)))


# ---------------------------------------------------------------- exponent
def exp_mle(s, c):
    small = s[s <= c]
    return small.size / float(np.sum(np.log(c / small))) if small.size else float("nan"), int(small.size)


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
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))], float(np.std(vals))


def acf(x, lags=(1, 2, 3)):
    x = x - x.mean()
    v = float(np.dot(x, x))
    return {str(k): round(float(np.dot(x[:-k], x[k:]) / v), 4) for k in lags}


# ---------------------------------------------------------------- calibration of the GUE/CUE KS
def surrogate_null(n_cue, ref_cdf, n_thin, M, rng):
    """sqrt(n)*D under CUE(n_cue) surrogate sequences, thinned exactly like the data."""
    th = SPEC["thin"]
    out = np.empty(M)
    for j in range(M):
        g = cue_gaps(n_cue, n_thin * th, rng)[::th][:n_thin]
        gs = np.sort(g)
        out[j] = ks_d(gs, ref_cdf(gs)) * math.sqrt(n_thin)
    return out


def ecdf_fn(sample):
    srt = np.sort(sample)
    return lambda x: np.searchsorted(srt, x, side="right") / srt.size


def calibrated_p(stat, null):
    return (1 + int(np.sum(null >= stat))) / (null.size + 1)


# ---------------------------------------------------------------- main
def main():
    blocks = [block_low(), block_high("zeros3", 10**12 + 1, "10^12"),
              block_high("zeros4", 10**21 + 1, "10^21"), block_high("zeros5", 10**22 + 1, "10^22")]
    th, c = SPEC["thin"], SPEC["s_max_exponent"]
    ncal = SPEC["calibration_n_thinned"]
    M = SPEC["cue_surrogates"]

    # GUE-limit calibration: one null for sqrt(n)*D, shared by all blocks (transfer to low block)
    lim_null = surrogate_null(SPEC["cue_limit_proxy_n"], gaudin_cdf, ncal, M, RNG_CUE)
    lim_ref = cue_gaps(SPEC["cue_limit_proxy_n"], 200_000, RNG_CUE)
    cue_cache = {}
    rows = []
    for blk in blocks:
        s = blk["s"]
        st = s[::th]
        n_t = st.size
        sts = np.sort(st)
        ne = n_eff(blk["height_median"])
        ne_rng = [n_eff(float(h)) for h in blk["height_range"]]
        n_round = max(2, int(round(ne)))
        if n_round not in cue_cache:
            ref = cue_gaps(n_round, SPEC["cue_reference_gaps"], RNG_CUE)
            fn = ecdf_fn(ref)
            cue_cache[n_round] = (ref, fn, surrogate_null(n_round, fn, ncal, M, RNG_CUE))
        cue_ref, cue_fn, cue_null = cue_cache[n_round]

        # GUE-limit (Gaudin) and CUE(N_eff) KS on the thinned sample
        d_lim = ks_d(sts, gaudin_cdf(sts))
        d_cue = ks_d(sts, cue_fn(sts))
        p_lim = calibrated_p(d_lim * math.sqrt(n_t), lim_null)
        p_cue = calibrated_p(d_cue * math.sqrt(n_t), cue_null)

        # Planck fit + parametric bootstrap with refitting
        a, Tp, llp = planck_fit(st)
        Fp, zcheck = planck_cdf_table(a, Tp)
        d_pl = ks_d(sts, np.interp(sts, PX, Fp))
        boot = np.empty(SPEC["planck_boot"])
        for b in range(boot.size):
            xb = np.interp(RNG_PLANCK.random(n_t), Fp, PX)
            xb = np.clip(xb, 1e-9, None)
            ab, Tb, _ = planck_fit(xb, start=(a, Tp))
            Fb, _ = planck_cdf_table(ab, Tb)
            xbs = np.sort(xb)
            boot[b] = ks_d(xbs, np.interp(xbs, PX, Fb))
        p_pl = calibrated_p(d_pl, boot)

        ll_w = float(np.sum(wigner_logpdf(st)))
        ll_g = float(np.sum(gaudin_logpdf(st)))

        # exponent
        b_hat, n_small = exp_mle(s, c)
        ci, se = exp_block_ci(s, c, SPEC["exp_block_len"], SPEC["exp_boot"], RNG_BOOT)
        implied = {
            "gue_limit_gaudin": exp_implied_from_cdf(G_GRID, G_CDF, c),
            "wigner_surmise": exp_implied_from_cdf(PX, wigner_cdf(PX), c),
            f"cue_N{n_round}": exp_mle(cue_ref, c)[0],
            "planck_fitted": exp_implied_from_cdf(PX, Fp, c),
        }
        rows.append({
            "block": blk["label"], "first_zero_index": blk["first_zero_index"],
            "zeros": blk["zeros"], "gaps_all": int(s.size), "gaps_thinned": int(n_t),
            "height_median": blk["height_median"], "height_range": blk["height_range"],
            "unfolded_mean_gap": round(float(s.mean()), 6),
            "n_eff": round(ne, 3), "n_eff_range_over_block": [round(v, 3) for v in ne_rng],
            "cue_n_used": n_round,
            "acf_all": acf(s), "acf_thinned": acf(st),
            "gue_limit_ks": {"D": round(d_lim, 5), "sqrtn_D": round(d_lim * math.sqrt(n_t), 4),
                             "p_calibrated": round(p_lim, 4),
                             "p_nominal_iid": float(stats.kstwo.sf(d_lim, n_t)),
                             "calibration": ("CUE(50) surrogates, n=%d thinned" % ncal) +
                                            ("" if n_t == ncal else "; sqrt(n)*D transferred to this n")},
            "cue_neff_ks": {"N": n_round, "D": round(d_cue, 5), "p_calibrated": round(p_cue, 4),
                            "p_nominal_iid": float(stats.kstwo.sf(d_cue, n_t))},
            "planck": {"a": round(a, 4), "T": round(Tp, 5), "cdf_exponent_a": round(a, 4),
                       "normaliser_numeric_over_analytic": round(zcheck, 6),
                       "ks_D": round(d_pl, 5), "ks_p_nominal_fixed_cdf_INVALID": float(stats.kstwo.sf(d_pl, n_t)),
                       "ks_p_bootstrap_refit": round(p_pl, 4), "boot_replicates": int(boot.size),
                       "boot_D_max": round(float(boot.max()), 5), "boot_D_q95": round(float(np.quantile(boot, .95)), 5),
                       "fit_denominator": int(n_t)},
            "marginal_loglik_thinned": {
                "note": "sum of marginal log densities; a composite score, not a joint likelihood",
                "planck_minus_wigner": round(llp - ll_w, 2),
                "planck_minus_gaudin": round(llp - ll_g, 2),
                "gaudin_minus_wigner": round(ll_g - ll_w, 2),
                "bic_penalty_planck_2p_vs_0p": round(math.log(n_t), 2)},
            "cdf_exponent": {"interval": [0, c], "estimator": "conditional power-law MLE",
                             "n_small": n_small, "b_hat": round(b_hat, 4),
                             "ci95_block_bootstrap": [round(v, 4) for v in ci], "se": round(se, 4),
                             "implied_by_model_same_estimator": {k: round(v, 4) for k, v in implied.items()},
                             "planck_a_inside_ci": bool(ci[0] <= a <= ci[1]),
                             "planck_implied_inside_ci": bool(ci[0] <= implied["planck_fitted"] <= ci[1]),
                             "gaudin_implied_inside_ci": bool(ci[0] <= implied["gue_limit_gaudin"] <= ci[1])},
        })
    q95 = float(np.quantile(lim_null, 0.95))
    out = {
        "card": "card001_hawking", "version": "lane_check_v2", "status": "retrospective_exploratory",
        "spec": SPEC, "spec_sha256": SPEC_SHA,
        "p_value_floor": {"planck_bootstrap": round(1 / (SPEC["planck_boot"] + 1), 4),
                          "cue_surrogates": round(1 / (SPEC["cue_surrogates"] + 1), 4),
                          "note": "a calibrated p equal to the floor means no replicate reached the observed statistic"},
        "script_sha256": sha256(os.path.abspath(__file__)),
        "inputs_sha256": {f: sha256(os.path.join(D, f)) for f in ("zeros1.gz", "zeros3", "zeros4", "zeros5")},
        "env": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "mpmath": mpmath.__version__, "platform": platform.platform()},
        "dependence_check": {
            "cue50_thinned_sqrtnD_q95": round(q95, 4), "kolmogorov_iid_q95": 1.3581,
            "cue50_acf_all": acf(lim_ref), "cue50_acf_thinned": acf(lim_ref[::th])},
        "gaudin_check": {"mean_gap": round(float(np.sum(G_PDF * G_GRID) * (G_GRID[1] - G_GRID[0])), 5),
                         "cdf_at_6": round(float(G_CDF[-1]), 6)},
        "blocks": rows,
        "runtime_s": round(time.time() - T0, 1),
    }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
