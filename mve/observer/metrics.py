"""Cluster sign flips; slot CP bounds are explicitly nominal/descriptive."""

from collections import Counter
import numpy as np
from scipy.stats import beta
from mve.observer.card import Card, go1, binding
from mve.observer.design import ARMS, require


def interval(successes, trials):
    return {
        "method": "nominal descriptive Clopper-Pearson; clustering invalidates binomial coverage",
        "lower95": float(beta.ppf(0.025, successes, trials - successes + 1))
        if successes
        else 0.0,
        "upper95": float(beta.ppf(0.975, successes + 1, trials - successes))
        if trials > successes
        else 1.0,
    }


def sign_flip(differences, *, seed):
    require(
        all(type(v) is int for v in differences),
        "integer survivor-count differences required (common S cancels)",
    )
    d = np.asarray(differences, dtype=int)
    observed = int(d.sum())
    k = len(d)
    if k <= 20:
        sums = np.array([0], dtype=np.int64)
        for value in d:
            sums = np.concatenate((sums + value, sums - value))
        r = int(np.count_nonzero(sums >= observed))
        return {
            "method": "exact sign-flip",
            "p": r / len(sums),
            "draws": len(sums),
            "exceedances": r,
            "nonzero": int(np.count_nonzero(d)),
        }
    rng = np.random.default_rng(seed)
    r = 0
    for _ in range(100):
        sums = (rng.integers(0, 2, size=(1000, k)) * 2 - 1) @ d
        r += int(np.count_nonzero(sums >= observed))
    return {
        "method": "Monte Carlo sign-flip",
        "p": (1 + r) / 100001,
        "draws": 100000,
        "exceedances": r,
        "upper95": float(beta.ppf(0.95, r + 1, 100000 - r)) if r < 100000 else 1.0,
        "nonzero": int(np.count_nonzero(d)),
    }


def report(plan, rows, observer):
    p = plan.to_dict()
    jobs = {j["id"]: j for j in p["jobs"]}
    expected = {(j["id"], i) for j in p["jobs"] for i in range(j["slots"])}
    require(
        len(rows) == len(expected)
        and {(r["job"], r["slot"]) for r in rows} == expected,
        "slot denominator mismatch",
    )
    counts = Counter()
    replies = {j: [] for j in jobs}
    checkable = []
    for row in rows:
        job = jobs[row["job"]]
        card = row.get("card")
        replies[row["job"]].append(card or {})
        if card:
            d = Card.from_dict(card).to_dict()
            require(
                d["observer"]["id"] == observer or job["arm"] == "image_free",
                "observer mismatch",
            )
            if row["checkable"]:
                checkable.append(tuple(binding(d).values()))
            survival = (
                d["status"] == "checked:baseline_exceeding_survivor"
                and (d["observer"]["blinded"] or job["arm"] == "image_free")
                and not d["context"]["retrospective"]
            )
            counts[job["cluster"], job["arm"]] += int(survival)
    by_origin = {}
    for ident, view in replies.items():
        origin = observer
        if jobs[ident]["arm"] == "image_free":
            origin = p["config"]["checks"][jobs[ident]["family"]]["observer"]["id"]
        by_origin.setdefault(origin, []).append(view)
    origins = go1(by_origin, slots_per_view=3, human_checkable=checkable)
    g1 = {
        k: sum(v[k] for v in origins.values())
        for k in ("requested", "well_formed", "data_checkable")
    }
    g1.update(
        well_formed_rate=g1["well_formed"] / g1["requested"],
        checkable_rate=g1["data_checkable"] / g1["requested"],
    )
    g1["passed"] = g1["well_formed_rate"] >= 0.9 and g1["checkable_rate"] >= 0.5
    g1["origin_breakdown"] = origins
    g1["image_free_origin"] = "frozen library author; shared control, no model call"
    for key in ("well_formed", "data_checkable"):
        g1[key + "_interval"] = interval(g1[key], g1["requested"])
    ordinary = [c for c in p["clusters"] if not c["contrast"]]
    contrasts = [c for c in p["clusters"] if c["contrast"]]
    slots = p["config"]["views"] * 3
    strata = {}
    for st in sorted({c["stratum"] for c in ordinary}):
        subset = [c for c in ordinary if c["stratum"] == st]
        strata[st] = {}
        for arm in ARMS:
            n = len(subset) * slots
            survivors = sum(counts[c["id"], arm] for c in subset)
            strata[st][arm] = {
                "survivors": survivors,
                "slots": n,
                "rate": survivors / n,
                **interval(survivors, n),
            }
    comparisons = {
        arm: sign_flip(
            [counts[c["id"], "real"] - counts[c["id"], arm] for c in ordinary],
            seed=p["config"]["seed"],
        )
        for arm in ARMS[1:]
    }
    for arm, comparison in comparisons.items():
        total = sum(counts[c["id"], "real"] - counts[c["id"], arm] for c in ordinary)
        comparison.update(
            statistic=total / slots,
            mean_lift=total / (slots * len(ordinary)),
            unit="survivors / S",
        )
    pooled = {
        arm: {
            "survivors": sum(counts[c["id"], arm] for c in ordinary),
            "slots": len(ordinary) * slots,
            **interval(
                sum(counts[c["id"], arm] for c in ordinary), len(ordinary) * slots
            ),
        }
        for arm in ARMS
    }
    stratum_tests = {
        st: {
            arm: sign_flip(
                [
                    counts[c["id"], "real"] - counts[c["id"], arm]
                    for c in ordinary
                    if c["stratum"] == st
                ],
                seed=p["config"]["seed"],
            )
            for arm in ARMS[1:]
        }
        for st in strata
    }
    detected = sum(counts[c["id"], "contrast"] > 0 for c in contrasts)
    decidable = len(ordinary) >= 20 and len(strata) >= 2 and not p["config"]["pilot"]
    passed = (
        decidable
        and len(contrasts) == 10
        and detected >= 8
        and all(v["p"] <= 0.05 for v in comparisons.values())
    )
    return {
        "mode": "offline_replay",
        "hosted_calls": 0,
        "observer": observer,
        "design_sha256": p["sha256"],
        "GO1": g1,
        "GO2": {
            "status": "conditional_pass"
            if passed
            else "not_established"
            if decidable
            else "descriptive_only",
            "clusters": len(ordinary),
            "slots_per_cluster_arm": slots,
            "by_stratum": strata,
            "pooled": pooled,
            "comparisons_by_stratum": stratum_tests,
            "comparisons": comparisons,
            "contrast_detected": detected,
            "contrast_clusters": len(contrasts),
            "cluster_outcomes": [
                {
                    **c,
                    "survivors": {
                        a: counts[c["id"], a]
                        for a in (("contrast",) if c["contrast"] else ARMS)
                    },
                }
                for c in p["clusters"]
            ],
            "assumptions": [
                "A1 independent clusters (not proven by disjointness)",
                "A2 within-cluster exchangeability / symmetric differences; random call order does not prove this",
            ],
            "decision_rule": "one-sided alpha .05 for all three comparisons (intersection-union), K>=20, >=2 strata, >=8/10 contrasts",
            "evidence": "synthetic replay is not a scientific GO2 certification",
        },
    }
