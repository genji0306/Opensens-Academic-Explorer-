"""Raw-first receipt interpretation; derived amounts are never vendor bills."""

import hashlib
import json

from mve.preflight.probe_contract import response_status, usage_from
from mve.pricing import token_ceiling


def validated_usage(body):
    parsed = usage_from(body)
    usage = body["usage"]
    incoming = parsed["input_tokens"]
    if "total_tokens" in usage:
        counter(usage["total_tokens"], parsed["total_tokens"])
    # Preserve unknown vendor counters, but validate known optional counters.
    for name in (
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "cached_tokens",
        "image_tokens",
    ):
        if name in usage:
            counter(usage[name], incoming)
    for name in ("prompt_tokens_details", "completion_tokens_details"):
        if name in usage:
            if not isinstance(usage[name], dict):
                raise ValueError("invalid token details")
            bound = incoming if name.startswith("prompt") else parsed["output_tokens"]
            for value in usage[name].values():
                counter(value, bound)
    if "prompt_cache_hit_tokens" in usage and "prompt_cache_miss_tokens" in usage:
        if (
            usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
            != incoming
        ):
            raise ValueError("inconsistent cached usage")
    return parsed, usage


def counter(value, bound):
    if type(value) is not int or not 0 <= value <= bound:
        raise ValueError("invalid optional token counter")


def reject_constant(value):
    raise ValueError("nonfinite JSON constant")


def inspect_live(reply, request, prices):
    result = {
        "status": reply.error or "malformed",
        "http_status": reply.http_status,
        "returned_model": None,
        "usage": None,
        "derived_micro_usd": None,
        "cost_basis": "reservation_retained_unknown_cost",
        "image_accepted": None,
        "raw_redacted": reply.raw_redacted,
        "raw_sha256": hashlib.sha256(reply.raw).hexdigest(),
    }
    if reply.http_status is not None and not 200 <= reply.http_status < 300:
        result.update(status="http_error", image_accepted=False)
        return result
    if reply.error:
        return result
    try:
        body = json.loads(reply.raw, parse_constant=reject_constant)
        model = body.get("model")
        result["returned_model"] = model if isinstance(model, str) else None
        result["status"] = "model_mismatch" if model != request.model else "malformed"
        parsed, usage = validated_usage(body)
        result["usage"] = usage
        if model != request.model:
            return result
        result["cost_basis"] = "derived_from_usage"
        result["derived_micro_usd"] = token_ceiling(
            prices,
            request.model,
            input_tokens=parsed["input_tokens"],
            output_tokens=parsed["output_tokens"],
        )
        result["status"] = response_status(body, request)
        # A valid chat response to the image-bearing request establishes API
        # acceptance only, not accurate visual understanding.
        result["image_accepted"] = True if model == request.model else None
        if (
            parsed["input_tokens"] > request.max_input_tokens
            or parsed["output_tokens"] > request.max_output_tokens
        ):
            result["status"] = "usage_bound_exceeded"
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ):
        if result["returned_model"] == request.model and result["usage"] is None:
            result["status"] = "usage_missing"
    return result


def receive_live(send, request, prices, output, timer):
    started = timer()
    reply = send()
    elapsed = max(0, timer() - started)
    with (output / "response.raw").open("xb") as stream:
        stream.write(reply.raw)
    return {**inspect_live(reply, request, prices), "latency_s": elapsed}
