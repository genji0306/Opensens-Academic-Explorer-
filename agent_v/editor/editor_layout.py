"""
OAE Crystal Editor — Dash layout components.

Provides the editor panel layout with:
  - Left: 3D structure viewer (iframe)
  - Right: Atom table + lattice parameter inputs + space group selector
  - Bottom: Action buttons (Add, Remove, Validate, Export)
"""
from __future__ import annotations

import logging

logger = logging.getLogger("CrystalEditor.Layout")

try:
    from dash import dcc, html, dash_table
    _DASH = True
except ImportError:
    _DASH = False

from agent_v.theme import (
    FONT_STACK, DARK_TEXT, TEAL_500, TEAL_400, BORDER,
    SURFACE, SURFACE_ALT,
    card_style, card_title_style, button_style,
    table_header_style, table_cell_style,
    RED_500, BLUE_500,
)

# 230 space groups (abbreviated — common ones first)
SPACE_GROUPS = [
    "P1", "P-1", "P2", "P21", "C2", "Pm", "Pc", "Cm", "Cc",
    "P2/m", "P21/m", "C2/m", "P2/c", "P21/c", "C2/c",
    "P222", "P2221", "P21212", "P212121", "C222", "C2221",
    "Pmm2", "Pmc21", "Pcc2", "Pma2", "Pca21", "Pnc2", "Pmn21",
    "Pba2", "Pna21", "Pnn2", "Cmm2", "Cmc21", "Ccc2",
    "Pmmm", "Pnnn", "Pccm", "Pban", "Pmma", "Pnna", "Pmna",
    "Pcca", "Pbam", "Pccn", "Pbcm", "Pnnm", "Pmmn", "Pbcn",
    "Pbca", "Pnma", "Cmcm", "Cmca", "Cmmm", "Cccm", "Cmma", "Ccca",
    "P4", "P41", "P42", "P43", "I4", "I41",
    "P-4", "I-4",
    "P4/m", "P42/m", "P4/n", "P42/n", "I4/m", "I41/a",
    "P422", "P4212", "P4122", "P41212", "P4222", "P42212",
    "P4322", "P43212", "I422", "I4122",
    "P4mm", "P4bm", "P42cm", "P42nm", "P4cc", "P4nc",
    "P42mc", "P42bc", "I4mm", "I4cm", "I41md", "I41cd",
    "P-42m", "P-42c", "P-421m", "P-421c",
    "P-4m2", "P-4c2", "P-4b2", "P-4n2",
    "I-4m2", "I-4c2", "I-42m", "I-42d",
    "P4/mmm", "P4/mcc", "P4/nbm", "P4/nnc", "P4/mbm", "P4/mnc",
    "P4/nmm", "P4/ncc", "P42/mmc", "P42/mcm", "P42/nbc", "P42/nnm",
    "P42/mbc", "P42/mnm", "P42/nmc", "P42/ncm",
    "I4/mmm", "I4/mcm", "I41/amd", "I41/acd",
    "P3", "P31", "P32", "R3",
    "P-3", "R-3",
    "P312", "P321", "P3112", "P3121", "P3212", "P3221", "R32",
    "P3m1", "P31m", "P3c1", "P31c", "R3m", "R3c",
    "P-31m", "P-3m1", "P-31c", "P-3c1", "R-3m", "R-3c",
    "P6", "P61", "P65", "P62", "P64", "P63",
    "P-6",
    "P6/m", "P63/m",
    "P622", "P6122", "P6522", "P6222", "P6422", "P6322",
    "P6mm", "P6cc", "P63cm", "P63mc",
    "P-6m2", "P-6c2", "P-62m", "P-62c",
    "P6/mmm", "P6/mcc", "P63/mcm", "P63/mmc",
    "P23", "F23", "I23", "P213", "I213",
    "Pm-3", "Pn-3", "Fm-3", "Fd-3", "Im-3", "Pa-3", "Ia-3",
    "P432", "P4232", "F432", "F4132", "I432", "P4332", "P4132", "I4132",
    "P-43m", "F-43m", "I-43m", "P-43n", "F-43c", "I-43d",
    "Pm-3m", "Pn-3n", "Pm-3n", "Pn-3m",
    "Fm-3m", "Fm-3c", "Fd-3m", "Fd-3c",
    "Im-3m", "Ia-3d",
]

# Panel styling constants — from theme
PANEL_STYLE = card_style()
PANEL_STYLE["marginBottom"] = "12px"

BUTTON_STYLE = button_style(TEAL_500)
BUTTON_DANGER = button_style(RED_500)
BUTTON_SECONDARY = button_style(BLUE_500)


def create_editor_layout() -> object:
    """Build the Crystal Editor Dash layout.

    Returns a Dash html.Div component tree.
    """
    if not _DASH:
        raise ImportError("dash is required for the Crystal Editor layout")

    return html.Div([
        # Title
        html.H3("Crystal Structure Editor",
                 style={"textAlign": "center", "color": DARK_TEXT,
                        "marginBottom": "16px", "fontWeight": "600",
                        "letterSpacing": "0.5px"}),

        # Top row: Viewer + Atom Table
        html.Div([
            # Left: 3D viewer
            html.Div([
                html.H4("3D Preview", style={"marginTop": "0"}),
                html.Div([
                    dcc.Dropdown(
                        id="editor-view-mode",
                        options=[
                            {"label": "Ball & Stick", "value": "ball-and-stick"},
                            {"label": "Space Filling", "value": "space-filling"},
                            {"label": "Polyhedral", "value": "polyhedral"},
                            {"label": "Unit Cell", "value": "unit-cell"},
                        ],
                        value="ball-and-stick",
                        clearable=False,
                        style={"width": "180px", "fontSize": "13px",
                               "marginBottom": "8px"},
                    ),
                ]),
                html.Iframe(
                    id="editor-viewer-iframe",
                    style={"width": "100%", "height": "400px",
                           "border": "1px solid #ccc", "borderRadius": "8px"},
                    srcDoc="<p style='text-align:center;padding:80px;color:#999;'>"
                           "Load or create a structure to preview</p>",
                ),
                html.Div([
                    html.Button("Refresh View", id="editor-refresh-btn",
                                style=BUTTON_SECONDARY, n_clicks=0),
                ], style={"marginTop": "8px"}),
            ], style={**PANEL_STYLE, "flex": "1", "minWidth": "400px"}),

            # Right: Lattice + Space Group
            html.Div([
                html.H4("Lattice Parameters", style={"marginTop": "0"}),
                _lattice_inputs(),
                html.Hr(),
                html.H4("Space Group"),
                dcc.Dropdown(
                    id="editor-space-group",
                    options=[{"label": sg, "value": sg} for sg in SPACE_GROUPS],
                    value="P1",
                    clearable=False,
                    style={"marginBottom": "12px"},
                ),
                html.Hr(),
                html.H4("Validation"),
                html.Div(id="editor-validation-output",
                         style={"fontSize": "12px", "color": "#666"}),
            ], style={**PANEL_STYLE, "flex": "0 0 320px"}),
        ], style={"display": "flex", "gap": "12px"}),

        # Atom table
        html.Div([
            html.H4("Atom Sites", style={"marginTop": "0"}),
            dash_table.DataTable(
                id="editor-atom-table",
                columns=[
                    {"name": "Element", "id": "element", "editable": True},
                    {"name": "x", "id": "x", "type": "numeric", "editable": True},
                    {"name": "y", "id": "y", "type": "numeric", "editable": True},
                    {"name": "z", "id": "z", "type": "numeric", "editable": True},
                    {"name": "Occupancy", "id": "occupancy", "type": "numeric", "editable": True},
                    {"name": "Label", "id": "label", "editable": True},
                ],
                data=[],
                editable=True,
                row_deletable=True,
                row_selectable="multi",
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center", "padding": "6px",
                             "fontSize": "13px"},
                style_header=table_header_style(),
                style_data_conditional=[
                    {"if": {"state": "active"},
                     "backgroundColor": "#E8F5E9", "border": "1px solid #2A9D8F"},
                ],
            ),
        ], style=PANEL_STYLE),

        # Action buttons
        html.Div([
            html.Button("Add Atom", id="editor-add-atom-btn",
                        style=BUTTON_STYLE, n_clicks=0),
            html.Button("Remove Selected", id="editor-remove-btn",
                        style=BUTTON_DANGER, n_clicks=0),
            html.Button("Validate", id="editor-validate-btn",
                        style=BUTTON_SECONDARY, n_clicks=0),
            html.Button("Undo", id="editor-undo-btn",
                        style=BUTTON_SECONDARY, n_clicks=0),
            html.Button("Redo", id="editor-redo-btn",
                        style=BUTTON_SECONDARY, n_clicks=0),
            html.Button("Clear All", id="editor-clear-btn",
                        style=BUTTON_DANGER, n_clicks=0),
        ], style={"display": "flex", "gap": "4px", "marginBottom": "12px"}),

        # Import / Export row
        html.Div([
            dcc.Upload(
                id="editor-cif-upload",
                children=html.Button("Import CIF", style=BUTTON_SECONDARY),
                multiple=False,
            ),
            html.Button("Export CIF", id="editor-export-btn",
                        style=BUTTON_STYLE, n_clicks=0),
            dcc.Download(id="editor-cif-download"),
        ], style={"display": "flex", "gap": "8px", "marginBottom": "12px"}),

        # Hidden state store
        dcc.Store(id="editor-state-store", data={}),
        html.Div(id="editor-status-msg",
                 style={"color": "#2A9D8F", "fontSize": "13px"}),
    ], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "16px",
              "fontFamily": FONT_STACK})


def _lattice_inputs():
    """Create 6 numeric inputs for lattice parameters."""
    if not _DASH:
        return None

    params = [
        ("a", "a (A)", 5.0), ("b", "b (A)", 5.0), ("c", "c (A)", 5.0),
        ("alpha", "alpha (deg)", 90.0), ("beta", "beta (deg)", 90.0),
        ("gamma", "gamma (deg)", 90.0),
    ]
    rows = []
    for pid, label, default in params:
        rows.append(html.Div([
            html.Label(label, style={"fontSize": "12px", "width": "80px",
                                     "display": "inline-block"}),
            dcc.Input(
                id=f"editor-lattice-{pid}",
                type="number",
                value=default,
                step=0.01,
                style={"width": "100px", "fontSize": "13px"},
            ),
        ], style={"marginBottom": "4px"}))
    return html.Div(rows)
