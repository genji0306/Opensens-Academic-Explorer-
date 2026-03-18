"""Smoke tests for Agent PB v2.0 package."""
import pytest


class TestConfig:
    def test_config_defaults(self):
        from agent_pb.config import PBConfig
        cfg = PBConfig()
        assert cfg.algorithm == "hybrid"
        assert cfg.max_steps == 5000
        assert cfg.top_k == 10

    def test_config_custom(self):
        from agent_pb.config import PBConfig
        cfg = PBConfig(formula="NaCl", max_steps=100, algorithm="tpe")
        assert cfg.formula == "NaCl"
        assert cfg.max_steps == 100
        assert cfg.algorithm == "tpe"


class TestChemistry:
    def test_parse_formula_simple(self):
        from agent_pb.constraints.chemistry import parse_formula
        result = parse_formula("NaCl")
        assert result == {"Na": 1, "Cl": 1}

    def test_parse_formula_complex(self):
        from agent_pb.constraints.chemistry import parse_formula
        result = parse_formula("YBa2Cu3O7")
        assert result["Y"] == 1
        assert result["Ba"] == 2
        assert result["Cu"] == 3
        assert result["O"] == 7

    def test_charge_neutrality_nacl(self):
        from agent_pb.constraints.chemistry import ChemistryConstraint
        cc = ChemistryConstraint()
        valid, imbalance = cc.check_charge_neutrality("NaCl")
        assert valid is True
        assert imbalance == pytest.approx(0.0)

    def test_validate_composition(self):
        from agent_pb.constraints.chemistry import ChemistryConstraint
        cc = ChemistryConstraint()
        # validate_composition returns bool directly
        result = cc.validate_composition("MgB2")
        assert result is True

    def test_validate_composition_invalid(self):
        from agent_pb.constraints.chemistry import ChemistryConstraint
        cc = ChemistryConstraint()
        # Unknown element should return False
        result = cc.validate_composition("Xx2Y3")
        assert result is False


class TestGeometry:
    def test_geometry_constraint_init(self):
        from agent_pb.constraints.geometry import GeometryConstraint
        gc = GeometryConstraint()
        assert gc is not None


class TestSymmetry:
    def test_symmetry_constraint_init(self):
        from agent_pb.constraints.symmetry import SymmetryConstraint
        # space_groups expects [min, max] range
        sc = SymmetryConstraint(space_groups=[1, 230], element_counts={"Na": 1, "Cl": 1})
        assert sc is not None

    def test_lattice_from_sg(self):
        pytest.importorskip("pymatgen")
        from agent_pb.constraints.symmetry import SymmetryConstraint
        sc = SymmetryConstraint(space_groups=[1, 1], element_counts={"Na": 1, "Cl": 1})
        lattice = sc.lattice_from_sg(1, {"a": 5.0, "b": 5.0, "c": 5.0,
                                         "alpha": 90, "beta": 90, "gamma": 90})
        assert lattice is not None


class TestCifIO:
    def test_imports(self):
        from agent_pb.io.cif_io import read_cif, write_cif
        assert callable(read_cif)
        assert callable(write_cif)


class TestAgentPB:
    def test_import(self):
        from agent_pb.predict import AgentPB
        agent = AgentPB()
        assert agent is not None

    def test_gnn_ensemble_import(self):
        from agent_pb.gnn.ensemble import GNNEnsemble, EnsemblePrediction
        assert GNNEnsemble is not None
        assert EnsemblePrediction is not None

    def test_m3gnet_predictor_import(self):
        from agent_pb.gnn.megnet_model import M3GNetPredictor
        assert M3GNetPredictor is not None
