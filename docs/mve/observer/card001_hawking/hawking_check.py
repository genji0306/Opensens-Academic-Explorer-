import json, math, sys
import numpy as np
from mpmath import mp, zetazero
from scipy import optimize, integrate, stats
mp.dps = 20
N = int(sys.argv[1])
t = np.array([float(zetazero(n).imag) for n in range(1, N + 1)])
def smooth(x):  # Riemann-von Mangoldt main terms
    return x / (2 * np.pi) * np.log(x / (2 * np.pi * np.e)) + 7 / 8
u = smooth(t); s = np.diff(u)[20:]           # drop the first 20 low zeros
s = s / s.mean()
def gue(x): return 32 / np.pi**2 * x**2 * np.exp(-4 * x**2 / np.pi)
def planck_pdf(x, a, T):
    z, _ = integrate.quad(lambda y: y**a / np.expm1(y / T), 0, np.inf)
    return x**a / np.expm1(x / T) / z
def nll(p):
    a, T = p
    if a <= 0.2 or T <= 0.01: return 1e12
    return -np.sum(np.log(planck_pdf(s, a, T) + 1e-300))
fit = optimize.minimize(nll, [3.0, 0.3], method="Nelder-Mead")
a, T = fit.x
ll_gue = float(np.sum(np.log(gue(s))))
ll_planck = float(-fit.fun)
cdf_gue = lambda x: np.array([integrate.quad(gue, 0, v)[0] for v in np.atleast_1d(x)])
cdf_pl = lambda x: np.array([integrate.quad(lambda y: planck_pdf(y, a, T), 0, v)[0] for v in np.atleast_1d(x)])
ks_gue = stats.kstest(s, cdf_gue).pvalue
ks_pl = stats.kstest(s, cdf_pl).pvalue
small = s[s < 0.5]
tail = {"frac_gt_2": float(np.mean(s > 2)), "gue_gt_2": float(1 - cdf_gue(2)[0]),
        "planck_gt_2": float(1 - cdf_pl(2)[0]), "poisson_gt_2": float(math.exp(-2))}
print(json.dumps({"zeros": N, "gaps": int(s.size), "planck_fit": {"a": round(a, 3), "T": round(T, 4)},
  "loglik": {"gue_wigner": round(ll_gue, 2), "planck_family_2param": round(ll_planck, 2),
             "delta_planck_minus_gue": round(ll_planck - ll_gue, 2)},
  "ks_pvalue": {"gue": round(float(ks_gue), 4), "planck": round(float(ks_pl), 4)},
  "frac_below_half": round(float(np.mean(s < 0.5)), 4), "tail": tail}, indent=1))
