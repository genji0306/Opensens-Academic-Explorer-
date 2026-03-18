"""
Unit tests for RTAP discovery-mode scoring functions in src.agents.agent_ob.

Tests the ambient Tc, synthesizability, electronic indicator, and mechanism
plausibility scoring components that drive the RTAP convergence loop.
"""
import sys
import os

import pytest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.agent_ob import (
    compute_ambient_tc_score,
    compute_synthesizability_score,
    compute_electronic_indicator_score,
    compute_mechanism_plausibility_score,
)


# ---------------------------------------------------------------------------
# Helper: build minimal synthetic DataFrames
# ---------------------------------------------------------------------------

def _make_synth_df(rows):
    """Build a DataFrame mimicking Agent Sin output columns."""
    df = pd.DataFrame(rows)
    # Ensure required columns exist with defaults
    if "pattern_id" not in df.columns and len(df) > 0:
        df["pattern_id"] = [f"test-{i}" for i in range(len(df))]
    if "composition" not in df.columns and len(df) > 0:
        df["composition"] = "NaCl"
    if "predicted_Tc_K" not in df.columns and len(df) > 0:
        df["predicted_Tc_K"] = 0.0
    if "electron_phonon_lambda" not in df.columns and len(df) > 0:
        df["electron_phonon_lambda"] = 0.5
    if "stability_confidence" not in df.columns and len(df) > 0:
        df["stability_confidence"] = 0.7
    return df


# ---------------------------------------------------------------------------
# compute_ambient_tc_score
# ---------------------------------------------------------------------------

class TestComputeAmbientTcScore:
    def test_compute_ambient_tc_score_empty(self):
        """Empty DataFrame -> score approximately 0."""
        df = pd.DataFrame()
        score = compute_ambient_tc_score(df)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_compute_ambient_tc_score_with_rt_candidates(self):
        """DataFrame with some predicted_Tc_K >= 273 -> score > 0."""
        rows = [
            {"predicted_Tc_K": 300.0},
            {"predicted_Tc_K": 280.0},
            {"predicted_Tc_K": 100.0},
            {"predicted_Tc_K": 50.0},
            {"predicted_Tc_K": 10.0},
        ]
        df = _make_synth_df(rows)
        score = compute_ambient_tc_score(df)
        assert score > 0, f"Score with RT candidates = {score:.4f}, expected > 0"

    def test_compute_ambient_tc_score_all_rt(self):
        """All candidates above 273K -> high score."""
        rows = [{"predicted_Tc_K": 300.0 + i} for i in range(10)]
        df = _make_synth_df(rows)
        score = compute_ambient_tc_score(df)
        assert score > 0.5, f"All-RT score = {score:.4f}, expected > 0.5"

    def test_compute_ambient_tc_score_none_above_200(self):
        """No candidates above 200K -> score should still be computed (may be small)."""
        rows = [{"predicted_Tc_K": float(i)} for i in range(10)]
        df = _make_synth_df(rows)
        score = compute_ambient_tc_score(df)
        assert score >= 0.0


# ---------------------------------------------------------------------------
# compute_synthesizability_score
# ---------------------------------------------------------------------------

class TestComputeSynthesizabilityScore:
    def test_compute_synthesizability_score_clean(self):
        """DataFrame with only common elements -> score > 0.5."""
        rows = [
            {"composition": "NaCl", "stability_confidence": 0.8},
            {"composition": "MgB2", "stability_confidence": 0.9},
            {"composition": "CaO", "stability_confidence": 0.7},
            {"composition": "SrTiO3", "stability_confidence": 0.85},
        ]
        df = _make_synth_df(rows)
        score = compute_synthesizability_score(df)
        assert score > 0.5, f"Clean composition score = {score:.4f}, expected > 0.5"

    def test_compute_synthesizability_score_toxic(self):
        """DataFrame with Hg, Tl compositions -> lower score than clean."""
        clean_rows = [
            {"composition": "NaCl", "stability_confidence": 0.8},
            {"composition": "MgB2", "stability_confidence": 0.8},
        ]
        toxic_rows = [
            {"composition": "HgBa2Cu3O7", "stability_confidence": 0.8},
            {"composition": "Tl2Ba2Cu3O10", "stability_confidence": 0.8},
        ]
        df_clean = _make_synth_df(clean_rows)
        df_toxic = _make_synth_df(toxic_rows)

        score_clean = compute_synthesizability_score(df_clean)
        score_toxic = compute_synthesizability_score(df_toxic)
        assert score_toxic < score_clean, (
            f"Toxic score ({score_toxic:.4f}) should be < clean score ({score_clean:.4f})"
        )

    def test_compute_synthesizability_score_empty(self):
        """Empty DataFrame -> score 0."""
        df = pd.DataFrame()
        score = compute_synthesizability_score(df)
        assert score == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# compute_electronic_indicator_score
# ---------------------------------------------------------------------------

class TestComputeElectronicIndicatorScore:
    def test_compute_electronic_indicator_score_basic(self):
        """DataFrame with electron_phonon_lambda column -> score >= 0."""
        rows = [
            {"electron_phonon_lambda": 2.0},
            {"electron_phonon_lambda": 1.8},
            {"electron_phonon_lambda": 0.5},
            {"electron_phonon_lambda": 1.2},
        ]
        df = _make_synth_df(rows)
        score = compute_electronic_indicator_score(df)
        assert score >= 0, f"Electronic indicator score = {score:.4f}, expected >= 0"

    def test_compute_electronic_indicator_score_with_mechanism(self):
        """With primary_mechanism column, diversity contributes to score."""
        rows = [
            {"electron_phonon_lambda": 2.0, "primary_mechanism": "bcs"},
            {"electron_phonon_lambda": 1.5, "primary_mechanism": "flat_band"},
            {"electron_phonon_lambda": 1.0, "primary_mechanism": "spin_fluctuation"},
        ]
        df = _make_synth_df(rows)
        score = compute_electronic_indicator_score(df)
        assert score > 0

    def test_compute_electronic_indicator_score_empty(self):
        """Empty DataFrame -> score 0."""
        df = pd.DataFrame()
        score = compute_electronic_indicator_score(df)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_compute_electronic_indicator_score_all_low_lambda(self):
        """All low lambda values -> lower score than high lambda."""
        rows_low = [{"electron_phonon_lambda": 0.2} for _ in range(5)]
        rows_high = [{"electron_phonon_lambda": 2.5} for _ in range(5)]
        df_low = _make_synth_df(rows_low)
        df_high = _make_synth_df(rows_high)
        score_low = compute_electronic_indicator_score(df_low)
        score_high = compute_electronic_indicator_score(df_high)
        assert score_high > score_low


# ---------------------------------------------------------------------------
# compute_mechanism_plausibility_score
# ---------------------------------------------------------------------------

class TestComputeMechanismPlausibilityScore:
    def test_compute_mechanism_plausibility_score_basic(self):
        """DataFrame with primary_mechanism column -> score >= 0."""
        rows = [
            {"primary_mechanism": "bcs", "electron_phonon_lambda": 0.8, "predicted_Tc_K": 30},
            {"primary_mechanism": "bcs", "electron_phonon_lambda": 1.2, "predicted_Tc_K": 40},
            {"primary_mechanism": "flat_band", "electron_phonon_lambda": 0.5, "predicted_Tc_K": 80},
        ]
        df = _make_synth_df(rows)
        score = compute_mechanism_plausibility_score(df)
        assert score >= 0, f"Mechanism plausibility score = {score:.4f}, expected >= 0"

    def test_compute_mechanism_plausibility_score_empty(self):
        """Empty DataFrame -> score 0."""
        df = pd.DataFrame()
        score = compute_mechanism_plausibility_score(df)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_compute_mechanism_plausibility_score_no_mechanism_column(self):
        """No primary_mechanism column -> neutral score 0.5."""
        rows = [{"electron_phonon_lambda": 1.0, "predicted_Tc_K": 30}]
        df = _make_synth_df(rows)
        # Remove primary_mechanism if it got added by _make_synth_df
        if "primary_mechanism" in df.columns:
            df = df.drop(columns=["primary_mechanism"])
        score = compute_mechanism_plausibility_score(df)
        assert score == pytest.approx(0.5, abs=1e-6)

    def test_compute_mechanism_plausibility_score_all_plausible(self):
        """All BCS with reasonable lambda and Tc -> high plausibility."""
        rows = [
            {"primary_mechanism": "bcs", "electron_phonon_lambda": 1.0, "predicted_Tc_K": 30}
            for _ in range(10)
        ]
        df = _make_synth_df(rows)
        score = compute_mechanism_plausibility_score(df)
        assert score == pytest.approx(1.0, abs=1e-6)
