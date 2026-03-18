"""
Integration tests for RTAP agent infrastructure.

Verifies that RTAP families, score weights, seed patterns, and Tc model
dispatching are properly wired across Agent CS, Agent Ob, and config.
"""
import sys
import os
import inspect

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Seed patterns include RTAP families
# ---------------------------------------------------------------------------

class TestSeedPatternsRTAPFamilies:
    def test_seed_patterns_include_rtap_families(self):
        """At least 3 RTAP families (kagome, ternary-hydride, infinite-layer)
        should appear in SEED_PATTERNS pattern_ids."""
        from src.agents.agent_cs import SEED_PATTERNS

        pattern_ids = [p.pattern_id for p in SEED_PATTERNS]
        pattern_ids_str = " ".join(pattern_ids)

        rtap_families_found = []
        for family in ["kagome", "ternary-hydride", "infinite-layer"]:
            if any(family in pid for pid in pattern_ids):
                rtap_families_found.append(family)

        assert len(rtap_families_found) >= 3, (
            f"Only found {len(rtap_families_found)} RTAP families in SEED_PATTERNS: "
            f"{rtap_families_found}. Expected at least 3 from "
            f"[kagome, ternary-hydride, infinite-layer]"
        )

    def test_seed_patterns_have_pattern_cards(self):
        """All SEED_PATTERNS entries should be PatternCard dataclass instances."""
        from src.agents.agent_cs import SEED_PATTERNS
        from src.core.schemas import PatternCard

        for pattern in SEED_PATTERNS:
            assert isinstance(pattern, PatternCard), (
                f"Pattern {getattr(pattern, 'pattern_id', '?')} is not a PatternCard"
            )


# ---------------------------------------------------------------------------
# RTAP_FAMILIES configuration
# ---------------------------------------------------------------------------

class TestRTAPFamiliesConfig:
    def test_rtap_families_count(self):
        """RTAP_FAMILIES should have at least 14 entries."""
        from src.core.config import RTAP_FAMILIES

        assert len(RTAP_FAMILIES) >= 14, (
            f"RTAP_FAMILIES has {len(RTAP_FAMILIES)} entries, expected >= 14"
        )

    def test_rtap_families_includes_core_families(self):
        """RTAP_FAMILIES should include cuprate, nickelate, hydride, kagome."""
        from src.core.config import RTAP_FAMILIES

        for family in ["cuprate", "nickelate", "hydride", "kagome"]:
            assert family in RTAP_FAMILIES, f"{family} not in RTAP_FAMILIES"


# ---------------------------------------------------------------------------
# RTAP_SCORE_WEIGHTS configuration
# ---------------------------------------------------------------------------

class TestRTAPScoreWeights:
    def test_rtap_score_weights_sum(self):
        """RTAP_SCORE_WEIGHTS values should sum to approximately 1.0."""
        from src.core.config import RTAP_SCORE_WEIGHTS

        total = sum(RTAP_SCORE_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=0.01), (
            f"RTAP_SCORE_WEIGHTS sum = {total:.4f}, expected ~1.0"
        )

    def test_rtap_score_weights_all_positive(self):
        """All weights should be positive."""
        from src.core.config import RTAP_SCORE_WEIGHTS

        for key, val in RTAP_SCORE_WEIGHTS.items():
            assert val > 0, f"Weight for {key} is {val}, expected > 0"

    def test_rtap_score_weights_ambient_tc_highest(self):
        """ambient_tc_score should be the highest weight (primary objective)."""
        from src.core.config import RTAP_SCORE_WEIGHTS

        max_key = max(RTAP_SCORE_WEIGHTS, key=RTAP_SCORE_WEIGHTS.get)
        assert max_key == "ambient_tc_score", (
            f"Highest weight is {max_key} ({RTAP_SCORE_WEIGHTS[max_key]:.2f}), "
            f"expected ambient_tc_score"
        )


# ---------------------------------------------------------------------------
# Tc model dispatch routing
# ---------------------------------------------------------------------------

class TestTcModelsDispatch:
    def test_tc_models_dispatch_routes_bcs(self):
        """estimate_tc_composite('bcs', ...) returns mechanism='bcs'."""
        from src.core.tc_models import estimate_tc_composite

        result = estimate_tc_composite("bcs", lambda_ep=1.0, omega_log_K=300)
        assert isinstance(result, dict)
        assert result["mechanism"] == "bcs"
        assert result["Tc_K"] > 0

    def test_tc_models_dispatch_routes_flat_band(self):
        """estimate_tc_composite('flat_band', ...) returns mechanism='flat_band'."""
        from src.core.tc_models import estimate_tc_composite

        result = estimate_tc_composite(
            "flat_band", lambda_ep=1.0, omega_log_K=200, W_bandwidth_eV=0.02,
        )
        assert isinstance(result, dict)
        assert result["mechanism"] == "flat_band"
        assert result["Tc_K"] > 0

    def test_tc_models_dispatch_routes_hydride_cage(self):
        """estimate_tc_composite('hydride_cage', ...) returns mechanism='hydride_cage'."""
        from src.core.tc_models import estimate_tc_composite

        result = estimate_tc_composite(
            "hydride_cage", lambda_ep=2.0, omega_log_K=1200,
            H_fraction=0.75, stabilizer_electronegativity=1.5,
        )
        assert result["mechanism"] == "hydride_cage"

    def test_tc_models_dispatch_routes_spin_fluctuation(self):
        """estimate_tc_composite('spin_fluctuation', ...) routes correctly."""
        from src.core.tc_models import estimate_tc_composite

        result = estimate_tc_composite(
            "spin_fluctuation", lambda_ep=0.5, T_sf_K=500,
        )
        assert result["mechanism"] == "spin_fluctuation"


# ---------------------------------------------------------------------------
# Agent Ob accepts RTAP mode
# ---------------------------------------------------------------------------

class TestAgentObRTAPMode:
    def test_agent_ob_accepts_rtap_mode(self):
        """run_agent_ob function signature accepts 'mode' parameter."""
        from src.agents.agent_ob import run_agent_ob

        sig = inspect.signature(run_agent_ob)
        assert "mode" in sig.parameters, (
            f"run_agent_ob signature {sig} does not include 'mode' parameter"
        )

    def test_agent_ob_mode_default_is_v1(self):
        """Default value for 'mode' parameter should be 'v1'."""
        from src.agents.agent_ob import run_agent_ob

        sig = inspect.signature(run_agent_ob)
        mode_param = sig.parameters["mode"]
        assert mode_param.default == "v1", (
            f"run_agent_ob mode default is {mode_param.default!r}, expected 'v1'"
        )

    def test_agent_ob_compute_convergence_accepts_mode(self):
        """AgentOb.compute_convergence also accepts 'mode' parameter."""
        from src.agents.agent_ob import AgentOb

        sig = inspect.signature(AgentOb.compute_convergence)
        assert "mode" in sig.parameters, (
            f"AgentOb.compute_convergence signature {sig} does not include 'mode'"
        )
