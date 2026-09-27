"""Frozen oriented PD grammar, with only the declared scoring equivalences."""

from collections import Counter
from dataclasses import dataclass
from itertools import permutations, product

ERRORS = frozenset(
    (
        "skeleton",
        "crossing_detection",
        "orientation",
        "traversal",
        "arc_association",
        "labels",
        "canonicalization",
        "unsupported_convention",
        "ambiguous_source",
        "unresolved",
    )
)
GRAMMAR = "mve-oriented-pd-v1"


class TopologyError(ValueError):
    def __init__(self, category, detail):
        if category not in ERRORS:
            raise ValueError("unknown topology error category")
        self.category = category
        super().__init__(category + ": " + detail)


def fail(category, detail):
    raise TopologyError(category, detail)


@dataclass(frozen=True)
class Diagram:
    pd: tuple[tuple[int, int, int, int], ...]
    components: tuple[tuple[int, ...], ...]
    signs: tuple[int, ...]
    mirror: bool = False

    def __post_init__(self):
        validate(self)

    def to_dict(self):
        return {
            "schema": GRAMMAR,
            "pd": [list(x) for x in self.pd],
            "components": [list(x) for x in self.components],
            "signs": list(self.signs),
            "mirror": self.mirror,
        }


def validate(d):
    if type(d.mirror) is not bool or not all(
        type(x) is tuple for x in (d.pd, d.components, d.signs, *d.pd, *d.components)
    ):
        fail("unsupported_convention", "immutable tuples and a Boolean mirror required")
    if len(d.pd) > 7 or not 1 <= len(d.components) <= 4:
        fail("unsupported_convention", "at most seven crossings and four components")
    if any(len(x) != 4 for x in d.pd) or len(d.signs) != len(d.pd):
        fail("crossing_detection", "four half-arcs and one sign per crossing")
    if any(type(s) is not int or s not in (-1, 1) for s in d.signs):
        fail("orientation", "right-handed signs must be +1 or -1")
    arcs = [a for c in d.components for a in c]
    if any(not c for c in d.components) or any(type(a) is not int for a in arcs):
        fail("labels", "nonempty component cycles of integer labels required")
    if sorted(arcs) != list(range(1, len(arcs) + 1)):
        fail("labels", "each positive contiguous arc label belongs to one component")
    count = Counter(a for row in d.pd for a in row)
    if any(type(a) is not int or a not in arcs or n != 2 for a, n in count.items()):
        fail("arc_association", "PD labels must occur exactly twice")
    if any(a not in count and len(c) != 1 for c in d.components for a in c):
        fail("arc_association", "only a crossing-free circle may lack PD occurrences")
    expected = {a: c[(i + 1) % len(c)] for c in d.components for i, a in enumerate(c)}
    actual = successor(d)
    if actual != expected:
        fail("traversal", "crossings must follow each declared oriented cycle")


def successor(d):
    result = {
        c[0]: c[0]
        for c in d.components
        if len(c) == 1 and c[0] not in {a for row in d.pd for a in row}
    }
    for (a, b, c, e), sign in zip(d.pd, d.signs):
        pairs = ((a, c), (e, b)) if sign == 1 else ((a, c), (b, e))
        for source, target in pairs:
            if source in result:
                fail("arc_association", "two outgoing successors for one arc")
            result[source] = target
    return result


def canonical_pd(d):
    """Orbit under component permutations and cyclic label shifts ONLY.

    Crossing list order, local CCW slot order, strand orientation, and mirror
    remain untouched. No Reidemeister move or knot-type equivalence is allowed.
    """
    keys = []
    for order in permutations(d.components):
        for shifts in product(*(range(len(c)) for c in order)):
            mapping, offset = {}, 1
            for c, shift in zip(order, shifts):
                rotated = c[shift:] + c[:shift]
                mapping.update({a: offset + i for i, a in enumerate(rotated)})
                offset += len(c)
            keys.append(
                (
                    tuple(len(c) for c in order),
                    tuple(tuple(mapping[a] for a in row) for row in d.pd),
                )
            )
    return min(keys)
