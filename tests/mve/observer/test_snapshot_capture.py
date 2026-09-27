import io
import json
import os
from pathlib import Path
import site
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from mve.observer import snapshot_capture as c, snapshot_render as r
from mve.observer import snapshots as s


@pytest.fixture
def private_runtime():
    with tempfile.TemporaryDirectory(prefix="mvewo1-", dir="/private/tmp") as root:
        yield Path(root)


def test_source_patches_fail_closed_and_expose_single_source():
    for filename, replacements in r.PATCHES.items():
        fixture = "\n".join(old for old, new in replacements)
        transformed = r.transform(filename, fixture)
        for old, new in replacements:
            assert new in transformed
        with pytest.raises(ValueError, match="drift"):
            r.transform(filename, "")
    assert r.transform("ordinary.js", "unchanged") == "unchanged"
    assert "__mveFieldRedraw" in r.transform(
        "field-lab.js", "boxMode: false, paused: false,"
    )
    assert "fillText" in r.INIT_SCRIPT and "strokeText" in r.INIT_SCRIPT


def test_virtual_route_never_falls_back_to_network(tmp_path):
    (tmp_path / "index.html").write_text("<h1>local only</h1>")
    handler = r.route_handler(tmp_path)
    for url in [
        "https://example.com/secret",
        "https://mve.invalid/../bad",
        "https://mve.invalid/missing",
    ]:
        route = Mock()
        handler(route, SimpleNamespace(url=url, method="GET"))
        route.abort.assert_called_once()
        route.fulfill.assert_not_called()
    route = Mock()
    handler(route, SimpleNamespace(url="https://mve.invalid/index.html", method="GET"))
    route.fulfill.assert_called_once()
    assert route.fulfill.call_args.kwargs["body"] == b"<h1>local only</h1>"
    route = Mock()
    handler(route, SimpleNamespace(url="https://mve.invalid/index.html", method="POST"))
    route.abort.assert_called_once()


def test_sandbox_profile_and_cli_restrictions(tmp_path, private_runtime):
    out = tmp_path / "mve/generated/capture"
    profile = c.sandbox_profile(out, private_runtime)
    # Exact equality prevents accidental broad write exceptions, including the
    # whole worktree, real HOME, shared /tmp, or shared /private/tmp.
    assert profile == (
        "(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n"
        f"(allow file-write* (subpath {json.dumps(str(out.resolve()))}) "
        f"(subpath {json.dumps(str(private_runtime))}))\n"
        '(allow file-write-data (literal "/dev/null"))\n'
    )
    home, tmp = c.private_paths(private_runtime)
    assert home.parent == tmp.parent == private_runtime
    assert private_runtime.stat().st_mode & 0o777 == 0o700
    assert len(os.fsencode(tmp)) + 1 + 64 < 100
    socket = tmp / ".org.chromium.Chromium.XXXXXX/SingletonSocket"
    assert len(os.fsencode(socket)) < 100
    with pytest.raises(ValueError, match="socket-path"):
        c.sandbox_profile(out, Path("/private/tmp/mvewo1-" + "x" * 80))
    with pytest.raises(ValueError, match="private"):
        c.sandbox_profile(out, Path("/private/tmp"))
    assert c.parse_args(["--prepare-only"]).prepare_only
    with pytest.raises(ValueError):
        c.output_path(tmp_path, "../escape")
    with pytest.raises(ValueError):
        c.output_path(tmp_path, "elsewhere")
    assert c.output_path(tmp_path, "mve/generated/capture").is_relative_to(tmp_path)


def test_browser_capture_fixture(tmp_path, monkeypatch):
    """Exercises orchestration with a fixture page, not a live browser claim."""

    class Page:
        def __init__(self):
            self.blind = False

        def add_init_script(self, *a, **kw):
            pass

        def goto(self, *a, **kw):
            pass

        def wait_for_function(self, *a, **kw):
            pass

        def evaluate(self, code, *args):
            if code == r.DATA_JS:
                return {"values": [1, 2, 3], "source": "zeros 11-100", "seed": 20260926}
            if code == r.TEXT_JS:
                return ["GUE planted title", "Poisson planted caption"]
            if code == r.STATE_JS:
                return {"controls": {}, "camera": None}
            if code == r.BLIND_JS:
                self.blind = True

        def locator(self, selector):
            return self

        def bounding_box(self):
            return {"x": 0, "y": 0, "width": 320, "height": 240}

        def screenshot(self, **kwargs):
            out = io.BytesIO()
            im = Image.new("RGB", (320, 240), "#091113")
            im.putpixel((90, 90), (134, 235, 201))
            im.putpixel((91, 90), (38, 56, 59))
            im.save(out, format="PNG")
            return out.getvalue()

        def close(self):
            pass

    page = Page()
    context = Mock()
    context.new_page.return_value = page
    monkeypatch.setattr(r, "configure", lambda p, j: None)
    monkeypatch.setattr(s, "disk_guard", lambda *a: None)
    job = s.capture_jobs()[0]
    entry = r.capture_one(context, tmp_path, job, {"chrome": "fixture"}, None)
    assert page.blind
    assert entry["data_ref"]["sha256"]
    assert entry["png_blinded"]["metadata_stripped"]
    assert set(entry["png_blinded"]["chunks"]) == {"IHDR", "IDAT", "IEND"}


def test_masks_and_nonblank_detection():
    assert r.masks_for("polar-ulam", 320, 240) == [(0, 0, 320, 50), (0, 210, 320, 240)]
    assert len(r.masks_for("spectral", 320, 240)) == 4
    assert len(r.masks_for("field-dyson", 600, 240)) == 6
    assert len(r.masks_for("field-dyson", 320, 240)) == 6
    assert r.masks_for("space-08", 320, 240) == []
    out = io.BytesIO()
    Image.new("RGB", (20, 20)).save(out, format="PNG")
    with pytest.raises(ValueError, match="blank"):
        r.assert_nonblank(out.getvalue())


def test_sandbox_denies_write_to_outside_fixture(tmp_path, private_runtime):
    """Real OS denial test; nested-sandbox refusal is a named skip, not a pass."""
    import shutil
    import subprocess
    import sys

    if not shutil.which("sandbox-exec"):
        pytest.skip("sandbox-exec unavailable")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    code = "import os,sys\ntry: os.open(sys.argv[1],os.O_WRONLY)\nexcept PermissionError: sys.exit(0)\nsys.exit(2)"
    proc = subprocess.run(
        [
            "sandbox-exec",
            "-p",
            c.sandbox_profile(allowed, private_runtime),
            sys.executable,
            "-c",
            code,
            str(outside),
        ],
        capture_output=True,
        text=True,
    )
    if "sandbox_apply: Operation not permitted" in proc.stderr:
        pytest.skip("nested-sandbox-only: sandbox_apply Operation not permitted")
    assert proc.returncode == 0
    assert outside.read_text() == "untouched"


def test_configure_all_modules():
    page = Mock()
    for job in s.capture_jobs():
        r.configure(page, job)
    assert page.select_option.call_count > 10
    page.wait_for_function.assert_called()


def test_text_suppression_executes_fixture_html(tmp_path):
    """Execute the real fixture script plus the actual init hook in offline Node."""
    import json
    import re
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("offline node unavailable")
    html = (Path(__file__).parent / "snapshot_fixtures/lab.html").read_text()
    script = re.search(r"<script>(.*?)</script>", html, re.S)[1]
    js = """
const vm=require('node:vm');
let text=[];
class CanvasRenderingContext2D {fillText(t){text.push(t)} strokeText(t){text.push(t)} fillRect(){}}
let context=new CanvasRenderingContext2D();
let env={CanvasRenderingContext2D,Math:Object.create(Math),window:{},document:{querySelector:()=>({getContext:()=>context})}};
vm.createContext(env);
vm.runInContext(INIT,env);
vm.runInContext(SCRIPT,env);
if(!text.includes('GUE planted legend'))throw Error('planted text was not seen');
text=[];env.window.__mveBlind=true;
vm.runInContext(SCRIPT.replace('const c =','var c2 =').replaceAll('c.','c2.'),env);
context.strokeText('withheld stroke');
if(text.length)throw Error('canvas text leaked');
console.log('fixture text calls suppressed');
""".replace("INIT", json.dumps(r.INIT_SCRIPT)).replace("SCRIPT", json.dumps(script))
    result = subprocess.run(
        [node, "-e", js], capture_output=True, text=True, check=True
    )
    assert "suppressed" in result.stdout


def test_javascript_route_and_png_nonblank(tmp_path):
    (tmp_path / "ordinary.js").write_text("const value=1;")
    handler = r.route_handler(tmp_path)
    route = Mock()
    handler(route, SimpleNamespace(url="https://mve.invalid/ordinary.js", method="GET"))
    assert route.fulfill.call_args.kwargs["body"] == b"const value=1;"
    im = Image.new("RGB", (20, 20))
    im.putpixel((1, 1), (1, 2, 3))
    im.putpixel((2, 2), (3, 2, 1))
    out = io.BytesIO()
    im.save(out, format="PNG")
    r.assert_nonblank(out.getvalue())


def test_worker_and_browser_orchestration(tmp_path, monkeypatch, private_runtime):
    args = c.parse_args(["--worker", "--repeat"])
    with pytest.raises(ValueError, match="parent"):
        c.run_worker(args, tmp_path)
    monkeypatch.setenv("MVE_WO1_SANDBOX_WORKER", "1")
    monkeypatch.setenv("MVE_WO1_PRIVATE_DIR", str(private_runtime))
    manifest = {
        "snapshots": [
            {
                "snapshot_id": "x",
                **{
                    k: {"sha256": "hash"}
                    for k in ("png_full", "png_blinded", "data_ref")
                },
            }
        ]
    }
    monkeypatch.setattr(r, "run_browser", lambda *a: manifest)
    assert c.run_worker(args, tmp_path) == 0
    assert (tmp_path / "repeat-verification.json").exists()
    assert not (tmp_path / "repeat").exists()
    (tmp_path / "capture").rmdir()
    changed = {
        "snapshots": [
            {
                "snapshot_id": "x",
                **{
                    k: {"sha256": "bad"}
                    for k in ("png_full", "png_blinded", "data_ref")
                },
            }
        ]
    }
    monkeypatch.setattr(r, "run_browser", Mock(side_effect=[manifest, changed]))
    with pytest.raises(ValueError, match="mismatch"):
        c.run_worker(args, tmp_path)


def test_run_browser_lifecycle(tmp_path, monkeypatch, private_runtime):
    import playwright.sync_api

    context = Mock()
    context.browser.version = "fixture chrome"
    launcher = Mock()
    launcher.chromium.launch_persistent_context.return_value = context
    manager = Mock()
    manager.__enter__ = Mock(return_value=launcher)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: manager)
    monkeypatch.setattr(s, "disk_guard", lambda *a: None)
    monkeypatch.setattr(s, "validate_manifest", lambda *a: None)
    monkeypatch.setattr(r, "capture_one", lambda context, out, job, *args: job)
    out = tmp_path / "capture"
    out.mkdir()
    manifest = r.run_browser(tmp_path, out, "chrome", None, private_runtime)
    assert len(manifest["snapshots"]) == 8
    context.close.assert_called_once()
    kwargs = launcher.chromium.launch_persistent_context.call_args.kwargs
    assert kwargs["device_scale_factor"] == 1 and kwargs["service_workers"] == "block"
    assert "--use-angle=swiftshader" in kwargs["args"]
    assert {
        "--disable-crash-reporter",
        "--disable-breakpad",
        "--no-first-run",
        "--no-default-browser-check",
    }.issubset(kwargs["args"])
    # Persistent-context user_data_dir is Playwright's --user-data-dir flag.
    assert launcher.chromium.launch_persistent_context.call_args.args == (
        str(private_runtime / "capture"),
    )
    assert kwargs["env"] == {
        "PATH": "/usr/bin:/bin",
        "HOME": str(private_runtime / "h"),
        "TMPDIR": str(private_runtime / "t"),
    }


@pytest.mark.parametrize("inherited_userbase", [None, "/unused-stale-userbase"])
def test_worker_preserves_parent_userbase_with_private_home(
    tmp_path, monkeypatch, inherited_userbase
):
    if inherited_userbase is None:
        monkeypatch.delenv("PYTHONUSERBASE", raising=False)
    else:
        monkeypatch.setenv("PYTHONUSERBASE", inherited_userbase)
    monkeypatch.setattr(c, "readonly_probe", Mock())
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(c.subprocess, "run", run)
    repos = {"atlas": tmp_path / "atlas", "lab": tmp_path / "lab"}

    c.isolated_capture(c.parse_args([]), tmp_path, repos, {})

    env = run.call_args.kwargs["env"]
    private = Path(env["MVE_WO1_PRIVATE_DIR"])
    assert env["PYTHONUSERBASE"] == site.USER_BASE
    assert env["HOME"] == str(private / "h")
    assert env["TMPDIR"] == str(private / "t")
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


@pytest.mark.parametrize("failure", [None, "probe", "returncode", "launch"])
def test_private_runtime_cleanup_and_worker_environment(tmp_path, monkeypatch, failure):
    """No browser: inspect the subprocess boundary and all cleanup exits."""
    seen = []

    def probe(profile, files):
        # Recover the exact fresh path from the generated allowlist.
        import re

        runtime = Path(json.loads(re.findall(r'\(subpath ("[^"]+")\)', profile)[1]))
        seen.append(runtime)
        assert runtime.exists()
        if failure == "probe":
            raise ValueError("fixture probe failure")

    def run(command, **kwargs):
        runtime = seen[-1]
        env = kwargs["env"]
        assert command[:2] == ["sandbox-exec", "-p"]
        assert command[2] == c.sandbox_profile(tmp_path, runtime)
        assert command[-1] == "--repeat"
        assert env["MVE_WO1_PRIVATE_DIR"] == str(runtime)
        assert env["HOME"] == str(runtime / "h")
        assert env["TMPDIR"] == str(runtime / "t")
        assert (runtime / "h").is_dir() and (runtime / "t").is_dir()
        (runtime / "t/fixture-socket").write_text("cleanup fixture")
        if failure == "launch":
            raise OSError("fixture launch failure")
        return SimpleNamespace(returncode=int(failure == "returncode"))

    monkeypatch.setattr(c, "readonly_probe", probe)
    monkeypatch.setattr(c.subprocess, "run", run)
    args = c.parse_args(["--repeat"])
    repos = {"atlas": tmp_path / "atlas", "lab": tmp_path / "lab"}
    receipt = {}
    if failure:
        with pytest.raises((ValueError, OSError)):
            c.isolated_capture(args, tmp_path, repos, receipt)
    else:
        c.isolated_capture(args, tmp_path, repos, receipt)
        c.isolated_capture(args, tmp_path, repos, receipt)
        assert seen[0] != seen[1]
    assert seen and all(not path.exists() for path in seen)
    assert ("outside_write_probe" in receipt) == (failure != "probe")


def test_capture_failures_close_page(tmp_path):
    for name in ["seed", "missing_canvas"]:
        root = tmp_path / name
        root.mkdir()
        page = Mock()
        context = Mock()
        context.new_page.return_value = page
        page.evaluate.side_effect = lambda code, *a: (
            {
                "values": [1],
                "source": "zeros 11-100",
                "seed": 0 if name == "seed" else 20260926,
            }
            if code == r.DATA_JS
            else ([] if code == r.TEXT_JS else {})
        )
        page.locator.return_value.bounding_box.return_value = None
        with pytest.raises(ValueError):
            r.capture_one(context, root, s.capture_jobs()[0], {}, None)
        page.close.assert_called_once()


def fake_archive(repo, name, dest, generated):
    dest.mkdir(parents=True)
    if name == "atlas":
        dist = dest / "vendor/zeta-explorer/dist"
        dist.mkdir(parents=True)
        for filename, replacements in r.PATCHES.items():
            (dist / filename).write_text("\n".join(old for old, new in replacements))
        index = dest / "data/riemann/evidence_atlas/inputs/lab_snapshots.json"
        index.parent.mkdir(parents=True)
        index.write_text('{"snapshots":[]}')
    else:
        (dest / "scripts").mkdir()
        (dest / "scripts/astra_p34_capture.py").write_text("# fixture")


def test_prepare_and_parent_orchestration(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "WORKTREE", tmp_path)
    monkeypatch.setattr(s, "disk_guard", lambda *a: None)
    monkeypatch.setattr(s, "isolation_state", lambda *a: {"fixture": "unchanged"})
    monkeypatch.setattr(s, "archive_repo", fake_archive)
    monkeypatch.setattr(c, "readonly_probe", lambda *a: None)
    monkeypatch.setattr(c.shutil, "which", lambda _: "sandbox-exec")
    monkeypatch.setattr(
        c.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0)
    )
    assert c.main(["--prepare-only"]) == 0
    assert not (tmp_path / "mve/generated/wo1-capture/stage").exists()
    with pytest.raises(ValueError, match="exists"):
        c.main(["--prepare-only"])
    assert c.main(["--output", "mve/generated/second", "--repeat"]) == 0
    monkeypatch.setattr(c, "run_worker", lambda *a: 12)
    assert c.main(["--worker"]) == 12
    with pytest.raises(ValueError, match="separate"):
        c.main(["--output", "mve/generated/third", "--atlas", str(tmp_path / "source")])


def test_parent_failure_receipts_and_cleanup(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(c, "WORKTREE", tmp_path)
    monkeypatch.setattr(s, "disk_guard", lambda *a: None)
    monkeypatch.setattr(s, "isolation_state", lambda *a: {"fixture": "unchanged"})
    monkeypatch.setattr(s, "archive_repo", fake_archive)
    monkeypatch.setattr(c.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="unavailable"):
        c.main([])
    out = tmp_path / "mve/generated/wo1-capture"
    assert json.loads((out / "receipt.json").read_text())["capture"] == "failed"
    monkeypatch.setattr(c.shutil, "which", lambda _: "sandbox-exec")
    monkeypatch.setattr(c, "readonly_probe", lambda *a: None)
    monkeypatch.setattr(
        c.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1)
    )
    with pytest.raises(ValueError, match="capture failed"):
        c.main(["--output", "mve/generated/failed"])
    monkeypatch.setattr(s, "isolation_state", Mock(side_effect=[{}, {"changed": True}]))
    with pytest.raises(ValueError, match="isolation changed"):
        c.main(["--prepare-only", "--output", "mve/generated/mutated"])


def test_readonly_probe_outcomes(monkeypatch):
    monkeypatch.setattr(
        c.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0)
    )
    c.readonly_probe("profile", ["a", "b"])
    monkeypatch.setattr(
        c.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=2)
    )
    with pytest.raises(ValueError, match="probe"):
        c.readonly_probe("profile", ["a", "b"])
