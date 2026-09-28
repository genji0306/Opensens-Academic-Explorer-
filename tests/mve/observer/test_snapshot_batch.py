import io
import json
from pathlib import Path
from copy import deepcopy
import pytest
from PIL import Image
from mve.observer import (
    snapshot_batch as batch,
    snapshot_inventory as inv,
    snapshot_render as render,
)


def png():
    image = Image.new("RGB", (640, 400), "#091113")
    image.putpixel((90, 90), (134, 235, 201))
    image.putpixel((91, 90), (38, 56, 59))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def fake_packet(job, raw):
    return dict(
        full=png(),
        blind=png(),
        data=raw,
        crop=[0, 0, 640, 400],
        masks=[],
        state={"camera": "fixture"},
        versions={"adapter": "fixture", "chrome": "153.fixture"},
    )


def finish_fixture(folder, plan, job, a, b, seconds):
    candidate = batch.finish_snapshot(folder, plan, job, a, b, seconds)
    return batch.accept_snapshot(
        folder,
        plan,
        job,
        candidate,
        {
            "source_repos_unchanged": True,
            "archive_unchanged": True,
            "source_audit_before_sha256": "fixture",
            "source_audit_after_sha256": "fixture",
        },
    )


def test_batch_selection_pilot_and_bounds():
    plan = inv.load()
    assert len(batch.select_jobs(plan, 0)) == 10
    pilot = batch.select_jobs(plan, 0, pilot=True)
    assert len(pilot) == 10 and len({j["block"]["cluster"] for j in pilot}) == 1
    assert len(batch.select_jobs(plan, 27)) == 10
    for k in [-1, 28]:
        with pytest.raises(ValueError):
            batch.select_jobs(plan, k)
    with pytest.raises(ValueError):
        batch.select_jobs(plan, 0, size=11)


def test_lean_pair_and_immutable_resume(tmp_path):
    plan = inv.load()
    job = batch.select_jobs(plan, 0)[0]
    raw = inv.block_data(plan, job["block"], purpose="capture")
    folder = tmp_path / job["snapshot_id"]
    folder.mkdir()
    a = fake_packet(job, raw)
    batch.save_pass(folder, 0, a)
    batch.save_pass(folder, 1, a)
    receipt = finish_fixture(folder, plan, job, a, a, 1.25)
    assert receipt["repeat"]["passed"] and receipt["bytes"] < inv.SNAPSHOT_CAP
    assert sorted(p.name for p in folder.iterdir()) == [
        "blind-0.png",
        "blind-1.png",
        "complete.json",
        "data.json",
        "difference.json",
        "pass-0.json",
        "pass-1.json",
    ]
    assert batch.completed(folder, plan, job)
    with pytest.raises(FileExistsError):
        batch.save_pass(folder, 0, a)
    (folder / "blind-1.png").write_bytes(b"drift")
    with pytest.raises(ValueError):
        batch.completed(folder, plan, job)


def test_failed_repeat_and_partial_never_skipped(tmp_path):
    plan = inv.load()
    job = batch.select_jobs(plan, 0)[0]
    a = fake_packet(job, inv.block_data(plan, job["block"], purpose="capture"))
    with pytest.raises(ValueError, match="incomplete"):
        batch.completed(tmp_path, plan, job)
    batch.save_pass(tmp_path, 0, a)
    b = deepcopy(a)
    b["data"] = b"{}\n"
    with pytest.raises(ValueError):
        batch.save_pass(tmp_path, 1, b)
    b = deepcopy(a)
    b["full"] = io.BytesIO()
    image = Image.new("RGB", (640, 400), "red")
    image.save(b["full"], format="PNG")
    b["full"] = b["full"].getvalue()
    batch.save_pass(tmp_path, 1, b)
    with pytest.raises(ValueError, match="repeat"):
        finish_fixture(tmp_path, plan, job, a, b, 1)
    assert not (tmp_path / "complete.json").exists()


def test_admission_accounts_full_inventory_and_archives(tmp_path, monkeypatch):
    monkeypatch.setattr(
        batch.storage.shutil, "disk_usage", lambda _: (10**11, 0, 10**11)
    )
    r = batch.admit(tmp_path, 280, 2 * 1024**2)
    assert r["projected_bytes"] < 200 * 1024**2
    with pytest.raises(ValueError):
        batch.admit(tmp_path, 280, 70 * 1024**2)
    monkeypatch.setattr(batch.storage.shutil, "disk_usage", lambda _: (10**11, 0, 1))
    with pytest.raises(Exception):
        batch.admit(tmp_path, 1, 0)


def test_block_response_patches_are_audited():
    for name, replacements in render.BLOCK_PATCHES.items():
        # Block transforms run after the existing WO-1 transformation.
        text = "\n".join(old for old, new in replacements)
        changed = render.block_transform(name, text)
        for old, new in replacements:
            assert new in changed
        with pytest.raises(ValueError, match="drift"):
            render.block_transform(name, "")


@pytest.mark.parametrize("module", inv.MODULES)
def test_native_capture_with_fake_page_and_actual_export(module, tmp_path):
    from unittest.mock import Mock
    from mve.observer import snapshots as s

    plan = inv.load()
    job = next(j for j in inv.jobs(plan) if j["module"] == module)
    job["raw"] = inv.block_data(plan, job["block"], purpose="capture")
    page = Mock()
    page.locator.return_value.bounding_box.return_value = {
        "x": 0,
        "y": 0,
        "width": 640,
        "height": 400,
    }
    page.screenshot.return_value = png()

    def evaluate(code, *args, **kwargs):
        if code == render.DATA_JS:
            return json.loads(job["raw"])
        if code == render.STATE_JS:
            return {"camera": "fixture"}

    page.evaluate.side_effect = evaluate
    context = Mock()
    context.new_page.return_value = page
    packet = render.capture_block(context, tmp_path, job, {"adapter": "fixture"}, None)
    assert packet["data"] == job["raw"]
    assert s.png_chunks(packet["blind"]) == ["IHDR", "IDAT", "IEND"]
    page.close.assert_called_once()
    page.locator.return_value.bounding_box.return_value = None
    with pytest.raises(ValueError, match="canvas"):
        render.capture_block(context, tmp_path, job, {}, None)
    page.evaluate.side_effect = (
        lambda code, *a, **kw: {} if code == render.DATA_JS else None
    )
    with pytest.raises(ValueError, match="numeric"):
        render.capture_block(context, tmp_path, job, {}, None)


def test_native_redraw_data_drift(tmp_path):
    from unittest.mock import Mock

    plan = inv.load()
    job = inv.jobs(plan)[0]
    job["raw"] = inv.block_data(plan, job["block"], purpose="capture")
    page = Mock()
    page.locator.return_value.bounding_box.return_value = {
        "x": 0,
        "y": 0,
        "width": 640,
        "height": 400,
    }
    page.screenshot.return_value = png()
    calls = 0

    def evaluate(code, *a, **kw):
        nonlocal calls
        if code == render.DATA_JS:
            calls += 1
            return json.loads(job["raw"]) if calls == 1 else {}

    page.evaluate.side_effect = evaluate
    context = Mock()
    context.new_page.return_value = page
    with pytest.raises(ValueError, match="redraw"):
        render.capture_block(context, tmp_path, job, {}, None)


@pytest.fixture
def fake_batch_env(tmp_path, monkeypatch):
    from mve.observer import snapshots as s

    monkeypatch.setattr(batch.policy, "browser_version", lambda _: "153.fixture")
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    monkeypatch.setattr(batch.storage, "WORKTREE", tmp_path)
    monkeypatch.setattr(
        batch.inv,
        "load",
        lambda path=None: json.loads((inv.ROOT / inv.PLAN).read_text()),
    )
    plan = inv.load()
    monkeypatch.setattr(batch.inv.data, "verify_cache", lambda _: plan["cache"])
    monkeypatch.setattr(batch, "archive_size", lambda _: 1000)
    monkeypatch.setattr(s, "isolation_state", lambda _: {"fixture": "unchanged"})

    def archive(repo, name, dest, generated):
        dest.mkdir(parents=True)
        (dest / "fixture").write_bytes(b"pinned")

    monkeypatch.setattr(s, "archive_repo", archive)
    monkeypatch.setattr(batch, "check_stage", lambda _: {"fixture": "checked"})
    monkeypatch.setattr(
        batch.render,
        "run_browser",
        lambda dist, out, chrome, ocr, private, **kw: [
            kw["capture"](None, out, j, {}, None) for j in kw["jobs"]
        ],
    )
    monkeypatch.setattr(
        batch.render,
        "capture_block",
        lambda context, root, job, versions, ocr, **kw: fake_packet(job, job["raw"]),
    )

    def isolated(args, out, repos, receipt):
        monkeypatch.setenv("MVE_WO1_SANDBOX_WORKER", "1")
        monkeypatch.setenv("MVE_WO1_PRIVATE_DIR", "/private/tmp/mvewo1-fixture")
        batch.worker(args, out)

    monkeypatch.setattr(batch.old, "isolated_capture", isolated)
    return tmp_path


def test_batch_cli_prepares_captures_then_skips_completed(fake_batch_env):
    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0", "--pilot"]
    assert batch.main(args + ["--prepare-only"]) == 0
    assert batch.main(args) == 0
    assert batch.main(args) == 0
    receipts = [
        json.loads(p.read_text())
        for p in fake_batch_env.glob("mve/generated/wo1b-*/pilot-*/receipt.json")
    ]
    assert {r["status"] for r in receipts} == {
        "prepared_only",
        "captured",
        "already_complete",
    }
    capture = json.loads(
        next(
            fake_batch_env.glob("mve/generated/wo1b-*/pilot-*/capture.json")
        ).read_text()
    )
    assert capture["snapshots"] == 10 and capture["bytes"] < 10 * inv.SNAPSHOT_CAP
    assert (
        len(list(fake_batch_env.glob("mve/generated/wo1b-*/snapshots/*/complete.json")))
        == 10
    )
    assert not list(fake_batch_env.rglob("full.png"))
    assert not list(fake_batch_env.rglob("stage"))


def test_cli_failed_capture_retains_partial_and_refuses_resume(
    fake_batch_env, monkeypatch
):
    def broken(*a, **kw):
        raise ValueError("fixture fail")

    monkeypatch.setattr(batch.render, "capture_block", broken)
    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "1"]
    assert batch.main(args) == 2
    assert batch.main(args) == 2
    assert next(fake_batch_env.rglob("receipt.json")).exists()


def test_cli_source_drift_and_cache_fail_closed(fake_batch_env, monkeypatch):
    calls = 0

    def audit(_):
        nonlocal calls
        calls += 1
        return {"fixture": calls}

    monkeypatch.setattr(batch.s, "isolation_state", audit)
    args = ["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0", "--prepare-only"]
    assert batch.main(args) == 2
    monkeypatch.setattr(batch.inv.data, "verify_cache", lambda _: {})
    assert batch.main(args) == 2


def test_worker_and_cli_guards(fake_batch_env, monkeypatch):
    args = batch.parse_args(
        [
            "--plan",
            str(inv.ROOT / inv.PLAN),
            "--batch",
            "0",
            "--worker",
            "--output",
            "mve/generated/wrong",
        ]
    )
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "-1"]) == 2
    assert (
        batch.main(
            [
                "--plan",
                str(inv.ROOT / inv.PLAN),
                "--batch",
                "0",
                "--worker",
                "--output",
                "mve/generated/wrong",
            ]
        )
        == 2
    )
    monkeypatch.delenv("MVE_WO1_SANDBOX_WORKER", raising=False)
    with pytest.raises(ValueError, match="sandboxed"):
        batch.worker(args, fake_batch_env)
    with pytest.raises(SystemExit):
        batch.parse_args(["--plan", "x", "--batch", "0", "--timeout-per-pass", "0"])
    with pytest.raises(ValueError):
        batch.select_jobs(inv.load(), 1, pilot=True)
    with pytest.raises(ValueError):
        batch.save_pass(fake_batch_env, 2, {})


def test_completed_artifact_identity_and_numeric_guards(tmp_path):
    plan = inv.load()
    job = inv.jobs(plan)[0]
    a = fake_packet(job, inv.block_data(plan, job["block"], purpose="capture"))
    batch.save_pass(tmp_path, 0, a)
    batch.save_pass(tmp_path, 1, a)
    receipt = finish_fixture(tmp_path, plan, job, a, a, 1)
    original = (tmp_path / "complete.json").read_bytes()
    r = deepcopy(receipt)
    r["view"] = 1
    (tmp_path / "complete.json").write_bytes(inv.encoded(inv.seal(r)))
    with pytest.raises(ValueError, match="identity"):
        batch.completed(tmp_path, plan, job)
    (tmp_path / "complete.json").write_bytes(original)
    (tmp_path / "extra").write_text("unexpected")
    with pytest.raises(ValueError, match="artifact set"):
        batch.completed(tmp_path, plan, job)
    (tmp_path / "extra").unlink()
    (tmp_path / "data.json").write_bytes(b"{}")
    r = deepcopy(receipt)
    r["files"]["data.json"] = batch.sha(b"{}")
    (tmp_path / "complete.json").write_bytes(inv.encoded(inv.seal(r)))
    with pytest.raises(ValueError, match="numeric"):
        batch.completed(tmp_path, plan, job)


def test_snapshot_cap_before_completing(tmp_path, monkeypatch):
    plan = inv.load()
    job = inv.jobs(plan)[0]
    a = fake_packet(job, inv.block_data(plan, job["block"], purpose="capture"))
    with pytest.raises(ValueError, match="envelope"):
        batch.save_pass(tmp_path, 0, {**a, "blind": b"x" * inv.SNAPSHOT_CAP})
    monkeypatch.setattr(inv, "SNAPSHOT_CAP", 1)
    with pytest.raises(ValueError, match="envelope"):
        finish_fixture(tmp_path, plan, job, a, a, 1)


def test_exact_pinned_js_patches_parse_and_no_source_edit(tmp_path):
    import subprocess
    from mve.observer import snapshots as s

    repo = Path(batch.old.DEFAULT_REPOS["atlas"]).expanduser()
    if not repo.exists():
        pytest.skip("owner local pinned atlas unavailable")
    hashes = {}
    for name in render.BLOCK_PATCHES:
        raw = subprocess.check_output(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(repo),
                "show",
                s.COMMITS["atlas"] + ":vendor/zeta-explorer/dist/" + name,
            ]
        ).decode()
        changed = render.block_transform(name, render.transform(name, raw))
        subprocess.run(
            ["node", "--input-type=module", "--check"],
            input=changed,
            text=True,
            check=True,
            capture_output=True,
        )
        hashes[name] = batch.sha(raw.encode())
    assert len(hashes) == 4


def test_injected_native_numeric_selections_execute_in_node():
    import subprocess

    for filename, module in [
        ("research.js", "spectral"),
        ("field-phase3.js", "field-dyson"),
        ("polar.js", "polar-ulam"),
        ("prime-sphere.js", "space-08"),
    ]:
        select = render.BLOCK_PATCHES[filename][0][1]
        export = render.BLOCK_PATCHES[filename][1][1]
        # The field anchor begins mid-declaration; the spectral anchor continues
        # a declaration list. Everything else is exact response-patch code.
        if filename == "field-phase3.js":
            select = "const " + select
        if filename == "research.js":
            select += ";"
        setup = """const window={__mveBlock:{values:VALUES,extent:40000,seed:123},__mveBlockModule:MODULE};
        const histogram=x=>x, statistics=x=>x, S={N:30000}, r={width:640,height:400}, fit=()=>{}, o={};
        """.replace(
            "VALUES", "[[0,1,2]]" if module == "field-dyson" else "[2,5,11]"
        ).replace("MODULE", json.dumps(module))
        result = subprocess.run(
            ["node", "--input-type=module"],
            input=setup
            + select
            + export
            + "console.log(JSON.stringify(window.__mveData));",
            text=True,
            capture_output=True,
            check=True,
        )
        assert json.loads(result.stdout)["values"] == (
            [[0, 1, 2]] if module == "field-dyson" else [2, 5, 11]
        )


def test_prospective_virtual_route(tmp_path):
    from unittest.mock import Mock
    from types import SimpleNamespace

    filename = "research.js"
    # Same route used by the native browser; transform both stages in memory.
    text = "\n".join(old for old, new in render.PATCHES[filename])
    (tmp_path / filename).write_text(text)
    route = Mock()
    render.route_handler(tmp_path, prospective=True)(
        route, SimpleNamespace(url=render.ORIGIN + "/" + filename, method="GET")
    )
    assert b"__mveBlock.values" in route.fulfill.call_args.kwargs["body"]
    assert (tmp_path / filename).read_text() == text


def test_actual_pathspec_only_preparation(tmp_path):
    repos = {
        name: Path(path).expanduser() for name, path in batch.old.DEFAULT_REPOS.items()
    }
    if not all(p.exists() for p in repos.values()):
        pytest.skip("local pinned sources unavailable")
    size = batch.archive_size(repos)
    assert size < 20 * 1024**2
    for name, repo in repos.items():
        batch.s.archive_repo(repo, name, tmp_path / name, tmp_path / "generated")
    hashes = batch.check_stage(tmp_path)
    assert set(hashes) == set(render.BLOCK_PATCHES)
    assert all(
        row["source_sha256"] != row["response_sha256"] for row in hashes.values()
    )


def test_archive_type_refusal(monkeypatch):
    import subprocess

    monkeypatch.setattr(
        subprocess, "check_output", lambda *a, **kw: b"120000 blob deadbeef 12\tlink\n"
    )
    with pytest.raises(ValueError):
        batch.archive_size({"atlas": Path(".")})


def test_worker_entry_from_parent(fake_batch_env, monkeypatch):
    plan = inv.load()
    base = fake_batch_env / "mve/generated" / ("wo1b-" + plan["sha256"][:16])
    (base / "snapshots").mkdir(parents=True)
    out = base / "batch-000-000"
    out.mkdir()
    monkeypatch.setenv("MVE_WO1_SANDBOX_WORKER", "1")
    monkeypatch.setenv("MVE_WO1_PRIVATE_DIR", "/private/tmp/mvewo1-fixture")
    assert (
        batch.main(
            [
                "--plan",
                str(inv.ROOT / inv.PLAN),
                "--batch",
                "0",
                "--worker",
                "--output",
                str(out.relative_to(fake_batch_env)),
            ]
        )
        == 0
    )


def test_parent_rejects_missing_worker_results(fake_batch_env, monkeypatch):
    monkeypatch.setattr(batch.old, "isolated_capture", lambda *a: None)
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]) == 2


def test_worker_pass_timeout(fake_batch_env, monkeypatch):
    import signal

    args = batch.parse_args(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"])
    plan = inv.load()
    base = fake_batch_env / "mve/generated" / ("wo1b-" + plan["sha256"][:16])
    (base / "snapshots").mkdir(parents=True)
    out = base / "batch-000-000"
    out.mkdir()
    monkeypatch.setenv("MVE_WO1_SANDBOX_WORKER", "1")
    monkeypatch.setenv("MVE_WO1_PRIVATE_DIR", "/private/tmp/mvewo1-fixture")

    def expire(*a, **kw):
        signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)

    monkeypatch.setattr(render, "run_browser", expire)
    with pytest.raises(ValueError, match="timeout"):
        batch.worker(args, out)


def test_bounded_log_keeps_evidence_on_failure(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    private = tmp_path / "runtime"
    private.mkdir()
    receipt = {}
    with pytest.raises(RuntimeError):
        with batch.old.capture_log(out, private, receipt, 8) as log:
            log.write("0123456789abcdef")
            raise RuntimeError("fixture")
    assert (out / "browser.log").read_text() == "01234567"
    assert receipt["browser_log_truncated"]


def test_observer_delivery_cannot_read_replication_even_for_tuning(
    tmp_path, monkeypatch
):
    plan = inv.load()
    job = inv.jobs(plan)[0]
    folder = tmp_path / job["snapshot_id"]
    folder.mkdir()
    a = fake_packet(job, inv.block_data(plan, job["block"], purpose="capture"))
    batch.save_pass(folder, 0, a)
    batch.save_pass(folder, 1, a)
    finish_fixture(folder, plan, job, a, a, 1)
    assert (
        inv.observer_png(plan, job["block"]["id"], 0, tmp_path, purpose="observer")
        == a["blind"]
    )
    with pytest.raises(ValueError):
        inv.observer_png(plan, job["block"]["id"], 2, tmp_path, purpose="observer")
    with pytest.raises(ValueError):
        inv.observer_png(plan, job["block"]["id"], 1, tmp_path, purpose="observer")
    held = next(b for b in plan["blocks"] if b["partition"] == "R")
    monkeypatch.setattr(
        Path, "read_bytes", lambda *a: pytest.fail("R opened before refusal")
    )
    for purpose in ["observer", "tuning"]:
        with pytest.raises(ValueError, match="replication"):
            inv.observer_png(plan, held["id"], 0, tmp_path, purpose=purpose)


def test_successful_pixels_are_not_complete_before_source_audit(tmp_path):
    plan = inv.load()
    job = inv.jobs(plan)[0]
    a = fake_packet(job, inv.block_data(plan, job["block"], purpose="capture"))
    batch.save_pass(tmp_path, 0, a)
    batch.save_pass(tmp_path, 1, a)
    candidate = batch.finish_snapshot(tmp_path, plan, job, a, a, 1)
    with pytest.raises(ValueError, match="incomplete"):
        batch.completed(tmp_path, plan, job)
    with pytest.raises(ValueError, match="audit"):
        batch.accept_snapshot(
            tmp_path,
            plan,
            job,
            candidate,
            {
                "source_repos_unchanged": False,
                "archive_unchanged": True,
                "source_audit_before_sha256": "a",
                "source_audit_after_sha256": "b",
            },
        )
    assert not (tmp_path / "complete.json").exists()


def test_captured_but_source_drift_never_becomes_skippable(fake_batch_env, monkeypatch):
    calls = 0

    def audit(_):
        nonlocal calls
        calls += 1
        return {"fixture": calls}

    monkeypatch.setattr(batch.s, "isolation_state", audit)
    assert batch.main(["--plan", str(inv.ROOT / inv.PLAN), "--batch", "0"]) == 2
    assert list(fake_batch_env.rglob("blind-0.png"))
    assert not list(fake_batch_env.rglob("complete.json"))
