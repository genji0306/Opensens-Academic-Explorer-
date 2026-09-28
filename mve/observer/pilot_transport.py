"""WO-4 live attempt adapter: reviewed WP-0b exchange and durable WP-9a P1 intent."""

import json
import time
from mve.observer import storage
from mve.observer.refusals import require, guarded, boundary
from mve.budget import checked_time
from mve.observer.pilot_inputs import INPUT_TOKENS, OUTPUT_TOKENS, CALL_CAP
from mve.preflight.probe import prepare_dispatch, verified_ceiling, write_json, usd
from mve.preflight.probe_contract import ProbeRequest, ProbeReply
from mve.preflight.probe_fixtures import FakeTransport
from mve.preflight import probe_live_transport as wire
from mve.preflight.probe_live_response import receive_live


@guarded("input_contract")
def request(png, prompt):
    require(len(prompt.encode()) <= 2048, "input_contract")
    r = ProbeRequest("deepseek-flash", prompt, png, INPUT_TOKENS, OUTPUT_TOKENS, 30)
    r.validate()
    return r


@guarded("budget_cap")
def dispatch(ledger, req, *, output, attempt, clock, live, fake_raw=None):
    require(len(ledger.snapshot()["attempts"]) < CALL_CAP, "call_cap")
    with boundary("storage"):
        require(
            storage.local(output.relative_to(storage.WORKTREE)) == output, "storage"
        )
    storage.disk_guard(storage.local(storage.GENERATED), 3 * 1024**2)
    req.validate()
    price, ceiling = verified_ceiling(ledger, req)

    def prepare():
        if live:
            return wire.prepare_call(req)
        require(type(fake_raw) is bytes, "input_contract")
        fake = FakeTransport(ProbeReply(fake_raw))
        return lambda: wire.LiveReply(fake.send(req).raw, 200)

    def safe_clock():
        with boundary("peak_window"):
            now = clock()
            checked_time(now)
            return now

    send = prepare_dispatch(
        ledger,
        req,
        output,
        safe_clock,
        attempt=attempt,
        phase="P1",
        wave="wo6:pilot",
        prepare=prepare,
    )
    outcome = receive_live(send, req, {req.model: price}, output, time.monotonic)
    del send
    receipt = dict(
        schema="mve-wo6-attempt-v1",
        mode="live" if live else "offline_fixture",
        attempt=attempt,
        phase="P1",
        reserved_micro_usd=ceiling,
        price=price,
        **outcome,
    )
    sha = write_json(output / "receipt.json", receipt)
    actual = outcome["derived_micro_usd"]
    ledger.reconcile(
        attempt, usd(ceiling if actual is None else actual), receipt_sha256=sha
    )
    if outcome["status"] in {"usage_bound_exceeded", "model_mismatch"}:
        ledger.stop("mechanical_failure")
    return receipt


def content(out, receipt):
    if receipt["status"] != "ok":
        return None
    return json.loads(
        json.loads((out / "response.raw").read_bytes())["choices"][0]["message"][
            "content"
        ]
    )
