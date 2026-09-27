"""Execute the pinned vision runner with fake responses; never uses HTTP."""

import argparse
import asyncio
import datetime as dt
import importlib
import inspect
import json
from pathlib import Path
import sys
import tempfile


def fixture_manifest(image):
    prices = {"input_cache_hit": 0.01, "input_cache_miss": 0.15, "output": 0.6}
    return {
        "provider": "deepseek",
        "run_cap_usd": 0.05,
        "wave_tag": "probe",
        "cell": {
            "model": "deepseek-flash",
            "cap_usd": 0.04,
            "max_tokens": 2048,
            "thinking": False,
        },
        "price_usd_per_1m": {
            "models": {"deepseek-flash": {"peak": prices, "offpeak": prices}}
        },
        "tasks": [
            {
                "id": str(i),
                "title": "fixture",
                "brief": "observe",
                "images": [str(image)],
            }
            for i in range(2)
        ],
    }


async def exercise(module, fleet):
    image = fleet / "fixture.png"
    image.write_bytes(b"fake-image-for-transport-contract")
    manifest = fixture_manifest(image)
    calls = []

    async def fake(payload):
        calls.append(payload)
        await asyncio.sleep(0.01)
        return {
            "choices": [
                {
                    "message": {"content": '{"outcome":"observation"}'},
                    "finish_reason": "stop",
                }
            ]
        }

    original_rate = module.W.rate_in_force
    try:
        module.W.rate_in_force = lambda when: "peak"
        await module.run_all(
            argparse.Namespace(concurrency=2, only=""), manifest, fleet, fake
        )
    finally:
        module.W.rate_in_force = original_rate
    rows = [
        json.loads(line) for line in (fleet / "ledger.jsonl").read_text().splitlines()
    ]
    return {
        "fake_calls_during_peak": len(calls),
        "cap": 0.05,
        "accounted_cost": sum(row["cost_usd"] for row in rows),
        "raw_responses_retained": len(list((fleet / "cells").glob("*.raw.json"))),
        "inflight_reservations_enforced": sum(row["cost_usd"] for row in rows) <= 0.05,
        "peak_refused": not calls,
    }


def main():
    sys.path.insert(0, sys.argv[1])
    module = importlib.import_module("rh_deepseek_vision_cell")
    window = {
        stamp: module.W.rate_in_force(dt.datetime.fromisoformat(stamp))
        for stamp in (
            "2026-09-28T00:59:00+00:00",
            "2026-09-28T01:00:00+00:00",
            "2026-09-28T04:00:00+00:00",
            "2026-09-27T02:00:00+00:00",
        )
    }
    with tempfile.TemporaryDirectory() as folder:
        result = asyncio.run(exercise(module, Path(folder)))
    result.update(
        callable=str(inspect.signature(module.run_task)),
        window=window,
        image_limits="not runtime validated by image_block; 1024-token estimate only",
        retries="at most two attempts; HTTP 400 thinking fallback",
    )
    print(json.dumps(result, indent=2))
    return (
        0 if result["inflight_reservations_enforced"] and result["peak_refused"] else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
