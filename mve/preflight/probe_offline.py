"""Reproducible refusal-path exercise; all prices, clocks, bills and replies are fake."""

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from mve.budget import BudgetLedger, BudgetError
from mve.preflight.probe import run_probe, write_json
from mve.preflight.probe_fixtures import FakeTransport, fixture_reply, fixture_request

EVIDENCE = b"WP-0b synthetic fixture price; NOT vendor verification or authorization.\n"
OFF = datetime(2026, 9, 28, 0, 59, tzinfo=timezone.utc)
PEAK = datetime(2026, 9, 28, 1, tzinfo=timezone.utc)


def price_fixture(verified):
    return {
        "deepseek-fixture": {
            "input_per_million": "10",
            "output_per_million": "10",
            "source_sha256": hashlib.sha256(EVIDENCE).hexdigest(),
            "verified": verified,
        }
    }


def exercise_case(root, name):
    root.mkdir()
    prices = price_fixture(name != "unverified_price")
    book = BudgetLedger(root / "campaign.sqlite", price_table=prices)
    request = fixture_request()
    fake = FakeTransport(
        fixture_reply(), fault="timeout" if name == "timeout" else None
    )
    times = iter(
        [PEAK, PEAK]
        if name == "peak"
        else [OFF, PEAK]
        if name == "boundary"
        else [OFF, OFF]
    )
    if name == "inflight":
        book.reserve("prior", "P0", "1.99", wave="fixture", when=OFF)
    if name == "probe_cap":
        request = replace(request, max_input_tokens=5001)
    elapsed = iter([0.0, 0.125])
    try:
        result = run_probe(
            book,
            request,
            output=root / "probe",
            transport=fake,
            mode="offline_fixture",
            clock=lambda: next(times),
            timer=lambda: next(elapsed),
        )
        status, reason = result["fixture_result"]["status"], None
    except BudgetError as exc:
        status, reason = "refused", str(exc)
    return {
        "case": name,
        "status": status,
        "reason": reason,
        "fake_calls": fake.calls,
        "snapshot": book.snapshot(),
    }


def run_matrix(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "price-evidence.fixture.txt").write_bytes(EVIDENCE)
    cases = [
        exercise_case(output / name, name)
        for name in (
            "unverified_price",
            "peak",
            "boundary",
            "inflight",
            "probe_cap",
            "success",
            "timeout",
        )
    ]
    accepted = all(
        row["fake_calls"] == (1 if row["case"] in {"success", "timeout"} else 0)
        for row in cases
    )
    report = {
        "schema": "mve-probe-offline-review-v1",
        "mode": "offline_fixture",
        "fixture_inputs_only": True,
        "latency_is_simulated": True,
        "hosted_calls": 0,
        "actual_api_cost_usd": "0",
        "cases": cases,
        "refusal_checks_passed": accepted,
        "live_probe_status": "disabled: requires Opus refusal-path review and owner go",
        "live_price_verified": False,
        "live_model_id": None,
        "live_image_support": "unverified",
        "live_tokens_per_image": None,
        "live_latency_s": None,
        "live_api_cost_usd": None,
    }
    report.update(artifact_pins(output))
    write_json(output / "report.json", report)
    return report


def artifact_pins(output):
    source_root = Path(__file__).resolve().parents[2]
    sources = [
        *Path(__file__).parent.glob("probe*.py"),
        *[
            source_root / "mve" / name
            for name in ("budget.py", "pricing.py", "money.py")
        ],
    ]
    return {
        "source_pins": [
            {
                "path": str(p.relative_to(source_root)),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in sorted(sources)
        ],
        "artifacts": [
            {
                "path": str(p.relative_to(output)),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in sorted(output.rglob("*"))
            if p.is_file() and p.suffix != ".sqlite"
        ],
    }
