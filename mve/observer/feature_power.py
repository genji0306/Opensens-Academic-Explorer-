"""Deterministic native-null calibration and explicit effect sensitivity, WO-6c."""

import json
from pathlib import Path
import numpy as np
from scipy.stats import ks_2samp
from mve.observer import development_c as dev, features as f, native_nulls as native
from mve.observer.card import digest
from mve.observer.power import bounds

OUTPUT = Path(__file__).with_name("config") / "wo6c_power.json"


def sample(module, n, seed):
    if (
        module not in dev.MODULES
        or not dev.STUDY_START <= seed < dev.STUDY_STOP
        or seed in dev.PROSPECTIVE_SEEDS
    ):
        raise ValueError("unregistered study draw")
    # Conditional fixed-n spatial native draws: rejection on total count only,
    # never on a feature. Seed drives one uninterrupted Mulberry stream.
    if module in dev.ZERO:
        chunks = []
        have = 0
        while have < n:
            draw = dev.null_data(module, seed + 1000 * len(chunks))
            x = f.coordinates(module, draw)[0][:, 0]
            chunks.append(x)
            have += len(x)
        return np.concatenate(chunks)[:n, None], (0.0, 3.0)
    extent = 30000 if module == "polar-ulam" else 100000
    first = 1 if module == "polar-ulam" else 3
    integers = np.arange(first, extent + 1)
    mask = integers >= 3
    rng = native.Mulberry(seed)
    probability = 1 / np.log(integers[mask])
    for _ in range(4096):
        u = rng.uniform(len(integers))
        values = integers[mask][u[mask] < probability]
        if len(values) == n:
            p, s, _ = f.coordinates(module, dict(values=values, extent=extent))
            return p, s
    raise ValueError("conditional native draw exhausted; no substitute")


def sample_pools(module, sizes, count):
    if module not in dev.MODULES:
        raise ValueError("unknown development module")
    if module in dev.ZERO:
        return {
            n: [
                sample(
                    module,
                    n,
                    dev.STUDY_START + dev.MODULES.index(module) * 20000 + ni * 4000 + i,
                )
                for i in range(count)
            ]
            for ni, n in enumerate(sizes)
        }
    extent = 30000 if module == "polar-ulam" else 100000
    first = 1 if module == "polar-ulam" else 3
    integers = np.arange(first, extent + 1)
    mask = integers >= 3
    candidates = integers[mask]
    probability = 1 / np.log(candidates)
    rng = native.Mulberry(dev.STUDY_START + dev.MODULES.index(module) * 20000)
    pools = {n: [] for n in sizes}
    for _ in range(4096 * count):
        u = rng.uniform(len(integers))
        values = candidates[u[mask] < probability]
        n = len(values)
        if n in pools and len(pools[n]) < count:
            p, s, _ = f.coordinates(module, dict(values=values, extent=extent))
            pools[n].append((p, s))
        if all(len(v) == count for v in pools.values()):
            return pools
    raise ValueError("conditional native pools exhausted")


def rank_p(calibration, value):
    return (1 + sum(x >= value for x in calibration)) / (1 + len(calibration))


def study(*, repeats=32, modules=dev.MODULES):
    if (
        type(repeats) is not int
        or not 20 <= repeats <= 128
        or not modules
        or any(m not in dev.MODULES for m in modules)
    ):
        raise ValueError("bounded development study required")
    register = dev.build_register()
    jobs = dev.jobs(register)
    rows = []
    for module in modules:
        local = [j for j in jobs if j["module"] == module]
        sizes = sorted(
            {
                len(f.coordinates(module, dev.data(j, s))[0])
                for j in local
                for s in ("A", "B")
            }
        )
        pools = sample_pools(module, sizes, 6 * repeats + 1)
        for job in local:
            aa, bb = [f.coordinates(module, dev.data(job, s))[0] for s in ("A", "B")]
            na, nb = len(aa), len(bb)
            support = pools[na][0][1]
            for tag in f.tags(module):
                for mode in ("one", "two"):
                    # one-sample rows for both actual side sizes, deduplicated below.
                    for n in sorted({na, nb}) if mode == "one" else [na]:
                        ca, tests, alts = [], [], []
                        reference = pools[n][-1][0]
                        for i in range(3 * repeats):
                            a = pools[n][2 * i][0]
                            b = pools[nb][2 * i + 1][0]
                            alt = f.alternative(a, tag, support)
                            if mode == "two":
                                val = f.two(a, b, tag, support)[0]
                                av = f.two(alt, b, tag, support)[0]
                            elif tag == "spacing_ks":
                                val = float(
                                    ks_2samp(
                                        a[:, 0], reference[:, 0], method="asymp"
                                    ).statistic
                                )
                                av = float(
                                    ks_2samp(
                                        alt[:, 0], reference[:, 0], method="asymp"
                                    ).statistic
                                )
                            else:
                                val = f.value(a, tag, support)
                                av = f.value(alt, tag, support)
                            if i < 2 * repeats:
                                ca.append(val)
                            else:
                                tests.append(val)
                                alts.append(av)
                        hits = sum(rank_p(ca, x) <= f.ALPHA for x in alts)
                        row = dict(
                            module=module,
                            tag=tag,
                            sample=mode,
                            n_a=n,
                            n_b=nb if mode == "two" else None,
                            calibration=ca,
                            power=hits / repeats,
                            power_interval95=bounds(hits, repeats),
                            size=sum(rank_p(ca, x) <= f.ALPHA for x in tests) / repeats,
                            alternative="fixed numeric effect: " + tag,
                        )
                        if mode == "one" and tag == "spacing_ks":
                            row["reference"] = reference[:, 0].tolist()
                        if not any(
                            all(
                                r[k] == row[k]
                                for k in ("module", "tag", "sample", "n_a", "n_b")
                            )
                            for r in rows
                        ):
                            rows.append(row)
    result = dict(
        schema="mve-wo6c-power-v1",
        seed=dev.STUDY_START,
        repeats=repeats,
        calibration_draws=2 * repeats,
        alpha=f.ALPHA,
        rows=rows,
        development_sha256=register["sha256"],
        limitations=[
            "Power is for pinned effects only, not all claims or real/null separability.",
            "Spatial native Bernoulli draws condition on exact n by count-only rejection; histogram native batches concatenate within-segment gaps.",
            "Empirical size is descriptive, not guaranteed conditional size; no multiplicity adjustment or GO gate.",
            "Coordinates derive from exported indices and the pinned renderer camera, never pixels.",
        ],
    )
    return {**result, "sha256": digest(result)}


def load():
    r = json.loads(OUTPUT.read_text())
    if r["sha256"] != digest({k: v for k, v in r.items() if k != "sha256"}):
        raise ValueError("power digest mismatch")
    return r


def check(module, tag, data, a, b=None, study_result=None):
    if tag not in f.tags(module):
        return dict(status="unavailable", inferential=False)
    pa, support, field = f.coordinates(module, a)
    if data != field:
        return dict(status="unavailable", inferential=False)
    pb = None if b is None else f.coordinates(module, b)[0]
    mode = "one" if b is None else "two"
    study_result = load() if study_result is None else study_result
    matches = [
        r
        for r in study_result["rows"]
        if (r["module"], r["tag"], r["sample"], r["n_a"], r["n_b"])
        == (module, tag, mode, len(pa), None if pb is None else len(pb))
    ]
    if len(matches) != 1:
        return dict(status="unavailable", inferential=False)
    row = matches[0]
    if pb is not None:
        value, side = f.two(pa, pb, tag, support)
    else:
        value = (
            float(ks_2samp(pa[:, 0], row["reference"], method="asymp").statistic)
            if tag == "spacing_ks"
            else f.value(pa, tag, support)
        )
        side = None
    p = rank_p(row["calibration"], value)
    return dict(
        status="checked",
        inferential=False,
        value=value,
        side=side,
        p_value=p,
        alpha=f.ALPHA,
        detected=p <= f.ALPHA,
        power=row["power"],
        power_study_sha256=study_result["sha256"],
        n_a=len(pa),
        n_b=None if pb is None else len(pb),
        tag=tag,
        data=data,
        data_sha256=digest([a, b]),
        sample=mode,
    )
