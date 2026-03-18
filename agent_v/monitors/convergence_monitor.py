"""
Convergence monitor for the multi-agent crystal prediction loop.

Reads ``data/reports/convergence_history.json`` and generates plotly
figures that track the composite convergence score and its 7 weighted
components across iterations.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from agent_v.config import REPORTS_DIR

logger = logging.getLogger("AgentV.Monitors.Convergence")

# ---------------------------------------------------------------------------
# Optional plotly
# ---------------------------------------------------------------------------
try:
    import plotly.graph_objects as go  # type: ignore[import-untyped]

    _PLOTLY = True
except ImportError:
    _PLOTLY = False
    logger.info("plotly not installed — convergence plots unavailable.")

# Score component labels (matches src/core/config.py SCORE_WEIGHTS keys)
_COMPONENT_LABELS: dict[str, str] = {
    "tc_distribution":         "Tc Distribution",
    "lattice_accuracy":        "Lattice Accuracy",
    "space_group_correctness": "Space Group",
    "electronic_property_match": "Electronic Match",
    "composition_validity":    "Composition Valid.",
    "coordination_geometry":   "Coordination Geom.",
    "pressure_tc_accuracy":    "Pressure-Tc Acc.",
}

# Colour per component (consistent across all charts)
_COMPONENT_COLORS: dict[str, str] = {
    "tc_distribution":         "#E63946",
    "lattice_accuracy":        "#457B9D",
    "space_group_correctness": "#2A9D8F",
    "electronic_property_match": "#E9C46A",
    "composition_validity":    "#F4A261",
    "coordination_geometry":   "#264653",
    "pressure_tc_accuracy":    "#A8DADC",
}


class ConvergenceMonitor:
    """Load and visualise the convergence history of the prediction loop."""

    def __init__(self, history_path: Optional[Path] = None) -> None:
        self._path = history_path or (REPORTS_DIR / "convergence_history.json")
        self._last_hash: str = ""
        self._cached_history: list[dict[str, Any]] = []
        self._cached_line_fig: Any = None
        self._cached_bar_fig: Any = None
        self._cached_bar_index: int = -1

    # ------------------------------------------------------------------ #
    # File change detection
    # ------------------------------------------------------------------ #

    def _file_hash(self) -> str:
        """Quick MD5 of the history file for change detection."""
        if not self._path.exists():
            return ""
        try:
            return hashlib.md5(self._path.read_bytes()).hexdigest()
        except Exception:
            return ""

    # ------------------------------------------------------------------ #
    # load_history
    # ------------------------------------------------------------------ #

    def load_history(self) -> list[dict[str, Any]]:
        """Read the convergence history JSON.

        Returns an empty list if the file is missing or unparseable.
        """
        if not self._path.exists():
            logger.warning("Convergence history not found at %s", self._path)
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                logger.error("Convergence history is not a JSON array.")
                return []
            logger.info("Loaded %d convergence records from %s", len(data), self._path)
            return data
        except Exception as exc:
            logger.error("Failed to load convergence history: %s", exc)
            return []

    def _load_if_changed(self) -> tuple[list[dict[str, Any]], bool]:
        """Load history only if file changed since last read."""
        current_hash = self._file_hash()
        if current_hash == self._last_hash and self._cached_history:
            return self._cached_history, False
        self._last_hash = current_hash
        self._cached_history = self.load_history()
        return self._cached_history, True

    # ------------------------------------------------------------------ #
    # create_convergence_plot
    # ------------------------------------------------------------------ #

    def create_convergence_plot(self) -> Optional[Any]:
        """Create a line chart of composite convergence score vs. record index.

        Uses file-hash caching and ``uirevision`` to prevent scroll jumps
        during periodic polling updates.

        Returns
        -------
        plotly.graph_objects.Figure or None
            ``None`` if plotly is not installed or history is empty.
        """
        if not _PLOTLY:
            logger.error("plotly required for create_convergence_plot.")
            return None

        history, changed = self._load_if_changed()
        if not history:
            return None

        # Return cached figure if data hasn't changed
        if not changed and self._cached_line_fig is not None:
            return self._cached_line_fig

        indices = list(range(len(history)))
        scores = [h.get("convergence_score", 0.0) for h in history]
        iterations = [h.get("iteration", "?") for h in history]
        timestamps = [h.get("timestamp", "") for h in history]

        # Hover text with iteration + timestamp
        hover = [
            f"Record {i}<br>Iteration {it}<br>Score {s:.4f}<br>{ts}"
            for i, it, s, ts in zip(indices, iterations, scores, timestamps)
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=indices,
            y=scores,
            mode="lines+markers",
            name="Convergence Score",
            line=dict(color="#E63946", width=2.5),
            marker=dict(size=5, line=dict(width=1, color="white")),
            text=hover,
            hoverinfo="text",
            fill="tozeroy",
            fillcolor="rgba(230,57,70,0.08)",
        ))

        # Target line
        target = 0.95  # default
        try:
            import importlib
            core_cfg = importlib.import_module("src.core.config")
            target = getattr(core_cfg, "CONVERGENCE_TARGET", 0.95)
        except Exception:
            pass

        fig.add_hline(
            y=target, line_dash="dash", line_color="#2A9D8F", line_width=2,
            annotation_text=f"Target {target}",
            annotation_position="top left",
            annotation_font=dict(size=11, color="#2A9D8F"),
        )

        fig.update_layout(
            title=dict(text="Convergence History", font=dict(size=14)),
            xaxis_title="Record #",
            yaxis_title="Score",
            yaxis_range=[0, 1.05],
            xaxis_range=[0, max(len(history), 1)],
            height=350,
            margin=dict(l=50, r=30, t=45, b=40),
            uirevision="convergence-line",  # preserves zoom/pan across updates
            showlegend=False,
            transition=dict(duration=300, easing="cubic-in-out"),
        )

        self._cached_line_fig = fig
        return fig

    # ------------------------------------------------------------------ #
    # create_component_bar
    # ------------------------------------------------------------------ #

    def create_component_bar(self, record_index: int = -1) -> Optional[Any]:
        """Create a bar chart of the 7 score components for a single record.

        Parameters
        ----------
        record_index : int
            Index into the history list.  ``-1`` selects the most recent.

        Returns
        -------
        plotly.graph_objects.Figure or None
        """
        if not _PLOTLY:
            logger.error("plotly required for create_component_bar.")
            return None

        history, changed = self._load_if_changed()
        if not history:
            return None

        # Return cached if data and index unchanged
        if not changed and self._cached_bar_fig is not None and self._cached_bar_index == record_index:
            return self._cached_bar_fig

        try:
            record = history[record_index]
        except IndexError:
            logger.error("Record index %d out of range (history has %d entries).",
                         record_index, len(history))
            return None

        components = record.get("component_scores", {})
        if not components:
            logger.warning("No component_scores in record %d.", record_index)
            return None

        labels = []
        values = []
        colors = []
        for key in _COMPONENT_LABELS:
            if key in components:
                labels.append(_COMPONENT_LABELS[key])
                values.append(components[key])
                colors.append(_COMPONENT_COLORS.get(key, "#888888"))

        iteration = record.get("iteration", "?")
        overall = record.get("convergence_score", 0.0)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            marker_line=dict(width=1, color="white"),
            text=[f"{v:.3f}" for v in values],
            textposition="outside",
            textfont=dict(size=11),
        ))

        fig.update_layout(
            title=dict(
                text=f"Component Scores — Iter {iteration}  ({overall:.4f})",
                font=dict(size=13),
            ),
            yaxis_title="Score",
            yaxis_range=[0, 1.15],
            height=350,
            margin=dict(l=50, r=30, t=45, b=80),
            xaxis_tickangle=-30,
            uirevision="convergence-bar",  # preserves UI state
        )

        self._cached_bar_fig = fig
        self._cached_bar_index = record_index
        return fig
