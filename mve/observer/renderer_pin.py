"""Operator-selected macOS renderer pin; no bundle paths are stored in the lock."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from mve.observer import capture_policy as policy

LOCK = Path(__file__).resolve().parents[1] / "DEPS.lock"


def record(name):
    return json.loads(LOCK.read_text())["pinned_renderers"][name]


def framework_hash(root):
    """Hash sorted per-file shasum lines, preserving spaces in filenames.

    Do not follow symlinks, just as find without -L does not. The literal xargs
    pipeline splits Chrome filenames; use the space-safe command in the handoff.
    """
    files = []
    for directory, _, names in os.walk(root):
        for name in names:
            path = Path(directory) / name
            if not path.is_symlink() and path.is_file():
                rel = "./" + path.relative_to(root).as_posix()
                if "\n" in rel or "\\" in rel:
                    raise policy.RendererVersionError("ambiguous framework filename")
                files.append((rel, path))
    if not files:
        raise policy.RendererVersionError("empty framework")
    result = hashlib.sha256()
    for rel, path in sorted(files):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        result.update(f"{digest}  {rel}\n".encode())
    return result.hexdigest()


def preflight(chrome, name):
    """Check bytes and a bounded native --version probe before evidence writes.

    A native operator runs this. Builder tests mock subprocess.run. Legacy
    unpinned runs retain the historical plist-only check.
    """
    if name is None:
        return policy.browser_version(chrome)
    try:
        pin = record(name)
        expected = pin["browser_version"]
        if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", expected):
            raise policy.RendererVersionError("invalid version pin")
        contents = Path(chrome).parent.parent
        versions = contents / "Frameworks/Google Chrome Framework.framework/Versions"
        tree = versions / expected
        if tree.is_symlink() or (versions / "Current").resolve(
            strict=True
        ) != tree.resolve(strict=True):
            raise policy.RendererVersionError("framework selection mismatch")
        policy.one_version([expected, policy.browser_version(chrome)])
        if framework_hash(tree) != pin["framework_tree_sha256"]:
            raise policy.RendererVersionError("framework digest mismatch")
        result = subprocess.run(
            [str(chrome), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        match = re.fullmatch(r"Google Chrome (\d+\.\d+\.\d+\.\d+)\s*", result.stdout)
        return policy.one_version([expected, match.group(1) if match else None])
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        raise policy.RendererVersionError("pinned renderer preflight failed") from exc
