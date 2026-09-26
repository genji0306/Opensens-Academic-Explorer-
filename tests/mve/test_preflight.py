import hashlib
import json
import sys
from pathlib import Path

from mve.preflight.core import pin, probe, write_report


def test_pin_existing_and_missing(tmp_path):
    p = tmp_path / 'fixture.py'
    p.write_text('answer = 42\n')
    got = pin(p)
    assert got['sha256'] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert got['path'] == str(p.resolve())
    assert pin(tmp_path / 'missing')['status'] == 'failed'


def test_probe_success_failure_timeout_and_missing(tmp_path):
    ok = probe('ok', [sys.executable, '-c', 'print(42)'], tmp_path)
    assert ok['status'] == 'ran' and ok['stdout'] == '42\n'
    bad = probe('bad', [sys.executable, '-c', 'raise ValueError("bad")'], tmp_path)
    assert bad['status'] == 'failed' and 'ValueError' in bad['stderr']
    timeout = probe('slow', [sys.executable, '-c', 'import time; time.sleep(2)'], tmp_path, timeout=.01)
    assert timeout['status'] == 'failed' and 'timeout' in timeout['reason']
    assert probe('absent', ['/nonexistent/mve-command'], tmp_path)['status'] == 'failed'


def test_report_preserves_failure_and_unknown_cost(tmp_path):
    write_report(tmp_path, [{'name': 'live', 'status': 'failed', 'reason': 'guard'}], [])
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['checks'][0]['status'] == 'failed'
    assert report['cost_model']['vision_latency_s'] is None
    assert report['live_calls'] == 0
    assert (tmp_path / 'DEPS.lock').exists()


def test_dependency_inventory_and_main(tmp_path, monkeypatch):
    from mve.preflight import run
    for key in ('BASE', 'VISION', 'JEV', 'ATLAS', 'LEAN'):
        monkeypatch.setattr(run, key, tmp_path)
    monkeypatch.setattr(run, 'pin', lambda p: {'path': str(p)})
    assert run.dependencies()
    monkeypatch.setattr(run, 'local_checks', lambda: [{'name': 'fixture', 'status': 'ran'}])
    monkeypatch.setattr(sys, 'argv', ['probe', '--output', str(tmp_path)])
    assert run.main() == 1
    assert json.loads((tmp_path / 'report.json').read_text())['live_calls'] == 0


def test_local_checks_dispatch_only_offline_probes(monkeypatch):
    from mve.preflight import run
    monkeypatch.setattr(run, 'probe', lambda name, *a, **k: {'name': name, 'status': 'ran'})
    monkeypatch.setattr(run, 'lean_check', lambda: {'name': 'lean_project_build', 'status': 'failed'})
    checks = run.local_checks()
    assert len(checks) == 7
    assert all('live' not in row['name'] for row in checks)


def test_guard_blocks_child_network(tmp_path):
    result = probe('network', [sys.executable, '-c',
                   'import socket; socket.create_connection(("localhost", 80))'], tmp_path)
    assert result['status'] == 'failed'
    assert 'network disabled' in result['stderr']
