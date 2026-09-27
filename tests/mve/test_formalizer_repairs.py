"""WP-6b tests written before the implementation; fixture compiler is explicit."""

from copy import deepcopy
import json
import pytest
from mve.formalizer.ir import build_ir
from mve.formalizer.emitter import emit
from mve.formalizer.repairs import Candidate, formalize, syntax_fixture
from mve.formalizer.equivalence import assess, LEVELS
from mve.identity import digest
from mve.formalizer.runtime import sha
from tests.mve.formalizer_fixtures import trusted_data
from mve.record import create


def trusted_record():
    data = trusted_data()
    data["problem"]["premises"][0]["proposition"] = {
        "pred": "Midpoint",
        "args": list("ABC"),
    }
    return create({**data, "stage": "ingested"}, "2026-09-27T00:00:00Z")


def compiler(source, project, output, **kw):
    return {
        "ok": "statement Prop" not in source,
        "outcome": "fixture",
        "statement_sha256": sha(source.encode()),
        "log_sha256": "1" * 64,
        "proof_checked": False,
        "toolchain": "fixture",
    }


@pytest.fixture
def local(monkeypatch):
    import mve.formalizer.repairs as module

    monkeypatch.setattr(module, "compile_source", compiler)
    monkeypatch.setattr(
        module, "verify_project", lambda p: {"lean_toolchain": "fixture"}
    )
    return module


def test_rule_repair_preserves_ir_binders_and_record(local, tmp_path):
    record = trusted_record()
    ir = build_ir(record)
    source = syntax_fixture(ir)
    (tmp_path / "lock.json").write_text("{}")
    result, report = formalize(
        record, tmp_path, tmp_path / "out", initial=Candidate.make(ir, source)
    )
    assert [r["typecheck"]["ok"] for r in report["attempts"]] == [False, True]
    assert {r["ir_sha256"] for r in report["attempts"]} == {digest(ir)}
    assert len({r["binder_sha256"] for r in report["attempts"]}) == 1
    assert report["equivalence"]["level"] == "machine_supported"
    assert report["proof_checked"] is False
    assert result.to_dict()["formal"]["status"] == "typechecked"
    assert "proof" not in result.to_dict()["formal"]
    assert result.to_dict()["content_hash"] == record.to_dict()["content_hash"]
    assert json.loads((tmp_path / "out/repair.json").read_text()) == report


@pytest.mark.parametrize("change", ["goal", "premise", "binder", "source", "evidence"])
def test_semantic_drift_is_refused_and_logged_before_compiler(local, tmp_path, change):
    record = trusted_record()
    ir = build_ir(record)
    changed = deepcopy(ir)
    source = emit(ir)
    if change == "goal":
        changed["goal"]["proposition"] = {"pred": "Distinct", "args": ["A", "B"]}
    elif change == "premise":
        changed["premises"].pop(0)
    elif change == "binder":
        changed["binders"][0]["entity"] = "ent_2"
    elif change == "evidence":
        changed["premises"][0]["evidence"] = "prm_99"
    else:
        source = source.replace("Collinear ℝ ({p0,p1,p2} : Set Point)", "True")
    (tmp_path / "lock.json").write_text("{}")
    result, report = formalize(
        record,
        tmp_path,
        tmp_path / "out",
        initial=Candidate.make(ir, syntax_fixture(ir)),
        repairs=[Candidate.make(changed, source)],
    )
    assert report["status"] == "refused"
    assert report["attempts"][-1]["refusal"]
    assert "typecheck" not in report["attempts"][-1]
    assert result == record
    assert report["equivalence"]["level"] == "unresolved"


def test_caps_no_goal_and_unrecognized_initial(local, tmp_path):
    record = trusted_record()
    ir = build_ir(record)
    (tmp_path / "lock.json").write_text("{}")
    for n in [-1, 4, True]:
        with pytest.raises(ValueError, match="0..3"):
            formalize(record, tmp_path, tmp_path / "out", max_repairs=n)
    _, report = formalize(
        record,
        tmp_path,
        tmp_path / "out",
        max_repairs=0,
        initial=Candidate.make(ir, syntax_fixture(ir)),
    )
    assert report["status"] == "error" and len(report["attempts"]) == 1
    _, report = formalize(
        record,
        tmp_path,
        tmp_path / "out",
        initial=Candidate.make(ir, "def statement : Prop := True"),
    )
    assert report["status"] == "refused"
    assert "typecheck" not in report["attempts"][0]


def test_evidence_never_promotes_typecheck_or_claimed_kernel_evidence():
    ir = build_ir(trusted_record())
    assert LEVELS == (
        "kernel_checked",
        "machine_supported",
        "reviewer_judged",
        "unresolved",
    )
    evidence = assess(ir, ir, emit(ir))
    assert evidence["level"] == "machine_supported"
    assert not evidence["semantic_acceptance"]
    assert assess(ir, ir, "def statement : Prop := True")["level"] == "unresolved"
    assert assess(ir, ir, syntax_fixture(ir))["level"] == "unresolved"
    with pytest.raises(ValueError, match="kernel"):
        assess(ir, ir, emit(ir), claimed_level="kernel_checked")


def test_candidate_snapshots_inputs():
    ir = build_ir(trusted_record())
    candidate = Candidate.make(ir, emit(ir))
    ir["premises"].clear()
    assert candidate.ir()["premises"]


def test_review_identity_rubric_and_no_typecheck_promotion():
    ir = build_ir(trusted_record())
    source = "unreviewed source"
    identity = assess(ir, ir, source)
    review = {
        k: identity[k]
        for k in ("reference_ir_sha256", "candidate_ir_sha256", "statement_sha256")
    }
    review.update(
        reviewer="human:reviewer",
        rationale="Compared all four components",
        blinded=True,
        rubric=dict.fromkeys(["binders", "premises", "goal", "nondegeneracy"], True),
    )
    result = assess(ir, ir, source, review=review)
    assert result["level"] == "reviewer_judged" and result["semantic_acceptance"]
    for key, value in [
        ("reviewer", ""),
        ("blinded", False),
        ("rubric", {}),
        ("statement_sha256", "0" * 64),
    ]:
        with pytest.raises(ValueError):
            assess(ir, ir, source, review={**review, key: value})
    review["rubric"]["goal"] = False
    assert not assess(ir, ir, source, review=review)["semantic_acceptance"]


def test_compiler_failure_and_receipt_mismatch(local, tmp_path):
    record = trusted_record()
    (tmp_path / "lock.json").write_text("{}")

    def failed(source, *a, **kw):
        return {**compiler(source, *a, **kw), "ok": False}

    local.compile_source = failed
    result, report = formalize(record, tmp_path, tmp_path / "out")
    assert result.to_dict()["formal"]["status"] == "emitted"
    assert len(report["attempts"]) == 1
    local.compile_source = lambda source, *a, **kw: {
        **failed(source, *a, **kw),
        "statement_sha256": "bad",
    }
    result, report = formalize(record, tmp_path, tmp_path / "out")
    assert report["status"] == "refused"


def test_reference_task_refuses_missing_goal_self_identity_and_degenerate():
    from mve.formalizer.repairs import require_task

    ir = build_ir(trusted_record())
    ir["goal"] = None
    with pytest.raises(ValueError, match="explicit"):
        require_task(ir)
    ir = build_ir(trusted_record())
    for prop in [
        {"pred": "EqualLength", "args": list("ABAB")},
        {"pred": "EqualAngle", "args": list("ABACDC")},
    ]:
        ir["goal"]["proposition"] = prop
        with pytest.raises(ValueError, match="degenerate|identity"):
            require_task(ir)
    ir["goal"]["proposition"] = ir["premises"][0]["proposition"]
    with pytest.raises(ValueError, match="trivial"):
        require_task(ir)


def test_adopted_assumptions_are_authorized_in_ir_and_payload():
    from mve.formalizer.runtime import formal_payload
    from tests.mve.test_verdict_capture import record, verdict

    r = verdict(record(), value="adopt")
    ir = build_ir(r)
    adopted = next(n for n in ir["premises"] if n["evidence"].startswith("asm_"))
    assert adopted["role"] == "hypothesis"
    payload = formal_payload(ir, "fixture")
    assert any(p["support"] == "assumption" for p in payload["propositions"])


def test_malformed_candidate_refused_with_audit(local, tmp_path):
    record = trusted_record()
    (tmp_path / "lock.json").write_text("{}")
    _, report = formalize(
        record, tmp_path, tmp_path / "out", initial=Candidate.make({}, "")
    )
    assert report["status"] == "refused"
    assert "malformed" in report["attempts"][0]["refusal"]


def test_three_round_cap_and_whitespace_only_repair(local, tmp_path):
    record = trusted_record()
    ir = build_ir(record)
    (tmp_path / "lock.json").write_text("{}")
    faulty = Candidate.make(ir, syntax_fixture(ir))
    _, report = formalize(
        record, tmp_path, tmp_path / "out", initial=faulty, repairs=[faulty] * 8
    )
    assert len(report["attempts"]) == 4 and report["status"] == "error"
    _, report = formalize(
        record,
        tmp_path,
        tmp_path / "out",
        initial=faulty,
        repairs=[Candidate.make(ir, emit(ir) + "\n")],
    )
    assert report["status"] == "typechecked"
    assert report["equivalence"]["level"] == "machine_supported"


def test_cli_uses_repair_path(tmp_path, monkeypatch, capsys):
    import mve.formalizer.__main__ as module

    path = tmp_path / "input.json"
    path.write_text(trusted_record().to_json())
    monkeypatch.setattr(
        module,
        "formalize",
        lambda record, *a, **kw: (record, {"status": "typechecked"}),
    )
    assert module.main(["--record", str(path), "--output", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "typechecked"


def test_refused_rerun_replaces_prior_output_record(local, tmp_path):
    record = trusted_record()
    ir = build_ir(record)
    (tmp_path / "lock.json").write_text("{}")
    formalize(record, tmp_path, tmp_path / "out")
    formalize(record, tmp_path, tmp_path / "out", initial=Candidate.make(ir, ""))
    assert json.loads((tmp_path / "out/record.json").read_text()) == record.to_dict()
