"""WP-8a contract tests, authored before implementation."""

from copy import deepcopy
import pytest
from mve.errors import RecordError
from mve.record import Record, transition
from mve.graph import nodes
from mve.verdicts import capture, propose, revise
from tests.mve.fixtures import populated
from tests.mve.test_authority import AT, checked, proof


def record():
    data = populated()
    prop = data["observations"][0]["proposition"]
    data["measurements"] = [
        {
            "id": "mea_1",
            "proposition": prop,
            "method": "coordinate_consistency",
            "outcome": "consistent",
            "residual": 0,
            "tolerance": 1,
            "residual_unit": "px",
            "kernel": "fixture",
            "depends_on": ["geo_1", "geo_2", "geo_3", "obs_1"],
        }
    ]
    data["derivations"] = [
        {
            "id": "der_1",
            "engine": "fixture",
            "target": prop,
            "outcome": "unknown",
            "depends_on": ["prm_1"],
            "budget_s": 1,
        }
    ]
    return Record.from_dict(data)


def verdict(r, target="obs_1", value="confirm", actor="human:alice", **kw):
    return capture(
        r,
        target=target,
        verdict=value,
        actor=actor,
        from_revision=r.to_dict()["revision"],
        at=AT,
        **kw,
    )


@pytest.mark.parametrize("target", ["obs_1", "mea_1", "der_1", "jud_1", "can_1"])
def test_targets_and_only_adopt_authorizes(target):
    r = record()
    r = verdict(r)
    r = propose(
        r,
        proposition=populated()["observations"][0]["proposition"],
        actor="model:manager",
        from_revision=2,
        at=AT,
        text="Three points align",
    )
    original = r.to_json()
    for value in ["confirm", "reject", "not_visible", "unsure", "decline"]:
        out = verdict(r, target, value).to_dict()
        assert not out["assumptions"]
        assert out["judgments"][-1]["depends_on"] == [target]
        assert out["judgments"][-1]["judge"] == "human:alice"
        assert out["judgments"][-1]["at"] == AT
        assert out["events"][-1]["from_revision"] == 3
    assert r.to_json() == original


@pytest.mark.parametrize("target", ["obs_1", "mea_1", "der_1", "can_1"])
def test_adoption_and_transitive_invalidation(target):
    r = propose(
        record(),
        proposition=populated()["observations"][0]["proposition"],
        actor="human:alice",
        from_revision=1,
        at=AT,
    )
    r = verdict(r, target, "adopt")
    data = r.to_dict()
    assert data["revision"] == 4  # judge + adopt are existing transitions, returned atomically
    assert data["assumptions"][0]["depends_on"] == ["jud_1"]
    assert data["assumptions"][0]["adopted_by"] == "human:alice"
    formal = checked()["formal"]
    formal.update(
        status="proved",
        proof=proof(),
        render_back={
            "id": "rnd_1",
            "renderer": "fixture",
            "realizations": "one",
            "sha256": "6" * 64,
            "depends_on": ["tc_1"],
        },
    )
    data.update(formal=formal, stage="proved")
    data["versions"].update(lean_lock_sha="3" * 64, lean_toolchain="lean4:v4.29.0")
    r = Record.from_dict(data)
    out = revise(
        r, judgment="jud_1", verdict="reject", actor="human:alice", from_revision=4, at=AT
    ).to_dict()
    graph = nodes(out)
    for key in ["asm_1", "prop_1", "tc_1", "prf_1", "rnd_1"]:
        assert graph[key]["valid"] is False
        assert key in out["events"][-1]["invalidates"]
    assert graph["jud_1"]["verdict"] == "reject"


def test_changed_candidate_invalidates_judgment_and_assumption():
    r = propose(
        record(),
        proposition=populated()["observations"][0]["proposition"],
        actor="human:alice",
        from_revision=1,
        at=AT,
    )
    r = verdict(r, "can_1", "adopt")
    out = transition(
        r,
        "edit",
        actor="human:alice",
        expected_revision=4,
        at=AT,
        payload={"patch": [{"op": "replace", "path": "/candidates/0/text", "value": "changed"}]},
    ).to_dict()
    assert set(out["events"][-1]["invalidates"]) == {"jud_1", "asm_1"}
    with pytest.raises(RecordError):
        verdict(Record.from_dict(out), "jud_1")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"actor": "model:manager", "verdict": "adopt"},
        {"actor": "model:manager", "verdict": "decline"},
        {"actor": "alice"},
        {"actor": "human:"},
        {"actor": "audit:alice"},
        {"target": "geo_1"},
        {"target": "obs_999"},
        {"from_revision": 0},
        {"at": "yesterday"},
        {"verdict": "human_confirmed"},
        {"question": "Q-claim-workflow", "verdict": "confirm"},
        {"verdict": "label", "question": "Q-claim-workflow", "label": "confirm"},
        {"verdict": "label", "question": "Q-missing", "label": "yes"},
        {"verdict": "confirm", "label": "restates_measured"},
    ],
)
def test_refusals_are_immutable(kwargs):
    r = record()
    args = dict(target="obs_1", verdict="confirm", actor="human:alice", from_revision=1, at=AT)
    args.update(kwargs)
    with pytest.raises(RecordError):
        capture(r, **args)
    assert r.to_dict()["revision"] == 1


def test_revise_cannot_impersonate_and_requires_current_revision():
    r = verdict(record())
    for actor, rev in [("model:alice", 2), ("human:bob", 2), ("human:alice", 1)]:
        with pytest.raises(RecordError):
            revise(r, judgment="jud_1", verdict="reject", actor=actor, from_revision=rev, at=AT)
    with pytest.raises(RecordError):
        verdict(r, "jud_1", "adopt")


def test_proposal_does_not_authorize_and_entities_are_dependencies():
    r = propose(
        record(),
        proposition=populated()["observations"][0]["proposition"],
        actor="human:alice",
        from_revision=1,
        at=AT,
    )
    data = r.to_dict()
    assert data["candidates"][0]["depends_on"] == ["ent_1", "ent_2", "ent_3"]
    assert not data["assumptions"] and not data["formal"]["propositions"]
    d = checked()
    d["candidates"] = data["candidates"]
    d["formal"]["propositions"][0]["depends_on"] = ["can_1"]
    with pytest.raises(RecordError):
        Record.from_dict(d)
    d = deepcopy(data)
    d["candidates"][0]["depends_on"] = []
    with pytest.raises(RecordError):
        Record.from_dict(d)


@pytest.mark.parametrize("at", ["yesterday", "2026-09-27T01:00:00", "2026-99-27T01:00:00Z"])
def test_timestamps_are_checked_without_optional_jsonschema_format_packages(at):
    with pytest.raises(RecordError):
        capture(
            record(), target="obs_1", verdict="confirm", actor="human:alice", from_revision=1, at=at
        )


@pytest.mark.parametrize(
    "actor,field,value",
    [
        ("human:alice", "judge", "human:bob"),
        ("human:bob", "verdict", "reject"),
    ],
)
def test_generic_edits_cannot_rewrite_judge_identity(actor, field, value):
    r = verdict(record())
    with pytest.raises(RecordError):
        transition(
            r,
            "edit",
            actor=actor,
            expected_revision=2,
            at=AT,
            payload={"patch": [{"op": "replace", "path": f"/judgments/0/{field}", "value": value}]},
        )


def test_actor_identity_and_mathematical_identity_survive_roundtrip():
    r = record()
    original = r.to_dict()
    r = verdict(r, value="adopt", actor="human:Alice.Smith")
    data = Record.from_json(r.to_json()).to_dict()
    assert data["assumptions"][0]["adopted_by"] == "human:Alice.Smith"
    assert data["judgments"][0]["judge"] == "human:Alice.Smith"
    assert (data["record_id"], data["content_hash"]) == (
        original["record_id"],
        original["content_hash"],
    )
    with pytest.raises(RecordError):
        propose(
            r,
            proposition=original["observations"][0]["proposition"],
            actor="human:alice",
            from_revision=1,
            at=AT,
        )
