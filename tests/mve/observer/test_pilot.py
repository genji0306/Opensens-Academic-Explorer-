"""WO-6 acceptance: every sender below is fake; socket guard stays active."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest
from mve.budget import BudgetLedger, BudgetError
from mve.observer import storage
from mve.observer.card import Card, card_hash, spec_hash
from mve.observer import pilot, pilot_accounting as accounting
from mve.observer import pilot_transport as transport
from mve.observer import pilot_inputs as inputs
from mve.preflight import probe_live_transport as wire
from mve.preflight.probe_live import price_table

OFF = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
PEAK = datetime(2026, 9, 28, 7, tzinfo=timezone.utc)


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    return tmp_path


class Reply:
    status = 200

    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.raw[:limit]


class Opener:
    def __init__(self, raw):
        self.raw, self.calls = raw, []

    def open(self, request, timeout):
        self.calls.append(request)
        if isinstance(self.raw, Exception):
            raise self.raw
        return Reply(self.raw)


def test_plan_real_inputs_and_budget():
    plan = inputs.load_plan()
    assert plan["planned_calls"] == 24
    assert plan["worst_case_micro_usd"] == 147456
    assert plan["call_cap"] == 24
    assert len(plan["clusters"]) == 4
    assert {j["arm"] for j in plan["jobs"]} == {
        "real",
        "null_twin",
        "image_free",
        "shuffled",
    }
    assert plan["independent_clusters"] == 0
    assert all(j["snapshot_id"] is None for j in plan["jobs"] if j["arm"] == "shuffled")
    assert {tuple(e["original_size"]) for e in plan["images"].values()} == {
        (1031, 356),
        (1031, 301),
        (1031, 561),
        (1086, 459),
    }
    assert all(max(e["delivered_size"]) <= 1024 for e in plan["images"].values())


def test_carry_once_and_pin(local):
    receipt = accounting.reconcile_campaign()
    assert receipt["report"]["aggregate"]["settled"]["micro_usd"] == 268
    assert receipt["remaining_micro_usd"] == 19999732
    assert len(receipt["report"]["attempts"]) == 1
    assert accounting.reconcile_campaign() == receipt
    assert accounting.verify_reconciliation(receipt) == receipt
    bad = deepcopy(receipt)
    bad["remaining_micro_usd"] += 1
    with pytest.raises(ValueError, match="reconciliation"):
        accounting.verify_reconciliation(bad)


def ledger(local):
    return BudgetLedger(
        storage.local("mve/generated/wo6-pilot/live/pilot.sqlite"),
        aggregate="19.999732",
        p1="0.25",
        price_table=price_table(),
    )


def setup_wire(monkeypatch, raw):
    opener = Opener(raw)
    monkeypatch.setattr(wire, "make_opener", lambda: opener)
    monkeypatch.setattr(wire, "read_key", lambda: "fake-secret-for-test")
    return opener


def request():
    return transport.request(
        inputs.image_bytes(next(iter(inputs.load_plan()["images"]))),
        "Return JSON only.",
    )


def test_raw_first_redacted_no_retry(local, monkeypatch):
    opener = setup_wire(monkeypatch, b"bad fake-secret-for-test")
    book = ledger(local)
    out = storage.local("mve/generated/wo6-pilot/live/a")
    r = transport.dispatch(
        book, request(), output=out, attempt="wo6:000", clock=lambda: OFF, live=True
    )
    assert r["status"] == "malformed"
    assert r["raw_redacted"]
    assert (out / "response.raw").read_bytes() == b"bad [REDACTED]"
    assert len(opener.calls) == 1
    assert book.snapshot()["attempts"][0]["state"] == "settled"
    assert book.snapshot()["exposure_micro_usd"] == 6144


def test_peak_refused_before_key_and_dispatch_recheck(local, monkeypatch):
    opener = setup_wire(monkeypatch, b"{}")
    book = ledger(local)
    with pytest.raises(ValueError, match="peak_window"):
        transport.dispatch(
            book,
            request(),
            output=storage.local("mve/generated/wo6-pilot/live/a"),
            attempt="wo6:000",
            clock=lambda: PEAK,
            live=True,
        )
    times = iter([OFF, PEAK])
    with pytest.raises(ValueError, match="peak_window"):
        transport.dispatch(
            book,
            request(),
            output=storage.local("mve/generated/wo6-pilot/live/b"),
            attempt="wo6:001",
            clock=lambda: next(times),
            live=True,
        )
    assert not opener.calls
    assert book.snapshot()["attempts"][0]["state"] == "cancelled"


def test_call_cap_and_budget_before_transport(local, monkeypatch):
    opener = setup_wire(monkeypatch, b"{}")
    book = ledger(local)
    monkeypatch.setattr(transport, "CALL_CAP", 1)
    transport.dispatch(
        book,
        request(),
        output=storage.local("mve/generated/wo6-pilot/live/a"),
        attempt="wo6:000",
        clock=lambda: OFF,
        live=True,
    )
    with pytest.raises(ValueError, match="call_cap"):
        transport.dispatch(
            book,
            request(),
            output=storage.local("mve/generated/wo6-pilot/live/b"),
            attempt="wo6:001",
            clock=lambda: OFF,
            live=True,
        )
    assert len(opener.calls) == 1
    low = BudgetLedger(
        storage.local("mve/generated/low.sqlite"), p1="0.001", price_table=price_table()
    )
    with pytest.raises(ValueError, match="budget_cap"):
        transport.dispatch(
            low,
            request(),
            output=storage.local("mve/generated/wo6-pilot/live/c"),
            attempt="wo6:002",
            clock=lambda: OFF,
            live=True,
        )
    assert len(opener.calls) == 1


def test_dry_run_whole_pipeline(local, monkeypatch, capsys):
    monkeypatch.setattr(wire, "read_key", lambda: pytest.fail("dry run read key"))
    assert pilot.main(["--dry-run"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["planned_calls"] == 24
    assert printed["worst_case_micro_usd"] == 147456
    assert printed["hosted_calls"] == 0
    result = json.loads(
        storage.local("mve/generated/wo6-pilot/dry-run/report.json").read_text()
    )
    assert len(result["slots"]) == 48
    assert result["GO2"]["passed"] is False
    assert result["second_observer"]["status"] == "SKIPPED"
    assert sum(s["status"] == "unavailable_donor" for s in result["slots"]) == 12
    assert all(
        s["card"]["status"] == "preliminary" for s in result["slots"] if s["card"]
    )
    assert storage.local("mve/generated/wo6-pilot/dry-run/report.md").exists()


def test_malformed_reply_retains_slots(local, monkeypatch):
    setup_wire(monkeypatch, b"not json")
    monkeypatch.setattr(pilot, "require_review", lambda *a: None)
    result = pilot.execute(live=True, reviewed_head="a" * 40, clock=lambda: OFF)
    assert len(result["slots"]) == 48
    visual = [s for s in result["slots"] if s["arm"] in ("real", "null_twin")]
    assert len(visual) == 24 and all(s["card"] is None for s in visual)
    assert result["calls"] == 24
    assert result["budget"]["aggregate"]["exposure"]["micro_usd"] == 147724
    with pytest.raises(ValueError, match="run_exists"):
        pilot.execute(live=True, reviewed_head="a" * 40, clock=lambda: OFF)


def test_unmapped_card_is_valid_preliminary_and_cannot_survive():
    from mve.observer.pilot_cards import make_card, proposal_fixture, check_card

    plan = inputs.load_plan()
    job = next(
        j for j in plan["jobs"] if j["module"] == "polar-ulam" and j["arm"] == "real"
    )
    card = make_card(proposal_fixture(), job, ["wo6:test"], live=False)
    card, check = check_card(card, job)
    assert card.to_dict()["status"] == "preliminary"
    assert check["status"] == "unavailable"
    bad = card.to_dict()
    bad["status"] = "checked:baseline_exceeding_survivor"
    with pytest.raises(Exception):
        Card.from_dict(bad)


def test_wo3_diagnostic_uses_sorted_gaps():
    import numpy as np
    from mve.observer import pilot_cards as cards
    from mve.observer.checks import spacing

    plan = inputs.load_plan()
    job = next(
        j for j in plan["jobs"] if j["module"] == "spectral" and j["arm"] == "real"
    )
    proposal = cards.proposal_fixture()
    proposal["testable_form"].update(statistic="gaudin_ks", baseline="Gaudin GUE")
    card, check = cards.check_card(
        cards.make_card(proposal, job, ["test"], live=False), job
    )
    e = cards.entry(job)
    x = np.sort(
        json.loads((inputs.INPUTS / e["data_ref"]["path"]).read_text())["values"]
    )
    assert check["value"] == spacing.ks_d(x, spacing.gaudin_cdf(x))
    assert card.to_dict()["status"] == "preliminary"


@pytest.mark.parametrize(
    "approval,commit", [("2026-09-27", "a" * 40), ("2026-09-28", "HEAD"), (None, None)]
)
def test_review_requires_exact_assertions(approval, commit):
    with pytest.raises(ValueError, match="owner_approval|review_head"):
        pilot.require_review(approval, commit)


@pytest.mark.parametrize("dirty,head", [(b" M test", "a" * 40), (b"", "b" * 40)])
def test_review_refuses_dirty_or_wrong_head(monkeypatch, dirty, head):
    from types import SimpleNamespace

    values = iter([head.encode(), dirty])
    monkeypatch.setattr(
        pilot.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=next(values))
    )
    with pytest.raises(ValueError, match="clean_tree|review_head"):
        pilot.require_review("2026-09-28", "a" * 40)


def test_review_clean_and_git_failure(monkeypatch):
    from types import SimpleNamespace

    values = iter([b"a" * 40, b""])
    monkeypatch.setattr(
        pilot.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=next(values))
    )
    pilot.require_review("2026-09-28", "a" * 40)

    def failed(*a, **kw):
        raise OSError("private-path")

    monkeypatch.setattr(pilot.subprocess, "run", failed)
    with pytest.raises(ValueError, match="review_head"):
        pilot.require_review("2026-09-28", "a" * 40)


@pytest.mark.parametrize(
    "failure", [TimeoutError("fake-secret-for-test"), OSError("fake-secret-for-test")]
)
def test_transport_fault_no_retry_no_secret(local, monkeypatch, failure):
    opener = setup_wire(monkeypatch, failure)
    book = ledger(local)
    out = storage.local("mve/generated/wo6-pilot/live/fault")
    r = transport.dispatch(
        book, request(), output=out, attempt="wo6:fault", clock=lambda: OFF, live=True
    )
    assert r["status"] in ("timeout", "transport_error")
    assert len(opener.calls) == 1
    assert b"fake-secret" not in (out / "receipt.json").read_bytes()
    assert book.snapshot()["exposure_micro_usd"] == 6144


def test_usage_overrun_freezes_and_stops_remaining_calls(local, monkeypatch):
    body = json.loads(pilot.fake_response("card", {"module": "spectral"}))
    body["usage"]["prompt_tokens"] = 20000
    opener = setup_wire(monkeypatch, json.dumps(body).encode())
    monkeypatch.setattr(pilot, "require_review", lambda *a: None)
    result = pilot.execute(live=True, clock=lambda: OFF)
    assert len(opener.calls) == 1
    assert result["calls"] == 1
    assert result["budget"]["frozen"]
    assert result["status_counts"]["ledger_frozen"] == 21
    assert result["budget"]["aggregate"]["exposure"]["micro_usd"] == 6508


def test_malformed_cards_do_not_remove_denominators(local, monkeypatch):
    original_response = pilot.fake_response
    monkeypatch.setattr(
        pilot,
        "fake_response",
        lambda prompt, job: original_response(prompt, job)
        if prompt == pilot.cards.PERCEPTION_PROMPT
        else json.dumps(
            {
                "model": "deepseek-flash",
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"cards": [{}]}'}}
                ],
            }
        ).encode(),
    )
    result = pilot.execute(live=False, clock=lambda: OFF)
    assert len(result["slots"]) == 48
    assert result["status_counts"]["malformed"] == 8
    assert result["status_counts"]["empty"] == 16


def test_card_overflow_is_failed_not_topped_up(local, monkeypatch):
    original_response = pilot.fake_response
    monkeypatch.setattr(
        pilot,
        "fake_response",
        lambda prompt, job: original_response(prompt, job)
        if prompt == pilot.cards.PERCEPTION_PROMPT
        else json.dumps(
            {
                "model": "deepseek-flash",
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"cards": [{},{},{},{}]}'},
                    }
                ],
            }
        ).encode(),
    )
    result = pilot.execute(live=False, clock=lambda: OFF)
    assert result["status_counts"]["malformed"] == 24
    assert result["calls"] == 24


def test_dispatch_failure_and_disk_failure_not_swallowed(local, monkeypatch):
    def failed(*a, **kw):
        raise BudgetError("test peak")

    monkeypatch.setattr(pilot, "observe", failed)
    result = pilot.execute(live=False, clock=lambda: OFF)
    assert result["status_counts"]["dispatch_failed"] == 24
    assert result["calls"] == 0


def test_disk_failure_aborts_pipeline(local, monkeypatch):
    def failed(*a, **kw):
        raise storage.DiskLimitError("disk_free")

    monkeypatch.setattr(pilot, "observe", failed)
    with pytest.raises(storage.DiskLimitError):
        pilot.execute(live=False, clock=lambda: OFF)


def test_unreconciled_campaign_refused_before_sender(local, monkeypatch):
    monkeypatch.setattr(
        wire, "read_key", lambda: pytest.fail("key before reconciliation")
    )
    monkeypatch.setattr(pilot, "require_review", lambda *a: None)

    def failed():
        raise ValueError("reconciliation missing")

    monkeypatch.setattr(accounting, "reconcile_campaign", failed)
    with pytest.raises(ValueError, match="reconciliation"):
        pilot.execute(live=True, clock=lambda: OFF)
    assert not storage.local("mve/generated/wo6-pilot/live").exists()


def test_cli_live_delegation_and_safe_failure(monkeypatch, capsys):
    def fake(**kwargs):
        assert kwargs["live"] and kwargs["owner_approval"] == "2026-09-28"
        return dict(
            planned_calls=24, calls=24, hosted_calls=24, worst_case_micro_usd=147456
        )

    monkeypatch.setattr(pilot, "execute", fake)
    assert (
        pilot.main(
            ["--live", "--owner-approval", "2026-09-28", "--reviewed-by-opus", "a" * 40]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["planned_calls"] == 24

    def fail(**kw):
        raise ValueError("secret must not print")

    monkeypatch.setattr(pilot, "execute", fail)
    with pytest.raises(SystemExit) as exc:
        pilot.main(["--dry-run"])
    assert exc.value.code == 2
    assert "secret must not print" not in capsys.readouterr().err


def test_wo4_delegates_live_mode(monkeypatch):
    from mve.observer import run

    calls = []
    monkeypatch.setattr(pilot, "main", lambda args: calls.append(args) or 0)
    assert run.main(["--dry-run"]) == 0
    assert calls == [["--dry-run"]]


def test_low_disk_and_generated_limit(local, monkeypatch):
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: (0, 0, 4 * 1024**3))
    with pytest.raises(storage.DiskLimitError, match="free"):
        pilot.execute(live=False, clock=lambda: OFF)
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: (0, 0, 10 * 1024**3))
    monkeypatch.setattr(storage, "tree_bytes", lambda p: 301 * 1024**2)
    with pytest.raises(storage.DiskLimitError, match="generated_cap"):
        pilot.execute(live=False, clock=lambda: OFF)


def test_raw_saved_before_parse(local, monkeypatch):
    from mve.preflight import probe_live_response

    original = probe_live_response.inspect_live
    out = storage.local("mve/generated/wo6-pilot/live/raw")
    setup_wire(monkeypatch, b"{}")

    def inspect(reply, *a):
        assert (out / "response.raw").read_bytes() == reply.raw
        return original(reply, *a)

    monkeypatch.setattr(probe_live_response, "inspect_live", inspect)
    transport.dispatch(
        ledger(local),
        request(),
        output=out,
        attempt="wo6:raw",
        clock=lambda: OFF,
        live=True,
    )


def test_declared_threshold_is_hashed_and_required():
    from mve.observer import pilot_cards as cards

    job = next(j for j in inputs.load_plan()["jobs"] if j["arm"] == "real")
    a = cards.make_card(cards.proposal_fixture(), job, ["call"], live=False).to_dict()
    b = cards.make_card(
        {**cards.proposal_fixture(), "kill_threshold": 0.2}, job, ["call"], live=False
    ).to_dict()
    assert a["content_hash"] != b["content_hash"]
    assert a["check_spec"]["spec_sha256"] != b["check_spec"]["spec_sha256"]
    a["check_spec"]["kill_rule"]["components"][0].pop("threshold")
    a["kill_criterion"] = a["check_spec"]["kill_rule"]
    a["check_spec"]["spec_sha256"] = spec_hash(a["check_spec"])
    a["content_hash"] = card_hash(a)
    with pytest.raises(Exception, match="threshold"):
        Card.from_dict(a)


def test_wrong_perception_shape_fails_fixed_slots(local, monkeypatch):
    original = pilot.fake_response

    def wrong(prompt, job):
        if prompt == pilot.cards.PERCEPTION_PROMPT:
            body = json.loads(original(prompt, job))
            body["choices"][0]["message"]["content"] = '{"unrelated": true}'
            return json.dumps(body).encode()
        return original(prompt, job)

    monkeypatch.setattr(pilot, "fake_response", wrong)
    result = pilot.execute(live=False, clock=lambda: OFF)
    assert result["status_counts"]["malformed"] == 24
    assert result["calls"] == 24


def test_frozen_library_declares_family_baselines():
    from mve.observer import pilot_cards as cards

    for job in inputs.load_plan()["jobs"]:
        if job["arm"] != "image_free":
            continue
        proposals = cards.library(job)
        assert len(proposals) == 3
        expected = (
            "Gaudin GUE"
            if job["module"] in ("spectral", "field-dyson")
            else "Cramer random primes"
        )
        assert {p["testable_form"]["baseline"] for p in proposals} == {expected}
        assert len({p["kill_threshold"] for p in proposals}) == 3
