"""Tests for the Riemann visualization dashboard."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann.visualization import build_dashboard_figure, load_result_bundle, write_dashboard


def _report_path() -> Path:
    return PROJECT_ROOT / "data" / "riemann" / "reports" / "final_report.json"


def test_build_dashboard_figure_uses_saved_history() -> None:
    report, analysis, debate = load_result_bundle(_report_path())

    fig = build_dashboard_figure(report, analysis, debate)

    assert len(fig.data) >= 7
    assert fig.layout.title.text == "Riemann loop result"
    assert any(getattr(trace, "name", "") == "Score" for trace in fig.data)
    assert any(getattr(trace, "type", "") == "table" for trace in fig.data)


def test_write_dashboard_creates_self_contained_html(tmp_path: Path) -> None:
    output = write_dashboard(_report_path(), tmp_path / "riemann_result_dashboard.html")

    assert output.exists()
    html = output.read_text()
    assert "Riemann Result Dashboard" in html
    assert "The loop found a high-precision interpolant" in html
    assert "Plotly.newPlot" in html
