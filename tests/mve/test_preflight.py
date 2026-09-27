import hashlib
import json
import sys
from pathlib import Path

from mve.preflight.core import pin, probe, write_report


def test_pin_existing_and_missing(tmp_path):
    p = tmp_path / "fixture.py"
    p.write_text("answer = 42\n")
    got = pin(p)
    assert got["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert got["path"] == str(p.resolve())
    assert pin(tmp_path / "missing")["status"] == "failed"


def test_probe_success_failure_timeout_and_missing(tmp_path):
    ok = probe("ok", [sys.executable, "-c", "print(42)"], tmp_path)
    assert ok["status"] == "ran" and ok["stdout"] == "42\n"
    bad = probe("bad", [sys.executable, "-c", 'raise ValueError("bad")'], tmp_path)
    assert bad["status"] == "failed" and "ValueError" in bad["stderr"]
    timeout = probe(
        "slow",
        [sys.executable, "-c", "import time; time.sleep(2)"],
        tmp_path,
        timeout=0.01,
    )
    assert timeout["status"] == "failed" and "timeout" in timeout["reason"]
    assert probe("absent", ["/nonexistent/mve-command"], tmp_path)["status"] == "failed"


def test_report_preserves_failure_and_unknown_cost(tmp_path):
    write_report(
        tmp_path, [{"name": "live", "status": "failed", "reason": "guard"}], []
    )
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["checks"][0]["status"] == "failed"
    assert report["cost_model"]["vision_latency_s"] is None
    assert report["live_calls"] == 0
    assert (tmp_path / "DEPS.lock").exists()


def test_dependency_inventory_and_main(tmp_path, monkeypatch):
    from mve.preflight import offline as run

    for key in ("base", "vision", "jev", "atlas", "lean"):
        monkeypatch.setitem(run.PATHS, key, tmp_path)
    monkeypatch.setattr(run, "pin", lambda p: {"path": str(p)})
    assert run.dependencies()
    monkeypatch.setattr(
        run, "local_checks", lambda: [{"name": "fixture", "status": "ran"}]
    )
    monkeypatch.setattr(sys, "argv", ["probe", "--output", str(tmp_path)])
    assert run.main() == 1
    assert json.loads((tmp_path / "report.json").read_text())["live_calls"] == 0


def test_local_checks_dispatch_only_offline_probes(monkeypatch):
    from mve.preflight import offline as run

    monkeypatch.setattr(
        run, "probe", lambda name, *a, **k: {"name": name, "status": "ran"}
    )
    monkeypatch.setattr(
        run, "lean_check", lambda: {"name": "lean_project_build", "status": "failed"}
    )
    checks = run.local_checks()
    assert len(checks) == 7
    assert all("live" not in row["name"] for row in checks)


def test_guard_blocks_child_network(tmp_path):
    result = probe(
        "network",
        [
            sys.executable,
            "-c",
            'import socket; socket.create_connection(("localhost", 80))',
        ],
        tmp_path,
    )
    assert result["status"] == "failed"
    assert "network disabled" in result["stderr"]


def test_r5_toolchain_probe_is_presence_only(monkeypatch):
    from mve.preflight import offline

    calls = []

    def capture(name, command, cwd, **kwargs):
        calls.append(command)
        return {"name": name, "status": "ran"}

    monkeypatch.setattr(offline, "probe", capture)
    assert offline.lean_check()["name"] == "lean_toolchain_presence"
    assert calls[0][-1] == "--version"
    assert all("build" not in call for call in calls)


def test_euclid_discovery_is_bounded_and_offline(tmp_path):
    from mve.preflight.offline import discover_euclid

    result = discover_euclid([tmp_path])
    assert result["status"] == "failed"
    assert result["stop_budget_engineer_hours"] == 2
    assert result["fallback_selected"] is False
    (tmp_path / "Euclid").mkdir()
    result = discover_euclid([tmp_path])
    assert result["candidates"] == [str(tmp_path / "Euclid")]
    assert (
        result["status"] == "failed"
    )  # directory presence does not prove a fixture runs


def test_r5_schema_packet_is_unchanged_and_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from jsonschema import Draft202012Validator

    root = Path(__file__).resolve().parents[2]
    schema = root / "schemas/mve_observation_record.json"
    data = json.loads(schema.read_text())
    assert data["$id"] == "oae-mve-observation-v5"
    Draft202012Validator.check_schema(data)
    assert (
        schema.read_bytes()
        == (root / "docs/mve/mve_observation_record.json").read_bytes()
    )


def test_preflight_lock_publication_preserves_reviewed_packets(tmp_path):
    from mve.preflight.core import publish_lock

    source = tmp_path / "new.lock"
    target = tmp_path / "DEPS.lock"
    preflight = {"schema": "mve-deps-v1", "files": [{"path": "fixture"}]}
    source.write_text(json.dumps(preflight))
    other = {"WP-1": {"files": ["unchanged"]}, "WP-9a": {"files": []}}
    target.write_text(json.dumps({"schema": "mve-deps-v1", "packets": other}))
    publish_lock(source, target)
    assert json.loads(target.read_text())["packets"] == {**other, "WP-0a": preflight}
    target.unlink()
    publish_lock(source, target)
    assert json.loads(target.read_text())["packets"] == {"WP-0a": preflight}


def test_default_report_preserves_other_packets(tmp_path, monkeypatch):
    from mve.preflight import offline

    monkeypatch.setitem(offline.PATHS, "root", tmp_path)
    monkeypatch.setattr(offline, "local_checks", lambda: [])
    monkeypatch.setattr(offline, "dependencies", lambda: [])
    monkeypatch.setattr(sys, "argv", ["probe"])
    (tmp_path / "mve").mkdir()
    lock = tmp_path / "mve/DEPS.lock"
    lock.write_text(
        json.dumps({"schema": "mve-deps-v1", "packets": {"WP-1": {"sentinel": True}}})
    )
    assert offline.main() == 1
    assert json.loads(lock.read_text())["packets"]["WP-1"] == {"sentinel": True}
    assert "WP-0a" in json.loads(lock.read_text())["packets"]


def test_dependency_paths_share_one_config(tmp_path):
    from mve.preflight.config import local_paths

    config = local_paths(tmp_path)
    assert config["jev"] == tmp_path / "Developer/Opensens/rh-jev-harness"
    assert config["codex"] == tmp_path / ".local/bin/codex"
