"""Pinned, network-denied Lean subprocess; success attests statement type only."""

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
from mve.formalizer.ir import build_ir
from mve.formalizer.emitter import emit
from mve.identity import digest
from mve.record import transition
from mve.predicates import canonical_proposition


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_project(project):
    project = Path(project)
    try:
        lock = json.loads((project / "lock.json").read_text())
        for name, expected in lock["project_files"].items():
            if sha((project / name).read_bytes()) != expected:
                raise ValueError("project pin mismatch")
        binary = lean_binary_path(lock)
        if sha(binary.read_bytes()) != lock["lean_binary_sha256"]:
            raise ValueError("Lean binary pin mismatch")
        for package in lock["packages"]:
            verify_package(project, package)
        if not Path("/usr/bin/sandbox-exec").exists():
            raise ValueError("offline subprocess sandbox unavailable")
    except (
        OSError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        raise ValueError("missing or invalid pinned Lean project") from exc
    return lock


def compile_source(source, project, output, *, timeout=60):
    if type(timeout) not in (int, float) or not 0 < timeout <= 120:
        raise ValueError("compile timeout must be 0..120 seconds")
    lock = verify_project(project)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    statement = output / (sha(source.encode()) + ".lean")
    statement.write_text(source)
    env = lean_environment(project, lock)
    command = [
        "/usr/bin/sandbox-exec",
        "-p",
        "(version 1) (allow default) (deny network*)",
        str(lean_binary_path(lock)),
        os.path.relpath(statement.resolve(), Path(project).resolve()),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        log = result.stdout + result.stderr
        ok = result.returncode == 0
        outcome = "typechecked" if ok else "error"
    except subprocess.TimeoutExpired:
        log = "Lean statement typecheck timed out\n"
        ok = False
        outcome = "timeout"
    return save_receipt(source, project, output, lock, log, ok, outcome)


def save_receipt(source, project, output, lock, log, ok, outcome):
    log_path = output / (sha(log.encode()) + ".log")
    log_path.write_text(log)
    receipt = {
        "ok": ok,
        "outcome": outcome,
        "statement_sha256": sha(source.encode()),
        "log_sha256": sha(log.encode()),
        "toolchain": lock["lean_toolchain"],
        "lock_sha256": sha((Path(project) / "lock.json").read_bytes()),
        "proof_checked": False,
        "hosted_calls": 0,
        "statement_path": sha(source.encode()) + ".lean",
        "log_path": log_path.name,
    }
    (output / (sha(source.encode()) + ".receipt.json")).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    return receipt


def formal_payload(ir, source):
    mapping = {b["name"]: b["entity"] for b in ir["binders"]}
    if any(value is None for value in mapping.values()):
        raise ValueError("formal record requires bound point entities")
    nodes = [*ir["premises"]] + ([ir["goal"]] if ir["goal"] else [])
    propositions = [
        {
            "id": f"prop_{i}",
            "role": n["role"],
            "proposition": canonical_proposition(n["proposition"], mapping),
            "support": "goal_source" if n["role"] == "goal" else "problem_text",
            "depends_on": [n["evidence"]],
        }
        for i, n in enumerate(nodes, 1)
    ]
    return {
        "status": "emitted",
        "target": "mathlib",
        "ir_sha256": digest(ir),
        "statement_sha256": sha(source.encode()),
        "propositions": propositions,
        "depends_on": [n["evidence"] for n in nodes],
    }


def typecheck_record(record, project, output, *, timeout=60, at=None):
    from datetime import datetime, timezone

    at = at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lock = verify_project(project)
    lock_sha = sha((Path(project) / "lock.json").read_bytes())
    ir = build_ir(record)
    source = emit(ir)
    formal = formal_payload(ir, source)
    emitted = transition(
        record,
        "formalize",
        actor="A4",
        expected_revision=record.to_dict()["revision"],
        at=at,
        payload={
            "formal": formal,
            "lean_lock_sha": lock_sha,
            "lean_toolchain": lock["lean_toolchain"],
        },
    )
    receipt = compile_source(source, project, output, timeout=timeout)
    (Path(output) / (digest(ir) + ".ir.json")).write_text(
        json.dumps(ir, sort_keys=True, separators=(",", ":"))
    )
    if not receipt["ok"]:
        return emitted, receipt
    formal.update(
        status="typechecked",
        typecheck={
            "id": "tc_1",
            "ok": True,
            "toolchain": lock["lean_toolchain"],
            "log_sha256": receipt["log_sha256"],
            "depends_on": [p["id"] for p in formal["propositions"]],
        },
    )
    checked = transition(
        emitted,
        "formalize",
        actor="A4",
        expected_revision=emitted.to_dict()["revision"],
        at=at,
        payload={
            "formal": formal,
            "lean_lock_sha": lock_sha,
            "lean_toolchain": lock["lean_toolchain"],
        },
    )
    return checked, receipt


def project_path(project, relative):
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("lock paths must be project-relative")
    return (Path(project) / relative).resolve()


def lean_available(project):
    return lean_unavailable_reason(project) is None


def lean_unavailable_reason(project):
    try:
        lock = json.loads((Path(project) / "lock.json").read_text())
        binary = lean_binary_path(lock)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            return "local Lean binary missing; set ELAN_HOME for the pinned toolchain"
        for package in lock["packages"]:
            path = package_path(project, package)
            if not (path / "lake-manifest.json").is_file() or (
                package["name"] == "mathlib"
                and not (path / ".lake/build/lib/lean").is_dir()
            ):
                return "local package cache missing; set MVE_LEAN_PACKAGES"
        if not Path("/usr/bin/sandbox-exec").is_file():
            return "network-denying sandbox unavailable"
    except (OSError, ValueError, KeyError):
        return "missing or invalid Lean lock configuration"
    return None


def lean_environment(project, lock):
    binary = lean_binary_path(lock)
    paths = [
        str(package_path(project, p) / ".lake/build/lib/lean") for p in lock["packages"]
    ]
    return {
        "PATH": str(binary.parent) + os.pathsep + os.defpath,
        "HOME": str(Path.home()),
        "LEAN_PATH": os.pathsep.join(paths),
    }


def lean_binary_path(lock):
    toolchain = lock["lean_toolchain"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", toolchain):
        raise ValueError("invalid pinned Lean toolchain name")
    folder = toolchain.replace("/", "--").replace(":", "---")
    root = Path(os.environ.get("ELAN_HOME", str(Path.home() / ".elan"))).expanduser()
    return project_path(root / "toolchains" / folder, lock["lean_binary"])


def package_path(project, package):
    root = Path(
        os.environ.get("MVE_LEAN_PACKAGES", str(Path(project) / ".lake/packages"))
    ).expanduser()
    return project_path(root, package["path"])


def verify_package(project, package):
    path = package_path(project, package)
    if sha((path / "lake-manifest.json").read_bytes()) != package["manifest_sha256"]:
        raise ValueError("dependency manifest pin mismatch")
    head = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.run(
        ["git", "-C", str(path), "diff", "--quiet", "HEAD", "--"], capture_output=True
    )
    if head != package["rev"] or dirty.returncode:
        raise ValueError("dependency pin mismatch")
