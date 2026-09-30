"""Offline recapture and failed-attempt regressions against copied evidence."""

import json
import shutil
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from mve.observer import capture_c, capture_evidence, capture_policy, quarantine_c
from mve.observer import snapshot_inventory as inv, snapshots as s, storage
from tests.mve.observer.test_wo1d import old_quarantine_sources


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
    with pytest.raises(ValueError, match="unidentified active attempt"):
        quarantine_c.admission(base)
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
    (attempt / "receipt.json").write_text(json.dumps({"plan_sha256": p["sha256"]}))
    for job in p["jobs"][:4]:
        (base / "snapshots" / job["snapshot_id"]).mkdir()
    with pytest.raises(ValueError, match="unidentified active snapshot"):
        quarantine_c.admission(base)
    for job in p["jobs"][:4]:
        (base / "snapshots" / job["snapshot_id"] / "pass-0.json").write_text(
            "new pass metadata"
        )
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


@pytest.mark.parametrize("failures", [1, 2])
def test_same_plan_failed_batch_set_aside_retry_and_next_batch(
    tmp_path, monkeypatch, failures
):
    from tests.mve.observer.test_wo6c import capture_env, fake_packet, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.batch = 1
    base = tmp_path / capture_c.BASE
    current = capture_c.plan()
    calls = 0

    def fail_midway(context, root, job, versions, ocr, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise capture_policy.PageTimeoutError("page timeout")
        return fake_packet(job)

    for n in range(failures):
        calls = 0
        monkeypatch.setattr(capture_c.render, "capture_block", fail_midway)
        with pytest.raises(capture_policy.PageTimeoutError):
            capture_c.run(args)
        first = base / "snapshots" / current["jobs"][4]["snapshot_id"]
        assert (first / "pass-0.json").is_file()
        assert (base / "native/1/receipt.json").is_file()
        name = f"failed-b1-{n + 1}"
        result = quarantine_c.run(
            SimpleNamespace(
                name=name,
                reason="page timeout",
                failed_attempt="1",
                plan_sha256=None,
            )
        )
        assert result["moves"] == 5
        assert not first.exists()
        assert (base / "quarantine" / name / "snapshots" / first.name).is_dir()
        assert len(quarantine_c.admission(base)) == n + 1

    monkeypatch.setattr(
        capture_c.render, "capture_block", lambda c, r, j, v, o, **kw: fake_packet(j)
    )
    assert capture_c.run(args) == 0
    assert len(quarantine_c.admission(base)) == failures
    receipt = json.loads((base / "native/1/receipt.json").read_text())
    assert receipt["plan_sha256"] == current["sha256"]
    args.batch = 2
    assert capture_c.run(args) == 0
    assert len(quarantine_c.admission(base)) == failures


@pytest.mark.parametrize("failure_edge", ["renderer", "acceptance"])
def test_completed_batch_edge_set_aside_retry_and_next_batch(
    tmp_path, monkeypatch, failure_edge
):
    from mve.observer import snapshot_batch as batch
    from tests.mve.observer.test_wo6c import capture_env, fake_packet, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.batch = 1
    base = tmp_path / capture_c.BASE
    current = capture_c.plan()
    jobs = current["jobs"][4:8]
    unrelated = base / "snapshots" / current["jobs"][0]["snapshot_id"]
    unrelated.mkdir(parents=True)
    (unrelated / "other-batch.txt").write_text("preserve")
    original_accept = batch.accept_snapshot
    if failure_edge == "renderer":
        calls = 0

        def fail_after_two(context, root, job, versions, ocr, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                audit = dict(
                    source_repos_unchanged=True,
                    archive_unchanged=True,
                    source_audit_before_sha256="same",
                    source_audit_after_sha256="same",
                )
                for finished in jobs[:2]:
                    folder = base / "snapshots" / finished["snapshot_id"]
                    packet = fake_packet(
                        {
                            **finished,
                            "raw": capture_c.capture_data(
                                finished["module"], finished["source"]
                            ),
                        }
                    )
                    batch.save_pass(folder, 1, packet)
                    candidate = batch.finish_snapshot(
                        folder, current, finished, packet, packet, 0
                    )
                    original_accept(folder, current, finished, candidate, audit)
                raise capture_policy.PageTimeoutError("page timeout")
            return fake_packet(job)

        monkeypatch.setattr(capture_c.render, "capture_block", fail_after_two)
        with pytest.raises(capture_policy.PageTimeoutError):
            capture_c.run(args)
        assert (
            json.loads((base / "native/1/receipt.json").read_text())["status"]
            == "failed"
        )
    else:
        calls = 0

        def crash_during_acceptance(*accept_args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("acceptance interrupted")
            return original_accept(*accept_args)

        monkeypatch.setattr(batch, "accept_snapshot", crash_during_acceptance)
        with pytest.raises(RuntimeError, match="acceptance interrupted"):
            capture_c.run(args)
        monkeypatch.setattr(batch, "accept_snapshot", original_accept)
        assert (
            json.loads((base / "native/1/receipt.json").read_text())["status"]
            == "captured"
        )

    assert (
        sum(
            (base / "snapshots" / j["snapshot_id"] / "complete.json").is_file()
            for j in jobs
        )
        == 2
    )
    name = f"failed-b1-{failure_edge}"
    result = quarantine_c.run(
        SimpleNamespace(
            name=name, reason="batch interrupted", failed_attempt="1", plan_sha256=None
        )
    )
    assert result["moves"] == 5
    assert all(not (base / "snapshots" / j["snapshot_id"]).exists() for j in jobs)
    assert all(
        (base / "quarantine" / name / "snapshots" / j["snapshot_id"]).is_dir()
        for j in jobs
    )
    assert (unrelated / "other-batch.txt").read_text() == "preserve"
    assert quarantine_c.admission(base)[0]["moves"] == 5

    def fresh_packet(context, root, job, versions, ocr, **kwargs):
        return {**fake_packet(job), "state": {"retry": True}}

    monkeypatch.setattr(capture_c.render, "capture_block", fresh_packet)
    assert capture_c.run(args) == 0
    assert all(
        batch.completed(base / "snapshots" / j["snapshot_id"], current, j) for j in jobs
    )
    assert quarantine_c.admission(base)[0]["moves"] == 5
    args.batch = 2
    assert capture_c.run(args) == 0
    assert quarantine_c.admission(base)[0]["moves"] == 5


def test_copied_back_complete_snapshot_is_superseded(tmp_path, monkeypatch):
    from tests.mve.observer.test_wo6c import capture_env, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.batch = 1
    base = tmp_path / capture_c.BASE
    assert capture_c.run(args) == 0
    plan = capture_c.plan()
    ident = plan["jobs"][4]["snapshot_id"]
    (base / "snapshots" / plan["jobs"][7]["snapshot_id"] / "complete.json").unlink()
    quarantine_c.run(
        SimpleNamespace(
            name="partial-accept",
            reason="acceptance interrupted",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    retry = base / "native/1"
    retry.mkdir()
    (retry / "plan.json").write_text(json.dumps(plan))
    (retry / "receipt.json").write_text(
        json.dumps({"plan_sha256": plan["sha256"], "status": "failed", "retry": 2})
    )
    shutil.copytree(
        base / "quarantine/partial-accept/snapshots" / ident, base / "snapshots" / ident
    )
    with pytest.raises(ValueError, match="failed attempt evidence still active"):
        quarantine_c.admission(base)


def test_failed_attempt_copied_back_identical_inventory_is_superseded(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    current = capture_c.plan()
    attempt = base / "native/1"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed"})
    )
    ident = current["jobs"][4]["snapshot_id"]
    partial = base / "snapshots" / ident
    partial.mkdir(parents=True)
    (partial / "pass-0.json").write_text("partial")
    quarantine_c.run(
        SimpleNamespace(
            name="failed-b1-1",
            reason="page timeout",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    moved = base / "quarantine/failed-b1-1"
    shutil.copytree(moved / "native/1", attempt)
    with pytest.raises(ValueError, match="failed attempt evidence still active"):
        quarantine_c.admission(base)
    shutil.rmtree(attempt)
    shutil.copytree(moved / "snapshots" / ident, partial)
    with pytest.raises(ValueError, match="failed attempt evidence still active"):
        quarantine_c.admission(base)


@pytest.mark.parametrize(
    "case,admitted",
    [
        ("unfinished_fresh", True),
        ("unfinished_subset", False),
        ("unfinished_identical", False),
        ("completed_current", True),
        ("completed_wrong_plan", False),
        ("wrong_batch", False),
    ],
)
def test_same_plan_retry_snapshot_claim_and_inventory(
    tmp_path, monkeypatch, case, admitted
):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    current = capture_c.plan()
    ident = current["jobs"][4]["snapshot_id"]
    attempt = base / "native/1"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed"})
    )
    snapshot = base / "snapshots" / ident
    snapshot.mkdir(parents=True)
    (snapshot / "data.json").write_text("old data")
    (snapshot / "pass-0.json").write_text("old pass")
    quarantine_c.run(
        SimpleNamespace(
            name="failed-b1",
            reason="page timeout",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    old = base / "quarantine/failed-b1/snapshots" / ident
    retry = base / "native" / ("2" if case == "wrong_batch" else "1")
    retry.mkdir()
    (retry / "plan.json").write_text(json.dumps(current))
    (retry / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed", "retry": 2})
    )
    snapshot.mkdir()
    if case == "unfinished_identical":
        shutil.copy2(old / "data.json", snapshot / "data.json")
        shutil.copy2(old / "pass-0.json", snapshot / "pass-0.json")
    elif case == "unfinished_subset":
        shutil.copy2(old / "data.json", snapshot / "data.json")
    else:
        (snapshot / "data.json").write_text("new data")
    if case.startswith("completed"):
        (snapshot / "complete.json").write_text(
            json.dumps(
                {
                    "plan_sha256": current["sha256"]
                    if case == "completed_current"
                    else "f" * 64
                }
            )
        )
    if admitted:
        assert quarantine_c.admission(base)[0]["moves"] == 2
    else:
        with pytest.raises(ValueError):
            quarantine_c.admission(base)


def test_same_plan_retry_unmoved_completion_requires_current_plan(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    current = capture_c.plan()
    ident = current["jobs"][4]["snapshot_id"]
    attempt = base / "native/1"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed"})
    )
    quarantine_c.run(
        SimpleNamespace(
            name="failed-b1",
            reason="page timeout",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    attempt.mkdir()
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed", "retry": 2})
    )
    snapshot = base / "snapshots" / ident
    snapshot.mkdir(parents=True)
    (snapshot / "complete.json").write_text(json.dumps({"plan_sha256": "f" * 64}))
    with pytest.raises(ValueError, match="unrecorded failed attempt snapshot"):
        quarantine_c.admission(base)
    (snapshot / "complete.json").write_text(
        json.dumps({"plan_sha256": current["sha256"]})
    )
    assert quarantine_c.admission(base)[0]["moves"] == 1


@pytest.mark.parametrize(
    "provenance", ["missing_receipt", "wrong_receipt", "wrong_plan"]
)
def test_same_plan_retry_native_requires_current_plan_and_receipt(
    tmp_path, monkeypatch, provenance
):
    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    current = capture_c.plan()
    attempt = base / "native/1"
    attempt.mkdir(parents=True)
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed"})
    )
    quarantine_c.run(
        SimpleNamespace(
            name="failed-b1",
            reason="page timeout",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    attempt.mkdir()
    wrong = inv.seal({**current, "development_sha256": "f" * 64})
    (attempt / "plan.json").write_text(
        json.dumps(wrong if provenance == "wrong_plan" else current)
    )
    if provenance != "missing_receipt":
        (attempt / "receipt.json").write_text(
            json.dumps(
                {
                    "plan_sha256": "f" * 64
                    if provenance == "wrong_receipt"
                    else current["sha256"],
                    "retry": 2,
                }
            )
        )
    with pytest.raises(ValueError, match="unidentified active attempt"):
        quarantine_c.admission(base)


def test_fully_accepted_batch_cannot_be_set_aside(tmp_path, monkeypatch):
    from tests.mve.observer.test_wo6c import capture_env, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.batch = 1
    assert capture_c.run(args) == 0
    base = tmp_path / capture_c.BASE
    with pytest.raises(ValueError, match="accepted"):
        quarantine_c.run(
            SimpleNamespace(
                name="bad",
                reason="fully accepted",
                failed_attempt="1",
                plan_sha256=None,
            )
        )
    assert (base / "native/1").is_dir()
    assert not (base / "quarantine/bad").exists()


def test_captured_receipt_with_invalid_completion_can_be_set_aside(
    tmp_path, monkeypatch
):
    from tests.mve.observer.test_wo6c import capture_env, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.batch = 1
    assert capture_c.run(args) == 0
    base = tmp_path / capture_c.BASE
    ident = capture_c.plan()["jobs"][7]["snapshot_id"]
    (base / "snapshots" / ident / "complete.json").write_text("{}")
    result = quarantine_c.run(
        SimpleNamespace(
            name="invalid-completion",
            reason="acceptance validation interrupted",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    assert result["moves"] == 5
    assert quarantine_c.admission(base)[0]["moves"] == 5


def test_failed_record_reader_rejects_fully_accepted_captured_batch(
    tmp_path, monkeypatch
):
    from tests.mve.observer.test_wo6c import capture_env, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.batch = 1
    assert capture_c.run(args) == 0
    base = tmp_path / capture_c.BASE
    ident = capture_c.plan()["jobs"][7]["snapshot_id"]
    completed = base / "snapshots" / ident / "complete.json"
    sealed_completion = completed.read_bytes()
    completed.unlink()
    quarantine_c.run(
        SimpleNamespace(
            name="partial-acceptance",
            reason="acceptance interrupted",
            failed_attempt="1",
            plan_sha256=None,
        )
    )
    folder = base / "quarantine/partial-acceptance"
    moved = folder / "snapshots" / ident
    (moved / "complete.json").write_bytes(sealed_completion)
    record_path = folder / "QUARANTINE.json"
    record = json.loads(record_path.read_text())
    for move in record["moves"]:
        if move["source"] == f"snapshots/{ident}":
            move["inventory"] = quarantine_c.inventory(moved)
    record_path.write_text(json.dumps(inv.seal(record)))
    with pytest.raises(ValueError, match="accepted batch cannot be set aside"):
        quarantine_c.admission(base)


@pytest.mark.parametrize("status", ["accepted", "prepared_only"])
def test_failed_attempt_refuses_other_status(tmp_path, monkeypatch, status):
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


@pytest.mark.parametrize(
    "plan_kind,receipt_kind",
    [
        ("superseded", "current"),
        ("current", "superseded"),
        ("current", "other"),
    ],
)
def test_active_attempt_refuses_superseded_or_inconsistent_provenance(
    tmp_path, monkeypatch, plan_kind, receipt_kind
):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    old = json.loads((base / "quarantine/old-plan/native/0/plan.json").read_text())
    current = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir()
    (attempt / "plan.json").write_text(
        json.dumps(old if plan_kind == "superseded" else current)
    )
    sha = {"current": current["sha256"], "superseded": old["sha256"], "other": "f" * 64}
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": sha[receipt_kind]})
    )
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


def test_active_attempt_refuses_symlinked_receipt(tmp_path, monkeypatch):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    current = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir()
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt-target.json").write_text(
        json.dumps({"plan_sha256": current["sha256"]})
    )
    (attempt / "receipt.json").symlink_to("receipt-target.json")
    with pytest.raises(ValueError, match="symlink active provenance"):
        quarantine_c.admission(base)


@pytest.mark.parametrize(
    "claim,contents",
    [
        ("superseded_plan", "fresh"),
        ("wrong_batch", "fresh"),
        ("missing_receipt", "fresh"),
        ("identical", "identical"),
        ("derived_subset", "derived_subset"),
    ],
)
def test_unfinished_snapshot_refuses_unowned_or_superseded_bytes(
    tmp_path, monkeypatch, claim, contents
):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    if contents == "derived_subset":
        ident = capture_c.plan()["jobs"][0]["snapshot_id"]
        (base / "snapshots" / ident / "pass-0.json").write_text("old pass")
    quarantine_c.run(args)
    old = json.loads((base / "quarantine/old-plan/native/0/plan.json").read_text())
    current = capture_c.plan()
    number = "1" if claim == "wrong_batch" else "0"
    attempt = base / "native" / number
    attempt.mkdir()
    (attempt / "plan.json").write_text(
        json.dumps(old if claim == "superseded_plan" else current)
    )
    if claim != "missing_receipt":
        (attempt / "receipt.json").write_text(
            json.dumps({"plan_sha256": current["sha256"]})
        )
    ident = current["jobs"][0]["snapshot_id"]
    snapshot = base / "snapshots" / ident
    if contents == "identical":
        shutil.copytree(base / "quarantine/old-plan/snapshots" / ident, snapshot)
    else:
        snapshot.mkdir()
        (snapshot / "data.json").write_text(
            "{}" if contents == "derived_subset" else "new capture"
        )
    if contents == "derived_subset":
        active = quarantine_c.inventory(snapshot)["files"]
        old_files = quarantine_c.inventory(
            base / "quarantine/old-plan/snapshots" / ident
        )["files"]
        assert active != old_files and active.items() <= old_files.items()
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


def test_unfinished_snapshot_accepts_current_batch_with_fresh_bytes(
    tmp_path, monkeypatch
):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    current = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir()
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"], "status": "failed"})
    )
    snapshot = base / "snapshots" / current["jobs"][0]["snapshot_id"]
    snapshot.mkdir()
    (snapshot / "data.json").write_text("new capture")
    assert quarantine_c.admission(base)[0]["moves"] == 20


def test_completed_current_plan_recapture_admits_shared_render_bytes(
    tmp_path, monkeypatch
):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    current = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir()
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"]})
    )
    ident = current["jobs"][0]["snapshot_id"]
    snapshot = base / "snapshots" / ident
    shutil.copytree(base / "quarantine/old-plan/snapshots" / ident, snapshot)
    old_files = quarantine_c.inventory(base / "quarantine/old-plan/snapshots" / ident)[
        "files"
    ]
    assert (
        old_files["data.json"] == quarantine_c.inventory(snapshot)["files"]["data.json"]
    )
    (snapshot / "complete.json").write_text(
        json.dumps({"plan_sha256": current["sha256"]})
    )
    assert quarantine_c.admission(base)[0]["moves"] == 20


@pytest.mark.parametrize("claim", ["missing_receipt", "wrong_batch"])
def test_completed_current_plan_snapshot_requires_claim(tmp_path, monkeypatch, claim):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    current = capture_c.plan()
    number = "1" if claim == "wrong_batch" else "0"
    attempt = base / "native" / number
    attempt.mkdir()
    (attempt / "plan.json").write_text(json.dumps(current))
    if claim != "missing_receipt":
        (attempt / "receipt.json").write_text(
            json.dumps({"plan_sha256": current["sha256"]})
        )
    ident = current["jobs"][0]["snapshot_id"]
    snapshot = base / "snapshots" / ident
    shutil.copytree(base / "quarantine/old-plan/snapshots" / ident, snapshot)
    (snapshot / "complete.json").write_text(
        json.dumps({"plan_sha256": current["sha256"]})
    )
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


def test_unfinished_current_batch_admits_overlap_with_new_artifact(
    tmp_path, monkeypatch
):
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    current = capture_c.plan()
    attempt = base / "native/0"
    attempt.mkdir()
    (attempt / "plan.json").write_text(json.dumps(current))
    (attempt / "receipt.json").write_text(
        json.dumps({"plan_sha256": current["sha256"]})
    )
    ident = current["jobs"][0]["snapshot_id"]
    snapshot = base / "snapshots" / ident
    shutil.copytree(base / "quarantine/old-plan/snapshots" / ident, snapshot)
    (snapshot / "pass-0.json").write_text("new pass metadata")
    assert quarantine_c.admission(base)[0]["moves"] == 20


def test_fake_renderer_two_batches_admit_deterministic_recapture(tmp_path, monkeypatch):
    from tests.mve.observer.test_wo6c import capture_env, png, sandbox

    sandbox.__wrapped__(tmp_path, monkeypatch)
    render_args = capture_env.__wrapped__(tmp_path, monkeypatch)
    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    current = capture_c.plan()
    rendered_png = png()
    repeat = dict(
        tolerance=s.PNG_REPEAT_TOLERANCE,
        data_bytes_equal=True,
        full=s.compare_png(BytesIO(rendered_png), BytesIO(rendered_png)),
        blind=s.compare_png(BytesIO(rendered_png), BytesIO(rendered_png)),
    )
    repeat["passed"] = repeat["data_bytes_equal"] and all(
        repeat[key]["passed"] for key in ("full", "blind")
    )
    for job in current["jobs"][:4]:
        snapshot = base / "snapshots" / job["snapshot_id"]
        (snapshot / "data.json").write_bytes(
            capture_c.capture_data(job["module"], job["source"])
        )
        (snapshot / "blind-0.png").write_bytes(rendered_png)
        (snapshot / "blind-1.png").write_bytes(rendered_png)
        (snapshot / "difference.json").write_bytes(inv.encoded(repeat))
    quarantine_c.run(args)
    render_args.prepare_only = False
    assert capture_c.run(render_args) == 0
    assert quarantine_c.admission(base)[0]["moves"] == 20
    for job in current["jobs"][:4]:
        ident = job["snapshot_id"]
        active_files = quarantine_c.inventory(base / "snapshots" / ident)["files"]
        old_files = quarantine_c.inventory(
            base / "quarantine/old-plan/snapshots" / ident
        )["files"]
        for name in ("data.json", "blind-0.png", "blind-1.png", "difference.json"):
            assert active_files[name] == old_files[name]
    render_args.batch = 1
    assert capture_c.run(render_args) == 0
    assert quarantine_c.admission(base)[0]["moves"] == 20


def test_native_capture_seals_receipt_before_worker_admission(tmp_path, monkeypatch):
    from tests.mve.observer.test_wo6c import sandbox, capture_env

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False

    def isolated(a, out, repos, receipt):
        early = json.loads((out / "receipt.json").read_text())
        assert early["plan_sha256"] == capture_c.plan()["sha256"]
        assert early["status"] == "failed"
        assert quarantine_c.admission(tmp_path / capture_c.BASE) == []
        raise capture_policy.PageTimeoutError("snapshot timeout")

    monkeypatch.setattr(capture_c.old, "isolated_capture", isolated)
    with pytest.raises(capture_policy.PageTimeoutError):
        capture_c.run(args)
    final = json.loads(
        (tmp_path / capture_c.BASE / "native/0/receipt.json").read_text()
    )
    assert final["failure_type"] == "PageTimeoutError"


@pytest.mark.parametrize(
    "message",
    [
        "api_token_sk_live_abc123secret",
        "relative/private/customer.csv",
        "/Users/person/private/customer.csv",
        "https://example.org/private?token=abc123",
    ],
)
def test_worker_traceback_redacts_token_or_path_message(tmp_path, message):
    try:
        raise ValueError(message)
    except ValueError as exc:
        capture_policy.write_traceback(tmp_path, exc, worker=True)
    raw = (tmp_path / "worker-traceback.txt").read_text()
    assert message not in raw
    assert raw.startswith("ValueError: <redacted>\n")


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
    elif fault == "snapshot_link":
        snapshot = base / "snapshots" / p["jobs"][0]["snapshot_id"]
        snapshot.parent.mkdir()
        snapshot.symlink_to(attempt)
    elif fault == "both_modes":
        args.plan_sha256 = "a" * 64
    with pytest.raises(ValueError):
        quarantine_c.run(args)
