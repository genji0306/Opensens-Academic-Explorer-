"""Loader for Odlyzko's zeros1 dataset (first 100K non-trivial zeros).

The LMFDB bulk-download page links to Odlyzko's tables; the same data is
available directly at zeros1 in a simple text-per-line format (leading
whitespace + gamma_n to ~9 decimals).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np

from .config import ZEROS1_FILE, ZEROS1_URL, ensure_dirs
from .schemas import ZeroDataset


def ensure_downloaded(force: bool = False) -> Path:
    ensure_dirs()
    if ZEROS1_FILE.exists() and not force:
        return ZEROS1_FILE
    # User-Agent required by some mirrors; plain urllib is enough here.
    req = urllib.request.Request(
        ZEROS1_URL,
        headers={"User-Agent": "Opensens-Academic-Explorer/0.1"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        ZEROS1_FILE.write_bytes(resp.read())
    return ZEROS1_FILE


def load(n_zeros: int = 10_000, force_download: bool = False) -> ZeroDataset:
    """Return the first ``n_zeros`` non-trivial zeros as a ZeroDataset."""
    path = ensure_downloaded(force=force_download)
    values: list[float] = []
    with path.open() as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            values.append(float(s))
            if len(values) >= n_zeros:
                break
    if len(values) < n_zeros:
        raise ValueError(
            f"Requested {n_zeros} zeros but only {len(values)} available in {path}"
        )
    gamma = np.asarray(values, dtype=np.float64)
    n = np.arange(1, len(gamma) + 1, dtype=np.int64)
    return ZeroDataset(
        n=n,
        gamma=gamma,
        source="odlyzko_zeros1",
        precision=3e-9,
    )
