"""WO-1c offline tests: native launch is mocked; owner evidence is read-only."""

import hashlib
import json
import plistlib
from types import SimpleNamespace

import pytest
from mve.observer import capture_policy as policy, capture_evidence as evidence
from mve.observer import snapshot_batch as batch, snapshot_inventory as inv
from tests.mve.observer.test_snapshot_batch import fake_batch_env as _fake_batch_env


@pytest.fixture
def fake_batch_env(tmp_path, monkeypatch):
    return _fake_batch_env.__wrapped__(tmp_path, monkeypatch)


VERSION = "153.0.8010.54"


def bundle(tmp_path):
    contents = tmp_path / "Chrome.app/Contents"
    tree = contents / f"Frameworks/Google Chrome Framework.framework/Versions/{VERSION}"
    tree.mkdir(parents=True)
    (tree / "a").write_bytes(b"alpha")
    (tree / "z").write_bytes(b"omega")
    (tree.parent / "Current").symlink_to(VERSION)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": VERSION})
    )
    chrome = contents / "MacOS/Google Chrome"
    chrome.parent.mkdir()
    chrome.write_bytes(b"launcher")
    from mve.observer import renderer_pin

    pin = renderer_pin.candidate(chrome)
    return contents / "MacOS/Google Chrome", tree, pin


def test_pinned_preflight_and_hash(tmp_path, monkeypatch):
    from mve.observer import renderer_pin as pin

    chrome, tree, record = bundle(tmp_path)
    assert pin.framework_hash(tree) == record["framework_tree_sha256"]
    monkeypatch.setattr(pin, "record", lambda _: record)
    calls = []

    def probe(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(stdout=f"Google Chrome {VERSION}\n")

    monkeypatch.setattr(pin.subprocess, "run", probe)
    assert pin.preflight(chrome, "chrome-153") == VERSION
    assert calls[0][0] == [str(chrome), "--version"]
    assert calls[0][1]["timeout"] == 30
    (tree / "a").write_bytes(b"drift")
    with pytest.raises(policy.RendererVersionError):
        pin.preflight(chrome, "chrome-153")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "fault", ["reported", "plist", "missing", "current", "launch", "pin"]
)
def test_pinned_preflight_refuses(tmp_path, monkeypatch, fault):
    from mve.observer import renderer_pin as pin

    chrome, tree, record = bundle(tmp_path)
    monkeypatch.setattr(pin, "record", lambda _: record)

    def probe(*a, **k):
        if fault == "launch":
            raise OSError("launch failed")
        return SimpleNamespace(
            stdout="Google Chrome 154.0.8037.58\n"
            if fault == "reported"
            else f"Google Chrome {VERSION}\n"
        )

    monkeypatch.setattr(pin.subprocess, "run", probe)
    if fault == "plist":
        (chrome.parent.parent / "Info.plist").write_bytes(
            plistlib.dumps({"CFBundleShortVersionString": "154"})
        )
    elif fault == "missing":
        (tree / "a").unlink()
    elif fault == "current":
        (tree.parent / "Current").unlink()
        (tree.parent / "Current").symlink_to("154")
    elif fault == "pin":
        record.clear()
    with pytest.raises(policy.RendererVersionError) as exc:
        pin.preflight(chrome, "chrome-153")
    assert exc.value.label == "renderer_pin"


@pytest.mark.parametrize("entry", ["wo1b", "wo6c", "admission"])
def test_public_version_label_prewrite(fake_batch_env, monkeypatch, capsys, entry):
    from mve.observer import capture_c, renderer_pin

    def refused(*a, **kw):
        policy.one_version(["153", "154"])

    monkeypatch.setattr(renderer_pin, "preflight", refused)
    if entry == "wo1b":
        result = batch.main(
            [
                "--plan",
                str(inv.ROOT / inv.PLAN),
                "--batch",
                "7",
                "--renderer-pin",
                "chrome-153",
            ]
        )
    elif entry == "wo6c":
        monkeypatch.setattr(capture_c, "ROOT", fake_batch_env)
        result = capture_c.main(["--batch", "3", "--renderer-pin", "chrome-153"])
    else:
        monkeypatch.setattr(evidence, "resume_state", refused)
        result = evidence.main(
            ["--base", str(fake_batch_env), "--plan", str(inv.ROOT / inv.PLAN)]
        )
    assert result == 2
    assert "renderer_version" in capsys.readouterr().out
    assert not (fake_batch_env / "mve").exists()


def test_partial_quarantine_synthetic_copy(fake_batch_env):
    import shutil
    from mve.observer import quarantine_partial as partial

    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "6"]
    assert batch.main(args) == 0
    base = next(fake_batch_env.glob("mve/generated/wo1b-*"))
    copy = base.parent / "synthetic-copy"
    shutil.copytree(base, copy)
    before = batch.s.tree_listing(base)
    plan = inv.load()
    chosen = [
        j["snapshot_id"]
        for j in batch.select_jobs(plan, 6)
        if j["block"]["cluster"] == "spectral-contrast-2"
    ]
    assert len(chosen) == 4
    command = [
        "--base",
        str(copy.relative_to(fake_batch_env)),
        "--plan",
        str(inv.ROOT / inv.PLAN),
        "--name",
        "partial-spectral-contrast-2",
        "--cluster",
        "spectral-contrast-2",
        "--attempt",
        "batch-006-000",
        "--reason",
        "renderer unavailable",
        "--snapshots",
        *chosen,
    ]
    assert partial.main(command) == 0
    state = evidence.resume_state(copy, plan)
    assert len(state["completed"]) == 6
    assert set(state["quarantine"][0]["snapshot_ids"]) == set(chosen)
    q = copy / "quarantine/partial-spectral-contrast-2"
    record = json.loads((q / "QUARANTINE.json").read_text())
    assert record["schema"] == "mve-wo1b-partial-quarantine-v1"
    for ident in chosen:
        assert batch.completed(
            q / ident,
            plan,
            next(j for j in inv.jobs(plan) if j["snapshot_id"] == ident),
        )
    assert evidence.main(["--base", str(copy), "--plan", str(inv.ROOT / inv.PLAN)]) == 0
    assert partial.main(command) == 2
    assert batch.s.tree_listing(base) == before
    (q / chosen[0] / "data.json").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        evidence.resume_state(copy, plan)


def test_report_renderer_covariate(tmp_path):
    from mve.observer.design import allocate
    from mve.observer.metrics import report
    from tests.mve.observer.wo45_helpers import fixture

    manifest, config = fixture(tmp_path)
    for e in manifest["snapshots"]:
        e["renderer_versions"]["chrome"] = VERSION
    plan = allocate(manifest, tmp_path, config)
    rows = [
        dict(job=j["id"], slot=i, card=None, checkable=False)
        for j in plan.to_dict()["jobs"]
        for i in range(3)
    ]
    result = report(plan, rows, "model:O-DS")["GO2"]
    assert all(c["renderer_version"] == VERSION for c in result["cluster_outcomes"])
    assert "confounded with capture order" in result["renderer_caveat"]
    assert "cannot establish renderer invariance" in result["renderer_caveat"]


def test_hash_spaces_symlinks_and_invalid_names(tmp_path):
    from mve.observer.renderer_pin import framework_hash

    with pytest.raises(policy.RendererVersionError):
        framework_hash(tmp_path)
    (tmp_path / "a file").write_bytes(b"bytes")
    expected = hashlib.sha256(
        (hashlib.sha256(b"bytes").hexdigest() + "  ./a file\n").encode()
    ).hexdigest()
    assert framework_hash(tmp_path) == expected
    (tmp_path / "link").symlink_to("a file")
    assert framework_hash(tmp_path) == expected
    (tmp_path / "bad\nname").write_bytes(b"bad")
    with pytest.raises(policy.RendererVersionError):
        framework_hash(tmp_path)


def test_record_and_invalid_pin_version(tmp_path, monkeypatch):
    from mve.observer import renderer_pin as pin

    assert pin.record("chrome-153")["browser_version"] == VERSION
    with pytest.raises(KeyError):
        pin.record("unknown")
    chrome, tree, record = bundle(tmp_path)
    record["browser_version"] = "../escape"
    monkeypatch.setattr(pin, "record", lambda _: record)
    with pytest.raises(policy.RendererVersionError):
        pin.preflight(chrome, "bad")


def test_quarantine_validation_faults(fake_batch_env):
    from copy import deepcopy
    from mve.observer import quarantine_partial as partial

    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "6"]) == 0
    base = next(fake_batch_env.glob("mve/generated/wo1b-*"))
    plan = inv.load()
    job = next(
        j
        for j in batch.select_jobs(plan, 6)
        if j["block"]["cluster"] == "spectral-contrast-2"
    )
    ident = job["snapshot_id"]
    source = base / "snapshots" / ident
    files = {p.name: batch.s.sha256(p) for p in source.iterdir()}
    record = dict(
        schema=partial.SCHEMA,
        plan_sha256=plan["sha256"],
        name="test",
        reason="version",
        attempt="batch-006-000",
        attempt_receipt_sha256=batch.s.sha256(base / "batch-006-000/receipt.json"),
        attempt_capture_sha256=batch.s.sha256(base / "batch-006-000/capture.json"),
        cluster="spectral-contrast-2",
        snapshots={ident: files},
    )
    jobs, audit = partial.validate(base, plan, record)
    for key, value in [
        ("schema", "bad"),
        ("plan_sha256", "bad"),
        ("name", ".."),
        ("reason", ""),
        ("reason", None),
        ("cluster", "wrong"),
        ("attempt_receipt_sha256", "bad"),
        ("attempt_capture_sha256", "bad"),
        ("snapshots", {}),
    ]:
        bad = deepcopy(record)
        bad[key] = value
        with pytest.raises(ValueError):
            partial.validate(base, plan, bad)
    with pytest.raises(ValueError):
        partial.read(base, source, plan, record)
    with pytest.raises(ValueError):
        partial.verify_snapshot(source, plan, job, {}, audit)
    with pytest.raises(ValueError):
        partial.verify_snapshot(source, plan, job, {**files, "data.json": "bad"}, audit)
    with pytest.raises(ValueError):
        partial.verify_snapshot(
            source, plan, job, files, {**audit, "source_audit_before_sha256": "bad"}
        )
    bad_audit = deepcopy(audit)
    bad_audit["candidates"][ident]["seconds"] += 1
    with pytest.raises(ValueError, match="candidate"):
        partial.verify_snapshot(source, plan, job, files, bad_audit)
    args = [
        "--base",
        str(base.relative_to(fake_batch_env)),
        "--plan",
        str(inv.ROOT / inv.PLAN),
        "--name",
        "bad",
        "--cluster",
        "spectral-contrast-2",
        "--attempt",
        "batch-006-000",
        "--reason",
        "version",
        "--snapshots",
        ident,
        ident,
    ]
    assert partial.main(args) == 2
    assert not (base / "quarantine").exists()
    assert partial.main(args[:-1] + ["../escape"]) == 2


def test_selection_changed_after_preflight_refuses(fake_batch_env, monkeypatch, capsys):
    jobs = batch.select_jobs(inv.load(), 0)
    states = iter(
        [
            dict(remaining=[], cluster_versions={}),
            dict(remaining=jobs, cluster_versions={}),
        ]
    )
    monkeypatch.setattr(batch, "resume_state", lambda *a: next(states))
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]) == 2
    assert "renderer_version" in capsys.readouterr().out
    assert not list(fake_batch_env.rglob("batch-000-*"))


def test_report_rejects_mixed_and_partial_versions(tmp_path):
    from mve.observer.design import allocate, Design
    from mve.observer.card import digest
    from mve.observer.metrics import report
    from tests.mve.observer.wo45_helpers import fixture

    manifest, config = fixture(tmp_path)
    plan = allocate(manifest, tmp_path, config).to_dict()
    rows = [
        dict(job=j["id"], slot=i, card=None, checkable=False)
        for j in plan["jobs"]
        for i in range(3)
    ]
    for e in plan["manifest"]["snapshots"]:
        e["renderer_versions"]["chrome"] = VERSION
    # Null twins belong to the covariate too.
    twin = next(
        e for e in plan["manifest"]["snapshots"] if e["control"]["kind"] == "null_twin"
    )
    for bad in ["154", None]:
        twin["renderer_versions"]["chrome"] = bad
        plan["sha256"] = digest({k: v for k, v in plan.items() if k != "sha256"})
        with pytest.raises(policy.RendererVersionError):
            report(Design.from_dict(plan), rows, "model:O-DS")


def test_pinned_batch_forwards_pin_and_records_it(fake_batch_env, monkeypatch):
    from mve.observer import renderer_pin

    seen = []

    def checked(chrome, name):
        seen.append(name)
        return "153.fixture"

    monkeypatch.setattr(renderer_pin, "preflight", checked)
    monkeypatch.setattr(renderer_pin, "verify", checked)
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
    assert batch.run(args) == 0
    assert seen == ["chrome-153"] * 4
    assert args.worker_args[-2:] == ["--renderer-pin", "chrome-153"]
    receipt = json.loads(next(fake_batch_env.rglob("receipt.json")).read_text())
    assert receipt["renderer_pin"] == "chrome-153"


def test_fallback_recaptures_only_quarantined_four(fake_batch_env, monkeypatch):
    from mve.observer import quarantine_partial as partial, snapshot_render as render
    from tests.mve.observer.test_snapshot_batch import fake_packet

    plan = inv.load()
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "6"]) == 0
    base = next(fake_batch_env.glob("mve/generated/wo1b-*"))
    chosen = [
        j["snapshot_id"]
        for j in batch.select_jobs(plan, 6)
        if j["block"]["cluster"] == "spectral-contrast-2"
    ]
    kept = {
        p.name: batch.s.tree_listing(p)
        for p in (base / "snapshots").iterdir()
        if p.name not in chosen
    }
    assert (
        partial.main(
            [
                "--base",
                str(base.relative_to(fake_batch_env)),
                "--plan",
                str(inv.ROOT / inv.PLAN),
                "--name",
                "fallback",
                "--cluster",
                "spectral-contrast-2",
                "--attempt",
                "batch-006-000",
                "--reason",
                "153 unavailable",
                "--snapshots",
                *chosen,
            ]
        )
        == 0
    )
    monkeypatch.setattr(policy, "browser_version", lambda _: "154.fixture")

    def packet(context, root, job, versions, ocr, **kw):
        p = fake_packet(job, job["raw"])
        p["versions"]["chrome"] = "154.fixture"
        return p

    monkeypatch.setattr(render, "capture_block", packet)
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "6"]) == 0
    state = evidence.resume_state(base, plan)
    assert len(state["completed"]) == 10
    assert state["cluster_versions"]["spectral-contrast-2"] == "154.fixture"
    assert state["quarantine"][0]["snapshot_ids"] == sorted(chosen)
    assert all(
        batch.s.tree_listing(base / "snapshots" / ident) == files
        for ident, files in kept.items()
    )
