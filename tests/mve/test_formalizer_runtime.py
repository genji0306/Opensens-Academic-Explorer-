from pathlib import Path
import json
import pytest
from mve.formalizer.runtime import typecheck_record, verify_project, compile_source
from mve.formalizer.emitter import HEADER, native
from mve.predicates import REGISTRY
from mve.record import Record
from tests.mve.fixtures import populated

PROJECT = Path(__file__).resolve().parents[2] / "mve/lean"


def available():
    return Path(
        "/Users/applefamily/.elan/toolchains/leanprover--lean4---v4.29.0/bin/lean"
    ).exists()


@pytest.mark.skipif(not available(), reason="requires pinned local Lean cache")
def test_native_targets_compile_without_proofs(tmp_path):
    source = HEADER
    for pred, row in REGISTRY.items():
        if row["active"]:
            names = list("ABCDEF")[: row["arity"]]
            expression = native(
                {"pred": pred, "args": names}, {x: f"p{i}" for i, x in enumerate(names)}
            )
            args = " ".join(f"p{i}" for i in range(len(names)))
            source += f"def check{pred} ({args} : Point) : Prop := {expression}\n"
    receipt = compile_source(source, PROJECT, tmp_path, timeout=60)
    assert receipt["ok"], receipt
    assert receipt["proof_checked"] is False
    assert receipt["hosted_calls"] == 0


@pytest.mark.skipif(not available(), reason="requires pinned local Lean cache")
def test_typecheck_record_keeps_proof_separate(tmp_path):
    original = Record.from_dict(populated())
    result, receipt = typecheck_record(original, PROJECT, tmp_path, timeout=60)
    data = result.to_dict()
    assert receipt["ok"]
    assert data["formal"]["status"] == "typechecked"
    assert data["stage"] == "formalized"
    assert "proof" not in data["formal"]
    assert data["revision"] == original.to_dict()["revision"] + 2
    assert data["content_hash"] == original.to_dict()["content_hash"]
    assert Record.from_json(result.to_json()) == result


def test_missing_or_tampered_project_refuses_before_compilation(tmp_path):
    with pytest.raises(ValueError):
        verify_project(tmp_path)
    lock = json.loads((PROJECT / "lock.json").read_text())
    lock["project_files"] = {"lean-toolchain": "0" * 64}
    (tmp_path / "lock.json").write_text(json.dumps(lock))
    (tmp_path / "lean-toolchain").write_text("unverified")
    with pytest.raises(ValueError, match="pin"):
        verify_project(tmp_path)


def test_compile_timeout_and_error_never_report_success(tmp_path, monkeypatch):
    import subprocess
    import mve.formalizer.runtime as runtime

    lock = json.loads((PROJECT / "lock.json").read_text())
    monkeypatch.setattr(runtime, "verify_project", lambda project: lock)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("lean", 1)

    monkeypatch.setattr(runtime.subprocess, "run", timeout)
    receipt = compile_source(HEADER, PROJECT, tmp_path, timeout=1)
    assert receipt["outcome"] == "timeout" and not receipt["ok"]
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", "type mismatch"),
    )
    receipt = compile_source(HEADER, PROJECT, tmp_path, timeout=1)
    assert receipt["outcome"] == "error" and not receipt["ok"]
    with pytest.raises(ValueError):
        compile_source(HEADER, PROJECT, tmp_path, timeout=0)


def test_failed_typecheck_leaves_record_emitted(tmp_path, monkeypatch):
    import mve.formalizer.runtime as runtime

    monkeypatch.setattr(
        runtime, "compile_source", lambda *a, **kw: {"ok": False, "outcome": "error"}
    )
    result, receipt = typecheck_record(Record.from_dict(populated()), PROJECT, tmp_path)
    assert result.to_dict()["formal"]["status"] == "emitted"
    assert not receipt["ok"]
    assert "typecheck" not in result.to_dict()["formal"]
