import json
from copy import deepcopy
from pathlib import Path
import pytest
from mve.observer.outbox import (
    Outbox,
    validate_bundle,
    proposal_status,
    packet_hash,
    relay,
)
from mve.observer.storage import disk_guard
from tests.mve.observer.test_cards import draft
from mve.observer.card import Card, binding


def survivor():
    d = draft().to_dict()
    d["context"]["retrospective"] = False
    d["context"]["original_png_available"] = True
    for source in d["sources"]:
        source["png_sha256"] = "b" * 64
    from mve.observer.card import card_hash

    d["content_hash"] = card_hash(d)
    c = (
        Card.from_dict(d)
        .transition("well_formed")
        .transition("frozen")
        .transition("preliminary")
    )
    d = c.to_dict()
    r = {
        **binding(d),
        "spec_sha256": d["check_spec"]["spec_sha256"],
        "status": "baseline_exceeding_survivor",
        "inferential": True,
    }
    return c.transition("checked:baseline_exceeding_survivor", receipt=r).judge(
        "human:owner", "adopt"
    )


@pytest.fixture
def outbox(monkeypatch, tmp_path):
    # Testing uses the same fixed-root guard, rooted in a disposable worktree analogue.
    import mve.observer.storage as s

    monkeypatch.setattr(s, "WORKTREE", tmp_path)
    return Outbox()


@pytest.mark.parametrize("name,status", [("H0", "inconclusive"), ("H1", "completed")])
def test_archival_bundles_schema_and_artifacts(outbox, name, status):
    c = Card.from_json(Path(f"tests/mve/observer/fixtures/{name}.json").read_text())
    p = outbox.result(
        c, run_id="fixture-" + name, reproduce="python3 -m mve.observer --help"
    )
    b = json.loads(p.read_text())
    assert b["status"] == status and b["review"]["state"] == "unreviewed"
    assert proposal_status() in b["limitations"]
    validate_bundle(b, outbox.root / "atlas")
    for a in b["artifacts"]:
        assert (outbox.root / "atlas" / a["path"]).is_file()
    with pytest.raises(FileExistsError):
        outbox.result(c, run_id="fixture-" + name, reproduce="record only")


def test_handshake_rounds_hash_and_adoption(outbox):
    c = survivor()
    p = outbox.submission(
        c, reviewer="opus", commit="a" * 40, submitted_at="2026-09-28T00:00:00+00:00"
    )
    first = json.loads(p.read_text())
    assert first["work_id"] == "mve-card-" + c.to_dict()["card_id"]
    assert first["packet_type"] == "attack_lane_proposal" and first[
        "packet_hash"
    ] == packet_hash(first)
    assert first["round"] == 1 and first["supersedes"] is None
    revised = c.revise({"prediction": "A different prediction"}, expected_revision=1)
    d = revised.to_dict()
    revised = (
        revised.transition("well_formed").transition("frozen").transition("preliminary")
    )
    r = {
        **binding(d),
        "spec_sha256": d["check_spec"]["spec_sha256"],
        "status": "baseline_exceeding_survivor",
        "inferential": True,
    }
    revised = revised.transition(
        "checked:baseline_exceeding_survivor", receipt=r
    ).judge("human:owner", "adopt")
    q = outbox.submission(
        revised,
        reviewer="opus",
        commit="b" * 40,
        submitted_at="2026-09-28T00:00:00+00:00",
    )
    second = json.loads(q.read_text())
    assert (
        second["round"] == 2
        and second["work_id"] == first["work_id"]
        and second["supersedes"] == first["review_id"]
    )
    with pytest.raises(ValueError):
        outbox.submission(
            draft(),
            reviewer="opus",
            commit="a" * 40,
            submitted_at="2026-09-28T00:00:00Z",
        )
    with pytest.raises(ValueError, match="technical_failure"):
        outbox.result(
            c, run_id="failure", outcome="technical_failure", reproduce="none"
        )
    assert not list(outbox.root.rglob("*failure*"))


def test_bundle_adversarial_validation(outbox):
    p = outbox.result(survivor(), run_id="r", reproduce="never executed")
    good = json.loads(p.read_text())
    for mutate in [
        lambda b: b.pop("method"),
        lambda b: b["review"].update(state="accepted"),
        lambda b: b["artifacts"][0].update(path="../escape"),
        lambda b: b["sources"][0].update(path="~/escape"),
        lambda b: b["artifacts"][0].update(sha256="a" * 64),
        lambda b: b.update(status="technical_failure"),
    ]:
        b = deepcopy(good)
        mutate(b)
        with pytest.raises(ValueError):
            validate_bundle(b, outbox.root / "atlas")


def test_outbox_refuses_escape_symlink_and_relay(outbox, tmp_path):
    for name in ("../bad", "/tmp/bad", "~bad", "a/b"):
        with pytest.raises(ValueError):
            outbox.result(survivor(), run_id=name, reproduce="none")
    for answers in ({}, {"Q3": "answered", "Q4": "answered", "Q5": "answered"}):
        with pytest.raises(ValueError, match="relay"):
            relay(answers)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    outbox.root.parent.mkdir(parents=True, exist_ok=True)
    outbox.root.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        outbox.result(survivor(), run_id="safe", reproduce="none")


def test_disk_limit(monkeypatch, tmp_path):
    import mve.observer.storage as s

    monkeypatch.setattr(s.shutil, "disk_usage", lambda _: (10**11, 0, 1))
    with pytest.raises(ValueError, match="5 GiB"):
        disk_guard(tmp_path, 1)
    monkeypatch.setattr(s.shutil, "disk_usage", lambda _: (10**11, 0, 10**11))
    monkeypatch.setattr(s, "tree_bytes", lambda _: 200 * 1024**2)
    with pytest.raises(ValueError, match="200 MiB"):
        disk_guard(tmp_path, 1)


def test_outbox_refusals_before_writes(outbox, monkeypatch):
    from mve.observer import outbox as o

    c = survivor()
    for kwargs in [
        dict(outcome="mystery", reproduce="none"),
        dict(outcome="replicated_observation", reproduce=""),
    ]:
        with pytest.raises(ValueError):
            outbox.result(c, run_id="invalid", **kwargs)
    unadopted = c.to_dict()
    unadopted["judgments"] = []
    with pytest.raises(ValueError, match="adopted"):
        outbox.result(Card.from_dict(unadopted), run_id="unadopted", reproduce="none")
    for commit, time in [("bad", "2026-09-28T00:00:00Z"), ("a" * 40, "2026-09-28")]:
        with pytest.raises(ValueError):
            outbox.submission(c, reviewer="opus", commit=commit, submitted_at=time)
    p = outbox.result(
        c,
        run_id="r",
        outcome="replicated_observation",
        reproduce="none",
        lane_receipt={**binding(c.to_dict()), "status": "replicated_observation"},
    )
    assert "specificity undecided" in " ".join(json.loads(p.read_text())["limitations"])
    monkeypatch.setattr(o, "SCHEMA_SHA", "0" * 64)
    with pytest.raises(ValueError, match="schema hash"):
        o.validate_bundle(json.loads(p.read_text()), outbox.root / "atlas")
    with pytest.raises(ValueError, match="schema hash"):
        outbox.result(c, run_id="changed", reproduce="none")


def test_packet_history_refuses_tampering_and_stale(outbox):
    c = survivor()
    kwargs = dict(reviewer="opus", commit="a" * 40, submitted_at="2026-09-28T00:00:00Z")
    p = outbox.submission(c, **kwargs)
    with pytest.raises(ValueError, match="stale"):
        outbox.submission(c, **kwargs)
    d = json.loads(p.read_text())
    d["summary"] = "tampered"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="hash"):
        outbox.submission(c, **kwargs)


def test_storage_paths_portability_and_lock(outbox):
    from mve.observer import storage as s

    for path in ("x", "mve/generated/../x", "/tmp/outside"):
        with pytest.raises(ValueError):
            s.local(path)
    with pytest.raises(ValueError, match="nonportable"):
        s.encoded({"path": "/" + "Users/" + "fixture/file"})
    with s.lock():
        with pytest.raises(ValueError, match="another"):
            with s.lock():
                pass
