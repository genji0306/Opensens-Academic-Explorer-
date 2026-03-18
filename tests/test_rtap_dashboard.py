"""
Tests for RTAP Exploration Dashboard — agent_v/rtap_dashboard.py.

Tests cover data loaders, figure creation, and state management
without requiring a running Dash server.
"""
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# RTAPRunState
# ---------------------------------------------------------------------------

class TestRTAPRunState:
    def test_initial_state(self):
        from agent_v.rtap_dashboard import RTAPRunState
        state = RTAPRunState()
        assert state.running is False
        assert state.process is None
        assert state.log_lines == []

    def test_get_status_idle(self):
        from agent_v.rtap_dashboard import RTAPRunState
        state = RTAPRunState()
        status = state.get_status()
        assert status["running"] is False
        assert isinstance(status["log_tail"], str)

    def test_stop_when_not_running(self):
        from agent_v.rtap_dashboard import RTAPRunState
        state = RTAPRunState()
        state.stop()  # Should not raise
        assert state.running is False


# ---------------------------------------------------------------------------
# Data loaders (with temp files)
# ---------------------------------------------------------------------------

class TestDataLoaders:
    def test_load_convergence_history_empty(self):
        from agent_v.rtap_dashboard import _load_convergence_history
        with patch("agent_v.rtap_dashboard.CONVERGENCE_HISTORY_PATH",
                    Path("/nonexistent/path.json")):
            result = _load_convergence_history()
            assert result == []

    def test_load_convergence_history_valid(self, tmp_path):
        from agent_v.rtap_dashboard import _load_convergence_history
        history = [
            {"iteration": 0, "convergence_score": 0.85, "component_scores": {}},
            {"iteration": 1, "convergence_score": 0.90, "component_scores": {}},
        ]
        hist_file = tmp_path / "convergence_history.json"
        hist_file.write_text(json.dumps(history))

        with patch("agent_v.rtap_dashboard.CONVERGENCE_HISTORY_PATH", hist_file):
            result = _load_convergence_history()
            assert len(result) == 2
            assert result[0]["convergence_score"] == 0.85

    def test_load_final_report_empty(self):
        from agent_v.rtap_dashboard import _load_final_report
        with patch("agent_v.rtap_dashboard.FINAL_REPORT_PATH",
                    Path("/nonexistent/path.json")):
            result = _load_final_report()
            assert result == {}

    def test_load_final_report_valid(self, tmp_path):
        from agent_v.rtap_dashboard import _load_final_report
        report = {
            "termination_reason": "rtap_convergence_reached",
            "final_convergence_score": 0.9574,
        }
        report_file = tmp_path / "final_report.json"
        report_file.write_text(json.dumps(report))

        with patch("agent_v.rtap_dashboard.FINAL_REPORT_PATH", report_file):
            result = _load_final_report()
            assert result["final_convergence_score"] == 0.9574

    def test_load_rt_candidates_empty(self):
        from agent_v.rtap_dashboard import _load_rt_candidates
        with patch("agent_v.rtap_dashboard.RTAP_CANDIDATES_DIR",
                    Path("/nonexistent/dir")):
            result = _load_rt_candidates()
            assert result == []


# ---------------------------------------------------------------------------
# Plotly figure creation (requires plotly)
# ---------------------------------------------------------------------------

class TestFigureCreation:
    @pytest.fixture(autouse=True)
    def check_plotly(self):
        try:
            import plotly.graph_objects as go
            self.go = go
        except ImportError:
            pytest.skip("plotly not installed")

    def test_empty_figure(self):
        from agent_v.rtap_dashboard import _empty_figure
        fig = _empty_figure("test message")
        assert fig is not None

    def test_convergence_figure_empty(self):
        from agent_v.rtap_dashboard import create_convergence_figure
        fig = create_convergence_figure([])
        assert fig is not None

    def test_convergence_figure_with_data(self):
        from agent_v.rtap_dashboard import create_convergence_figure
        history = [
            {"iteration": 0, "convergence_score": 0.80},
            {"iteration": 1, "convergence_score": 0.85},
            {"iteration": 2, "convergence_score": 0.90},
        ]
        fig = create_convergence_figure(history)
        assert len(fig.data) >= 1

    def test_component_radar_empty(self):
        from agent_v.rtap_dashboard import create_component_radar
        fig = create_component_radar([])
        assert fig is not None

    def test_component_radar_with_data(self):
        from agent_v.rtap_dashboard import create_component_radar
        history = [{
            "iteration": 0,
            "convergence_score": 0.95,
            "component_scores": {
                "ambient_tc_score": 0.94,
                "ambient_stability_score": 1.0,
                "synthesizability_score": 0.95,
                "electronic_indicator_score": 0.91,
                "mechanism_plausibility_score": 0.99,
                "composition_validity": 0.90,
            },
        }]
        fig = create_component_radar(history)
        assert len(fig.data) >= 1

    def test_mechanism_pie_empty_df(self):
        from agent_v.rtap_dashboard import create_mechanism_pie
        fig = create_mechanism_pie(None)
        assert fig is not None

    def test_family_tc_chart_none(self):
        from agent_v.rtap_dashboard import create_family_tc_chart
        fig = create_family_tc_chart(None)
        assert fig is not None


# ---------------------------------------------------------------------------
# Figure creation with pandas DataFrames
# ---------------------------------------------------------------------------

class TestFigureWithDataFrame:
    @pytest.fixture(autouse=True)
    def check_deps(self):
        try:
            import plotly.graph_objects as go
            import pandas as pd
            self.pd = pd
        except ImportError:
            pytest.skip("plotly or pandas not installed")

    def test_family_tc_chart_with_data(self):
        from agent_v.rtap_dashboard import create_family_tc_chart
        df = self.pd.DataFrame({
            "pattern_id": [
                "cuprate-001", "cuprate-001", "kagome-001", "kagome-001",
            ],
            "ambient_pressure_Tc_K": [135, 140, 280, 300],
        })
        fig = create_family_tc_chart(df)
        assert len(fig.data) >= 1

    def test_mechanism_pie_with_data(self):
        from agent_v.rtap_dashboard import create_mechanism_pie
        df = self.pd.DataFrame({
            "primary_mechanism": ["bcs", "bcs", "spin_fluctuation", "flat_band"],
        })
        fig = create_mechanism_pie(df)
        assert len(fig.data) >= 1


# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------

class TestDashboardConstants:
    def test_dark_bg_is_hex(self):
        from agent_v.rtap_dashboard import DARK_BG
        assert DARK_BG.startswith("#")
        assert len(DARK_BG) == 7

    def test_rtap_family_colors_covers_14(self):
        from agent_v.rtap_dashboard import RTAP_FAMILY_COLORS
        assert len(RTAP_FAMILY_COLORS) >= 14

    def test_component_colors_covers_6(self):
        from agent_v.rtap_dashboard import COMPONENT_COLORS
        assert len(COMPONENT_COLORS) >= 6

    def test_poll_interval_positive(self):
        from agent_v.rtap_dashboard import _POLL_MS
        assert _POLL_MS > 0


# ---------------------------------------------------------------------------
# Dashboard class instantiation (requires dash)
# ---------------------------------------------------------------------------

class TestRTAPDashboardClass:
    def test_import_without_dash(self):
        """Module should import even if dash is not available."""
        # Already imported above — if it got here, import worked
        from agent_v.rtap_dashboard import RTAPDashboard
        assert RTAPDashboard is not None

    def test_instantiation_requires_dash(self):
        from agent_v.rtap_dashboard import _DASH, RTAPDashboard
        if not _DASH:
            with pytest.raises(ImportError):
                RTAPDashboard()
        else:
            # If dash is available, should instantiate OK
            dashboard = RTAPDashboard()
            assert dashboard is not None
