"""Small preflight primitives. No live transport is exposed by this package."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def pin(path):
    """Pin actual file bytes, including dirty by-path dependencies."""
    path = Path(path).resolve()
    if not path.is_file():
        return {"path": str(path), "status": "failed", "reason": "file missing"}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    git = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=10,
    )
    return {
        "path": str(path),
        "status": "pinned",
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
        "git_sha": git.stdout.strip() if git.returncode == 0 else None,
    }


def probe(name, command, cwd, timeout=60, extra_env=None):
    """Capture bounded local execution; socket access is disabled in Python children."""
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        **(extra_env or {}),
    )
    guard = Path(__file__).parent / "guard"
    env["PYTHONPATH"] = str(guard) + os.pathsep + env.get("PYTHONPATH", "")
    for key in ("DEEPSEEK_API_KEY", "TYPESAFE_API_KEY"):
        env.pop(key, None)
    started = time.monotonic()
    base = {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        result = subprocess.run(
            command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        reason = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
        return dict(
            base, status="failed", reason=reason, duration_s=time.monotonic() - started
        )
    return dict(
        base,
        status="ran" if result.returncode == 0 else "failed",
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_s=time.monotonic() - started,
    )


def write_report(output, checks, dependencies):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "mve-preflight-v1",
        "work_packet": "WP-0a",
        "plan_revision": "r5",
        "observation_schema": "oae-mve-observation-v5",
        "checks": checks,
        "live_calls": 0,
        "actual_api_cost_usd": 0,
        "cost_model": {
            "vision_latency_s": None,
            "tokens_per_image": None,
            "human_seconds_per_verdict": None,
            "calls_per_image": 2,
            "cost_formula": "2 * (input_tokens * miss_rate + output_tokens * output_rate) / 1e6",
            "status": "deferred to WP-0b and human session; WP-0a is offline only",
            "aggregate_cap_usd": 20,
            "p0_cap_usd": 2,
            "p1_cap_usd": 8,
        },
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lock = {
        "schema": "mve-deps-v1",
        "files": dependencies,
        "note": "File hashes pin actual bytes; git SHA alone does not exclude dirty edits.",
    }
    (output / "DEPS.lock").write_text(json.dumps(lock, separators=(",", ":")) + "\n")


def publish_lock(source, target):
    """Publish this packet's receipt without replacing other reviewed packet locks."""
    source, target = Path(source), Path(target)
    packet = json.loads(source.read_text())
    lock = (
        json.loads(target.read_text())
        if target.exists()
        else {"schema": "mve-deps-v1", "packets": {}}
    )
    if "packets" not in lock:
        lock = {"schema": "mve-deps-v1", "packets": {"WP-0a": lock}}
    lock["packets"]["WP-0a"] = packet
    target.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
