"""Exact algebraic plane evaluator. Unsupported input raises; no approximate truth branch."""

import ast
from functools import lru_cache
from itertools import combinations
import sympy as sp
from mve.exact import canonical_exact, _number
from mve.degeneracy import repeated_degenerate, distinct_pairs
from mve.predicates import REGISTRY, canonical_proposition

VERSION = "mve-algebraic-plane-v1-e1a"


class ExactError(ValueError):
    pass


@lru_cache(maxsize=4096)
def parse_coordinate(text):
    try:
        if canonical_exact(text) != text:
            raise ExactError("noncanonical mathematical coordinate")
        return _number(ast.parse(text.replace("^", "**"), mode="eval").body)
    except (ValueError, TypeError) as exc:
        raise ExactError(str(exc)) from exc


def zero(value):
    if value.is_Rational:
        return value == 0
    if value.is_zero is not None:
        return bool(value.is_zero)
    value = sp.cancel(sp.expand(value))
    if value.is_zero is not None:
        return bool(value.is_zero)
    return sp.polys.numberfields.to_number_field(value).coeffs() == [0]


def sign(value):
    if value.is_Rational:
        return 0 if value == 0 else 1 if value > 0 else -1
    result = sp.sign(sp.cancel(sp.expand(value)))
    if result not in (-1, 0, 1):
        raise ExactError("algebraic sign not resolved; diagram excluded")
    return int(result)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def area(a, b, c):
    return cross(sub(b, a), sub(c, a))


def circle_determinant(points):
    # Translate the first point to zero; expand the remaining 3x3 determinant.
    rows = [
        (*sub(p, points[0]), dot(sub(p, points[0]), sub(p, points[0])))
        for p in points[1:]
    ]
    a, b, c = rows
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def equal_angle(points):
    a, b, c, d, e, f = points
    u, v, w, z = sub(a, b), sub(c, b), sub(d, e), sub(f, e)
    left, right = dot(u, v), dot(w, z)
    if sign(left) != sign(right):
        return False  # Squaring alone would confuse supplementary angles.
    return zero(left**2 * dot(w, w) * dot(z, z) - right**2 * dot(u, u) * dot(v, v))


def relation(pred, p):
    if pred in ("Collinear", "NotCollinear"):
        collinear = zero(area(*p))
        return collinear if pred == "Collinear" else not collinear
    if pred == "Distinct":
        return not all(zero(x - y) for x, y in zip(*p))
    if pred == "Concyclic":
        return zero(circle_determinant(p))
    if pred in ("Parallel", "Perpendicular", "EqualLength"):
        u, v = sub(p[1], p[0]), sub(p[3], p[2])
        value = (
            cross(u, v)
            if pred == "Parallel"
            else dot(u, v)
            if pred == "Perpendicular"
            else dot(u, u) - dot(v, v)
        )
        return zero(value)
    if pred == "EqualAngle":
        return equal_angle(p)
    if pred == "Midpoint":
        return all(zero(2 * p[0][i] - p[1][i] - p[2][i]) for i in (0, 1))
    if pred == "SBetween":
        return zero(area(*p)) and sign(dot(sub(p[0], p[1]), sub(p[0], p[2]))) < 0
    if pred == "RightAngle":
        return zero(dot(sub(p[0], p[1]), sub(p[2], p[1])))
    raise ExactError("unsupported predicate")


class ExactEvaluator:
    def __init__(self, coordinates):
        if not isinstance(coordinates, dict) or not coordinates:
            raise ExactError("exact coordinate mapping required")
        self.points = {}
        for name, values in coordinates.items():
            if (
                not isinstance(values, (list, tuple))
                or len(values) != 2
                or any(not isinstance(v, str) for v in values)
            ):
                raise ExactError("two canonical exact strings per point required")
            self.points[name] = tuple(parse_coordinate(v) for v in values)
        self.angles = {}
        self.coincident = set()
        for a, b in combinations(self.points, 2):
            if all(zero(x - y) for x, y in zip(self.points[a], self.points[b])):
                self.coincident.update(((a, b), (b, a)))

    def classify(self, proposition):
        try:
            prop = canonical_proposition(proposition)
            points = [self.points[name] for name in prop["args"]]
        except (ValueError, KeyError) as exc:
            raise ExactError("unsupported candidate or unknown point") from exc
        row = REGISTRY[prop["pred"]]
        if row["degeneracy"] != "none":
            if repeated_degenerate(prop["pred"], prop["args"]) or any(
                (a, b) in self.coincident
                for a, b in distinct_pairs(prop["pred"], prop["args"])
            ):
                return "degenerate"
            if prop["pred"] == "Concyclic" and any(
                zero(area(*triple)) for triple in combinations(points, 3)
            ):
                return "degenerate"
        if prop["pred"] == "EqualAngle":
            left = self.angle_signature(tuple(prop["args"][:3]))
            right = self.angle_signature(tuple(prop["args"][3:]))
            result = left[0] == right[0] and zero(left[1] - right[1])
        else:
            result = relation(prop["pred"], points)
        return "true" if result else "false"

    def angle_signature(self, names):
        if names not in self.angles:
            a, b, c = (self.points[n] for n in names)
            u, v = sub(a, b), sub(c, b)
            cosine_numerator = dot(u, v)
            squared_cosine = sp.cancel(cosine_numerator**2 / (dot(u, u) * dot(v, v)))
            self.angles[names] = (sign(cosine_numerator), squared_cosine)
        return self.angles[names]
