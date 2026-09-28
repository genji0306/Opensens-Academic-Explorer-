"""Frozen WO-1b inventory, numeric commitments and held-out access boundaries.

The inventory is an input packet, not an observer result or GO2 certification.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from mve.observer.card import digest
from mve.observer import snapshot_blocks as data
from mve.observer import snapshots as s

MODULES = tuple(s.MODULES)
ZERO = data.ZERO
ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("mve/observer/config/wo1b_manifest.json")
POWER = Path("mve/observer/config/wo1b_power.json")
SEED = 2026092817
SNAPSHOT_CAP = 512 * 1024


def encoded(value):
    def canonical(x):
        if isinstance(x, float) and x.is_integer():
            return int(x)
        if isinstance(x, list):
            return [canonical(v) for v in x]
        if isinstance(x, dict):
            return {k: canonical(v) for k, v in x.items()}
        return x

    value = canonical(value)
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def seal(value):
    body = json.loads(encoded({k: v for k, v in value.items() if k != "sha256"}))
    return {**body, "sha256": digest(body)}


def load_power():
    value = json.loads((ROOT / POWER).read_text())
    if value["sha256"] != digest({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("power digest mismatch")
    return value


def layout():
    blocks, clusters = [], []
    counters = {name: 0 for name in data.HEIGHTS}
    zero_count, prime_count = 0, 0
    rng = random.Random(SEED)

    def block(module, role, partition, generator, cluster):
        nonlocal zero_count, prime_count
        i = len(blocks)
        if generator == "Odlyzko":
            name = tuple(data.HEIGHTS)[zero_count % 4]
            origin, height = data.HEIGHTS[name]
            start = (2000 if name == "zeros1.gz" else 0) + counters[name] * 1025
            source = dict(
                population="zeta-zero-index",
                file=name,
                start=start,
                stop=start + 1025,
                index_start=str(origin + start + 1),
                index_stop_exclusive=str(origin + start + 1026),
                height_offset=height,
            )
            counters[name] += 1
            zero_count += 1
        elif module in ZERO:
            source = dict(population=f"simulation:{i}", start=0, stop=1025)
        else:
            start = 200001 + prime_count * 40000
            source = dict(population="integer-index", start=start, stop=start + 40000)
            prime_count += 1
        ident = f"b{i:03d}"
        blocks.append(
            dict(
                id=ident,
                cluster=cluster,
                module=module,
                stratum=module
                + " × "
                + ("zero spacings" if module in ZERO else "primes"),
                role=role,
                partition=partition,
                generator=generator,
                seed=28000000 + i,
                source=source,
                n=1024 if module in ZERO else 2048,
                crop={
                    "selector": s.MODULES[module]["selector"],
                    "mode": "canvas-only",
                    "resize": [640, 400],
                },
                camera={
                    "views": [
                        {"viewport": [1440, 1100], "camera": "native-static"},
                        {"viewport": [1280, 1000], "camera": "native-static"},
                    ]
                },
                unfolding="local zero intensity then mean-one"
                if module in ZERO
                else "log(midpoint source index) then mean-one",
                null_semantics="GUE positive control"
                if module in ZERO
                else "random-prime baseline",
                check={
                    "statistic": "gaudin_ks",
                    "baseline": "Gaudin GUE",
                    "direction": "greater",
                    "data": "source_gaps" if module in ZERO else "source_index_gaps",
                    "target": {
                        "Poisson": "Exponential spacings lack GUE level repulsion",
                        "GOE": "Beta=1 spacings have weaker repulsion than beta=2 GUE",
                        "Cramer": "Bernoulli prime-index gaps lack GUE repulsion; not a spatial-distance check",
                        "shuffled-index": "Uniform site-membership permutation destroys arithmetic index selection; KS targets index-gap repulsion only",
                    }.get(
                        generator,
                        "GUE departure in declared source gaps; not a survival verdict",
                    ),
                },
                data_sha256=None,
            )
        )
        return ident

    for module in MODULES:
        local = []
        for k in range(5):
            cid = f"{module}-ordinary-{k}"
            assigned = {}
            for role, part in [
                ("D", "D"),
                ("R", "R"),
                ("donor", "D"),
                ("null-D", "D"),
                ("null-R", "R"),
            ]:
                gen = (
                    ("GUE" if module in ZERO else "random-prime")
                    if role.startswith("null")
                    else ("Odlyzko" if module in ZERO else "primes")
                )
                assigned[role] = block(module, role, part, gen, cid)
            c = dict(id=cid, module=module, contrast=False, blocks=assigned)
            clusters.append(c)
            local.append(c)
        donors = [c["blocks"]["donor"] for c in local]
        rng.shuffle(donors)
        for c, donor in zip(local, donors):
            c["blocks"]["donor"] = donor
            next(b for b in blocks if b["id"] == donor)["cluster"] = c["id"]
        generators = {
            "spectral": ["Poisson", "GOE", "Poisson"],
            "field-dyson": ["GOE", "Poisson", "GOE"],
            "polar-ulam": ["Cramer", "shuffled-index"],
            "space-08": ["Cramer", "shuffled-index"],
        }[module]
        for k, gen in enumerate(generators):
            cid = f"{module}-contrast-{k}"
            assigned = {}
            for role, part in [
                ("D", "D"),
                ("R", "R"),
                ("null-D", "D"),
                ("null-R", "R"),
            ]:
                g = (
                    ("GUE" if module in ZERO else "random-prime")
                    if role.startswith("null")
                    else gen
                )
                assigned[role] = block(
                    module, "contrast" if role in ("D", "R") else role, part, g, cid
                )
            clusters.append(dict(id=cid, module=module, contrast=True, blocks=assigned))
    return dict(
        schema="mve-wo1b-inventory-v1",
        seed=SEED,
        blocks=blocks,
        clusters=clusters,
        views=2,
        slots_per_view=3,
        opportunities_per_arm=6,
        retries=2,
        development={
            "excluded": True,
            "snapshots": 8,
            "zero_indices_through": 1000,
            "integer_indices_through": 100000,
        },
        go2={
            "K": 20,
            "contrast_clusters": 10,
            "contrast_required": 8,
            "alpha_per_arm": 0.05,
            "arms": ["null_twin", "image_free", "shuffled"],
            "test": "exact sign-flip sum of cluster differences; 2^20 patterns per arm; intersection-union requires all three",
            "assumptions": [
                "A1 independent clusters",
                "A2 within-cluster symmetric differences",
            ],
            "status": "inventory only; no outcomes; not GO2 power",
            "contrast_detection": "At least one frozen observer slot names the declared source-spacing target and passes its pinned diagnostic on disjoint D and R. Numeric rejection alone is not observer detection.",
        },
        retention={
            "full_page": False,
            "reviewed_full_page_flag": None,
            "passes": 2,
            "snapshot_byte_cap": SNAPSHOT_CAP,
            "generated_byte_cap": 200 * 1024**2,
            "free_floor": 5 * 1024**3,
        },
        sources={
            "commits": s.COMMITS,
            "pathspecs": {k: list(v) for k, v in s.PATHS.items()},
        },
    )


def build(cache=data.CACHE):
    plan = layout()
    plan["cache"] = data.verify_cache(cache)
    plan["power_sha256"] = load_power()["sha256"]
    for b in plan["blocks"]:
        b["data_sha256"] = hashlib.sha256(
            encoded(data.numeric(b, cache, purpose="capture"))
        ).hexdigest()
    return seal(plan)


def power_row(block, study):
    rows = [
        r
        for r in study["rows"]
        if r.get("null") == "GUE"
        and (r["module"], r["n"], r["alternative"])
        == (block["module"], block["n"], block["generator"])
    ]
    if len(rows) != 1 or rows[0]["upper_power"] < 0.8:
        raise ValueError("contrast lacks powered check")
    return rows[0]


def validate(plan):
    if seal(plan) != plan:
        raise ValueError("inventory digest mismatch")
    expected = layout()
    stripped = deepcopy(plan)
    for key in ("sha256", "power_sha256", "cache"):
        stripped.pop(key, None)
    seen = set()
    for b in stripped["blocks"]:
        source = b["source"]
        development = plan["development"]
        if (
            source["population"] == "zeta-zero-index"
            and int(source["index_start"]) <= development["zero_indices_through"]
        ):
            raise ValueError("zero block overlaps development")
        if (
            b["module"] not in ZERO
            and source["start"] <= development["integer_indices_through"]
        ):
            raise ValueError("prime block overlaps development")
        sha = b["data_sha256"]
        if (
            not isinstance(sha, str)
            or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
            or sha in seen
        ):
            raise ValueError("invalid/reused data digest")
        seen.add(sha)
        b["data_sha256"] = None
    if stripped != expected:
        raise ValueError("frozen inventory structure/role/support mismatch")
    study = load_power()
    if plan["power_sha256"] != study["sha256"]:
        raise ValueError("power pin mismatch")
    for b in plan["blocks"]:
        if b["role"] == "contrast":
            power_row(b, study)
    return plan


def load(path=None):
    plan = validate(json.loads(Path(path or ROOT / PLAN).read_text()))
    lock = json.loads((ROOT / "mve/DEPS.lock").read_text())["packets"]["WO-1b"]
    if plan["sha256"] != lock["manifest_sha256"]:
        raise ValueError("DEPS inventory pin mismatch")
    for relative, expected in lock["source_hashes"].items():
        if s.sha256(s.inside(ROOT, relative)) != expected:
            raise ValueError("WO-1b runtime source pin mismatch")
    return plan


def jobs(plan):
    return [
        dict(
            snapshot_id=digest({"plan": plan["sha256"], "block": b["id"], "view": v})[
                :24
            ],
            block=b,
            view=v,
            module=b["module"],
        )
        for b in plan["blocks"]
        for v in range(2)
    ]


def require_go2_freeze(plan):
    """Recompute the reviewed GO2 commitment before opening held-out artifacts.

    The lock record is a sealed {manifest_sha256, files} object. Each of the five
    required file groups maps worktree-relative paths to SHA-256 hashes. Merely
    pinning a list of filenames or trusting cached hashes cannot open R.
    """
    try:
        record = json.loads((ROOT / "mve/DEPS.lock").read_text())["packets"]["WO-1b"][
            "go2_freeze"
        ]
        groups = record["files"]
        if (
            not isinstance(groups, dict)
            or set(groups)
            != {
                "observer_prompts",
                "contract",
                "power_study",
                "thresholds",
                "runner_source",
            }
            or any(
                not isinstance(files, dict) or not files for files in groups.values()
            )
            or record["manifest_sha256"] != plan["sha256"]
            or seal(record) != record
        ):
            raise ValueError("invalid freeze record")
        actual = {
            category: {path: s.sha256(s.inside(ROOT, path)) for path in files}
            for category, files in groups.items()
        }
        if seal({"manifest_sha256": plan["sha256"], "files": actual}) != record:
            raise ValueError("freeze digest mismatch")
    except (KeyError, TypeError, OSError, ValueError) as exc:
        raise ValueError("replication requires matching GO2 freeze") from exc


def observer_block(plan, ident, *, purpose):
    """R never enters tuning; observer/analysis require a reviewed GO2 freeze."""
    if purpose not in ("observer", "tuning", "analysis"):
        raise ValueError("invalid observer purpose")
    block = next(b for b in plan["blocks"] if b["id"] == ident)
    if block["partition"] == "R":
        if purpose == "tuning":
            raise ValueError("replication is sealed from tuning")
        require_go2_freeze(plan)
    validate(plan)
    return deepcopy(block)


def block_data(plan, block, cache=data.CACHE, *, purpose):
    data.require_purpose(block, purpose)
    expected = next(b for b in plan["blocks"] if b["id"] == block["id"])
    if expected != block:
        raise ValueError("block outside frozen plan")
    raw = encoded(data.numeric(block, cache, purpose=purpose))
    if hashlib.sha256(raw).hexdigest() != block["data_sha256"]:
        raise ValueError("block data drift")
    return raw


def snapshot_artifact(plan, ident, view, root, *, purpose, filename):
    """All observer/analysis artifact delivery passes the seal before any read."""
    from mve.observer.snapshot_batch import completed

    if filename not in ("blind-0.png", "data.json"):
        raise ValueError("invalid delivery artifact")
    observer_block(plan, ident, purpose=purpose)
    if view not in (0, 1):
        raise ValueError("invalid view")
    job = next(j for j in jobs(plan) if j["block"]["id"] == ident and j["view"] == view)
    folder = s.inside(root, job["snapshot_id"])
    if not completed(folder, plan, job):
        raise ValueError("capture unavailable")
    return (folder / filename).read_bytes()


def observer_png(plan, ident, view, root, *, purpose):
    return snapshot_artifact(
        plan, ident, view, root, purpose=purpose, filename="blind-0.png"
    )


def snapshot_data(plan, ident, view, root, *, purpose):
    return snapshot_artifact(
        plan, ident, view, root, purpose=purpose, filename="data.json"
    )
