"""Closed-braid fixtures: independent symbolic crossing truth and rational geometry."""

from dataclasses import dataclass
from fractions import Fraction as F
from hashlib import sha256
import json
from pathlib import Path

from mve.evaluation.splits import freeze, PARTITIONS
from mve.topology.geometry import decode
from mve.topology.render import render
from mve.topology.scoring import score
from mve.topology.model import Diagram
from mve.topology.geometry import Skeleton, Gap, Pass, Crossing, assemble, sub

FAMILIES = {
    "unknot": (1, ()),
    "trefoil": (2, (1, 1, 1)),
    "figure_eight": (3, (1, -2, 1, -2)),
    "hopf": (2, (1, 1)),
    "unlink": (2, ()),
}
VARIANTS = ("base", "mirror", "r1", "r1_negative", "r2", "near_miss")


@dataclass(frozen=True)
class Fixture:
    id: str
    family: str
    variant: str
    skeleton: Skeleton
    truth: Diagram

    @property
    def knot_type(self):
        if self.family == "trefoil":
            return "trefoil_positive" if self.truth.mirror else "trefoil_negative"
        return self.family


def braid(n, word, near=False):
    height = 4 * (len(word) + int(near) + 1)
    paths = [[(4 * i, height)] for i in range(n)]
    occupied, expected = list(range(n)), []
    if near:
        for i in range(n):
            mid = 2 + (F(-1, 16) if i == 0 else F(1, 16)) if i < 2 else 4 * i
            paths[i] += [(mid, height - 2), (4 * i, height - 4)]
    for row, g in enumerate(word):
        j, y = abs(g) - 1, height - 4 * (row + int(near))
        left, right = occupied[j : j + 2]
        over, under = (left, right) if g > 0 else (right, left)
        for slot, track in enumerate(occupied):
            target = j + 1 if slot == j else j if slot == j + 1 else slot
            paths[track].append((4 * target, y - 4))
        expected.append(
            ((4 * j + 2, y - 2), tuple(paths[under][-2:]), tuple(paths[over][-2:]))
        )
        occupied[j : j + 2] = [right, left]
    for slot, track in enumerate(occupied):
        paths[track].append((4 * slot, 0))
    return close_braid(paths, occupied, height, n), expected


def close_braid(paths, occupied, height, n):
    components, used = [], set()
    for start in range(n):
        if start in used:
            continue
        points, track = [], start
        while track not in used:
            used.add(track)
            points.extend(paths[track])
            slot = occupied.index(track)
            depth, right = 4 * (n - slot), 4 * n + 4 * (n - slot)
            points.extend(
                [
                    (4 * slot, -depth),
                    (right, -depth),
                    (right, height + depth),
                    (4 * slot, height + depth),
                ]
            )
            track = slot
        components.append(tuple(points))
    return tuple(components)


def fixture(family, variant="base"):
    if family not in FAMILIES or variant not in VARIANTS:
        raise ValueError("unknown fixture family or variant")
    n, word = FAMILIES[family]
    if variant in ("r1", "r1_negative") or (variant in ("r2", "near_miss") and n == 1):
        word, n = word + ((-n if variant == "r1_negative" else n),), n + 1
    if variant == "r2":
        word += (1, -1)
    components, expected = braid(n, word, variant == "near_miss")
    mirror = variant == "mirror"

    def transform(p):
        return (-p[0], p[1]) if mirror else p

    components = tuple(tuple(transform(p) for p in c) for c in components)
    if mirror:
        components = tuple(c[::-1] for c in components)
    crossings, gaps = [], []
    for p, under, over in expected:
        u = locate(components, tuple(transform(v) for v in under))
        o = locate(components, tuple(transform(v) for v in over))
        crossings.append(Crossing(transform(p), u, o))
        gaps.append(Gap(u.component, u.segment, F(3, 8), F(5, 8)))
    skeleton = Skeleton(components, tuple(gaps), mirror)
    truth = assemble(tuple(crossings), len(components), mirror)
    return Fixture(family + "-" + variant, family, variant, skeleton, truth)


def locate(components, edge):
    for ci, points in enumerate(components):
        for i, (a, b) in enumerate(zip(points, points[1:] + points[:1])):
            if set((a, b)) == set(edge):
                return Pass(ci, i, F(1, 2), sub(b, a))
    raise ValueError("symbolic braid edge absent from geometry")


def corpus():
    return tuple(fixture(f, v) for f in FAMILIES for v in VARIANTS)


def frozen_split(items):
    frozen = freeze(
        [{"id": x.id, "family": x.family} for x in items],
        seed="mve-wp10-v1",
        allocations=dict.fromkeys(PARTITIONS, 1),
    )
    # All 30 cases are public regression fixtures, including the evaluation family.
    return frozen.retire("public coordinate regression corpus used during development")


def skeleton_dict(s):
    return {
        "components": [[[str(v) for v in p] for p in c] for c in s.components],
        "gaps": [
            {
                "component": g.component,
                "segment": g.segment,
                "start": str(g.start),
                "end": str(g.end),
            }
            for g in s.gaps
        ],
        "mirror": s.mirror,
    }


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def write_corpus(output):
    output = Path(output)
    for folder in ("images", "truth", "geometry"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    items, hashes = corpus(), {}
    for item in items:
        (output / "images" / f"{item.id}.png").write_bytes(render(item.skeleton))
        write_json(output / "truth" / f"{item.id}.json", item.truth.to_dict())
        write_json(
            output / "geometry" / f"{item.id}.json", skeleton_dict(item.skeleton)
        )
        for folder, suffix in (
            ("images", "png"),
            ("truth", "json"),
            ("geometry", "json"),
        ):
            p = Path(folder) / f"{item.id}.{suffix}"
            hashes[str(p)] = sha256((output / p).read_bytes()).hexdigest()
    write_json(
        output / "manifest.json",
        [
            {
                "id": i.id,
                "family": i.family,
                "variant": i.variant,
                "knot_type": i.knot_type,
                "generator": "closed-braid-v1",
            }
            for i in items
        ],
    )
    split = frozen_split(items)
    (output / "split.json").write_text(split.payload)
    receipt = {
        "schema": "mve-topology-fixtures-v1",
        "scope": "synthetic_coordinate_self_consistency",
        "g5_status": "not established",
        "hosted_calls": 0,
        "perception_runs": 0,
        "external_diagrams": 0,
        "split_sha256": split.sha256,
        "split_retired": True,
        "scores": score(items, {i.id: decode(i.skeleton) for i in items}),
        "files": hashes,
    }
    write_json(output / "receipt.json", receipt)
    return receipt
