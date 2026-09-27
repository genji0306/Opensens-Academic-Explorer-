"""Bounded WP-0b request/reply values; no provider client or network dependency."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import re
from PIL import Image
from mve.money import BudgetError, microdollars


class ProbeRefused(BudgetError):
    pass


@dataclass(frozen=True)
class ProbeRequest:
    model: str
    prompt: str
    image: bytes
    max_input_tokens: int
    max_output_tokens: int
    timeout_s: int = 30

    def validate(self):
        if not isinstance(self.model, str) or not re.fullmatch(
            r"deepseek-[A-Za-z0-9_.-]{1,100}", self.model
        ):
            raise ProbeRefused("explicit DeepSeek model id required")
        if "-pro" in self.model.lower():
            raise ProbeRefused("V4-Pro image requests are refused")
        if (
            not isinstance(self.prompt, str)
            or not 0 < len(self.prompt.encode()) <= 16_384
        ):
            raise ProbeRefused("bounded nonempty prompt required")
        if type(self.image) is not bytes or not 0 < len(self.image) <= 4_194_304:
            raise ProbeRefused("bounded PNG bytes required")
        for value in (self.max_input_tokens, self.max_output_tokens):
            if type(value) is not int or not 0 < value <= 1_000_000_000:
                raise ProbeRefused("positive integer token bounds required")
        if type(self.timeout_s) is not int or not 0 < self.timeout_s <= 60:
            raise ProbeRefused("probe timeout must be 1..60 seconds")
        try:
            with Image.open(BytesIO(self.image)) as image:
                if image.format != "PNG" or max(image.size) > 1024:
                    raise ProbeRefused(
                        "probe fixture must be PNG, at most 1024 by 1024"
                    )
                image.verify()
        except (OSError, ValueError) as exc:
            raise ProbeRefused("invalid bounded PNG") from exc

    def manifest(self):
        return {
            "model": self.model,
            "prompt": self.prompt,
            "image_sha256": hashlib.sha256(self.image).hexdigest(),
            "image_count": 1,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "timeout_s": self.timeout_s,
            "temperature": 0,
            "thinking": False,
            "response_format": "json",
        }


@dataclass(frozen=True)
class ProbeReply:
    raw: bytes
    billed_usd: str | None = None


def usage_from(body):
    usage = body["usage"]
    incoming, outgoing = usage["prompt_tokens"], usage["completion_tokens"]
    if any(
        type(n) is not int or not 0 <= n <= 1_000_000_000 for n in (incoming, outgoing)
    ):
        raise ValueError("invalid usage")
    if "total_tokens" in usage and usage["total_tokens"] != incoming + outgoing:
        raise ValueError("inconsistent usage")
    image_tokens = usage.get("image_tokens")
    if image_tokens is not None and (
        type(image_tokens) is not int or not 0 <= image_tokens <= incoming
    ):
        raise ValueError("invalid image usage")
    return {
        "input_tokens": incoming,
        "output_tokens": outgoing,
        "total_tokens": incoming + outgoing,
        "image_tokens": image_tokens,
    }


def response_status(body, request):
    if body.get("model") != request.model:
        return "model_mismatch"
    choice = body["choices"][0]
    if choice["message"].get("refusal"):
        return "refused"
    if choice["finish_reason"] != "stop":
        return "truncated"
    content = json.loads(choice["message"]["content"])
    return "ok" if isinstance(content, dict) else "malformed"


def inspect_reply(reply, request):
    result = {
        "status": "malformed",
        "returned_model": None,
        "usage": None,
        "billed_micro_usd": None,
    }
    if reply.billed_usd is not None:
        try:
            result["billed_micro_usd"] = microdollars(reply.billed_usd)
        except BudgetError:
            result["status"] = "invalid_billing"
            return result
    try:
        body = json.loads(reply.raw)
        returned_model = body.get("model")
        if returned_model is not None and not isinstance(returned_model, str):
            return result
        result["returned_model"] = returned_model
        result["status"] = response_status(body, request)
        result["usage"] = usage_from(body)
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ):
        if result["status"] == "ok":
            result["status"] = "usage_missing"
        return result
    if (
        result["usage"]["input_tokens"] > request.max_input_tokens
        or result["usage"]["output_tokens"] > request.max_output_tokens
    ):
        result["status"] = "usage_bound_exceeded"
    return result
