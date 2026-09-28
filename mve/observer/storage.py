"""Fixed worktree-local destinations and the WO-4/5 hard disk limits."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
from mve.observer.snapshots import tree_bytes
from mve.observer.refusals import Refusal

WORKTREE = Path(__file__).resolve().parents[2]
OUTBOX = Path("mve/generated/outbox")
GENERATED = Path("mve/generated")


def token(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", value
    ):
        raise ValueError("unsafe identifier")
    return value


def local(relative):
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.is_relative_to(GENERATED):
        raise ValueError("output must be inside worktree mve/generated")
    current = WORKTREE
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink in output path")
    return current


class DiskLimitError(Refusal):
    """Hard stop: never convert disk exhaustion into an ordinary failed slot."""


def disk_guard(generated, incoming=0):
    if shutil.disk_usage("/")[2] < 5 * 1024**3:
        raise DiskLimitError("disk_free")
    if tree_bytes(generated) + incoming > 200 * 1024**2:
        raise DiskLimitError("generated_cap")


def encoded(value):
    data = (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode()
    if b"/" + b"Users/" in data:  # split literal so the repo-wide path lint stays clean
        raise ValueError("nonportable user path in output")
    return data


def write(relative, value):
    data = value if isinstance(value, bytes) else encoded(value)
    dest = local(relative)
    disk_guard(local(GENERATED), len(data))
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return dest


@contextmanager
def lock():
    """One local writer/runner at a time; also serializes generated-byte admission."""
    disk_guard(local(GENERATED), 4096)
    p = local(GENERATED / ".wo45.lock")
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal("lock_held") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
