"""Exact segment intersection and gap-preserving PD assembly, not raster perception."""

from dataclasses import dataclass
from fractions import Fraction as F
from functools import cmp_to_key
from itertools import combinations

from mve.topology.model import Diagram, fail


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def det(a, b):
    return a[0] * b[1] - a[1] * b[0]


@dataclass(frozen=True)
class Gap:
    component: int
    segment: int
    start: F
    end: F


@dataclass(frozen=True)
class Skeleton:
    components: tuple
    gaps: tuple[Gap, ...]
    mirror: bool


@dataclass(frozen=True)
class Pass:
    component: int
    segment: int
    t: F
    tangent: tuple


@dataclass(frozen=True)
class Crossing:
    point: tuple
    under: Pass
    over: Pass


def segments(s):
    if not 1 <= len(s.components) <= 4 or type(s.mirror) is not bool:
        fail("skeleton", "one to four closed oriented components required")
    rows = []
    for ci, points in enumerate(s.components):
        if len(points) < 3 or any(
            len(p) != 2 or any(type(v) not in (int, F) for v in p) for p in points
        ):
            fail("skeleton", "exact rational polygon coordinates required")
        pairs = list(zip(points, points[1:] + points[:1]))
        if sum(det(a, b) for a, b in pairs) <= 0:
            fail("orientation", "component traversal must be counter-clockwise")
        for i, (a, b) in enumerate(pairs):
            if a == b:
                fail("skeleton", "zero-length segment")
            rows.append((ci, i, a, b))
    return rows


def meet(a, b, c, d):
    u, v, w = sub(b, a), sub(d, c), sub(c, a)
    divisor = det(u, v)
    if divisor == 0:
        if det(w, u) == 0:
            axis = 0 if u[0] else 1
            lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
            hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
            if lo <= hi:
                fail("crossing_detection", "non-transverse overlap or touch")
        return None
    t, q = F(det(w, v), divisor), F(det(w, u), divisor)
    if 0 <= t <= 1 and 0 <= q <= 1:
        if t in (0, 1) or q in (0, 1):
            fail("crossing_detection", "non-transverse vertex crossing")
        return t, q, (a[0] + t * u[0], a[1] + t * u[1])
    return None


def intersections(s):
    rows, found, points = segments(s), [], set()
    for (ci, i, a, b), (cj, j, c, d) in combinations(rows, 2):
        if ci == cj and (i - j) % len(s.components[ci]) in (
            1,
            len(s.components[ci]) - 1,
        ):
            # Adjacent segments may join but must not fold back and overlap.
            if det(sub(b, a), sub(d, c)) == 0:
                shared = set((a, b)) & set((c, d))
                p = next(iter(shared))
                x, y = (
                    next(v for v in (a, b) if v != p),
                    next(v for v in (c, d) if v != p),
                )
                if sum(u * v for u, v in zip(sub(x, p), sub(y, p))) > 0:
                    fail("skeleton", "adjacent segments backtrack")
            continue
        hit = meet(a, b, c, d)
        if hit is None:
            continue
        t, q, p = hit
        if p in points:
            fail("crossing_detection", "triple crossing")
        points.add(p)
        found.append((p, Pass(ci, i, t, sub(b, a)), Pass(cj, j, q, sub(d, c))))
    if len(found) > 7:
        fail("unsupported_convention", "more than seven crossings")
    return tuple(found)


def decode(s):
    hits = intersections(s)
    crossings, used = [], set()
    for p, a, b in hits:
        evidence = [
            (i, passage)
            for i, g in enumerate(s.gaps)
            for passage in (a, b)
            if (g.component, g.segment) == (passage.component, passage.segment)
            and 0 < g.start < passage.t < g.end < 1
        ]
        if len(evidence) != 1:
            fail("ambiguous_source", "exactly one underpass gap required per crossing")
        i, under = evidence[0]
        if i in used:
            fail("ambiguous_source", "gap spans multiple crossings")
        used.add(i)
        crossings.append(Crossing(p, under, b if under == a else a))
    if used != set(range(len(s.gaps))):
        fail("ambiguous_source", "unassociated or invalid gap evidence")
    return assemble(tuple(crossings), len(s.components), s.mirror)


def angle_compare(a, b):
    def half(p):
        return 0 if p[1] > 0 or (p[1] == 0 and p[0] >= 0) else 1

    if half(a[0]) != half(b[0]):
        return half(a[0]) - half(b[0])
    return -1 if det(a[0], b[0]) > 0 else 1


def arc_labels(crossings, count):
    cycles, labels, offset = [], {}, 1
    ordered = sorted(crossings, key=lambda x: (x.point[1], x.point[0]))
    component_order = sorted(
        range(count),
        key=lambda ci: next(
            (
                (i, 0 if x.under.component == ci else 1)
                for i, x in enumerate(ordered)
                if ci in (x.under.component, x.over.component)
            ),
            (len(ordered), ci),
        ),
    )
    for ci in component_order:
        visits = [
            (x, p) for x in ordered for p in (x.under, x.over) if p.component == ci
        ]
        if not visits:
            cycles.append((offset,))
            offset += 1
            continue
        anchor = visits[0][1]
        passes = sorted((p for _, p in visits), key=lambda p: (p.segment, p.t))
        start = passes.index(anchor)
        passes = passes[start:] + passes[:start]
        cycle = tuple(range(offset, offset + len(passes)))
        for i, p in enumerate(passes):
            labels[p] = (cycle[i], cycle[(i + 1) % len(cycle)])
        cycles.append(cycle)
        offset += len(passes)
    return tuple(cycles), labels


def assemble(crossings, count, mirror):
    cycles, labels = arc_labels(crossings, count)
    pd, signs = [], []
    for x in sorted(crossings, key=lambda x: (x.point[1], x.point[0])):
        rays = []
        for passage in (x.under, x.over):
            incoming, outgoing = labels[passage]
            rays += [
                ((-passage.tangent[0], -passage.tangent[1]), incoming),
                (passage.tangent, outgoing),
            ]
        rays.sort(key=cmp_to_key(angle_compare))
        # Locate by ray as an R1 loop can have equal incoming/outgoing labels.
        start = next(
            i
            for i, (v, _) in enumerate(rays)
            if v == (-x.under.tangent[0], -x.under.tangent[1])
        )
        pd.append(tuple(a for _, a in rays[start:] + rays[:start]))
        signs.append(1 if det(x.over.tangent, x.under.tangent) > 0 else -1)
    return Diagram(tuple(pd), cycles, tuple(signs), mirror)
