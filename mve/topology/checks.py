"""Named optional operations and a certificate only about the decoded record."""

from mve.topology.model import successor, fail


def snappy_checks(diagram):
    # No import-time probe or installation. This packet has no locally pinned SnapPy.
    operations = {
        "construction": "snappy.Link(pd)",
        "identification": "Link.exterior().identify()",
        "invariant": "Link.jones_polynomial()",
    }
    return {
        key: {
            "operation": op,
            "status": "unavailable",
            "value": None,
            "reason": "SnapPy not installed or pinned in WP-10; not executed",
            "meaning": "candidate identification, not truth"
            if key == "identification"
            else "invariant consistency, not transcript verification"
            if key == "invariant"
            else "construction validity, not picture transcription",
        }
        for key, op in operations.items()
    }


def certificate(diagram):
    """Emit a closed finite orbit theorem, with strand successors read from PD."""
    succ = successor(diagram)
    start = min(succ)
    orbit, current = [], start
    while current not in orbit:
        orbit.append(current)
        current = succ[current]
    if current != start or set(orbit) != set(succ):
        fail("traversal", "one-component certificate requires a single successor orbit")
    cases = "\n".join(f"  | {a} => {b}" for a, b in sorted(succ.items()))
    arcs = ", ".join(map(str, orbit))
    return (
        "-- Certificate of the decoded PD only; no image or knot-type assertion.\n"
        "namespace MVETopology\n"
        f"def successor : Nat → Nat\n{cases}\n  | _ => 0\n"
        "def walk : Nat → Nat → Nat\n"
        "  | 0, a => a\n  | n+1, a => successor (walk n a)\n"
        "theorem one_component :\n"
        f"    (List.range {len(orbit)}).map (fun i => walk i {start}) = [{arcs}] ∧\n"
        f"    walk {len(orbit)} {start} = {start} := by decide\n"
        "end MVETopology\n"
    )


def check_certificate(diagram):
    """Check generated core Lean with the existing pin; no user Lean or build tool."""
    import json
    import os
    from pathlib import Path
    import subprocess
    from mve.formalizer.runtime import lean_binary_path, sha

    source = certificate(diagram)
    lock_path = Path(__file__).resolve().parents[1] / "lean/lock.json"
    lock = json.loads(lock_path.read_text())
    binary = lean_binary_path(lock)
    receipt = {
        "scope": "decoded_record_only",
        "statement_sha256": sha(source.encode()),
        "toolchain": lock["lean_toolchain"],
        "binary_sha256": lock["lean_binary_sha256"],
        "axioms": None,
        "status": "unavailable",
        "hosted_calls": 0,
    }
    if not binary.is_file() or sha(binary.read_bytes()) != lock["lean_binary_sha256"]:
        return {**receipt, "reason": "local Lean binary absent or pin mismatch"}
    try:
        result = subprocess.run(
            [str(binary), "--stdin"],
            input=source + "\n#print axioms MVETopology.one_component\n",
            text=True,
            capture_output=True,
            timeout=30,
            env={"PATH": os.defpath},
            cwd=lock_path.parent,
        )
    except subprocess.TimeoutExpired:
        return {
            **receipt,
            "status": "timeout",
            "reason": "core Lean exceeded 30 seconds",
        }
    log = result.stdout + result.stderr
    checked = result.returncode == 0 and "does not depend on any axioms" in log
    return {
        **receipt,
        "status": "kernel_checked" if checked else "error",
        "axioms": [] if checked else None,
        "log_sha256": sha(log.encode()),
        "log": log,
    }
