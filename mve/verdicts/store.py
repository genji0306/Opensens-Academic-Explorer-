"""Cooperating local writers: lock, read current revision, validate, atomic replace."""

from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import tempfile
from mve.record import Record, transition
from mve.validation import require
from mve.verdicts.capture import capture, propose, revise


def dispatch(record, request):
    require(isinstance(request, dict), "request must be an object")
    args = dict(request)
    operation = args.pop("operation", None)
    args.setdefault("at", datetime.now(timezone.utc).isoformat())
    if operation == "edit":
        revision = args.pop("from_revision")
        patch = args.pop("patch")
        nonce = args.pop("request_nonce", None)
        return transition(
            record,
            "edit",
            expected_revision=revision,
            payload={"patch": patch, "request_nonce": nonce},
            **args,
        )
    require(operation in {"capture", "propose", "revise"}, "unknown verdict operation")
    return {"capture": capture, "propose": propose, "revise": revise}[operation](record, **args)


def apply_request(path, request):
    """All writers of this record must use the same sidecar lock protocol."""
    path = Path(path).resolve(strict=True)
    with path.with_name(path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = Record.from_json(path.read_text())
        result = dispatch(record, request)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=path.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(result.to_json() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return result
