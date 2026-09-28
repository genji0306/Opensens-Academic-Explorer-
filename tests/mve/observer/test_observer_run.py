import json
import pytest
from mve.observer.design import allocate
from mve.observer.run import run, reconciliation, human_cards, second_model
from mve.observer import storage
from mve.perceiver import Replay
from tests.mve.observer.wo45_helpers import fixture, replays
from tests.mve.perceiver_helpers import book, OFF, mutate_reply, prices
from mve.observer.card import Card
from pathlib import Path


def setup(tmp_path, monkeypatch, retries=0):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    m, c = fixture(tmp_path / "inputs")
    c["retries"] = retries
    p = allocate(m, tmp_path / "inputs", c)
    (tmp_path / "mve").mkdir(exist_ok=True)
    (tmp_path / "mve/DEPS.lock").write_text(
        json.dumps(
            {"packets": {"WO-4": {"frozen_design_sha256s": [p.to_dict()["sha256"]]}}}
        )
    )
    b = book(tmp_path / "mve/generated")
    return p, b, reconciliation(b, provider_records=[])


def test_offline_run_cards_slots_and_real_guards(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch)
    result = run(
        p,
        root=tmp_path / "inputs",
        ledger=b,
        reconciled=r,
        replays=replays(p),
        run_id="test",
        clock=lambda: OFF,
    )
    assert result["report"]["GO1"]["requested"] == 12
    assert result["report"]["GO1"]["well_formed"] == 12
    assert result["report"]["GO1"]["data_checkable"] == 12
    assert result["report"]["GO2"]["status"] == "descriptive_only"
    assert len(result["cards"]) == 12
    assert all(
        Card.from_dict(c).to_dict()["status"] == "checked:inconclusive"
        for c in result["cards"]
    )
    attempts = b.snapshot()["attempts"]
    sent = [a for a in attempts if a["state"] == "settled"]
    assert len(sent) == 9 and all(a["phase"] == "P1" for a in attempts)
    assert all(a["reserved"] >= a["actual"] > 0 for a in sent)
    assert result["worst_case_micro_usd"] == 9 * 8192
    for f in (tmp_path / "mve/generated").rglob("request.json"):
        payload = json.loads(f.read_text())
        assert "withheld secret" not in f.read_text()
        assert (
            "deep_link" not in payload["prompt"]
            and "source_block_id" not in payload["prompt"]
        )
    with pytest.raises(ValueError, match="reconciled"):
        run(
            p,
            root=tmp_path / "inputs",
            ledger=b,
            reconciled=r,
            replays=replays(p),
            run_id="stale",
            clock=lambda: OFF,
        )


def test_missing_reconciliation_and_owner_placeholders(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch)
    for invalid in (None, {**r, "remaining_micro_usd": 0}, {**r, "reconciled": False}):
        with pytest.raises(ValueError, match="reconciled"):
            run(
                p,
                root=tmp_path / "inputs",
                ledger=b,
                reconciled=invalid,
                replays=replays(p),
                run_id="no",
                clock=lambda: OFF,
            )
    assert not b.snapshot()["attempts"]
    with pytest.raises(ValueError, match="owner Q2 unanswered"):
        second_model()
    with pytest.raises(ValueError, match="owner Q2 unanswered"):
        run(
            p,
            root=tmp_path / "inputs",
            ledger=b,
            reconciled=r,
            replays={},
            run_id="no",
            observer="model:O-M2",
        )


def test_malformed_refusal_and_transport_denominators(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch)
    replay = replays(p)
    keys = list(replay)
    replay[keys[0]] = (Replay(("timeout", "timeout")), replay[keys[0]][1])
    replay[keys[1]] = (replay[keys[1]][0], Replay((mutate_reply(refusal="refused"),)))
    replay[keys[2]] = (
        replay[keys[2]][0],
        Replay((mutate_reply(content={"cards": [{}, None]}),)),
    )
    result = run(
        p,
        root=tmp_path / "inputs",
        ledger=b,
        reconciled=r,
        replays=replay,
        run_id="bad",
        clock=lambda: OFF,
    )
    assert result["report"]["GO1"]["requested"] == 12
    assert result["report"]["GO1"]["well_formed"] == 3
    assert len(result["slots"]) == 12
    assert sum(a["state"] == "dispatched" for a in b.snapshot()["attempts"]) == 2


def test_budget_and_nonfake_refusal_before_dispatch(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch, 2)
    replay = replays(p)
    key = next(iter(replay))
    replay[key] = (object(), replay[key][1])
    with pytest.raises(ValueError, match="Replay"):
        run(
            p,
            root=tmp_path / "inputs",
            ledger=b,
            reconciled=r,
            replays=replay,
            run_id="bad",
            clock=lambda: OFF,
        )
    assert not b.snapshot()["attempts"]


def test_human_intake_uses_card_api_and_excludes_unblinded():
    c = Card.from_json(Path("tests/mve/observer/fixtures/H1.json").read_text())
    result = human_cards([c.to_dict()])
    assert (
        result["cards"][0] == c.to_dict()
        and result["GO2"] == "excluded: owner Q6 unanswered"
    )
    with pytest.raises(ValueError):
        human_cards([{}])


def test_retry_replacement_frozen_ledger_and_reservation_tickets(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch, 2)
    replay = replays(p)
    key = next(iter(replay))
    good = replay[key]
    replay[key] = (
        good[0],
        Replay((mutate_reply(content={"cards": "wrong"}), good[1].entries[0])),
    )
    result = run(
        p,
        root=tmp_path / "inputs",
        ledger=b,
        reconciled=r,
        replays=replay,
        run_id="retry",
        clock=lambda: OFF,
    )
    assert len(result["slots"]) == 12 and len(result["cards"]) == 12
    attempts = b.snapshot()["attempts"]
    assert sum(a["state"] == "settled" for a in attempts) == 10
    assert result["worst_case_micro_usd"] == 27 * 8192
    assert all(a["state"] in ("settled", "cancelled") for a in attempts)
    assert len([a for a in attempts if ":reserve:" in a["id"]]) == 27


def test_model_mismatch_stops_dispatch_keeps_denominators(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch)
    replay = replays(p)
    key = next(iter(replay))
    replay[key] = (Replay((mutate_reply(model="wrong"),)), replay[key][1])
    result = run(
        p,
        root=tmp_path / "inputs",
        ledger=b,
        reconciled=r,
        replays=replay,
        run_id="frozen",
        clock=lambda: OFF,
    )
    assert result["report"]["GO1"]["requested"] == 12
    assert result["report"]["GO1"]["well_formed"] == 3
    assert b.snapshot()["frozen"]
    assert sum(a["state"] == "settled" for a in b.snapshot()["attempts"]) == 1


def test_exhausted_replay_and_check_failure(tmp_path, monkeypatch):
    from mve.observer.run import make_card, check_card

    p, b, r = setup(tmp_path, monkeypatch)
    replay = replays(p)
    key = next(iter(replay))
    replay[key] = (Replay((mutate_reply(),)), replay[key][1])
    result = run(
        p,
        root=tmp_path / "inputs",
        ledger=b,
        reconciled=r,
        replays=replay,
        run_id="exhausted",
        clock=lambda: OFF,
    )
    assert result["report"]["GO1"]["well_formed"] == 9
    d = p.to_dict()
    job = d["jobs"][0]
    card = make_card(
        d["config"]["image_free"]["zero spacings"][0],
        job=job,
        plan=p,
        observer="model:O-DS",
        call_ids=["fake"],
        slot=0,
    )
    checked, ok = check_card(card, root=tmp_path / "inputs", blocks={})
    assert not ok and checked.to_dict()["status"] == "frozen"


def test_full_budget_cap_and_frozen_design_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    m, c = fixture(tmp_path / "inputs", 4)
    p = allocate(m, tmp_path / "inputs", c)
    (tmp_path / "mve").mkdir(exist_ok=True)
    lock = tmp_path / "mve/DEPS.lock"
    lock.write_text(json.dumps({"packets": {"WO-4": {"frozen_design_sha256s": []}}}))
    b = book(tmp_path / "mve/generated")
    r = reconciliation(b, provider_records=[])
    kwargs = dict(
        root=tmp_path / "inputs",
        ledger=b,
        reconciled=r,
        replays=replays(p),
        run_id="budget",
        clock=lambda: OFF,
    )
    with pytest.raises(ValueError, match="DEPS.lock"):
        run(p, **kwargs)
    lock.write_text(
        json.dumps(
            {"packets": {"WO-4": {"frozen_design_sha256s": [p.to_dict()["sha256"]]}}}
        )
    )
    with pytest.raises(ValueError, match="0.25"):
        run(p, **kwargs)
    assert not b.snapshot()["attempts"]


def test_cli_has_no_live_mode():
    from mve.observer.run import main

    with pytest.raises(SystemExit):
        main(["--live"])


def test_offline_cli(tmp_path, monkeypatch, capsys):
    from mve.observer.run import main

    p, b, r = setup(tmp_path, monkeypatch)
    data = {
        "design": p.to_dict(),
        "input_root": "inputs",
        "ledger": "ledger.sqlite",
        "prices": prices(),
        "reconciliation": r,
        "run_id": "cli",
        "fixture_time": OFF.isoformat(),
        "replays": {
            key: [
                [
                    {"raw": e.raw.decode(), "billed_usd": e.billed_usd}
                    for e in rep.entries
                ]
                for rep in pair
            ]
            for key, pair in replays(p).items()
        },
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(data))
    assert main(["--request", str(path)]) == 0
    assert '"hosted_calls": 0' in capsys.readouterr().out


def test_disk_drop_aborts_before_dispatch(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch)
    real = storage.disk_guard

    def drop(generated, incoming=0):
        if incoming == 6 * 1024**2:
            raise storage.DiskLimitError("disk_free")
        return real(generated, incoming)

    monkeypatch.setattr(storage, "disk_guard", drop)
    with pytest.raises(storage.DiskLimitError):
        run(
            p,
            root=tmp_path / "inputs",
            ledger=b,
            reconciled=r,
            replays=replays(p),
            run_id="disk",
            clock=lambda: OFF,
        )
    assert not any(
        a["state"] in ("dispatched", "settled") for a in b.snapshot()["attempts"]
    )
    assert all(a["state"] == "cancelled" for a in b.snapshot()["attempts"])


def test_provider_reconciliation_needs_matching_rows(tmp_path, monkeypatch):
    p, b, r = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="provider usage"):
        reconciliation(
            b, provider_records=[{"attempt": "unknown", "billed_micro_usd": 1}]
        )
    r["provider_records_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="reconciled"):
        run(
            p,
            root=tmp_path / "inputs",
            ledger=b,
            reconciled=r,
            replays=replays(p),
            run_id="forged",
            clock=lambda: OFF,
        )
