"""Card #1 sanity addendum to lane_check_v2 (r6.2). EXPLORATORY; NOT an inferential certification.

Demonstrates, on the retrospective card-#1 data, the two calibration devices r6.2 requires of
future prospective checks. The devices themselves are not validated here (no size check against
a known dependent null), so every number below is nominal.

1. Dependence-preserving refit calibration of the fitted-Planck KS at the ACTUAL thinned size:
   quantile transform s*_i = F_fit^{-1}(rank(s_i)/(n+1)) of the full unfolded sequence (data copula,
   fitted marginal), moving-block bootstrap of s* (block BLOCK), thin every 3rd gap, refit, KS.
2. Joint moving-block bootstrap of the difference (measured CDF exponent - Planck-implied exponent),
   refitting Planck on each replicate, with a 99.5% percentile CI (one component of a Bonferroni
   0.5% + 0.5% kill rule).
Usage: python3 lane_check_v2_sanity.py > lane_check_v2_sanity.json
"""
import json, math, os, platform, sys, time
import numpy as np
import scipy

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_check_v2 as v2  # noqa: E402  (module import runs no analysis)

B_KS, B_DIFF, BLOCK, SEED = 400, 1000, 100, 20260929
RNG = np.random.default_rng(SEED)
T0 = time.time()


def block_resample(x, rng):
    n = x.size
    nb = int(math.ceil(n / BLOCK))
    starts = rng.integers(0, n - BLOCK + 1, nb)
    return x[(starts[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]]


def ks_fitted(st):
    a, T, _ = v2.planck_fit(st)
    F, _ = v2.planck_cdf_table(a, T)
    ss = np.sort(st)
    return v2.ks_d(ss, np.interp(ss, v2.PX, F)), a, T, F


def run_block(blk):
    s = blk["s"]
    th, c = v2.SPEC["thin"], v2.SPEC["s_max_exponent"]
    st = s[::th]
    d_obs, a, T, F = ks_fitted(st)
    # 1. copula-preserving null: fitted marginal, data ranks
    u = (np.argsort(np.argsort(s)) + 1) / (s.size + 1)
    s_null = np.clip(np.interp(u, F, v2.PX), 1e-9, None)
    null = np.array([ks_fitted(block_resample(s_null, RNG)[::th])[0] for _ in range(B_KS)])
    exceed = int(np.sum(null >= d_obs))
    # 2. joint bootstrap of measured - implied exponent
    diffs = np.empty(B_DIFF)
    for b in range(B_DIFF):
        sb = block_resample(s, RNG)
        ab, Tb, _ = v2.planck_fit(sb[::th], start=(a, T))
        Fb, _ = v2.planck_cdf_table(ab, Tb)
        diffs[b] = v2.exp_mle(sb, c)[0] - v2.exp_implied_from_cdf(v2.PX, Fb, c)
    obs_diff = v2.exp_mle(s, c)[0] - v2.exp_implied_from_cdf(v2.PX, F, c)
    lo, hi = np.percentile(diffs, [0.25, 99.75])
    return {"block": blk["label"], "gaps_thinned": int(st.size), "ks_D": round(d_obs, 5),
            "copula_null": {"replicates": B_KS, "exceedances": exceed,
                            "p_mc": round((1 + exceed) / (B_KS + 1), 5),
                            "p_upper95_if_zero_exceed": round(1 - 0.05 ** (1 / B_KS), 5) if exceed == 0 else None,
                            "null_D_max": round(float(null.max()), 5),
                            "null_D_q99": round(float(np.quantile(null, 0.99)), 5)},
            "exponent_difference": {"measured_minus_planck_implied": round(obs_diff, 4),
                                    "ci99_5_joint_block_bootstrap": [round(lo, 4), round(hi, 4)],
                                    "replicates": B_DIFF, "excludes_zero": bool(hi < 0 or lo > 0)}}


def main():
    blocks = [v2.block_low(), v2.block_high("zeros3", 10**12 + 1, "10^12"),
              v2.block_high("zeros4", 10**21 + 1, "10^21"), v2.block_high("zeros5", 10**22 + 1, "10^22")]
    out = {"card": "card001_hawking", "version": "lane_check_v2_sanity",
           "status": "exploratory_nominal_not_inferential",
           "caveat": "devices not validated by a size check against a known dependent null; "
                     "retrospective data; replication size 9,999 < declared 10,000",
           "params": {"B_ks": B_KS, "B_diff": B_DIFF, "block_len": BLOCK, "seed": SEED,
                      "v2_spec_sha256": v2.SPEC_SHA},
           "script_sha256": v2.sha256(os.path.abspath(__file__)),
           "v2_script_sha256": v2.sha256(os.path.abspath(v2.__file__)),
           "env": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
           "blocks": [run_block(b) for b in blocks]}
    out["runtime_s"] = round(time.time() - T0, 1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
