"""The live activation is tested exclusively with a fake urllib opener."""

from datetime import datetime, timezone
from io import BytesIO
import json
import subprocess
import urllib.error

import pytest

from mve.budget import BudgetError
from mve.preflight import probe_live as live
from mve.preflight import probe_live_transport as transport
from mve.preflight.probe import PROBE_ID
from mve.preflight.probe_contract import ProbeRefused

SECRET = "test-only-key-DO-NOT-PERSIST"
OFF = datetime(2026, 9, 28, 0, 59, tzinfo=timezone.utc)
PEAK = datetime(2026, 9, 28, 1, tzinfo=timezone.utc)


def body(**changes):
    result = {
        "model": "deepseek-flash",
        "choices": [
            {"message": {"content": '{"observations":[]}'}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 90,
            "prompt_tokens_details": {"cached_tokens": 10, "image_tokens": 20},
        },
    }
    result.update(changes)
    return json.dumps(result).encode()


class Reply(BytesIO):
    status = 200


class Opener:
    def __init__(self, raw=None, fault=None, before=None):
        self.raw = body() if raw is None else raw
        self.fault, self.before, self.calls = fault, before, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.before:
            self.before()
        if self.fault:
            raise self.fault
        return Reply(self.raw)


@pytest.fixture
def setup_live(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "LIVE_ROOT", tmp_path / "live")
    monkeypatch.setattr(live, "require_review", lambda approval, commit: None)
    monkeypatch.setattr(transport, "read_key", lambda: SECRET)
    opener = Opener()
    monkeypatch.setattr(transport, "make_opener", lambda: opener)
    return opener


def run():
    return live.run_live(
        owner_approval="2026-09-27", reviewed_by_opus="a" * 40, clock=lambda: OFF
    )


def test_success_persisted_before_send_and_restart_refuses(setup_live):
    def before():
        attempt = live.open_ledger().snapshot()["attempts"][0]
        assert attempt["id"] == PROBE_ID and attempt["phase"] == "P0"
        assert attempt["state"] == "dispatched"
        assert (live.LIVE_ROOT / "probe/request.json").is_file()

    setup_live.before = before
    result = run()
    assert result["status"] == "ok" and result["image_accepted"] is True
    assert result["cost_basis"] == "derived_from_usage"
    assert result["derived_micro_usd"] == 90
    assert result["usage"]["prompt_tokens_details"]["image_tokens"] == 20
    request, timeout = setup_live.calls[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert request.method == "POST" and timeout == 30
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["max_tokens"] == 512
    assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert (live.LIVE_ROOT / "probe/response.raw").read_bytes() == setup_live.raw
    receipt = json.loads((live.LIVE_ROOT / "probe/receipt.json").read_text())
    assert receipt["requested_model"] == "deepseek-flash"
    assert receipt["observation"]["http_status"] == 200
    assert receipt["window_verified"] is True
    assert receipt["reserved_micro_usd"] <= 50_000
    with pytest.raises(BudgetError, match="already exists"):
        run()
    assert len(setup_live.calls) == 1


@pytest.mark.parametrize("code", [400, 401, 429, 500, 503, 302])
def test_http_failures_saved_settled_never_retried(setup_live, code):
    raw = b'{"error":"image rejected"}'
    setup_live.fault = urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions", code, "error", {}, BytesIO(raw)
    )
    result = run()
    assert result["status"] == "http_error" and result["http_status"] == code
    assert result["image_accepted"] is False
    assert (live.LIVE_ROOT / "probe/response.raw").read_bytes() == raw
    row = live.open_ledger().snapshot()["attempts"][0]
    assert row["state"] == "settled" and row["actual"] == row["reserved"]
    assert result["cost_basis"] == "reservation_retained_unknown_cost"
    with pytest.raises(BudgetError):
        run()
    assert len(setup_live.calls) == 1


@pytest.mark.parametrize(
    "fault,status",
    [
        (TimeoutError(SECRET), "timeout"),
        (urllib.error.URLError(TimeoutError(SECRET)), "timeout"),
        (OSError(SECRET), "transport_error"),
    ],
)
def test_transport_failure_and_secret_safe_errors(setup_live, fault, status):
    setup_live.fault = fault
    result = run()
    assert result["status"] == status
    assert result["http_status"] is None
    assert result["image_accepted"] is None
    assert_no_secret()


def assert_no_secret():
    for path in live.LIVE_ROOT.rglob("*"):
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes(), path


@pytest.mark.parametrize(
    "raw,status",
    [
        (b"not json", "malformed"),
        (body(usage=None), "usage_missing"),
        (body(model="other"), "model_mismatch"),
        (body(usage={"prompt_tokens": True, "completion_tokens": 2}), "usage_missing"),
        (
            body(usage={"prompt_tokens": 999999, "completion_tokens": 1}),
            "usage_bound_exceeded",
        ),
    ],
)
def test_response_failures(setup_live, raw, status):
    setup_live.raw = raw
    assert run()["status"] == status
    assert (live.LIVE_ROOT / "probe/response.raw").read_bytes() == raw
    assert live.open_ledger().snapshot()["attempts"][0]["state"] == "settled"


def test_echoed_key_is_redacted_before_raw_persistence(setup_live):
    setup_live.raw = body(error=SECRET, headers={"Authorization": "Bearer " + SECRET})
    result = run()
    assert result["raw_redacted"] is True
    assert_no_secret()


def test_missing_key_refuses_without_dispatch(setup_live, monkeypatch):
    def missing():
        raise ProbeRefused("Keychain key unavailable")

    monkeypatch.setattr(transport, "read_key", missing)
    with pytest.raises(ProbeRefused, match="Keychain"):
        run()
    assert not setup_live.calls
    assert live.open_ledger().snapshot()["attempts"][0]["state"] == "cancelled"


def test_offpeak_rechecked_after_key_preparation(setup_live):
    times = iter([OFF, PEAK])
    with pytest.raises(BudgetError, match="peak"):
        live.run_live(
            owner_approval="2026-09-27",
            reviewed_by_opus="a" * 40,
            clock=lambda: next(times),
        )
    assert not setup_live.calls


@pytest.mark.parametrize("value", [b"", b"bad\nkey", b"bad\x00key"])
def test_key_reader_rejects_invalid_without_exposure(monkeypatch, value):
    monkeypatch.setattr(
        transport.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, value, SECRET.encode()),
    )
    with pytest.raises(ProbeRefused) as exc:
        transport.read_key()
    assert SECRET not in str(exc.value)


def test_key_reader_exact_argv_and_failure_redaction(monkeypatch):
    def read(args, **kwargs):
        assert args == [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            "oae-deepseek-api-key",
            "-w",
        ]
        assert kwargs["timeout"] <= 10 and kwargs["capture_output"]
        return subprocess.CompletedProcess(args, 0, SECRET.encode() + b"\n", b"")

    monkeypatch.setattr(transport.subprocess, "run", read)
    assert transport.read_key() == SECRET

    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, "security", output=SECRET)

    monkeypatch.setattr(transport.subprocess, "run", fail)
    with pytest.raises(ProbeRefused) as exc:
        transport.read_key()
    import traceback

    assert SECRET not in "".join(traceback.format_exception(exc.value))
    assert exc.value.__context__ is None


def test_review_requires_exact_head_and_clean_tree(monkeypatch):
    def git(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0, b"a" * 40 + b"\n" if "rev-parse" in args else b"", b""
        )

    monkeypatch.setattr(live.subprocess, "run", git)
    live.require_review("2026-09-27", "a" * 40)
    for approval, commit in [
        (None, "a" * 40),
        ("2026-09-26", "a" * 40),
        ("2026-09-27", "b" * 40),
        ("2026-09-27", "HEAD"),
    ]:
        with pytest.raises(ProbeRefused):
            live.require_review(approval, commit)


@pytest.mark.parametrize(
    "flags",
    [
        [],
        ["--live"],
        ["--owner-approval", "2026-09-27"],
        ["--live", "--owner-approval", "2026-09-27"],
        ["--live", "--reviewed-by-opus", "a" * 40],
        ["--live", "--offline-fixture"],
    ],
)
def test_cli_gates_before_live_runner(monkeypatch, flags, tmp_path):
    from mve.preflight import probe

    monkeypatch.setattr(live, "run_live", lambda **k: pytest.fail("gating must refuse"))
    monkeypatch.setattr(
        "sys.argv", ["probe", "--output", str(tmp_path / "out"), *flags]
    )
    with pytest.raises(SystemExit):
        probe.main()


def test_opener_blocks_redirects_and_environment_proxies(monkeypatch):
    import urllib.request

    monkeypatch.setenv("HTTPS_PROXY", "http://invalid.local:9999")
    opener = transport.make_opener()
    assert not any(isinstance(h, urllib.request.HTTPHandler) for h in opener.handlers)
    assert not any(
        isinstance(h, urllib.request.ProxyHandler) and h.proxies
        for h in opener.handlers
    )
    assert any(isinstance(h, urllib.request.HTTPSHandler) for h in opener.handlers)
    handler = next(h for h in opener.handlers if isinstance(h, transport.NoRedirect))
    request = urllib.request.Request(transport.URL)
    assert (
        handler.redirect_request(
            request, None, 302, "redirect", {}, "https://other.invalid"
        )
        is None
    )
    with pytest.raises(urllib.error.HTTPError):
        opener.error(
            "http",
            request,
            BytesIO(),
            302,
            "redirect",
            {"location": "https://other.invalid"},
        )


def test_raw_is_saved_before_inspection(setup_live, monkeypatch):
    from mve.preflight import probe_live_response as response

    original = response.inspect_live

    def inspect(*args):
        assert (live.LIVE_ROOT / "probe/response.raw").read_bytes() == setup_live.raw
        return original(*args)

    monkeypatch.setattr(response, "inspect_live", inspect)
    run()


def test_oversized_response_stops_without_retry(setup_live):
    setup_live.raw = b"x" * (transport.MAX_REPLY_BYTES + 2)
    assert run()["status"] == "response_too_large"
    assert len(setup_live.calls) == 1
    assert (
        live.LIVE_ROOT / "probe/response.raw"
    ).stat().st_size == transport.MAX_REPLY_BYTES + 1


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": 100, "completion_tokens": 50, "prompt_cache_hit_tokens": 101},
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 1,
        },
        {"prompt_tokens": 100, "completion_tokens": 50, "prompt_tokens_details": None},
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "completion_tokens_details": {"reasoning_tokens": 51},
        },
        {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 151},
    ],
)
def test_invalid_optional_usage_is_uncertain(setup_live, usage):
    setup_live.raw = body(usage=usage)
    assert run()["cost_basis"] == "reservation_retained_unknown_cost"


def test_malformed_content_still_accounts_usage(setup_live):
    setup_live.raw = body(
        choices=[{"message": {"content": "broken"}, "finish_reason": "stop"}]
    )
    result = run()
    assert result["status"] == "malformed" and result["derived_micro_usd"] == 90


def test_pinned_image_and_evidence_refuse_tampering(tmp_path, monkeypatch):
    import shutil

    shutil.copytree(live.EVIDENCE, tmp_path / "evidence")
    monkeypatch.setattr(live, "EVIDENCE", tmp_path / "evidence")
    (live.EVIDENCE / "wp0b-fit.png").write_bytes(b"bad")
    with pytest.raises(ProbeRefused, match="fit"):
        live.live_request()
    (live.EVIDENCE / "deepseek-20260927.json").write_bytes(b"bad")
    with pytest.raises(ProbeRefused, match="evidence"):
        live.price_table()


def test_unverified_evidence_refused_even_with_matching_hash(tmp_path, monkeypatch):
    import hashlib

    evidence = json.loads((live.EVIDENCE / "deepseek-20260927.json").read_bytes())
    evidence["price_verified"] = False
    raw = json.dumps(evidence).encode()
    (tmp_path / "deepseek-20260927.json").write_bytes(raw)
    monkeypatch.setattr(live, "EVIDENCE", tmp_path)
    monkeypatch.setattr(live, "PRICE_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ProbeRefused, match="unverified"):
        live.price_table()


def test_review_git_failure_and_dirty_tree(monkeypatch):
    def fail(*a, **k):
        raise OSError("git failed")

    monkeypatch.setattr(live.subprocess, "run", fail)
    with pytest.raises(ProbeRefused, match="cannot verify"):
        live.require_review("2026-09-27", "a" * 40)
    monkeypatch.setattr(
        live.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, b"a" * 40, b""),
    )
    with pytest.raises(ProbeRefused, match="clean"):
        live.require_review("2026-09-27", "a" * 40)


@pytest.mark.parametrize(
    "flags",
    [
        ["--live"],
        ["--live", "--owner-approval", "2026-09-27"],
        ["--live", "--reviewed-by-opus", "a" * 40],
        ["--offline-fixture"],
    ],
)
def test_cli_missing_required_arguments_without_output(monkeypatch, flags):
    from mve.preflight import probe

    monkeypatch.setattr(live, "run_live", lambda **k: pytest.fail("must refuse"))
    monkeypatch.setattr("sys.argv", ["probe", *flags])
    with pytest.raises(SystemExit):
        probe.main()


@pytest.mark.parametrize("status,expected", [("ok", 0), ("http_error", 1)])
def test_cli_live_delegates_only_with_all_flags(monkeypatch, capsys, status, expected):
    from mve.preflight import probe

    def fake(**kwargs):
        assert kwargs == {"owner_approval": "2026-09-27", "reviewed_by_opus": "a" * 40}
        return {"status": status}

    monkeypatch.setattr(live, "run_live", fake)
    monkeypatch.setattr(
        "sys.argv",
        [
            "probe",
            "--live",
            "--owner-approval",
            "2026-09-27",
            "--reviewed-by-opus",
            "a" * 40,
        ],
    )
    assert probe.main() == expected
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_cli_review_refusal_is_safe(monkeypatch):
    from mve.preflight import probe

    def refuse(**kwargs):
        raise ProbeRefused("not reviewed")

    monkeypatch.setattr(live, "run_live", refuse)
    monkeypatch.setattr(
        "sys.argv",
        [
            "probe",
            "--live",
            "--owner-approval",
            "2026-09-27",
            "--reviewed-by-opus",
            "a" * 40,
        ],
    )
    with pytest.raises(SystemExit):
        probe.main()


def test_nonfinite_unknown_usage_does_not_break_receipt(setup_live):
    setup_live.raw = body(
        usage={"prompt_tokens": 1, "completion_tokens": 0, "unknown": float("nan")}
    )
    result = run()
    assert result["status"] == "malformed"
    assert result["cost_basis"] == "reservation_retained_unknown_cost"


def test_model_mismatch_never_priced_as_requested_model(setup_live):
    setup_live.raw = body(model="unpriced-model")
    result = run()
    assert result["usage"]["prompt_tokens"] == 100
    assert result["derived_micro_usd"] is None
    assert live.open_ledger().snapshot()["frozen"]


def test_cancelled_key_failure_consumes_one_shot(setup_live, monkeypatch):
    monkeypatch.setattr(
        transport,
        "read_key",
        lambda: (_ for _ in ()).throw(ProbeRefused("key missing")),
    )
    with pytest.raises(ProbeRefused):
        run()
    monkeypatch.setattr(transport, "read_key", lambda: SECRET)
    with pytest.raises(BudgetError, match="already exists"):
        run()
    assert not setup_live.calls


def test_process_loss_after_dispatch_retains_reservation_and_blocks_restart(setup_live):
    setup_live.fault = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run()
    attempt = live.open_ledger().snapshot()["attempts"][0]
    assert attempt["state"] == "dispatched" and attempt["actual"] is None
    assert live.open_ledger().snapshot()["exposure_micro_usd"] == 39936
    setup_live.fault = None
    with pytest.raises(BudgetError, match="already exists"):
        run()
    assert len(setup_live.calls) == 1


def test_real_review_gate_refuses_before_key_or_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "LIVE_ROOT", tmp_path / "live")
    monkeypatch.setattr(transport, "read_key", lambda: pytest.fail("no key access"))
    monkeypatch.setattr(
        live.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, b"b" * 40, b""),
    )
    with pytest.raises(ProbeRefused):
        run()
    assert not live.LIVE_ROOT.exists()


def test_valid_total_and_completion_details(setup_live):
    setup_live.raw = body(
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
    )
    assert run()["status"] == "ok"


def test_nonzero_keychain_result_is_refused_without_secret_context(monkeypatch):
    monkeypatch.setattr(
        transport.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 1, SECRET.encode(), SECRET.encode()
        ),
    )
    with pytest.raises(ProbeRefused) as exc:
        transport.read_key()
    assert exc.value.__context__ is None
    assert SECRET not in str(exc.value)
