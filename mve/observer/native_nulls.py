"""NumPy/SciPy ports of the pinned WO-1 controls, including RNG draw order.

Source algorithms: atlas 97b1e48, vendor/zeta-explorer/dist/{research-math,
field-dyson-math,random-controls-math,prime-sphere-math}.js. No JS runtime needed.
SciPy's tridiagonal eigensolver replaces 58-step Sturm bisection; fixtures verify
all exported values, not just marginal distributions.
"""

import math
import numpy as np
from scipy.linalg import eigh_tridiagonal
from mve.observer import pilot_inputs as inputs
import json


class Mulberry:
    def __init__(self, seed):
        self.seed = seed & 0xFFFFFFFF

    def uniform(self, count):
        t = (np.arange(1, count + 1, dtype=np.uint64) * 0x6D2B79F5 + self.seed).astype(
            np.uint32
        )
        self.seed = (self.seed + count * 0x6D2B79F5) & 0xFFFFFFFF
        t = (t ^ (t >> 15)) * (t | 1)
        t ^= t + ((t ^ (t >> 7)) * (t | 61))
        return (t ^ (t >> 14)).astype(float) / 4294967296

    def normal(self, count, floor):
        u = self.uniform(2 * count).reshape(-1, 2)
        return np.sqrt(-2 * np.log(np.maximum(u[:, 0], floor))) * np.cos(
            2 * np.pi * u[:, 1]
        )


def unfold(eigen, n):
    q = np.clip(eigen / (2 * math.sqrt(n)), -1, 1)
    return n * (0.5 + (np.arcsin(q) + q * np.sqrt(1 - q * q)) / np.pi)


def matrix_segments(module, seed):
    n = 64 if module == "spectral" else 200
    rng = Mulberry(seed)
    out = []
    for _ in range(8):
        diag = rng.normal(n, 1e-15 if module == "spectral" else 1e-300)
        sizes = np.arange(n - 1, 0, -1)
        starts = np.r_[0, np.cumsum(sizes)[:-1]]
        if module == "spectral":
            draws = -np.log(np.maximum(rng.uniform(int(sizes.sum())), 1e-15))
            off = np.sqrt(np.add.reduceat(draws, starts))
        else:
            draws = rng.normal(int(2 * sizes.sum()), 1e-300) ** 2
            off = np.sqrt(np.add.reduceat(draws, 2 * starts) / 2)
        eigen = eigh_tridiagonal(diag, off, eigvals_only=True)
        out.append(unfold(eigen[math.floor(n * 0.2) : math.ceil(n * 0.8)], n))
    return out


def snapshot(module, seed):
    if module in ("spectral", "field-dyson"):
        segments = matrix_segments(module, seed)
        if module == "field-dyson":
            return np.asarray(segments)
        gaps = np.concatenate([np.diff(s) for s in segments])
        return (gaps / gaps.mean())[:89]
    n = 30000 if module == "polar-ulam" else 100000
    first = 1 if module == "polar-ulam" else 3
    values = np.arange(first, n + 1)
    draws = Mulberry(seed).uniform(len(values))
    mask = values >= 3
    return values[mask][draws[mask] < 1 / np.log(values[mask])]


def gaps(module, values):
    if module == "field-dyson":
        sample = np.concatenate([np.diff(s) / np.diff(s).mean() for s in values])
    elif module == "spectral":
        sample = np.asarray(values, dtype=float)
    else:
        v = np.asarray(values, dtype=float)
        # Index spacings unfolded by local Cramer intensity; NOT pixel NN distances.
        sample = np.diff(v) / np.log((v[:-1] + v[1:]) / 2)
    return sample / sample.mean()


def data(job):
    e = next(
        e
        for e in inputs.manifest()["snapshots"]
        if e["snapshot_id"] == job["source_id"]
    )
    ref = e["data_ref"]
    raw = (inputs.INPUTS / ref["path"]).read_bytes()
    import hashlib

    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("source hash mismatch")
    return gaps(job["module"], json.loads(raw)["values"]), ref["sha256"]


def sample_native(module, count, rng):
    chunks, have = [], 0
    while have < count:
        x = gaps(module, snapshot(module, int(rng.integers(0, 2**32))))
        chunks.append(x)
        have += len(x)
    return np.concatenate(chunks)[:count]


def sample_gue(count, rng):
    """Independent GUE(64) bulk spectra, unfolded; joins never create gaps."""
    out = []
    for _ in range(math.ceil(count / 39)):
        eigen = eigh_tridiagonal(
            rng.normal(size=64),
            np.sqrt(rng.gamma(np.arange(63, 0, -1))),
            eigvals_only=True,
        )
        out.append(np.diff(unfold(eigen[12:52], 64)))
    return np.concatenate(out)[:count]
