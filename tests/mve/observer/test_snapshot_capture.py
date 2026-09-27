import io
import json
import os
from pathlib import Path
import site
import signal
import subprocess
import sys
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


@pytest.fixture
def outside_runtime():
    # pytest's default tmp_path lives inside the Darwin temp write allowance.
    with tempfile.TemporaryDirectory(
        prefix="mvewo1-outside-", dir="/private/tmp"
    ) as root:
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


def test_sandbox_profile_and_cli_restrictions(tmp_path, private_runtime, monkeypatch):
    monkeypatch.setattr(
        c,
        "darwin_runtime_paths",
        lambda: [
            Path("/private/var/folders/user/T"),
            Path("/private/var/folders/user/C"),
        ],
    )
    out = tmp_path / "mve/generated/capture"
    profile = c.sandbox_profile(out, private_runtime)
    # Exact equality prevents accidental broad write exceptions, including the
    # whole worktree, real HOME, shared /tmp, or shared /private/tmp.
    assert profile == (
        "(version 1)\n(allow default)\n(deny network*)\n"
        "(allow network* (local unix-socket))\n"
        "(allow network* (remote unix-socket))\n(deny file-write*)\n"
        f"(allow file-write* (subpath {json.dumps(str(out.resolve()))}) "
        f"(subpath {json.dumps(str(private_runtime))}) "
        '(subpath "/private/var/folders/user/T") (subpath "/private/var/folders/user/C"))\n'
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


def test_sandbox_denies_write_to_outside_fixture(
    tmp_path, private_runtime, outside_runtime
):
    """Real OS denial test; nested-sandbox refusal is a named skip, not a pass."""
    import shutil
    import subprocess
    import sys

    if not shutil.which("sandbox-exec"):
        pytest.skip("sandbox-exec unavailable")
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = outside_runtime / "outside"
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


@pytest.mark.parametrize("seconds", [300, 450])
@pytest.mark.parametrize("slow_pass", [None, "capture", "repeat"])
def test_each_capture_pass_gets_a_fresh_deadline(
    tmp_path, monkeypatch, private_runtime, seconds, slow_pass
):
    monkeypatch.setenv("MVE_WO1_SANDBOX_WORKER", "1")
    monkeypatch.setenv("MVE_WO1_PRIVATE_DIR", str(private_runtime))
    argv = ["--repeat"]
    if seconds != 300:
        argv += ["--timeout-per-pass", str(seconds)]
    args = c.parse_args(argv)
    assert args.timeout_per_pass == seconds
    now, deadline = 0, None
    armed = []
    previous = signal.getsignal(signal.SIGALRM)

    def set_timer(which, duration):
        nonlocal deadline
        assert which == signal.ITIMER_REAL
        deadline = now + duration if duration else None
        armed.append(duration)

    def capture(dist, out, *unused):
        nonlocal now
        now += seconds + 1 if out.name == slow_pass else seconds - 1
        if now >= deadline:
            signal.raise_signal(signal.SIGALRM)
        return {"snapshots": []}

    monkeypatch.setattr(c.signal, "setitimer", set_timer)
    monkeypatch.setattr(r, "run_browser", capture)
    if slow_pass:
        with pytest.raises(ValueError, match=f"{slow_pass} pass exceeded {seconds}"):
            c.run_worker(args, tmp_path)
        assert not (tmp_path / "repeat-verification.json").exists()
    else:
        assert c.run_worker(args, tmp_path) == 0
        assert now > seconds  # Both passes together exceed the old shared bound.
        assert (tmp_path / "repeat-verification.json").exists()
    assert armed == [seconds, 0] * (1 if slow_pass == "capture" else 2)
    assert deadline is None
    assert signal.getsignal(signal.SIGALRM) == previous


def test_capture_pass_real_wall_clock_timeout(tmp_path, monkeypatch):
    import time

    previous = signal.getsignal(signal.SIGALRM)
    monkeypatch.setattr(r, "run_browser", lambda *args: time.sleep(1))
    args = SimpleNamespace(timeout_per_pass=0.01, chrome="unused")
    with pytest.raises(ValueError, match="wall-clock timeout"):
        c.capture_pass(args, tmp_path, tmp_path / "capture", tmp_path)
    assert signal.getitimer(signal.ITIMER_REAL) == (0, 0)
    assert signal.getsignal(signal.SIGALRM) == previous


@pytest.mark.parametrize("value", ["0", "-1", "901", "nan"])
def test_invalid_pass_timeout(value):
    with pytest.raises(SystemExit):
        c.parse_args(["--timeout-per-pass", value])


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
    assert kwargs["chromium_sandbox"] is False
    assert Path(kwargs["executable_path"]).read_text().endswith('exec chrome "$@"\n')
    assert kwargs["device_scale_factor"] == 1 and kwargs["service_workers"] == "block"
    assert "--use-angle=swiftshader" in kwargs["args"]
    assert {
        "--headless=new",
        "--no-sandbox",
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
    monkeypatch.setattr(
        c, "darwin_runtime_paths", lambda: [Path("/private/var/folders")]
    )
    if inherited_userbase is None:
        monkeypatch.delenv("PYTHONUSERBASE", raising=False)
    else:
        monkeypatch.setenv("PYTHONUSERBASE", inherited_userbase)
    monkeypatch.setattr(c, "readonly_probe", Mock())
    run = Mock(return_value=Mock(returncode=0, pid=12345))
    monkeypatch.setattr(c.subprocess, "Popen", run)
    monkeypatch.setattr(c.os, "killpg", Mock())
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
    monkeypatch.setattr(
        c, "darwin_runtime_paths", lambda: [Path("/private/var/folders")]
    )
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
        return Mock(returncode=int(failure == "returncode"), pid=12345)

    monkeypatch.setattr(c, "readonly_probe", probe)
    monkeypatch.setattr(c.subprocess, "Popen", run)
    monkeypatch.setattr(c.os, "killpg", Mock())
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
    monkeypatch.setattr(
        c, "darwin_runtime_paths", lambda: [Path("/private/var/folders")]
    )
    monkeypatch.setattr(c.os, "killpg", Mock())
    monkeypatch.setattr(c, "WORKTREE", tmp_path)
    monkeypatch.setattr(s, "disk_guard", lambda *a: None)
    monkeypatch.setattr(s, "isolation_state", lambda *a: {"fixture": "unchanged"})
    monkeypatch.setattr(s, "archive_repo", fake_archive)
    monkeypatch.setattr(c, "readonly_probe", lambda *a: None)
    monkeypatch.setattr(c.shutil, "which", lambda _: "sandbox-exec")
    monkeypatch.setattr(
        c.subprocess, "Popen", lambda *a, **k: Mock(returncode=0, pid=12345)
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
    monkeypatch.setattr(
        c, "darwin_runtime_paths", lambda: [Path("/private/var/folders")]
    )
    monkeypatch.setattr(c.os, "killpg", Mock())
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
        c.subprocess, "Popen", lambda *a, **kw: Mock(returncode=1, pid=12345)
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


def test_darwin_paths_are_canonical_and_narrow(monkeypatch):
    run = Mock(
        side_effect=[
            SimpleNamespace(stdout="/var/folders/user/T/\n"),
            SimpleNamespace(stdout="/var/folders/user/C/\n"),
        ]
    )
    monkeypatch.setattr(c.subprocess, "run", run)
    assert c.darwin_runtime_paths() == [
        Path("/var/folders/user/T").resolve(),
        Path("/var/folders/user/C").resolve(),
    ]
    assert [call.args[0][-1] for call in run.call_args_list] == [
        "DARWIN_USER_TEMP_DIR",
        "DARWIN_USER_CACHE_DIR",
    ]
    assert all(call.kwargs["timeout"] == 5 for call in run.call_args_list)


@pytest.mark.parametrize(
    "result",
    [
        subprocess.CalledProcessError(1, "getconf"),
        subprocess.TimeoutExpired("getconf", 5),
        SimpleNamespace(stdout="/\n"),
        SimpleNamespace(stdout="\n"),
    ],
)
def test_darwin_paths_fallback(monkeypatch, result):
    run = (
        Mock(side_effect=result)
        if isinstance(result, Exception)
        else Mock(return_value=result)
    )
    monkeypatch.setattr(c.subprocess, "run", run)
    assert c.darwin_runtime_paths() == [Path("/private/var/folders")]


@pytest.mark.parametrize("timeout", [False, True])
def test_worker_kills_all_groups_even_after_normal_exit(tmp_path, monkeypatch, timeout):
    monkeypatch.setattr(c, "readonly_probe", Mock())
    monkeypatch.setattr(
        c, "darwin_runtime_paths", lambda: [Path("/private/var/folders")]
    )
    proc = Mock(pid=12345, returncode=0)
    if timeout:
        proc.wait.side_effect = [subprocess.TimeoutExpired("worker", 900), -9]

    def launch(*args, **kwargs):
        assert kwargs["start_new_session"] is True
        command = args[0]
        assert command[command.index("--timeout-per-pass") + 1] == "600"
        private = Path(kwargs["env"]["MVE_WO1_PRIVATE_DIR"])
        (private / "capture-chrome.pgid").write_text("12346\n")
        (private / "repeat-chrome.pgid").write_text("12347\n")
        return proc

    monkeypatch.setattr(c.subprocess, "Popen", launch)
    kill = Mock()
    monkeypatch.setattr(c.os, "killpg", kill)
    repos = {"atlas": tmp_path / "atlas", "lab": tmp_path / "lab"}
    args = c.parse_args(["--repeat", "--timeout-per-pass", "600"])
    if timeout:
        with pytest.raises(ValueError, match="wall-clock timeout"):
            c.isolated_capture(args, tmp_path, repos, {})
    else:
        c.isolated_capture(args, tmp_path, repos, {})
    assert {call.args for call in kill.call_args_list} == {
        (12345, signal.SIGKILL),
        (12346, signal.SIGKILL),
        (12347, signal.SIGKILL),
    }
    assert proc.wait.call_args_list[0].kwargs == {"timeout": 900}
    assert proc.wait.call_args_list[1].kwargs == {"timeout": 5}


def test_chrome_group_cleanup_kills_lingering_child(private_runtime):
    """A real Chrome substitute exits, leaving a child holding its stdout pipe."""
    launcher = r.chrome_launcher(private_runtime, "capture", sys.executable)
    proc = subprocess.Popen(
        [
            str(launcher),
            "-c",
            "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print('ready',flush=True)",
        ],
        start_new_session=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        proc.wait(timeout=5)
        assert int((private_runtime / "capture-chrome.pgid").read_text()) == proc.pid
        r.kill_browser_groups(private_runtime)
        # EOF only arrives after the lingering child loses its inherited pipe.
        stdout, _ = proc.communicate(timeout=5)
        assert stdout == "ready\n"
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def test_sandbox_unix_ipc_allowed_inet_denied(tmp_path, private_runtime):
    import shutil

    if not shutil.which("sandbox-exec"):
        pytest.skip("sandbox-exec unavailable")
    # No remote service or internet request: local Unix pair must connect; even
    # binding an IPv4/IPv6 loopback listener must fail with PermissionError.
    code = """
import socket, sys
path = sys.argv[1]
with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as client:
    server.bind(path)
    server.listen(1)
    client.connect(path)
    peer, _ = server.accept()
    peer.close()
for family, addr in [(socket.AF_INET, ('127.0.0.1', 0)), (socket.AF_INET6, ('::1', 0))]:
    for operation in ('bind', 'connect'):
        try:
            with socket.socket(family) as inet:
                getattr(inet, operation)(addr)
        except PermissionError:
            continue
        raise AssertionError('inet was allowed')
"""
    proc = subprocess.run(
        [
            "sandbox-exec",
            "-p",
            c.sandbox_profile(tmp_path, private_runtime),
            sys.executable,
            "-c",
            code,
            str(private_runtime / "test.sock"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if "sandbox_apply: Operation not permitted" in proc.stderr:
        pytest.skip("nested-sandbox-only: sandbox_apply Operation not permitted")
    assert proc.returncode == 0, proc.stderr
