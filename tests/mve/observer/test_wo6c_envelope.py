"""The WO-6c development register stays disjoint from the live WO-1b manifest.

development_c.py hard-codes WO-1b's seed and interval envelopes; this re-derives
them from the committed manifest so a regenerated manifest cannot outgrow them.
Reads manifest metadata only; no block is materialised.
"""

import json
from pathlib import Path

from mve.observer import development_c as dev

MANIFEST = Path(__file__).resolve().parents[3] / "mve/observer/config/wo1b_manifest.json"
PRIMES = ("polar-ulam", "space-08")


def _manifest():
    return json.loads(MANIFEST.read_text())


def _module(block):
    return block.get("module") or block.get("stratum") or block["cluster"].rsplit("-", 2)[0]


def test_every_wo1b_seed_is_inside_the_hardcoded_envelope():
    m = _manifest()
    seeds = {b["seed"] for b in m["blocks"]} | {m["seed"]}
    assert seeds <= dev.PROSPECTIVE_SEEDS


def test_every_wo1b_zero_interval_is_inside_a_hardcoded_zero_interval():
    for b in _manifest()["blocks"]:
        src = b.get("source", {})
        if "index_start" not in src:
            continue
        # Absolute zero indices, stored as strings; height_offset is a height, not an index.
        lo, hi = int(src["index_start"]), int(src["index_stop_exclusive"])
        assert any(a <= lo and hi <= z for a, z in dev.PROSPECTIVE_ZERO_INTERVALS), b["id"]


def test_every_wo1b_prime_interval_is_inside_the_hardcoded_integer_interval():
    a, z = dev.PROSPECTIVE_INTEGER_INTERVAL
    blocks = [b for b in _manifest()["blocks"] if _module(b) in PRIMES]
    assert blocks
    for b in blocks:
        assert a <= b["source"]["start"] and b["source"]["stop"] <= z, b["id"]
