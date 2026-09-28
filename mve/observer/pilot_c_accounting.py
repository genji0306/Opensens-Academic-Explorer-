"""Replay committed receipts once: WP-0b + WO-6 + WO-6b, no account lookup."""

import hashlib
import json
from mve.observer import pilot_b_accounting as previous, pilot_transport as transport
from mve.observer import pilot_inputs as inputs
from mve.observer.card import digest
from mve.observer.refusals import guarded, require
from mve.preflight.probe_live_response import inspect_live
from mve.preflight.probe_live_transport import LiveReply
from mve.pricing import normalize_prices
from mve.preflight.probe_live import price_table
from mve.reporting.ledger import merge_attempts, summarize_budget

ROOT = previous.ROOT
EVIDENCE = ROOT / "docs/mve/reviews/wo6b-live"
PIN = ROOT / "mve/observer/config/wo6c_reconciliation.json"


def build():
    prior = previous.reconcile()
    ledger = json.loads((EVIDENCE / "ledger.json").read_text())
    plan = json.loads((EVIDENCE / "design.json").read_text())
    jobs = {j["id"]: j for j in plan["jobs"]}
    require(len(ledger["attempts"]) == 24 and not ledger["frozen"], "reconciliation")
    sources = dict(prior["sources"])
    for name in ("ledger.json", "design.json"):
        sources[(EVIDENCE / name).relative_to(ROOT).as_posix()] = hashlib.sha256(
            (EVIDENCE / name).read_bytes()
        ).hexdigest()
    for row in ledger["attempts"]:
        prefix, jobid, index = row["id"].split(":")
        require(prefix == "wo6b" and index in ("0", "1", "2"), "reconciliation")
        folder = EVIDENCE / "attempts" / jobid / index
        raw, rr, qr = [
            (folder / n).read_bytes()
            for n in ("response.raw", "receipt.json", "request.json")
        ]
        receipt, request = json.loads(rr), json.loads(qr)
        req = transport.request(
            inputs.image_bytes(jobs[jobid]["snapshot_id"]), request["prompt"]
        )
        inspected = inspect_live(
            LiveReply(raw, 200), req, normalize_prices(price_table())
        )
        require(
            req.manifest() == request
            and row["state"] == "settled"
            and row["phase"] == "P1"
            and row["receipt"] == hashlib.sha256(rr).hexdigest()
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
        for name, data in zip(
            ("response.raw", "receipt.json", "request.json"), (raw, rr, qr)
        ):
            sources[(folder / name).relative_to(ROOT).as_posix()] = hashlib.sha256(
                data
            ).hexdigest()
    prior_rows = {
        "frozen": prior["report"]["frozen"],
        "attempts": [
            {k: v for k, v in r.items() if k != "origins"}
            for r in prior["report"]["attempts"]
        ],
    }
    merged = merge_attempts({"prior": prior_rows, "wo6b": ledger})
    campaign = {
        "attempts": [{k: v for k, v in r.items() if k != "origins"} for r in merged]
    }
    # summarize_budget requires the original campaign caps and completeness flags.
    old_campaign = json.loads((ROOT / previous.old.CAMPAIGN).read_text())
    campaign = {**old_campaign, **campaign}
    campaign.pop("exposure_micro_usd", None)
    report = summarize_budget(
        campaign, json.loads((ROOT / (previous.old.LIVE + "ledger.json")).read_text())
    )
    require(
        report["complete"]
        and not report["frozen"]
        and len(report["attempts"]) == 49
        and report["aggregate"]["exposure"]["micro_usd"] == 16339,
        "reconciliation",
    )
    r = dict(
        schema="mve-wo6c-reconciliation-v1",
        report=report,
        prior_micro_usd=16339,
        remaining_micro_usd=19983661,
        sources=sources,
        basis="Committed usage-derived peak exposure; supplied campaign cut, not an invoice or account balance.",
    )
    return {**r, "sha256": digest(r)}


@guarded("reconciliation")
def reconcile():
    r = build()
    require(r == json.loads(PIN.read_text()), "reconciliation")
    return r
