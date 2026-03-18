"""Tests for OAE NEMAD Adapter — src/core/nemad_adapter.py."""
import sys
import os
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNemadAdapterHelpers:
    def test_formula_to_readable(self):
        from src.core.nemad_adapter import _formula_to_readable
        assert _formula_to_readable("Fe3.0O4.0") == "Fe3O4"
        assert _formula_to_readable("NaCl") == "NaCl"
        assert _formula_to_readable("MgB2.0") == "MgB2"

    def test_formula_to_readable_non_string(self):
        from src.core.nemad_adapter import _formula_to_readable
        assert _formula_to_readable(123) == "123"
        assert _formula_to_readable(None) == "None"

    def test_extract_elements(self):
        from src.core.nemad_adapter import _extract_elements
        assert _extract_elements("Fe3O4") == ["Fe", "O"]
        assert _extract_elements("YBa2Cu3O7") == ["Y", "Ba", "Cu", "O"]
        assert _extract_elements("NaCl") == ["Na", "Cl"]


class TestNemadAdapterMissing:
    """Test adapter behavior when dataset files are missing."""

    def test_load_fm_missing(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path("/nonexistent"))
        result = adapter.load_fm_curie()
        assert result == []

    def test_load_afm_missing(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path("/nonexistent"))
        result = adapter.load_afm_neel()
        assert result == []

    def test_load_classification_missing(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path("/nonexistent"))
        result = adapter.load_classification()
        assert result == []

    def test_load_all_missing(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path("/nonexistent"))
        result = adapter.load_all()
        assert result == []

    def test_count_missing(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path("/nonexistent"))
        counts = adapter.count()
        assert counts["fm_curie"] == 0
        assert counts["afm_neel"] == 0
        assert counts["classification"] == 0


class TestNemadAdapterWithCSV:
    """Test adapter with synthetic CSV data."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

        # Create a minimal FM CSV
        fm_csv = Path(self.tmp) / "FM_with_curie.csv"
        fm_csv.write_text(
            "Normalized_Composition,Mean_TC_K,Fe,O\n"
            "Fe3.0O4.0,858.0,3.0,4.0\n"
            "Co2.0O3.0,392.0,0.0,3.0\n"
        )

        # Create a minimal classification CSV
        cls_csv = Path(self.tmp) / "Classification_FM_AFM_NM.csv"
        cls_csv.write_text(
            "Normalized_Composition,Type\n"
            "Fe3.0O4.0,1\n"
            "MnO1.0,0\n"
            "NaCl1.0,2\n"
        )

    def test_load_fm_curie(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path(self.tmp))
        entries = adapter.load_fm_curie()
        assert len(entries) == 2
        assert entries[0]["composition"] == "Fe3O4"
        assert entries[0]["properties"]["curie_temp_K"] == 858.0
        assert entries[0]["source"] == "nemad"
        assert "nemad-fm" in entries[0]["tags"]

    def test_load_classification(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path(self.tmp))
        entries = adapter.load_classification()
        assert len(entries) == 3
        # Type=1 -> FM
        assert entries[0]["properties"]["magnetic_class"] == "FM"
        # Type=0 -> AFM
        assert entries[1]["properties"]["magnetic_class"] == "AFM"
        # Type=2 -> NM
        assert entries[2]["properties"]["magnetic_class"] == "NM"

    def test_count(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path(self.tmp))
        counts = adapter.count()
        assert counts["fm_curie"] == 2
        assert counts["classification"] == 3

    def test_caching(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path(self.tmp))
        first = adapter.load_fm_curie()
        second = adapter.load_fm_curie()
        assert first is second  # same object from cache

    def test_load_all_deduplicates(self):
        from src.core.nemad_adapter import NemadAdapter
        adapter = NemadAdapter(dataset_dir=Path(self.tmp))
        all_entries = adapter.load_all()
        compositions = [e["composition"] for e in all_entries]
        # Fe3O4 appears in both FM and classification, should be deduplicated
        assert compositions.count("Fe3O4") == 1


class TestGetDefaultAdapter:
    def test_factory(self):
        from src.core.nemad_adapter import get_default_adapter
        adapter = get_default_adapter()
        assert adapter is not None
