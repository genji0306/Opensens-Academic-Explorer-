"""Smoke tests for Agent V package."""
import pytest


class TestConfig:
    def test_cpk_colors(self):
        from agent_v.config import CPK_COLORS
        assert "C" in CPK_COLORS
        assert "O" in CPK_COLORS
        assert "Fe" in CPK_COLORS

    def test_family_colors(self):
        from agent_v.config import FAMILY_COLORS
        assert "cuprate" in FAMILY_COLORS
        assert "hydride" in FAMILY_COLORS


class TestCIFGenerator:
    def test_import(self):
        from agent_v.cif.generator import CIFGenerator
        gen = CIFGenerator()
        assert gen is not None

    def test_from_crystal_card(self):
        from agent_v.cif.generator import CIFGenerator
        card = {
            "formula": "NaCl",
            "space_group": "Fm-3m",
            "space_group_number": 225,
            "lattice": {"a": 5.64, "b": 5.64, "c": 5.64,
                        "alpha": 90.0, "beta": 90.0, "gamma": 90.0},
            "sites": [
                {"element": "Na", "x": 0.0, "y": 0.0, "z": 0.0},
                {"element": "Cl", "x": 0.5, "y": 0.5, "z": 0.5},
            ],
        }
        cif_str = CIFGenerator.from_crystal_card(card)
        assert "data_" in cif_str
        assert "_cell_length_a" in cif_str
        assert "5.64" in cif_str


class TestCIFValidator:
    def test_import(self):
        from agent_v.cif.parser import CIFValidator
        v = CIFValidator()
        assert v is not None


class TestConvergenceMonitor:
    def test_import(self):
        from agent_v.monitors.convergence_monitor import ConvergenceMonitor
        mon = ConvergenceMonitor()
        assert mon is not None


class TestAgentStatusMonitor:
    def test_import(self):
        from agent_v.monitors.agent_status_monitor import AgentStatusMonitor
        mon = AgentStatusMonitor()
        assert mon is not None

    def test_get_agent_states_returns_dict(self):
        from agent_v.monitors.agent_status_monitor import AgentStatusMonitor
        mon = AgentStatusMonitor()
        status = mon.get_agent_states()
        assert isinstance(status, dict)


class TestStructureViewer:
    def test_import(self):
        from agent_v.viewers.structure_viewer import StructureViewer
        viewer = StructureViewer()
        assert viewer is not None


class TestArtifactGenerator:
    def test_import(self):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="superconductor")
        assert gen is not None

    def test_naming_convention(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="cuprate", export_dir=tmp_path)
        path = gen.next_path("architecture_flow")
        name = path.name
        # Format: cuprate_YYYYMMDD_001_architecture_flow.mp4
        parts = name.split("_", 3)
        assert parts[0] == "cuprate"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert parts[1].isdigit()
        assert parts[2] == "001"
        assert name.endswith("_architecture_flow.mp4")

    def test_round_increments(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="hydride", export_dir=tmp_path)
        p1 = gen.next_path("test_a")
        p2 = gen.next_path("test_b")
        p3 = gen.next_path("test_c")
        assert "_001_" in p1.name
        assert "_002_" in p2.name
        assert "_003_" in p3.name

    def test_generate_suite(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="superconductor", export_dir=tmp_path)
        paths = gen.generate_suite()
        assert len(paths) == 8
        names = [p.name for p in paths]
        assert any("architecture_flow" in n for n in names)
        assert any("score_radar" in n for n in names)

    def test_manifest_persists(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="magnetic", export_dir=tmp_path)
        gen.next_path("test")
        manifest_path = tmp_path / "artifact_manifest.json"
        assert manifest_path.exists()
        import json
        data = json.loads(manifest_path.read_text())
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["material_type"] == "magnetic"

    def test_list_templates(self):
        from agent_v.artifact_generator import ArtifactGenerator
        templates = ArtifactGenerator.list_templates()
        assert len(templates) == 8
        names = [t["name"] for t in templates]
        assert "architecture_flow" in names
        assert "convergence_pulse" in names

    def test_gif_format(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="cuprate", export_dir=tmp_path, fmt="gif")
        path = gen.next_path("test")
        assert path.name.endswith(".gif")

    def test_convenience_function(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator, artifact_path
        # Can't easily redirect export_dir for convenience func,
        # just verify it returns a Path
        path = artifact_path("cuprate", "test")
        assert path.name.startswith("cuprate_")
        assert path.name.endswith("_test.mp4")

    def test_list_artifacts_filter(self, tmp_path):
        from agent_v.artifact_generator import ArtifactGenerator
        gen = ArtifactGenerator(material_type="cuprate", export_dir=tmp_path)
        gen.next_path("a")
        gen.next_path("b")
        arts = gen.list_artifacts(material_type="cuprate")
        assert len(arts) == 2
        arts_none = gen.list_artifacts(material_type="hydride")
        assert len(arts_none) == 0
