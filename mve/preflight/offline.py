"""Run the WP-0a offline probes and persist explicit failures for missing prerequisites."""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

from mve.preflight.core import pin, probe, write_report

BASE = Path.home() / 'Developer/Opensens'
DESKTOP = Path.home() / 'Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer'
VISION = DESKTOP / '.claude/worktrees/rh-handover-opus-deepseek-dc7dc2'
JEV = BASE / 'rh-jev-harness'
ATLAS = BASE / 'worktrees/oae-rh-atlas-p0-20260924'
LEAN = BASE / 'Opensens Academic Explorer/lean'
ROOT = Path(__file__).resolve().parents[2]


def dependencies():
    paths = [VISION / 'scripts' / name for name in
             ('rh_deepseek_vision_cell.py', 'rh_deepseek_worker_runner.py')]
    paths += list((VISION / 'riemann/research/deepseek').glob('*.py'))
    paths += list((JEV / 'rhjev').rglob('*.py'))
    paths += list((JEV / 'tests').rglob('*.py'))
    paths += list((ROOT / 'mve/preflight').rglob('*.py'))
    paths += [ROOT / 'docs/mve/MVE_PLAN.md', ROOT / 'schemas/mve_observation_record.json']
    paths += list((BASE / 'rh-visual-fields/rhvf').rglob('*.py'))
    paths += list((ATLAS / 'rh_evidence').rglob('*.py'))
    paths += [BASE / 'models/openjev' / name for name in
              ('model_fp16.onnx', 'tokenizer.json', 'calibrator.json')]
    paths += [LEAN / name for name in ('lean-toolchain', 'lakefile.lean', 'lake-manifest.json')]
    paths += [ATLAS / 'data/riemann/evidence_atlas/schema/result.schema.json',
              BASE / 'worktrees/zeta-explorer-main/dist/index.html',
              BASE / 'worktrees/zeta-explorer-main/dist/geometry.js',
              BASE / 'runtimes/qwen-local-worker/com.opensens.qwen-local-worker.plist',
              Path.home() / '.local/bin/codex']
    return [pin(path) for path in sorted(set(paths))]


def local_checks():
    checks = []
    checks.append(probe('vision_and_runner_contract', [sys.executable,
        str(ROOT / 'mve/preflight/vision_contract.py'), str(VISION / 'scripts')], ROOT))
    checks.append(probe('rhjev_tests', [sys.executable, '-m', 'pytest', '-q',
        '-p', 'no:cacheprovider'], JEV, timeout=120))
    checks.append(probe('openjev_fixture', [str(BASE / 'runtimes/openjev-venv/bin/python3'),
        str(ROOT / 'mve/preflight/openjev_fixture.py'), str(JEV)], ROOT, timeout=120))
    checks.append(probe('newclid_import', [sys.executable, '-c', 'import newclid; print(newclid.__file__)'], ROOT))
    checks.append(probe('atlas_ingest_contract', [sys.executable, '-c',
        'import inspect; from rh_evidence.adapters.result_bundle import validate_bundle; '
        'from pathlib import Path; print(inspect.signature(validate_bundle)); '
        'print(validate_bundle({}, schema_path=Path("data/riemann/evidence_atlas/schema/result.schema.json"), '
        'project_root=Path.cwd()))'], ATLAS))
    checks.append(probe('codex_cli', [str(Path.home() / '.local/bin/codex'), '--version'], ROOT))
    checks.append(lean_check())
    return checks


def lean_check():
    toolchain = Path.home() / '.elan/toolchains/leanprover--lean4---v4.29.0/bin/lean'
    return probe('lean_toolchain_presence', [str(toolchain), '--version'], ROOT)


def discover_euclid(roots):
    """Bounded directory discovery; no fetching or executing unknown entry points."""
    candidates = sorted(str(p) for root in roots if root.is_dir()
                        for p in root.iterdir()
                        if p.is_dir() and 'euclid' in p.name.lower())
    return {'name': 'euclid_generator_discovery', 'status': 'failed',
            'at': datetime.now(timezone.utc).isoformat(), 'candidates': candidates,
            'searched_roots': [str(root) for root in roots],
            'reason': ('local candidate found; executable fixture not yet established' if candidates
                       else 'no local Euclid checkout in bounded roots; cannot run fixture offline'),
            'stop_budget_engineer_hours': 2, 'fallback_selected': False,
            'next': 'WP-2 in-house fallback only after the discovery stop criterion is recorded'}



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'mve/preflight/results')
    args = parser.parse_args()
    checks = local_checks()
    checks.append(discover_euclid([ROOT / 'vendor', ROOT / 'references', BASE, BASE / 'worktrees', BASE / 'runtimes']))
    failures = {
        'newclid_jgex_roundtrip': 'Newclid import failed in selected Python; no JGEX round-trip capability established',
        'newclid_geogebra_terms': 'actual imported Newclid dependency/terms unavailable; no licence conclusion',
        'rhvf_isolation': 'source pinned only; end-to-end isolation requires WP-11a process boundary',
        'explorer_scenes': 'index and geometry entrypoints pinned; scene-to-record integration awaits WP-9',
        'local_prover_host': 'runtime plist present; DSP/Goedel model fit and inference not executed',
        'human_latency': 'no observed human verdict session; estimate remains null'}
    checks += [{'name': name, 'status': 'failed', 'reason': reason} for name, reason in failures.items()]
    write_report(args.output, checks, dependencies())
    if args.output == ROOT / 'mve/preflight/results':
        (args.output / 'DEPS.lock').replace(ROOT / 'mve/DEPS.lock')
    print(json.dumps({row['name']: row['status'] for row in checks}, indent=2))
    return int(any(row['status'] == 'failed' for row in checks))


if __name__ == '__main__':
    raise SystemExit(main())
