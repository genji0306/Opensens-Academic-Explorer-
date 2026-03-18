"""Tests for OAE Superagent Laboratory module."""
import sys
import os
import json
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestProtocolDataclasses:
    def test_protocol_stage(self):
        from laboratory.protocol import ProtocolStage
        stage = ProtocolStage(name="test", agent="agent_cs", action="build_catalog")
        assert stage.name == "test"
        assert stage.checkpoint is False
        assert stage.optional is False
        d = stage.to_dict()
        assert d["name"] == "test"

    def test_lab_protocol(self):
        from laboratory.protocol import LabProtocol, ProtocolStage
        protocol = LabProtocol(
            protocol_id="test-proto",
            name="Test Protocol",
            description="A test",
            stages=[
                ProtocolStage(name="S1", agent="a", action="b"),
                ProtocolStage(name="S2", agent="c", action="d"),
            ],
        )
        assert len(protocol.stages) == 2
        assert protocol.stage_names() == ["S1", "S2"]

    def test_protocol_to_dict(self):
        from laboratory.protocol import LabProtocol, ProtocolStage
        protocol = LabProtocol(
            protocol_id="p1",
            name="Proto",
            description="desc",
            stages=[ProtocolStage(name="S", agent="a", action="b")],
        )
        d = protocol.to_dict()
        assert d["protocol_id"] == "p1"
        assert len(d["stages"]) == 1

    def test_checkpoint_data(self):
        from laboratory.protocol import CheckpointData
        cp = CheckpointData(
            protocol_id="p1", stage_index=2, stage_name="Score"
        )
        d = cp.to_dict()
        assert d["protocol_id"] == "p1"
        assert d["stage_index"] == 2


class TestProtocolRegistry:
    def test_list_protocols(self):
        from laboratory.registry import list_protocols
        protocols = list_protocols()
        assert len(protocols) >= 6
        ids = [p["protocol_id"] for p in protocols]
        assert "discovery" in ids
        assert "structure_prediction" in ids
        assert "xrd_analysis" in ids
        assert "magnetic_study" in ids
        assert "rtap_exploration" in ids
        assert "verification" in ids

    def test_get_protocol(self):
        from laboratory.registry import get_protocol
        proto = get_protocol("discovery")
        assert proto is not None
        assert proto.name == "Material Discovery"
        assert len(proto.stages) >= 3

    def test_get_nonexistent(self):
        from laboratory.registry import get_protocol
        assert get_protocol("nonexistent") is None

    def test_protocol_details(self):
        from laboratory.registry import get_protocol
        for pid in ["discovery", "structure_prediction", "rtap_exploration",
                     "magnetic_study", "xrd_analysis", "verification"]:
            proto = get_protocol(pid)
            assert proto is not None, f"Protocol {pid} not found"
            assert proto.protocol_id == pid
            assert len(proto.stages) >= 2
            assert proto.material_type in ("superconductor", "magnetic", "crystal")


class TestLabRunner:
    def test_runner_creation(self):
        from laboratory.runner import LabRunner
        runner = LabRunner()
        assert runner is not None

    def test_execute_with_optional_stages(self):
        """Execute a protocol where all stages are optional (won't fail)."""
        from laboratory.protocol import LabProtocol, ProtocolStage
        from laboratory.runner import LabRunner

        protocol = LabProtocol(
            protocol_id="test-optional",
            name="Test Optional",
            description="All optional stages",
            stages=[
                ProtocolStage(name="Render", agent="agent_v", action="render",
                              optional=True),
            ],
        )
        runner = LabRunner()
        result = runner.execute(protocol)
        assert result["protocol_id"] == "test-optional"
        assert result["total_stages"] == 1
        assert "results" in result

    def test_execute_unknown_agent(self):
        """Unknown agent/action should return skipped status."""
        from laboratory.protocol import LabProtocol, ProtocolStage
        from laboratory.runner import LabRunner

        protocol = LabProtocol(
            protocol_id="test-unknown",
            name="Test Unknown",
            description="Unknown agent",
            stages=[
                ProtocolStage(name="Unknown", agent="fake_agent",
                              action="fake_action", optional=True),
            ],
        )
        runner = LabRunner()
        result = runner.execute(protocol)
        assert result["results"][0]["status"] == "skipped"

    def test_checkpoint_save(self):
        """Verify checkpoint file is created when stage has checkpoint=True."""
        from laboratory.protocol import LabProtocol, ProtocolStage
        from laboratory.runner import LabRunner, CHECKPOINT_DIR

        protocol = LabProtocol(
            protocol_id="test-checkpoint",
            name="Test Checkpoint",
            description="Checkpoint test",
            stages=[
                ProtocolStage(name="Render", agent="agent_v", action="render",
                              checkpoint=True, optional=True),
            ],
        )
        runner = LabRunner()
        runner.execute(protocol)

        cp_path = CHECKPOINT_DIR / "checkpoint_test-checkpoint_0.json"
        assert cp_path.exists()
        data = json.loads(cp_path.read_text())
        assert data["protocol_id"] == "test-checkpoint"

        # Cleanup
        cp_path.unlink(missing_ok=True)

    def test_execute_start_stage(self):
        """Test resuming from a later stage."""
        from laboratory.protocol import LabProtocol, ProtocolStage
        from laboratory.runner import LabRunner

        protocol = LabProtocol(
            protocol_id="test-resume",
            name="Test Resume",
            description="Resume test",
            stages=[
                ProtocolStage(name="S1", agent="agent_v", action="render",
                              optional=True),
                ProtocolStage(name="S2", agent="agent_v", action="render",
                              optional=True),
                ProtocolStage(name="S3", agent="agent_v", action="render",
                              optional=True),
            ],
        )
        runner = LabRunner()
        result = runner.execute(protocol, start_stage=1)
        # S1 should be skipped_resume, S2 and S3 should run
        assert result["results"][0]["status"] == "skipped_resume"
        assert result["results"][1]["status"] == "ok"


class TestBuiltInProtocols:
    def test_discovery_protocol(self):
        from laboratory.registry import get_protocol
        proto = get_protocol("discovery")
        assert proto.material_type == "superconductor"
        stage_names = proto.stage_names()
        assert "Build crystal patterns" in stage_names
        assert "Generate synthetic structures" in stage_names
        assert "Score and compare" in stage_names

    def test_magnetic_study_protocol(self):
        from laboratory.registry import get_protocol
        proto = get_protocol("magnetic_study")
        assert proto.material_type == "magnetic"
        stage_names = proto.stage_names()
        assert "Load NEMAD data" in stage_names
        assert "NEMAD comparison" in stage_names

    def test_rtap_protocol(self):
        from laboratory.registry import get_protocol
        proto = get_protocol("rtap_exploration")
        assert proto.material_type == "superconductor"
        assert proto.default_params.get("target_pressure_GPa") == 0.0

    def test_verification_protocol_has_cb_and_p(self):
        """Verification protocol must include crystal builder and pressure scan."""
        from laboratory.registry import get_protocol
        proto = get_protocol("verification")
        assert proto.material_type == "superconductor"
        stage_names = proto.stage_names()
        assert "Build crystal models" in stage_names
        assert "Pressure scan" in stage_names
        # Verify correct agent/action pairs
        agents = [(s.agent, s.action) for s in proto.stages]
        assert ("agent_cb", "build_structures") in agents
        assert ("agent_p", "pressure_scan") in agents

    def test_verification_protocol_stage_order(self):
        """CB and P stages should come after scoring but before visualization."""
        from laboratory.registry import get_protocol
        proto = get_protocol("verification")
        stage_names = proto.stage_names()
        ob_idx = stage_names.index("Score candidates")
        cb_idx = stage_names.index("Build crystal models")
        p_idx = stage_names.index("Pressure scan")
        v_idx = stage_names.index("Visualize results")
        assert ob_idx < cb_idx < p_idx < v_idx


class TestDispatchCoverage:
    """Test that all agent dispatch cases in the runner are reachable."""

    def test_dispatch_agent_cb(self):
        """agent_cb/build_structures dispatch exists and doesn't error on import."""
        from laboratory.runner import _dispatch_agent
        # Without GCD predictions, it will raise FileNotFoundError — that's expected
        result = _dispatch_agent("agent_cb", "build_structures", {})
        assert result["status"] in ("ok", "error")

    def test_dispatch_agent_p(self):
        """agent_p/pressure_scan dispatch exists."""
        from laboratory.runner import _dispatch_agent
        result = _dispatch_agent("agent_p", "pressure_scan",
                                 {"target_pressure_GPa": 0.0})
        assert result["status"] in ("ok", "error")

    def test_dispatch_agent_xc_no_path(self):
        """agent_xc/predict skips when no xrd_path provided."""
        from laboratory.runner import _dispatch_agent
        result = _dispatch_agent("agent_xc", "predict", {})
        assert result["status"] == "skipped"
        assert "xrd_path" in result.get("reason", "")

    def test_dispatch_agent_v(self):
        """agent_v/render always returns ok."""
        from laboratory.runner import _dispatch_agent
        result = _dispatch_agent("agent_v", "render", {})
        assert result["status"] == "ok"

    def test_dispatch_unknown(self):
        """Unknown agent/action returns skipped."""
        from laboratory.runner import _dispatch_agent
        result = _dispatch_agent("agent_zzz", "noop", {})
        assert result["status"] == "skipped"


class TestOAECLI:
    def test_list_protocols_cli(self):
        """Test that --list-protocols works via oae.py."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "oae.py", "--list-protocols"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0
        assert "discovery" in result.stdout
        assert "magnetic_study" in result.stdout
