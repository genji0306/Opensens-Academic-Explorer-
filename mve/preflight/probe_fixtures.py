"""Local fake transport and synthetic prices. No fixture is live vendor evidence."""

from dataclasses import dataclass
from io import BytesIO
import json
from PIL import Image
from mve.preflight.probe_contract import ProbeRequest, ProbeReply


@dataclass
class FakeTransport:
    reply: ProbeReply
    fault: str | None = None
    calls: int = 0

    def send(self, request):
        self.calls += 1
        if self.fault == "timeout":
            raise TimeoutError("fixture timeout")
        if self.fault:
            raise OSError("fixture transport failure")
        return self.reply


def fixture_request():
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    return ProbeRequest(
        "deepseek-fixture",
        "Return a JSON observation of this fixture.",
        buffer.getvalue(),
        1000,
        1000,
    )


def fixture_reply():
    body = {
        "model": "deepseek-fixture",
        "choices": [
            {
                "message": {"content": '{"fixture_observation":true}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    return ProbeReply(json.dumps(body, sort_keys=True).encode(), ".0015")
