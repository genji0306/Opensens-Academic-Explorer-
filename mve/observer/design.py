"""Frozen paired allocation from WO-1 manifests; no results or model text enter it."""

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import hashlib
import random
from mve.observer.card import Card, card_hash, digest
from mve.observer.snapshots import validate_manifest

ARMS = ("real", "null_twin", "image_free", "shuffled")


def require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass(frozen=True)
class Design:
    _json: str

    @classmethod
    def from_dict(cls, data):
        require(
            data.get("sha256")
            == digest({k: v for k, v in data.items() if k != "sha256"}),
            "design hash mismatch",
        )
        return cls(json.dumps(data, sort_keys=True, allow_nan=False))

    def to_dict(self):
        return json.loads(self._json)


def catalogue(manifest, root):
    validate_manifest(manifest, root, prospective=True, defer_replication_data=True)
    blocks, by_id = {}, {e["snapshot_id"]: e for e in manifest["snapshots"]}
    supports = []
    for e in manifest["snapshots"]:
        ref = e["data_ref"]
        ident = ref["source_block_id"]
        if ident in blocks:
            require(blocks[ident][0]["data_ref"] == ref, "inconsistent block views")
        else:
            support = ref.get("support")
            require(
                isinstance(support, dict)
                and set(support) == {"population", "start", "stop"},
                "disjoint support declaration required",
            )
            require(
                isinstance(support["population"], str)
                and support["population"]
                and type(support["start"]) is int
                and type(support["stop"]) is int
                and 0 <= support["start"] < support["stop"],
                "invalid block support",
            )
            for other, sha in supports:
                require(ref["sha256"] != sha, "reused source bytes")
                require(
                    support["population"] != other["population"]
                    or support["stop"] <= other["start"]
                    or other["stop"] <= support["start"],
                    "overlapping block support",
                )
            supports.append((support, ref["sha256"]))
            blocks[ident] = []
        blocks[ident].append(e)
    for views in blocks.values():
        views.sort(key=lambda e: e["snapshot_id"])
    return blocks, by_id


def allocate(manifest, root, config):
    """Seeded permutation within frozen role pools. Unused inputs are never redrawn.

    Null seeds are those of the pre-rendered twins selected by the allocation;
    the runner cannot reseed an existing PNG. Support intervals are declarations,
    not a proof of statistical independence (A1) or exchangeability (A2).
    """
    c = deepcopy(config)
    require(type(c["seed"]) is int and type(c["pilot"]) is bool, "seed/pilot required")
    require(
        c["views"] == (1 if c["pilot"] else 2) and c["slots"] == 3,
        "fixed V/C slots required",
    )
    require(
        type(c["retries"]) is int and 0 <= c["retries"] <= 2, "retries must be 0..2"
    )
    require(
        c["strata"] and len({s["id"] for s in c["strata"]}) == len(c["strata"]),
        "unique frozen strata required",
    )
    blocks, by_id = catalogue(manifest, root)
    rng, used, clusters, jobs = random.Random(c["seed"]), set(), [], []
    actual_dev = {
        k for k, v in blocks.items() if v[0]["data_ref"]["role"] == "development"
    }
    require(set(c["development_blocks"]) == actual_dev, "development list mismatch")
    baseline_seeds = set()
    for st in c["strata"]:
        require(st["id"] == st["module"] + " × " + st["family"], "stratum mismatch")
        template = c["checks"][st["family"]]
        Card.from_dict(template)
        require(
            template["check_spec"]["check_id"] == "spacing"
            and st["family"] == "zero spacings",
            "family check unavailable",
        )
        require(
            len(c["image_free"][st["family"]]) == c["views"] * 3,
            "image-free slots must match",
        )
        require(
            template["status"] == "draft", "frozen family template must start at draft"
        )
        for proposal in c["image_free"][st["family"]]:
            require(
                type(proposal) is dict
                and set(proposal)
                == {"claim", "testable_form", "prediction", "resemblance_target"},
                "invalid generic library slot",
            )
            require(
                proposal["testable_form"] == template["testable_form"],
                "generic changes check mapping",
            )
            generic = deepcopy(template)
            generic.update(proposal)
            generic["content_hash"] = card_hash(generic)
            Card.from_dict(generic)
        pools = {
            k: sorted(st[k])
            for k in (
                "discovery",
                "replication",
                "donors",
                "contrast_discovery",
                "contrast_replication",
            )
        }
        n = len(pools["discovery"])
        require(
            n > 0 and len(pools["replication"]) == len(pools["donors"]) == n,
            "paired pools must have equal size",
        )
        require(
            len(pools["contrast_discovery"]) == len(pools["contrast_replication"]),
            "contrast pair mismatch",
        )
        for values in pools.values():
            rng.shuffle(values)
        pairs = [
            (pools["discovery"][i], pools["replication"][i], pools["donors"][i], False)
            for i in range(n)
        ]
        pairs += [
            (d, r, None, True)
            for d, r in zip(pools["contrast_discovery"], pools["contrast_replication"])
        ]
        for d, r, donor, contrast in pairs:
            chosen = {}
            for ident, role in ((d, "discovery"), (r, "replication"), (donor, "donor")):
                if ident is None:
                    continue
                require(
                    ident in blocks and ident not in used and ident not in actual_dev,
                    "block reuse or missing block",
                )
                views = blocks[ident]
                require(len(views) == c["views"], "fixed views missing")
                require(
                    all(
                        e["data_ref"]["role"] == role
                        and e["data_ref"]["stratum"] == st["id"]
                        and e["module"] == st["module"]
                        and e["control"]["kind"] == "none"
                        for e in views
                    ),
                    "role or stratum mismatch",
                )
                used.add(ident)
                chosen[role] = views
            null_d = [
                by_id[e["control"]["twin_snapshot_id"]] for e in chosen["discovery"]
            ]
            null_r = [
                by_id[e["control"]["twin_snapshot_id"]] for e in chosen["replication"]
            ]
            for twins, role in ((null_d, "discovery"), (null_r, "replication")):
                ids = {e["data_ref"]["source_block_id"] for e in twins}
                require(len(ids) == 1 and not ids & used, "null block reuse")
                require(
                    all(e["data_ref"]["role"] == role for e in twins),
                    "null partition mismatch",
                )
                used.update(ids)
            seeds = (null_d[0]["data_ref"]["seed"], null_r[0]["data_ref"]["seed"])
            require(
                len(set(seeds)) == 2 and not set(seeds) & baseline_seeds,
                "baseline seed reuse",
            )
            baseline_seeds.update(seeds)
            cid = digest({"seed": c["seed"], "d": d, "r": r})[:16]
            cluster = dict(
                id=cid,
                stratum=st["id"],
                family=st["family"],
                discovery=d,
                replication=r,
                donor=donor,
                null_discovery=null_d[0]["data_ref"]["source_block_id"],
                null_replication=null_r[0]["data_ref"]["source_block_id"],
                baseline_seeds=list(seeds),
                contrast=contrast,
            )
            clusters.append(cluster)
            for arm in ("contrast",) if contrast else ARMS:
                delivered = (
                    null_d
                    if arm == "null_twin"
                    else chosen.get("donor")
                    if arm == "shuffled"
                    else chosen["discovery"]
                )
                for v in range(c["views"]):
                    ident = digest(
                        {"cluster": cid, "arm": arm, "view": v, "seed": c["seed"]}
                    )[:16]
                    jobs.append(
                        dict(
                            id=ident,
                            cluster=cid,
                            arm=arm,
                            view=v,
                            slots=3,
                            snapshot_id=None
                            if arm == "image_free"
                            else delivered[v]["snapshot_id"],
                            discovery=cluster["null_discovery"]
                            if arm == "null_twin"
                            else d,
                            replication=cluster["null_replication"]
                            if arm == "null_twin"
                            else r,
                            family=st["family"],
                        )
                    )
    rng.shuffle(jobs)
    data = dict(
        protocol_sha256=hashlib.sha256(
            Path(__file__).with_name("dispatch.py").read_bytes()
        ).hexdigest(),
        schema="mve-observer-design-v1",
        config=c,
        manifest=deepcopy(manifest),
        clusters=clusters,
        jobs=jobs,
    )
    data["sha256"] = digest(data)
    return Design.from_dict(data)
