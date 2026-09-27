import gzip
import hashlib
import json
import pytest
from mve.record import Record
from mve.errors import RecordError
from mve.predicates import canonical_proposition
from tests.mve.perceiver_helpers import ROOT, OFF, book, reply, run
from mve.perceiver import perceive, Replay
from mve.perceiver.contract import ImageInput


@pytest.mark.parametrize("seed", range(5))
def test_frozen_wp2_development_replays_are_evidence_only(tmp_path, seed):
    manifest = json.loads((ROOT / "manifest.json").read_text())
    row = manifest["items"][seed]
    assert row["split"] == "development"
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    ledger = book(tmp_path)
    result = perceive(
        ledger,
        ImageInput((ROOT / f"public/development_{seed}.png").read_bytes()),
        replay=Replay((reply(1, seed), reply(2, seed))),
        output=tmp_path / "run",
        nonce=f"{seed:016x}",
        clock=lambda: OFF,
    )
    data = result.record.to_dict()
    assert Record.from_json(result.record.to_json()) == result.record
    assert data["stage"] == "perceived" and data["provenance"]["perceiver_calls"] == 2
    assert data["sources"] == [] and data["problem"]["premises"] == []
    assert (
        data["formal"]["propositions"] == []
        and data["assumptions"] == []
        and data["derivations"] == []
    )
    assert (
        data["provenance"]["cost_usd"] == 0
    )  # actual hosted spend; simulated totals in receipt
    assert result.report()["simulated_cost_usd"] == "0.003600"
    assert result.report()["hosted_calls"] == 0
    assert len(ledger.snapshot()["attempts"]) == 2
    alignment = result.report()["alignment"]
    assert len(alignment["matches"]) + len(alignment["unmatched_left"]) == 6
    assert all(len(e["geometries"]) in {1, 2} for e in data["entities"])
    labels = {e["id"]: e["label"] for e in data["entities"]}
    props = [
        canonical_proposition(o["proposition"], labels)
        for o in data["observations"]
        if o["kind"] == "proposition"
    ]
    assert props[0] == props[1]
    # Only the test scorer reads these frozen development answers, after inference.
    truth_bytes = gzip.decompress(
        (ROOT / f"truth/development_{seed}.json.gz").read_bytes()
    )
    assert hashlib.sha256(truth_bytes).hexdigest() == row["truth_sha256"]
    truth = json.loads(truth_bytes)
    candidate = next(c for c in truth["candidates"] if c["proposition"] == props[0])
    assert candidate["class"] == ("unknown" if seed == 4 else "false")
    assert data["image"]["sha256"] == row["image_sha256"]
    assert (tmp_path / "run/record.json").read_text().strip() == result.record.to_json()


def test_observations_cannot_authorise_and_returned_record_is_immutable(tmp_path):
    result = run(tmp_path)
    data = result.record.to_dict()
    obs = next(o for o in data["observations"] if o["kind"] == "proposition")
    data["formal"]["propositions"] = [
        {
            "id": "prop_1",
            "role": "hypothesis",
            "proposition": obs["proposition"],
            "support": "assumption",
            "depends_on": [obs["id"]],
        }
    ]
    with pytest.raises(RecordError):
        Record.from_dict(data)
    assert result.record.to_dict()["formal"]["propositions"] == []


def test_two_identical_requests_no_first_reply_or_truth_in_second_prompt(tmp_path):
    result = run(tmp_path)
    requests = [
        json.loads(p.read_text())
        for p in sorted((tmp_path / "run").glob("call*/request.json"))
    ]
    assert requests[0] == requests[1]
    assert requests[0]["thinking"] is False and requests[0]["temperature"] == 0
    assert requests[0]["model"] == "deepseek-flash"
    assert "truth" not in requests[0]["prompt"]
    assert result.report()["alignment"]["agreement_is_verification"] is False


@pytest.mark.parametrize(
    "seed,expected",
    [(0, "premise"), (1, "false"), (2, "false"), (3, "premise"), (4, "unknown")],
)
def test_positive_and_not_to_scale_truth_never_promote_a_claim(
    tmp_path, seed, expected
):
    responses = []
    for call in (1, 2):
        body = json.loads(reply(call, seed).raw)
        c = json.loads(body["choices"][0]["message"]["content"])
        ids = {e["label"]: e["id"] for e in c["entities"]}
        c["observations"] = [
            {
                "proposition": {"pred": "Midpoint", "args": [ids[x] for x in "CAB"]},
                "confidence": 1,
            }
        ]
        body["choices"][0]["message"]["content"] = json.dumps(c)
        from mve.preflight.probe_contract import ProbeReply

        responses.append(ProbeReply(json.dumps(body).encode(), "0.0018"))
    result = perceive(
        book(tmp_path),
        ImageInput((ROOT / f"public/development_{seed}.png").read_bytes()),
        replay=Replay(tuple(responses)),
        output=tmp_path / "run",
        nonce=f"{seed:016x}",
        clock=lambda: OFF,
    )
    assert result.record.to_dict()["assumptions"] == []
    truth = json.loads(
        gzip.decompress((ROOT / f"truth/development_{seed}.json.gz").read_bytes())
    )
    assert (
        next(
            c["class"]
            for c in truth["candidates"]
            if c["proposition"] == {"pred": "Midpoint", "args": ["C", "A", "B"]}
        )
        == expected
    )
