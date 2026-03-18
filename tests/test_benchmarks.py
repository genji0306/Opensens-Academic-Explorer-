"""Smoke tests for benchmarking framework."""
import pytest


class TestDatasets:
    def test_available_datasets(self):
        from benchmarks.datasets import AVAILABLE_DATASETS
        assert "supercon_24" in AVAILABLE_DATASETS
        assert "seed_patterns_12" in AVAILABLE_DATASETS

    def test_load_supercon_24(self):
        from benchmarks.datasets import load_dataset
        data = load_dataset("supercon_24")
        assert isinstance(data, list)
        assert len(data) > 0
        # Check record structure
        record = data[0]
        assert "composition" in record
        assert "Tc_K" in record
        assert "crystal_system" in record

    def test_load_unknown_dataset(self):
        from benchmarks.datasets import load_dataset
        with pytest.raises(ValueError, match="Unknown dataset"):
            load_dataset("nonexistent_dataset")


class TestMetrics:
    def test_convergence_score_missing_file(self):
        from benchmarks.metrics import convergence_score
        from pathlib import Path
        # Should return 0.0 for nonexistent file
        score = convergence_score(Path("/nonexistent/path.json"))
        assert score == 0.0

    def test_energy_mae(self):
        from benchmarks.metrics import energy_mae
        mae = energy_mae([1.0, 2.0, 3.0], [1.1, 2.2, 3.3])
        assert 0 < mae < 1.0

    def test_energy_mae_empty(self):
        from benchmarks.metrics import energy_mae
        assert energy_mae([], []) == -1.0

    def test_rwp_identical(self):
        import numpy as np
        from benchmarks.metrics import rwp
        pattern = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        assert rwp(pattern, pattern) == pytest.approx(0.0, abs=1e-6)

    def test_rwp_different(self):
        import numpy as np
        from benchmarks.metrics import rwp
        obs = np.array([1.0, 2.0, 3.0])
        calc = np.array([1.5, 2.5, 3.5])
        r = rwp(obs, calc)
        assert 0 < r < 1.0


class TestReport:
    def test_generate_comparison_table(self):
        from benchmarks.report import generate_comparison_table
        results = {
            "agent_a": {"score": 0.95, "n_structures": 10},
            "agent_b": {"score": 0.80, "n_structures": 8},
        }
        df = generate_comparison_table(results)
        assert len(df) == 2
        assert "score" in df.columns

    def test_print_comparison(self, capsys):
        from benchmarks.report import print_comparison
        results = {
            "agent_a": {"score": 0.95},
            "agent_b": {"score": 0.80},
        }
        print_comparison(results)
        captured = capsys.readouterr()
        assert "agent_a" in captured.out
        assert "agent_b" in captured.out


class TestAgentBenchmark:
    def test_benchmark_runs(self):
        from benchmarks.compare_agents import AgentBenchmark
        bm = AgentBenchmark(dataset="supercon_24", agents=["crystal_agent"])
        results = bm.run()
        assert "crystal_agent" in results
        assert "n_structures" in results["crystal_agent"]

    def test_unknown_agent(self):
        from benchmarks.compare_agents import AgentBenchmark
        bm = AgentBenchmark(dataset="supercon_24", agents=["nonexistent"])
        results = bm.run()
        assert "error" in results["nonexistent"]
