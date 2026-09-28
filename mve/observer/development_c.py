"""WO-6c development allowlist. Never opens the prospective inventory or cache."""

import hashlib
import json
from pathlib import Path
import random
from mve.observer import pilot_inputs as inputs, native_nulls as native
from mve.observer.card import digest

ROOT = Path(__file__).resolve().parents[2]
MODULES = inputs.MODULES
ZERO = ("spectral", "field-dyson")
REGISTER = Path("mve/observer/config/wo6c_development.json")
# Conservative envelopes from WO-1b's source/review, not materialized blocks.
PROSPECTIVE_SEEDS = frozenset(range(28000000, 28000140)) | {2026092816, 2026092817}
PROSPECTIVE_INTEGER_INTERVAL = (200001, 2840001)
PROSPECTIVE_ZERO_INTERVALS = (
    (2001, 10201),
    (10**12 + 1, 10**12 + 8201),
    (10**21 + 1, 10**21 + 7176),
    (10**22 + 1, 10**22 + 7176),
)
ORDER_SEED = 63001000
STUDY_START, STUDY_STOP = 63100000, 63200000

ORIGINAL_IDS = {
    "spectral": ("e7e62f118767a71e4f9f5667", "ad3e2d070bf2281c2f4e5776"),
    "field-dyson": ("72a4faadef98a29892dbaabf", "4fa1ba104ef92cc9974a34d0"),
    "polar-ulam": ("26273407940f612fa020ca13", "f3252b4209f5b923c2742faf"),
    "space-08": ("c850cba22bfce83c435c9b3b", "f65fc613988149f3756457a3"),
}


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def original(module, kind):
    if module not in MODULES or kind not in ("real", "null"):
        raise ValueError("development source required")
    e = next(
        e
        for e in inputs.manifest()["snapshots"]
        if e["module"] == module
        and (e["control"]["kind"] == "none") == (kind == "real")
    )
    if e["data_ref"]["role"] != "development" or e["go2_eligible"]:
        raise ValueError("development role required")
    ident = ORIGINAL_IDS[module][kind == "null"]
    if e["snapshot_id"] != ident or e["data_ref"]["path"] != ident + "/data.json":
        raise ValueError("source outside the eight development snapshots")
    raw = (inputs.INPUTS / ident / "data.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != e["data_ref"]["sha256"]:
        raise ValueError("development digest mismatch")
    return json.loads(raw)


def null_data(module, seed):
    if module not in MODULES or not (
        63000000 <= seed < 63000008 or STUDY_START <= seed < STUDY_STOP
    ):
        raise ValueError("unregistered development draw")
    d = dict(
        values=native.snapshot(module, seed).tolist(),
        seed=seed,
        source="development-native-null",
    )
    if module not in ZERO:
        d["extent"] = 30000 if module == "polar-ulam" else 100000
    return d


def build_register():
    nulls = []
    for mi, m in enumerate(MODULES):
        for i in range(2):
            seed = 63000000 + 2 * mi + i
            nulls.append(
                dict(
                    id=f"{m}-null-{i}",
                    module=m,
                    seed=seed,
                    role="development",
                    interval=[1, 30001 if m == "polar-ulam" else 100001]
                    if m not in ZERO
                    else None,
                    population="integer-index" if m not in ZERO else "simulation",
                    data_sha256=hashlib.sha256(encoded(null_data(m, seed))).hexdigest(),
                )
            )
    r = dict(
        schema="mve-wo6c-development-v1",
        original_snapshots=[e["snapshot_id"] for e in inputs.manifest()["snapshots"]],
        nulls=nulls,
        order_seed=ORDER_SEED,
        study_seeds=[STUDY_START, STUDY_STOP],
        purpose="development only; excluded from GO2",
        prospective_access=False,
    )
    return {**r, "sha256": digest(r)}


def validate_register(r):
    seeds = [n["seed"] for n in r["nulls"]] + [r["order_seed"]]
    if len(seeds) != len(set(seeds)) or set(seeds) & PROSPECTIVE_SEEDS:
        raise ValueError("development seed collision")
    if set(range(*r["study_seeds"])) & (PROSPECTIVE_SEEDS | set(seeds)):
        raise ValueError("study seed collision")
    for n in r["nulls"]:
        if n["interval"] is not None:
            a, b = n["interval"]
            c, d = PROSPECTIVE_INTEGER_INTERVAL
            if max(a, c) < min(b, d):
                raise ValueError("development interval collision")
    if any(max(1, a) < min(1001, b) for a, b in PROSPECTIVE_ZERO_INTERVALS):
        raise ValueError("development zero collision")
    if r != build_register():
        raise ValueError("development register drift")
    return r


def load():
    return validate_register(json.loads((ROOT / REGISTER).read_text()))


def jobs(register):
    validate_register(register)
    rng = random.Random(ORDER_SEED)
    jobs = []
    for module in MODULES:
        for kind, sources in [
            ("real-null", ["real", "null"]),
            ("null-null", ["new-0", "new-1"]),
        ]:
            rng.shuffle(sources)
            jobs.append(
                dict(
                    id=digest([module, kind, ORDER_SEED])[:16],
                    module=module,
                    pair_type=kind,
                    sealed=dict(zip(("A", "B"), sources)),
                )
            )
    return jobs


def data(job, side):
    source = job["sealed"][side]
    if source in ("real", "null"):
        return original(job["module"], source)
    if source not in ("new-0", "new-1"):
        raise ValueError("source outside development")
    return null_data(
        job["module"], 63000000 + 2 * MODULES.index(job["module"]) + int(source[-1])
    )
