"""WO-1 command: bounded git archives; offline, write-confined native capture.

Run from this worktree: python3 -m mve.observer.snapshot_capture --prepare-only
Omit --prepare-only for capture (requires macOS sandbox-exec and system Chrome).
No build/publish command or network listener is used. All browser requests are
fulfilled from the archive by Playwright; the OS denies inet access (Unix IPC allowed).
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import site
import subprocess
import sys
import tempfile

from mve.observer import snapshots as s
from mve.observer import snapshot_render as render

WORKTREE = Path(__file__).resolve().parents[2]
DEFAULT_REPOS = {
    "atlas": "~/Developer/Opensens/worktrees/oae-rh-atlas-p0-20260924",
    "lab": "~/Developer/Opensens/worktrees/zeta-explorer-main",
}
PASS_TIMEOUT_SECONDS = 300
CAPTURE_TIMEOUT_SECONDS = 900


def darwin_runtime_paths():
    """Chrome uses confstr paths for singleton sockets, ignoring TMPDIR."""
    paths = []
    for key in ("DARWIN_USER_TEMP_DIR", "DARWIN_USER_CACHE_DIR"):
        try:
            result = subprocess.run(
                ["/usr/bin/getconf", key],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            path = Path(result.stdout.strip()).resolve()
            if not path.is_relative_to("/private/var/folders") or path == Path(
                "/private/var/folders"
            ):
                raise ValueError("invalid Darwin runtime path")
        except (OSError, subprocess.SubprocessError, ValueError):
            # Authorized compatibility fallback when confstr is unavailable.
            return [Path("/private/var/folders")]
        paths.append(path)
    return paths


def output_path(worktree, value):
    p = s.inside(worktree, value)
    if not p.is_relative_to(Path(worktree) / "mve/generated"):
        raise ValueError("outputs must be under mve/generated")
    return p


def private_paths(private):
    private = Path(private).resolve()
    if private.parent != Path("/private/tmp") or not private.name.startswith("mvewo1-"):
        raise ValueError(
            "browser runtime must be a private /private/tmp/mvewo1-* directory"
        )
    home, tmp = private / "h", private / "t"
    # Reserve 64 bytes for Chromium's scoped directory and SingletonSocket name.
    # Keep the full encoded Unix socket path strictly below 100 bytes.
    if len(os.fsencode(tmp)) + 1 + 64 >= 100:
        raise ValueError("browser runtime exceeds socket-path length bound")
    return home, tmp


def sandbox_profile(out, private):
    # Unix IPC is needed for Chrome's singleton socket; inet stays denied.
    private_paths(private)
    output = json.dumps(str(Path(out).resolve()))
    runtime = json.dumps(str(Path(private).resolve()))
    darwin = " ".join(f"(subpath {json.dumps(str(p))})" for p in darwin_runtime_paths())
    return (
        "(version 1)\n(allow default)\n(deny network*)\n"
        "(allow network* (local unix-socket))\n"
        "(allow network* (remote unix-socket))\n(deny file-write*)\n"
        f"(allow file-write* (subpath {output}) (subpath {runtime}) {darwin})\n"
        '(allow file-write-data (literal "/dev/null"))\n'
    )


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default="mve/generated/wo1-capture")
    ap.add_argument("--atlas", default=DEFAULT_REPOS["atlas"])
    ap.add_argument("--lab", default=DEFAULT_REPOS["lab"])
    ap.add_argument(
        "--chrome",
        default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument(
        "--timeout-per-pass",
        type=int,
        default=PASS_TIMEOUT_SECONDS,
        help="wall-clock seconds per capture pass (default: 300; overall cap: 900)",
    )
    ap.add_argument(
        "--repeat",
        action="store_true",
        help="capture twice; require exact data bytes and declared PNG tolerance",
    )
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if not 0 < args.timeout_per_pass <= CAPTURE_TIMEOUT_SECONDS:
        ap.error("--timeout-per-pass must be between 1 and 900 seconds")
    return args


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def check_sources(stage):
    dist = stage / "atlas/vendor/zeta-explorer/dist"
    for name in render.PATCHES:
        render.transform(name, (dist / name).read_text())
    index = s.read_index(
        stage / "atlas/data/riemann/evidence_atlas/inputs/lab_snapshots.json",
        stage / "atlas",
    )
    return {
        "commits": s.COMMITS,
        "index": index,
        "archive_trees": {name: s.tree_listing(stage / name) for name in s.COMMITS},
        "capture_script_sha256": s.sha256(stage / "lab/scripts/astra_p34_capture.py"),
        "source_patch_validation": "passed",
        "planned_pairs": 4,
        "independent_discovery_blocks": 0,
        "independent_null_blocks": 0,
        "shortfall": "10 real and 10 null disjoint discovery blocks remain unallocated; four development pairs only.",
    }


def readonly_probe(profile, repo_files):
    """Open for writing without O_TRUNC, O_CREAT or writing a byte; must be denied.

    A protection defect cannot modify a source file even if the open succeeds.
    """
    code = (
        "import os,sys\n"
        "for p in sys.argv[1:]:\n"
        " try: f=os.open(p,os.O_WRONLY)\n"
        " except PermissionError: continue\n"
        " else: os.close(f); sys.exit(2)\n"
    )
    result = subprocess.run(
        [
            "sandbox-exec",
            "-p",
            profile,
            sys.executable,
            "-c",
            code,
            *map(str, repo_files),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode:
        raise ValueError(
            "OS isolation probe unavailable or failed (nested sandbox may deny sandbox_apply)"
        )


def capture_pass(args, dist, out, private):
    def expired(signum, frame):
        raise ValueError(
            f"{out.name} pass exceeded {args.timeout_per_pass}-second wall-clock timeout"
        )

    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, args.timeout_per_pass)
        return render.run_browser(
            dist, out, args.chrome, shutil.which("tesseract"), private
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def verify_repeat(first, second, first_root, second_root):
    """Compare repeats without replacing the first pass's artifacts or identities."""
    a = {e["snapshot_id"]: e for e in first["snapshots"]}
    b = {e["snapshot_id"]: e for e in second["snapshots"]}
    if (
        not a
        or a.keys() != b.keys()
        or len(a) != len(first["snapshots"])
        or len(b) != len(second["snapshots"])
    ):
        raise ValueError("repeat capture snapshot set mismatch")
    rows = []
    for ident, entry in a.items():
        other = b[ident]
        if any(
            e["png_repeat_tolerance"] != s.PNG_REPEAT_TOLERANCE for e in (entry, other)
        ):
            raise ValueError("repeat capture tolerance mismatch")
        data_equal = (
            s.inside(first_root, entry["data_ref"]["path"]).read_bytes()
            == s.inside(second_root, other["data_ref"]["path"]).read_bytes()
        )
        images = {}
        for kind in ("png_full", "png_blinded"):
            first_path = s.inside(first_root, entry[kind]["path"])
            second_path = s.inside(second_root, other[kind]["path"])
            images[kind] = {
                "first_sha256": s.sha256(first_path),
                "repeat_sha256": s.sha256(second_path),
                **s.compare_png(first_path, second_path),
            }
        rows.append(
            {
                "snapshot_id": ident,
                "first_snapshot_sha256": entry["snapshot_sha256"],
                "data_bytes_equal": data_equal,
                "images": images,
                "passed": data_equal
                and all(image["passed"] for image in images.values()),
            }
        )
    return {
        "png_repeat_tolerance": s.PNG_REPEAT_TOLERANCE,
        "identity_pass": "first",
        "snapshots": rows,
        "passed": all(row["passed"] for row in rows),
    }


def run_worker(args, out):
    # Internal worker is deliberately unusable unless the parent explicitly seals
    # its environment; it still only writes to validated generated output paths.
    if os.environ.get("MVE_WO1_SANDBOX_WORKER") != "1":
        raise ValueError("worker requires sandboxed parent")
    private = Path(os.environ["MVE_WO1_PRIVATE_DIR"])
    private_paths(private)
    dist = out / "stage/atlas/vendor/zeta-explorer/dist"
    first = out / "capture"
    first.mkdir()
    a = capture_pass(args, dist, first, private)
    if args.repeat:
        second = out / "repeat"
        second.mkdir()
        b = capture_pass(args, dist, second, private)

        report = verify_repeat(a, b, first, second)
        write_json(out / "repeat-verification.json", report)
        if not report["passed"]:
            raise ValueError("repeat capture data bytes/PNG tolerance mismatch")
        shutil.rmtree(second)
    return 0


def isolated_capture(args, out, repos, receipt):
    # TemporaryDirectory uses mkdtemp (mode 0700). Cleanup also covers probe and
    # launch failures, before the caller attempts its source-tree audit.
    with tempfile.TemporaryDirectory(prefix="mvewo1-", dir="/private/tmp") as root:
        private = Path(root)
        home, tmp = private_paths(private)
        home.mkdir()
        tmp.mkdir()
        profile = sandbox_profile(out, private)
        readonly_probe(
            profile,
            [repos["atlas"] / s.PATHS["atlas"][2], repos["lab"] / "dist/index.html"],
        )
        receipt["outside_write_probe"] = "denied_for_both_repos"
        command = [
            "sandbox-exec",
            "-p",
            profile,
            sys.executable,
            "-m",
            "mve.observer.snapshot_capture",
            "--worker",
            "--output",
            args.output,
            "--chrome",
            args.chrome,
            "--timeout-per-pass",
            str(args.timeout_per_pass),
        ]
        if args.repeat:
            command.append("--repeat")
        env = {
            **os.environ,
            "MVE_WO1_SANDBOX_WORKER": "1",
            "MVE_WO1_PRIVATE_DIR": str(private),
            "PYTHONDONTWRITEBYTECODE": "1",
            # Keep the parent's installed packages visible with a private HOME.
            # The sandbox still denies writes to the real user base.
            "PYTHONUSERBASE": site.USER_BASE,
            "HOME": str(home),
            "TMPDIR": str(tmp),
        }
        # Logs stay private; do not echo installed paths or inherited values.
        with (out / "browser.log").open("w") as log:
            result = subprocess.Popen(
                command,
                cwd=WORKTREE,
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                result.wait(timeout=CAPTURE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                raise ValueError(
                    "isolated capture exceeded 900-second overall wall-clock timeout"
                ) from exc
            finally:
                # Stop worker/driver before collecting separately detached Chrome
                # groups. Always kill, even after the group leader has exited:
                # Chrome's updater may still be running in that group.
                try:
                    os.killpg(result.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    render.kill_browser_groups(private)
                finally:
                    result.wait(timeout=5)
        if result.returncode:
            raise ValueError("isolated capture failed; inspect private browser.log")


def main(argv=None):
    args = parse_args(argv)
    out = output_path(WORKTREE, args.output)
    if args.worker:
        return run_worker(args, out)
    generated = WORKTREE / "mve/generated"
    s.disk_guard(generated, 200 * 1024**2)
    if out.exists():
        raise ValueError("output already exists; choose a new output directory")
    repos = {
        name: Path(getattr(args, name)).expanduser().resolve() for name in s.COMMITS
    }
    if any(repo.is_relative_to(WORKTREE) for repo in repos.values()):
        raise ValueError("source repos must be separate from capture worktree")
    before = s.isolation_state(repos)
    out.mkdir(parents=True)
    write_json(out / "isolation-before.json", before)
    stage = out / "stage"
    receipt = {"mode": "offline_only", "hosted_calls": 0, "capture": "not_run"}
    archive_before = None
    try:
        for name, repo in repos.items():
            s.archive_repo(repo, name, stage / name, generated)
        sources = check_sources(stage)
        write_json(out / "source-receipt.json", sources)
        archive_before = s.tree_listing(stage)
        if args.prepare_only:
            receipt["capture"] = "prepared_only"
        else:
            if not shutil.which("sandbox-exec"):
                raise ValueError(
                    "OS write/network isolation unavailable; capture refused"
                )
            isolated_capture(args, out, repos, receipt)
            receipt["capture"] = "captured"
    except Exception as exc:
        receipt["capture"] = "failed"
        receipt["failure_type"] = type(exc).__name__
        raise
    finally:
        after = s.isolation_state(repos)
        write_json(out / "isolation-after.json", after)
        receipt["source_repos_unchanged"] = before == after
        receipt["isolation_scope"] = (
            "All files including ignored under both allowed source pathspec sets; full git status --ignored of both repos. Not a hash audit of unrelated repo directories."
        )
        if archive_before is not None:
            receipt["archive_unchanged"] = archive_before == s.tree_listing(stage)
        # Delete only this run's fresh archive, never a caller's existing output.
        if stage.exists():
            shutil.rmtree(stage)
        receipt["generated_bytes"] = s.tree_bytes(generated)
        write_json(out / "receipt.json", receipt)
        if (
            not receipt["source_repos_unchanged"]
            or receipt.get("archive_unchanged") is False
        ):
            raise ValueError("isolation changed; no passing capture receipt")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
