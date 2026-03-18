"""Tests for OAE NeMAD Comparative Study."""
import sys
import os

import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestClassificationAgreement:
    def test_perfect_agreement(self):
        from benchmarks.nemad_comparison import classification_agreement
        result = classification_agreement(["FM", "AFM", "NM"], ["FM", "AFM", "NM"])
        assert result["accuracy"] == 1.0

    def test_no_agreement(self):
        from benchmarks.nemad_comparison import classification_agreement
        result = classification_agreement(["FM", "FM", "FM"], ["AFM", "AFM", "AFM"])
        assert result["accuracy"] == 0.0

    def test_partial_agreement(self):
        from benchmarks.nemad_comparison import classification_agreement
        result = classification_agreement(["FM", "AFM", "NM", "FM"],
                                          ["FM", "FM", "NM", "AFM"])
        assert result["accuracy"] == 0.5

    def test_empty_lists(self):
        from benchmarks.nemad_comparison import classification_agreement
        result = classification_agreement([], [])
        assert result["accuracy"] == 0.0


class TestTemperatureCorrelation:
    def test_perfect_correlation(self):
        from benchmarks.nemad_comparison import temperature_correlation
        result = temperature_correlation([100, 200, 300], [100, 200, 300])
        assert result["pearson_r"] == pytest.approx(1.0, abs=0.01)

    def test_zero_values_filtered(self):
        from benchmarks.nemad_comparison import temperature_correlation
        result = temperature_correlation([0, 100, 200], [0, 100, 200])
        assert result["n_nonzero"] == 2

    def test_empty(self):
        from benchmarks.nemad_comparison import temperature_correlation
        result = temperature_correlation([], [])
        assert result["pearson_r"] == 0.0


class TestFeatureCorrelation:
    def test_identical_features(self):
        from benchmarks.nemad_comparison import feature_correlation
        features = np.array([[1, 2, 3], [4, 5, 6]])
        result = feature_correlation(features, features)
        assert result["mean_r"] == pytest.approx(1.0, abs=0.01)

    def test_empty(self):
        from benchmarks.nemad_comparison import feature_correlation
        result = feature_correlation(np.array([]), np.array([]))
        assert result["mean_r"] == 0.0


class TestRunComparison:
    def test_run_comparison(self):
        from benchmarks.nemad_comparison import run_comparison
        report = run_comparison(max_compounds=10)
        assert "n_compounds" in report
        assert report["n_compounds"] <= 10
        assert "classification" in report
        assert "temperature" in report
        assert "summary" in report

    def test_overlap_compounds_exist(self):
        from benchmarks.nemad_comparison import OVERLAP_COMPOUNDS
        assert len(OVERLAP_COMPOUNDS) >= 15
        for c in OVERLAP_COMPOUNDS:
            assert "composition" in c
            assert "nemad_class" in c

    def test_complementary_candidates(self):
        from benchmarks.nemad_comparison import run_comparison
        report = run_comparison(max_compounds=20)
        # Should find some complementary candidates
        assert "complementary_candidates" in report


class TestNemadModelsHelpers:
    def test_composition_to_features(self):
        from benchmarks.nemad_models import _composition_to_features, ELEMENT_COLUMNS
        features = _composition_to_features("Fe3O4")
        fe_idx = ELEMENT_COLUMNS.index("Fe")
        o_idx = ELEMENT_COLUMNS.index("O")
        assert features[fe_idx] == 3.0
        assert features[o_idx] == 4.0
        assert features.sum() == 7.0

    def test_composition_single_element(self):
        from benchmarks.nemad_models import _composition_to_features, ELEMENT_COLUMNS
        features = _composition_to_features("Cu")
        cu_idx = ELEMENT_COLUMNS.index("Cu")
        assert features[cu_idx] == 1.0

    def test_element_columns_count(self):
        from benchmarks.nemad_models import ELEMENT_COLUMNS
        assert len(ELEMENT_COLUMNS) == 94


class TestMetricsExtensions:
    def test_classification_agreement_metric(self):
        from benchmarks.metrics import classification_agreement
        acc = classification_agreement(["FM", "AFM"], ["FM", "AFM"])
        assert acc == 1.0

    def test_temperature_correlation_metric(self):
        from benchmarks.metrics import temperature_correlation
        r = temperature_correlation([100, 200, 300], [100, 200, 300])
        assert r == pytest.approx(1.0, abs=0.01)
