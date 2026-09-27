"""G3 corpus and gate contracts, written before the replacement builder."""

import json
from collections import Counter

import pytest

from mve.formalizer import taskset
from mve.formalizer.emitter import emit
from mve.formalizer.ir import build_ir
from mve.formalizer.repairs import require_task
from mve.generator.exact import ExactEvaluator
from mve.degeneracy import required_nondegeneracy
from mve.formalizer.runtime import sha


@pytest.fixture(scope="module")
def packet():
    return taskset.load_packet()


def test_distinct_statements_stratification_and_explicit_exact_evidence(packet):
    rows = packet["sealed"]
    assert len(rows) == 100
    assert len({r["canonical_statement_sha256"] for r in rows}) == 100
    assert set(r["predicate"] for r in rows) == set(taskset.PREDICATES)
    for row in (
        rows + packet["references"] + packet["development"] + packet["retrieval"]
    ):
        record = taskset.record(row)
        ir = build_ir(record)
        require_task(ir)
        assert sha(emit(ir).encode()) == row["canonical_statement_sha256"]
        truth = packet["truth"][row["truth_key"]]
        evaluator = ExactEvaluator(truth["math_coordinates"])
        problem = record.to_dict()["problem"]
        premises = [p["proposition"] for p in problem["premises"]]
        assert premises == truth["premises"]
        goal = problem["goal"]["proposition"]
        candidate = next(r for r in truth["candidates"] if r["proposition"] == goal)
        assert candidate["math_class"] == "true" and candidate["class"] != "premise"
        assert goal not in premises
        all_props = premises + [p["proposition"] for p in problem["nondegeneracy"]]
        assert all(evaluator.classify(p) == "true" for p in all_props + [goal])
        for p in premises + [goal]:
            assert all(n in all_props for n in required_nondegeneracy(p))
    counts = Counter(r["predicate"] for r in rows)
    assert packet["summary"]["per_predicate_counts"] == dict(counts)
    assert packet["summary"]["unique_canonical_statements"] == 100
    for pred, gap in packet["summary"]["quota_gaps"].items():
        assert counts[pred] < gap["quota"] and gap["reason"]


def test_frozen_wp2_family_roles_and_reference_isolation(packet):
    assert packet["wp2_split_sha256"] == (
        "63da5b93adce004b172d9c6ddd182227d6c22c9adb482fddfa8d263795dff909"
    )
    roles = taskset.family_roles()
    groups = {
        name: {r["family"] for r in packet[name]}
        for name in ("sealed", "development", "retrieval", "references")
    }
    for name in ("sealed", "development", "retrieval"):
        assert all(roles[f] == name for f in groups[name])
    assert len(packet["references"]) == 50
    assert not groups["sealed"] & groups["development"]
    assert not groups["references"] & (
        groups["sealed"] | groups["retrieval"] | groups["development"]
    )
    reference_sources = {r["canonical_statement_sha256"] for r in packet["references"]}
    assert len(reference_sources) == 50
    assert not reference_sources & {
        r["canonical_statement_sha256"]
        for group in ("sealed", "retrieval")
        for r in packet[group]
    }


def test_blinded_sheet_has_no_judgments_or_family_leakage(packet, tmp_path):
    taskset.write_review_sheet(packet["references"], tmp_path)
    rows = json.loads((tmp_path / "rubric-template.json").read_text())
    assert len(rows) == 50
    for row in rows:
        assert row["reviewer"] is None and row["rationale"] is None
        assert row["blinded"] is None
        assert row["rubric"] == dict.fromkeys(
            ("binders", "premises", "goal", "nondegeneracy")
        )
        assert row["reference_statement"] == row["candidate_statement"]
        assert "family" not in row and "truth" not in row
        assert row["problem"]["goal"] and row["problem"]["binders"]
    import csv

    with (tmp_path / "rubric-template.csv").open(newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == 50
    assert all(
        not r[k]
        for r in csv_rows
        for k in (
            "reviewer",
            "rationale",
            "blinded",
            "binders",
            "premises",
            "goal",
            "nondegeneracy",
        )
    )
    assert b"\r" not in (tmp_path / "rubric-template.csv").read_bytes()


def test_deterministic_generation_matches_committed_packet(packet):
    assert taskset.generate_packet() == packet


def test_gate_boundaries_and_missing_human_rubric():
    from mve.formalizer.g3 import gate

    args = dict(tasks=100, unique=100, first=80, post=95, references=50, semantic=20)
    assert gate(**args)["g3_pass"] is True
    for key, value in [
        ("tasks", 99),
        ("unique", 99),
        ("first", 79),
        ("post", 94),
        ("references", 49),
        ("semantic", 19),
    ]:
        assert gate(**{**args, key: value})["g3_pass"] is False
    result = gate(**{**args, "semantic": 0})
    assert not result["g3_pass"] and any(
        "blinded semantic rubric" in r for r in result["g3_reasons"]
    )


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("split", "frozen split"),
        ("count", "task count"),
        ("family", "family outside"),
        ("statement", "truth binding"),
        ("candidate", "truth binding"),
        ("overlap", "reference statement overlaps"),
    ],
)
def test_packet_tampering_refused(packet, mutation, match):
    import copy

    data = copy.deepcopy(packet)
    if mutation == "split":
        data["wp2_split_sha256"] = "0" * 64
    elif mutation == "count":
        data["sealed"].pop()
    elif mutation == "family":
        data["sealed"][0]["family"] = data["retrieval"][0]["family"]
    elif mutation == "overlap":
        data["references"][0]["canonical_statement_sha256"] = data["sealed"][0][
            "canonical_statement_sha256"
        ]
    elif mutation == "candidate":
        data["sealed"][0]["candidate_id"] = "0" * 64
    else:
        data["sealed"][0]["canonical_statement_sha256"] = "0" * 64
    with pytest.raises(ValueError, match=match):
        taskset.validate_packet(data)


def test_insufficient_candidate_pool_refused():
    with pytest.raises(ValueError, match="distinct statements available"):
        taskset.select([], 100)


def test_taskset_cli_writes_no_compiler_receipts(packet, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(taskset, "ROOT", tmp_path)
    monkeypatch.setattr(taskset, "generate_packet", lambda: packet)
    taskset.main()
    assert json.loads(capsys.readouterr().out)["tasks"] == 100
    assert taskset.load_packet(tmp_path) == packet
    assert not (tmp_path / "checks").exists()
