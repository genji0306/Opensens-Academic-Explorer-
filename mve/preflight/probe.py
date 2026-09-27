"""WP-0b refusal boundary. Hosted mode is disabled pending Opus review and owner go."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from mve.budget import WINDOW_POLICY
from mve.pricing import token_ceiling, PriceError
from mve.preflight.probe_contract import ProbeRequest, ProbeRefused, inspect_reply
from mve.preflight.probe_fixtures import FakeTransport

PROBE_ID = "wp0b:single-model-probe"
PROBE_CAP_MICRO_USD = 50_000


def utc_now():
    return datetime.now(timezone.utc)


def usd(amount):
    return f"{amount // 1_000_000}.{amount % 1_000_000:06d}"


def write_json(path, data):
    payload = (
        json.dumps(data, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    )
    with Path(path).open("xb") as stream:
        stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


def verified_ceiling(ledger, request):
    prices = ledger.snapshot()["configuration"]["prices"]
    if request.model not in prices or prices[request.model]["verified"] is not True:
        raise PriceError("probe refuses missing or unverified price")
    ceiling = token_ceiling(
        prices,
        request.model,
        input_tokens=request.max_input_tokens,
        output_tokens=request.max_output_tokens,
    )
    if not 0 < ceiling <= PROBE_CAP_MICRO_USD:
        raise ProbeRefused("positive probe reservation must not exceed USD 0.05")
    return prices[request.model], ceiling


def prepare_dispatch(
    ledger, request, output, clock, *, attempt=PROBE_ID, phase="P0", wave="wp0b"
):
    ledger.reserve_tokens(
        attempt,
        phase,
        request.model,
        input_tokens=request.max_input_tokens,
        output_tokens=request.max_output_tokens,
        wave=wave,
        when=clock(),
    )
    try:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "request.json", request.manifest())
        (output / "image.png").write_bytes(request.image)
        ledger.mark_dispatched(attempt, when=clock())
    except Exception:
        # The ledger itself refuses cancellation if dispatch was durably committed.
        ledger.cancel_unsent(attempt)
        raise


def receive(transport, request, output, timer):
    started = timer()
    try:
        reply = transport.send(request)
    except (TimeoutError, OSError) as exc:
        return {
            "status": "timeout" if isinstance(exc, TimeoutError) else "transport_error",
            "returned_model": None,
            "usage": None,
            "billed_micro_usd": None,
            "raw_sha256": None,
            "latency_s": max(0, timer() - started),
        }
    latency = max(0, timer() - started)
    with (output / "response.raw").open("xb") as stream:
        stream.write(reply.raw)
    return {
        **inspect_reply(reply, request),
        "raw_sha256": hashlib.sha256(reply.raw).hexdigest(),
        "latency_s": latency,
    }


def finish(ledger, request, output, price, ceiling, observation):
    receipt = {
        "schema": "mve-probe-receipt-v1",
        "mode": "offline_fixture",
        "attempt": PROBE_ID,
        "phase": "P0",
        "requested_model": request.model,
        "price": price,
        "window_policy": WINDOW_POLICY,
        "reserved_micro_usd": ceiling,
        "request": request.manifest(),
        "observation": observation,
        "hosted_calls": 0,
    }
    receipt_sha = write_json(output / "receipt.json", receipt)
    settle(ledger, PROBE_ID, observation, receipt_sha)
    result = {
        "schema": "mve-probe-cost-model-v1",
        "mode": "offline_fixture",
        "hosted_calls": 0,
        "actual_api_cost_usd": "0",
        "receipt_sha256": receipt_sha,
        "fixture_result": observation,
        "ledger": ledger.snapshot(),
        "live_cost_model": {
            "status": "pending reviewed refusal path and owner go",
            "model_id": None,
            "image_support": "unverified",
            "tokens_per_image": None,
            "latency_s": None,
            "price_verified": False,
            "api_cost_usd": None,
        },
    }
    write_json(output / "cost_model.json", result)
    return result


def run_probe(
    ledger,
    request: ProbeRequest,
    *,
    output,
    transport,
    mode="hosted",
    clock=utc_now,
    timer=time.monotonic,
):
    price, ceiling, observation = dispatch_fixture(
        ledger,
        request,
        output=output,
        transport=transport,
        mode=mode,
        attempt=PROBE_ID,
        phase="P0",
        wave="wp0b",
        clock=clock,
        timer=timer,
    )
    return finish(ledger, request, Path(output), price, ceiling, observation)


def settle(ledger, attempt, observation, receipt_sha):
    actual = observation["billed_micro_usd"]
    if actual is not None:
        ledger.reconcile(attempt, usd(actual), receipt_sha256=receipt_sha)
    if observation["status"] in {
        "usage_bound_exceeded",
        "model_mismatch",
        "invalid_billing",
    }:
        ledger.stop("mechanical_failure")


def dispatch_fixture(
    ledger,
    request,
    *,
    output,
    transport,
    attempt,
    phase,
    wave,
    mode="offline_fixture",
    clock=utc_now,
    timer=time.monotonic,
):
    """Shared WP-0b boundary: no transport except the exact local fake."""
    if mode != "offline_fixture":
        raise ProbeRefused("hosted probe disabled pending Opus review and owner go")
    if type(transport) is not FakeTransport:
        raise ProbeRefused("offline fixture mode requires the local FakeTransport")
    if phase not in {"P0", "P1"}:
        raise ProbeRefused("image dispatch requires P0 or P1")
    request.validate()
    price, ceiling = verified_ceiling(ledger, request)
    output = Path(output)
    prepare_dispatch(
        ledger, request, output, clock, attempt=attempt, phase=phase, wave=wave
    )
    observation = receive(transport, request, output, timer)
    return price, ceiling, observation


def main():
    import argparse
    from mve.preflight.probe_offline import run_matrix

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline-fixture", action="store_true")
    args = parser.parse_args()
    if not args.offline_fixture:
        parser.error(
            "hosted probe disabled pending Opus review and owner go; use --offline-fixture"
        )
    report = run_matrix(args.output)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"cases", "source_pins", "artifacts"}
            },
            indent=2,
        )
    )
    return 0 if report["refusal_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
