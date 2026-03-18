"""Tests for OAE Crystal Editor — agent_v/editor/crystal_editor.py."""
import sys
import os
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_v.editor.crystal_editor import CrystalEditor, AtomSite, LatticeState


class TestAtomSite:
    def test_creation(self):
        site = AtomSite(element="Fe", x=0.5, y=0.5, z=0.5)
        assert site.element == "Fe"
        assert site.occupancy == 1.0
        assert site.label == "Fe"

    def test_custom_label(self):
        site = AtomSite(element="O", x=0, y=0, z=0, label="O1")
        assert site.label == "O1"


class TestLatticeState:
    def test_default(self):
        lat = LatticeState()
        assert lat.a == 5.0
        assert lat.alpha == 90.0

    def test_volume_cubic(self):
        lat = LatticeState(a=5, b=5, c=5, alpha=90, beta=90, gamma=90)
        assert abs(lat.volume() - 125.0) < 0.01

    def test_volume_positive(self):
        lat = LatticeState(a=3.82, b=3.82, c=11.68)
        assert lat.volume() > 0


class TestCrystalEditorBasic:
    def test_empty_editor(self):
        ed = CrystalEditor()
        assert len(ed.atoms) == 0
        assert ed.space_group == "P1"

    def test_add_atom(self):
        ed = CrystalEditor()
        idx = ed.add_atom("Y", 0.5, 0.5, 0.5)
        assert idx == 0
        assert len(ed.atoms) == 1
        assert ed.atoms[0].element == "Y"

    def test_remove_atom(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        ed.add_atom("O", 0.5, 0.5, 0.5)
        assert ed.remove_atom(0) is True
        assert len(ed.atoms) == 1
        assert ed.atoms[0].element == "O"

    def test_remove_invalid_index(self):
        ed = CrystalEditor()
        assert ed.remove_atom(0) is False
        assert ed.remove_atom(-1) is False

    def test_move_atom(self):
        ed = CrystalEditor()
        ed.add_atom("Na", 0.0, 0.0, 0.0)
        assert ed.move_atom(0, 0.25, 0.25, 0.25) is True
        assert ed.atoms[0].x == 0.25

    def test_update_atom(self):
        ed = CrystalEditor()
        ed.add_atom("X", 0.0, 0.0, 0.0)
        assert ed.update_atom(0, element="Cu", occupancy=0.8) is True
        assert ed.atoms[0].element == "Cu"
        assert ed.atoms[0].occupancy == 0.8

    def test_set_lattice(self):
        ed = CrystalEditor()
        ed.set_lattice(a=3.82, b=3.86, c=11.68)
        assert ed.lattice.a == 3.82
        assert ed.lattice.c == 11.68

    def test_set_space_group(self):
        ed = CrystalEditor()
        ed.set_space_group("Pmmm")
        assert ed.space_group == "Pmmm"

    def test_clear(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        ed.set_lattice(a=10)
        ed.clear()
        assert len(ed.atoms) == 0
        assert ed.lattice.a == 5.0
        assert ed.space_group == "P1"


class TestCrystalEditorUndoRedo:
    def test_undo_add(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        assert len(ed.atoms) == 1
        assert ed.undo() is True
        assert len(ed.atoms) == 0

    def test_redo(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        ed.undo()
        assert ed.redo() is True
        assert len(ed.atoms) == 1

    def test_undo_empty(self):
        ed = CrystalEditor()
        assert ed.undo() is False
        assert ed.can_undo is False

    def test_redo_empty(self):
        ed = CrystalEditor()
        assert ed.redo() is False
        assert ed.can_redo is False

    def test_undo_clears_redo(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        ed.undo()
        assert ed.can_redo is True
        ed.add_atom("O", 0.5, 0.5, 0.5)  # new action clears redo
        assert ed.can_redo is False

    def test_multiple_undo(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        ed.add_atom("O", 0.5, 0.5, 0.5)
        ed.add_atom("Cu", 0.25, 0.25, 0.25)
        assert len(ed.atoms) == 3
        ed.undo()
        assert len(ed.atoms) == 2
        ed.undo()
        assert len(ed.atoms) == 1
        ed.undo()
        assert len(ed.atoms) == 0


class TestCrystalEditorCIF:
    def test_to_cif(self):
        ed = CrystalEditor()
        ed.set_lattice(a=3.82, b=3.82, c=11.68)
        ed.set_space_group("Pmmm")
        ed.add_atom("Y", 0.5, 0.5, 0.5)
        ed.add_atom("Ba", 0.5, 0.5, 0.185)
        cif = ed.to_cif()
        assert "data_oae_editor" in cif
        assert "_cell_length_a" in cif
        assert "3.820000" in cif
        assert "Pmmm" in cif
        assert "Y" in cif
        assert "Ba" in cif

    def test_from_cif_roundtrip(self):
        ed = CrystalEditor()
        ed.set_lattice(a=3.82, b=3.82, c=11.68)
        ed.set_space_group("Pmmm")
        ed.add_atom("Y", 0.5, 0.5, 0.5)
        ed.add_atom("Ba", 0.5, 0.5, 0.185)

        cif = ed.to_cif()
        ed2 = CrystalEditor.from_cif(cif)

        assert len(ed2.atoms) == 2
        assert ed2.lattice.a == pytest.approx(3.82, abs=0.001)
        assert ed2.lattice.c == pytest.approx(11.68, abs=0.001)
        assert ed2.space_group == "Pmmm"
        assert ed2.atoms[0].element == "Y"
        assert ed2.atoms[1].element == "Ba"

    def test_export_cif_file(self):
        ed = CrystalEditor()
        ed.add_atom("Na", 0.0, 0.0, 0.0)
        ed.add_atom("Cl", 0.5, 0.5, 0.5)

        tmp = tempfile.mkdtemp()
        path = ed.export_cif(Path(tmp) / "test.cif")
        assert path.exists()
        content = path.read_text()
        assert "_cell_length_a" in content

    def test_from_cif_file(self):
        ed = CrystalEditor()
        ed.add_atom("Mg", 0.0, 0.0, 0.0)
        ed.add_atom("B", 0.333, 0.667, 0.5)

        tmp = tempfile.mkdtemp()
        path = ed.export_cif(Path(tmp) / "mgb2.cif")
        ed2 = CrystalEditor.from_cif_file(path)
        assert len(ed2.atoms) == 2


class TestCrystalEditorDict:
    def test_to_dict(self):
        ed = CrystalEditor()
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        d = ed.to_dict()
        assert "atoms" in d
        assert "lattice" in d
        assert len(d["atoms"]) == 1

    def test_from_dict_roundtrip(self):
        ed = CrystalEditor()
        ed.add_atom("O", 0.25, 0.25, 0.25)
        ed.set_lattice(a=4.2)
        ed.set_space_group("Fm-3m")

        d = ed.to_dict()
        ed2 = CrystalEditor.from_dict(d)
        assert len(ed2.atoms) == 1
        assert ed2.atoms[0].element == "O"
        assert ed2.lattice.a == 4.2
        assert ed2.space_group == "Fm-3m"


class TestCrystalEditorValidation:
    def test_empty_structure_warning(self):
        ed = CrystalEditor()
        warnings = ed.validate()
        assert any("No atoms" in w for w in warnings)

    def test_valid_structure(self):
        ed = CrystalEditor()
        ed.set_lattice(a=5.64, b=5.64, c=5.64)
        ed.add_atom("Na", 0.0, 0.0, 0.0)
        ed.add_atom("Cl", 0.5, 0.5, 0.5)
        warnings = ed.validate()
        assert len(warnings) == 0

    def test_overlapping_atoms_warning(self):
        ed = CrystalEditor()
        ed.set_lattice(a=5.0, b=5.0, c=5.0)
        ed.add_atom("Fe", 0.0, 0.0, 0.0)
        ed.add_atom("Fe", 0.01, 0.01, 0.01)
        warnings = ed.validate()
        assert any("very close" in w for w in warnings)

    def test_repr(self):
        ed = CrystalEditor()
        ed.add_atom("Cu", 0.0, 0.0, 0.0)
        r = repr(ed)
        assert "1 atoms" in r
        assert "SG=P1" in r


class TestEditorLayout:
    def test_layout_creation(self):
        try:
            from agent_v.editor.editor_layout import create_editor_layout
            layout = create_editor_layout()
            assert layout is not None
        except ImportError:
            pytest.skip("dash not installed")

    def test_space_groups_list(self):
        from agent_v.editor.editor_layout import SPACE_GROUPS
        assert len(SPACE_GROUPS) > 100
        assert "P1" in SPACE_GROUPS
        assert "Fm-3m" in SPACE_GROUPS
        assert "Im-3m" in SPACE_GROUPS
