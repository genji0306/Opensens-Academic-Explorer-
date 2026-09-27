import copy
import json
from pathlib import Path

import pytest

from mve.errors import RecordError
from mve.observer.card import Card, card_hash, spec_hash, go1
from mve.formal import check_authorization
from mve.validation import check_adoptions, check_derivations, check_problem
from mve.formalizer.ir import build_ir
from tests.mve.fixtures import populated

FIXTURES = Path("tests/mve/observer/fixtures")


def draft():
    d = json.loads((FIXTURES / "H0.json").read_text())
    d["status"] = "draft"
    d["artifacts"] = []
    d["judgments"] = []
    return Card.from_dict(d)


def test_fixtures_and_immutable_roundtrip():
    for name, status in [("H0", "inconclusive"), ("H1", "baseline_explained")]:
        card = Card.from_json((FIXTURES / f"{name}.json").read_text())
        assert card.to_dict()["status"] == "checked:" + status
        assert not card.handoff_eligible()
        d = card.to_dict()
        d["claim"] = "changed"
        assert card.to_dict()["claim"] != d["claim"]


@pytest.mark.parametrize(
    "field",
    [
        "prediction",
        "primary_statistic",
        "check_spec",
        "sources",
        "observer",
        "resemblance_target",
    ],
)
def test_revision_invalidates_transitively(field):
    card = (
        draft().transition("well_formed").transition("frozen").transition("preliminary")
    )
    d = card.to_dict()
    root = f"{d['card_id']}@{d['revision']}:{d['content_hash']}"
    d["artifacts"] = [
        dict(id="check_1", depends_on=[root], valid=True),
        dict(id="adoption_1", depends_on=["check_1"], valid=True),
        dict(id="handoff_1", depends_on=["adoption_1"], valid=True),
    ]
    card = Card.from_dict(d)
    value = copy.deepcopy(d[field])
    if field == "check_spec":
        value["seed"] += 1
    elif field == "sources":
        value[0]["data_sha256"] = "a" * 64
    elif field == "observer":
        value["id"] = "human:other"
    elif field == "resemblance_target":
        value["mapping"] += " revised"
    else:
        value += " revised"
    revised = card.revise({field: value}, expected_revision=1)
    assert revised.to_dict()["content_hash"] != d["content_hash"]
    assert revised.to_dict()["status"] == "draft"
    assert all(not a["valid"] for a in revised.to_dict()["artifacts"])
    assert card.to_dict()["artifacts"][0]["valid"]


@pytest.mark.parametrize(
    "defect",
    [
        "vague",
        "kill",
        "spec",
        "hash",
        "model_human",
        "model_adopt",
        "split",
        "source",
        "double_observer",
    ],
)
def test_card_negatives(defect):
    d = draft().to_dict()
    if defect == "vague":
        d["testable_form"] = "looks structured"
    elif defect == "kill":
        del d["kill_criterion"]
    elif defect == "spec":
        del d["check_spec"]
    elif defect == "hash":
        d["content_hash"] = "f" * 64
    elif defect == "model_human":
        d["observer"]["kind"] = "model"
    elif defect == "model_adopt":
        d["judgments"] = [
            dict(
                id="jud_1",
                actor="model:x",
                verdict="adopt",
                weight=0.5,
                card_id=d["card_id"],
                revision=1,
                content_hash=d["content_hash"],
                depends_on=[],
                valid=True,
            )
        ]
    elif defect == "split":
        d["check_spec"]["kill_rule"]["components"][1]["alpha"] = 0.05
    elif defect == "source":
        d["sources"][0]["data_sha256"] = "unknown"
    else:
        d["observer"] = [d["observer"], d["observer"]]
    with pytest.raises(RecordError):
        Card.from_dict(d)


def test_lifecycle_and_go1():
    card = draft()
    with pytest.raises(RecordError):
        card.transition("preliminary")
    card = card.transition("well_formed").transition("frozen").transition("preliminary")
    assert card.to_dict()["status"] == "preliminary"
    with pytest.raises(RecordError):
        card.transition("adopted")
    with pytest.raises(RecordError):
        card.revise({"prediction": "x"}, expected_revision=0)
    result = go1(
        {"human:owner": [[card.to_dict(), None, "{broken"], [], ["refusal"]]},
        slots_per_view=3,
    )
    assert result["human:owner"]["requested"] == 9
    assert result["human:owner"]["well_formed"] == 1
    assert result["human:owner"]["data_checkable"] == 0


@pytest.mark.parametrize("transitive", [False, True])
@pytest.mark.parametrize(
    "path", ["proposition", "assumption", "derivation", "problem", "formalizer"]
)
def test_hypotheses_never_authorize(path, transitive):
    d = populated()
    from mve.graph import nodes

    graph = nodes(d)
    graph["hyp_1"] = dict(id="hyp_1", depends_on=[])
    graph["jud_999"] = dict(id="jud_999", depends_on=["hyp_1"])
    refs = ["jud_999" if transitive else "hyp_1"]
    if path == "proposition":
        node = dict(depends_on=refs)

        def call():
            return check_authorization(node, d, graph)
    elif path == "assumption":
        d["assumptions"] = [dict(id="asm_999", depends_on=refs)]

        def call():
            return check_adoptions(d, graph)
    elif path == "derivation":
        d["derivations"] = [dict(id="der_999", depends_on=refs)]

        def call():
            return check_derivations(d, graph)
    elif path == "problem":
        d["problem"]["premises"][0]["depends_on"] = refs

        def call():
            return check_problem(d, graph)
    else:
        d["sources"][0]["depends_on"] = ["hyp_1"]

        class Unchecked:
            def to_dict(self):
                return d

        def call():
            return build_ir(Unchecked())

    with pytest.raises(RecordError, match="hypothesis"):
        call()


def prospective():
    d = draft().to_dict()
    d["context"]["retrospective"] = False
    d["context"]["original_png_available"] = True
    for src in d["sources"]:
        src["png_sha256"] = "d" * 64
    d["content_hash"] = card_hash(d)
    return Card.from_dict(d)


def test_handoff_current_human_survivor_only_and_full_lifecycle():
    from mve.observer.card import binding

    card = (
        prospective()
        .transition("well_formed")
        .transition("frozen")
        .transition("preliminary")
    )
    d = card.to_dict()
    receipt = dict(
        **binding(d),
        status="baseline_exceeding_survivor",
        inferential=True,
        spec_sha256=d["check_spec"]["spec_sha256"],
    )
    card = card.transition("checked:baseline_exceeding_survivor", receipt=receipt)
    assert not card.handoff_eligible()
    model = card.judge("model:a", "confirm")
    assert (
        model.to_dict()["judgments"][0]["weight"] == 0.5
        and not model.handoff_eligible()
    )
    with pytest.raises(RecordError):
        card.judge("model:a", "adopt")
    card = card.judge("human:reviewer", "adopt")
    assert card.handoff_eligible()
    card = card.transition("adopted").transition("handed_off")
    with pytest.raises(RecordError):
        card.transition("lane_verdict:supported")
    card = card.transition(
        "lane_verdict:supported", receipt={"verdict": "supported"}
    ).transition("reported")
    edited = card.revise(
        {"prediction": "Changed quantitative prediction"}, expected_revision=1
    )
    assert not edited.handoff_eligible()
    assert all(not j["valid"] for j in edited.to_dict()["judgments"])
    assert all(not a["valid"] for a in edited.to_dict()["artifacts"])


def test_judgment_bindings_go1_identity_and_empty_cases():
    from mve.observer.card import binding

    card = draft().judge("human:a", "unsure")
    with pytest.raises(RecordError):
        draft().judge("audit:a", "confirm")
    d = card.to_dict()
    d["judgments"][0]["weight"] = 0.5
    with pytest.raises(RecordError):
        Card.from_dict(d)
    d = card.to_dict()
    d["judgments"][0]["revision"] = 2
    with pytest.raises(RecordError):
        Card.from_dict(d)
    d = draft().to_dict()
    result = go1(
        {"human:owner": [[json.dumps(d)]]},
        slots_per_view=1,
        human_checkable=[tuple(binding(d).values())],
    )
    assert result["human:owner"]["passed"]
    assert (
        go1({"model:other": [[d]]}, slots_per_view=1)["model:other"]["well_formed"] == 0
    )
    assert (
        go1({"human:owner": []}, slots_per_view=1)["human:owner"]["well_formed_rate"]
        is None
    )
    with pytest.raises(RecordError):
        go1({}, slots_per_view=0)
    with pytest.raises(RecordError):
        go1({"human:owner": [[d, d]]}, slots_per_view=1)
    with pytest.raises(RecordError):
        draft().revise({"status": "adopted"}, expected_revision=1)
    with pytest.raises(RecordError):
        draft().revise({"prediction": d["prediction"]}, expected_revision=1)
    with pytest.raises(RecordError):
        Card.from_dict(dict(d, claim=float("nan")))
    with pytest.raises(RecordError):
        Card.from_json('{"claim":"a","claim":"b"}')


@pytest.mark.parametrize(
    "field",
    ["alpha", "baselines", "fitting_interval", "development", "observer", "history"],
)
def test_semantic_negatives_rehashed(field):
    d = draft().to_dict()
    if field == "alpha":
        d["check_spec"]["alpha"] = 0.1
    elif field == "baselines":
        d["check_spec"]["baselines"][0]["role"] = "secondary"
    elif field == "fitting_interval":
        d["check_spec"][field] = [1, 0.3]
    elif field == "development":
        d["check_spec"]["replication"][0] = copy.deepcopy(
            d["check_spec"]["development"][0]
        )
    elif field == "observer":
        d["observer"]["model_id"] = "not-human"
    else:
        d["revision"] = 2
    d["check_spec"]["spec_sha256"] = spec_hash(d["check_spec"])
    d["content_hash"] = card_hash(d)
    with pytest.raises(RecordError):
        Card.from_dict(d)


@pytest.mark.parametrize("entry", ["emit", "formal_payload"])
@pytest.mark.parametrize("field", ["evidence", "source_refs"])
def test_direct_ir_entrypoints_reject_hypotheses(entry, field):
    from mve.formalizer.emitter import emit
    from mve.formalizer.runtime import formal_payload
    from mve.record import Record

    ir = build_ir(Record.from_dict(populated()))
    ir["premises"][0][field] = "hyp_1" if field == "evidence" else ["hyp_1"]
    with pytest.raises(RecordError, match="hypothesis"):
        emit(ir) if entry == "emit" else formal_payload(ir, "unused")


def test_nominal_receipt_cannot_kill():
    from mve.observer.card import binding

    card = (
        draft().transition("well_formed").transition("frozen").transition("preliminary")
    )
    d = card.to_dict()
    receipt = dict(
        **binding(d),
        status="killed",
        inferential=False,
        spec_sha256=d["check_spec"]["spec_sha256"],
    )
    with pytest.raises(RecordError, match="nominal"):
        card.transition("checked:killed", receipt=receipt)
