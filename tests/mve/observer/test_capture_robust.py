"""Offline regressions; owner evidence is only ever opened for reading."""

import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from mve.observer import capture_policy as policy
from mve.observer import snapshot_batch as batch, snapshot_inventory as inv
from mve.observer import snapshot_render as render
from tests.mve.observer.test_snapshot_batch import fake_batch_env, fake_packet  # noqa: F401


@pytest.fixture
def robust_env(tmp_path, monkeypatch):
    return fake_batch_env.__wrapped__(tmp_path, monkeypatch)


REAL = (
    Path.home()
    / "Developer/Opensens/worktrees/oae-mve-wo1b/mve/generated/wo1b-d286a45abc8187fd"
)


def test_bounds_are_derived_and_bounded():
    a = batch.parse_args(["--plan", "x", "--batch", "7"])
    assert a.page_load_timeout == 120
    assert a.timeout_per_pass == 1860
    assert a.overall_timeout == 3840
    for option, value in [
        ("page-load-timeout", "0"),
        ("page-load-timeout", "121"),
        ("timeout-per-pass", "1859"),
        ("timeout-per-pass", "1861"),
        ("max-load", "nan"),
        ("max-load", "-1"),
    ]:
        with pytest.raises(SystemExit):
            batch.parse_args(["--plan", "x", "--batch", "7", "--" + option, value])


def test_load_refusal_precedes_any_directory(robust_env, monkeypatch, capsys):
    monkeypatch.setattr(policy.os, "getloadavg", lambda: (70.0, 60.0, 50.0))
    assert (
        batch.main(
            ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "7", "--max-load", "10"]
        )
        == 2
    )
    assert "host_load" in capsys.readouterr().out
    assert not (robust_env / "mve").exists()


def test_real_resume_read_only():
    if not REAL.exists():
        pytest.skip("owner evidence unavailable")
    before = batch.s.tree_listing(REAL)
    plan = inv.load()
    assert plan["sha256"].startswith("d286a45abc8187fd")
    state = batch.resume_state(REAL, plan)
    assert len(state["completed"]) == 70
    assert len(state["remaining"]) == 210
    selected = batch.select_jobs(plan, 7)
    assert {j["snapshot_id"] for j in selected} <= {
        j["snapshot_id"] for j in state["remaining"]
    }
    for record in state["quarantine"]:
        assert set(record["snapshot_ids"]) == {j["snapshot_id"] for j in selected}
    assert len(state["quarantine"]) == 2
    assert batch.s.tree_listing(REAL) == before


def test_new_receipts_load_versions_and_timeouts(robust_env, monkeypatch):
    monkeypatch.setattr(policy.os, "getloadavg", lambda: (1.0, 2.0, 3.0))
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]) == 0
    receipt = json.loads(next(robust_env.rglob("receipt.json")).read_text())
    assert receipt["load_start"] == receipt["load_end"] == [1.0, 2.0, 3.0]
    assert (
        receipt["browser_version_start"]
        == receipt["browser_version_end"]
        == "153.fixture"
    )
    assert receipt["browser_version"] == "153.fixture"
    for p in robust_env.rglob("complete.json"):
        assert json.loads(p.read_text())["browser_version"] == "153.fixture"


def test_versions_fail_closed():
    for versions in [[], [None], ["152", "153"]]:
        with pytest.raises(ValueError, match="renderer"):
            policy.one_version(versions)
    assert policy.one_version(["152", "152"]) == "152"


def test_navigation_timeout_explicit_and_no_retry():
    plan = inv.load()
    j = inv.jobs(plan)[0]
    j["raw"] = inv.block_data(plan, j["block"], purpose="capture")
    context = Mock()
    page = context.new_page.return_value
    page.goto.side_effect = TimeoutError("load")
    with pytest.raises(TimeoutError):
        render.capture_block(context, None, j, {}, None, page_load_timeout=120)
    assert page.goto.call_count == 1
    assert page.goto.call_args.kwargs["timeout"] == 120000
    page.close.assert_called_once()


def test_drift_separate_immutable_output(robust_env):
    from mve.observer import renderer_drift as drift

    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]
    assert batch.main(args + ["--pilot"]) == 0
    accepted = next(robust_env.glob("mve/generated/wo1b-*"))
    before = batch.s.tree_listing(accepted)
    cmd = args + [
        "--drift-cluster",
        "spectral-ordinary-0",
        "--drift-from",
        str(accepted),
        "--drift-output",
        "mve/generated/drift-test",
    ]
    assert drift.main(cmd) == 0
    r = json.loads(
        next((robust_env / "mve/generated/drift-test").rglob("drift.json")).read_text()
    )
    assert r["passed"] and len(r["comparisons"]) == 10
    assert all(
        row["data_bytes_equal"]
        and row["blind_0"]["pixels_over_threshold_fraction"] == 0
        for row in r["comparisons"]
    )
    assert drift.main(cmd) == 2
    assert batch.s.tree_listing(accepted) == before


@pytest.mark.parametrize("phase", ["between_passes", "end", "end_unreadable"])
def test_renderer_drift_never_accepts(robust_env, monkeypatch, phase):
    if phase.startswith("end"):
        calls = iter(["153.fixture", "154.fixture"])

        def version(_):
            value = next(calls)
            if phase == "end_unreadable" and value == "154.fixture":
                raise OSError("bundle updating")
            return value

        monkeypatch.setattr(policy, "browser_version", version)
    else:
        count = 0

        def packet(context, root, job, versions, ocr, **kw):
            nonlocal count
            count += 1
            p = fake_packet(job, job["raw"])
            p["versions"]["chrome"] = "153.fixture" if count <= 10 else "154.fixture"
            return p

        monkeypatch.setattr(render, "capture_block", packet)
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]) == 2
    assert not list(robust_env.rglob("complete.json"))
    r = json.loads(next(robust_env.rglob("receipt.json")).read_text())
    assert r["source_repos_unchanged"] and "load_end" in r


def test_cross_batch_cluster_version_refusal(robust_env, monkeypatch):
    args = ["--plan", str(inv.ROOT / inv.PLAN)]
    assert batch.main(args + ["--batch", "0"]) == 0
    monkeypatch.setattr(policy, "browser_version", lambda _: "154.fixture")
    # Batch 3 contains blocks belonging to the cluster begun in batch 0.
    assert batch.main(args + ["--batch", "3"]) == 2
    assert not list(robust_env.rglob("batch-003-*"))


def test_deadline_restores_outer_and_expires():
    import signal
    import time

    prior = signal.getsignal(signal.SIGALRM)
    with policy.deadline(2):
        with policy.deadline(1):
            assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 1
        assert 1 < signal.getitimer(signal.ITIMER_REAL)[0] <= 2
    assert signal.getsignal(signal.SIGALRM) == prior
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0
    with pytest.raises(ValueError, match="snapshot timeout"):
        with policy.deadline(0.01):
            time.sleep(0.02)


def test_version_read_without_browser_launch(tmp_path):
    import plistlib

    contents = tmp_path / "Chrome.app/Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "153.0.8010.54"})
    )
    assert policy.browser_version(contents / "MacOS/Google Chrome") == "153.0.8010.54"


def quarantine_fixture(tmp_path, plan):
    selected = {j["snapshot_id"]: {} for j in batch.select_jobs(plan, 7)}
    attempt = tmp_path / "batch-007-000"
    attempt.mkdir()
    receipt = dict(
        batch=7,
        selected=list(selected),
        source_repos_unchanged=True,
        archive_unchanged=True,
        source_audit_before_sha256="same",
        source_audit_after_sha256="same",
    )
    (attempt / "receipt.json").write_text(json.dumps(receipt))
    q = tmp_path / "quarantine/batch-007-000"
    q.mkdir(parents=True)
    for ident in selected:
        folder = q / ident
        folder.mkdir()
        (folder / "data.json").write_bytes(b"original")
        selected[ident]["data.json"] = batch.sha(b"original")
    record = dict(
        schema="mve-wo1b-quarantine-v1",
        attempt=attempt.name,
        batch=7,
        snapshots=selected,
        source_repos_unchanged=True,
        archive_unchanged=True,
        attempt_receipt_sha256=batch.s.sha256(attempt / "receipt.json"),
    )
    (q / "QUARANTINE.json").write_text(json.dumps(record))
    return q, record


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "missing",
        "extra",
        "symlink",
        "schema",
        "identity",
        "selection",
        "attempt_hash",
        "unsafe_name",
    ],
)
def test_quarantine_tampering_refused(tmp_path, change):
    from mve.observer.capture_evidence import quarantine

    plan = inv.load()
    q, record = quarantine_fixture(tmp_path, plan)
    assert len(quarantine(tmp_path, plan)) == 1
    folder = q / next(iter(record["snapshots"]))
    if change == "bytes":
        (folder / "data.json").write_bytes(b"changed")
    elif change == "missing":
        (folder / "data.json").unlink()
    elif change == "extra":
        (q / "extra").write_bytes(b"x")
    elif change == "symlink":
        (folder / "data.json").unlink()
        (folder / "data.json").symlink_to(q / "QUARANTINE.json")
    elif change == "schema":
        record["schema"] = "unknown"
    elif change == "identity":
        record["attempt"] = "other"
    elif change == "selection":
        record["snapshots"].pop(next(iter(record["snapshots"])))
    elif change == "unsafe_name":
        record["snapshots"][folder.name] = {"../data.json": "x"}
        # Exercise the path guard directly as file-set validation is earlier.
        from mve.observer.capture_evidence import plain_child

        with pytest.raises(ValueError):
            plain_child(folder, "../data.json")
    else:
        record["attempt_receipt_sha256"] = "bad"
    (q / "QUARANTINE.json").write_text(json.dumps(record))
    with pytest.raises((ValueError, OSError)):
        quarantine(tmp_path, plan)


def test_unknown_snapshot_and_cluster_size(tmp_path):
    (tmp_path / "snapshots/unknown").mkdir(parents=True)
    with pytest.raises(ValueError, match="unknown snapshot"):
        batch.resume_state(tmp_path, inv.load())
    with pytest.raises(ValueError):
        batch.select_jobs(inv.load(), 0, size=5)


def test_real_evidence_resume_captures_only_batch_seven(robust_env, monkeypatch):
    import shutil

    if not REAL.exists():
        pytest.skip("owner evidence unavailable")
    original = batch.s.tree_listing(REAL)
    target = robust_env / "mve/generated" / REAL.name
    shutil.copytree(REAL, target)
    old = {p.name: batch.s.tree_listing(p) for p in (target / "snapshots").iterdir()}
    versions = {
        json.loads(p.read_text())["versions"]["chrome"]
        for p in target.glob("snapshots/*/pass-0.json")
    }
    version = policy.one_version(versions)
    monkeypatch.setattr(policy, "browser_version", lambda _: version)
    seen = []

    def capture(context, root, job, versions, ocr, **kw):
        seen.append(job["snapshot_id"])
        packet = fake_packet(job, job["raw"])
        packet["versions"]["chrome"] = version
        return packet

    monkeypatch.setattr(render, "capture_block", capture)
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "7"]) == 0
    expected = [j["snapshot_id"] for j in batch.select_jobs(inv.load(), 7)]
    assert seen == expected * 2
    assert len(list(target.glob("snapshots/*/complete.json"))) == 80
    for name, listing in old.items():
        assert batch.s.tree_listing(target / "snapshots" / name) == listing
    assert batch.s.tree_listing(REAL) == original


def test_historical_152_completion_still_verifies(robust_env):
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]) == 0
    plan = inv.load()
    job = inv.jobs(plan)[0]
    folder = (
        next(robust_env.glob("mve/generated/wo1b-*")) / "snapshots" / job["snapshot_id"]
    )
    receipt = json.loads((folder / "complete.json").read_text())
    receipt.pop("browser_version")  # Legacy format, no surfaced version.
    for n in (0, 1):
        p = folder / f"pass-{n}.json"
        r = json.loads(p.read_text())
        r["versions"].update(
            chrome="152.0.fixture", snapshot_render_sha256="original-runtime"
        )
        p.write_bytes(inv.encoded(r))
        receipt["files"][p.name] = batch.s.sha256(p)
    (folder / "complete.json").write_bytes(inv.encoded(inv.seal(receipt)))
    assert batch.completed(folder, plan, job)


def test_drift_guards_and_failure_receipt(robust_env, monkeypatch):
    from mve.observer import renderer_drift as drift

    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]
    assert drift.main(args) == 2
    plan = inv.load()
    jobs = batch.select_jobs(plan, 0, pilot=True)
    with pytest.raises(ValueError):
        drift.accepted_cluster(robust_env, plan, [])
    with pytest.raises(ValueError):
        drift.accepted_cluster(robust_env, plan, jobs[:1])
    with pytest.raises(ValueError):
        drift.accepted_cluster(robust_env, plan, jobs)
    assert batch.main(args + ["--pilot"]) == 0
    accepted = next(robust_env.glob("mve/generated/wo1b-*"))
    cmd = args + [
        "--drift-from",
        str(accepted),
        "--drift-output",
        "mve/generated/drift-failure",
        "--drift-cluster",
        "spectral-ordinary-0",
    ]
    original_compare = drift.compare

    def different(*a):
        r = original_compare(*a)
        r["comparisons"][0]["blind_0"]["pixels_over_threshold_fraction"] = 0.2
        r["passed"] = False
        return inv.seal(r)

    monkeypatch.setattr(drift, "compare", different)
    assert drift.main(cmd) == 2
    assert (
        json.loads(
            next(
                (robust_env / "mve/generated/drift-failure").rglob("drift.json")
            ).read_text()
        )["passed"]
        is False
    )
    assert batch.main(args + ["--drift-from", str(accepted)]) == 2
    bad = args + [
        "--drift-from",
        str(accepted),
        "--drift-output",
        str(accepted.relative_to(robust_env)),
        "--drift-cluster",
        "spectral-ordinary-0",
    ]
    assert batch.main(bad) == 2
    assert batch.main(cmd + ["--drift-cluster", "absent"]) == 2


def test_actual_browser_context_version_checks_are_mocked(tmp_path, monkeypatch):
    import playwright.sync_api

    context = Mock()
    context.browser.version = "153.fixture"
    manager = Mock()
    manager.__enter__ = Mock(return_value=manager)
    manager.__exit__ = Mock(return_value=False)
    manager.chromium.launch_persistent_context.return_value = context
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: manager)
    monkeypatch.setattr(policy, "browser_version", lambda _: "153.fixture")
    jobs = [dict(snapshot_id="fixture")]
    assert render.run_browser(
        tmp_path,
        tmp_path / "pass-0",
        "unused",
        None,
        tmp_path,
        jobs=jobs,
        capture=lambda *a: "packet",
    ) == ["packet"]

    def change(*a):
        context.browser.version = "154.fixture"
        return "packet"

    with pytest.raises(ValueError, match="renderer"):
        render.run_browser(
            tmp_path,
            tmp_path / "pass-1",
            "unused",
            None,
            tmp_path,
            jobs=jobs,
            capture=change,
        )
    assert context.close.call_count == 2
    capture = Mock()
    with pytest.raises(policy.RendererVersionError):
        render.run_browser(
            tmp_path,
            tmp_path / "pass-2",
            "unused",
            None,
            tmp_path,
            jobs=jobs,
            capture=capture,
        )
    capture.assert_not_called()
    assert context.close.call_count == 3


def test_policy_low_bounds_and_invalid_count():
    from types import SimpleNamespace

    a = SimpleNamespace(page_load_timeout=60, timeout_per_pass=None, max_load=10)
    assert policy.bounds(a, 4)["overall_seconds"] == 1200
    with pytest.raises(ValueError):
        policy.bounds(a, 11)


def test_drift_pixel_fraction_from_changed_packets(robust_env, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from mve.observer import renderer_drift as drift

    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]
    assert batch.main(args + ["--pilot"]) == 0
    accepted = next(robust_env.glob("mve/generated/wo1b-*"))

    def changed(context, root, job, versions, ocr, **kw):
        packet = fake_packet(job, job["raw"])
        im = Image.open(BytesIO(packet["blind"])).convert("RGB")
        im.paste((255, 0, 0), (0, 0, 64, 400))
        stream = BytesIO()
        im.save(stream, format="PNG")
        packet["blind"] = stream.getvalue()
        return packet

    monkeypatch.setattr(render, "capture_block", changed)
    assert (
        drift.main(
            args
            + [
                "--drift-cluster",
                "spectral-ordinary-0",
                "--drift-from",
                str(accepted),
                "--drift-output",
                "mve/generated/drift-pixels",
            ]
        )
        == 2
    )
    r = json.loads(
        next(
            (robust_env / "mve/generated/drift-pixels").rglob("drift.json")
        ).read_text()
    )
    assert not r["passed"]
    assert all(
        row["data_bytes_equal"]
        and row["blind_0"]["pixels_over_threshold_fraction"] == 0.1
        for row in r["comparisons"]
    )


def test_invalid_navigation_bound_before_page_creation():
    context = Mock()
    with pytest.raises(ValueError, match="bounded"):
        render.capture_block(context, None, {}, {}, None, page_load_timeout=121)
    context.new_page.assert_not_called()


def test_drift_output_race_checked_under_lock(robust_env, monkeypatch):
    from contextlib import contextmanager

    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]
    assert batch.main(args + ["--pilot"]) == 0
    accepted = next(robust_env.glob("mve/generated/wo1b-*"))
    target = robust_env / "mve/generated/drift-race"

    @contextmanager
    def race():
        target.mkdir()
        yield

    monkeypatch.setattr(batch.storage, "lock", race)
    assert (
        batch.main(
            args
            + [
                "--drift-cluster",
                "spectral-ordinary-0",
                "--drift-from",
                str(accepted),
                "--drift-output",
                "mve/generated/drift-race",
            ]
        )
        == 2
    )
    assert list(target.iterdir()) == []
