import numpy as np
import pytest
from scipy.integrate import quad
from mve.observer.checks import spacing as s
from mve.observer.checks.calibration import (
    calibrate,
    joint_exponent,
    size_check,
    mc_tail,
)


def sample(n=240):
    return s.cue_gaps(6, n, np.random.default_rng(3))


def test_baselines_and_normaliser():
    x, F, p = s.gaudin_table(h=0.01)
    assert abs(np.trapezoid(p * x, x) - 1) < 0.001
    assert abs(s.exp_implied_from_cdf(x, F, 0.3) - 2.9164) < 0.01
    assert s.n_eff(1.4417689750954697e20) == pytest.approx(10.260364, rel=1e-6)
    assert s.effective_cue(1.4417689750954697e20)["N"] == 10
    assert np.sum(sample(60)) == pytest.approx(60)
    assert quad(lambda v: np.exp(s.planck_logpdf(np.array([v]), 4.3, 0.19))[0], 0, 20)[
        0
    ] == pytest.approx(1)
    assert s.wigner_cdf(np.array([0, 10])) == pytest.approx([0, 1])
    a, T, score = s.planck_fit(sample())
    assert a > 0 and T > 0 and np.isfinite(score)
    assert s.composite_scores(sample())["planck"]["parameters"] == 2


def test_refit_actual_size_and_joint_bootstrap():
    x = sample()
    result = calibrate(x, thin=3, block_len=12, replicates=5, seed=2)
    assert result["fit_size"] == result["test_size"] == 80
    assert result["replicate_sizes"] == [80] * 5
    assert (
        result["refits"] == 5
        and result["label"] == "nominal"
        and not result["inferential"]
    )
    joint = joint_exponent(x, thin=3, block_len=12, replicates=5, seed=2, cutoff=0.6)
    assert joint["refits"] == 5 and joint["label"] == "nominal"
    assert joint["difference"] == pytest.approx(
        joint["measured"] - joint["model_implied"]
    )
    assert mc_tail(0, 200)["upper95"] == pytest.approx(0.014867, abs=1e-6)


def test_size_check_cannot_certify_small_defaults():
    result = size_check(
        n=120, cue_n=6, thin=3, block_len=12, replicates=3, trials=3, seed=5, alpha=0.01
    )
    assert result["label"] == "nominal" and not result["validated"]
    assert result["required_trials"] == 2000
    assert result["sample_size"] == 120


def test_invalid_numerics_and_mc_endpoints():
    from mve.observer.checks.calibration import rule_fires

    for x in [[], [0, 1], [1, np.nan], [[1, 2]]]:
        with pytest.raises(ValueError):
            s.positive_sample(x)
    for h, lam in [(1, 1), (10, 0), (float("nan"), 1)]:
        with pytest.raises(ValueError):
            s.n_eff(h, lam)
    for n, count in [(1, 2), (2, 0)]:
        with pytest.raises(ValueError):
            s.cue_gaps(n, count, np.random.default_rng(1))
    with pytest.raises(ValueError):
        s.planck_logpdf(np.array([1]), 0, 1)
    with pytest.raises(ValueError):
        s.planck_fit(np.array([0, 1]))
    with pytest.raises(ValueError):
        s.planck_fit(np.array([1, 2]), start=(-1, -1))
    with pytest.raises(ValueError):
        mc_tail(1, 0)
    assert mc_tail(3, 3)["upper95"] == 1
    for kwargs in [dict(thin=0), dict(block_len=500), dict(thin=500)]:
        with pytest.raises(ValueError):
            calibrate(sample(), **kwargs)
    with pytest.raises(ValueError):
        joint_exponent(sample(), alpha=0)
    with pytest.raises(ValueError):
        size_check(n=12, trials=0)
    with pytest.raises(ValueError):
        size_check(
            n=12,
            rule=dict(
                method="primary",
                overall_alpha=0.02,
                components=[dict(statistic="ks", alpha=0.02)],
            ),
        )
    rule = dict(
        method="bonferroni",
        overall_alpha=0.01,
        components=[
            dict(statistic="ks", alpha=0.005),
            dict(statistic="exponent_difference", alpha=0.005),
        ],
    )
    assert rule_fires({"upper95": 0.001}, {"alpha": 0.005, "ci": None}, rule)
    assert rule_fires({"upper95": 0.1}, {"alpha": 0.005, "ci": [-2, -1]}, rule)
    assert not rule_fires({"upper95": 0.1}, {"alpha": 0.005, "ci": [-2, 1]}, rule)
    with pytest.raises(ValueError):
        rule_fires({"upper95": 0.1}, {"alpha": 0.05, "ci": [-2, 1]}, rule)
    empty = joint_exponent(np.ones(30), block_len=3, replicates=2, cutoff=0.3)
    assert empty["ci"] is None and not empty["complete"]


def test_historical_secondary_numerics():
    x = sample(360)
    ci, se = s.exp_block_ci(x, 0.6, 12, 5, np.random.default_rng(0))
    assert ci[0] < ci[1] and se > 0
    assert set(s.acf(x)) == {"1", "2", "3"}
    assert np.isfinite(s.gaudin_logpdf(np.array([0.3, 1]))).all()
    assert s.ecdf_fn([1, 2, 3])(2) == pytest.approx(2 / 3)


def test_planck_cdf_rejects_unresolved_scale():
    with pytest.raises(ValueError, match="normaliser"):
        s.planck_cdf_table(4, 50)
    with pytest.raises(ValueError, match="interval"):
        joint_exponent(sample(), cutoff=1e-5)


def test_gaudin_card_has_zero_fit_parameters_and_joint_structural_check():
    result = calibrate(sample(), model="gaudin", thin=3, block_len=12, replicates=3)
    assert result["refits"] == 0 and result["model"] == "gaudin"
    joint = joint_exponent(sample(), model="gaudin", cutoff=0.6, replicates=3)
    assert joint["model_asymptotic_exponent"] == 3 and joint["refits"] == 0
    with pytest.raises(ValueError):
        calibrate(sample(), model="unsupported")


@pytest.mark.slow
@pytest.mark.skipif(
    __import__("os").environ.get("MVE_RUN_SIZE_CHECK") != "1",
    reason="full nested size calibration is explicitly opt-in",
)
def test_full_dependent_null_size_check():
    result = size_check(
        n=120,
        cue_n=6,
        thin=3,
        block_len=12,
        replicates=4000,
        joint_replicates=4000,
        trials=2000,
        seed=20260928,
        alpha=0.01,
    )
    assert result["trials"] >= result["required_trials"]
    assert result["label"] == (
        "validated_conditional" if result["validated"] else "nominal"
    )
    if result["validated"]:
        assert result["upper95"] <= 0.01


def test_negative_component_alpha_never_certifies():
    from mve.errors import RecordError

    with pytest.raises(RecordError, match="component alpha"):
        size_check(
            n=12,
            rule=dict(
                method="primary",
                overall_alpha=0.01,
                components=[dict(statistic="ks", alpha=-0.01)],
            ),
        )
