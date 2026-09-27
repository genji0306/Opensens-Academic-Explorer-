"""Geometry-only alignment; labels never determine identity or authorise a claim."""

import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

CONTRACT_PATH = Path(__file__).parents[1] / "measurement/perceiver_alignment_v1.json"
CONTRACT_BYTES = CONTRACT_PATH.read_bytes()
CONTRACT = json.loads(CONTRACT_BYTES)
ALIGNMENT_SHA = hashlib.sha256(CONTRACT_BYTES).hexdigest()


def normalized(entity, width, height):
    p, kind = entity["params"], entity["kind"]
    if kind in {"circle", "arc"}:
        return [p[0] / width, p[1] / height, p[2] / math.hypot(width, height)] + [
            x / 360 for x in p[3:]
        ]
    return [x / (width if i % 2 == 0 else height) for i, x in enumerate(p)]


def distance(a, b, width, height):
    if a["kind"] != b["kind"] or len(a["params"]) != len(b["params"]):
        return math.inf
    x, y = normalized(a, width, height), normalized(b, width, height)
    variants = [y]
    if a["kind"] in {"segment", "line"}:
        variants.append(y[2:] + y[:2])
    return min(math.dist(x, v) for v in variants)


def align(left, right, width, height):
    threshold = CONTRACT["threshold"]
    n, m = len(left), len(right)
    # One dummy column per left entity. A dummy costs more than the sum of all
    # admissible distances, so matching cardinality takes precedence over distance.
    dummy = (n + 1) * (threshold + 1)
    costs = np.full((n, m + n), dummy)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            d = distance(a, b, width, height)
            costs[i, j] = d if d <= threshold else dummy * (n + 1)
    rows, cols = linear_sum_assignment(costs)
    ambiguous = [
        (i, j)
        for i, j in zip(rows, cols)
        if j < m
        and costs[i, j] <= threshold
        and (
            sum(abs(costs[i, k] - costs[i, j]) < 1e-12 for k in range(m)) > 1
            or sum(abs(costs[k, j] - costs[i, j]) < 1e-12 for k in range(n)) > 1
        )
    ]
    matches = [
        {"left": left[i]["id"], "right": right[j]["id"], "distance": float(costs[i, j])}
        for i, j in zip(rows, cols)
        if j < m and costs[i, j] <= threshold and (i, j) not in ambiguous
    ]
    matched_left, matched_right = (
        {v["left"] for v in matches},
        {v["right"] for v in matches},
    )
    return {
        "contract_sha256": ALIGNMENT_SHA,
        "matches": matches,
        "ambiguous": [
            {"left": left[i]["id"], "right": right[j]["id"]} for i, j in ambiguous
        ],
        "unmatched_left": [e["id"] for e in left if e["id"] not in matched_left],
        "unmatched_right": [e["id"] for e in right if e["id"] not in matched_right],
        "agreement_is_verification": False,
    }
