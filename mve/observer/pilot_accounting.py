"""Pinned campaign cut, reconciled from WP-0b raw usage with WP-9b deduplication."""

import hashlib
import json
from pathlib import Path
from mve.observer import storage
from mve.observer.card import digest
from mve.observer.design import require
from mve.preflight.probe_live import live_request, price_table
from mve.preflight.probe_live_response import inspect_live
from mve.preflight.probe_live_transport import LiveReply
from mve.pricing import normalize_prices
from mve.reporting.ledger import summarize_budget, merge_attempts

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = "mve/observer/config/wo6_campaign.json"
LIVE = "docs/mve/reviews/wp0b-live/"
PIN = "mve/observer/config/wo6_reconciliation.json"


def build_reconciliation():
    paths = [
        CAMPAIGN,
        LIVE + "ledger.json",
        LIVE + "receipt.json",
        LIVE + "response.raw",
    ]
    raw = {p: (ROOT / p).read_bytes() for p in paths}
    campaign, live = (json.loads(raw[p]) for p in paths[:2])
    receipt = json.loads(raw[paths[2]])
    observation = inspect_live(
        LiveReply(raw[paths[3]], 200), live_request(), normalize_prices(price_table())
    )
    report = summarize_budget(campaign, live)
    require(
        observation["derived_micro_usd"] == 268 and observation["status"] == "ok",
        "WP-0b usage reconciliation failed",
    )
    require(
        len(report["attempts"]) == 1
        and report["attempts"][0]["actual"] == 268
        and report["attempts"][0]["receipt"]
        == hashlib.sha256(raw[paths[2]]).hexdigest()
        and receipt["observation"]["raw_sha256"]
        == hashlib.sha256(raw[paths[3]]).hexdigest()
        and report["complete"]
        and not report["frozen"]
        and all(a["state"] == "settled" for a in report["attempts"]),
        "campaign reconciliation failed",
    )
    result = dict(
        schema="mve-wo6-reconciliation-v1",
        report=report,
        remaining_micro_usd=report["aggregate"]["remaining"]["micro_usd"],
        sources={p: hashlib.sha256(b).hexdigest() for p, b in raw.items()},
        basis="Pinned campaign cut: WP-0b is the sole prior hosted attempt. Usage-derived peak estimate, not a vendor invoice. New campaign spending requires a new reviewed cut.",
    )
    return {**result, "sha256": digest(result)}


def verify_reconciliation(receipt):
    require(
        receipt == build_reconciliation() == json.loads((ROOT / PIN).read_text()),
        "aggregate reconciliation pin mismatch",
    )
    return receipt


def reconcile_campaign():
    receipt = verify_reconciliation(json.loads((ROOT / PIN).read_text()))
    path = storage.GENERATED / "wo6-pilot" / "reconciliation.json"
    dest = storage.local(path)
    if dest.exists():
        require(
            json.loads(dest.read_text()) == receipt, "stored reconciliation mismatch"
        )
    else:
        storage.write(path, receipt)
    return receipt


def combined_report(snapshot):
    campaign = json.loads((ROOT / CAMPAIGN).read_text())
    live = json.loads((ROOT / (LIVE + "ledger.json")).read_text())
    rows = merge_attempts({"campaign": campaign, "pilot": snapshot})
    campaign["attempts"] = [
        {k: v for k, v in r.items() if k != "origins"} for r in rows
    ]
    campaign.pop("exposure_micro_usd", None)
    campaign["frozen"] |= snapshot["frozen"]
    campaign["events"] += snapshot["events"]
    return summarize_budget(campaign, live)
