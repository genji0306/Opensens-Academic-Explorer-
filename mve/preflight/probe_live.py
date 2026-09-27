"""Owner-approved WP-0b activation; never called by fixtures or the perceiver."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from mve.budget import BudgetLedger, WINDOW_POLICY
from mve.preflight.probe import (
    PROBE_ID,
    prepare_dispatch,
    utc_now,
    usd,
    verified_ceiling,
    write_json,
)
from mve.preflight.probe_contract import ProbeRefused, ProbeRequest
from mve.preflight.probe_live_response import receive_live
from mve.preflight.probe_live_transport import prepare_call

ROOT = Path(__file__).resolve().parents[2]
LIVE_ROOT = ROOT / "mve/generated/wp0b-live"
EVIDENCE = Path(__file__).parent / "evidence"
MODEL = "deepseek-flash"
PROMPT = 'Return only JSON: {"observations":[]}. List visible point labels and geometric relations in this image. No reasoning.'
# A deliberately large allowance for this pinned 288px image, text, and hidden
# overhead. This is an engineering bound, not a verified vendor tokenization rule.
INPUT_ALLOWANCE = 131_072
PRICE_SHA256 = "7e82f84f86abef7ff95eb3a54dc2928e39919b5d2c065b0242f8ac50a2248a4a"
IMAGE_SHA256 = "15f0d4cda4c3677eda6f2e4bce9f1c43ee22ecf77c2dc11ebdb7ee346ad59371"


def require_review(owner_approval, commit):
    if (
        owner_approval != "2026-09-27"
        or not isinstance(commit, str)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
    ):
        raise ProbeRefused(
            "live requires owner approval 2026-09-27 and full reviewed HEAD commit"
        )
    try:
        head = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                timeout=10,
            )
            .stdout.decode()
            .strip()
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            timeout=10,
        ).stdout
    except Exception:
        raise ProbeRefused("cannot verify reviewed HEAD") from None
    if head != commit or dirty:
        raise ProbeRefused("reviewed commit must equal HEAD and worktree must be clean")


def price_table():
    raw = (EVIDENCE / "deepseek-20260927.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != PRICE_SHA256:
        raise ProbeRefused("vendor evidence hash mismatch")
    evidence = json.loads(raw)
    if (
        evidence["price_verified"] is not True
        or evidence["window_verified"] is not True
    ):
        raise ProbeRefused("unverified vendor evidence")
    peak = evidence["prices_usd_per_million"]["peak"]
    return {
        MODEL: {
            "input_per_million": peak["input_cache_miss"],
            "output_per_million": peak["output"],
            "source_sha256": PRICE_SHA256,
            "verified": True,
        }
    }


def open_ledger():
    # Fixed location and caps: no CLI ledger/output override can grant a new shot.
    return BudgetLedger(
        LIVE_ROOT / "campaign.sqlite",
        aggregate="0.05",
        p0="0.05",
        price_table=price_table(),
    )


def live_request():
    image = (EVIDENCE / "wp0b-fit.png").read_bytes()
    provenance = json.loads((EVIDENCE / "wp0b-fit.json").read_bytes())
    if (
        provenance["split"] != "fit"
        or hashlib.sha256(image).hexdigest() != IMAGE_SHA256
        or provenance["image_sha256"] != IMAGE_SHA256
    ):
        raise ProbeRefused("probe requires the pinned WP-2 fit PNG")
    request = ProbeRequest(MODEL, PROMPT, image, INPUT_ALLOWANCE, 512, timeout_s=30)
    request.validate()
    return request


def run_live(*, owner_approval, reviewed_by_opus, clock=utc_now, timer=time.monotonic):
    require_review(owner_approval, reviewed_by_opus)
    request, ledger = live_request(), open_ledger()
    price, ceiling = verified_ceiling(ledger, request)
    output = LIVE_ROOT / "probe"
    send = prepare_dispatch(
        ledger, request, output, clock, prepare=lambda: prepare_call(request)
    )
    observation = receive_live(send, request, {MODEL: price}, output, timer)
    receipt = {
        "schema": "mve-probe-live-receipt-v1",
        "mode": "live",
        "attempt": PROBE_ID,
        "phase": "P0",
        "requested_model": MODEL,
        "request": request.manifest(),
        "owner_approval": owner_approval,
        "reviewed_by_opus": reviewed_by_opus,
        "price": price,
        "price_source": "https://api-docs.deepseek.com/quick_start/pricing",
        "price_fetch_date": "2026-09-27",
        "window_policy": WINDOW_POLICY,
        "window_verified": True,
        "holiday_policy": "no holiday exemption; conservative",
        "reserved_micro_usd": ceiling,
        "observation": observation,
        "cost_policy": "peak cache-miss input and peak output; cache discounts not assumed; derived upper estimate, not vendor-billed",
        "input_allowance": "131072 includes image/text/hidden overhead; engineering allowance, vendor tokenizer unverified",
        "image_source": "WP-2 midpoint_grid seed 0 fit",
        "image_wire_format_previously_verified": False,
        "headers": {"Authorization": "[REDACTED]", "Content-Type": "application/json"},
    }
    receipt_sha = write_json(output / "receipt.json", receipt)
    actual = observation["derived_micro_usd"]
    # Failed attempts settle with a full retained reservation when usage is unknown.
    ledger.reconcile(
        PROBE_ID, usd(ceiling if actual is None else actual), receipt_sha256=receipt_sha
    )
    if observation["status"] in {"usage_bound_exceeded", "model_mismatch"}:
        ledger.stop("mechanical_failure")
    write_json(output / "ledger.json", ledger.snapshot())
    return observation
