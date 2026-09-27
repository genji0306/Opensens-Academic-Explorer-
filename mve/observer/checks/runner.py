"""Two-stage frozen checks. Loaders run only after specification/partition checks.

The size check currently validates an already-unfolded CUE-copula Planck null.
Zeta and other dependence laws remain nominal until separately validated.
"""

import hashlib
import math
from pathlib import Path
import platform
import time
import numpy as np
import scipy
import mpmath
from mve.errors import RecordError
from mve.validation import require
from mve.observer.card import digest, spec_hash
from . import spacing as s
from .calibration import (
    calibrate,
    joint_exponent,
    rule_fires,
    procedure,
    mc_tail,
    fitted_ks,
)


def unfold(values, method, *, base=0):
    x = np.asarray(values, dtype=float)
    if method == "already_unfolded":
        return s.positive_sample(x)
    require(
        x.ndim == 1
        and len(x) >= 3
        and np.all(np.isfinite(x))
        and np.all(np.diff(x) > 0),
        "ordered finite zero sequence required",
    )
    if method == "smooth_count":
        require(np.all(x > 0) and base == 0, "positive low zero ordinates required")
        u = (
            x / (2 * np.pi) * np.log(x / (2 * np.pi * np.e))
            + 7 / 8
            + 1 / (48 * np.pi * x)
        )
        gaps = np.diff(u)
    elif method == "local_density_offsets":
        require(base > 2 * np.pi, "high-zero base required; retain offsets separately")
        density = np.log((float(base) + (x[1:] + x[:-1]) / 2) / (2 * np.pi)) / (
            2 * np.pi
        )
        gaps = np.diff(x) * density
    else:
        raise RecordError("unknown unfolding method")
    return s.positive_sample(gaps)


def verify_calibration(validation, spec, n, null_id):
    """Fail closed on stale settings, sample sizes, null family, or insufficient tails."""
    if not validation or not validation.get("validated"):
        return False
    cal, dep = spec["calibration"], spec["dependence"]
    config = procedure(
        n,
        dep["thin"],
        dep["block_len"],
        cal["replicates"],
        spec["fitting_interval"][1],
        cal["joint_replicates"],
        spec["alpha"],
    )
    alpha_min = min(c["alpha"] for c in spec["kill_rule"]["components"])
    return (
        spec["unfolding"] == "already_unfolded"
        and spec["model"] == "planck"
        and validation.get("null") == null_id == "CUE_copula_Planck_marginal"
        and validation.get("procedure") == config
        and validation.get("procedure_sha256") == digest(config)
        and validation.get("kill_rule") == spec["kill_rule"]
        and validation.get("trials", 0) >= math.ceil(20 / spec["alpha"])
        and validation.get("upper95", 1) <= spec["alpha"]
        and cal["replicates"] >= math.ceil(20 / alpha_min)
        and cal["joint_replicates"] >= math.ceil(20 / alpha_min)
    )


def baseline_comparison(x, height, spec):
    """Same KS statistic and thinning on actual-size CUE surrogate sequences.

    These diagnostics are nominal: CUE simulations do not establish the zeta
    dependence law. Wigner is a secondary descriptive reference only.
    """
    dep, cal = spec["dependence"], spec["calibration"]
    th = dep["thin"]
    st = np.sort(x[::th])
    n = len(st)
    info = s.effective_cue(height, spec["lambda_bogomolny"])
    rng = np.random.default_rng(spec["seed"] + 2)
    reference = s.cue_gaps(info["N"], max(2000, len(x) * 2), rng)
    cue_cdf = s.ecdf_fn(reference)
    out = {}
    primary_observed = fitted_ks(x[::th], spec["model"])[0]
    for name, N, cdf in [("gaudin", 50, s.gaudin_cdf), ("cue", info["N"], cue_cdf)]:
        observed = s.ks_d(st, cdf(st))
        null = []
        primary_null = []
        for _ in range(cal["replicates"]):
            xb = np.sort(s.cue_gaps(N, len(x), rng)[::th])
            null.append(s.ks_d(xb, cdf(xb)))
            primary_null.append(fitted_ks(xb, spec["model"])[0])
        out[name] = dict(
            label="nominal",
            inferential=False,
            statistic=observed,
            fit_size=n,
            test_size=n,
            simulation_size=len(x),
            **mc_tail(sum(v >= observed for v in null), len(null)),
            fitted_primary=dict(
                label="nominal",
                statistic=primary_observed,
                refits=len(primary_null) if spec["model"] == "planck" else 0,
                **mc_tail(
                    sum(v >= primary_observed for v in primary_null), len(primary_null)
                ),
            ),
        )
    out["effective_cue"] = info
    out["wigner_secondary"] = dict(
        label="nominal", statistic=s.ks_d(st, s.wigner_cdf(st))
    )
    return out


def run_stage(card, stage, loader, *, validation=None, null_id=None):
    """loader(block) -> {sha256, values, base?, height}; hash must describe raw bytes.

    No loader is called before the card is frozen. The stage receipt pins all
    source hashes and the card identity. Runtime/versions describe this execution.
    """
    start = time.monotonic()
    d = card.to_dict()
    spec = d["check_spec"]
    require(stage in (1, 2), "stage must be 1 or 2")
    require(
        d["status"] in (("frozen",) if stage == 1 else ("preliminary",)),
        "freeze before reading data",
    )
    require(spec["spec_sha256"] == spec_hash(spec), "changed frozen spec")
    require(
        d["primary_statistic"]
        == {"planck": "fitted_planck_ks", "gaudin": "gaudin_ks"}[spec["model"]],
        "primary statistic does not match model",
    )
    partition = "development" if stage == 1 else "replication"
    rows = []
    for block in spec[partition]:
        raw = loader(block)
        require(raw["sha256"] == block["sha256"], "source data hash mismatch")
        x = unfold(raw["values"], spec["unfolding"], base=raw.get("base", 0))
        kwargs = dict(
            thin=spec["dependence"]["thin"],
            block_len=spec["dependence"]["block_len"],
            model=spec["model"],
        )
        if len(x) < block["min_gaps"]:
            rows.append(
                dict(
                    source_block_id=block["source_block_id"],
                    data_sha256=block["sha256"],
                    actual_gaps=len(x),
                    required_gaps=block["min_gaps"],
                    status="inconclusive",
                    inferential=False,
                    label="nominal",
                )
            )
            continue
        ks = calibrate(
            x, **kwargs, replicates=spec["calibration"]["replicates"], seed=spec["seed"]
        )
        exponent_alpha = next(
            (
                c["alpha"]
                for c in spec["kill_rule"]["components"]
                if c["statistic"] == "exponent_difference"
            ),
            spec["alpha"],
        )
        joint = joint_exponent(
            x,
            **kwargs,
            replicates=spec["calibration"]["joint_replicates"],
            seed=spec["seed"] + 1,
            cutoff=spec["fitting_interval"][1],
            alpha=exponent_alpha,
        )
        valid = (
            verify_calibration(validation, spec, len(x), null_id) and joint["complete"]
        )
        if valid:
            ks.update(label="validated_conditional", inferential=True)
            joint.update(label="validated_conditional", inferential=True)
        fired = rule_fires(ks, joint, spec["kill_rule"])
        rows.append(
            dict(
                source_block_id=block["source_block_id"],
                data_sha256=block["sha256"],
                actual_gaps=len(x),
                required_gaps=block["min_gaps"],
                ks=ks,
                exponent=joint,
                baselines=baseline_comparison(x, raw["height"], spec),
                scores=s.composite_scores(x[:: kwargs["thin"]]),
                nominal_kill=fired,
                label="validated_conditional" if valid else "nominal",
                inferential=valid,
                status="killed" if valid and fired else "inconclusive",
            )
        )
    return dict(
        schema="mve-spacing-receipt-v1",
        stage=stage,
        card_id=d["card_id"],
        revision=d["revision"],
        content_hash=d["content_hash"],
        spec_sha256=spec["spec_sha256"],
        status="preliminary" if stage == 1 else "inconclusive",
        inferential=False,
        label="nominal",
        blocks=rows,
        seed=spec["seed"],
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        implementation_sha256={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob("*.py")
        },
        runtime_s=time.monotonic() - start,
        env=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            scipy=scipy.__version__,
            mpmath=mpmath.__version__,
        ),
    )


def combine_stages(card, first, second):
    """A stage alone never yields a verdict; nominal evidence never kills/survives.

    Specificity is deliberately undecided while baseline calibration is nominal,
    so this library cannot manufacture a baseline-exceeding survivor.
    """
    d = card.to_dict()
    for receipt, stage, partition in [
        (first, 1, "development"),
        (second, 2, "replication"),
    ]:
        require(
            receipt["stage"] == stage
            and all(receipt[k] == d[k] for k in ("card_id", "revision", "content_hash"))
            and receipt["spec_sha256"] == d["check_spec"]["spec_sha256"],
            "stale or wrong-stage receipt",
        )
        expected = d["check_spec"][partition]
        require(
            [(r["source_block_id"], r["data_sha256"]) for r in receipt["blocks"]]
            == [(b["source_block_id"], b["sha256"]) for b in expected],
            "receipt partition mismatch",
        )
    all_rows = first["blocks"] + second["blocks"]
    inference = not d["context"]["retrospective"] and all(
        r["inferential"] and r["actual_gaps"] >= r["required_gaps"] for r in all_rows
    )
    killed = inference and all(r["status"] == "killed" for r in all_rows)
    return dict(
        status="killed" if killed else "inconclusive",
        inferential=bool(inference),
        label="validated_conditional" if inference else "nominal",
        spec_sha256=d["check_spec"]["spec_sha256"],
        card_id=d["card_id"],
        revision=d["revision"],
        content_hash=d["content_hash"],
        stages=[first, second],
        limitation="baseline specificity unvalidated; no survival certification",
    )
