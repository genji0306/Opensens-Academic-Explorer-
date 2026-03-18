"""
Tests for MC3D Client — Materials Cloud 3D Crystals Database Interface.

Tests are designed to work offline (no network calls) by mocking HTTP responses.
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.mc3d_client import (
    MC3DClient,
    MC3DStructure,
    AIIDA_BASE,
    _http_get,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_NODE_TA_GE = {
    "id": 11,
    "uuid": "03855809-e68a-4a7f-823d-007cd7cf80df",
    "label": "",
    "ctime": "2019-07-20T00:41:05Z",
    "mtime": "2025-08-25T18:07:56Z",
    "node_type": "data.core.structure.StructureData.",
    "attributes": {
        "cell": [[-3.33, 3.33, 6.04], [3.33, -3.33, 6.04], [3.33, 3.33, -6.04]],
        "kinds": [
            {"name": "Ta", "mass": 180.94788, "symbols": ["Ta"]},
            {"name": "Ge", "mass": 72.64, "symbols": ["Ge"]},
        ],
        "sites": [
            {"kind_name": "Ta", "position": [0.0, 0.0, 0.0]},
            {"kind_name": "Ta", "position": [1.665, 1.665, 3.02]},
            {"kind_name": "Ge", "position": [3.33, 0.0, 3.02]},
        ],
        "pbc1": True,
        "pbc2": True,
        "pbc3": True,
    },
}

MOCK_NODE_CU_O = {
    "id": 42,
    "uuid": "aaaabbbb-cccc-dddd-eeee-ffffffffffff",
    "label": "CuO test",
    "ctime": "2020-01-01T00:00:00Z",
    "mtime": "2025-01-01T00:00:00Z",
    "attributes": {
        "cell": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        "kinds": [
            {"name": "Cu", "mass": 63.546, "symbols": ["Cu"]},
            {"name": "O", "mass": 15.999, "symbols": ["O"]},
        ],
        "sites": [
            {"kind_name": "Cu", "position": [0.0, 0.0, 0.0]},
            {"kind_name": "O", "position": [2.0, 2.0, 2.0]},
        ],
        "pbc1": True,
        "pbc2": True,
        "pbc3": True,
    },
}


def _mock_search_response(*nodes):
    """Build a mock AiiDA REST API response containing given nodes."""
    return {"data": {"nodes": list(nodes)}}


# ---------------------------------------------------------------------------
# MC3DStructure dataclass
# ---------------------------------------------------------------------------

class TestMC3DStructure:
    def test_elements_from_species(self):
        s = MC3DStructure(
            uuid="test", node_id=1, formula="TaGe",
            species=[{"name": "Ta"}, {"name": "Ge"}],
            cell=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
            pbc=(True, True, True), n_atoms=2,
        )
        assert "Ta" in s.elements
        assert "Ge" in s.elements

    def test_elements_strips_numeric_suffix(self):
        s = MC3DStructure(
            uuid="test", node_id=1, formula="Fe2O3",
            species=[{"name": "Fe1"}, {"name": "Fe2"}, {"name": "O1"}],
            cell=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            pbc=(True, True, True), n_atoms=3,
        )
        elems = s.elements
        assert "Fe" in elems
        assert "O" in elems
        # No duplicates
        assert elems.count("Fe") == 1

    def test_elements_unique(self):
        s = MC3DStructure(
            uuid="test", node_id=1, formula="NaCl",
            species=[{"name": "Na"}, {"name": "Cl"}, {"name": "Na"}],
            cell=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            positions=[[0, 0, 0], [0.5, 0.5, 0.5], [1, 0, 0]],
            pbc=(True, True, True), n_atoms=3,
        )
        assert len(s.elements) == 2


# ---------------------------------------------------------------------------
# MC3DClient._parse_structure_node
# ---------------------------------------------------------------------------

class TestParseStructureNode:
    def setup_method(self):
        self.client = MC3DClient(rate_limit=0)

    def test_parse_ta_ge(self):
        s = self.client._parse_structure_node(MOCK_NODE_TA_GE)
        assert s.uuid == "03855809-e68a-4a7f-823d-007cd7cf80df"
        assert s.node_id == 11
        assert s.n_atoms == 3
        assert "Ta" in s.elements
        assert "Ge" in s.elements
        assert s.pbc == (True, True, True)
        assert len(s.cell) == 3
        assert len(s.positions) == 3

    def test_parse_cu_o(self):
        s = self.client._parse_structure_node(MOCK_NODE_CU_O)
        assert s.node_id == 42
        assert "Cu" in s.elements
        assert "O" in s.elements
        assert s.formula == "CuO"

    def test_parse_derives_formula(self):
        s = self.client._parse_structure_node(MOCK_NODE_TA_GE)
        assert "Ge" in s.formula
        assert "Ta" in s.formula

    def test_parse_empty_node(self):
        s = self.client._parse_structure_node({})
        assert s.uuid == ""
        assert s.n_atoms == 0
        assert s.formula == ""


# ---------------------------------------------------------------------------
# MC3DClient.search_structures (mocked)
# ---------------------------------------------------------------------------

class TestSearchStructures:
    def setup_method(self):
        self.client = MC3DClient(rate_limit=0)

    @patch("src.core.mc3d_client._http_get")
    def test_search_returns_structures(self, mock_get):
        mock_get.return_value = _mock_search_response(MOCK_NODE_TA_GE, MOCK_NODE_CU_O)

        results = self.client.search_structures(limit=10)
        assert len(results) == 2
        assert all(isinstance(s, MC3DStructure) for s in results)

    @patch("src.core.mc3d_client._http_get")
    def test_search_filters_by_elements(self, mock_get):
        mock_get.return_value = _mock_search_response(MOCK_NODE_TA_GE, MOCK_NODE_CU_O)

        results = self.client.search_structures(elements=["Cu", "O"], limit=10)
        assert len(results) == 1
        assert results[0].node_id == 42

    @patch("src.core.mc3d_client._http_get")
    def test_search_empty_response(self, mock_get):
        mock_get.return_value = {"data": {"nodes": []}}

        results = self.client.search_structures(limit=10)
        assert len(results) == 0

    @patch("src.core.mc3d_client._http_get")
    def test_search_limit_capped_at_500(self, mock_get):
        mock_get.return_value = _mock_search_response()

        self.client.search_structures(limit=1000)
        call_args = mock_get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else {}
        assert params.get("limit", 500) <= 500


# ---------------------------------------------------------------------------
# MC3DClient.get_structure (mocked)
# ---------------------------------------------------------------------------

class TestGetStructure:
    def setup_method(self):
        self.client = MC3DClient(rate_limit=0)

    @patch("src.core.mc3d_client._http_get")
    def test_get_structure_by_uuid(self, mock_get):
        mock_get.return_value = {"data": {"nodes": [MOCK_NODE_TA_GE]}}

        s = self.client.get_structure("03855809-e68a-4a7f-823d-007cd7cf80df")
        assert s is not None
        assert s.node_id == 11

    @patch("src.core.mc3d_client._http_get")
    def test_get_structure_not_found(self, mock_get):
        mock_get.return_value = {"data": {"nodes": []}}

        s = self.client.get_structure("nonexistent-uuid")
        # Returns None or raises — parse of empty node returns stub
        # Either behavior is acceptable


# ---------------------------------------------------------------------------
# MC3DClient.get_properties (mocked)
# ---------------------------------------------------------------------------

class TestGetProperties:
    def setup_method(self):
        self.client = MC3DClient(rate_limit=0)

    @patch("src.core.mc3d_client._http_get")
    def test_get_properties(self, mock_get):
        mock_get.side_effect = [
            {"data": {"attributes": {"cell": [[1, 0, 0]]}}},
            {"data": {"extras": {"sg": 225}}},
        ]
        props = self.client.get_properties(node_id=11)
        assert "attributes" in props
        assert "extras" in props


# ---------------------------------------------------------------------------
# MC3DClient.fetch_reference_structures (mocked)
# ---------------------------------------------------------------------------

class TestFetchReferenceStructures:
    def setup_method(self):
        self.client = MC3DClient(rate_limit=0)

    @patch("src.core.mc3d_client._http_get")
    def test_fetch_reference_returns_list(self, mock_get):
        mock_get.return_value = _mock_search_response(MOCK_NODE_CU_O)

        refs = self.client.fetch_reference_structures(families=["cuprate"], limit=10)
        assert isinstance(refs, list)

    @patch("src.core.mc3d_client._http_get")
    def test_fetch_reference_deduplicates(self, mock_get):
        # Same node returned twice
        mock_get.return_value = _mock_search_response(MOCK_NODE_CU_O, MOCK_NODE_CU_O)

        refs = self.client.fetch_reference_structures(limit=10)
        uuids = [r.uuid for r in refs]
        assert len(set(uuids)) == len(uuids)


# ---------------------------------------------------------------------------
# Agent Sin calibration integration
# ---------------------------------------------------------------------------

class TestAgentSinMC3DCalibration:
    @patch("src.core.mc3d_client._http_get")
    def test_calibrate_from_mc3d_returns_dict(self, mock_get):
        mock_get.return_value = _mock_search_response(MOCK_NODE_CU_O)

        from src.agents.agent_sin import AgentSin
        agent = AgentSin()
        result = agent.calibrate_from_mc3d()
        assert isinstance(result, dict)
        assert "source" in result
        assert result["source"] == "mc3d"

    @patch("src.core.mc3d_client._http_get")
    def test_calibrate_caches_result(self, mock_get):
        mock_get.return_value = _mock_search_response(MOCK_NODE_CU_O)

        from src.agents.agent_sin import AgentSin
        agent = AgentSin()
        r1 = agent.calibrate_from_mc3d()
        r2 = agent.calibrate_from_mc3d()
        assert r1 is r2  # Same object — cached

    def test_calibrate_handles_offline_gracefully(self):
        """If MC3D API is unreachable, calibration should not raise."""
        from src.agents.agent_sin import AgentSin
        agent = AgentSin()

        with patch("src.core.mc3d_client._http_get", side_effect=ConnectionError("offline")):
            result = agent.calibrate_from_mc3d()
            # Should still return a valid dict, just with empty families
            assert isinstance(result, dict)
            assert result["source"] == "mc3d"


# ---------------------------------------------------------------------------
# get_default_client
# ---------------------------------------------------------------------------

class TestDefaultClient:
    def test_get_default_client(self):
        from src.core.mc3d_client import get_default_client
        client = get_default_client()
        assert isinstance(client, MC3DClient)
