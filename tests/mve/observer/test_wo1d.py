"""WO-1d offline regressions; no native browser or network."""

import json
import os
import plistlib
from types import SimpleNamespace

import pytest

from mve.observer import capture_policy as policy, capture_c, renderer_pin
from mve.observer import snapshot_render as render


def synthetic_bundle(tmp_path):
    contents = tmp_path / "Browser.app" / "Contents"
    versions = (
        contents / "Frameworks" / "Google Chrome Framework.framework" / "Versions"
    )
    tree = versions / "153.0.8010.54"
    tree.mkdir(parents=True)
    (tree / "binary").write_bytes(b"framework")
    (tree / "alias").symlink_to("binary")
    (versions / "Current").symlink_to("153.0.8010.54")
    chrome = contents / "MacOS" / "Google Chrome"
    chrome.parent.mkdir()
    chrome.write_bytes(b"launcher")
    (contents / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "153.0.8010.54"})
    )
    return chrome


def test_space08_control_after_default_timeout_and_expiry():
    class Page:
        def __init__(self, appears):
            self.appears = appears
            self.clock = 0
            self.timeout = 30000

        def set_default_timeout(self, ms):
            self.timeout = ms

        def select_option(self, selector, value, **kw):
            if selector == "#psView":
                assert self.timeout > 30000
                if not self.appears:
                    raise policy.PageTimeoutError("control never appeared")
                self.clock += 69000

        def locator(self, selector):
            return SimpleNamespace(set_checked=lambda *a, **k: None)

        def evaluate(self, *a):
            pass

        def wait_for_function(self, *a, **k):
            pass

    job = {"module": "space-08", "control": {"kind": "none"}}
    page = Page(True)
    render.configure(page, job, action_timeout_ms=150000)
    assert page.clock == 69000
    with pytest.raises(policy.PageTimeoutError) as exc:
        render.configure(Page(False), job, action_timeout_ms=150000)
    assert exc.value.label == "page_timeout"


def test_bounds_cover_slow_space08():
    args = SimpleNamespace(page_load_timeout=120, timeout_per_pass=None, max_load=None)
    b = policy.bounds(args, 10)
    assert b["snapshot_seconds"] >= 120 + 150
    assert b["pass_seconds"] >= 10 * b["snapshot_seconds"] + 60
    assert b["overall_seconds"] == 2 * b["pass_seconds"] + 120


def test_bundle_record_and_each_component(tmp_path, monkeypatch):
    chrome = synthetic_bundle(tmp_path)
    candidate = renderer_pin.candidate(chrome)
    assert candidate["launcher_sha256"] and candidate["info_plist_sha256"]
    assert candidate["versions_current_target"] == "153.0.8010.54"
    assert candidate["bundle_symlinks"]
    monkeypatch.setattr(renderer_pin, "record", lambda _: candidate)
    monkeypatch.setattr(
        renderer_pin.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout="Google Chrome 153.0.8010.54\n"),
    )
    assert renderer_pin.preflight(chrome, "chrome-153") == "153.0.8010.54"
    for path, change in [
        (chrome, lambda p: p.write_bytes(b"changed")),
        (
            chrome.parent.parent / "Info.plist",
            lambda p: p.write_bytes(p.read_bytes() + b" "),
        ),
        (
            chrome.parent.parent
            / "Frameworks/Google Chrome Framework.framework/Versions/153.0.8010.54/alias",
            lambda p: (p.unlink(), p.symlink_to("other")),
        ),
    ]:
        before = path.read_bytes() if not path.is_symlink() else os.readlink(path)
        change(path)
        with pytest.raises(policy.RendererPinError):
            renderer_pin.preflight(chrome, "chrome-153")
        path.unlink()
        if isinstance(before, bytes):
            path.write_bytes(before)
        else:
            path.symlink_to(before)


def test_unlabeled_exception_is_internal_error(monkeypatch, capsys):
    monkeypatch.setattr(
        capture_c, "run", lambda a: (_ for _ in ()).throw(RuntimeError("secret"))
    )
    monkeypatch.setattr(policy, "bounds", lambda *a: {})
    assert capture_c.main(["--batch", "0"]) == 2
    assert capsys.readouterr().out.strip() == "WO-6 refused: internal_error"


def test_wo6c_quarantine_write_ahead_and_empty_dirs(tmp_path, monkeypatch):
    from mve.observer import quarantine_c, storage

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    old = "a" * 64
    for n in range(4):
        attempt = base / "native" / str(n)
        attempt.mkdir(parents=True)
        (attempt / "receipt.json").write_text(json.dumps({"plan_sha256": old}))
        (attempt / "browser.log").write_text("bounded diagnostic")
    ids = [j["snapshot_id"] for j in capture_c.plan()["jobs"]]
    for ident in ids:
        folder = base / "snapshots" / ident
        folder.mkdir(parents=True)
        if ident not in ids[-4:]:
            (folder / "data.json").write_text("{}")
    args = SimpleNamespace(
        name="old-plan", plan_sha256=old, reason="superseded runtime"
    )
    result = quarantine_c.run(args)
    assert result["moves"] == 20
    assert not list((base / "native").iterdir())
    assert not list((base / "snapshots").iterdir())
    assert len(quarantine_c.admission(base)) == 1
    q = base / "quarantine/old-plan"
    record = json.loads((q / "QUARANTINE.json").read_text())
    assert len([m for m in record["moves"] if not m["inventory"]["files"]]) == 4
    with pytest.raises(ValueError):
        quarantine_c.run(args)
    (q / "native/3/browser.log").write_text("tamper")
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


def test_traceback_is_bounded_private_and_no_exception_text(tmp_path):
    try:
        raise RuntimeError("secret-value")
    except RuntimeError as exc:
        policy.write_traceback(tmp_path, exc)
    path = tmp_path / "traceback.txt"
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.stat().st_size <= 65536
    assert b"secret-value" not in path.read_bytes()


def test_smoke_record_immutable_hashed_and_no_native_launch(tmp_path, monkeypatch):
    import hashlib
    import shutil
    import sys

    source_chrome = synthetic_bundle(tmp_path / "source")
    source = source_chrome.parents[2]
    target = tmp_path / "target" / source.name
    shutil.copytree(source, target, symlinks=True)
    chrome = target / "Contents/MacOS/Google Chrome"
    chrome.write_bytes(b"edited launcher")
    plist = target / "Contents/Info.plist"
    data = plistlib.loads(plist.read_bytes())
    data["CFBundleVersion"] = "8010.54"
    plist.write_bytes(plistlib.dumps(data))

    def command(args, **kwargs):
        if args[0] == "codesign":
            return SimpleNamespace(returncode=0, stdout="", stderr="valid")
        return SimpleNamespace(stdout="Google Chrome 153.0.8010.54\n")

    monkeypatch.setattr(renderer_pin.subprocess, "run", command)

    class Browser:
        version = "153.0.8010.54"

    class Context:
        browser = Browser()

        def close(self):
            pass

    class Chromium:
        def launch_persistent_context(self, *a, **kw):
            return Context()

    class Playwright:
        chromium = Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setitem(
        sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=Playwright)
    )
    output = tmp_path / "smoke.json"
    digest = renderer_pin.smoke(source, chrome, output)
    record = json.loads(output.read_text())
    assert record["sha256"] == digest
    assert (
        digest
        == hashlib.sha256(
            json.dumps(
                {k: v for k, v in record.items() if k != "sha256"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert record["source_copy"]["basename"] == source.name
    assert record["info_plist_edits"]["CFBundleVersion"]["after"] == "8010.54"
    assert record["codesign_verify_succeeded"] and record["launch_succeeded"]
    assert record["browser_context_version"] == "153.0.8010.54"
    with pytest.raises(FileExistsError):
        renderer_pin.smoke(source, chrome, output)

    class BrokenChromium:
        def launch_persistent_context(self, *a, **kw):
            raise RuntimeError("private launch detail")

    Playwright.chromium = BrokenChromium()

    def failed_command(args, **kwargs):
        if args[0] == "codesign":
            return SimpleNamespace(returncode=1, stdout="", stderr="invalid signature")
        raise OSError("native version probe failed")

    monkeypatch.setattr(renderer_pin.subprocess, "run", failed_command)
    failed_path = tmp_path / "failed-smoke.json"
    renderer_pin.smoke(source, chrome, failed_path)
    failed = json.loads(failed_path.read_text())
    assert failed["launch_succeeded"] is False
    assert failed["browser_context_version"] is None
    assert failed["codesign_verify_succeeded"] is False
    assert failed["native_version_output"] is None
    assert "private launch detail" not in failed_path.read_text()


def test_worker_timeout_label_relay_and_private_record(tmp_path):
    exc = policy.PageTimeoutError("secret message")
    policy.write_worker_refusal(tmp_path, exc)
    assert (tmp_path / "worker_refusal.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(policy.PageTimeoutError) as raised:
        policy.relay_worker_refusal(tmp_path, ValueError("child exited"))
    assert raised.value.label == "page_timeout"


def quarantine_fixture(tmp_path, monkeypatch):
    from mve.observer import quarantine_c, storage

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    (base / "native/0").mkdir(parents=True)
    (base / "native/0/receipt.json").write_text(json.dumps({"plan_sha256": "a" * 64}))
    ident = capture_c.plan()["jobs"][0]["snapshot_id"]
    (base / "snapshots" / ident).mkdir(parents=True)
    args = SimpleNamespace(name="old", plan_sha256="a" * 64, reason="old runtime")
    quarantine_c.run(args)
    return base, args


@pytest.mark.parametrize(
    "fault",
    [
        "hash",
        "schema",
        "plan",
        "extra",
        "duplicate",
        "path",
        "active",
        "artifact",
        "root_extra",
        "folder_name",
        "symlink",
    ],
)
def test_quarantine_admission_rejects_tampering(tmp_path, monkeypatch, fault):
    from mve.observer import quarantine_c, snapshot_inventory as inv

    base, _ = quarantine_fixture(tmp_path, monkeypatch)
    q = base / "quarantine/old"
    path = q / "QUARANTINE.json"
    record = json.loads(path.read_text())
    if fault == "hash":
        record["reason"] = "edited"
    elif fault == "schema":
        record["schema"] = "wrong"
    elif fault == "plan":
        record["superseded_plan_sha256"] = "short"
    elif fault == "duplicate":
        record["moves"].append(record["moves"][0])
    elif fault == "path":
        record["moves"][0]["dest"] = "other"
    elif fault == "folder_name":
        record["name"] = "different"
    elif fault == "extra":
        (q / "snapshots/extra").mkdir()
    elif fault == "active":
        (base / "native/0").mkdir()
    elif fault == "artifact":
        (q / "native/0/receipt.json").write_text("drift")
    elif fault == "root_extra":
        (q / "extra").write_text("extra")
    elif fault == "symlink":
        (q / "native/0/link").symlink_to("receipt.json")
    if fault in {"schema", "plan", "duplicate", "path", "folder_name"}:
        path.write_text(json.dumps(inv.seal(record)))
    elif fault == "hash":
        path.write_text(json.dumps(record))
    with pytest.raises((ValueError, OSError)):
        quarantine_c.admission(base)


@pytest.mark.parametrize(
    "fault",
    [
        "invalid_hash",
        "no_attempt",
        "unexpected_attempt",
        "unexpected_snapshot",
        "wrong_plan",
    ],
)
def test_quarantine_writer_refuses_invalid_sources(tmp_path, monkeypatch, fault):
    from mve.observer import quarantine_c, storage

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    args = SimpleNamespace(name="old", plan_sha256="a" * 64, reason="old runtime")
    if fault != "no_attempt":
        (base / "native/0").mkdir(parents=True)
        (base / "native/0/receipt.json").write_text(
            json.dumps({"plan_sha256": "a" * 64})
        )
    if fault == "invalid_hash":
        args.plan_sha256 = "bad"
    elif fault == "unexpected_attempt":
        (base / "native/4").mkdir()
    elif fault == "unexpected_snapshot":
        (base / "snapshots/unknown").mkdir(parents=True)
    elif fault == "wrong_plan":
        (base / "native/0/receipt.json").write_text(
            json.dumps({"plan_sha256": "b" * 64})
        )
    with pytest.raises((ValueError, OSError)):
        quarantine_c.run(args)


def test_current_wo6c_plan_cannot_be_quarantined(tmp_path, monkeypatch):
    from mve.observer import quarantine_c, storage

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    (base / "native/0").mkdir(parents=True)
    args = SimpleNamespace(
        name="bad", plan_sha256=capture_c.plan()["sha256"], reason="incorrect"
    )
    with pytest.raises(ValueError, match="current plan"):
        quarantine_c.run(args)


def test_renderer_candidate_cli_and_guards(tmp_path, monkeypatch, capsys):
    chrome = synthetic_bundle(tmp_path)
    assert renderer_pin.main(["--candidate", str(chrome)]) == 0
    assert json.loads(capsys.readouterr().out)["browser_version"] == "153.0.8010.54"
    with pytest.raises(SystemExit):
        renderer_pin.main(["--smoke", str(tmp_path)])
    with pytest.raises(policy.RendererPinError):
        renderer_pin.candidate(tmp_path / "wrong")
    (
        chrome.parent.parent
        / "Frameworks/Google Chrome Framework.framework/Versions/153.0.8010.54"
    ).rename(
        chrome.parent.parent
        / "Frameworks/Google Chrome Framework.framework/Versions/moved"
    )
    with pytest.raises(policy.RendererPinError):
        renderer_pin.candidate(chrome)


def test_worker_refusal_labels_and_duplicate_traceback(tmp_path):
    for label, cls in [
        ("renderer_pin", policy.RendererPinError),
        ("renderer_version", policy.RendererVersionError),
        ("internal_error", ValueError),
    ]:
        (tmp_path / "worker_refusal.json").write_text(json.dumps({"label": label}))
        with pytest.raises(cls):
            policy.relay_worker_refusal(tmp_path, ValueError("child failed"))
    try:
        raise ValueError("private")
    except ValueError as exc:
        policy.write_traceback(tmp_path, exc)
        policy.write_traceback(tmp_path, exc)


def test_wo1b_bundle_change_at_batch_end_never_accepts(tmp_path, monkeypatch):
    from mve.observer import snapshot_batch as batch, snapshot_inventory as inv
    from tests.mve.observer.test_snapshot_batch import fake_batch_env

    fake_batch_env.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(renderer_pin, "preflight", lambda *a: "153.fixture")
    calls = 0

    def verify(*a):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise policy.RendererPinError("bytes changed")
        return "153.fixture"

    monkeypatch.setattr(renderer_pin, "verify", verify)
    args = batch.parse_args(
        [
            "--plan",
            str(inv.ROOT / inv.PLAN),
            "--batch",
            "0",
            "--renderer-pin",
            "chrome-153",
        ]
    )
    with pytest.raises(policy.RendererPinError):
        batch.run(args)
    receipt = json.loads(next(tmp_path.rglob("receipt.json")).read_text())
    assert receipt["status"] == "renderer_pin"
    assert not list(tmp_path.rglob("complete.json"))


def test_wo6c_bundle_change_at_batch_end_never_accepts(tmp_path, monkeypatch):
    from tests.mve.observer.test_wo6c import sandbox, capture_env

    sandbox.__wrapped__(tmp_path, monkeypatch)
    args = capture_env.__wrapped__(tmp_path, monkeypatch)
    args.prepare_only = False
    args.renderer_pin = "chrome-153"
    monkeypatch.setattr(renderer_pin, "preflight", lambda *a: "153.fixture")
    calls = 0

    def verify(*a):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise policy.RendererPinError("bytes changed")
        return "153.fixture"

    monkeypatch.setattr(renderer_pin, "verify", verify)
    with pytest.raises(policy.RendererPinError):
        capture_c.run(args)
    receipt = json.loads(next(tmp_path.rglob("receipt.json")).read_text())
    assert receipt["status"] == "renderer_pin"
    assert not list(tmp_path.rglob("complete.json"))


def test_quarantine_cli_and_inventory_edges(tmp_path, monkeypatch, capsys):
    from mve.observer import quarantine_c, storage

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    (base / "native/0/nested").mkdir(parents=True)
    (base / "native/0/nested/file").write_bytes(b"x")
    (base / "native/0/receipt.json").write_text(json.dumps({"plan_sha256": "a" * 64}))
    assert (
        quarantine_c.main(["--name", "old", "--plan-sha256", "bad", "--reason", "old"])
        == 2
    )
    assert "refused" in capsys.readouterr().out
    assert (
        quarantine_c.main(
            ["--name", "old", "--plan-sha256", "a" * 64, "--reason", "old"]
        )
        == 0
    )
    assert '"moves": 1' in capsys.readouterr().out
    record = json.loads((base / "quarantine/old/QUARANTINE.json").read_text())
    assert record["moves"][0]["inventory"]["directories"] == ["nested"]
    assert (
        quarantine_c.main(
            ["--name", "old", "--plan-sha256", "a" * 64, "--reason", "old"]
        )
        == 2
    )
    with pytest.raises(ValueError):
        quarantine_c.inventory(tmp_path / "absent")
    (base / "quarantine/invalid").write_text("not a directory")
    with pytest.raises(ValueError):
        quarantine_c.admission(base)
    (base / "quarantine/invalid").unlink()
    (base / "quarantine/link").symlink_to("old")
    with pytest.raises(ValueError):
        quarantine_c.admission(base)
