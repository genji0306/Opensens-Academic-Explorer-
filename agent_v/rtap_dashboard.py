"""
RTAP Exploration Dashboard — Run & Visualize Discovery Loop
=============================================================
Interactive Dash dashboard that:

1. **Launches** the RTAP discovery loop from the browser
2. **Monitors** convergence in real-time during the run
3. **Animates** results using plotly (Tc race, convergence pulse, radar)
4. **Displays** top RT candidates and family breakdown

Panels:
  - Control Panel: Start/stop RTAP loop, set parameters
  - Live Convergence: Animated line + component scores
  - Family Tc Race: Animated bar chart of family mean Tc over iterations
  - RTAP Radar: Animated radar of 6 score components
  - Candidate Table: Top RT candidates (Tc >= 273K at P <= 1 GPa)
  - MC3D Status: Reference structure counts from Materials Cloud

Usage::

    python3 -m agent_v.rtap_dashboard --port 8051
    python3 -m agent_v.rtap_dashboard --port 8051 --debug

Or from Python::

    from agent_v.rtap_dashboard import RTAPDashboard
    app = RTAPDashboard()
    app.run(debug=True)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentV.RTAPDashboard")

# ---------------------------------------------------------------------------
# Optional Dash / Plotly
# ---------------------------------------------------------------------------
try:
    import dash
    from dash import dcc, html, dash_table
    from dash.dependencies import Input, Output, State
    _DASH = True
except ImportError:
    _DASH = False
    logger.warning("dash not installed.  pip install dash plotly")

try:
    import plotly.graph_objects as go
    import plotly.express as px
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from agent_v.config import (
    DATA_DIR,
    REPORTS_DIR,
    PROJECT_ROOT,
    FAMILY_COLORS,
)

# RTAP-specific paths
RTAP_DIR = DATA_DIR / "rtap"
RTAP_CANDIDATES_DIR = RTAP_DIR / "candidates"
CONVERGENCE_HISTORY_PATH = REPORTS_DIR / "convergence_history.json"
FINAL_REPORT_PATH = REPORTS_DIR / "final_report.json"
SYNTHETIC_DIR = DATA_DIR / "synthetic"

# Dashboard defaults
RTAP_DASH_HOST = "127.0.0.1"
RTAP_DASH_PORT = 8051
_POLL_MS = 3_000  # 3 seconds

# Dark theme colors (matching ANIMATION_GUIDELINE.md)
DARK_BG = "#0D1117"
DARK_PANEL = "#161B22"
DARK_BORDER = "#30363D"
ACCENT_CYAN = "#58A6FF"
ACCENT_GREEN = "#3FB950"
ACCENT_RED = "#F85149"
TEXT_PRIMARY = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"

# RTAP score component colors
COMPONENT_COLORS = {
    "ambient_tc_score": "#E63946",
    "ambient_stability_score": "#2A9D8F",
    "synthesizability_score": "#E9C46A",
    "electronic_indicator_score": "#457B9D",
    "mechanism_plausibility_score": "#F4A261",
    "composition_validity": "#264653",
}

# Family colors extended for RTAP
RTAP_FAMILY_COLORS = {
    "cuprate": "#E63946",
    "nickelate": "#F4A261",
    "hydride": "#E9C46A",
    "iron-pnictide": "#457B9D",
    "iron-chalcogenide": "#1D3557",
    "kagome": "#2A9D8F",
    "ternary-hydride": "#FFD700",
    "infinite-layer": "#FF6B6B",
    "topological": "#A8DADC",
    "2d-heterostructure": "#DDA15E",
    "carbon-based": "#606C38",
    "engineered-cuprate": "#BC6C25",
    "mof-sc": "#9B5DE5",
    "flat-band": "#00BBF9",
}


# ---------------------------------------------------------------------------
# State management for async run
# ---------------------------------------------------------------------------

class RTAPRunState:
    """Thread-safe state for the RTAP exploration loop."""

    def __init__(self):
        self.running = False
        self.process: Optional[subprocess.Popen] = None
        self.log_lines: list[str] = []
        self.start_time: Optional[float] = None
        self._lock = threading.Lock()

    def start(self, max_iterations: int = 20, target: float = 0.85):
        """Launch RTAP loop as a subprocess."""
        if self.running:
            return
        with self._lock:
            self.running = True
            self.log_lines = []
            self.start_time = time.time()

        cmd = [
            sys.executable, str(PROJECT_ROOT / "run.py"),
            "--rtap",
            "--max-iterations", str(max_iterations),
            "--target", str(target),
            "-v",
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        # Read output in background thread
        t = threading.Thread(target=self._read_output, daemon=True)
        t.start()

    def _read_output(self):
        """Read subprocess output line by line."""
        if not self.process:
            return
        for line in self.process.stdout:
            with self._lock:
                self.log_lines.append(line.rstrip())
                # Keep last 500 lines
                if len(self.log_lines) > 500:
                    self.log_lines = self.log_lines[-500:]
        self.process.wait()
        with self._lock:
            self.running = False

    def stop(self):
        """Terminate the running process."""
        if self.process and self.running:
            self.process.terminate()
            with self._lock:
                self.running = False
                self.log_lines.append("--- Process terminated by user ---")

    def get_status(self) -> dict:
        """Return current state."""
        with self._lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            return {
                "running": self.running,
                "elapsed": elapsed,
                "log_tail": "\n".join(self.log_lines[-30:]),
                "total_lines": len(self.log_lines),
            }


# Singleton state
_run_state = RTAPRunState()


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_convergence_history() -> list[dict]:
    """Load convergence history from JSON."""
    if not CONVERGENCE_HISTORY_PATH.exists():
        return []
    try:
        with open(CONVERGENCE_HISTORY_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def _load_final_report() -> dict:
    """Load the final report if available."""
    if not FINAL_REPORT_PATH.exists():
        return {}
    try:
        with open(FINAL_REPORT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _load_latest_properties() -> Optional["pd.DataFrame"]:
    """Load the latest properties.csv from synthetic data."""
    try:
        import pandas as pd
        # Find latest iteration directory
        iter_dirs = sorted(SYNTHETIC_DIR.glob("iteration_*"))
        if not iter_dirs:
            return None
        latest = iter_dirs[-1]
        csv_path = latest / "properties.csv"
        if csv_path.exists():
            return pd.read_csv(csv_path)
    except Exception:
        pass
    return None


def _load_rt_candidates() -> list[dict]:
    """Load flagged RT candidates."""
    if not RTAP_CANDIDATES_DIR.exists():
        return []
    rows = []
    for f in sorted(RTAP_CANDIDATES_DIR.glob("rt_candidates_iter_*.csv")):
        try:
            with open(f, newline="") as fh:
                reader = csv.DictReader(fh)
                rows.extend(list(reader))
        except Exception:
            pass
    return rows


# ---------------------------------------------------------------------------
# Plotly figures
# ---------------------------------------------------------------------------

def _dark_layout(fig: "go.Figure", title: str = "", height: int = 350) -> "go.Figure":
    """Apply dark theme to a plotly figure."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=DARK_PANEL,
        plot_bgcolor=DARK_BG,
        font=dict(color=TEXT_PRIMARY, family="JetBrains Mono, monospace"),
        title=dict(text=title, font=dict(size=14)),
        height=height,
        margin=dict(l=40, r=20, t=40, b=30),
    )
    return fig


def _empty_figure(msg: str = "No data") -> "go.Figure":
    """Blank figure with centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=msg, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=14, color=TEXT_SECONDARY),
    )
    return _dark_layout(fig)


def create_convergence_figure(history: list[dict]) -> "go.Figure":
    """Line chart of RTAP convergence score over iterations."""
    if not history:
        return _empty_figure("No convergence data — start an RTAP run")

    iterations = [h.get("iteration", i) for i, h in enumerate(history)]
    scores = [h.get("convergence_score", h.get("score", 0)) for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=iterations, y=scores,
        mode="lines+markers",
        name="RTAP Score",
        line=dict(color=ACCENT_CYAN, width=3),
        marker=dict(size=8, color=ACCENT_CYAN),
    ))
    # Target line
    fig.add_hline(y=0.85, line_dash="dash", line_color=ACCENT_GREEN,
                  annotation_text="Target 0.85")
    fig.add_hline(y=0.95, line_dash="dot", line_color=ACCENT_RED,
                  annotation_text="Stretch 0.95")

    fig.update_xaxes(title="Iteration")
    fig.update_yaxes(title="Score", range=[0, 1.05])
    return _dark_layout(fig, "RTAP Convergence", height=300)


def create_component_radar(history: list[dict]) -> "go.Figure":
    """Radar chart of the latest RTAP score components."""
    if not history:
        return _empty_figure("No component data")

    latest = history[-1]
    components = latest.get("component_scores", {})
    if not components:
        return _empty_figure("No component scores in latest record")

    labels = list(components.keys())
    values = [components[k] for k in labels]
    # Close the polygon
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    colors = [COMPONENT_COLORS.get(k, ACCENT_CYAN) for k in labels]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=[k.replace("_score", "").replace("_", " ").title() for k in labels_closed],
        fill="toself",
        fillcolor="rgba(88, 166, 255, 0.15)",
        line=dict(color=ACCENT_CYAN, width=2),
        marker=dict(size=6, color=ACCENT_CYAN),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=DARK_BG,
            radialaxis=dict(visible=True, range=[0, 1.05], gridcolor=DARK_BORDER),
            angularaxis=dict(gridcolor=DARK_BORDER),
        ),
    )
    return _dark_layout(fig, "Score Components", height=350)


def create_family_tc_chart(df: "pd.DataFrame") -> "go.Figure":
    """Bar chart of mean Tc per family."""
    if df is None or df.empty:
        return _empty_figure("No synthetic data")

    tc_col = "ambient_pressure_Tc_K" if "ambient_pressure_Tc_K" in df.columns else "predicted_Tc_K"
    if tc_col not in df.columns:
        return _empty_figure("No Tc data")

    family_col = "pattern_id"
    if family_col not in df.columns:
        return _empty_figure("No pattern_id column")

    # Extract family from pattern_id
    df = df.copy()
    df["family"] = df["pattern_id"].apply(lambda x: x.rsplit("-", 1)[0] if isinstance(x, str) else "unknown")
    family_means = df.groupby("family")[tc_col].mean().sort_values(ascending=True)

    colors = [RTAP_FAMILY_COLORS.get(f, TEXT_SECONDARY) for f in family_means.index]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=family_means.values,
        y=family_means.index,
        orientation="h",
        marker_color=colors,
    ))
    fig.add_vline(x=273, line_dash="dash", line_color=ACCENT_RED,
                  annotation_text="273K (RT)")
    fig.update_xaxes(title="Mean Tc (K)")
    fig.update_yaxes(title="")
    return _dark_layout(fig, "Family Mean Tc", height=400)


def create_mechanism_pie(df: "pd.DataFrame") -> "go.Figure":
    """Pie chart of pairing mechanism distribution."""
    if df is None or df.empty or "primary_mechanism" not in df.columns:
        return _empty_figure("No mechanism data")

    mech_counts = df["primary_mechanism"].value_counts()
    mech_colors = {
        "bcs": "#457B9D", "spin_fluctuation": "#E63946",
        "flat_band": "#2A9D8F", "excitonic": "#E9C46A",
        "hydride_cage": "#F4A261", "mixed": "#264653",
    }
    colors = [mech_colors.get(m, TEXT_SECONDARY) for m in mech_counts.index]

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=mech_counts.index,
        values=mech_counts.values,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hole=0.4,
    ))
    return _dark_layout(fig, "Pairing Mechanisms", height=300)


# ---------------------------------------------------------------------------
# Dashboard class
# ---------------------------------------------------------------------------

class RTAPDashboard:
    """Interactive RTAP Exploration Dashboard."""

    def __init__(self) -> None:
        if not _DASH:
            raise ImportError("dash required: pip install dash plotly")

        self._app = dash.Dash(
            __name__,
            title="RTAP Discovery Dashboard",
            update_title="Running...",
        )
        self._app.layout = self._create_layout()
        self._register_callbacks()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _create_layout(self) -> Any:
        return html.Div(
            style={
                "fontFamily": "JetBrains Mono, Fira Code, monospace",
                "backgroundColor": DARK_BG,
                "color": TEXT_PRIMARY,
                "minHeight": "100vh",
                "padding": "16px",
            },
            children=[
                # Header
                html.Div(
                    style={"textAlign": "center", "marginBottom": "16px"},
                    children=[
                        html.H1(
                            "RTAP Discovery Dashboard",
                            style={"color": ACCENT_CYAN, "margin": "0", "fontSize": "24px"},
                        ),
                        html.P(
                            "OAE — Room-Temperature Ambient-Pressure Discovery",
                            style={"color": TEXT_SECONDARY, "margin": "4px 0"},
                        ),
                        html.P(id="rtap-clock", style={"color": TEXT_SECONDARY, "fontSize": "12px"}),
                    ],
                ),

                # Polling
                dcc.Interval(id="rtap-poll", interval=_POLL_MS, n_intervals=0),

                # Row 1: Controls + Convergence + Radar
                html.Div(
                    style={"display": "flex", "gap": "12px", "marginBottom": "12px"},
                    children=[
                        # Control panel
                        html.Div(
                            style=self._panel_style("0.7"),
                            children=[
                                html.H4("Control", style={"color": ACCENT_CYAN, "marginTop": "0"}),
                                html.Label("Max Iterations:", style={"fontSize": "12px"}),
                                dcc.Input(
                                    id="rtap-max-iter", type="number", value=20,
                                    min=1, max=50,
                                    style=self._input_style(),
                                ),
                                html.Label("Target Score:", style={"fontSize": "12px", "marginTop": "8px"}),
                                dcc.Input(
                                    id="rtap-target", type="number", value=0.85,
                                    min=0.5, max=1.0, step=0.01,
                                    style=self._input_style(),
                                ),
                                html.Div(style={"marginTop": "12px"}, children=[
                                    html.Button(
                                        "Start RTAP",
                                        id="rtap-start-btn",
                                        style=self._btn_style(ACCENT_GREEN),
                                    ),
                                    html.Button(
                                        "Stop",
                                        id="rtap-stop-btn",
                                        style={**self._btn_style(ACCENT_RED), "marginLeft": "8px"},
                                    ),
                                ]),
                                html.Div(id="rtap-status", style={
                                    "marginTop": "12px", "fontSize": "12px",
                                    "color": TEXT_SECONDARY,
                                }),
                            ],
                        ),
                        # Convergence chart
                        html.Div(
                            style=self._panel_style("1.3"),
                            children=[
                                dcc.Graph(id="rtap-convergence", config={"displayModeBar": False}),
                            ],
                        ),
                        # Radar chart
                        html.Div(
                            style=self._panel_style("1"),
                            children=[
                                dcc.Graph(id="rtap-radar", config={"displayModeBar": False}),
                            ],
                        ),
                    ],
                ),

                # Row 2: Family Tc + Mechanism Pie
                html.Div(
                    style={"display": "flex", "gap": "12px", "marginBottom": "12px"},
                    children=[
                        html.Div(
                            style=self._panel_style("1.5"),
                            children=[
                                dcc.Graph(id="rtap-family-tc", config={"displayModeBar": False}),
                            ],
                        ),
                        html.Div(
                            style=self._panel_style("1"),
                            children=[
                                dcc.Graph(id="rtap-mechanism-pie", config={"displayModeBar": False}),
                            ],
                        ),
                    ],
                ),

                # Row 3: Candidate table + Log
                html.Div(
                    style={"display": "flex", "gap": "12px"},
                    children=[
                        html.Div(
                            style=self._panel_style("1.5"),
                            children=[
                                html.H4("RT Candidates (Tc >= 273K)", style={"color": ACCENT_CYAN, "marginTop": "0"}),
                                html.Div(id="rtap-candidates-table"),
                            ],
                        ),
                        html.Div(
                            style=self._panel_style("1"),
                            children=[
                                html.H4("Run Log", style={"color": ACCENT_CYAN, "marginTop": "0"}),
                                html.Pre(
                                    id="rtap-log",
                                    style={
                                        "backgroundColor": DARK_BG,
                                        "color": ACCENT_GREEN,
                                        "padding": "8px",
                                        "borderRadius": "4px",
                                        "fontSize": "11px",
                                        "maxHeight": "350px",
                                        "overflowY": "auto",
                                        "whiteSpace": "pre-wrap",
                                        "border": f"1px solid {DARK_BORDER}",
                                    },
                                ),
                            ],
                        ),
                    ],
                ),

                # Hidden div for triggering
                html.Div(id="rtap-trigger-start", style={"display": "none"}),
                html.Div(id="rtap-trigger-stop", style={"display": "none"}),
            ],
        )

    @staticmethod
    def _panel_style(flex: str = "1") -> dict:
        return {
            "flex": flex,
            "border": f"1px solid {DARK_BORDER}",
            "borderRadius": "8px",
            "padding": "12px",
            "backgroundColor": DARK_PANEL,
        }

    @staticmethod
    def _input_style() -> dict:
        return {
            "width": "100%",
            "padding": "6px",
            "backgroundColor": DARK_BG,
            "color": TEXT_PRIMARY,
            "border": f"1px solid {DARK_BORDER}",
            "borderRadius": "4px",
            "fontSize": "13px",
        }

    @staticmethod
    def _btn_style(color: str) -> dict:
        return {
            "padding": "8px 16px",
            "backgroundColor": color,
            "color": "#fff",
            "border": "none",
            "borderRadius": "6px",
            "cursor": "pointer",
            "fontWeight": "bold",
            "fontSize": "13px",
        }

    # ------------------------------------------------------------------ #
    # Callbacks
    # ------------------------------------------------------------------ #

    def _register_callbacks(self) -> None:
        app = self._app

        # Clock
        @app.callback(Output("rtap-clock", "children"), Input("rtap-poll", "n_intervals"))
        def update_clock(_n):
            return f"Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"

        # Start button
        @app.callback(
            Output("rtap-trigger-start", "children"),
            Input("rtap-start-btn", "n_clicks"),
            State("rtap-max-iter", "value"),
            State("rtap-target", "value"),
            prevent_initial_call=True,
        )
        def start_rtap(n_clicks, max_iter, target):
            if n_clicks:
                _run_state.start(max_iterations=max_iter or 20, target=target or 0.85)
            return ""

        # Stop button
        @app.callback(
            Output("rtap-trigger-stop", "children"),
            Input("rtap-stop-btn", "n_clicks"),
            prevent_initial_call=True,
        )
        def stop_rtap(n_clicks):
            if n_clicks:
                _run_state.stop()
            return ""

        # Status + log
        @app.callback(
            [Output("rtap-status", "children"), Output("rtap-log", "children")],
            Input("rtap-poll", "n_intervals"),
        )
        def update_status(_n):
            status = _run_state.get_status()
            if status["running"]:
                elapsed = f"{status['elapsed']:.0f}s"
                state_text = f"Running... ({elapsed})"
            else:
                report = _load_final_report()
                if report:
                    score = report.get("final_convergence_score", 0)
                    reason = report.get("termination_reason", "unknown")
                    state_text = f"Complete: {score:.4f} ({reason})"
                else:
                    state_text = "Idle — press Start to begin"
            return state_text, status["log_tail"]

        # Convergence chart
        @app.callback(
            Output("rtap-convergence", "figure"),
            Input("rtap-poll", "n_intervals"),
        )
        def update_convergence(_n):
            history = _load_convergence_history()
            return create_convergence_figure(history)

        # Radar
        @app.callback(
            Output("rtap-radar", "figure"),
            Input("rtap-poll", "n_intervals"),
        )
        def update_radar(_n):
            history = _load_convergence_history()
            return create_component_radar(history)

        # Family Tc
        @app.callback(
            Output("rtap-family-tc", "figure"),
            Input("rtap-poll", "n_intervals"),
        )
        def update_family_tc(_n):
            df = _load_latest_properties()
            return create_family_tc_chart(df)

        # Mechanism pie
        @app.callback(
            Output("rtap-mechanism-pie", "figure"),
            Input("rtap-poll", "n_intervals"),
        )
        def update_mech_pie(_n):
            df = _load_latest_properties()
            return create_mechanism_pie(df)

        # Candidates table
        @app.callback(
            Output("rtap-candidates-table", "children"),
            Input("rtap-poll", "n_intervals"),
        )
        def update_candidates(_n):
            rows = _load_rt_candidates()
            if not rows:
                return html.P("No RT candidates flagged yet.", style={"color": TEXT_SECONDARY})

            # Select key columns
            key_cols = ["composition", "pattern_id", "ambient_pressure_Tc_K",
                        "predicted_Tc_K", "primary_mechanism", "energy_above_hull_meV"]
            available_cols = [c for c in key_cols if c in rows[0]]
            if not available_cols:
                available_cols = list(rows[0].keys())[:6]

            col_map = {
                "composition": "Formula",
                "pattern_id": "Family",
                "ambient_pressure_Tc_K": "Tc@0GPa (K)",
                "predicted_Tc_K": "Tc (K)",
                "primary_mechanism": "Mechanism",
                "energy_above_hull_meV": "E_hull (meV)",
            }
            columns = [{"name": col_map.get(c, c), "id": c} for c in available_cols]

            return dash_table.DataTable(
                data=rows[:100],
                columns=columns,
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": DARK_BG,
                    "color": ACCENT_CYAN,
                    "fontWeight": "bold",
                    "fontSize": "11px",
                    "borderBottom": f"1px solid {DARK_BORDER}",
                },
                style_cell={
                    "backgroundColor": DARK_PANEL,
                    "color": TEXT_PRIMARY,
                    "fontSize": "11px",
                    "padding": "4px 8px",
                    "border": f"1px solid {DARK_BORDER}",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": DARK_BG},
                ],
                page_size=15,
                sort_action="native",
            )

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #

    def run(self, host: str = RTAP_DASH_HOST, port: int = RTAP_DASH_PORT,
            debug: bool = False) -> None:
        """Start the dashboard server."""
        logger.info("RTAP Dashboard on http://%s:%d", host, port)
        self._app.run(host=host, port=port, debug=debug)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent_v.rtap_dashboard",
        description="RTAP Discovery Dashboard — Run & Visualize",
    )
    parser.add_argument("--host", default=RTAP_DASH_HOST)
    parser.add_argument("--port", type=int, default=RTAP_DASH_PORT)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        dashboard = RTAPDashboard()
    except ImportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    dashboard.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
