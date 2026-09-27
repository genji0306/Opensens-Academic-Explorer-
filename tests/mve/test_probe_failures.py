from dataclasses import replace
import hashlib
import json
import pytest
from mve.preflight.probe import PROBE_ID
from mve.preflight.probe_contract import ProbeReply, ProbeRefused
from mve.preflight.probe_fixtures import FakeTransport, fixture_reply, fixture_request
from tests.mve.test_probe_guards import ledger, invoke


@pytest.mark.parametrize(
    "fault,status", [("timeout", "timeout"), ("network_error", "transport_error")]
)
def test_uncertain_failure_keeps_full_reservation_without_retry(
    tmp_path, fault, status
):
    book, fake = ledger(tmp_path), FakeTransport(fixture_reply(), fault=fault)
    result = invoke(book, tmp_path, fake)
    assert fake.calls == 1
    assert result["fixture_result"]["status"] == status
    assert book.snapshot()["attempts"][0]["state"] == "dispatched"
    assert book.snapshot()["exposure_micro_usd"] == 20_000
    assert not (tmp_path / "probe/response.raw").exists()


@pytest.mark.parametrize(
    "raw,status", [(b"not-json", "malformed"), (b"[]", "malformed")]
)
def test_malformed_raw_is_retained_and_never_refunds_unknown_cost(
    tmp_path, raw, status
):
    book = ledger(tmp_path)
    result = invoke(book, tmp_path, FakeTransport(ProbeReply(raw)))
    assert result["fixture_result"]["status"] == status
    assert (tmp_path / "probe/response.raw").read_bytes() == raw
    assert result["fixture_result"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert book.snapshot()["exposure_micro_usd"] == 20_000


def test_missing_usage_remains_unknown_without_billing_receipt(tmp_path):
    body = json.loads(fixture_reply().raw)
    del body["usage"]
    book = ledger(tmp_path)
    result = invoke(
        book, tmp_path, FakeTransport(ProbeReply(json.dumps(body).encode()))
    )
    assert result["fixture_result"]["status"] == "usage_missing"
    assert result["fixture_result"]["usage"] is None
    assert book.snapshot()["attempts"][0]["state"] == "dispatched"


def test_failed_response_can_still_be_charged(tmp_path):
    book = ledger(tmp_path)
    result = invoke(book, tmp_path, FakeTransport(ProbeReply(b"malformed", ".01")))
    assert result["fixture_result"]["status"] == "malformed"
    assert book.snapshot()["attempts"][0]["actual"] == 10_000
    receipt = (tmp_path / "probe/receipt.json").read_bytes()
    assert (
        book.snapshot()["attempts"][0]["receipt"] == hashlib.sha256(receipt).hexdigest()
    )


@pytest.mark.parametrize(
    "case,status",
    [
        ("over_tokens", "usage_bound_exceeded"),
        ("model", "model_mismatch"),
        ("bad_bill", "invalid_billing"),
    ],
)
def test_contract_breach_freezes_campaign(tmp_path, case, status):
    body, bill = json.loads(fixture_reply().raw), ".0015"
    if case == "over_tokens":
        body["usage"].update(prompt_tokens=1001, total_tokens=1051)
    elif case == "model":
        body["model"] = "deepseek-other"
    else:
        bill = "-1"
    book = ledger(tmp_path)
    result = invoke(
        book, tmp_path, FakeTransport(ProbeReply(json.dumps(body).encode(), bill))
    )
    assert result["fixture_result"]["status"] == status
    assert book.snapshot()["frozen"]


def test_overcharge_is_not_clamped_to_the_reservation(tmp_path):
    book = ledger(tmp_path)
    invoke(book, tmp_path, FakeTransport(replace(fixture_reply(), billed_usd=".06")))
    snap = book.snapshot()
    assert snap["frozen"] and snap["exposure_micro_usd"] == 60_000
    assert snap["events"][0]["kind"] == "accounting_breach"


def test_pre_dispatch_artifact_failure_cancels_unsent_only(tmp_path):
    book, fake = ledger(tmp_path), FakeTransport(fixture_reply())
    (tmp_path / "probe").mkdir()
    with pytest.raises(FileExistsError):
        invoke(book, tmp_path, fake)
    assert fake.calls == 0
    assert book.snapshot()["attempts"][0]["state"] == "cancelled"


def test_crash_after_dispatch_does_not_release_reservation(tmp_path, monkeypatch):
    book = ledger(tmp_path)

    def crash(self, request):
        raise SystemExit("simulated process loss")

    monkeypatch.setattr(FakeTransport, "send", crash)
    with pytest.raises(SystemExit):
        invoke(book, tmp_path)
    assert book.snapshot()["attempts"][0]["id"] == PROBE_ID
    assert book.snapshot()["attempts"][0]["state"] == "dispatched"
    assert book.snapshot()["exposure_micro_usd"] == 20_000


@pytest.mark.parametrize(
    "change",
    [
        dict(model="deepseek-v4-pro"),
        dict(model="another-provider"),
        dict(prompt=""),
        dict(image=b"invalid-png"),
        dict(image=bytearray(b"not-immutable")),
        dict(timeout_s=0),
        dict(max_input_tokens=True),
    ],
)
def test_bad_requests_refuse_before_reservation(tmp_path, change):
    book, fake = ledger(tmp_path), FakeTransport(fixture_reply())
    with pytest.raises(ProbeRefused):
        invoke(book, tmp_path, fake, replace(fixture_request(), **change))
    assert fake.calls == 0 and book.snapshot()["attempts"] == []


@pytest.mark.parametrize(
    "case,status",
    [
        ("refusal", "refused"),
        ("length", "truncated"),
        ("content", "malformed"),
        ("usage", "usage_missing"),
    ],
)
def test_provider_response_outcomes_are_not_success(tmp_path, case, status):
    body = json.loads(fixture_reply().raw)
    if case == "refusal":
        body["choices"][0]["message"]["refusal"] = "fixture refusal"
    elif case == "length":
        body["choices"][0]["finish_reason"] = "length"
    elif case == "content":
        body["choices"][0]["message"]["content"] = "[]"
    else:
        body["usage"]["prompt_tokens"] = True
    result = invoke(
        ledger(tmp_path), tmp_path, FakeTransport(ProbeReply(json.dumps(body).encode()))
    )
    assert result["fixture_result"]["status"] == status
    assert result["live_cost_model"]["image_support"] == "unverified"
