"""Offline prospective block generators. High zeros stay in offset coordinates."""

import gzip
import hashlib
import math
from pathlib import Path
import re

import numpy as np
from scipy.linalg import eigh_tridiagonal
from mve.observer import native_nulls as native

CACHE = Path("~/Developer/Opensens/cache/odlyzko_zeros")
ZERO = ("spectral", "field-dyson")
HEIGHTS = {
    "zeros1.gz": (0, "0"),
    "zeros3": (10**12, "267653395647"),
    "zeros4": (10**21, "144176897509546973000"),
    "zeros5": (10**22, "1370919909931995300000"),
}


def verify_cache(root):
    root = Path(root).expanduser()
    files = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        sha, name = line.split()
        if (
            name not in HEIGHTS
            or hashlib.sha256((root / name).read_bytes()).hexdigest() != sha
        ):
            raise ValueError("cache digest mismatch")
        files[name] = sha
    return {
        "files": files,
        "sums_sha256": hashlib.sha256((root / "SHA256SUMS").read_bytes()).hexdigest(),
        "provenance_sha256": hashlib.sha256(
            (root / "PROVENANCE.txt").read_bytes()
        ).hexdigest(),
        "provenance": (root / "PROVENANCE.txt").read_text().strip(),
    }


def read_zeros(root, name):
    raw = (Path(root).expanduser() / name).read_bytes()
    text = (gzip.decompress(raw) if name.endswith(".gz") else raw).decode()
    return np.array(
        [float(x) for x in text.splitlines() if re.fullmatch(r"\s*\d+\.\d+\s*", x)]
    )


def primes(start, stop):
    mask = np.ones(stop - start, dtype=bool)
    for p in range(2, math.isqrt(stop - 1) + 1):
        # A small local sieve avoids external tables and downloads.
        if all(p % d for d in range(2, math.isqrt(p) + 1)):
            first = max(p * p, ((start + p - 1) // p) * p)
            mask[first - start :: p] = False
    return np.arange(start, stop)[mask]


def sample(generator, module, n, seed, start=200001, stop=240001):
    rng = np.random.default_rng(seed)
    if generator in ("GUE", "GOE"):
        beta, dim = (
            (2 if generator == "GUE" else 1),
            (64 if module == "spectral" else 200),
        )
        chunks = []
        width = math.ceil(0.8 * dim) - math.floor(0.2 * dim) - 1
        for _ in range(math.ceil(n / width)):
            eig = eigh_tridiagonal(
                rng.normal(size=dim) * math.sqrt(2 / beta),
                np.sqrt(rng.chisquare(beta * np.arange(dim - 1, 0, -1)) / beta),
                eigvals_only=True,
            )
            bulk = native.unfold(eig[math.floor(0.2 * dim) : math.ceil(0.8 * dim)], dim)
            chunks.extend(np.diff(bulk))
        x = np.array(chunks[:n])
        return x / x.mean()
    if generator == "Poisson":
        x = rng.exponential(size=n)
        return x / x.mean()
    if generator == "primes":
        x = primes(start, stop)[: n + 1]
    elif generator in ("random-prime", "Cramer"):
        # Existing native Bernoulli 1/log(integer), same Mulberry draw rule.
        # First n+1 arrivals in the reserved interval, identically for real/null.
        integers = np.arange(start, stop)
        x = integers[
            native.Mulberry(seed).uniform(len(integers)) < 1 / np.log(integers)
        ][: n + 1]
    elif generator == "shuffled-index":
        # Permute integer site membership: uniform fixed-count subset. Sorting
        # merely restores index order; this is not shuffling an unchanged gap list.
        x = np.sort(rng.choice(np.arange(start, stop), n + 1, replace=False))
    else:
        raise ValueError("unknown block generator")
    if len(x) != n + 1:
        raise ValueError("reserved interval has insufficient arrivals")
    return x


def require_purpose(block, purpose):
    if purpose not in ("capture", "observer", "tuning", "analysis"):
        raise ValueError("invalid numeric purpose")
    if block["partition"] == "R" and purpose != "capture":
        raise ValueError("replication numeric materialization is capture-only")


def numeric(block, cache=None, *, purpose):
    require_purpose(block, purpose)
    source = block["source"]
    if block["generator"] == "Odlyzko":
        offsets = read_zeros(cache or CACHE, source["file"])[
            source["start"] : source["stop"]
        ]
        if len(offsets) != block["n"] + 1 or np.any(np.diff(offsets) <= 0):
            raise ValueError("invalid zero interval")
        # At huge heights compute log(height)+log1p(offset/height), never add
        # the offset to a float height before differencing adjacent ordinates.
        height = float(source["height_offset"])
        mid = (offsets[:-1] + offsets[1:]) / 2
        logs = (
            np.log(mid / (2 * np.pi))
            if not height
            else math.log(height / (2 * np.pi)) + np.log1p(mid / height)
        )
        gaps = np.diff(offsets) * logs / (2 * np.pi)
        gaps /= gaps.mean()
        indices = None
    else:
        values = sample(
            block["generator"],
            block["module"],
            block["n"],
            block["seed"],
            source["start"],
            source["stop"],
        )
        indices = None if block["module"] in ZERO else values
        gaps = (
            values
            if indices is None
            else np.diff(values) / np.log((values[:-1] + values[1:]) / 2)
        )
        gaps = gaps / gaps.mean()
    if block["module"] == "spectral":
        drawn = gaps.tolist()
    elif block["module"] == "field-dyson":
        drawn = [np.r_[0, np.cumsum(gaps)].tolist()]
    else:
        drawn = (indices - source["start"] + 1).tolist()
    return {
        "values": drawn,
        "source_indices": None if indices is None else indices.tolist(),
        "source_gaps": gaps.tolist(),
        "seed": block["seed"],
        "source": block["generator"],
        "index_origin": source["start"] if indices is not None else None,
        "extent": 40000 if indices is not None else None,
    }
