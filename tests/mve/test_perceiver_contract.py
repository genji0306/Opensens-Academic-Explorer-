import json
import pytest
from mve.perceiver import ImageInput, Replay
from mve.perceiver.parsing import parse
from mve.preflight.probe_contract import ProbeReply, ProbeRefused
from tests.mve.perceiver_helpers import content, mutate_reply, run, reply, book


@pytest.mark.parametrize(
    "entries",
    [
        [],
        (),
        ("unknown",),
        (object(),),
        (ProbeReply("text"),),
        (ProbeReply(b"x" * 1_048_577),),
        (ProbeReply(b"{}", 5),),
        tuple(["timeout"] * 7),
    ],
)
def test_only_bounded_immutable_replays(entries):
    with pytest.raises(ProbeRefused):
        Replay(entries)


def test_exhausted_replay_never_allocates_another_attempt(tmp_path):
    ledger = book(tmp_path)
    with pytest.raises(ProbeRefused, match="exhausted"):
        run(tmp_path, [reply()], ledger=ledger)
    assert len(ledger.snapshot()["attempts"]) == 1


@pytest.mark.parametrize(
    "track,task",
    [
        ("unknown", "appearance"),
        ("appearance_only", "annotation_reading"),
        ("annotated_problem", "unknown"),
    ],
)
def test_task_contract(track, task):
    with pytest.raises(ProbeRefused):
        ImageInput(b"bad", track, task).request()


def test_invalid_code_sha(tmp_path):
    with pytest.raises(ProbeRefused, match="code sha"):
        run(tmp_path, code_sha="no")


@pytest.mark.parametrize(
    "text",
    [
        '{"entities":[],"entities":[],"observations":[]}',
        '{"entities":NaN,"observations":[]}',
        "{}",
        "null",
    ],
)
def test_json_is_strict(text):
    assert parse(mutate_reply(content=text).raw, 288, 288)["status"] == "malformed"


@pytest.mark.parametrize(
    "kind,params,pieces",
    [
        ("point", [10, 20], None),
        ("crossing", [10, 20], None),
        ("segment", [10, 20, 40, 50], None),
        ("line", [10, 20, 40, 50], None),
        ("ray", [10, 20, 40, 50], None),
        ("circle", [50, 50, 10], None),
        ("arc", [50, 50, 10, 0, 90], None),
        ("polygon", [10, 10, 40, 10, 40, 40], None),
        ("curve", [10, 10, 40, 10, 40, 40], None),
        ("region", [10, 10, 40, 10, 40, 40], None),
        ("strand", [10, 10, 40, 10, 40, 40], [[10, 10, 20, 10], [30, 10, 40, 10]]),
        ("tick", [10, 10, 4, 4], None),
        ("arrow", [10, 10, 4, 4], None),
        ("angle_mark", [10, 10, 4, 4], None),
        ("right_angle_mark", [10, 10, 4, 4], None),
    ],
)
def test_geometry_kinds_validate_roundtrip_and_align(tmp_path, kind, params, pieces):
    e = {"id": "x", "label": None, "kind": kind, "params": params}
    if pieces is not None:
        e["pieces"] = pieces
    response = mutate_reply(content={"entities": [e], "observations": []})
    result = run(tmp_path, [response, response])
    assert result.record is not None
    assert result.report()["alignment"]["matches"][0]["distance"] == 0
    assert result.record.to_dict()["entities"][0]["geometries"][0]["params"] == params


@pytest.mark.parametrize(
    "change,status",
    [
        (lambda c: c["entities"][0].update(kind="unknown"), "malformed"),
        (
            lambda c: c["entities"][0].update(kind="circle", params=[10, 10, 0]),
            "malformed",
        ),
        (
            lambda c: c["entities"][0].update(kind="tick", params=[280, 280, 20, 20]),
            "out_of_image",
        ),
        (
            lambda c: c["entities"][0].update(
                kind="strand", params=[1, 1, 2, 2, 3, 3], pieces=[[0, 0, 999, 999]]
            ),
            "out_of_image",
        ),
        (
            lambda c: c["observations"][0]["proposition"].update(pred="Unknown"),
            "malformed",
        ),
        (lambda c: c["observations"][0]["proposition"].update(args=["A"]), "malformed"),
        (lambda c: c["entities"][0].update(kind="crossing"), "malformed"),
    ],
)
def test_invalid_geometry_or_proposition(change, status):
    c = content()
    change(c)
    assert parse(mutate_reply(content=c).raw, 288, 288)["status"] == status


def test_reasoning_channel_is_rejected():
    body = json.loads(reply().raw)
    body["choices"][0]["message"]["reasoning_content"] = "reasoning not requested"
    assert parse(json.dumps(body).encode(), 288, 288)["status"] == "malformed"


def test_extreme_number_becomes_malformed_instead_of_escaping_after_dispatch(tmp_path):
    c = content()
    c["entities"][0]["params"] = [10**400, 0]
    result = run(tmp_path, [mutate_reply(content=c), reply(2)], retries=0)
    assert result.report()["calls"][0]["status"] == "malformed"
