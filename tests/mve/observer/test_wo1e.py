"""Offline recapture and failed-attempt regressions against copied evidence."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from mve.observer import capture_c, capture_evidence, capture_policy, quarantine_c
from mve.observer import snapshot_inventory as inv, storage


WO1B = (
    Path.home()
    / "Developer/Opensens/worktrees/oae-mve-wo1b/mve/generated/wo1b-d286a45abc8187fd"
)
WO6C = (
    Path.home()
    / "Developer/Opensens/worktrees/oae-mve-wo6c/mve/generated/wo6c-pilot/captures"
)


def test_real_wo1b_partial_recapture_admission(tmp_path):
    if not WO1B.is_dir():
        pytest.skip("read-only WO-1b native evidence unavailable")
    base = tmp_path / "wo1b"
    shutil.copytree(WO1B, base)
    plan = inv.load(inv.ROOT / inv.PLAN)
    state = capture_evidence.resume_state(base, plan)
    assert len(state["completed"]) == 66
    q = base / "quarantine/partial-spectral-contrast-2-153"
    record = json.loads((q / "QUARANTINE.json").read_text())
    assert len(record["snapshots"]) == 4
    for ident in record["snapshots"]:
        shutil.copytree(q / ident, base / "snapshots" / ident)
    state = capture_evidence.resume_state(base, plan)
    assert len(state["completed"]) == 70
    assert any(r.get("name") == q.name for r in state["quarantine"])


def test_real_wo6c_failed_then_in_progress_recapture(tmp_path, monkeypatch):
    if not WO6C.is_dir():
        pytest.skip("read-only WO-6c native evidence unavailable")
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    shutil.copytree(WO6C, base)
    assert any(r["moves"] == 20 for r in quarantine_c.admission(base))
    result = quarantine_c.run(
        SimpleNamespace(
            name="failed-604055543b64-b0",
            reason="failed admission",
            failed_attempt="0",
            plan_sha256=None,
        )
    )
    assert result["moves"] == 1
    assert len(quarantine_c.admission(base)) == 2
    attempt = base / "native/0"
    attempt.mkdir()
    p = capture_c.plan()
    (attempt / "plan.json").write_text(json.dumps(p))
    for job in p["jobs"][:4]:
        (base / "snapshots" / job["snapshot_id"]).mkdir()
    assert any(r["moves"] == 20 for r in quarantine_c.admission(base))


def test_failed_attempt_record_preserves_and_admits(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    p = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(p))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": p["sha256"], "status": "failed"})
    )
    ident = p["jobs"][0]["snapshot_id"]
    snapshot = base / "snapshots" / ident
    snapshot.mkdir(parents=True)
    (snapshot / "pass-0.json").write_text("partial")
    args = SimpleNamespace(
        name="failed-0", reason="failed worker", failed_attempt="0", plan_sha256=None
    )
    result = quarantine_c.run(args)
    assert result["moves"] == 2
    assert not attempt.exists() and not snapshot.exists()
    assert (base / "quarantine/failed-0/native/0/receipt.json").exists()
    assert quarantine_c.admission(base)[0]["moves"] == 2


@pytest.mark.parametrize("status", ["captured", "accepted"])
def test_failed_attempt_refuses_success(tmp_path, monkeypatch, status):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    attempt = base / "native/0"
    attempt.mkdir(parents=True)
    p = capture_c.plan()
    (attempt / "plan.json").write_text(json.dumps(p))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": p["sha256"], "status": status})
    )
    with pytest.raises(ValueError):
        quarantine_c.run(
            SimpleNamespace(
                name="bad", reason="failed", failed_attempt="0", plan_sha256=None
            )
        )


def test_worker_traceback_message_only_without_absolute_path(tmp_path):
    try:
        raise ValueError("superseded evidence still active")
    except ValueError as exc:
        capture_policy.write_traceback(tmp_path, exc, worker=True)
    raw = (tmp_path / "worker-traceback.txt").read_text()
    assert "ValueError: superseded evidence still active" in raw
    assert "/Users/" not in raw
    try:
        raise ValueError("secret at /Users/person/private")
    except ValueError as exc:
        capture_policy.write_traceback(tmp_path, exc, worker=True)
    assert (tmp_path / "worker-traceback.txt").read_text() == raw
    quoted = tmp_path / "quoted"
    quoted.mkdir()
    try:
        raise ValueError("opened ('/Users/person/private')")
    except ValueError as exc:
        capture_policy.write_traceback(quoted, exc, worker=True)
    assert "Users" not in (quoted / "worker-traceback.txt").read_text()


def test_worker_admission_failure_retains_own_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    (base / "native/0").mkdir(parents=True)
    monkeypatch.setattr(
        quarantine_c,
        "admission",
        lambda base: (_ for _ in ()).throw(
            ValueError("superseded evidence still active")
        ),
    )
    args = ["--batch", "0", "--worker", "--output", str(capture_c.BASE / "native/0")]
    assert capture_c.main(args) == 2
    assert "internal_error" in capsys.readouterr().out
    raw = (base / "native/0/worker-traceback.txt").read_text()
    assert "ValueError: superseded evidence still active" in raw
    assert "capture_c.py" in raw


def test_failed_attempt_record_rejects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    p = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(p))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": p["sha256"], "status": "failed"})
    )
    args = SimpleNamespace(
        name="failed-0", reason="failed worker", failed_attempt="0", plan_sha256=None
    )
    quarantine_c.run(args)
    (base / "quarantine/failed-0/native/0/receipt.json").write_text(
        json.dumps({"plan_sha256": p["sha256"], "status": "captured"})
    )
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


@pytest.mark.parametrize(
    "fault",
    [
        "hash",
        "reason",
        "number",
        "root",
        "missing_move",
        "foreign_move",
        "path",
        "artifact",
        "active",
        "active_symlink",
        "extra",
    ],
)
def test_failed_attempt_admission_faults(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    p = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(p))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": p["sha256"], "status": "failed"})
    )
    (attempt / "browser.log").write_text("original")
    args = SimpleNamespace(
        name="failed-0", reason="failed worker", failed_attempt="0", plan_sha256=None
    )
    quarantine_c.run(args)
    folder = base / "quarantine/failed-0"
    path = folder / "QUARANTINE.json"
    record = json.loads(path.read_text())
    if fault == "hash":
        record["reason"] = "changed"
    elif fault == "reason":
        record["reason"] = ""
    elif fault == "number":
        record["attempt"] = "7"
    elif fault == "root":
        (folder / "extra").write_text("x")
    elif fault == "missing_move":
        record["moves"] = []
    elif fault == "foreign_move":
        record["moves"].append(
            {
                "source": "snapshots/unknown",
                "dest": "quarantine/failed-0/snapshots/unknown",
                "inventory": {"files": {}, "directories": []},
            }
        )
    elif fault == "path":
        record["moves"][0]["dest"] = "quarantine/failed-0/native/other"
    elif fault == "artifact":
        (folder / "native/0/browser.log").write_text("modified")
    elif fault == "active":
        shutil.copytree(folder / "native/0", base / "native/0")
    elif fault == "active_symlink":
        (base / "snapshots").mkdir()
        (base / "snapshots" / p["jobs"][0]["snapshot_id"]).symlink_to(
            folder / "native/0"
        )
    elif fault == "extra":
        (folder / "snapshots/extra").mkdir()
    if fault in {"reason", "number", "missing_move", "foreign_move", "path"}:
        path.write_text(json.dumps(inv.seal(record)))
    elif fault == "hash":
        path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


@pytest.mark.parametrize(
    "fault",
    [
        "number",
        "reason",
        "exists",
        "missing",
        "batch",
        "snapshot_symlink",
        "accepted",
        "snapshot_link",
        "both_modes",
    ],
)
def test_failed_attempt_writer_faults(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    attempt = base / "native/0"
    attempt.mkdir(parents=True)
    p = capture_c.plan()
    if fault == "batch":
        p = inv.seal({**p, "jobs": []})
    (attempt / "plan.json").write_text(json.dumps(p))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": p["sha256"], "status": "failed"})
    )
    args = SimpleNamespace(
        name="failed-0", reason="failed worker", failed_attempt="0", plan_sha256=None
    )
    if fault == "number":
        args.failed_attempt = "4"
    elif fault == "reason":
        args.reason = " "
    elif fault == "exists":
        quarantine_c.run(args)
    elif fault == "missing":
        shutil.rmtree(attempt)
    elif fault == "snapshot_symlink":
        (base / "snapshots").symlink_to(attempt, target_is_directory=True)
    elif fault == "accepted":
        snapshot = base / "snapshots" / p["jobs"][0]["snapshot_id"]
        snapshot.mkdir(parents=True)
        (snapshot / "complete.json").write_text("{}")
    elif fault == "snapshot_link":
        snapshot = base / "snapshots" / p["jobs"][0]["snapshot_id"]
        snapshot.parent.mkdir()
        snapshot.symlink_to(attempt)
    elif fault == "both_modes":
        args.plan_sha256 = "a" * 64
    with pytest.raises(ValueError):
        quarantine_c.run(args)
