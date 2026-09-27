"""Offline v2 reproduction only. Historical nominal p-values are never certified."""

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from . import spacing

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/mve/observer/card001_hawking"


def verified_inputs(cache):
    cache = Path(cache)
    hashes = {}
    for line in (EVIDENCE / "ODLYZKO_SHA256SUMS").read_text().splitlines():
        expected, name = line.split()
        actual = hashlib.sha256((cache / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Odlyzko hash mismatch: {name}")
        hashes[name] = actual
    return hashes


def reproduce(cache):
    """Use shared kernels in the unchanged historical driver, after input verification."""
    hashes = verified_inputs(cache)
    path = EVIDENCE / "lane_check_v2.py"
    spec = importlib.util.spec_from_file_location("mve_historical_v2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.D = str(Path(cache))
    for name in (
        "gaudin_table",
        "wigner_logpdf",
        "wigner_cdf",
        "cue_gaps",
        "logexpm1",
        "planck_logpdf",
        "planck_fit",
        "planck_cdf_table",
        "ks_d",
        "exp_mle",
        "exp_implied_from_cdf",
        "exp_block_ci",
        "acf",
        "ecdf_fn",
    ):
        setattr(module, name, getattr(spacing, name))
    stream = io.StringIO()
    with redirect_stdout(stream):
        module.main()
    receipt = json.loads(stream.getvalue())
    receipt.update(
        inferential=False,
        label="nominal",
        fixture_role="regression_only",
        verified_inputs=hashes,
        shared_kernel_sha256=hashlib.sha256(
            Path(spacing.__file__).read_bytes()
        ).hexdigest(),
    )
    return receipt


def compare(receipt):
    golden = json.loads((EVIDENCE / "lane_check_v2.json").read_text())
    failures = []
    for actual, expected in zip(receipt["blocks"], golden["blocks"], strict=True):
        for key in (
            "block",
            "first_zero_index",
            "zeros",
            "gaps_all",
            "gaps_thinned",
            "height_median",
            "height_range",
            "n_eff",
            "cue_n_used",
        ):
            if actual[key] != expected[key]:
                failures.append(f"{expected['block']}: {key}")
        for key in ("a", "T"):
            if abs(actual["planck"][key] - expected["planck"][key]) > 0.01:
                failures.append(key)
        for a, b in zip(
            [
                actual["cdf_exponent"]["b_hat"],
                *actual["cdf_exponent"]["ci95_block_bootstrap"],
            ],
            [
                expected["cdf_exponent"]["b_hat"],
                *expected["cdf_exponent"]["ci95_block_bootstrap"],
            ],
        ):
            if abs(a - b) > 0.02:
                failures.append("exponent")
        for group, key in [
            ("planck", "ks_p_bootstrap_refit"),
            ("gue_limit_ks", "p_calibrated"),
            ("cue_neff_ks", "p_calibrated"),
        ]:
            # Golden rounds to 4 decimals; with B=200 this uniquely identifies counts.
            if round(actual[group][key] * 201 - 1) != round(
                expected[group][key] * 201 - 1
            ):
                failures.append(group + " exceedances")
    return dict(
        passed=not failures,
        failures=failures,
        blocks=len(receipt["blocks"]),
        inferential=False,
        label="nominal",
    )
