"""
OAE Crystal Editor — Mutable crystal structure state with undo/redo.

Manages a list of atoms + lattice parameters and provides operations
for interactive editing: add, remove, move atoms, change lattice, etc.
Round-trips through CIF for import/export.
"""
from __future__ import annotations

import copy
import logging
import math
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("CrystalEditor")


@dataclass
class AtomSite:
    """A single atom in the crystal structure."""
    element: str
    x: float  # fractional coordinate
    y: float
    z: float
    occupancy: float = 1.0
    label: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = self.element


@dataclass
class LatticeState:
    """Lattice parameters for the crystal."""
    a: float = 5.0
    b: float = 5.0
    c: float = 5.0
    alpha: float = 90.0
    beta: float = 90.0
    gamma: float = 90.0

    def volume(self) -> float:
        """Calculate unit cell volume from lattice parameters."""
        ar, br, gr = (
            math.radians(self.alpha),
            math.radians(self.beta),
            math.radians(self.gamma),
        )
        cos_a, cos_b, cos_g = math.cos(ar), math.cos(br), math.cos(gr)
        val = 1.0 - cos_a**2 - cos_b**2 - cos_g**2 + 2 * cos_a * cos_b * cos_g
        return self.a * self.b * self.c * math.sqrt(max(val, 0.0))


@dataclass
class EditorSnapshot:
    """Immutable snapshot for undo/redo."""
    atoms: list[dict]
    lattice: dict
    space_group: str


class CrystalEditor:
    """Mutable crystal structure editor with undo/redo stack.

    Usage:
        editor = CrystalEditor()
        editor.set_lattice(a=3.82, b=3.82, c=11.68)
        editor.add_atom("Y", 0.5, 0.5, 0.5)
        editor.add_atom("Ba", 0.5, 0.5, 0.185)
        editor.undo()
        editor.export_cif("output.cif")
    """

    MAX_UNDO = 50

    def __init__(self):
        self.atoms: list[AtomSite] = []
        self.lattice = LatticeState()
        self.space_group: str = "P1"
        self._undo_stack: list[EditorSnapshot] = []
        self._redo_stack: list[EditorSnapshot] = []

    # ------------------------------------------------------------------
    # Snapshot / undo / redo
    # ------------------------------------------------------------------

    def _snapshot(self) -> EditorSnapshot:
        return EditorSnapshot(
            atoms=[asdict(a) for a in self.atoms],
            lattice=asdict(self.lattice),
            space_group=self.space_group,
        )

    def _push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore(self, snap: EditorSnapshot):
        self.atoms = [AtomSite(**d) for d in snap.atoms]
        self.lattice = LatticeState(**snap.lattice)
        self.space_group = snap.space_group

    def undo(self) -> bool:
        """Undo last operation. Returns True if successful."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self._restore(self._undo_stack.pop())
        return True

    def redo(self) -> bool:
        """Redo last undone operation. Returns True if successful."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        return True

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # ------------------------------------------------------------------
    # Atom operations
    # ------------------------------------------------------------------

    def add_atom(self, element: str, x: float, y: float, z: float,
                 occupancy: float = 1.0, label: str = "") -> int:
        """Add an atom. Returns the index of the new atom."""
        self._push_undo()
        site = AtomSite(element=element, x=x, y=y, z=z,
                        occupancy=occupancy, label=label or element)
        self.atoms.append(site)
        return len(self.atoms) - 1

    def remove_atom(self, index: int) -> bool:
        """Remove atom at index. Returns True if successful."""
        if index < 0 or index >= len(self.atoms):
            return False
        self._push_undo()
        self.atoms.pop(index)
        return True

    def move_atom(self, index: int, x: float, y: float, z: float) -> bool:
        """Move atom to new fractional coordinates."""
        if index < 0 or index >= len(self.atoms):
            return False
        self._push_undo()
        self.atoms[index].x = x
        self.atoms[index].y = y
        self.atoms[index].z = z
        return True

    def update_atom(self, index: int, **kwargs) -> bool:
        """Update atom properties (element, x, y, z, occupancy, label)."""
        if index < 0 or index >= len(self.atoms):
            return False
        self._push_undo()
        atom = self.atoms[index]
        for key, val in kwargs.items():
            if hasattr(atom, key):
                setattr(atom, key, val)
        return True

    # ------------------------------------------------------------------
    # Lattice operations
    # ------------------------------------------------------------------

    def set_lattice(self, **kwargs) -> None:
        """Update lattice parameters (a, b, c, alpha, beta, gamma)."""
        self._push_undo()
        for key, val in kwargs.items():
            if hasattr(self.lattice, key):
                setattr(self.lattice, key, float(val))

    def set_space_group(self, sg: str) -> None:
        """Set space group symbol (Hermann-Mauguin)."""
        self._push_undo()
        self.space_group = sg

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all atoms and reset lattice."""
        self._push_undo()
        self.atoms.clear()
        self.lattice = LatticeState()
        self.space_group = "P1"

    def replace_all_atoms(self, atoms: list[dict]) -> None:
        """Replace all atoms from list of dicts."""
        self._push_undo()
        self.atoms = [AtomSite(**a) for a in atoms]

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Export editor state as a plain dict."""
        return {
            "atoms": [asdict(a) for a in self.atoms],
            "lattice": asdict(self.lattice),
            "space_group": self.space_group,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CrystalEditor":
        """Create editor from dict (inverse of to_dict)."""
        editor = cls()
        editor.atoms = [AtomSite(**a) for a in data.get("atoms", [])]
        editor.lattice = LatticeState(**data.get("lattice", {}))
        editor.space_group = data.get("space_group", "P1")
        return editor

    def to_cif(self) -> str:
        """Export current state as CIF string."""
        lines = [
            f"data_oae_editor",
            f"_symmetry_space_group_name_H-M   '{self.space_group}'",
            f"_cell_length_a   {self.lattice.a:.6f}",
            f"_cell_length_b   {self.lattice.b:.6f}",
            f"_cell_length_c   {self.lattice.c:.6f}",
            f"_cell_angle_alpha   {self.lattice.alpha:.4f}",
            f"_cell_angle_beta    {self.lattice.beta:.4f}",
            f"_cell_angle_gamma   {self.lattice.gamma:.4f}",
            "",
            "loop_",
            "_atom_site_label",
            "_atom_site_type_symbol",
            "_atom_site_fract_x",
            "_atom_site_fract_y",
            "_atom_site_fract_z",
            "_atom_site_occupancy",
        ]
        # Assign unique labels per element
        elem_counts: dict[str, int] = {}
        for atom in self.atoms:
            elem_counts[atom.element] = elem_counts.get(atom.element, 0) + 1
            label = f"{atom.element}{elem_counts[atom.element]}"
            lines.append(
                f"  {label:6s} {atom.element:4s} "
                f"{atom.x:.6f} {atom.y:.6f} {atom.z:.6f} {atom.occupancy:.4f}"
            )
        return "\n".join(lines) + "\n"

    def export_cif(self, path: str | Path) -> Path:
        """Write CIF to file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_cif())
        return p

    @classmethod
    def from_cif(cls, cif_text: str) -> "CrystalEditor":
        """Parse a CIF string into an editor state."""
        editor = cls()

        # Extract lattice parameters
        for param, attr in [
            ("_cell_length_a", "a"), ("_cell_length_b", "b"),
            ("_cell_length_c", "c"), ("_cell_angle_alpha", "alpha"),
            ("_cell_angle_beta", "beta"), ("_cell_angle_gamma", "gamma"),
        ]:
            m = re.search(rf"{param}\s+([\d.]+)", cif_text)
            if m:
                setattr(editor.lattice, attr, float(m.group(1)))

        # Extract space group
        m = re.search(r"_symmetry_space_group_name_H-M\s+'([^']+)'", cif_text)
        if m:
            editor.space_group = m.group(1).strip()

        # Extract atom sites from loop
        lines = cif_text.splitlines()
        in_loop = False
        columns: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped == "loop_":
                in_loop = True
                columns = []
                continue
            if in_loop and stripped.startswith("_atom_site_"):
                columns.append(stripped)
                continue
            if in_loop and columns and not stripped.startswith("_"):
                if not stripped or stripped.startswith("loop_") or stripped.startswith("data_"):
                    in_loop = False
                    continue
                parts = stripped.split()
                if len(parts) < len(columns):
                    continue

                col_map = {c: i for i, c in enumerate(columns)}
                elem_idx = col_map.get("_atom_site_type_symbol",
                           col_map.get("_atom_site_label"))
                x_idx = col_map.get("_atom_site_fract_x")
                y_idx = col_map.get("_atom_site_fract_y")
                z_idx = col_map.get("_atom_site_fract_z")
                occ_idx = col_map.get("_atom_site_occupancy")

                if elem_idx is not None and x_idx is not None:
                    elem = re.sub(r"[\d.+-]+$", "", parts[elem_idx])
                    x = float(parts[x_idx].split("(")[0])
                    y = float(parts[y_idx].split("(")[0]) if y_idx is not None else 0.0
                    z = float(parts[z_idx].split("(")[0]) if z_idx is not None else 0.0
                    occ = float(parts[occ_idx]) if occ_idx is not None else 1.0
                    editor.atoms.append(AtomSite(
                        element=elem, x=x, y=y, z=z, occupancy=occ
                    ))

        return editor

    @classmethod
    def from_cif_file(cls, path: str | Path) -> "CrystalEditor":
        """Load a CIF file into an editor."""
        return cls.from_cif(Path(path).read_text())

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Run basic structural validation. Returns list of warnings."""
        warnings = []
        if not self.atoms:
            warnings.append("No atoms in structure")
        if self.lattice.a <= 0 or self.lattice.b <= 0 or self.lattice.c <= 0:
            warnings.append("Lattice parameters must be positive")
        if self.lattice.volume() < 1.0:
            warnings.append(f"Very small unit cell volume: {self.lattice.volume():.2f} A^3")

        # Check for overlapping atoms (< 0.5 A in fractional space as rough check)
        for i in range(len(self.atoms)):
            for j in range(i + 1, len(self.atoms)):
                ai, aj = self.atoms[i], self.atoms[j]
                dx = abs(ai.x - aj.x)
                dy = abs(ai.y - aj.y)
                dz = abs(ai.z - aj.z)
                # Apply PBC
                dx = min(dx, 1.0 - dx)
                dy = min(dy, 1.0 - dy)
                dz = min(dz, 1.0 - dz)
                # Rough Cartesian distance
                dist = math.sqrt(
                    (dx * self.lattice.a) ** 2 +
                    (dy * self.lattice.b) ** 2 +
                    (dz * self.lattice.c) ** 2
                )
                if dist < 0.5:
                    warnings.append(
                        f"Atoms {i} ({ai.element}) and {j} ({aj.element}) "
                        f"are very close: {dist:.2f} A"
                    )
        return warnings

    def __repr__(self) -> str:
        return (f"CrystalEditor({len(self.atoms)} atoms, "
                f"SG={self.space_group}, "
                f"V={self.lattice.volume():.1f} A^3)")
