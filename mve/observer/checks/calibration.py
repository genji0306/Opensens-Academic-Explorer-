"""Actual-size block refits and joint structural bootstrap; nominal by default.

Size validation is against a declared CUE copula transformed to the fitted Planck
marginal (a known dependent null). It is conditional on that null, not a claim
about dependence in zeta zeros. No calibration is transferred across sample sizes.
"""

import math
import numpy as np
from scipy import stats
from mve.observer.card import digest
from . import spacing as s


def mc_tail(exceedances, replicates):
    if not 0 <= exceedances <= replicates or replicates < 1:
        raise ValueError("invalid Monte Carlo counts")
    upper = (
        1.0
        if exceedances == replicates
        else float(stats.beta.ppf(0.95, exceedances + 1, replicates - exceedances))
    )
    return dict(
        exceedances=int(exceedances),
        replicates=int(replicates),
        p_mc=(1 + exceedances) / (1 + replicates),
        upper95=upper,
    )


def _settings(x, thin, block_len, replicates):
    x = s.positive_sample(x)
    if any(type(v) is not int or v < 1 for v in (thin, block_len, replicates)):
        raise ValueError("positive integer settings required")
    if block_len < 2 or block_len > len(x) or len(x[::thin]) < 2:
        raise ValueError("block or thinning exceeds actual sample size")
    return x


def moving_blocks(x, block_len, rng):
    starts = rng.integers(0, len(x) - block_len + 1, math.ceil(len(x) / block_len))
    return x[(starts[:, None] + np.arange(block_len)).ravel()[: len(x)]]


def fitted_ks(x, model="planck"):
    if model == "planck":
        a, t, _ = s.planck_fit(x)
        F, _ = s.planck_cdf_table(a, t)
    elif model == "gaudin":
        a, t, F = 3, None, s.gaudin_cdf(s.PX)
    else:
        raise ValueError("unsupported spacing model")
    xs = np.sort(x)
    return s.ks_d(xs, np.interp(xs, s.PX, F)), a, t, F


def procedure(
    n, thin, block_len, replicates, cutoff=0.3, joint_replicates=19, alpha=0.01
):
    return dict(
        version="spacing-v1",
        sample_size=n,
        thin=thin,
        block_len=block_len,
        replicates=replicates,
        cutoff=cutoff,
        joint_replicates=joint_replicates,
        alpha=alpha,
        unfolding="already_unfolded",
        method="rank_moving_block_refit",
    )


def calibrate(x, *, thin=3, block_len=12, replicates=19, seed=0, model="planck"):
    x = _settings(x, thin, block_len, replicates)
    rng = np.random.default_rng(seed)
    observed, a, t, F = fitted_ks(x[::thin], model)
    # Keep the full sequence's rank copula, then resample contiguous blocks before thinning.
    ranks = stats.rankdata(x, method="average") / (len(x) + 1)
    null_sequence = np.clip(np.interp(ranks, F, s.PX), 1e-9, None)
    null = [
        fitted_ks(moving_blocks(null_sequence, block_len, rng)[::thin], model)[0]
        for _ in range(replicates)
    ]
    n = len(x[::thin])
    return dict(
        label="nominal",
        inferential=False,
        method="rank_moving_block_refit",
        raw_size=len(x),
        fit_size=n,
        test_size=n,
        replicate_sizes=[n] * replicates,
        refits=replicates if model == "planck" else 0,
        model=model,
        seed=seed,
        thin=thin,
        block_len=block_len,
        statistic=observed,
        a=a,
        T=t,
        null_statistics=null,
        **mc_tail(sum(v >= observed for v in null), replicates),
    )


def joint_exponent(
    x,
    *,
    thin=3,
    block_len=12,
    replicates=19,
    seed=1,
    cutoff=0.3,
    alpha=0.005,
    model="planck",
):
    x = _settings(x, thin, block_len, replicates)
    if not 0 < alpha < 1 or not 2 * s.PX[1] <= cutoff <= s.PX[-1]:
        raise ValueError("invalid exponent interval or alpha")
    _, a, t, F = fitted_ks(x[::thin], model)
    measured = s.exp_mle(x, cutoff)[0]
    implied = s.exp_implied_from_cdf(s.PX, F, cutoff)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(replicates):
        xb = moving_blocks(x, block_len, rng)
        if model == "planck":
            ab, tb, _ = s.planck_fit(xb[::thin], start=(a, t))
            fb, _ = s.planck_cdf_table(ab, tb)
        else:
            fb = F
        values.append(
            s.exp_mle(xb, cutoff)[0] - s.exp_implied_from_cdf(s.PX, fb, cutoff)
        )
    finite = bool(np.isfinite(measured) and np.all(np.isfinite(values)))
    ci = (
        list(map(float, np.quantile(values, [alpha / 2, 1 - alpha / 2])))
        if finite
        else None
    )
    return dict(
        label="nominal",
        inferential=False,
        measured=float(measured) if np.isfinite(measured) else None,
        model_implied=implied,
        difference=float(measured - implied) if np.isfinite(measured) else None,
        model_asymptotic_exponent=a,
        gaudin_asymptotic_exponent=3,
        interval=[0, cutoff],
        estimator="conditional_power_mle",
        ci=ci,
        alpha=alpha,
        refits=replicates if model == "planck" else 0,
        model=model,
        replicates=replicates,
        seed=seed,
        fit_size=len(x[::thin]),
        test_size=len(x),
        complete=finite,
    )


def rule_fires(ks, exponent, rule):
    """One frozen union rule. Monte Carlo upper bound is required for a KS kill."""
    for component in rule["components"]:
        if component["statistic"] == "ks":
            if ks["upper95"] < component["alpha"]:
                return True
        else:
            if exponent["alpha"] != component["alpha"]:
                raise ValueError("structural alpha does not match kill rule")
            ci = exponent["ci"]
            if ci is not None and (ci[1] < 0 or ci[0] > 0):
                return True
    return False


def size_check(
    *,
    n,
    cue_n=6,
    thin=3,
    block_len=12,
    replicates=19,
    trials=5,
    joint_replicates=19,
    cutoff=0.3,
    seed=0,
    alpha=0.01,
    rule=None,
):
    """Validate the complete union rule on independent sequences from a known null.

    CUE circular gaps -> finite-CUE empirical CDF -> Planck inverse CDF creates
    a declared dependent Planck null. Reference size and seed are recorded. The
    conservative acceptance rule requires the size's one-sided 95% upper bound
    <= overall alpha AND at least 20/alpha trials and inner replicates. Small
    defaults exercise code only and can never establish calibration.
    """
    if trials < 1 or not 0 < alpha < 1:
        raise ValueError("invalid size-check trials/alpha")
    rule = rule or dict(
        method="primary",
        overall_alpha=alpha,
        components=[dict(statistic="ks", alpha=alpha)],
    )
    from mve.observer.card import check_rule

    check_rule(rule)
    if rule["overall_alpha"] != alpha:
        raise ValueError("size-check alpha mismatch")
    rng = np.random.default_rng(seed)
    ref_count = max(10000, n * 10)
    reference = np.sort(s.cue_gaps(cue_n, ref_count, rng))
    F, _ = s.planck_cdf_table(4.3, 0.19)
    rejected = 0
    exp_alpha = next(
        (
            c["alpha"]
            for c in rule["components"]
            if c["statistic"] == "exponent_difference"
        ),
        alpha,
    )
    for _ in range(trials):
        gaps = s.cue_gaps(cue_n, n, rng)
        u = (np.searchsorted(reference, gaps, side="right") + 0.5) / (
            len(reference) + 1
        )
        x = np.clip(np.interp(u, F, s.PX), 1e-9, None)
        ks = calibrate(
            x,
            thin=thin,
            block_len=block_len,
            replicates=replicates,
            seed=int(rng.integers(2**32)),
        )
        joint = joint_exponent(
            x,
            thin=thin,
            block_len=block_len,
            replicates=joint_replicates,
            cutoff=cutoff,
            alpha=exp_alpha,
            seed=int(rng.integers(2**32)),
        )
        rejected += rule_fires(ks, joint, rule)
    tail = mc_tail(rejected, trials)
    required = math.ceil(20 / alpha)
    minimum_alpha = min(c["alpha"] for c in rule["components"])
    validated = (
        trials >= required
        and replicates >= math.ceil(20 / minimum_alpha)
        and joint_replicates >= math.ceil(20 / minimum_alpha)
        and tail["upper95"] <= alpha
    )
    config = procedure(n, thin, block_len, replicates, cutoff, joint_replicates, alpha)
    return dict(
        label="validated_conditional" if validated else "nominal",
        validated=validated,
        sample_size=n,
        required_trials=required,
        trials=trials,
        rejected=rejected,
        upper95=tail["upper95"],
        null="CUE_copula_Planck_marginal",
        cue_n=cue_n,
        reference_size=ref_count,
        seed=seed,
        parameters=[4.3, 0.19],
        procedure=config,
        procedure_sha256=digest(config),
        kill_rule=rule,
        scope="declared dependent null only; no zeta dependence certification",
    )
