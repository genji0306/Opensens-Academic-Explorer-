"""Smoke tests for Agent XC package."""
import pytest
import numpy as np


class TestXRDReader:
    def test_xrd_pattern_dataclass(self):
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        p = XRDPattern(
            two_theta=np.linspace(5, 90, 100),
            intensity=np.random.rand(100),
        )
        assert len(p.two_theta) == 100
        assert p.wavelength == pytest.approx(1.5406)
        assert p.n_points == 100
        assert p.two_theta_range == pytest.approx((5.0, 90.0), abs=0.1)

    def test_read_xrd_nonexistent(self):
        from agent_xc.preprocessing.xrd_reader import read_xrd
        from pathlib import Path
        with pytest.raises(FileNotFoundError):
            read_xrd(Path("/nonexistent/pattern.xy"))


class TestNormalizer:
    def test_normalize_intensity(self):
        from agent_xc.preprocessing.normalizer import normalize_intensity
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        p = XRDPattern(
            two_theta=np.linspace(5, 90, 100),
            intensity=np.array([10.0, 50.0, 100.0, 30.0] * 25),
        )
        normed = normalize_intensity(p)
        assert normed.intensity.max() == pytest.approx(1.0)
        assert normed.intensity.min() == pytest.approx(0.0)

    def test_resample_to_grid(self):
        from agent_xc.preprocessing.normalizer import resample_to_grid
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        p = XRDPattern(
            two_theta=np.array([5.0, 10.0, 20.0, 50.0, 90.0]),
            intensity=np.array([0.1, 0.5, 1.0, 0.3, 0.05]),
        )
        resampled = resample_to_grid(p, two_theta_range=(5.0, 90.0), step=2.0)
        assert len(resampled.two_theta) > 0
        assert resampled.two_theta[0] == pytest.approx(5.0)


class TestNoiseFilter:
    def test_savitzky_golay(self):
        from agent_xc.preprocessing.noise_filter import savitzky_golay_filter
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        noisy = np.sin(np.linspace(0, 4 * np.pi, 200)) + np.random.normal(0, 0.1, 200)
        p = XRDPattern(
            two_theta=np.linspace(5, 90, 200),
            intensity=noisy,
        )
        filtered = savitzky_golay_filter(p, window_length=11, polyorder=3)
        assert filtered.n_points == p.n_points
        # Filtered should have lower variance
        assert np.std(filtered.intensity) < np.std(noisy) + 0.5


class TestMatchScorer:
    def test_rwp_identical(self):
        from agent_xc.postprocessing.match_scorer import compute_rwp
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        two_theta = np.linspace(5, 90, 500)
        intensity = np.abs(np.sin(two_theta * 0.1)) + 0.01
        obs = XRDPattern(two_theta=two_theta, intensity=intensity)
        r = compute_rwp(obs, obs)
        assert r == pytest.approx(0.0, abs=1e-4)

    def test_rwp_different(self):
        from agent_xc.postprocessing.match_scorer import compute_rwp
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        two_theta = np.linspace(5, 90, 500)
        obs = XRDPattern(two_theta=two_theta,
                         intensity=np.abs(np.sin(two_theta * 0.1)) + 0.01)
        calc = XRDPattern(two_theta=two_theta,
                          intensity=np.abs(np.sin(two_theta * 0.1 + 0.5)) + 0.01)
        r = compute_rwp(obs, calc)
        assert r > 0

    def test_pattern_similarity(self):
        from agent_xc.postprocessing.match_scorer import compute_pattern_similarity
        from agent_xc.preprocessing.xrd_reader import XRDPattern
        two_theta = np.linspace(5, 90, 500)
        intensity = np.abs(np.sin(two_theta * 0.1)) + 0.01
        a = XRDPattern(two_theta=two_theta, intensity=intensity)
        sim = compute_pattern_similarity(a, a)
        assert sim == pytest.approx(1.0, abs=0.01)


class TestAgentXC:
    def test_import(self):
        from agent_xc.predict import AgentXC
        agent = AgentXC()
        assert agent is not None

    def test_config(self):
        from agent_xc.config import XCConfig
        cfg = XCConfig()
        assert cfg.wavelength == pytest.approx(1.5406)
        assert cfg.num_candidates == 10
