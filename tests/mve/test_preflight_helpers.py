import argparse
import asyncio
from dataclasses import dataclass
import json
from types import SimpleNamespace
import pytest
from mve.preflight import openjev_fixture, vision_contract


class FakeVision:
    def __init__(self, refuse=False):
        self.W = SimpleNamespace(rate_in_force=lambda when: "offpeak")
        self.original_rate = self.W.rate_in_force
        self.refuse = refuse

    @staticmethod
    def run_task(task, manifest, fleet, transport):
        pass

    async def run_all(self, args, manifest, fleet, transport):
        assert isinstance(args, argparse.Namespace) and args.concurrency == 2
        assert manifest["run_cap_usd"] == 0.05
        assert self.W.rate_in_force(None) == "peak"
        rows = []
        (fleet / "cells").mkdir()
        if not self.refuse:
            responses = await asyncio.gather(
                *(transport(task) for task in manifest["tasks"])
            )
            for i, response in enumerate(responses):
                assert (
                    json.loads(response["choices"][0]["message"]["content"])["outcome"]
                    == "observation"
                )
                (fleet / "cells" / f"{i}.raw.json").write_text(json.dumps(response))
                rows.append({"cost_usd": 0.04})
        (fleet / "ledger.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )


@pytest.mark.parametrize("refuse", [False, True])
def test_vision_exercise_with_injected_fake_runner(tmp_path, refuse):
    module = FakeVision(refuse)
    result = asyncio.run(vision_contract.exercise(module, tmp_path))
    assert result["fake_calls_during_peak"] == (0 if refuse else 2)
    assert result["accounted_cost"] == (0 if refuse else 0.08)
    assert result["raw_responses_retained"] == (0 if refuse else 2)
    assert result["inflight_reservations_enforced"] is refuse
    assert result["peak_refused"] is refuse
    assert module.W.rate_in_force is module.original_rate


def test_vision_main_uses_fake_module_and_records_original_window(monkeypatch, capsys):
    monkeypatch.setattr(
        vision_contract.importlib, "import_module", lambda name: FakeVision()
    )
    monkeypatch.setattr(
        vision_contract.sys, "argv", ["vision_contract.py", "/fake/scripts"]
    )
    assert vision_contract.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert set(result["window"].values()) == {"offpeak"}
    assert result["fake_calls_during_peak"] == 2


@dataclass
class FakeAnswer:
    domain: str = "plane_geometry"


class FakeBackend:
    def ask(self, request):
        assert request == "fixture-request"
        return FakeAnswer()

    def token_counts(self, request):
        assert request == "fixture-request"
        return {"domain": 38}


def test_openjev_exercise_with_fake_backend():
    result = openjev_fixture.exercise(FakeBackend(), "fixture-request")
    assert result["answers"] == {"domain": "plane_geometry"}
    assert result["complete_input_tokens"] == {"domain": 38}
    assert result["duration_s"] >= 0


def test_openjev_unavailable_backend_is_not_a_success():
    backend = SimpleNamespace(ask=lambda request: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        openjev_fixture.exercise(backend, "fixture-request")


def test_openjev_main_has_no_real_backend(monkeypatch, capsys):
    import sys

    monkeypatch.setitem(sys.modules, "rhjev", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "rhjev.openjev", SimpleNamespace(OpenJevBackend=FakeBackend)
    )
    monkeypatch.setitem(
        sys.modules,
        "rhjev.questions",
        SimpleNamespace(
            Choice=lambda *a: "choice", make_request=lambda *a: "fixture-request"
        ),
    )
    monkeypatch.setattr(sys, "argv", ["openjev_fixture.py", "/fake/rhjev"])
    assert openjev_fixture.main() == 0
    assert json.loads(capsys.readouterr().out)["answers"] == {
        "domain": "plane_geometry"
    }
