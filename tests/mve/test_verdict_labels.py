import pytest
from mve.errors import RecordError
from mve.evaluation.splits import freeze
from mve.verdicts import export_labels, revise
from tests.mve.test_verdict_capture import record, verdict
from tests.mve.test_authority import AT


def split_for(r, role="fit", sealed="sealed"):
    roles = ["development", "retrieval", "fit", "calibration", sealed]
    image = r.to_dict()["image"]["sha256"]
    frozen = freeze(
        [{"id": str(i), "family": str(i)} for i in range(5)],
        seed="labels",
        allocations={s: 1 for s in roles},
    )
    from mve.evaluation.splits import FrozenSplit, canonical

    data = frozen.manifest()
    for row in data["items"]:
        if row["split"] == role:
            row["id"] = image
    return FrozenSplit(canonical(data))


def label(r, actor="model:manager", answer="remeasure"):
    return verdict(r, value="label", actor=actor, question="Q-agree-action", label=answer)


def test_human_overrides_manager_in_both_orders_and_records_conflict():
    for human_first in [False, True]:
        r = record()
        if human_first:
            r = label(r, "human:alice", "merge")
        r = label(r)
        if not human_first:
            r = label(r, "human:alice", "merge")
        assert "label_conflict" in r.to_dict()["events"][-1]["note"]
        rows = export_labels([r], split_for(r))
        assert len(rows) == 1
        row = rows[0]
        assert row["actor_kind"] == "human" and row["actor"] == "human:alice"
        assert row["label"] == "merge" and row["weight"] == 1
        assert row["family"] and row["split"] == "fit"
        assert row["split_sha256"] == split_for(r).sha256
        assert len(row["conflicting_judgments"]) == 1


def test_manager_weight_abstention_and_visibility_not_catalogue_labels():
    r = label(record())
    assert export_labels([r], split_for(r))[0]["weight"] == 0.5
    r = verdict(r, value="not_visible")
    assert len(export_labels([r], split_for(r))) == 1
    r = verdict(r, value="unsure", question="Q-agree-action")
    assert "label_conflict" in r.to_dict()["events"][-1]["note"]
    assert export_labels([r], split_for(r)) == []  # human abstention overrides model
    r = revise(
        r,
        judgment="jud_3",
        verdict="label",
        label="human",
        actor="human:alice",
        from_revision=4,
        at=AT,
    )
    assert export_labels([r], split_for(r))[0]["label"] == "human"


@pytest.mark.parametrize(
    "role", ["development", "retrieval", "calibration", "sealed", "evaluation"]
)
def test_training_never_exports_other_splits(role):
    r = label(record())
    frozen = split_for(r, role, "evaluation" if role == "evaluation" else "sealed")
    assert export_labels([r], frozen) == []


def test_unknown_split_item_fails_closed_and_purpose_is_explicit():
    r = label(record())
    with pytest.raises(RecordError, match="split"):
        export_labels([r], split_for(record(), "fit").retire("exposed"), purpose="evaluation")
    with pytest.raises(RecordError):
        export_labels([r], split_for(r), purpose="all")
    from tests.mve.fixtures import bare
    from mve.record import Record

    with pytest.raises(RecordError, match="split"):
        export_labels([Record.from_dict(bare(2))], split_for(r))
    assert export_labels([r], split_for(r, "calibration"), purpose="calibration")


def test_labels_on_invalidated_targets_are_excluded():
    r = label(record())
    from mve.record import transition

    r = transition(
        r,
        "edit",
        actor="human:alice",
        expected_revision=2,
        at=AT,
        payload={
            "patch": [{"op": "replace", "path": "/entities/0/geometries/0/params/0", "value": 11}]
        },
    )
    assert export_labels([r], split_for(r)) == []


def test_claim_workflow_requires_free_text_target():
    with pytest.raises(RecordError):
        verdict(record(), value="label", question="Q-claim-workflow", label="discard")


def test_visibility_verdicts_export_separately_from_classifier_labels():
    from mve.verdicts import export_verdicts

    r = verdict(record(), actor="model:manager")
    r = verdict(r, value="not_visible")
    assert export_labels([r], split_for(r)) == []
    rows = export_verdicts([r], split_for(r))
    assert len(rows) == 1
    assert rows[0]["verdict"] == "not_visible" and rows[0]["abstained"] is True
    assert rows[0]["label"] is None and rows[0]["label_scope"] == "visibility"
    assert rows[0]["actor"] == "human:alice" and rows[0]["weight"] == 1
    assert rows[0]["conflicting_judgments"] == ["jud_1"]
    assert export_verdicts([r], split_for(r, "sealed")) == []


def test_synthetic_metadata_cannot_relabel_sealed_item_as_fit():
    from tests.mve.test_authority import synthetic
    from mve.record import Record

    data = synthetic()
    data["image"]["truth"]["split"] = "sealed"
    r = Record.from_dict(data)
    with pytest.raises(RecordError, match="family/split"):
        export_labels([r], split_for(r))


def test_claim_label_success_and_duplicate_export_refusal():
    from mve.verdicts import propose

    r = propose(
        record(),
        proposition=record().to_dict()["observations"][0]["proposition"],
        actor="human:Alice.Smith",
        from_revision=1,
        at=AT,
        text="A, B, C align",
    )
    r = verdict(r, target="can_1", value="label", question="Q-claim-workflow", label="discard")
    assert export_labels([r], split_for(r))[0]["label"] == "discard"
    with pytest.raises(RecordError, match="duplicate"):
        export_labels([r, r], split_for(r))


def test_latest_revision_wins_even_if_caller_timestamp_is_older():
    r = label(record(), "human:alice", "merge")
    r = label(r, "human:bob", "remeasure")
    r = revise(
        r,
        judgment="jud_1",
        verdict="label",
        label="human",
        actor="human:alice",
        from_revision=3,
        at="2025-01-01T00:00:00Z",
    )
    row = export_labels([r], split_for(r))[0]
    assert row["label"] == "human" and row["judgment_revision"] == 4
