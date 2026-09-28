"""WO-6b campaign cut: WP-0b once plus all 24 committed WO-6 receipts."""

import hashlib
import json
from mve.observer import (
    pilot_accounting as old,
    pilot_inputs as inputs,
    pilot_transport as transport,
)
from mve.observer.card import digest
from mve.observer.refusals import require, guarded
from mve.preflight.probe_live_response import inspect_live
from mve.preflight.probe_live_transport import LiveReply
from mve.pricing import normalize_prices
from mve.preflight.probe_live import price_table
from mve.reporting.ledger import merge_attempts, summarize_budget

ROOT = old.ROOT
EVIDENCE = ROOT / "docs/mve/reviews/wo6-live"
PIN = ROOT / "mve/observer/config/wo6b_reconciliation.json"


def build():
    previous = old.verify_reconciliation(old.build_reconciliation())
    ledger = json.loads((EVIDENCE / "ledger.json").read_text())
    plan = json.loads((EVIDENCE / "design.json").read_text())
    jobs = {j["id"]: j for j in plan["jobs"]}
    require(len(ledger["attempts"]) == 24 and not ledger["frozen"], "reconciliation")
    sources = dict(previous["sources"])
    for path in (EVIDENCE / "ledger.json", EVIDENCE / "design.json"):
        sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    for row in ledger["attempts"]:
        _, jobid, index = row["id"].split(":")
        folder = EVIDENCE / "attempts" / jobid / index
        raw, receipt_raw, request_raw = (
            (folder / name).read_bytes()
            for name in ("response.raw", "receipt.json", "request.json")
        )
        receipt, request = json.loads(receipt_raw), json.loads(request_raw)
        req = transport.request(
            inputs.image_bytes(jobs[jobid]["snapshot_id"]), request["prompt"]
        )
        require(req.manifest() == request, "reconciliation")
        inspected = inspect_live(
            LiveReply(raw, 200), req, normalize_prices(price_table())
        )
        require(
            row["state"] == "settled"
            and row["phase"] == "P1"
            and row["receipt"] == hashlib.sha256(receipt_raw).hexdigest()
            and receipt["attempt"] == row["id"]
            and receipt["price"] == normalize_prices(price_table())[req.model]
            and inspected["status"] == receipt["status"] == "ok"
            and inspected["raw_sha256"] == receipt["raw_sha256"]
            and inspected["usage"] == receipt["usage"]
            and inspected["derived_micro_usd"]
            == receipt["derived_micro_usd"]
            == row["actual"],
            "reconciliation",
        )
        for name, data in [
            ("response.raw", raw),
            ("receipt.json", receipt_raw),
            ("request.json", request_raw),
        ]:
            sources[(folder / name).relative_to(ROOT).as_posix()] = hashlib.sha256(
                data
            ).hexdigest()
    campaign = json.loads((ROOT / old.CAMPAIGN).read_text())
    merged = merge_attempts({"campaign": campaign, "wo6": ledger})
    campaign["attempts"] = [
        {k: v for k, v in r.items() if k != "origins"} for r in merged
    ]
    campaign.pop("exposure_micro_usd", None)
    report = summarize_budget(
        campaign, json.loads((ROOT / (old.LIVE + "ledger.json")).read_text())
    )
    require(
        report["complete"]
        and not report["frozen"]
        and len(report["attempts"]) == 25
        and report["aggregate"]["exposure"]["micro_usd"] == 6895,
        "reconciliation",
    )
    result = dict(
        schema="mve-wo6b-reconciliation-v1",
        report=report,
        prior_micro_usd=6895,
        remaining_micro_usd=19993105,
        sources=sources,
        basis="Pinned supplied campaign cut; usage-derived peak estimate, not invoice or online balance. New spending requires a new review.",
    )
    return {**result, "sha256": digest(result)}


@guarded("reconciliation")
def reconcile():
    result = build()
    require(result == json.loads(PIN.read_text()), "reconciliation")
    return result
