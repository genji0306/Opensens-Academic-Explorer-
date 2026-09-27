"""Offline G3 contracts, authored before harness implementation."""

import json
import pytest
from mve.formalizer.g3 import build_tasks, controls, run
from mve.formalizer.ir import build_ir
from mve.formalizer.emitter import emit
from mve.formalizer.repairs import inspect_candidate
from mve.formalizer.runtime import sha


def test_synthetic_tasks_have_explicit_goals_and_retrieval_disjoint_families():
    tasks, retrieval, split = build_tasks(6)
    assert len(tasks) == 6 and len(retrieval) == 2
    rows = {r["id"]: r for r in split.manifest()["items"]}
    for record in tasks:
        ir = build_ir(record)
        assert ir["goal"] and ir["premises"]
        assert rows[record.to_dict()["image"]["sha256"]]["split"] == "sealed"
        assert emit(ir)
    a = {rows[r.to_dict()["image"]["sha256"]]["family"] for r in tasks}
    b = {rows[r.to_dict()["image"]["sha256"]]["family"] for r in retrieval}
    assert not a & b


def test_all_g3_controls_detected_before_compilation():
    tasks, retrieval, split = build_tasks(2)
    ir, other = build_ir(tasks[0]), build_ir(retrieval[0])
    variants = controls(ir, other)
    assert set(variants) == {
        "empty",
        "trivial",
        "nearest_retrieval",
        "weakened",
        "strengthened",
        "vacuous",
        "unrelated_but_provable",
    }
    assert all("refusal" in inspect_candidate(ir, v) for v in variants.values())


def test_harness_counts_and_no_semantic_acceptance(tmp_path, monkeypatch):
    import mve.formalizer.g3 as module

    calls = []

    def compile(source, project, output):
        calls.append(source)
        return {
            "ok": "statement Prop" not in source,
            "outcome": "fixture",
            "statement_sha256": sha(source.encode()),
            "proof_checked": False,
        }

    monkeypatch.setattr(module, "compile_source", compile)
    report = run(tmp_path, count=6)
    assert report["tasks"] == 6
    assert report["first_pass_well_typed"] == 4
    assert report["post_repair_well_typed"] == 6
    assert report["semantic_rubric_passes"] == 0
    assert report["g3_pass"] is False and report["null"] == "N/A"
    assert report["hosted_calls"] == 0
    assert report["reference_tasks"] == 50
    assert all(r["detected"] == r["total"] == 6 for r in report["controls"].values())
    assert len(calls) == report["unique_compiler_inputs"]
    assert json.loads((tmp_path / "g3.json").read_text()) == report


def test_failed_compiler_is_unresolved_and_mismatch_refused(tmp_path, monkeypatch):
    import mve.formalizer.g3 as module

    def compile(source, *a, **kw):
        return {
            "ok": False,
            "outcome": "sandbox_error",
            "statement_sha256": sha(source.encode()),
            "proof_checked": False,
        }

    monkeypatch.setattr(module, "compile_source", compile)
    report = run(tmp_path, count=2)
    assert report["post_repair_well_typed"] == 0
    assert report["equivalence_counts"]["unresolved"] == 50
    monkeypatch.setattr(
        module, "compile_source", lambda *a: {**compile("bad"), "proof_checked": True}
    )
    with pytest.raises(ValueError, match="mismatched"):
        module.checked("test", tmp_path, tmp_path, {})
    with pytest.raises(ValueError, match="2..100"):
        build_tasks(0)


def test_g3_cli(tmp_path, monkeypatch, capsys):
    import mve.formalizer.g3 as module

    monkeypatch.setattr(module, "run", lambda output: {"tasks": 100})
    module.main(["--output", str(tmp_path)])
    assert json.loads(capsys.readouterr().out)["tasks"] == 100


def test_real_lean_repairs_statement_without_proof(tmp_path):
    from mve.formalizer.runtime import lean_unavailable_reason
    from mve.formalizer.repairs import formalize, Candidate, syntax_fixture
    from mve.formalizer.tasks import task
    from pathlib import Path

    project = Path(__file__).resolve().parents[2] / "mve/lean"
    reason = lean_unavailable_reason(project)
    if reason:
        print("MVE WP-6b real-Lean check skipped: " + reason)
        pytest.skip(reason)
    record = task("midpoint_grid", 0, 0)
    ir = build_ir(record)
    checked, report = formalize(
        record, project, tmp_path, initial=Candidate.make(ir, syntax_fixture(ir))
    )
    assert report["status"] == "typechecked", report
    assert [a["typecheck"]["ok"] for a in report["attempts"]] == [False, True]
    assert checked.to_dict()["formal"]["status"] == "typechecked"
    assert not report["proof_checked"]


def test_full_gate_requires_bound_human_reviews(tmp_path, monkeypatch):
    import mve.formalizer.g3 as module
    from mve.formalizer.taskset import load_packet, review_rows

    monkeypatch.setattr(
        module,
        "compile_source",
        lambda source, *args: {
            "ok": "statement Prop" not in source,
            "outcome": "fixture",
            "statement_sha256": sha(source.encode()),
            "proof_checked": False,
        },
    )
    templates = review_rows(load_packet()["references"])
    # Explicit synthetic reviewer evidence exercises plumbing, never persisted as real judgments.
    reviews = [
        {
            **r,
            "reviewer": "test-only",
            "rationale": "fixture evidence",
            "blinded": True,
            "rubric": dict.fromkeys(r["rubric"], True),
        }
        for r in templates[:20]
    ]
    report = module.run(tmp_path, reviews=reviews)
    assert report["first_pass_well_typed"] == 80
    assert (
        report["post_repair_well_typed"] == report["unique_canonical_statements"] == 100
    )
    assert report["first_pass_rate"] == 0.8 and report["post_repair_rate"] == 1
    assert report["semantic_rubric_passes"] == report["human_reviews"] == 20
    assert report["g3_pass"] and not report["g3_reasons"]
    assert all(r["detected"] == r["total"] == 100 for r in report["controls"].values())
    assert report["equivalence_counts"]["machine_supported"] == 50
    assert report["equivalence_counts"]["reviewer_judged"] == 0
    for invalid, match in [
        ({}, "list"),
        ([None], "object"),
        ([reviews[0], reviews[0]], "duplicate"),
        ([{**reviews[0], "task_id": "sealed-000"}], "unknown"),
        ([{**reviews[0], "statement_sha256": "0" * 64}], "bind"),
        ([templates[0]], "reviewer identity"),
    ]:
        with pytest.raises(ValueError, match=match):
            module.evaluate_references(
                load_packet()["references"], invalid, tmp_path, tmp_path, {}
            )


def test_g3_cli_review_file(tmp_path, monkeypatch, capsys):
    import mve.formalizer.g3 as module

    reviews = tmp_path / "reviews.json"
    reviews.write_text("[]")
    monkeypatch.setattr(module, "run", lambda output, reviews: {"reviews": reviews})
    module.main(["--reviews", str(reviews)])
    assert json.loads(capsys.readouterr().out) == {"reviews": []}
