from pathlib import Path
import json
import pytest
from mve.formalizer.runtime import (
    typecheck_record,
    verify_project,
    compile_source,
    lean_available,
    lean_unavailable_reason,
    package_path,
)
from mve.formalizer.emitter import HEADER, native
from mve.predicates import REGISTRY
from mve.record import Record
from tests.mve.formalizer_fixtures import trusted_record

PROJECT = Path(__file__).resolve().parents[2] / "mve/lean"


@pytest.fixture(scope="module")
def real_lean(request):
    reason = lean_unavailable_reason(PROJECT)
    if reason:
        terminal = request.config.pluginmanager.get_plugin("terminalreporter")
        if terminal:
            terminal.write_line("MVE real-Lean checks skipped: " + reason)
        pytest.skip(reason)


def test_native_targets_compile_without_proofs(tmp_path, real_lean):
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


def test_typecheck_record_keeps_proof_separate(tmp_path, real_lean):
    original = trusted_record()
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
        runtime,
        "verify_project",
        lambda project: json.loads((PROJECT / "lock.json").read_text()),
    )

    monkeypatch.setattr(
        runtime, "compile_source", lambda *a, **kw: {"ok": False, "outcome": "error"}
    )
    result, receipt = typecheck_record(trusted_record(), PROJECT, tmp_path)
    assert result.to_dict()["formal"]["status"] == "emitted"
    assert not receipt["ok"]
    assert "typecheck" not in result.to_dict()["formal"]


def test_real_lean_gate_uses_configured_relative_binary(tmp_path, monkeypatch):
    binary = tmp_path / "elan/toolchains/leanprover--lean4---v4.29.0/bin/lean"
    binary.parent.mkdir(parents=True)
    binary.touch()
    binary.chmod(0o700)
    monkeypatch.setenv("ELAN_HOME", str(tmp_path / "elan"))
    (tmp_path / "lock.json").write_text(
        json.dumps(
            {
                "lean_binary": "bin/lean",
                "lean_toolchain": "leanprover/lean4:v4.29.0",
                "packages": [],
            }
        )
    )
    assert lean_available(tmp_path)
    binary.unlink()
    assert not lean_available(tmp_path)


def test_compiler_gets_only_minimal_env_and_relative_receipt_paths(
    tmp_path, monkeypatch
):
    import subprocess
    import mve.formalizer.runtime as runtime

    lock = json.loads((PROJECT / "lock.json").read_text())
    monkeypatch.setattr(runtime, "verify_project", lambda project: lock)
    monkeypatch.setenv("MVE_TEST_SECRET", "must-not-reach-lean")

    def compiler(*args, **kwargs):
        assert set(kwargs["env"]) == {"PATH", "HOME", "LEAN_PATH"}
        assert "must-not-reach-lean" not in str(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, "statement : Prop\n", "")

    monkeypatch.setattr(runtime.subprocess, "run", compiler)
    receipt = compile_source(HEADER, PROJECT, tmp_path)
    for field in ("statement_path", "log_path"):
        assert not Path(receipt[field]).is_absolute()
        assert (tmp_path / receipt[field]).is_file()


def test_missing_nondegeneracy_prevents_record_emission(tmp_path, monkeypatch):
    import mve.formalizer.runtime as runtime
    from tests.mve.fixtures import populated

    monkeypatch.setattr(
        runtime,
        "verify_project",
        lambda project: json.loads((PROJECT / "lock.json").read_text()),
    )

    def never(*args, **kwargs):
        raise AssertionError("compiler must not run")

    monkeypatch.setattr(runtime, "compile_source", never)
    with pytest.raises(ValueError, match="missing.*Distinct"):
        typecheck_record(Record.from_dict(populated()), PROJECT, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_spike_import_header_matches_emitter():
    assert (PROJECT / "MVE/Spike.lean").read_text().startswith(HEADER)


def test_lock_and_stored_receipts_have_no_absolute_paths():
    lock = json.loads((PROJECT / "lock.json").read_text())
    assert not Path(lock["lean_binary"]).is_absolute()
    assert all(not Path(row["path"]).is_absolute() for row in lock["packages"])


def test_committed_typecheck_receipts_resolve_from_output_directory():
    for path in (PROJECT / "artifacts").rglob("*.receipt.json"):
        receipt = json.loads(path.read_text())
        for key in ("statement_path", "log_path"):
            assert not Path(receipt[key]).is_absolute()
            assert (path.parent / receipt[key]).is_file()


def test_absolute_lock_path_is_refused(tmp_path):
    from mve.formalizer.runtime import project_path

    with pytest.raises(ValueError, match="project-relative"):
        project_path(tmp_path, str(tmp_path / "lean"))


def test_semantics_map_uses_current_registry_degeneracy():
    data = json.loads((PROJECT / "SemanticsMap.json").read_text())
    for pred, row in data["predicates"].items():
        assert row["registry_degeneracy"] == REGISTRY[pred]["degeneracy"]


def test_real_lean_typechecks_from_relocated_project(tmp_path, monkeypatch, real_lean):
    import shutil

    lock = json.loads((PROJECT / "lock.json").read_text())
    packages = package_path(PROJECT, lock["packages"][0]).parent
    monkeypatch.setenv("MVE_LEAN_PACKAGES", str(packages))
    relocated = tmp_path / "arbitrary/checkout/depth/lean"
    relocated.mkdir(parents=True)
    for name in ["lock.json", *lock["project_files"]]:
        shutil.copyfile(PROJECT / name, relocated / name)
    checked, receipt = typecheck_record(
        trusted_record(), relocated, tmp_path / "output"
    )
    assert receipt["ok"]
    assert checked.to_dict()["formal"]["status"] == "typechecked"
    assert not receipt["proof_checked"]


def test_missing_cache_prints_one_skip_diagnostic(tmp_path):
    import os
    import subprocess
    import sys

    env = dict(os.environ, ELAN_HOME=str(tmp_path / "absent"), PYTEST_ADDOPTS="")
    tests = [
        "test_native_targets_compile_without_proofs",
        "test_typecheck_record_keeps_proof_separate",
        "test_real_lean_typechecks_from_relocated_project",
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *[str(Path(__file__)) + "::" + t for t in tests],
        ],
        cwd=PROJECT.parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 skipped" in result.stdout
    assert result.stdout.count("MVE real-Lean checks skipped:") == 1
