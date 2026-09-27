"""WO-1 command: bounded git archives; offline, write-confined native capture.

Run from this worktree: python3 -m mve.observer.snapshot_capture --prepare-only
Omit --prepare-only for capture (requires macOS sandbox-exec and system Chrome).
No build/publish command or network listener is used. All browser requests are
fulfilled from the archive by Playwright; the OS also denies network access.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from mve.observer import snapshots as s
from mve.observer import snapshot_render as render

WORKTREE = Path(__file__).resolve().parents[2]
DEFAULT_REPOS = {
    "atlas": "~/Developer/Opensens/worktrees/oae-rh-atlas-p0-20260924",
    "lab": "~/Developer/Opensens/worktrees/zeta-explorer-main",
}


def output_path(worktree, value):
    p = s.inside(worktree, value)
    if not p.is_relative_to(Path(worktree) / "mve/generated"):
        raise ValueError("outputs must be under mve/generated")
    return p


def sandbox_profile(worktree):
    # deny-default for writes and network; allow ordinary read/process/Mach APIs
    # needed by installed Chrome. No /tmp write exception or external HOME.
    path = json.dumps(str(Path(worktree).resolve()))
    return (
        "(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n"
        f"(allow file-write* (subpath {path}))\n"
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
        "--repeat",
        action="store_true",
        help="capture twice and compare all PNG/data hashes",
    )
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return ap.parse_args(argv)


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
    )
    if result.returncode:
        raise ValueError(
            "OS isolation probe unavailable or failed (nested sandbox may deny sandbox_apply)"
        )


def run_worker(args, out):
    # Internal worker is deliberately unusable unless the parent explicitly seals
    # its environment; it still only writes to validated generated output paths.
    if os.environ.get("MVE_WO1_SANDBOX_WORKER") != "1":
        raise ValueError("worker requires sandboxed parent")
    dist = out / "stage/atlas/vendor/zeta-explorer/dist"
    first = out / "capture"
    first.mkdir()
    a = render.run_browser(dist, first, args.chrome, shutil.which("tesseract"))
    if args.repeat:
        second = out / "repeat"
        second.mkdir()
        b = render.run_browser(dist, second, args.chrome, shutil.which("tesseract"))

        def hashes(manifest):
            return [
                (
                    e["snapshot_id"],
                    *[e[k]["sha256"] for k in ("png_full", "png_blinded", "data_ref")],
                )
                for e in manifest["snapshots"]
            ]

        if hashes(a) != hashes(b):
            raise ValueError("repeat capture PNG/data hash mismatch")
        write_json(
            out / "repeat-verification.json",
            {"all_hashes_equal": True, "snapshots": len(a["snapshots"])},
        )
        shutil.rmtree(second)
    return 0


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
            profile = sandbox_profile(WORKTREE)
            readonly_probe(
                profile,
                [
                    repos["atlas"] / s.PATHS["atlas"][2],
                    repos["lab"] / "dist/index.html",
                ],
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
            ]
            if args.repeat:
                command.append("--repeat")
            env = {
                **os.environ,
                "MVE_WO1_SANDBOX_WORKER": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "TMPDIR": str(out),
            }
            # Logs stay private; do not echo installed paths or inherited values.
            with (out / "browser.log").open("w") as log:
                result = subprocess.run(
                    command, cwd=WORKTREE, env=env, stdout=log, stderr=log
                )
            if result.returncode:
                raise ValueError("isolated capture failed; inspect private browser.log")
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
        # Delete only this run's fresh archive/profile dirs, never a caller's existing output.
        if stage.exists():
            shutil.rmtree(stage)
        for folder in (out / "capture/browser-profile", out / "repeat/browser-profile"):
            if folder.exists():
                shutil.rmtree(folder)
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
