"""Two independent replay calls, each traversing the merged WP-0b dispatch boundary."""

from dataclasses import dataclass
import json
from pathlib import Path
from mve.preflight.probe import dispatch_fixture, settle, write_json, usd, utc_now
from mve.record import Record
from mve.preflight.probe_contract import ProbeRefused
from mve.perceiver.contract import (
    MODEL,
    CONTRACT,
    CONTRACT_SHA,
    ImageInput,
    validate_options,
)
from mve.perceiver.parsing import parse
from mve.perceiver.alignment import align
from mve.perceiver.records import ingested, build_record

RETRYABLE = {
    "malformed",
    "truncated",
    "timeout",
    "transport_error",
    "out_of_image",
    "missing_entities",
}


@dataclass(frozen=True)
class PerceptionResult:
    record: Record | None
    _report: str

    def report(self):
        return json.loads(self._report)


def attempt(ledger, request, transport, *, folder, ident, phase, clock, size):
    price, ceiling, outcome = dispatch_fixture(
        ledger,
        request,
        output=folder,
        transport=transport,
        attempt=ident,
        phase=phase,
        wave="wp3:simulated",
        clock=clock,
    )
    parsed = None
    if outcome["status"] == "ok":
        parsed = parse((folder / "response.raw").read_bytes(), *size)
        outcome["status"] = parsed["status"]
    receipt = {
        "schema": "mve-perceiver-attempt-v1",
        "cost_basis": "simulated_replay_metadata",
        "mode": "offline_fixture",
        "hosted_calls": 0,
        "actual_api_cost_usd": "0",
        "attempt": ident,
        "phase": phase,
        "reserved_micro_usd": ceiling,
        "price": price,
        "window_policy": ledger.snapshot()["configuration"]["window"],
        "contract_sha256": CONTRACT_SHA,
        "request": request.manifest(),
        **outcome,
    }
    receipt_sha = write_json(folder / "receipt.json", receipt)
    settle(ledger, ident, outcome, receipt_sha)
    return {**receipt, "receipt_sha256": receipt_sha, "path": folder.name}, parsed


def calls(ledger, request, replay, root, nonce, phase, retries, clock, size):
    attempts, selected, contents = [], [], []
    for call in (1, 2):
        for retry in range(retries + 1):
            name = f"call{call}-attempt{retry+1}"
            outcome, parsed = attempt(
                ledger,
                request,
                replay.transport(len(attempts)),
                folder=root / name,
                ident=f"wp3:{nonce}:{name}",
                phase=phase,
                clock=clock,
                size=size,
            )
            attempts.append(outcome)
            if ledger.snapshot()["frozen"] or outcome["status"] not in RETRYABLE:
                break
        selected.append(outcome)
        contents.append(parsed)
        if ledger.snapshot()["frozen"]:
            break
    return attempts, selected, contents


def report_cost(attempts):
    billed = [a["billed_micro_usd"] for a in attempts]
    known = sum(x for x in billed if x is not None)
    return {
        "cost_basis": "simulated_replay_metadata",
        "actual_api_cost_usd": "0",
        "hosted_calls": 0,
        "simulated_cost_usd": usd(known)
        if all(x is not None for x in billed)
        else None,
        "known_simulated_cost_usd": usd(known),
        "unknown_billing_attempts": sum(x is None for x in billed),
    }


def perceive(
    ledger,
    image,
    *,
    replay,
    output,
    nonce,
    phase="P1",
    retries=2,
    model=MODEL,
    clock=utc_now,
    code_sha="0" * 40,
):
    if type(image) is not ImageInput:
        raise ProbeRefused("only the immutable ImageInput is accepted")
    validate_options(replay, nonce, phase, retries, code_sha)
    request = image.request(model)
    base = ingested(image, nonce, code_sha, utc_now().isoformat())
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "contract.json", CONTRACT)
    attempts, selected, contents = calls(
        ledger, request, replay, root, nonce, phase, retries, clock, image.size()
    )
    record, alignment = None, None
    if len(selected) == 2 and all(s["status"] == "ok" for s in selected):
        alignment = align(
            contents[0]["entities"], contents[1]["entities"], *image.size()
        )
        record = build_record(base, contents, alignment, selected)
        with (root / "record.json").open("x") as stream:
            stream.write(record.to_json() + "\n")
    report = {
        "schema": "mve-perceiver-receipt-v1",
        "mode": "offline_fixture",
        "status": "complete" if record else "incomplete",
        "contract_sha256": CONTRACT_SHA,
        "image_sha256": request.manifest()["image_sha256"],
        "request_nonce": nonce,
        "calls": selected,
        "attempts": attempts,
        "alignment": alignment,
        "record_id": record.to_dict()["record_id"] if record else None,
        **report_cost(attempts),
    }
    write_json(root / "receipt.json", report)
    return PerceptionResult(record, json.dumps(report, sort_keys=True, allow_nan=False))
