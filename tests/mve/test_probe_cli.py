import json
import hashlib
from pathlib import Path
import subprocess
import sys
from mve.preflight.probe_offline import run_matrix

ROOT = Path(__file__).resolve().parents[2]


def test_offline_matrix_derives_refusal_results_and_zero_hosted_cost(tmp_path):
    root = tmp_path / "review"
    report = run_matrix(root)
    assert report["refusal_checks_passed"]
    assert report["hosted_calls"] == 0 and report["actual_api_cost_usd"] == "0"
    rows = {row["case"]: row for row in report["cases"]}
    for name in ("unverified_price", "peak", "boundary", "inflight", "probe_cap"):
        assert rows[name]["status"] == "refused" and rows[name]["fake_calls"] == 0
    assert rows["success"]["snapshot"]["attempts"][0]["state"] == "settled"
    assert rows["timeout"]["snapshot"]["exposure_micro_usd"] == 20_000
    assert json.loads((root / "report.json").read_text()) == report
    for row in report["artifacts"]:
        assert (
            hashlib.sha256((root / row["path"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    for row in report["source_pins"]:
        assert (
            hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
            == row["sha256"]
        )


def test_cli_defaults_to_hosted_refusal_with_no_output(tmp_path):
    target = tmp_path / "no-send"
    result = subprocess.run(
        [sys.executable, "-m", "mve.preflight.probe", "--output", str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "hosted probe disabled" in result.stderr
    assert not target.exists()


def test_cli_runs_only_explicit_offline_fixture_mode(tmp_path):
    target = tmp_path / "fixtures"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mve.preflight.probe",
            "--output",
            str(target),
            "--offline-fixture",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["hosted_calls"] == 0
