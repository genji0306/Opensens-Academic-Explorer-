"""Run the WP-0 local probes and persist explicit failures for missing prerequisites."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

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
    toolchain = Path.home() / '.elan/toolchains/leanprover--lean4---v4.29.0/bin/lake'
    if not toolchain.is_file():
        return {'name': 'lean_project_build', 'status': 'failed', 'reason': 'pinned Lake binary missing'}
    # Do not build in the borrowed project or auto-fetch dependencies.
    with tempfile.TemporaryDirectory(prefix='mve-lean-') as tmp:
        dest = Path(tmp)
        for name in ('lakefile.lean', 'lean-toolchain', 'lake-manifest.json'):
            shutil.copy2(LEAN / name, dest / name)
        (dest / 'RH').mkdir()
        (dest / 'RH.lean').write_text('import Mathlib\n')
        # macOS sandbox denies network to Lake and all its child processes.
        sandbox = Path('/usr/bin/sandbox-exec')
        if not sandbox.exists():
            return {'name': 'lean_project_build', 'status': 'failed',
                    'reason': 'network-denying OS sandbox unavailable'}
        return probe('lean_project_build', [str(sandbox), '-p',
            '(version 1)(allow default)(deny network*)', str(toolchain),
            '--no-cache', 'build'], dest, timeout=60,
            extra_env={'PATH': str(toolchain.parent) + os.pathsep + os.environ['PATH']})



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'mve/preflight/results')
    args = parser.parse_args()
    checks = local_checks()
    failures = {
        'deepseek_live_probe': 'not sent: borrowed runner fails aggregate in-flight reservation and peak-refusal prerequisites; no current verified price lock',
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
