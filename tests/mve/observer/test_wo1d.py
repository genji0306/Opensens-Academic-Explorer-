"""WO-1d offline regressions; no native browser or network."""

import json
import os
import plistlib
from types import SimpleNamespace

import pytest

from mve.observer import capture_policy as policy, capture_c, renderer_pin
from mve.observer import snapshot_render as render

OLD_IDS = (
    "93376ce123f8426439c1b3e6",
    "0bb9e1f84029cea57041d4cd",
    "65e365d1ac2f5c474cc05a1e",
    "ca9e1b12e3a7ba6cdfeec931",
    "c8bf43bc1bdb578db09f5365",
    "b1c2807deb8641dca0fea2a3",
    "214acada2b09237754145c42",
    "03b77b35aff9820b12dd7271",
    "d27c9f581d94d3525f242a72",
    "d6612f609a3a66362b57db25",
    "458301fd43f9448d5d89bb3c",
    "d8ca2378b89b644d037289be",
    "a5e81925bca7373df6762649",
    "f0dc286c666c0f33c1b4eb8e",
    "ce2391138dbdb78a0d52298f",
    "7337e2000bb8fea0bc1a5a77",
)


def old_quarantine_sources(tmp_path, monkeypatch):
    from mve.observer import snapshot_inventory as inv, storage

    monkeypatch.setattr(storage, "WORKTREE", tmp_path)
    base = tmp_path / capture_c.BASE
    old_plan = inv.seal(
        dict(
            schema="mve-wo6c-capture-v1",
            jobs=[dict(snapshot_id=ident) for ident in OLD_IDS],
        )
    )
    for n in range(4):
        attempt = base / "native" / str(n)
        attempt.mkdir(parents=True)
        (attempt / "plan.json").write_text(json.dumps(old_plan))
        (attempt / "receipt.json").write_text(
            json.dumps({"plan_sha256": old_plan["sha256"]})
        )
        (attempt / "browser.log").write_text("bounded diagnostic")
    for ident in OLD_IDS:
        folder = base / "snapshots" / ident
        folder.mkdir(parents=True)
        if ident not in OLD_IDS[-4:]:
            (folder / "data.json").write_text("{}")
    args = SimpleNamespace(
        name="old-plan", plan_sha256=old_plan["sha256"], reason="superseded runtime"
    )
    return base, args


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


def test_null_lock_fields_refuse_preflight(tmp_path, monkeypatch):
    chrome = synthetic_bundle(tmp_path)
    candidate = renderer_pin.candidate(chrome)
    for key in ("launcher_sha256", "info_plist_sha256", "bundle_symlinks"):
        candidate[key] = None
    monkeypatch.setattr(renderer_pin, "record", lambda _: candidate)
    with pytest.raises(policy.RendererPinError) as exc:
        renderer_pin.preflight(chrome, "chrome-153")
    assert exc.value.label == "renderer_pin"


def test_unlabeled_exception_is_internal_error(monkeypatch, capsys):
    monkeypatch.setattr(
        capture_c, "run", lambda a: (_ for _ in ()).throw(RuntimeError("secret"))
    )
    monkeypatch.setattr(policy, "bounds", lambda *a: {})
    assert capture_c.main(["--batch", "0"]) == 2
    assert capsys.readouterr().out.strip() == "WO-6 refused: internal_error"


def test_wo6c_quarantine_write_ahead_and_empty_dirs(tmp_path, monkeypatch):
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
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


@pytest.mark.parametrize("missing", ["native/3", "snapshots/7337e2000bb8fea0bc1a5a77"])
def test_quarantine_writer_requires_complete_source_set(tmp_path, monkeypatch, missing):
    import shutil
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    shutil.rmtree(base / missing)
    with pytest.raises(ValueError, match="complete|missing"):
        quarantine_c.run(args)
    assert not (base / "quarantine").exists()


def test_quarantine_writer_rejects_extra_snapshot(tmp_path, monkeypatch):
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    (base / "snapshots/extra").mkdir()
    with pytest.raises(ValueError, match="snapshot"):
        quarantine_c.run(args)
    assert not (base / "quarantine").exists()


@pytest.mark.parametrize("fault", ["symlink_attempt", "short_plan", "bad_identity"])
def test_quarantine_rejects_invalid_old_plan_inventory(tmp_path, monkeypatch, fault):
    import shutil
    from mve.observer import quarantine_c, snapshot_inventory as inv

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    attempt = base / "native/0"
    if fault == "symlink_attempt":
        shutil.rmtree(attempt)
        attempt.symlink_to("1")
    else:
        plan = json.loads((attempt / "plan.json").read_text())
        if fault == "short_plan":
            plan["jobs"].pop()
        else:
            plan["jobs"][0]["snapshot_id"] = "invalid"
        plan = inv.seal(plan)
        (attempt / "plan.json").write_text(json.dumps(plan))
        (attempt / "receipt.json").write_text(
            json.dumps({"plan_sha256": plan["sha256"]})
        )
        args.plan_sha256 = plan["sha256"]
    with pytest.raises(ValueError):
        quarantine_c.expected_snapshots(base / "native", args.plan_sha256)


def test_quarantine_admission_rejects_partial_record_and_half_move(
    tmp_path, monkeypatch
):
    import shutil
    from mve.observer import quarantine_c, snapshot_inventory as inv

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    q = base / "quarantine/old-plan"
    path = q / "QUARANTINE.json"
    record = json.loads(path.read_text())
    complete = list(record["moves"])
    record["moves"] = [
        m
        for m in record["moves"]
        if m["source"] != "snapshots/7337e2000bb8fea0bc1a5a77"
    ]
    path.write_text(json.dumps(inv.seal(record)))
    (q / "snapshots/7337e2000bb8fea0bc1a5a77").rmdir()
    with pytest.raises(ValueError, match="complete|missing"):
        quarantine_c.admission(base)
    record["moves"] = complete
    path.write_text(json.dumps(inv.seal(record)))
    (q / "snapshots/7337e2000bb8fea0bc1a5a77").mkdir()
    shutil.move(q / "native/3", base / "native/3")
    with pytest.raises(ValueError):
        quarantine_c.admission(base)


def test_quarantine_admission_allows_new_plan_recapture(tmp_path, monkeypatch):
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    quarantine_c.run(args)
    new_plan = capture_c.plan()
    (base / "native/0").mkdir()
    (base / "native/0/plan.json").write_text(json.dumps(new_plan))
    (base / "native/0/receipt.json").write_text(
        json.dumps({"plan_sha256": new_plan["sha256"]})
    )
    (base / "snapshots" / OLD_IDS[0]).mkdir()
    (base / "snapshots" / OLD_IDS[0] / "complete.json").write_text(
        json.dumps({"plan_sha256": new_plan["sha256"]})
    )
    assert quarantine_c.admission(base)[0]["moves"] == 20


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
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
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
    q = base / "quarantine/old-plan"
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
    import shutil
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    if fault == "invalid_hash":
        args.plan_sha256 = "bad"
    elif fault == "no_attempt":
        shutil.rmtree(base / "native")
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


@pytest.mark.parametrize("entry", ["wo6c", "wo1b"])
@pytest.mark.parametrize("pin_changed", [True, False])
def test_batch_end_pin_precedes_earlier_capture_error(
    tmp_path, monkeypatch, capsys, entry, pin_changed
):
    from mve.observer import snapshot_batch as batch, snapshot_inventory as inv

    if entry == "wo6c":
        from tests.mve.observer.test_wo6c import sandbox, capture_env

        sandbox.__wrapped__(tmp_path, monkeypatch)
        capture_env.__wrapped__(tmp_path, monkeypatch)

        def command():
            return capture_c.main(
                [
                    "--batch",
                    "0",
                    "--renderer-pin",
                    "chrome-153",
                    "--chrome",
                    "unused",
                    "--atlas",
                    "atlas",
                    "--lab",
                    "lab",
                ]
            )

        public = "WO-6 refused: "
    else:
        from tests.mve.observer.test_snapshot_batch import fake_batch_env

        fake_batch_env.__wrapped__(tmp_path, monkeypatch)

        def command():
            return batch.main(
                [
                    "--plan",
                    str(inv.ROOT / inv.PLAN),
                    "--batch",
                    "0",
                    "--renderer-pin",
                    "chrome-153",
                ]
            )

        public = "WO-1b refused: "
    monkeypatch.setattr(renderer_pin, "preflight", lambda *a: "153.fixture")
    if pin_changed:
        monkeypatch.setattr(
            renderer_pin,
            "verify",
            lambda *a: (_ for _ in ()).throw(policy.RendererPinError("changed")),
        )
    else:
        monkeypatch.setattr(renderer_pin, "verify", lambda *a: "153.fixture")
    monkeypatch.setattr(
        batch.old,
        "isolated_capture",
        lambda *a: (_ for _ in ()).throw(policy.PageTimeoutError("earlier")),
    )
    assert command() == 2
    assert capsys.readouterr().out.strip() == public + (
        "renderer_pin" if pin_changed else "page_timeout"
    )
    receipt = json.loads(next(tmp_path.rglob("receipt.json")).read_text())
    assert receipt["status"] == ("renderer_pin" if pin_changed else "failed")
    assert receipt["failure_type"] == "PageTimeoutError"
    assert receipt["failure_label"] == "page_timeout"
    assert not list(tmp_path.rglob("complete.json"))


@pytest.mark.parametrize("entry", ["wo6c", "wo1b"])
@pytest.mark.parametrize(
    "pin_changed,audit_failed,capture_failed,expected_label",
    [
        (True, True, False, "renderer_pin"),
        (True, True, True, "renderer_pin"),
        (False, True, False, "internal_error"),
        (False, False, False, None),
    ],
)
def test_batch_end_pin_precedes_source_audit_and_clean_batch(
    tmp_path,
    monkeypatch,
    capsys,
    entry,
    pin_changed,
    audit_failed,
    capture_failed,
    expected_label,
):
    from mve.observer import snapshot_batch as batch, snapshot_inventory as inv
    from mve.observer import snapshots as s

    if entry == "wo6c":
        from tests.mve.observer.test_wo6c import sandbox, capture_env

        sandbox.__wrapped__(tmp_path, monkeypatch)
        capture_env.__wrapped__(tmp_path, monkeypatch)

        def command():
            return capture_c.main(
                [
                    "--batch",
                    "0",
                    "--renderer-pin",
                    "chrome-153",
                    "--chrome",
                    "unused",
                    "--atlas",
                    "atlas",
                    "--lab",
                    "lab",
                ]
            )

        public = "WO-6 refused: "
    else:
        from tests.mve.observer.test_snapshot_batch import fake_batch_env

        fake_batch_env.__wrapped__(tmp_path, monkeypatch)

        def command():
            return batch.main(
                [
                    "--plan",
                    str(inv.ROOT / inv.PLAN),
                    "--batch",
                    "0",
                    "--renderer-pin",
                    "chrome-153",
                ]
            )

        public = "WO-1b refused: "

    monkeypatch.setattr(renderer_pin, "preflight", lambda *a: "153.fixture")
    if pin_changed:
        monkeypatch.setattr(
            renderer_pin,
            "verify",
            lambda *a: (_ for _ in ()).throw(policy.RendererPinError("changed")),
        )
    else:
        monkeypatch.setattr(renderer_pin, "verify", lambda *a: "153.fixture")
    if capture_failed:
        monkeypatch.setattr(
            batch.old,
            "isolated_capture",
            lambda *a: (_ for _ in ()).throw(policy.PageTimeoutError("earlier")),
        )
    audit_calls = 0

    def isolation_state(repos):
        nonlocal audit_calls
        audit_calls += 1
        return {"fixture": "changed" if audit_failed and audit_calls > 1 else "same"}

    monkeypatch.setattr(s, "isolation_state", isolation_state)
    assert command() == (2 if expected_label else 0)
    output = capsys.readouterr().out.strip()
    if expected_label:
        assert output == public + expected_label
    receipt = json.loads(next(tmp_path.rglob("receipt.json")).read_text())
    assert receipt["status"] == ("renderer_pin" if pin_changed else "captured")
    assert receipt["source_repos_unchanged"] is (not audit_failed)
    if audit_failed:
        assert receipt["audit_failure_type"] == "ValueError"
        assert receipt["audit_failure_label"] == "internal_error"
        assert not list(tmp_path.rglob("complete.json"))
    else:
        assert "audit_failure_type" not in receipt
        assert list(tmp_path.rglob("complete.json"))
    if capture_failed:
        assert receipt["failure_type"] == "PageTimeoutError"
        assert receipt["failure_label"] == "page_timeout"


def test_quarantine_cli_and_inventory_edges(tmp_path, monkeypatch, capsys):
    from mve.observer import quarantine_c

    base, args = old_quarantine_sources(tmp_path, monkeypatch)
    (base / "native/0/nested").mkdir()
    (base / "native/0/nested/file").write_bytes(b"x")
    assert (
        quarantine_c.main(["--name", "old", "--plan-sha256", "bad", "--reason", "old"])
        == 2
    )
    assert "refused" in capsys.readouterr().out
    assert (
        quarantine_c.main(
            ["--name", args.name, "--plan-sha256", args.plan_sha256, "--reason", "old"]
        )
        == 0
    )
    assert '"moves": 20' in capsys.readouterr().out
    record = json.loads((base / "quarantine/old-plan/QUARANTINE.json").read_text())
    assert record["moves"][0]["inventory"]["directories"] == ["nested"]
    assert (
        quarantine_c.main(
            ["--name", args.name, "--plan-sha256", args.plan_sha256, "--reason", "old"]
        )
        == 2
    )
    with pytest.raises(ValueError):
        quarantine_c.inventory(tmp_path / "absent")
    (base / "quarantine/invalid").write_text("not a directory")
    with pytest.raises(ValueError):
        quarantine_c.admission(base)
    (base / "quarantine/invalid").unlink()
    (base / "quarantine/link").symlink_to("old-plan")
    with pytest.raises(ValueError):
        quarantine_c.admission(base)
