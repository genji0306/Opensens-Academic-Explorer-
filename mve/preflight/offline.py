"""Run the WP-0a offline probes and persist explicit failures for missing prerequisites."""

import argparse
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

from mve.preflight.core import pin, probe, write_report, publish_lock

from mve.preflight.config import PATHS


def dependencies():
    paths = [
        PATHS["vision"] / "scripts" / name
        for name in ("rh_deepseek_vision_cell.py", "rh_deepseek_worker_runner.py")
    ]
    paths += list((PATHS["vision"] / "riemann/research/deepseek").glob("*.py"))
    paths += list((PATHS["jev"] / "rhjev").rglob("*.py"))
    paths += list((PATHS["jev"] / "tests").rglob("*.py"))
    paths += list((PATHS["root"] / "mve/preflight").rglob("*.py"))
    paths += [
        PATHS["root"] / "docs/mve/MVE_PLAN.md",
        PATHS["root"] / "schemas/mve_observation_record.json",
    ]
    paths += list((PATHS["base"] / "rh-visual-fields/rhvf").rglob("*.py"))
    paths += list((PATHS["atlas"] / "rh_evidence").rglob("*.py"))
    paths += [
        PATHS["base"] / "models/openjev" / name
        for name in ("model_fp16.onnx", "tokenizer.json", "calibrator.json")
    ]
    paths += [
        PATHS["lean"] / name
        for name in ("lean-toolchain", "lakefile.lean", "lake-manifest.json")
    ]
    paths += [
        PATHS["atlas"] / "data/riemann/evidence_atlas/schema/result.schema.json",
        PATHS["base"] / "worktrees/zeta-explorer-main/dist/index.html",
        PATHS["base"] / "worktrees/zeta-explorer-main/dist/geometry.js",
        PATHS["base"]
        / "runtimes/qwen-local-worker/com.opensens.qwen-local-worker.plist",
        PATHS["codex"],
    ]
    return [pin(path) for path in sorted(set(paths))]


def local_checks():
    checks = []
    checks.append(
        probe(
            "vision_and_runner_contract",
            [
                sys.executable,
                str(PATHS["root"] / "mve/preflight/vision_contract.py"),
                str(PATHS["vision"] / "scripts"),
            ],
            PATHS["root"],
        )
    )
    checks.append(
        probe(
            "rhjev_tests",
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            PATHS["jev"],
            timeout=120,
        )
    )
    checks.append(
        probe(
            "openjev_fixture",
            [
                str(PATHS["openjev_python"]),
                str(PATHS["root"] / "mve/preflight/openjev_fixture.py"),
                str(PATHS["jev"]),
            ],
            PATHS["root"],
            timeout=120,
        )
    )
    checks.append(
        probe(
            "newclid_import",
            [sys.executable, "-c", "import newclid; print(newclid.__file__)"],
            PATHS["root"],
        )
    )
    checks.append(atlas_check())
    checks.append(probe("codex_cli", [str(PATHS["codex"]), "--version"], PATHS["root"]))
    checks.append(lean_check())
    return checks


def atlas_check():
    return probe(
        "atlas_ingest_contract",
        [
            sys.executable,
            "-c",
            "import inspect; from rh_evidence.adapters.result_bundle import validate_bundle; "
            "from pathlib import Path; print(inspect.signature(validate_bundle)); "
            'print(validate_bundle({}, schema_path=Path("data/riemann/evidence_atlas/schema/result.schema.json"), '
            "project_root=Path.cwd()))",
        ],
        PATHS["atlas"],
    )


def lean_check():
    toolchain = PATHS["lean_binary"]
    return probe(
        "lean_toolchain_presence", [str(toolchain), "--version"], PATHS["root"]
    )


def discover_euclid(roots):
    """Bounded directory discovery; no fetching or executing unknown entry points."""
    candidates = sorted(
        str(p)
        for root in roots
        if root.is_dir()
        for p in root.iterdir()
        if p.is_dir() and "euclid" in p.name.lower()
    )
    return {
        "name": "euclid_generator_discovery",
        "status": "failed",
        "at": datetime.now(timezone.utc).isoformat(),
        "candidates": candidates,
        "searched_roots": [str(root) for root in roots],
        "reason": (
            "local candidate found; executable fixture not yet established"
            if candidates
            else "no local Euclid checkout in bounded roots; cannot run fixture offline"
        ),
        "stop_budget_engineer_hours": 2,
        "fallback_selected": False,
        "next": "WP-2 in-house fallback only after the discovery stop criterion is recorded",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=PATHS["root"] / "mve/preflight/results"
    )
    args = parser.parse_args()
    checks = local_checks()
    checks.append(
        discover_euclid(
            [
                PATHS["root"] / "vendor",
                PATHS["root"] / "references",
                PATHS["base"],
                PATHS["base"] / "worktrees",
                PATHS["base"] / "runtimes",
            ]
        )
    )
    failures = {
        "newclid_jgex_roundtrip": "Newclid import failed in selected Python; no JGEX round-trip capability established",
        "newclid_geogebra_terms": "actual imported Newclid dependency/terms unavailable; no licence conclusion",
        "rhvf_isolation": "source pinned only; end-to-end isolation requires WP-11a process boundary",
        "explorer_scenes": "index and geometry entrypoints pinned; scene-to-record integration awaits WP-9",
        "local_prover_host": "runtime plist present; DSP/Goedel model fit and inference not executed",
        "human_latency": "no observed human verdict session; estimate remains null",
    }
    checks += [
        {"name": name, "status": "failed", "reason": reason}
        for name, reason in failures.items()
    ]
    write_report(args.output, checks, dependencies())
    if args.output == PATHS["root"] / "mve/preflight/results":
        publish_lock(args.output / "DEPS.lock", PATHS["root"] / "mve/DEPS.lock")
    print(json.dumps({row["name"]: row["status"] for row in checks}, indent=2))
    return int(any(row["status"] == "failed" for row in checks))


if __name__ == "__main__":
    raise SystemExit(main())
