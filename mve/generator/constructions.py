"""Versioned in-house fallback recipes; all mathematical coordinates are algebraic."""

import sympy as sp
from mve.exact import canonical_exact
from mve.identity import digest

FAMILIES = (
    "midpoint_grid",
    "rectangle_center",
    "oblique_parallelogram",
    "right_triangle",
    "rational_circle",
    "isosceles_pair",
    "trapezoid",
    "concave_polygon",
    "parallel_triples",
    "radical_triangle",
    "orthogonal_pairs",
    "circle_radius",
    "skew_grid",
    "convex_hexagon",
    "collinear_extension",
)
CONTROLS = (
    "exact_positive",
    "near_miss_negative",
    "adversarial_negative",
    "not_to_scale",
    "degenerate",
)
VERSION = "inhouse-plane-v1"


S, T = sp.symbols("s t")
RECIPES = {
    "midpoint_grid": [(0, 0), (2 * S, 0), (S, 0), (0, T), (2 * S, T), (S, T)],
    "rectangle_center": [
        (0, 0),
        (2 * S, 0),
        (2 * S, 2 * T),
        (0, 2 * T),
        (S, T),
        (3 * S, T),
    ],
    "oblique_parallelogram": [
        (0, 0),
        (2 * S, 0),
        (2 * S + T, 2 * T),
        (T, 2 * T),
        (S, 0),
        (S + T, 2 * T),
    ],
    "right_triangle": [(0, 0), (2 * S, 0), (0, 2 * T), (S, 0), (0, T), (S, T)],
    "isosceles_pair": [(0, 0), (2 * S, 0), (S, T), (S, 0), (3 * S, T), (4 * S, 0)],
    "trapezoid": [
        (0, 0),
        (3 * S, 0),
        (2 * S, T),
        (S, T),
        (0, 2 * T),
        (3 * S, 2 * T),
    ],
    "concave_polygon": [
        (0, 0),
        (3 * S, 0),
        (3 * S, 3 * T),
        (S, T),
        (0, 3 * T),
        (S, 2 * T),
    ],
    "parallel_triples": [
        (0, 0),
        (S, T),
        (2 * S, 2 * T),
        (0, 3 * T),
        (S, 4 * T),
        (2 * S, 5 * T),
    ],
    "radical_triangle": [
        (0, 0),
        (2 * S, 0),
        (S, sp.sqrt(3) * T),
        (3 * S, sp.sqrt(3) * T),
        (4 * S, 0),
        (5 * S, 2 * T),
    ],
    "orthogonal_pairs": [
        (0, 0),
        (2 * S, 0),
        (S, -T),
        (S, T),
        (3 * S, -T),
        (3 * S, T),
    ],
    "circle_radius": [(0, 0), (S, 0), (0, S), (-S, 0), (S, T), (S, -T)],
    "skew_grid": [
        (0, 0),
        (S, 0),
        (S / 3, T),
        (4 * S / 3, T),
        (2 * S, 3 * T),
        (7 * S / 3, 4 * T),
    ],
    "convex_hexagon": [
        (0, 0),
        (2 * S, 0),
        (3 * S, T),
        (2 * S, 3 * T),
        (0, 2 * T),
        (-S, T),
    ],
    "collinear_extension": [(i * S, i * T) for i in range(6)],
}


def anchors(family, s, t):
    if family == "rational_circle":
        return [
            (s * (1 - q * q) / (1 + q * q), s * 2 * q / (1 + q * q))
            for q in [sp.Rational(i) + t / 10 for i in range(-2, 4)]
        ]
    return [
        tuple(sp.sympify(v).subs({S: s, T: t}) for v in xy) for xy in RECIPES[family]
    ]


def construct(family, seed, *, control=None):
    if family not in FAMILIES or type(seed) is not int or seed < 0:
        raise ValueError(
            "known construction family and nonnegative integer seed required"
        )
    control = CONTROLS[seed % len(CONTROLS)] if control is None else control
    if control not in CONTROLS:
        raise ValueError("unsupported control")
    code = int(digest([family, seed]), 16)
    s, t = (
        2
        + sp.Rational(seed + 1, 1009)
        + sp.Rational(FAMILIES.index(family) + 1, 1000003),
        2 + sp.Rational((code >> 8) % 43, 103),
    )
    points = dict(zip("ABCDEF", anchors(family, s, t)))
    a, b = points["A"], points["B"]
    midpoint = tuple(sp.Rational(1, 2) * (x + y) for x, y in zip(a, b))
    delta = (
        sp.Rational(1, 10**6) if control == "near_miss_negative" else sp.Rational(1, 3)
    )
    if control in {"exact_positive", "not_to_scale"}:
        points["C"] = midpoint
    elif control == "degenerate":
        points["C"] = a
    else:
        points["C"] = (
            midpoint[0] - (b[1] - a[1]) * delta,
            midpoint[1] + (b[0] - a[0]) * delta,
        )
    coordinates = {
        name: [
            canonical_exact(str(sp.expand(v)).replace("**", "^").replace(" ", ""))
            for v in xy
        ]
        for name, xy in points.items()
    }
    premises = [{"pred": "Distinct", "args": ["A", "B"]}]
    if control in {"exact_positive", "not_to_scale"}:
        premises.append({"pred": "Midpoint", "args": ["C", "A", "B"]})
    return {
        "family": family,
        "coordinates": coordinates,
        "premises": premises,
        "control": control,
        "control_target": {"pred": "Collinear", "args": ["A", "B", "C"]},
        "generator": {
            "id": "mve-inhouse",
            "version": VERSION,
            "seed": seed,
            "config_sha256": digest(
                {"family": family, "control": control, "version": VERSION}
            ),
        },
    }
