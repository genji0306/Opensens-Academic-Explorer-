"""
Agent V — Interactive Dash dashboard for Opensens Academic Explorer (OAE).

Provides a four-panel layout:

1. **Structure Viewer** — Renders the selected crystal structure (CIF) as
   inline HTML (3D via py3Dmol or 2D matplotlib fallback).
2. **Convergence Chart** — Live-updating plotly line chart of the
   composite convergence score plus a bar chart of component scores.
3. **Agent Status** — Table showing each agent's activity state, last-
   active timestamp, and file count.
4. **Candidate Table** — Top-ranked novel candidates from the latest
   prediction run (``data/predictions/gcd_top_candidates.csv``).

Usage::

    python -m agent_v.dashboard          # default host/port
    python -m agent_v.dashboard --port 8055 --debug

Or from Python::

    from agent_v.dashboard import AgentVDashboard
    app = AgentVDashboard()
    app.run(debug=True)
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentV.Dashboard")

# ---------------------------------------------------------------------------
# Optional Dash / plotly
# ---------------------------------------------------------------------------
try:
    import dash  # type: ignore[import-untyped]
    from dash import dcc, html, dash_table  # type: ignore[import-untyped]
    from dash.dependencies import Input, Output  # type: ignore[import-untyped]

    _DASH = True
except ImportError:
    _DASH = False
    logger.warning("dash is not installed.  pip install dash plotly")

try:
    import plotly.graph_objects as go  # type: ignore[import-untyped]
    import plotly.io as pio  # type: ignore[import-untyped]

    _PLOTLY = True
except ImportError:
    _PLOTLY = False

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from agent_v.config import (
    DASH_HOST,
    DASH_PORT,
    DATA_DIR,
    EXPORTS_DIR,
    FAMILY_COLORS,
    PREDICTIONS_WATCH_DIR,
    REPORTS_DIR,
    STRUCTURES_WATCH_DIR,
)
from agent_v.monitors.convergence_monitor import ConvergenceMonitor
from agent_v.monitors.agent_status_monitor import AgentStatusMonitor
from agent_v.viewers.structure_viewer import StructureViewer
from agent_v.theme import (
    FONT_STACK, FONT_MONO, FONT_CDN,
    NAVY_700, NAVY_900, TEAL_400, TEAL_500,
    DARK_TEXT, TEXT_PRIMARY, TEXT_SECONDARY,
    SURFACE, SURFACE_ALT, BORDER,
    card_style, card_title_style, tab_style, tab_selected_style,
    badge_style, table_header_style, table_cell_style,
    header_bar, plotly_template,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POLL_INTERVAL_MS = 5_000  # 5 seconds


def _load_candidates_csv() -> list[dict[str, str]]:
    """Load the top candidates CSV produced by the convergence loop."""
    csv_path = PREDICTIONS_WATCH_DIR / "gcd_top_candidates.csv"
    if not csv_path.exists():
        return []
    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        return rows
    except Exception as exc:
        logger.error("Failed to read candidates CSV: %s", exc)
        return []


def _list_cif_files() -> list[dict[str, str]]:
    """Return a list of ``{label, path}`` dicts for all CIF files found
    under ``data/crystal_structures/`` and ``data/exports/``."""
    cif_files: list[dict[str, str]] = []
    for search_dir in (STRUCTURES_WATCH_DIR, EXPORTS_DIR):
        if not search_dir.is_dir():
            continue
        for p in sorted(search_dir.rglob("*.cif")):
            cif_files.append({
                "label": f"{p.parent.name}/{p.name}" if p.parent != search_dir else p.name,
                "path": str(p),
            })
    return cif_files


def _empty_figure(message: str = "No data") -> "go.Figure":
    """Return a blank plotly figure with a centred annotation."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#9CA3AF"),
    )
    fig.update_layout(
        height=350,
        margin=dict(l=30, r=30, t=30, b=30),
        uirevision="empty",
    )
    return fig


# ---------------------------------------------------------------------------
# View mode options
# ---------------------------------------------------------------------------
_VIEW_MODES = [
    {"label": "Ball & Stick", "value": "ball-and-stick"},
    {"label": "Space Filling", "value": "space-filling"},
    {"label": "Polyhedral", "value": "polyhedral"},
    {"label": "Unit Cell", "value": "unit-cell"},
]


# ---------------------------------------------------------------------------
# Dashboard class
# ---------------------------------------------------------------------------

class AgentVDashboard:
    """Interactive Dash dashboard for the multi-agent platform."""

    def __init__(self) -> None:
        if not _DASH:
            raise ImportError(
                "The 'dash' package is required for the Agent V dashboard.  "
                "Install it with:  pip install dash plotly"
            )
        self._conv_monitor = ConvergenceMonitor()
        self._status_monitor = AgentStatusMonitor()
        self._viewer = StructureViewer()

        # Register custom plotly template
        if _PLOTLY:
            tpl = plotly_template()
            if tpl:
                pio.templates["oae"] = tpl
                pio.templates.default = "oae"

        self._app = dash.Dash(
            __name__,
            title="OAE — Crystal Structure Explorer",
            update_title=None,  # prevent title flicker on poll
            suppress_callback_exceptions=True,
            external_stylesheets=[FONT_CDN],
        )
        self._app.layout = self._create_tabbed_layout()
        self.register_callbacks()
        # Register crystal editor callbacks
        try:
            from agent_v.editor.editor_callbacks import register_callbacks as register_editor_cbs
            register_editor_cbs(self._app)
        except Exception as e:
            logger.warning("Crystal editor callbacks not registered: %s", e)

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _create_tabbed_layout(self) -> Any:
        """Wrap monitor + editor in a Tabs component."""
        try:
            from agent_v.editor.editor_layout import create_editor_layout
            editor_tab = create_editor_layout()
        except Exception:
            editor_tab = html.Div("Crystal editor unavailable (missing dependencies)")

        return html.Div(
            style={
                "fontFamily": FONT_STACK,
                "margin": "0 auto",
                "maxWidth": "1440px",
                "padding": "16px 20px",
                "backgroundColor": SURFACE_ALT,
                "minHeight": "100vh",
            },
            children=[
                # Header
                header_bar(),

                # Tabs
                dcc.Tabs(
                    id="dashboard-tabs", value="monitor",
                    children=[
                        dcc.Tab(
                            label="Monitor", value="monitor",
                            children=[self.create_layout()],
                            style=tab_style(),
                            selected_style=tab_selected_style(),
                        ),
                        dcc.Tab(
                            label="Crystal Editor", value="editor",
                            children=[editor_tab],
                            style=tab_style(),
                            selected_style=tab_selected_style(),
                        ),
                    ],
                    style={"marginBottom": "16px"},
                ),
            ],
        )

    def create_layout(self) -> Any:
        """Build the four-panel Dash layout."""
        cif_options = _list_cif_files()
        dropdown_opts = [
            {"label": cf["label"], "value": cf["path"]}
            for cf in cif_options
        ]

        _dropdown_style = {
            "marginBottom": "8px",
            "fontFamily": FONT_STACK,
            "fontSize": "13px",
        }

        return html.Div(
            style={"padding": "4px 0"},
            children=[
                # Polling interval
                dcc.Interval(id="poll-interval", interval=_POLL_INTERVAL_MS, n_intervals=0),

                # ── Row 1: Structure Viewer + Convergence ──
                html.Div(
                    style={"display": "flex", "gap": "16px", "marginBottom": "16px"},
                    children=[
                        # Panel 1 — Structure viewer
                        html.Div(
                            style=card_style("1", "440px"),
                            children=[
                                html.H4("Crystal Structure Viewer", style=card_title_style()),
                                html.Div(
                                    style={"display": "flex", "gap": "8px", "marginBottom": "10px"},
                                    children=[
                                        dcc.Dropdown(
                                            id="cif-selector",
                                            options=dropdown_opts,
                                            value=dropdown_opts[0]["value"] if dropdown_opts else None,
                                            placeholder="Select a CIF file...",
                                            style={**_dropdown_style, "flex": "1"},
                                        ),
                                        dcc.Dropdown(
                                            id="view-mode-selector",
                                            options=_VIEW_MODES,
                                            value="ball-and-stick",
                                            clearable=False,
                                            style={**_dropdown_style, "width": "160px"},
                                        ),
                                    ],
                                ),
                                html.Div(id="structure-viewer-area",
                                         style={"minHeight": "350px"}),
                            ],
                        ),

                        # Panel 2 — Convergence
                        html.Div(
                            style=card_style("1"),
                            children=[
                                html.H4("Convergence History", style=card_title_style()),
                                dcc.Graph(
                                    id="convergence-line-chart",
                                    config={"displayModeBar": False},
                                    style={"height": "350px"},
                                ),
                                dcc.Graph(
                                    id="component-bar-chart",
                                    config={"displayModeBar": False},
                                    style={"height": "350px"},
                                ),
                            ],
                        ),
                    ],
                ),

                # ── Row 2: Agent Status + Candidate Table ──
                html.Div(
                    style={"display": "flex", "gap": "16px"},
                    children=[
                        # Panel 3 — Agent status
                        html.Div(
                            style=card_style("1"),
                            children=[
                                html.H4("Agent Status", style=card_title_style()),
                                html.Div(id="agent-status-table"),
                            ],
                        ),

                        # Panel 4 — Candidate table
                        html.Div(
                            style={**card_style("1.4"), "overflowX": "auto"},
                            children=[
                                html.H4("Top Candidates", style=card_title_style()),
                                html.Div(id="candidate-table-container"),
                            ],
                        ),
                    ],
                ),
            ],
        )

    # ------------------------------------------------------------------ #
    # Callbacks
    # ------------------------------------------------------------------ #

    def register_callbacks(self) -> None:
        """Wire Dash callbacks for live polling and interactivity."""

        app = self._app

        # --- Clock ---
        @app.callback(
            Output("clock", "children"),
            Input("poll-interval", "n_intervals"),
        )
        def update_clock(_n: int) -> str:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            return f"Last refresh: {now}"

        # --- Structure viewer (triggered by dropdown + view mode) ---
        @app.callback(
            Output("structure-viewer-area", "children"),
            [Input("cif-selector", "value"),
             Input("view-mode-selector", "value")],
        )
        def update_viewer(cif_path: Optional[str], view_mode: Optional[str]) -> Any:
            if not cif_path:
                return html.P("No CIF file selected.",
                              style={"color": "#9CA3AF", "textAlign": "center",
                                     "padding": "60px 0"})
            p = Path(cif_path)
            if not p.exists():
                return html.P(f"File not found: {p.name}",
                              style={"color": "#E63946", "textAlign": "center"})
            style = view_mode or "ball-and-stick"
            html_str = self._viewer.render_cif(p, style=style)
            return html.Div([
                html.Iframe(
                    srcDoc=html_str,
                    style={"width": "100%", "height": "420px", "border": "none",
                           "borderRadius": "8px"},
                )
            ])

        # --- Convergence line chart ---
        @app.callback(
            Output("convergence-line-chart", "figure"),
            Input("poll-interval", "n_intervals"),
        )
        def update_convergence_line(_n: int) -> Any:
            fig = self._conv_monitor.create_convergence_plot()
            return fig if fig else _empty_figure("No convergence data yet")

        # --- Component bar chart ---
        @app.callback(
            Output("component-bar-chart", "figure"),
            Input("poll-interval", "n_intervals"),
        )
        def update_component_bar(_n: int) -> Any:
            fig = self._conv_monitor.create_component_bar(record_index=-1)
            return fig if fig else _empty_figure("No component data")

        # --- Agent status table ---
        @app.callback(
            Output("agent-status-table", "children"),
            Input("poll-interval", "n_intervals"),
        )
        def update_agent_status(_n: int) -> Any:
            states = self._status_monitor.get_agent_states()
            if not states:
                return html.P("No agent data.",
                              style={"color": "#9CA3AF", "textAlign": "center"})

            rows = []
            for agent_name, info in states.items():
                state = info["state"]
                badge_el = html.Span(state, style=badge_style(state))
                last_active = info.get("last_active", "—")
                if last_active and last_active != "—":
                    try:
                        dt = datetime.fromisoformat(last_active)
                        last_active = dt.strftime("%H:%M:%S")
                    except Exception:
                        pass
                sec_ago = info.get("seconds_ago")
                age_str = f"{sec_ago:.0f}s ago" if sec_ago is not None else "—"
                files = info.get("file_count", 0)

                _td = {"padding": "8px 10px", "fontSize": "13px", "borderBottom": f"1px solid {BORDER}"}
                rows.append(
                    html.Tr([
                        html.Td(agent_name, style={**_td, "fontWeight": "600", "color": DARK_TEXT}),
                        html.Td(badge_el, style=_td),
                        html.Td(last_active, style={**_td, "fontFamily": FONT_MONO, "color": "#6B7280"}),
                        html.Td(age_str, style={**_td, "color": "#6B7280"}),
                        html.Td(str(files), style={**_td, "textAlign": "right", "color": "#6B7280"}),
                    ])
                )

            _th = {
                "textAlign": "left", "padding": "8px 10px",
                "borderBottom": f"2px solid {TEAL_500}",
                "color": DARK_TEXT, "fontSize": "12px",
                "fontWeight": "600", "textTransform": "uppercase",
                "letterSpacing": "0.5px",
            }
            return html.Table(
                style={"width": "100%", "borderCollapse": "collapse"},
                children=[
                    html.Thead(html.Tr([
                        html.Th("Agent", style=_th),
                        html.Th("State", style=_th),
                        html.Th("Last Active", style=_th),
                        html.Th("Age", style=_th),
                        html.Th("Files", style={**_th, "textAlign": "right"}),
                    ])),
                    html.Tbody(rows),
                ],
            )

        # --- Candidate table ---
        @app.callback(
            Output("candidate-table-container", "children"),
            Input("poll-interval", "n_intervals"),
        )
        def update_candidates(_n: int) -> Any:
            rows = _load_candidates_csv()
            if not rows:
                return html.P("No candidate data found.",
                              style={"color": "#9CA3AF", "textAlign": "center"})

            columns = list(rows[0].keys())

            # Rename columns for readability
            col_map = {
                "formula": "Formula",
                "space_group": "Space Group",
                "sg_number": "SG #",
                "tc_predicted": "Tc (K)",
                "tc_pred": "Tc (K)",
                "energy_above_hull": "E_hull (meV)",
                "e_above_hull": "E_hull (meV)",
                "family": "Family",
                "score": "Score",
                "confidence": "Confidence",
            }

            display_cols = []
            for c in columns:
                display_cols.append({"name": col_map.get(c, c), "id": c})

            return dash_table.DataTable(
                data=rows[:50],  # cap at 50 for performance
                columns=display_cols,
                style_table={"overflowX": "auto", "borderRadius": "8px"},
                style_header=table_header_style(),
                style_cell=table_cell_style(),
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": SURFACE_ALT,
                    },
                    {
                        "if": {"state": "active"},
                        "backgroundColor": "#EFF6FF",
                    },
                ],
                page_size=15,
                sort_action="native",
                filter_action="native",
            )

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #

    def run(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        debug: bool = False,
    ) -> None:
        """Start the Dash development server."""
        host = host or DASH_HOST
        port = port or DASH_PORT
        logger.info("Starting Agent V dashboard on http://%s:%d", host, port)
        self._app.run(host=host, port=port, debug=debug)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and launch the dashboard."""

    parser = argparse.ArgumentParser(
        prog="agent_v.dashboard",
        description="Agent V — Crystal Prediction Visualization Dashboard",
    )
    parser.add_argument(
        "--host", default=DASH_HOST,
        help=f"Bind address (default: {DASH_HOST})",
    )
    parser.add_argument(
        "--port", type=int, default=DASH_PORT,
        help=f"Port (default: {DASH_PORT})",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable Dash debug mode with hot reload",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Set log level to DEBUG",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        dashboard = AgentVDashboard()
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Install dependencies:  pip install dash plotly", file=sys.stderr)
        sys.exit(1)

    dashboard.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
