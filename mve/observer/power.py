"""Bounded offline power of the only two WO-6b mapped diagnostics.

Each ordered pair calibrates the scalar KS distance under its named null using
independent simulations, then measures two-sided tail rejection under the other
population. This measures distinguishability, not survival or GO2 power. Finite
GUE(64) is an explicitly finite bulk approximation to the Gaudin limit.
"""

import argparse
import json
import math
from pathlib import Path
import numpy as np
from mve.observer import native_nulls as native, pilot_inputs as inputs
from mve.observer.checks import spacing
from mve.observer.card import digest

SEED = 2026092806
REPEATS = 128
GRID = (16, 32, 64, 128, 256, 512, 1024)
OUTPUT = Path(__file__).with_name("config") / "wo6b_power.json"
STATISTICS = ("gaudin_ks", "poisson_ks")


def diagnostic(x, statistic):
    x = np.sort(spacing.positive_sample(x) / np.mean(x))
    cdf = spacing.gaudin_cdf(x) if statistic == "gaudin_ks" else -np.expm1(-x)
    return spacing.ks_d(x, cdf)


def snapshot_ns():
    result = {m: {} for m in inputs.MODULES}
    for e in inputs.manifest()["snapshots"]:
        d = json.loads((inputs.INPUTS / e["data_ref"]["path"]).read_text())
        result[e["module"]][
            "real" if e["control"]["kind"] == "none" else "null_twin"
        ] = len(native.gaps(e["module"], d["values"]))
    return result


def bounds(k, n):
    # Wilson 95%, descriptive Monte Carlo uncertainty (not scientific inference).
    p, z = k / n, 1.959963984540054
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(center - radius, 6), round(center + radius, 6)]


def study(*, ns=None, repeats=REPEATS, seed=SEED, modules=inputs.MODULES):
    if type(repeats) is not int or not 20 <= repeats <= 256:
        raise ValueError("bounded repeats 20..256 required")
    if ns is not None and (
        not ns or any(type(n) is not int or not 4 <= n <= 10000 for n in ns)
    ):
        raise ValueError("bounded n grid 4..10000 required")
    if not modules or any(m not in inputs.MODULES for m in modules):
        raise ValueError("unknown module")
    sizes = snapshot_ns()
    rows = []
    for mi, module in enumerate(modules):
        grid = sorted(set(ns if ns is not None else [*GRID, *sizes[module].values()]))
        rng = np.random.default_rng(
            np.random.SeedSequence([seed, inputs.MODULES.index(module)])
        )
        scores = {
            pop: {n: {stat: [] for stat in STATISTICS} for n in grid}
            for pop in ("GUE", "Poisson", "native")
        }
        for pop in scores:
            for _ in range(3 * repeats):
                x = (
                    native.sample_gue(max(grid), rng)
                    if pop == "GUE"
                    else rng.exponential(size=max(grid))
                    if pop == "Poisson"
                    else native.sample_native(module, max(grid), rng)
                )
                for n in grid:
                    for stat in STATISTICS:
                        scores[pop][n][stat].append(diagnostic(x[:n], stat))
        for n in grid:
            for stat in STATISTICS:
                for null in scores:
                    calibration = np.sort(scores[null][n][stat][: 2 * repeats])
                    # Exchangeable rank test, finite Monte Carlo alpha <= .05.
                    tail = math.floor(0.025 * (len(calibration) + 1))
                    lo = calibration[tail - 1] if tail else -math.inf
                    hi = calibration[-tail] if tail else math.inf
                    upper_tail = math.floor(0.05 * (len(calibration) + 1))
                    upper95 = calibration[-upper_tail]
                    for alternative in scores:
                        if alternative == null:
                            continue
                        test = np.asarray(scores[alternative][n][stat][2 * repeats :])
                        null_test = np.asarray(scores[null][n][stat][2 * repeats :])
                        k = int(np.count_nonzero((test < lo) | (test > hi)))
                        upper_k = int(np.count_nonzero(test > upper95))
                        rows.append(
                            dict(
                                module=module,
                                statistic=stat,
                                n=n,
                                null=null,
                                alternative=alternative,
                                power=k / repeats,
                                power_interval95=bounds(k, repeats),
                                detected=k,
                                upper_power=upper_k / repeats,
                                upper_power_interval95=bounds(upper_k, repeats),
                                upper_detected=upper_k,
                                upper_critical95=float(upper95),
                                upper_size=float(np.mean(null_test > upper95)),
                                size=float(
                                    np.mean((null_test < lo) | (null_test > hi))
                                ),
                                lower_critical=None
                                if not math.isfinite(lo)
                                else float(lo),
                                upper_critical=None
                                if not math.isfinite(hi)
                                else float(hi),
                            )
                        )
    minima = []
    for module in modules:
        for stat in STATISTICS:
            for null in ("GUE", "Poisson", "native"):
                for alt in ("GUE", "Poisson", "native"):
                    if null != alt:
                        selected = [
                            r
                            for r in rows
                            if (
                                r["module"],
                                r["statistic"],
                                r["null"],
                                r["alternative"],
                            )
                            == (module, stat, null, alt)
                            and r["power"] >= 0.8
                        ]
                        upper_selected = [
                            r["n"]
                            for r in rows
                            if (
                                r["module"],
                                r["statistic"],
                                r["null"],
                                r["alternative"],
                            )
                            == (module, stat, null, alt)
                            and r["upper_power"] >= 0.8
                        ]
                        minima.append(
                            dict(
                                module=module,
                                statistic=stat,
                                null=null,
                                alternative=alt,
                                minimum_upper_grid_n=min(upper_selected)
                                if upper_selected
                                else None,
                                minimum_grid_n=min(r["n"] for r in selected)
                                if selected
                                else None,
                            )
                        )
    result = dict(
        schema="mve-wo6b-power-v1",
        seed=seed,
        alpha=0.05,
        repeats=repeats,
        calibration_draws=2 * repeats,
        stage1_rule="Upper empirical rank tail at alpha .05, matching direction=greater. Stage-1 gate uses upper_power; power is supplemental two-sided distinguishability.",
        snapshot_n=sizes,
        rows=rows,
        minima=minima,
        statistics=list(STATISTICS),
        method="Independent calibration/test draws; two-sided empirical rank tails of each scalar KS; alpha <= .05 by ranks under the simulated null. No iid KS critical line.",
        limitations=[
            "Descriptive simulation power; finite GUE(64), not a proof of infinite Gaudin accuracy.",
            "Small n uses prefixes; large n concatenates independent native batches with no cross-segment gaps. Native generator parameters stay fixed.",
            "Cramer index gaps are locally unfolded; no mapping from pixel nearest neighbors or prime sphere geometry.",
            "minimum_grid_n means first tested n, not a continuous minimum; null means not reached on the tested grid.",
            "Pair correlation is not implemented in the WO-3 Python card check mapping; no proxy power is claimed.",
            "All stage-1 results stay preliminary, including powered diagnostics. No replication or GO2 decision.",
        ],
    )
    return {**result, "sha256": digest(result)}


def load():
    value = json.loads(OUTPUT.read_text())
    if value["sha256"] != digest({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("power pin mismatch")
    return value


def check(proposal, job, study_result=None):
    form = proposal["testable_form"]
    expected_data = (
        "source_gaps"
        if job["module"] in ("spectral", "field-dyson")
        else "source_index_gaps"
    )
    statistic = form["statistic"]
    baseline = {"gaudin_ks": "Gaudin GUE", "poisson_ks": "Poisson"}.get(statistic)
    if (
        not baseline
        or form["baseline"] != baseline
        or form["data"] != expected_data
        or form["direction"] != "greater"
    ):
        return dict(
            status="unavailable",
            inferential=False,
            reason="No exact statistic/data/baseline/direction mapping.",
        )
    x, sha = native.data(job)
    result = load() if study_result is None else study_result
    null = "GUE" if statistic == "gaudin_ks" else "Poisson"
    rows = [
        r
        for r in result["rows"]
        if r["module"] == job["module"]
        and r["statistic"] == statistic
        and r["n"] == len(x)
        and r["null"] == null
    ]
    power = min((r["upper_power"] for r in rows), default=0)
    complete = {r["alternative"] for r in rows} == (
        {"GUE", "Poisson", "native"} - {null}
    )
    powered = complete and power >= 0.8
    return dict(
        status="stage1_only" if powered else "underpowered",
        label="descriptive",
        inferential=False,
        statistic=statistic,
        value=diagnostic(x, statistic),
        n=len(x),
        data_sha256=sha,
        power=power,
        power_study_sha256=result["sha256"],
        power_complete=complete,
        alternatives=rows,
        lifecycle="preliminary",
        reason="Minimum upper-tail power across both pinned alternatives at alpha .05; no replication or survival inference.",
    )


# WO-6c is isolated from prospective_study: only WO-1 development data and
# registered new native draws are consumed here.
def comparative_study(*, repeats=32, modules=inputs.MODULES):
    from mve.observer import feature_power as fp

    return fp.study(repeats=repeats, modules=modules)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--prospective", action="store_true")
    parser.add_argument("--comparative", action="store_true")
    args = parser.parse_args(argv)
    if (args.prospective or args.comparative) and args.output == OUTPUT:
        parser.error("prospective study requires an explicit output path")
    if args.prospective and args.comparative:
        parser.error("choose one study")
    result = (
        comparative_study()
        if args.comparative
        else prospective_study()
        if args.prospective
        else study()
    )
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {"rows": len(result["rows"]), "seed": result["seed"], "hosted_calls": 0}
        )
    )


def prospective_study(*, repeats=128, sizes=(1024, 2048)):
    """WO-1b upper-tail sensitivity at exact block n, independent calibration.

    Empirical size is reported, not claimed to be a guaranteed conditional alpha.
    Prime contrasts target index-spacing repulsion, never spatial point distance.
    """
    from mve.observer.snapshot_blocks import sample

    if (
        repeats < 20
        or repeats > 256
        or len(sizes) != 2
        or any(n < 4 or n > 4096 for n in sizes)
    ):
        raise ValueError("bounded prospective study required")
    rows = []
    seed = 2026092816
    for mi, module in enumerate(inputs.MODULES):
        zero = module in ("spectral", "field-dyson")
        n = sizes[0 if zero else 1]
        populations = (
            ("GUE", "Poisson", "GOE") if zero else ("GUE", "Cramer", "shuffled-index")
        )
        scores = {}
        for pi, population in enumerate(populations):
            values = []
            for draw in range(3 * repeats):
                draw_seed = int(
                    np.random.SeedSequence([seed, mi, pi, draw]).generate_state(1)[0]
                )
                x = sample(population, module, n, draw_seed)
                if population in ("Cramer", "shuffled-index"):
                    x = np.diff(x) / np.log((x[:-1] + x[1:]) / 2)
                values.append(diagnostic(x, "gaudin_ks"))
            scores[population] = np.array(values)
        calibration = np.sort(scores["GUE"][: 2 * repeats])
        critical = float(calibration[-math.floor(0.05 * (2 * repeats + 1))])
        for population in populations[1:]:
            k = int(np.count_nonzero(scores[population][2 * repeats :] > critical))
            rows.append(
                dict(
                    module=module,
                    n=n,
                    statistic="gaudin_ks",
                    null="GUE",
                    alternative=population,
                    upper_power=k / repeats,
                    power_interval95=bounds(k, repeats),
                    upper_critical95=critical,
                    upper_size=float(np.mean(scores["GUE"][2 * repeats :] > critical)),
                )
            )
    result = dict(
        schema="mve-wo1b-power-v1",
        seed=seed,
        repeats=repeats,
        calibration_draws=2 * repeats,
        alpha=0.05,
        rows=rows,
        rule="gaudin_ks > upper_critical95; stage-1 sensitivity only",
        limitations="Finite beta ensembles; empirical size and power, not GO2 power or inferential survival.",
    )
    return {**result, "sha256": digest(result)}


def prospective_check(block, numeric, study_result):
    """Frozen contrast sensitivity check; never declares inferential survival."""
    from mve.observer.snapshot_inventory import power_row

    row = power_row(block, study_result)
    x = spacing.positive_sample(numeric["source_gaps"])
    if len(x) != block["n"]:
        raise ValueError("contrast sample count mismatch")
    value = diagnostic(x, row["statistic"])
    return dict(
        statistic=row["statistic"],
        n=len(x),
        value=value,
        detected=value > row["upper_critical95"],
        threshold=row["upper_critical95"],
        power=row["upper_power"],
        inferential=False,
        status="stage1_sensitivity_only",
    )


if __name__ == "__main__":
    main()
