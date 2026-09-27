"""Frozen family partitions for offline evaluation; no inference or truth loading."""

from dataclasses import dataclass
from hashlib import sha256
import json

PARTITIONS = ("development", "retrieval", "fit", "calibration", "evaluation")


class SplitError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(value.encode()).hexdigest()


def validate(manifest):
    required = {
        "schema",
        "seed",
        "allocations",
        "items",
        "retired",
        "reason",
        "parent_sha256",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest["schema"] != "mve-split-v1"
    ):
        raise SplitError("invalid split manifest")
    if not isinstance(manifest["seed"], str) or not manifest["seed"]:
        raise SplitError("nonempty seed required")
    counts = manifest["allocations"]
    if not isinstance(counts, dict) or set(counts) != set(PARTITIONS):
        raise SplitError("all five disjoint uses must be declared")
    if any(type(n) is not int or n <= 0 for n in counts.values()):
        raise SplitError("positive family counts required")
    seen, families = set(), {}
    for row in manifest["items"]:
        if not isinstance(row, dict) or set(row) != {"id", "family", "split"}:
            raise SplitError("invalid split row")
        if any(not isinstance(row[k], str) or not row[k] for k in row):
            raise SplitError("nonempty string identifiers required")
        if row["id"] in seen or row["split"] not in PARTITIONS:
            raise SplitError("duplicate id or unknown partition")
        if families.setdefault(row["family"], row["split"]) != row["split"]:
            raise SplitError("family crosses partitions")
        seen.add(row["id"])
    if {s: sum(v == s for v in families.values()) for s in PARTITIONS} != counts:
        raise SplitError("family allocation counts do not match")
    if type(manifest["retired"]) is not bool:
        raise SplitError("retirement flag must be boolean")
    if manifest["retired"] and (
        not manifest["reason"] or not manifest["parent_sha256"]
    ):
        raise SplitError("retirement requires a reason and parent hash")


@dataclass(frozen=True)
class FrozenSplit:
    payload: str

    def __post_init__(self):
        try:
            validate(json.loads(self.payload))
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise SplitError("invalid split payload") from exc

    @property
    def sha256(self):
        return digest(self.payload)

    def manifest(self):
        return json.loads(self.payload)

    @classmethod
    def load(cls, payload, *, expected_sha256):
        if digest(payload) != expected_sha256:
            raise SplitError("frozen manifest hash mismatch")
        return cls(payload)

    def require_evaluation(self):
        if self.manifest()["retired"]:
            raise SplitError("evaluation set retired after development exposure")
        return self.sha256

    def retire(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise SplitError("retirement reason required")
        data = self.manifest()
        data.update(retired=True, reason=reason, parent_sha256=self.sha256)
        return FrozenSplit(canonical(data))


def freeze(items, *, seed, allocations):
    if not isinstance(seed, str) or not seed:
        raise SplitError("nonempty seed required")
    if not isinstance(items, list) or not items:
        raise SplitError("nonempty item list required")
    for row in items:
        if not isinstance(row, dict) or set(row) != {"id", "family"}:
            raise SplitError("input rows need only id and family")
        if any(not isinstance(v, str) or not v for v in row.values()):
            raise SplitError("nonempty string identifiers required")
    if not isinstance(allocations, dict) or set(allocations) != set(PARTITIONS):
        raise SplitError("all partitions required")
    if any(type(n) is not int or n <= 0 for n in allocations.values()):
        raise SplitError("positive family counts required")
    families = sorted(
        {r["family"] for r in items}, key=lambda f: (digest(canonical([seed, f])), f)
    )
    if sum(allocations.values()) != len(families):
        raise SplitError("allocation must use each family exactly once")
    assignment, cursor = {}, 0
    for split in PARTITIONS:
        for family in families[cursor : cursor + allocations[split]]:
            assignment[family] = split
        cursor += allocations[split]
    rows = [
        dict(r, split=assignment[r["family"]])
        for r in sorted(items, key=lambda r: r["id"])
    ]
    return FrozenSplit(
        canonical(
            {
                "schema": "mve-split-v1",
                "seed": seed,
                "allocations": allocations,
                "items": rows,
                "retired": False,
                "reason": None,
                "parent_sha256": None,
            }
        )
    )
