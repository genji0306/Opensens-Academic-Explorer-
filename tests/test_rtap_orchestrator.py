"""
Tests for the RTAP orchestrator loop and supporting infrastructure.

Verifies that run_rtap_loop is importable, the --rtap flag is wired into
run.py, RTAP directories are created by ensure_dirs_rtap, and the
check_plateau utility behaves correctly on boundary inputs.
"""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# run_rtap_loop importable
# ---------------------------------------------------------------------------

class TestRunRTAPLoopExists:
    def test_run_rtap_loop_exists(self):
        """from src.orchestrator import run_rtap_loop -- no error."""
        from src.orchestrator import run_rtap_loop

        assert callable(run_rtap_loop)

    def test_run_rtap_loop_signature(self):
        """run_rtap_loop accepts max_iterations and target kwargs."""
        import inspect
        from src.orchestrator import run_rtap_loop

        sig = inspect.signature(run_rtap_loop)
        assert "max_iterations" in sig.parameters
        assert "target" in sig.parameters


# ---------------------------------------------------------------------------
# --rtap flag in run.py
# ---------------------------------------------------------------------------

class TestRTAPFlagInRunPy:
    def test_rtap_flag_in_run_py(self):
        """run.py should contain the '--rtap' flag string."""
        run_py_path = PROJECT_ROOT / "run.py"
        assert run_py_path.exists(), f"run.py not found at {run_py_path}"

        content = run_py_path.read_text()
        assert "--rtap" in content, (
            "run.py does not contain '--rtap' flag"
        )

    def test_rtap_imports_in_run_py(self):
        """run.py should reference RTAP-related config when --rtap is used."""
        run_py_path = PROJECT_ROOT / "run.py"
        content = run_py_path.read_text()
        assert "RTAP" in content, "run.py does not reference RTAP"

    def test_run_py_calls_run_rtap_loop(self):
        """run.py should call run_rtap_loop when --rtap is active."""
        run_py_path = PROJECT_ROOT / "run.py"
        content = run_py_path.read_text()
        assert "run_rtap_loop" in content, (
            "run.py does not call run_rtap_loop"
        )


# ---------------------------------------------------------------------------
# ensure_dirs_rtap
# ---------------------------------------------------------------------------

class TestEnsureDirsRTAP:
    def test_ensure_dirs_rtap_creates_dirs(self):
        """call ensure_dirs_rtap(), verify RTAP_CANDIDATES_DIR exists."""
        from src.core.config import ensure_dirs_rtap, RTAP_CANDIDATES_DIR

        ensure_dirs_rtap()
        assert RTAP_CANDIDATES_DIR.exists(), (
            f"RTAP_CANDIDATES_DIR {RTAP_CANDIDATES_DIR} does not exist after ensure_dirs_rtap()"
        )

    def test_ensure_dirs_rtap_creates_reports_dir(self):
        """RTAP_REPORTS_DIR should also be created."""
        from src.core.config import ensure_dirs_rtap, RTAP_REPORTS_DIR

        ensure_dirs_rtap()
        assert RTAP_REPORTS_DIR.exists(), (
            f"RTAP_REPORTS_DIR {RTAP_REPORTS_DIR} does not exist after ensure_dirs_rtap()"
        )

    def test_ensure_dirs_rtap_creates_base_rtap_dir(self):
        """RTAP_DIR should be created."""
        from src.core.config import ensure_dirs_rtap, RTAP_DIR

        ensure_dirs_rtap()
        assert RTAP_DIR.exists(), (
            f"RTAP_DIR {RTAP_DIR} does not exist after ensure_dirs_rtap()"
        )

    def test_ensure_dirs_rtap_idempotent(self):
        """Calling ensure_dirs_rtap() twice should not raise."""
        from src.core.config import ensure_dirs_rtap

        ensure_dirs_rtap()
        ensure_dirs_rtap()  # second call should be fine


# ---------------------------------------------------------------------------
# check_plateau utility
# ---------------------------------------------------------------------------

class TestCheckPlateau:
    def test_check_plateau_short_history(self):
        """History shorter than window -> returns False."""
        from src.orchestrator import check_plateau

        result = check_plateau([0.5, 0.6, 0.7], window=5)
        assert result is False

    def test_check_plateau_flat_history(self):
        """Flat history (identical scores) -> returns True."""
        from src.orchestrator import check_plateau

        flat = [0.8500] * 10
        result = check_plateau(flat, window=5, threshold=0.005)
        assert result is True

    def test_check_plateau_improving_history(self):
        """Steadily improving history -> not a plateau."""
        from src.orchestrator import check_plateau

        improving = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        result = check_plateau(improving, window=5, threshold=0.005)
        assert result is False

    def test_check_plateau_barely_below_threshold(self):
        """Very small changes just below threshold -> plateau detected."""
        from src.orchestrator import check_plateau

        # Changes of 0.001 over window of 5, with threshold 0.005
        history = [0.900, 0.901, 0.902, 0.903, 0.904, 0.9045, 0.905]
        result = check_plateau(history, window=5, threshold=0.005)
        assert result is True

    def test_check_plateau_empty_history(self):
        """Empty history -> returns False."""
        from src.orchestrator import check_plateau

        result = check_plateau([], window=5)
        assert result is False

    def test_check_plateau_exact_window_size(self):
        """History exactly at window size with flat data -> True."""
        from src.orchestrator import check_plateau

        flat = [0.85, 0.85, 0.85, 0.85, 0.85]
        result = check_plateau(flat, window=5, threshold=0.005)
        assert result is True
