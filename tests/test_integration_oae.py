"""OAE Integration Tests — End-to-end verification across all phases."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Phase 0: OAE Rename ────────────────────────────────────────────────

class TestOAEBranding:
    def test_oae_cli_help(self):
        """oae.py --help shows OAE branding."""
        result = subprocess.run(
            [sys.executable, "oae.py", "--list-protocols"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0
        assert "OAE Laboratory" in result.stdout

    def test_run_py_still_works(self):
        """run.py is still importable (backward compat)."""
        result = subprocess.run(
            [sys.executable, "-c", "import run; print('ok')"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0
        assert "ok" in result.stdout


# ── Phase 1: Database Layer ─────────────────────────────────────────────

class TestDatabaseIntegration:
    def test_registry_and_nemad_adapter_together(self):
        """DataRegistry can store entries produced by NemadAdapter."""
        from src.core.data_registry import DataRegistry
        from src.core.nemad_adapter import NemadAdapter

        with tempfile.TemporaryDirectory() as tmp:
            reg = DataRegistry(path=Path(tmp) / "reg.json")
            adapter = NemadAdapter(dataset_dir=Path("/nonexistent"))
            # Even with missing data, adapter returns empty safely
            entries = adapter.load_all()
            assert isinstance(entries, list)
            # Add a synthetic entry
            reg.add({
                "material_type": "magnetic",
                "composition": "Fe3O4",
                "source": "nemad",
                "properties": {"curie_temp_K": 858},
                "tags": ["nemad-fm", "integration-test"],
            })
            found = reg.find_by_type("magnetic")
            assert len(found) == 1
            assert found[0]["composition"] == "Fe3O4"

    def test_material_entry_schema(self):
        """MaterialEntry works for all material types."""
        from src.core.schemas import MaterialEntry
        for mt in ("superconductor", "magnetic", "crystal", "general"):
            entry = MaterialEntry(
                material_id=f"test-{mt}",
                material_type=mt,
                composition="NaCl",
                source="test",
            )
            assert entry.material_type == mt

    def test_json_datasets_exist(self):
        """Externalized JSON datasets are present."""
        datasets_dir = PROJECT_ROOT / "data" / "datasets"
        expected = [
            "supercon_24.json",
            "icsd_ref_30.json",
            "formation_energy_25.json",
            "rtap_candidates_40.json",
            "high_tc_reference_15.json",
        ]
        for name in expected:
            path = datasets_dir / name
            assert path.exists(), f"Missing dataset: {name}"
            data = json.loads(path.read_text())
            assert len(data) > 0, f"Empty dataset: {name}"

    def test_benchmarks_datasets_load(self):
        """benchmarks.datasets still loads all datasets correctly."""
        from benchmarks.datasets import (
            load_supercon_24, load_icsd_ref_30,
            load_formation_energy_25, load_rtap_candidates_40,
            load_high_tc_reference_15,
        )
        assert len(load_supercon_24()) >= 8
        assert len(load_icsd_ref_30()) >= 10
        assert len(load_formation_energy_25()) >= 10
        assert len(load_rtap_candidates_40()) >= 10
        assert len(load_high_tc_reference_15()) >= 5


# ── Phase 2: Crystal Editor ─────────────────────────────────────────────

class TestCrystalEditorIntegration:
    def test_editor_cif_roundtrip(self):
        """Create structure -> export CIF -> re-import -> verify."""
        from agent_v.editor.crystal_editor import CrystalEditor

        # Build a YBaCuO structure
        editor = CrystalEditor()
        editor.set_lattice(a=3.82, b=3.82, c=11.68)
        editor.set_space_group("P4/mmm")
        editor.add_atom("Y", 0.5, 0.5, 0.5)
        editor.add_atom("Ba", 0.5, 0.5, 0.185)
        editor.add_atom("Cu", 0.0, 0.0, 0.0)
        editor.add_atom("O", 0.5, 0.0, 0.0)

        # Export CIF
        cif_text = editor.to_cif()
        assert "P4/mmm" in cif_text
        assert "3.820000" in cif_text

        # Re-import
        editor2 = CrystalEditor.from_cif(cif_text)
        assert len(editor2.atoms) == 4
        assert editor2.space_group == "P4/mmm"
        assert abs(editor2.lattice.a - 3.82) < 0.001
        assert abs(editor2.lattice.c - 11.68) < 0.001

    def test_editor_cif_file_roundtrip(self):
        """Export CIF to file -> re-import from file."""
        from agent_v.editor.crystal_editor import CrystalEditor

        editor = CrystalEditor()
        editor.set_lattice(a=5.64, b=5.64, c=5.64)
        editor.add_atom("Na", 0.0, 0.0, 0.0)
        editor.add_atom("Cl", 0.5, 0.5, 0.5)

        with tempfile.NamedTemporaryFile(suffix=".cif", delete=False) as f:
            tmp_path = Path(f.name)

        try:
            editor.export_cif(tmp_path)
            assert tmp_path.exists()

            editor2 = CrystalEditor.from_cif_file(tmp_path)
            assert len(editor2.atoms) == 2
            assert abs(editor2.lattice.a - 5.64) < 0.001
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_editor_undo_redo_chain(self):
        """Complex undo/redo sequence preserves integrity."""
        from agent_v.editor.crystal_editor import CrystalEditor

        editor = CrystalEditor()
        editor.add_atom("Fe", 0, 0, 0)     # state 1
        editor.add_atom("Se", 0.5, 0.5, 0) # state 2
        editor.add_atom("O", 0.5, 0, 0.5)  # state 3

        assert len(editor.atoms) == 3
        editor.undo()  # back to state 2
        assert len(editor.atoms) == 2
        editor.undo()  # back to state 1
        assert len(editor.atoms) == 1
        editor.redo()  # forward to state 2
        assert len(editor.atoms) == 2

        # Add new atom clears redo
        editor.add_atom("N", 0, 0, 0.5)
        assert len(editor.atoms) == 3
        assert not editor.can_redo

    def test_editor_dict_serialization(self):
        """to_dict/from_dict round-trip (used by Dash dcc.Store)."""
        from agent_v.editor.crystal_editor import CrystalEditor

        editor = CrystalEditor()
        editor.set_lattice(a=3.0, b=4.0, c=5.0, alpha=90, beta=90, gamma=120)
        editor.set_space_group("P63/mmc")
        editor.add_atom("Mg", 0, 0, 0)
        editor.add_atom("B", 0.333, 0.667, 0.5)

        d = editor.to_dict()
        assert isinstance(d, dict)

        editor2 = CrystalEditor.from_dict(d)
        assert len(editor2.atoms) == 2
        assert editor2.space_group == "P63/mmc"
        assert abs(editor2.lattice.gamma - 120) < 0.001

    def test_editor_layout_importable(self):
        """Editor layout module creates valid Dash layout."""
        from agent_v.editor.editor_layout import create_editor_layout
        layout = create_editor_layout()
        assert layout is not None


# ── Phase 3: NeMAD Comparison ────────────────────────────────────────────

class TestNemadComparisonIntegration:
    def test_full_comparison_run(self):
        """Run comparison on 10 compounds and verify report structure."""
        from benchmarks.nemad_comparison import run_comparison
        report = run_comparison(max_compounds=10)

        assert report["n_compounds"] == 10
        assert "classification" in report
        assert "temperature" in report
        assert "oae_strengths" in report
        assert "nemad_strengths" in report
        assert "summary" in report
        assert 0 <= report["summary"]["classification_accuracy"] <= 1.0

    def test_comparison_report_export(self):
        """Generate and save comparison report as JSON."""
        from benchmarks.nemad_comparison import run_comparison, generate_report_file
        report = run_comparison(max_compounds=5)

        with tempfile.TemporaryDirectory() as tmp:
            path = generate_report_file(report, output_path=Path(tmp) / "report.json")
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["n_compounds"] == 5

    def test_comparison_cli(self):
        """CLI --compounds flag works."""
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.nemad_comparison", "--compounds", "5"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0
        assert "total_overlap" in result.stdout

    def test_metrics_functions_work(self):
        """New metrics in benchmarks.metrics are functional."""
        from benchmarks.metrics import classification_agreement, temperature_correlation
        acc = classification_agreement(["FM", "AFM", "NM"], ["FM", "AFM", "FM"])
        assert 0 <= acc <= 1.0
        corr = temperature_correlation([100, 200, 300], [110, 190, 310])
        assert -1 <= corr <= 1


# ── Phase 4: Laboratory Module ───────────────────────────────────────────

class TestLaboratoryIntegration:
    def test_all_protocols_loadable(self):
        """All 6 built-in protocols load and have valid structure."""
        from laboratory.registry import list_protocols, get_protocol
        protocols = list_protocols()
        assert len(protocols) >= 6

        for p in protocols:
            proto = get_protocol(p["protocol_id"])
            assert proto is not None
            assert len(proto.stages) >= 2
            assert proto.material_type in ("superconductor", "magnetic", "crystal")

    def test_discovery_protocol_execute(self):
        """Discovery protocol runs (all stages have dispatch handlers)."""
        from laboratory.registry import get_protocol
        from laboratory.runner import LabRunner

        proto = get_protocol("discovery")
        runner = LabRunner()
        result = runner.execute(proto)

        assert result["protocol_id"] == "discovery"
        assert result["total_stages"] == len(proto.stages)
        assert "results" in result
        assert result["elapsed_s"] >= 0

    def test_protocol_checkpoint_and_resume(self):
        """Protocol checkpoint save and resume cycle."""
        from laboratory.protocol import LabProtocol, ProtocolStage
        from laboratory.runner import LabRunner, CHECKPOINT_DIR

        protocol = LabProtocol(
            protocol_id="test-integration-cp",
            name="Integration Checkpoint",
            description="Test checkpoint/resume",
            stages=[
                ProtocolStage(name="S1", agent="agent_v", action="render",
                              checkpoint=True, optional=True),
                ProtocolStage(name="S2", agent="agent_v", action="render",
                              optional=True),
            ],
        )
        runner = LabRunner()
        runner.execute(protocol)

        cp_path = CHECKPOINT_DIR / "checkpoint_test-integration-cp_0.json"
        assert cp_path.exists()

        data = json.loads(cp_path.read_text())
        assert data["protocol_id"] == "test-integration-cp"
        assert data["stage_name"] == "S1"

        # Cleanup
        cp_path.unlink(missing_ok=True)

    def test_list_protocols_cli(self):
        """OAE CLI --list-protocols shows all protocols."""
        result = subprocess.run(
            [sys.executable, "oae.py", "--list-protocols"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0
        for pid in ["discovery", "structure_prediction", "xrd_analysis",
                     "magnetic_study", "rtap_exploration", "verification"]:
            assert pid in result.stdout

    def test_protocol_cli_execution(self):
        """OAE CLI --protocol runs a protocol."""
        result = subprocess.run(
            [sys.executable, "oae.py", "--protocol", "verification"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )
        assert result.returncode == 0
        assert "Completed" in result.stdout


# ── Cross-Phase Integration ──────────────────────────────────────────────

class TestCrossPhaseIntegration:
    def test_nemad_adapter_to_registry(self):
        """Phase 1+3: NemadAdapter data can be registered in DataRegistry."""
        from src.core.data_registry import DataRegistry
        from benchmarks.nemad_comparison import OVERLAP_COMPOUNDS

        with tempfile.TemporaryDirectory() as tmp:
            reg = DataRegistry(path=Path(tmp) / "reg.json")
            for c in OVERLAP_COMPOUNDS[:5]:
                reg.add({
                    "material_type": "magnetic",
                    "composition": c["composition"],
                    "source": "nemad",
                    "properties": {
                        "nemad_class": c["nemad_class"],
                        "oae_family": c["oae_family"],
                    },
                    "tags": ["overlap"],
                })
            found = reg.find_by_type("magnetic")
            assert len(found) == 5

    def test_editor_with_registry_structure(self):
        """Phase 1+2: Editor can build structures for registry materials."""
        from agent_v.editor.crystal_editor import CrystalEditor

        # Build structure for a material that could come from registry
        editor = CrystalEditor()
        editor.set_lattice(a=2.87, b=2.87, c=2.87, alpha=90, beta=90, gamma=90)
        editor.set_space_group("Im-3m")
        editor.add_atom("Fe", 0.0, 0.0, 0.0)

        d = editor.to_dict()
        assert d["space_group"] == "Im-3m"
        assert len(d["atoms"]) == 1

        # Validate
        warnings = editor.validate()
        assert not any("No atoms" in w for w in warnings)

    def test_protocol_uses_nemad_agent(self):
        """Phase 3+4: magnetic_study protocol references nemad agent."""
        from laboratory.registry import get_protocol
        proto = get_protocol("magnetic_study")
        agents = [s.agent for s in proto.stages]
        assert "nemad" in agents
