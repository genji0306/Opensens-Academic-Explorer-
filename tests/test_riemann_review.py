"""Tests for the Riemann math analysis and debate agents."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann.math_review import MathAnalysisAgent, MathDebateAgent, run_math_review


def _load_summary() -> dict:
    report = PROJECT_ROOT / "data" / "riemann" / "reports" / "final_report.json"
    return json.loads(report.read_text())


def _report_path() -> Path:
    return PROJECT_ROOT / "data" / "riemann" / "reports" / "final_report.json"


def test_math_analysis_agent_detects_holdout_drift(tmp_path: Path) -> None:
    summary = _load_summary()
    report = MathAnalysisAgent().run(
        summary=summary,
        source_report=_report_path(),
        output_dir=tmp_path,
    )

    assert report.training_zeros == 10000
    assert report.spline_knots == report.training_zeros
    assert report.holdout_zeros == 200
    assert report.holdout_rmse > 0.25
    assert report.holdout_nearest_index_hit_rate < 1.0
    assert "not a proof" in report.conclusion.lower()
    assert any("knot" in flag.lower() for flag in report.red_flags)
    assert (tmp_path / "math_analysis.json").exists()


def test_math_debate_agent_returns_skeptical_verdict(tmp_path: Path) -> None:
    summary = _load_summary()
    analysis = MathAnalysisAgent().run(
        summary=summary,
        source_report=_report_path(),
        output_dir=tmp_path,
    )
    debate = MathDebateAgent().run(analysis=analysis, output_dir=tmp_path)

    assert debate.turns[0]["speaker"] == "Proponent"
    assert debate.turns[-1]["speaker"] == "Moderator"
    assert "proof" in debate.verdict.lower()
    assert "interpol" in debate.summary.lower()
    assert len(debate.open_questions) >= 3
    assert (tmp_path / "math_debate.json").exists()


def test_run_math_review_writes_bundle(tmp_path: Path) -> None:
    summary = _load_summary()
    review = run_math_review(
        summary=summary,
        source_report=_report_path(),
        output_dir=tmp_path,
    )

    assert "analysis" in review
    assert "debate" in review
    assert review["analysis"]["holdout_rmse"] > 0.25
    assert review["analysis"]["holdout_nearest_index_hit_rate"] < 1.0
    assert Path(review["analysis_path"]).exists()
    assert Path(review["debate_path"]).exists()
