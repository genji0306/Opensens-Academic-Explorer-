"""Tests for OAE Data Registry — src/core/data_registry.py."""
import sys
import os
import json
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDataRegistryCRUD:
    def setup_method(self):
        from src.core.data_registry import DataRegistry
        self.tmp = tempfile.mkdtemp()
        self.reg = DataRegistry(path=Path(self.tmp) / "test_registry.json")

    def test_empty_registry(self):
        assert self.reg.count == 0
        assert len(self.reg) == 0

    def test_add_entry(self):
        mid = self.reg.add({
            "composition": "NaCl",
            "material_type": "crystal",
            "source": "user",
        })
        assert mid is not None
        assert self.reg.count == 1

    def test_get_entry(self):
        mid = self.reg.add({
            "material_id": "test-001",
            "composition": "MgB2",
            "material_type": "superconductor",
        })
        entry = self.reg.get("test-001")
        assert entry is not None
        assert entry["composition"] == "MgB2"

    def test_remove_entry(self):
        self.reg.add({"material_id": "del-001", "composition": "FeSe"})
        assert self.reg.remove("del-001") is True
        assert self.reg.get("del-001") is None
        assert self.reg.remove("nonexistent") is False

    def test_update_entry(self):
        self.reg.add({"material_id": "upd-001", "composition": "LaH10"})
        assert self.reg.update("upd-001", material_type="superconductor") is True
        entry = self.reg.get("upd-001")
        assert entry["material_type"] == "superconductor"

    def test_update_nonexistent(self):
        assert self.reg.update("nonexistent", foo="bar") is False


class TestDataRegistryQueries:
    def setup_method(self):
        from src.core.data_registry import DataRegistry
        self.tmp = tempfile.mkdtemp()
        self.reg = DataRegistry(path=Path(self.tmp) / "test_registry.json")
        self.reg.add({"material_id": "sc-001", "composition": "YBa2Cu3O7",
                       "material_type": "superconductor", "source": "agent_cs",
                       "tags": ["cuprate"]})
        self.reg.add({"material_id": "mag-001", "composition": "Fe3O4",
                       "material_type": "magnetic", "source": "nemad",
                       "tags": ["nemad-fm"]})
        self.reg.add({"material_id": "cry-001", "composition": "NaCl",
                       "material_type": "crystal", "source": "user",
                       "tags": []})

    def test_find_by_composition(self):
        results = self.reg.find_by_composition("Fe3O4")
        assert len(results) == 1
        assert results[0]["material_id"] == "mag-001"

    def test_find_by_type(self):
        results = self.reg.find_by_type("superconductor")
        assert len(results) == 1

    def test_find_by_source(self):
        results = self.reg.find_by_source("nemad")
        assert len(results) == 1

    def test_find_by_family(self):
        results = self.reg.find_by_family("cuprate")
        assert len(results) == 1

    def test_all_entries(self):
        assert len(self.reg.all_entries()) == 3

    def test_stats(self):
        stats = self.reg.stats()
        assert stats["total"] == 3
        assert stats["by_type"]["superconductor"] == 1
        assert stats["by_type"]["magnetic"] == 1


class TestDataRegistryPersistence:
    def test_save_and_reload(self):
        from src.core.data_registry import DataRegistry
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "persist_test.json"

        reg1 = DataRegistry(path=path)
        reg1.add({"material_id": "p-001", "composition": "MgB2"})
        reg1.save()

        reg2 = DataRegistry(path=path)
        assert reg2.count == 1
        assert reg2.get("p-001")["composition"] == "MgB2"

    def test_repr(self):
        from src.core.data_registry import DataRegistry
        tmp = tempfile.mkdtemp()
        reg = DataRegistry(path=Path(tmp) / "repr_test.json")
        assert "0 entries" in repr(reg)


class TestMaterialEntry:
    def test_material_entry_dataclass(self):
        from src.core.schemas import MaterialEntry
        entry = MaterialEntry(
            material_id="test-001",
            material_type="superconductor",
            composition="MgB2",
            source="agent_cs",
            tags=["mgb2-type"],
        )
        assert entry.material_id == "test-001"
        assert entry.composition == "MgB2"

    def test_material_entry_to_dict(self):
        from src.core.schemas import MaterialEntry
        entry = MaterialEntry(material_id="t", composition="NaCl")
        d = entry.to_dict()
        assert d["material_id"] == "t"
        assert d["composition"] == "NaCl"

    def test_material_entry_from_dict(self):
        from src.core.schemas import MaterialEntry
        d = {"material_id": "from-dict", "composition": "FeSe", "material_type": "superconductor"}
        entry = MaterialEntry.from_dict(d)
        assert entry.material_id == "from-dict"
        assert entry.material_type == "superconductor"
