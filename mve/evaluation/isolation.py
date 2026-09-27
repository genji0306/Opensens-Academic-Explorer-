"""Offline macOS worker barrier for declared private gold roots.

This denies access to specified gold locations, not all user files. Workers receive
only staged public data; callers must inventory every gold location before launching.
"""

import json
from pathlib import Path
import subprocess
import sys


class IsolationError(ValueError):
    pass


def public_packet(data, *, track, task):
    if track not in {"appearance_only", "annotated_problem"} or task not in {
        "appearance",
        "annotation_reading",
        "problem_understanding",
    }:
        raise IsolationError("declared schema-v5 track and task required")
    allowed = {"image", "labels", "stated_givens", "problem_text"}
    if not isinstance(data, dict) or set(data) - allowed or "image" not in data:
        raise IsolationError("only allowlisted public fields accepted")
    if not isinstance(data["image"], str) or not data["image"]:
        raise IsolationError("relative image filename required")
    path = Path(data["image"])
    if path.is_absolute() or ".." in path.parts:
        raise IsolationError("image must be inside staged public directory")
    if track == "appearance_only" and (
        set(data) & {"stated_givens", "problem_text"} or task != "appearance"
    ):
        raise IsolationError("appearance-only input cannot include textual givens")
    for key in ("labels", "stated_givens"):
        if key in data and (
            not isinstance(data[key], list)
            or any(not isinstance(x, str) for x in data[key])
        ):
            raise IsolationError("public labels and givens must be string lists")
    if "problem_text" in data and not isinstance(data["problem_text"], str):
        raise IsolationError("problem text must be a string")
    return json.loads(json.dumps({**data, "track": track, "eval_task": task}))


def _paths(script, public_dir, private_roots):
    public = Path(public_dir).resolve(strict=True)
    worker = Path(script).resolve(strict=True)
    private = [Path(p).resolve() for p in private_roots]
    if (
        not private
        or not public.is_dir()
        or not worker.is_file()
        or not worker.is_relative_to(public)
    ):
        raise IsolationError(
            "public script and nonempty private-root inventory required"
        )
    if any(
        root.is_relative_to(public) or public.is_relative_to(root) for root in private
    ):
        raise IsolationError("public and private roots must be disjoint")
    if any(
        p.is_symlink() or (p.is_file() and p.stat().st_nlink > 1)
        for p in public.rglob("*")
    ):
        raise IsolationError("stage copies, never links, into public input")
    if any(
        not str(p).isascii() or any(ord(c) < 32 for c in str(p))
        for p in [public, worker, *private]
    ):
        raise IsolationError("sandbox paths must be printable ASCII")
    return worker, public, private


def run_offline(script, *, public_dir, private_roots, args=(), timeout=10):
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise IsolationError("tested macOS sandbox required; no unguarded fallback")
    worker, public, private = _paths(script, public_dir, private_roots)
    denied = " ".join(f"(subpath {json.dumps(str(root))})" for root in private)
    profile = f"(version 1)(allow default)(deny network*)(deny file-read* {denied})(deny file-write* {denied})"
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(public),
        "TMPDIR": str(public),
        "LANG": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # -I excludes user site/PYTHONPATH; no parent secrets or descriptors are inherited.
    command = [
        "/usr/bin/sandbox-exec",
        "-p",
        profile,
        str(Path(sys.executable).resolve()),
        "-I",
        "-B",
        str(worker),
        *args,
    ]
    try:
        return subprocess.run(
            command,
            cwd=public,
            env=environment,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IsolationError("isolated worker launch failed or timed out") from exc
