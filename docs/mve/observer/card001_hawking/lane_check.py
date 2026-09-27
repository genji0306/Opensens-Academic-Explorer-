"""Attack lane for hypothesis card H0 (Planck-shaped gap law) vs GUE / finite-N CUE."""
import gzip, json, math, os
import numpy as np
from scipy import optimize, integrate, stats
from scipy.stats import unitary_group
D = os.path.expanduser("~/Developer/Opensens/cache/odlyzko_zeros")
rng = np.random.default_rng(2026)

def load_high(name):
    lines = open(os.path.join(D, name)).read().splitlines()
    head = " ".join(lines[:4]); base = int(head.split("gamma - ")[1].split(",")[0])
    vals = []
    for ln in lines:
        try: vals.append(float(ln.strip()))
        except ValueError: pass
    return base, np.array(vals)

def spacings_high(name):
    base, off = load_high(name)
    T = float(base) + off.mean()
    dens = math.log(T / (2 * math.pi)) / (2 * math.pi)
    s = np.diff(off) * dens
    return T, s / s.mean()

def spacings_low():
    t = np.array([float(x) for x in gzip.open(os.path.join(D, "zeros1.gz"), "rt").read().split()])
    u = t / (2 * np.pi) * np.log(t / (2 * np.pi * np.e)) + 7 / 8
    s = np.diff(u)[1000:]  # skip the lowest 1000
    return float(np.median(t[1000:])), s / s.mean()

def cue_sample(n, count):
    out = []
    while sum(len(o) for o in out) < count:
        ph = np.sort(np.angle(np.linalg.eigvals(unitary_group.rvs(n, random_state=rng))))
        g = np.diff(np.concatenate([ph, [ph[0] + 2 * np.pi]])) * n / (2 * np.pi)
        out.append(g)
    return np.concatenate(out)[:count]

def wigner(x): return 32 / np.pi**2 * x**2 * np.exp(-4 * x**2 / np.pi)
def wigner_cdf(x): return np.array([integrate.quad(wigner, 0, v)[0] for v in np.atleast_1d(x)])

def planck_fit(s):
    def pdfn(x, a, T):
        z = integrate.quad(lambda y: y**a / np.expm1(min(y / T, 700)), 0, 40)[0]
        return x**a / np.expm1(np.minimum(x / T, 700)) / z
    nll = lambda p: 1e12 if p[0] <= .2 or p[1] <= .01 else -np.sum(np.log(pdfn(s, *p) + 1e-300))
    r = optimize.minimize(nll, [3.0, .3], method="Nelder-Mead")
    a, T = r.x
    cdf = lambda x: np.array([integrate.quad(lambda y: pdfn(y, a, T), 0, v)[0] for v in np.atleast_1d(x)])
    return a, T, -r.fun, cdf

def small_exponent(s, lo=0.1, hi=0.4):
    xs = np.linspace(lo, hi, 8); F = np.array([np.mean(s < x) for x in xs])
    k = np.polyfit(np.log(xs), np.log(F), 1)[0]
    return float(k)  # CDF exponent: GUE ~ 3 (density s^2)

rows = []
sets = [("low zeros 1001-100000", *spacings_low())] + [
    (f"zeros {n}", *spacings_high(f)) for n, f in (("1e12+", "zeros3"), ("1e21+", "zeros4"), ("1e22+", "zeros5"))]
for label, T, s in sets:
    n_eff = math.log(T / (2 * math.pi)) / math.sqrt(12)
    cue = cue_sample(max(2, round(n_eff)), 200000)
    big = cue_sample(200, 200000)
    s_fit = s if s.size <= 12000 else rng.choice(s, 12000, replace=False)
    a, Tp, llp, pcdf = planck_fit(s_fit)
    llw = float(np.sum(np.log(wigner(s_fit))))
    rows.append({
        "set": label, "height_T": T, "gaps": int(s.size), "n_eff_BK": round(n_eff, 2),
        "cdf_small_gap_exponent": round(small_exponent(s), 3),
        "ks_p": {"wigner_surmise": float(stats.kstest(s_fit, wigner_cdf).pvalue),
                 "cue_N200": float(stats.ks_2samp(s, big).pvalue),
                 "cue_Neff": float(stats.ks_2samp(s, cue).pvalue),
                 "planck_fitted": float(stats.kstest(s_fit, pcdf).pvalue)},
        "planck": {"a": round(a, 3), "T": round(Tp, 4), "density_small_exponent": round(a - 1, 3),
                   "dloglik_vs_wigner": round(llp - llw, 2)},
    })
print(json.dumps(rows, indent=1))
