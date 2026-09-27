"""Deterministic coordinate consistency; tolerances are fixture inputs, not fitted claims."""

from itertools import combinations
import math
import numpy as np
from mve.predicates import REGISTRY, canonical_proposition

VERSION = "mve-coordinate-fixture-v1"
ZERO = 1e-12
NEAR = 1e-6


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def height(points):
    a, b, c = points
    longest = max(np.linalg.norm(x - y) for x, y in combinations(points, 2))
    return abs(cross(b - a, c - a)) / longest if longest else 0.0


def angle(a, b, c):
    u, v = a - b, c - b
    return math.degrees(math.atan2(abs(cross(u, v)), float(np.dot(u, v))))


def residual(pred, p):
    if pred in {"Collinear", "NotCollinear"}:
        value = height(p)
        return (
            (float(value <= ZERO), "ratio")
            if pred == "NotCollinear"
            else (value, "px_normalized")
        )
    if pred == "Distinct":
        return float(np.linalg.norm(p[0] - p[1]) <= ZERO), "ratio"
    if pred == "Concyclic":
        q = p - p.mean(axis=0)
        center = np.linalg.lstsq(2 * q, np.sum(q * q, axis=1), rcond=None)[0]
        radii = np.linalg.norm(q - center, axis=1)
        return float(np.max(np.abs(radii - radii.mean()))), "px_normalized"
    if pred in {"Parallel", "Perpendicular", "EqualLength"}:
        u, v = p[1] - p[0], p[3] - p[2]
        lengths = np.linalg.norm(u), np.linalg.norm(v)
        if pred == "EqualLength":
            return abs(lengths[0] - lengths[1]), "px_normalized"
        value = abs(cross(u, v)) if pred == "Parallel" else abs(float(np.dot(u, v)))
        return value / (lengths[0] * lengths[1]), "ratio"
    if pred == "EqualAngle":
        return abs(angle(*p[:3]) - angle(*p[3:])), "deg"
    if pred == "RightAngle":
        return abs(angle(*p) - 90), "deg"
    if pred == "Midpoint":
        return float(np.linalg.norm(p[0] - (p[1] + p[2]) / 2)), "px_normalized"
    if pred == "SBetween":
        b, a, c = p
        t = float(np.dot(b - a, c - a) / np.dot(c - a, c - a))
        return float(
            np.linalg.norm(b - (a + np.clip(t, 0, 1) * (c - a)))
        ), "px_normalized"
    raise ValueError("unsupported predicate")


def degeneracy(pred, p, args):
    if REGISTRY[pred]["degeneracy"] == "none":
        return None
    distances = [float(np.linalg.norm(a - b)) for a, b in combinations(p, 2)]
    if len(set(args)) < len(args) or min(distances) == 0:
        return "degenerate"
    if pred == "Concyclic":
        areas = [height(np.asarray(t)) for t in combinations(p, 3)]
        if min(areas) == 0:
            return "degenerate"
        distances += areas
    return "near_degenerate" if min(distances) < NEAR else None


def measure(proposition, coordinates, *, width, height, tolerance):
    prop = canonical_proposition(proposition)
    if any(
        type(v) not in (int, float) or not math.isfinite(v) or v <= 0
        for v in (width, height)
    ):
        raise ValueError("finite positive image dimensions required")
    if (
        type(tolerance) not in (int, float)
        or not math.isfinite(tolerance)
        or tolerance < 0
    ):
        raise ValueError("finite nonnegative fixture tolerance required")
    if prop["pred"] in {"Distinct", "NotCollinear"} and tolerance != 0:
        raise ValueError("nondegeneracy violation indicators require tolerance zero")
    result = {
        "proposition": prop,
        "method": "coordinate_consistency",
        "kernel": f"numpy:{np.__version__}:{VERSION}",
        "residual": None,
        "residual_unit": None,
        "tolerance": tolerance,
        "uncertainty": None,
        "normalization": "pixel coordinates / hypot(image width,image height)",
        "outcome": "unmeasurable",
    }
    try:
        p = np.asarray([coordinates[name] for name in prop["args"]], dtype=float)
    except (KeyError, ValueError, TypeError):
        return result
    if p.shape != (len(prop["args"]), 2) or not np.isfinite(p).all():
        return result
    p = p / math.hypot(width, height)
    state = degeneracy(prop["pred"], p, prop["args"])
    if state == "degenerate":
        return {**result, "outcome": state}
    value, unit = residual(prop["pred"], p)
    if not math.isfinite(value):
        return result
    return {
        **result,
        "residual": float(value),
        "residual_unit": unit,
        "outcome": state or ("consistent" if value <= tolerance else "inconsistent"),
    }
