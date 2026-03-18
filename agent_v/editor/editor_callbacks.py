"""
OAE Crystal Editor — Dash callbacks for interactive editing.

Registers all callbacks for the crystal editor: atom table edits,
lattice changes, CIF upload/download, undo/redo, validation, viewer refresh.
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import asdict

logger = logging.getLogger("CrystalEditor.Callbacks")

try:
    from dash import Input, Output, State, callback_context, no_update
    from dash.exceptions import PreventUpdate
    _DASH = True
except ImportError:
    _DASH = False

from agent_v.editor.crystal_editor import CrystalEditor, AtomSite


def _editor_from_store(store_data: dict) -> CrystalEditor:
    """Reconstruct a CrystalEditor from the dcc.Store data."""
    if not store_data:
        return CrystalEditor()
    return CrystalEditor.from_dict(store_data)


def _editor_to_store(editor: CrystalEditor) -> dict:
    """Serialize editor state for dcc.Store."""
    return editor.to_dict()


def _atoms_to_table(editor: CrystalEditor) -> list[dict]:
    """Convert editor atoms to DataTable rows."""
    return [
        {"element": a.element, "x": round(a.x, 6), "y": round(a.y, 6),
         "z": round(a.z, 6), "occupancy": round(a.occupancy, 4),
         "label": a.label}
        for a in editor.atoms
    ]


def _render_viewer_html(editor: CrystalEditor, view_mode: str = "ball-and-stick") -> str:
    """Generate an HTML string with 3Dmol.js viewer for the current structure.

    Uses the full StructureViewer pipeline when pymatgen is available,
    which supports ball-and-stick, space-filling, polyhedral, and unit-cell
    modes with proper lattice vectors.
    """
    if not editor.atoms:
        return ("<p style='text-align:center;padding:80px;color:#999;'>"
                "No atoms to display</p>")

    # Try to build a pymatgen Structure and use StructureViewer
    try:
        from pymatgen.core import Structure, Lattice
        from agent_v.viewers.structure_viewer import StructureViewer

        lat = editor.lattice
        pmg_lattice = Lattice.from_parameters(
            lat.a, lat.b, lat.c,
            lat.alpha, lat.beta, lat.gamma,
        )
        species = [a.element for a in editor.atoms]
        frac_coords = [[a.x, a.y, a.z] for a in editor.atoms]
        structure = Structure(pmg_lattice, species, frac_coords)

        viewer = StructureViewer()
        return viewer.render_structure(structure, style=view_mode)
    except Exception as exc:
        logger.warning("StructureViewer fallback: %s", exc)

    # Fallback: simple 3Dmol.js stick+sphere view
    lat = editor.lattice
    n = len(editor.atoms)
    xyz_lines = [str(n), f"OAE Editor: {editor.space_group}"]
    for atom in editor.atoms:
        cx = atom.x * lat.a
        cy = atom.y * lat.b
        cz = atom.z * lat.c
        xyz_lines.append(f"{atom.element}  {cx:.6f}  {cy:.6f}  {cz:.6f}")
    xyz_str = "\\n".join(xyz_lines)

    from agent_v.config import CPK_COLORS, CPK_DEFAULT_COLOR
    elements = set(a.element for a in editor.atoms)
    style_js = "\n".join(
        f'  viewer.setStyle({{elem: "{el}"}}, '
        f'{{stick: {{color: "{CPK_COLORS.get(el, CPK_DEFAULT_COLOR)}"}}, '
        f'sphere: {{scale: 0.3, color: "{CPK_COLORS.get(el, CPK_DEFAULT_COLOR)}"}}}});'
        for el in elements
    )

    html = f"""<!DOCTYPE html>
<html><head>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>
</head><body style="margin:0;padding:0;">
<div id="viewer" style="width:100%;height:100%;position:absolute;"></div>
<script>
  var viewer = $3Dmol.createViewer("viewer", {{backgroundColor: "white"}});
  viewer.addModel("{xyz_str}", "xyz");
{style_js}
  viewer.zoomTo();
  viewer.render();
</script>
</body></html>"""
    return html


def register_callbacks(app):
    """Register all crystal editor callbacks on a Dash app.

    Args:
        app: A Dash application instance.
    """
    if not _DASH:
        logger.warning("Dash not available — editor callbacks not registered")
        return

    # ------------------------------------------------------------------
    # Add atom
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-atom-table", "data", allow_duplicate=True),
         Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        Input("editor-add-atom-btn", "n_clicks"),
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def add_atom(n_clicks, store_data):
        if not n_clicks:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        editor.add_atom("X", 0.0, 0.0, 0.0)
        return _atoms_to_table(editor), _editor_to_store(editor), "Atom added"

    # ------------------------------------------------------------------
    # Remove selected atoms
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-atom-table", "data", allow_duplicate=True),
         Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        Input("editor-remove-btn", "n_clicks"),
        [State("editor-atom-table", "selected_rows"),
         State("editor-state-store", "data")],
        prevent_initial_call=True,
    )
    def remove_atoms(n_clicks, selected_rows, store_data):
        if not n_clicks or not selected_rows:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        for idx in sorted(selected_rows, reverse=True):
            editor.remove_atom(idx)
        return (_atoms_to_table(editor), _editor_to_store(editor),
                f"Removed {len(selected_rows)} atom(s)")

    # ------------------------------------------------------------------
    # Atom table edits (user directly edits cells)
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        Input("editor-atom-table", "data"),
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def sync_table_to_store(table_data, store_data):
        if table_data is None:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        atoms = []
        for row in table_data:
            try:
                atoms.append({
                    "element": str(row.get("element", "X")),
                    "x": float(row.get("x", 0)),
                    "y": float(row.get("y", 0)),
                    "z": float(row.get("z", 0)),
                    "occupancy": float(row.get("occupancy", 1.0)),
                    "label": str(row.get("label", "")),
                })
            except (ValueError, TypeError):
                continue
        editor.replace_all_atoms(atoms)
        return _editor_to_store(editor), ""

    # ------------------------------------------------------------------
    # Lattice parameter changes
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        [Input(f"editor-lattice-{p}", "value") for p in
         ["a", "b", "c", "alpha", "beta", "gamma"]],
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def update_lattice(a, b, c, alpha, beta, gamma, store_data):
        editor = _editor_from_store(store_data)
        try:
            editor.set_lattice(
                a=float(a or 5), b=float(b or 5), c=float(c or 5),
                alpha=float(alpha or 90), beta=float(beta or 90),
                gamma=float(gamma or 90),
            )
        except (ValueError, TypeError):
            raise PreventUpdate
        return _editor_to_store(editor), ""

    # ------------------------------------------------------------------
    # Space group change
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        Input("editor-space-group", "value"),
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def update_space_group(sg, store_data):
        if not sg:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        editor.set_space_group(sg)
        return _editor_to_store(editor), f"Space group: {sg}"

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    @app.callback(
        Output("editor-validation-output", "children"),
        Input("editor-validate-btn", "n_clicks"),
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def validate(n_clicks, store_data):
        if not n_clicks:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        warnings = editor.validate()
        if not warnings:
            return "All checks passed."
        return "; ".join(warnings)

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-atom-table", "data", allow_duplicate=True),
         Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        [Input("editor-undo-btn", "n_clicks"),
         Input("editor-redo-btn", "n_clicks")],
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def undo_redo(undo_clicks, redo_clicks, store_data):
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        editor = _editor_from_store(store_data)
        if trigger_id == "editor-undo-btn":
            ok = editor.undo()
            msg = "Undone" if ok else "Nothing to undo"
        else:
            ok = editor.redo()
            msg = "Redone" if ok else "Nothing to redo"
        return _atoms_to_table(editor), _editor_to_store(editor), msg

    # ------------------------------------------------------------------
    # Clear all
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-atom-table", "data", allow_duplicate=True),
         Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        Input("editor-clear-btn", "n_clicks"),
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def clear_all(n_clicks, store_data):
        if not n_clicks:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        editor.clear()
        return [], _editor_to_store(editor), "Cleared"

    # ------------------------------------------------------------------
    # Refresh viewer (triggered by button or view mode change)
    # ------------------------------------------------------------------
    @app.callback(
        Output("editor-viewer-iframe", "srcDoc"),
        [Input("editor-refresh-btn", "n_clicks"),
         Input("editor-view-mode", "value")],
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def refresh_viewer(n_clicks, view_mode, store_data):
        editor = _editor_from_store(store_data)
        mode = view_mode or "ball-and-stick"
        return _render_viewer_html(editor, view_mode=mode)

    # ------------------------------------------------------------------
    # Import CIF
    # ------------------------------------------------------------------
    @app.callback(
        [Output("editor-atom-table", "data", allow_duplicate=True),
         Output("editor-state-store", "data", allow_duplicate=True),
         Output("editor-lattice-a", "value"),
         Output("editor-lattice-b", "value"),
         Output("editor-lattice-c", "value"),
         Output("editor-lattice-alpha", "value"),
         Output("editor-lattice-beta", "value"),
         Output("editor-lattice-gamma", "value"),
         Output("editor-space-group", "value"),
         Output("editor-status-msg", "children", allow_duplicate=True)],
        Input("editor-cif-upload", "contents"),
        State("editor-cif-upload", "filename"),
        prevent_initial_call=True,
    )
    def import_cif(contents, filename):
        if not contents:
            raise PreventUpdate
        # Decode base64 upload
        content_type, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string).decode("utf-8")
        editor = CrystalEditor.from_cif(decoded)
        lat = editor.lattice
        return (
            _atoms_to_table(editor),
            _editor_to_store(editor),
            lat.a, lat.b, lat.c,
            lat.alpha, lat.beta, lat.gamma,
            editor.space_group,
            f"Imported {filename}: {len(editor.atoms)} atoms",
        )

    # ------------------------------------------------------------------
    # Export CIF
    # ------------------------------------------------------------------
    @app.callback(
        Output("editor-cif-download", "data"),
        Input("editor-export-btn", "n_clicks"),
        State("editor-state-store", "data"),
        prevent_initial_call=True,
    )
    def export_cif(n_clicks, store_data):
        if not n_clicks:
            raise PreventUpdate
        editor = _editor_from_store(store_data)
        cif_str = editor.to_cif()
        return {"content": cif_str, "filename": "oae_structure.cif"}
