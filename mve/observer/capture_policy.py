"""Pinned capture limits shared by WO-1b and WO-6c; no browser probes."""

from contextlib import contextmanager
import math
import os
from pathlib import Path
import plistlib
import signal
import traceback
import time

PAGE_LOAD_SECONDS = 120
POST_LOAD_SECONDS = 150
PASS_OVERHEAD_SECONDS = 60
BATCH_OVERHEAD_SECONDS = 120
MAX_PASS_SECONDS = 2760
MAX_BATCH_SECONDS = 5640


class RendererVersionError(ValueError):
    label = "renderer_version"


class RendererPinError(RendererVersionError):
    label = "renderer_pin"


class PageTimeoutError(ValueError):
    label = "page_timeout"


class HostLoadError(ValueError):
    label = "host_load"


def options(parser):
    parser.add_argument(
        "--renderer-pin", help="named pinned_renderers record in DEPS.lock"
    )
    parser.add_argument("--page-load-timeout", type=int, default=PAGE_LOAD_SECONDS)
    parser.add_argument("--timeout-per-pass", type=int)
    parser.add_argument("--max-load", type=float)


def bounds(args, count):
    if not 1 <= args.page_load_timeout <= PAGE_LOAD_SECONDS:
        raise ValueError("page load timeout must be 1..120 seconds")
    if not 1 <= count <= 10:
        raise ValueError("bounded snapshot count required")
    minimum = (
        count * (args.page_load_timeout + POST_LOAD_SECONDS) + PASS_OVERHEAD_SECONDS
    )
    if args.timeout_per_pass is None:
        args.timeout_per_pass = minimum
    if not minimum <= args.timeout_per_pass <= MAX_PASS_SECONDS:
        raise ValueError("pass timeout outside derived bounds")
    args.overall_timeout = 2 * args.timeout_per_pass + BATCH_OVERHEAD_SECONDS
    if args.max_load is not None and (
        not math.isfinite(args.max_load) or args.max_load < 0
    ):
        raise ValueError("max load must be finite and nonnegative")
    return dict(
        page_load_seconds=args.page_load_timeout,
        snapshot_seconds=args.page_load_timeout + POST_LOAD_SECONDS,
        pass_seconds=args.timeout_per_pass,
        overall_seconds=args.overall_timeout,
    )


def load(maximum=None):
    # Receipt order is 1-minute, 5-minute, 15-minute, with no normalization.
    values = list(os.getloadavg())
    if maximum is not None and values[0] > maximum:
        raise HostLoadError("host_load")
    return values


def browser_version(chrome):
    """Read the installed macOS bundle version without launching Chrome."""
    with (Path(chrome).parent.parent / "Info.plist").open("rb") as stream:
        value = plistlib.load(stream)["CFBundleShortVersionString"]
    return one_version([value])


def one_version(values):
    values = list(values)
    if (
        not values
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != 1
    ):
        raise RendererVersionError("renderer version mismatch or missing")
    return values[0]


@contextmanager
def deadline(seconds):
    """Nest a snapshot deadline inside the remaining pass deadline."""
    began = time.monotonic()
    previous = signal.getsignal(signal.SIGALRM)
    remaining, interval = signal.getitimer(signal.ITIMER_REAL)

    def expired(signum, frame):
        raise PageTimeoutError("snapshot timeout")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(
        signal.ITIMER_REAL, min(seconds, remaining) if remaining else seconds
    )
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if remaining:
            signal.setitimer(
                signal.ITIMER_REAL,
                max(0.000001, remaining - (time.monotonic() - began)),
                interval,
            )


def end_version(receipt, chrome, started):
    try:
        ended = browser_version(chrome) if started else None
    except (OSError, ValueError, KeyError, plistlib.InvalidFileException):
        ended = None
    receipt["browser_version_end"] = ended
    if started != ended:
        receipt["status"] = "renderer_drift"


def write_traceback(out, exc, *, worker=False):
    """Persist only exception type and stack locations, never values or source lines."""
    if out is None or not Path(out).is_dir():
        return
    target = Path(out) / ("worker-traceback.txt" if worker else "traceback.txt")
    if target.exists():
        return
    frames = traceback.extract_tb(exc.__traceback__)
    message = str(exc)
    # An exception can contain source paths, private workspace paths or URLs.
    # Retain its message only when it has no path-shaped absolute component.
    import re

    if (
        worker
        and message
        and not re.search(r"(?<![A-Za-z0-9._-])/(?:[^/\s]+)|[A-Za-z]:[\\/]", message)
    ):
        heading = f"{type(exc).__name__}: {message[:4096]}"
    else:
        heading = type(exc).__name__
    rows = [heading] + [
        f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames
    ]
    raw = ("\n".join(rows) + "\n").encode()[:65536]
    fd = os.open(
        target,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)


def write_worker_refusal(out, exc):
    if out is None or not Path(out).is_dir():
        return
    label = getattr(exc, "label", "internal_error")
    if label not in (
        "page_timeout",
        "renderer_pin",
        "renderer_version",
        "internal_error",
    ):
        label = "internal_error"
    fd = os.open(
        Path(out) / "worker_refusal.json",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(fd, "w") as stream:
        stream.write('{"label":"' + label + '"}\n')


def relay_worker_refusal(out, exc):
    path = Path(out) / "worker_refusal.json"
    if not path.is_file():
        raise exc
    import json

    label = json.loads(path.read_text())["label"]
    if label == "page_timeout":
        raise PageTimeoutError("worker page timeout") from exc
    if label == "renderer_pin":
        raise RendererPinError("worker renderer pin mismatch") from exc
    if label == "renderer_version":
        raise RendererVersionError("worker renderer version mismatch") from exc
    raise exc
