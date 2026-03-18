"""
Tests for RTAP benchmark datasets and RTAP-specific metrics.

Verifies that the rtap_candidates_40 and high_tc_reference_15 datasets
load correctly with required fields, and that RTAP metrics
(rtap_discovery_score, mechanism_diversity_score, pressure_reduction_factor)
behave correctly on boundary conditions.
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.datasets import load_dataset
from benchmarks.metrics import (
    rtap_discovery_score,
    mechanism_diversity_score,
    pressure_reduction_factor,
)


# ---------------------------------------------------------------------------
# rtap_candidates_40 dataset
# ---------------------------------------------------------------------------

class TestRTAPCandidates40:
    def test_rtap_candidates_40_loads(self):
        """load_dataset('rtap_candidates_40') returns list of 40 entries."""
        data = load_dataset("rtap_candidates_40")
        assert isinstance(data, list)
        assert len(data) == 40, f"Expected 40 entries, got {len(data)}"

    def test_rtap_candidates_40_has_required_fields(self):
        """Each entry has composition, Tc_K, family, mechanism."""
        data = load_dataset("rtap_candidates_40")
        required_fields = ["composition", "Tc_K", "family", "mechanism"]
        for i, entry in enumerate(data):
            for field in required_fields:
                assert field in entry, (
                    f"Entry {i} ({entry.get('composition', '?')}) missing field '{field}'"
                )

    def test_rtap_candidates_40_has_pressure(self):
        """Each entry should have pressure_GPa."""
        data = load_dataset("rtap_candidates_40")
        for i, entry in enumerate(data):
            assert "pressure_GPa" in entry, (
                f"Entry {i} ({entry.get('composition', '?')}) missing 'pressure_GPa'"
            )

    def test_rtap_candidates_40_tc_range(self):
        """Tc values should span from 0 (controls) to 300+ (speculative)."""
        data = load_dataset("rtap_candidates_40")
        tc_values = [e["Tc_K"] for e in data]
        assert min(tc_values) == 0, "Expected control entries with Tc=0"
        assert max(tc_values) >= 200, f"Max Tc={max(tc_values)}, expected >= 200"

    def test_rtap_candidates_40_multiple_families(self):
        """Dataset should span multiple SC families."""
        data = load_dataset("rtap_candidates_40")
        families = set(e["family"] for e in data)
        assert len(families) >= 5, (
            f"Only {len(families)} families: {families}, expected >= 5"
        )


# ---------------------------------------------------------------------------
# high_tc_reference_15 dataset
# ---------------------------------------------------------------------------

class TestHighTcReference15:
    def test_high_tc_reference_15_loads(self):
        """load_dataset('high_tc_reference_15') returns list of 15 entries."""
        data = load_dataset("high_tc_reference_15")
        assert isinstance(data, list)
        assert len(data) == 15, f"Expected 15 entries, got {len(data)}"

    def test_high_tc_reference_15_has_required_fields(self):
        """Each entry has composition, Tc_K, family, mechanism."""
        data = load_dataset("high_tc_reference_15")
        required_fields = ["composition", "Tc_K", "family", "mechanism"]
        for i, entry in enumerate(data):
            for field in required_fields:
                assert field in entry, (
                    f"Entry {i} ({entry.get('composition', '?')}) missing field '{field}'"
                )

    def test_high_tc_reference_15_sorted_desc(self):
        """Entries should be roughly ordered by Tc (highest first)."""
        data = load_dataset("high_tc_reference_15")
        tc_values = [e["Tc_K"] for e in data]
        # Allow for minor non-monotonicity but first should be >= last
        assert tc_values[0] >= tc_values[-1], (
            f"First Tc={tc_values[0]} < last Tc={tc_values[-1]}, expected descending order"
        )


# ---------------------------------------------------------------------------
# rtap_discovery_score metric
# ---------------------------------------------------------------------------

class TestRTAPDiscoveryScore:
    def test_rtap_discovery_score_zero(self):
        """Empty list -> score 0."""
        score = rtap_discovery_score([])
        assert score == 0.0

    def test_rtap_discovery_score_all_rt_ambient(self):
        """All structures above 273K at ambient -> score = 1.0."""
        structures = [
            {"predicted_Tc_K": 300.0, "pressure_GPa": 0.0}
            for _ in range(10)
        ]
        score = rtap_discovery_score(structures)
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_rtap_discovery_score_none_qualifying(self):
        """All structures below 273K -> score = 0."""
        structures = [
            {"predicted_Tc_K": 100.0, "pressure_GPa": 0.0}
            for _ in range(10)
        ]
        score = rtap_discovery_score(structures)
        assert score == 0.0

    def test_rtap_discovery_score_high_pressure_excluded(self):
        """Structures above 273K but at high pressure should not qualify."""
        structures = [
            {"predicted_Tc_K": 300.0, "pressure_GPa": 150.0}
            for _ in range(10)
        ]
        score = rtap_discovery_score(structures)
        assert score == 0.0


# ---------------------------------------------------------------------------
# mechanism_diversity_score metric
# ---------------------------------------------------------------------------

class TestMechanismDiversityScore:
    def test_mechanism_diversity_score_three_mechanisms(self):
        """List with 3 different mechanisms -> score > 0."""
        structures = [
            {"primary_mechanism": "bcs"},
            {"primary_mechanism": "flat_band"},
            {"primary_mechanism": "spin_fluctuation"},
        ]
        score = mechanism_diversity_score(structures)
        assert score > 0, f"Diversity score with 3 mechanisms = {score:.4f}, expected > 0"

    def test_mechanism_diversity_score_empty(self):
        """Empty list -> score 0."""
        score = mechanism_diversity_score([])
        assert score == 0.0

    def test_mechanism_diversity_score_single_mechanism(self):
        """All same mechanism -> score 0."""
        structures = [{"primary_mechanism": "bcs"} for _ in range(10)]
        score = mechanism_diversity_score(structures)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_mechanism_diversity_score_uniform(self):
        """Perfectly uniform distribution across N mechanisms -> high score."""
        structures = [
            {"primary_mechanism": "bcs"},
            {"primary_mechanism": "flat_band"},
            {"primary_mechanism": "spin_fluctuation"},
            {"primary_mechanism": "hydride_cage"},
        ]
        score = mechanism_diversity_score(structures)
        assert score > 0.5, f"Uniform diversity score = {score:.4f}, expected > 0.5"


# ---------------------------------------------------------------------------
# pressure_reduction_factor metric
# ---------------------------------------------------------------------------

class TestPressureReductionFactor:
    def test_pressure_reduction_factor_ambient(self):
        """All ambient pressure -> score = 1.0."""
        structures = [{"pressure_GPa": 0.0} for _ in range(5)]
        score = pressure_reduction_factor(structures)
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_pressure_reduction_factor_high_pressure(self):
        """All at 200 GPa -> score = 0.0."""
        structures = [{"pressure_GPa": 200.0} for _ in range(5)]
        score = pressure_reduction_factor(structures)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_pressure_reduction_factor_mixed(self):
        """Mixed pressures -> 0 <= score <= 1."""
        structures = [
            {"pressure_GPa": 0.0},
            {"pressure_GPa": 50.0},
            {"pressure_GPa": 100.0},
            {"pressure_GPa": 150.0},
            {"pressure_GPa": 200.0},
        ]
        score = pressure_reduction_factor(structures)
        assert 0.0 <= score <= 1.0, f"Pressure reduction score = {score:.4f}, expected in [0, 1]"

    def test_pressure_reduction_factor_empty(self):
        """Empty list -> score 0."""
        score = pressure_reduction_factor([])
        assert score == 0.0
