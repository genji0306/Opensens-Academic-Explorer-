"""WP-3 fixtures: the adapter receives only public PNG/reply bytes."""

from datetime import datetime, timezone
import json
from pathlib import Path
from mve.budget import BudgetLedger
from mve.preflight.probe_contract import ProbeReply

ROOT = Path(__file__).parent / "perceiver_fixtures"
OFF = datetime(2026, 9, 28, 0, 59, tzinfo=timezone.utc)
PEAK = datetime(2026, 9, 28, 1, tzinfo=timezone.utc)


def prices(verified=True):
    return {
        "deepseek-flash": {
            "input_per_million": "1",
            "output_per_million": "1",
            "source_sha256": "a" * 64,
            "verified": verified,
        }
    }


def book(path, **kwargs):
    return BudgetLedger(path / "ledger.sqlite", price_table=prices(), **kwargs)


def reply(call=1, seed=0):
    return ProbeReply(
        (ROOT / "public" / f"development_{seed}.call{call}.raw").read_bytes(), "0.0018"
    )


def mutate_reply(
    *,
    content=None,
    model="deepseek-flash",
    finish="stop",
    refusal=None,
    usage=True,
    bill="0.0018",
):
    body = json.loads(reply().raw)
    body["model"] = model
    body["choices"][0].update(finish_reason=finish)
    body["choices"][0]["message"].update(refusal=refusal)
    if content is not None:
        body["choices"][0]["message"]["content"] = (
            content if isinstance(content, str) else json.dumps(content)
        )
    if not usage:
        del body["usage"]
    return ProbeReply(json.dumps(body).encode(), bill)


def content():
    return json.loads(json.loads(reply().raw)["choices"][0]["message"]["content"])


def run(path, replies=None, ledger=None, **kwargs):
    from mve.perceiver import perceive, Replay
    from mve.perceiver.contract import ImageInput

    return perceive(
        ledger or book(path),
        ImageInput((ROOT / "public/development_0.png").read_bytes()),
        replay=Replay(tuple(replies or [reply(), reply(2)])),
        output=path / "run",
        nonce="0123456789abcdef",
        clock=lambda: OFF,
        **kwargs,
    )
