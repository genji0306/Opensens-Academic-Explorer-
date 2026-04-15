"""Visualization dashboard for the Riemann loop result.

This module turns the saved ``data/riemann/reports/final_report.json`` and
its review bundle into a self-contained HTML dashboard. The dashboard focuses
on what matters for the current run:

* convergence score growth across iterations,
* residual collapse as the spline capacity reaches the training size,
* in-sample versus holdout diagnostics, and
* the debate verdict that separates numerical usefulness from proof.
"""
from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.io import to_html
from plotly.subplots import make_subplots

from .core.config import REPORT_DIR

DEFAULT_REPORT_PATH = REPORT_DIR / "final_report.json"
DEFAULT_OUTPUT_PATH = REPORT_DIR / "riemann_result_dashboard.html"

TEAL = "#0f766e"
EMERALD = "#059669"
AMBER = "#d97706"
RED = "#dc2626"
SLATE = "#475569"
NAVY = "#0f172a"
SURFACE = "#f8fafc"
CARD = "#ffffff"
BORDER = "rgba(15, 23, 42, 0.08)"


def _fmt_float(value: Any, digits: int = 4, fallback: str = "n/a") -> str:
    try:
        if value is None:
            return fallback
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return fallback


def _fmt_percent(value: Any, digits: int = 1, fallback: str = "n/a") -> str:
    try:
        if value is None:
            return fallback
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return fallback


def _fmt_int(value: Any, fallback: str = "n/a") -> str:
    try:
        if value is None:
            return fallback
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return fallback


def _safe_text(value: Any, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_result_bundle(report_path: Path = DEFAULT_REPORT_PATH) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """Load the final report and any saved review files beside it."""

    report = _read_json(report_path)
    analysis: dict[str, Any] | None = None
    debate: dict[str, Any] | None = None

    analysis_path = report_path.with_name("math_analysis.json")
    if analysis_path.exists():
        analysis = _read_json(analysis_path)

    debate_path = report_path.with_name("math_debate.json")
    if debate_path.exists():
        debate = _read_json(debate_path)

    review = report.get("math_review")
    if analysis is None and isinstance(review, dict):
        maybe_analysis = review.get("analysis")
        if isinstance(maybe_analysis, dict):
            analysis = maybe_analysis
    if debate is None and isinstance(review, dict):
        maybe_debate = review.get("debate")
        if isinstance(maybe_debate, dict):
            debate = maybe_debate

    return report, analysis, debate


def _series(history: list[dict[str, Any]], key: str) -> list[float]:
    series: list[float] = []
    for item in history:
        try:
            series.append(float(item.get(key, np.nan)))
        except (TypeError, ValueError):
            series.append(float("nan"))
    return series


def _best_iteration(report: dict[str, Any]) -> int:
    best = report.get("best_iteration")
    if best is not None:
        try:
            return int(best)
        except (TypeError, ValueError):
            pass
    best_report = report.get("best_report", {})
    try:
        return int(best_report.get("iteration", 0))
    except (TypeError, ValueError):
        return 0


def _capacity_jump_iteration(analysis: dict[str, Any] | None) -> int | None:
    if not analysis:
        return None
    value = analysis.get("capacity_jump_iteration")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _finite_max(values: list[float], fallback: float = 1.0) -> float:
    finite = [v for v in values if np.isfinite(v)]
    if not finite:
        return fallback
    return max(finite)


def _add_vertical_marker(
    fig: go.Figure,
    x_value: int,
    xref: str,
    yref: str,
    y_max: float,
    color: str,
    dash: str,
) -> None:
    fig.add_shape(
        type="line",
        x0=x_value,
        x1=x_value,
        y0=0,
        y1=y_max,
        xref=xref,
        yref=yref,
        line=dict(color=color, width=1.5, dash=dash),
        layer="below",
    )


def _render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def _analysis_conclusion(report: dict[str, Any], analysis: dict[str, Any] | None) -> str:
    if analysis and analysis.get("conclusion"):
        return str(analysis["conclusion"])
    review = report.get("math_review")
    if isinstance(review, dict):
        maybe_analysis = review.get("analysis", {})
        if isinstance(maybe_analysis, dict) and maybe_analysis.get("conclusion"):
            return str(maybe_analysis["conclusion"])
    if report.get("converged"):
        return "The loop converged, but the review bundle is missing."
    return "The loop did not converge to a final principle."


def build_dashboard_figure(
    report: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    debate: dict[str, Any] | None = None,
) -> go.Figure:
    """Build the multi-panel Plotly figure used in the dashboard."""

    history = report.get("history") or []
    if not isinstance(history, list):
        history = []

    iterations = [int(item.get("iteration", idx + 1)) for idx, item in enumerate(history)]
    score = _series(history, "score")
    match_rate = _series(history, "match_rate")
    spacing_fit = _series(history, "spacing_fit")
    rmse = _series(history, "rmse")
    rel_error_median = _series(history, "rel_error_median")
    residual_abs_mean = _series(history, "residual_abs_mean")
    residual_abs_max = _series(history, "residual_abs_max")

    best_iter = _best_iteration(report)
    jump_iter = _capacity_jump_iteration(analysis)
    residual_axis_max = max(1.05, _finite_max(rmse + residual_abs_mean + residual_abs_max + rel_error_median) * 1.05)

    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{}, {}],
            [{"type": "table"}, {}],
        ],
        column_widths=[0.47, 0.53],
        row_heights=[0.48, 0.52],
        horizontal_spacing=0.08,
        vertical_spacing=0.14,
        subplot_titles=(
            "Convergence Trajectory",
            "Residual Collapse",
            "Result Snapshot",
            "Holdout Drift",
        ),
    )

    # Convergence trajectory.
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=score,
            mode="lines+markers",
            name="Score",
            line=dict(color=TEAL, width=2.5),
            marker=dict(size=7, color=TEAL),
            hovertemplate="iter=%{x}<br>score=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=match_rate,
            mode="lines+markers",
            name="Match rate",
            line=dict(color=EMERALD, width=2, dash="dash"),
            marker=dict(size=6, color=EMERALD),
            hovertemplate="iter=%{x}<br>match=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=spacing_fit,
            mode="lines+markers",
            name="Spacing fit",
            line=dict(color=SLATE, width=2, dash="dot"),
            marker=dict(size=6, color=SLATE),
            hovertemplate="iter=%{x}<br>spacing=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Residual collapse.
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=rmse,
            mode="lines+markers",
            name="RMSE",
            line=dict(color=RED, width=2.4),
            marker=dict(size=7, color=RED),
            hovertemplate="iter=%{x}<br>rmse=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=residual_abs_mean,
            mode="lines+markers",
            name="Residual mean",
            line=dict(color=AMBER, width=2, dash="dash"),
            marker=dict(size=6, color=AMBER),
            hovertemplate="iter=%{x}<br>mean abs residual=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=residual_abs_max,
            mode="lines+markers",
            name="Residual max",
            line=dict(color=SLATE, width=2, dash="dot"),
            marker=dict(size=6, color=SLATE),
            hovertemplate="iter=%{x}<br>max abs residual=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=rel_error_median,
            mode="lines+markers",
            name="Median rel. error",
            line=dict(color="#7c3aed", width=2, dash="dashdot"),
            marker=dict(size=6, color="#7c3aed"),
            hovertemplate="iter=%{x}<br>median rel. error=%{y:.4f}<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Snapshot table.
    principle = report.get("principle", {})
    analysis_refinement = (analysis or {}).get("refinement_mode_label") or _safe_text((analysis or {}).get("refinement_mode"))
    table_rows = [
        ("Training zeros", _fmt_int(report.get("n_zeros"))),
        ("Iterations run", _fmt_int(report.get("iterations_run"))),
        ("Best iteration", _fmt_int(report.get("best_iteration"))),
        ("Best score", _fmt_float(report.get("best_score"), 6)),
        ("In-sample match rate", _fmt_percent((report.get("best_report") or {}).get("match_rate"))),
        ("In-sample RMSE", _fmt_float((report.get("best_report") or {}).get("rmse"), 6)),
        ("Spline knots", _fmt_int((analysis or {}).get("spline_knots"))),
        ("Knot/sample ratio", _fmt_float((analysis or {}).get("knot_to_sample_ratio"), 2)),
        ("Holdout zeros", _fmt_int((analysis or {}).get("holdout_zeros"))),
        ("Holdout RMSE", _fmt_float((analysis or {}).get("holdout_rmse"))),
        ("Holdout MAE", _fmt_float((analysis or {}).get("holdout_mae"))),
        ("Holdout match rate", _fmt_percent((analysis or {}).get("holdout_match_rate"))),
        ("Nearest-index hit rate", _fmt_percent((analysis or {}).get("holdout_nearest_index_hit_rate"))),
        ("Max index offset", _fmt_int((analysis or {}).get("holdout_max_index_offset"))),
        ("Refinement mode", _safe_text(analysis_refinement)),
        ("Conclusion", _safe_text(_analysis_conclusion(report, analysis))),
    ]
    fig.add_trace(
        go.Table(
            header=dict(
                values=["Metric", "Value"],
                fill_color=TEAL,
                font=dict(color="white", size=12),
                align="left",
                height=28,
            ),
            cells=dict(
                values=[[row[0] for row in table_rows], [row[1] for row in table_rows]],
                fill_color=[[SURFACE] * len(table_rows), ["white"] * len(table_rows)],
                align=["left", "left"],
                font=dict(color=[NAVY, SLATE], size=11),
                height=28,
            ),
            columnwidth=[0.52, 0.48],
        ),
        row=2,
        col=1,
    )

    # Holdout drift scatter.
    mismatch_examples = []
    if analysis and isinstance(analysis.get("holdout_mismatch_examples"), list):
        mismatch_examples = analysis["holdout_mismatch_examples"]

    if mismatch_examples:
        pred = []
        target = []
        labels = []
        hover = []
        for example in mismatch_examples:
            try:
                pred.append(float(example["predicted_gamma"]))
                target.append(float(example["target_gamma"]))
                labels.append(f"n={int(example['n'])}")
                hover.append(
                    "n=%s<br>predicted=%.4f<br>target=%.4f<br>nearest_index=%s<br>offset=%s"
                    % (
                        example.get("n"),
                        float(example.get("predicted_gamma", 0.0)),
                        float(example.get("target_gamma", 0.0)),
                        example.get("nearest_index"),
                        example.get("index_offset"),
                    )
                )
            except (TypeError, ValueError, KeyError):
                continue

        if pred and target:
            lo = min(min(pred), min(target))
            hi = max(max(pred), max(target))
            pad = max((hi - lo) * 0.08, 0.5)
            fig.add_trace(
                go.Scatter(
                    x=[lo - pad, hi + pad],
                    y=[lo - pad, hi + pad],
                    mode="lines",
                    line=dict(color="#94a3b8", width=1.5, dash="dash"),
                    name="Perfect match",
                    hoverinfo="skip",
                    showlegend=False,
                ),
                row=2,
                col=2,
            )
            fig.add_trace(
                go.Scatter(
                    x=pred,
                    y=target,
                    mode="markers+text",
                    text=labels,
                    textposition="top center",
                    name="Mismatch examples",
                    marker=dict(size=11, color=RED, line=dict(color="white", width=1.2)),
                    hovertext=hover,
                    hovertemplate="%{hovertext}<extra></extra>",
                ),
                row=2,
                col=2,
            )
            fig.update_xaxes(range=[lo - pad, hi + pad], row=2, col=2)
            fig.update_yaxes(range=[lo - pad, hi + pad], row=2, col=2)
    else:
        fig.add_annotation(
            x=0.5,
            y=0.5,
            text="No holdout mismatch examples available",
            showarrow=False,
            font=dict(color=SLATE, size=13),
            row=2,
            col=2,
        )

    # Shared axis and layout styling.
    fig.update_xaxes(title_text="Iteration", row=1, col=1, dtick=1, gridcolor="rgba(15,23,42,0.08)")
    fig.update_xaxes(title_text="Iteration", row=1, col=2, dtick=1, gridcolor="rgba(15,23,42,0.08)")
    fig.update_xaxes(title_text="Predicted gamma", row=2, col=2, gridcolor="rgba(15,23,42,0.08)")
    fig.update_yaxes(title_text="Score / Rate", row=1, col=1, range=[0, 1.05], gridcolor="rgba(15,23,42,0.08)")
    fig.update_yaxes(title_text="Error", row=1, col=2, range=[0, residual_axis_max], gridcolor="rgba(15,23,42,0.08)")
    fig.update_yaxes(title_text="Target gamma", row=2, col=2, gridcolor="rgba(15,23,42,0.08)")
    if best_iter > 0:
        _add_vertical_marker(fig, best_iter, "x1", "y1", 1.05, TEAL, "dot")
        _add_vertical_marker(fig, best_iter, "x2", "y2", residual_axis_max, TEAL, "dot")
    if jump_iter and jump_iter > 0:
        _add_vertical_marker(fig, jump_iter, "x1", "y1", 1.05, RED, "dash")
        _add_vertical_marker(fig, jump_iter, "x2", "y2", residual_axis_max, RED, "dash")

    fig.update_layout(
        template="plotly_white",
        height=980,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=36, r=24, t=72, b=30),
        font=dict(family='Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', size=12, color=NAVY),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor=BORDER,
            borderwidth=1,
        ),
        hovermode="x unified",
        title=dict(
            text="Riemann loop result",
            x=0.02,
            xanchor="left",
            font=dict(size=20, color=NAVY),
        ),
    )

    return fig


def _render_metric_card(title: str, value: str, subtitle: str = "", accent: str = TEAL) -> str:
    subtitle_html = f"<span>{escape(subtitle)}</span>" if subtitle else ""
    return f"""
      <div class="metric-card" style="--accent: {accent};">
        <small>{escape(title)}</small>
        <strong>{escape(value)}</strong>
        {subtitle_html}
      </div>
    """


def _render_list(title: str, items: list[Any], tone: str = "neutral") -> str:
    if not items:
        body = "<p class='muted'>No items recorded.</p>"
    else:
        body = "".join(f"<li>{escape(_safe_text(item))}</li>" for item in items)
        body = f"<ul>{body}</ul>"
    return f"""
      <section class="panel panel-{tone}">
        <h2>{escape(title)}</h2>
        {body}
      </section>
    """


def _render_turns(debate: dict[str, Any] | None) -> str:
    if not debate:
        return """
          <section class="panel panel-neutral">
            <h2>Debate</h2>
            <p class="muted">No debate bundle was saved alongside the report.</p>
          </section>
        """

    turns = debate.get("turns", [])
    turn_cards = []
    for turn in turns:
        speaker = _safe_text(turn.get("speaker", "Unknown"))
        stance = _safe_text(turn.get("stance", "neutral")).lower()
        claim = _safe_text(turn.get("claim", ""))
        tone = "support" if stance == "support" else "challenge" if stance == "challenge" else "verdict" if stance == "verdict" else "neutral"
        turn_cards.append(
            f"""
              <div class="turn turn-{tone}">
                <div class="turn-meta">{escape(speaker)} <span>{escape(stance)}</span></div>
                <p>{escape(claim)}</p>
              </div>
            """
        )

    open_questions = debate.get("open_questions", [])
    summary = _safe_text(debate.get("summary", ""))
    verdict = _safe_text(debate.get("verdict", ""))
    return f"""
      <section class="panel panel-neutral">
        <h2>Debate</h2>
        <div class="turn-stack">
          {''.join(turn_cards)}
        </div>
        <div class="callout">
          <strong>Verdict</strong>
          <p>{escape(verdict)}</p>
          <p class="muted">{escape(summary)}</p>
        </div>
        <div class="question-list">
          <strong>Open questions</strong>
          <ul>
            {''.join(f'<li>{escape(_safe_text(q))}</li>' for q in open_questions)}
          </ul>
        </div>
      </section>
    """


def render_dashboard_html(
    report: dict[str, Any],
    analysis: dict[str, Any] | None,
    debate: dict[str, Any] | None,
    figure_html: str,
) -> str:
    conclusion = _analysis_conclusion(report, analysis)
    best_score = _fmt_float(report.get("best_score"), 6)
    holdout_rmse = _fmt_float((analysis or {}).get("holdout_rmse"))
    holdout_hit_rate = _fmt_percent((analysis or {}).get("holdout_nearest_index_hit_rate"))
    refinement_mode = _safe_text((analysis or {}).get("refinement_mode_label") or (analysis or {}).get("refinement_mode"))
    spline_knots = _fmt_int((analysis or {}).get("spline_knots"))
    knot_ratio = _fmt_float((analysis or {}).get("knot_to_sample_ratio"), 2)
    final_report_path = _safe_text(report.get("math_review", {}).get("analysis_path")) if isinstance(report.get("math_review"), dict) else ""

    metrics_html = "".join(
        [
            _render_metric_card("Best score", best_score, "Highest composite score reached"),
            _render_metric_card("Holdout RMSE", holdout_rmse, "Next-zero slice error"),
            _render_metric_card("Holdout hit rate", holdout_hit_rate, "Nearest-index accuracy"),
            _render_metric_card("Spline knots", spline_knots, f"Knot/sample ratio: {knot_ratio}"),
        ]
    )

    findings = (analysis or {}).get("findings", [])
    red_flags = (analysis or {}).get("red_flags", [])
    recommendations = (analysis or {}).get("recommendations", [])
    analysis_summary = _safe_text((analysis or {}).get("conclusion", conclusion))

    detail_html = f"""
      <div class="detail-grid">
        {_render_list("Findings", findings, tone="support")}
        {_render_turns(debate)}
        {_render_list("Red flags", red_flags, tone="warning")}
        {_render_list("Recommendations", recommendations, tone="neutral")}
      </div>
    """

    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Riemann Result Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --card: #ffffff;
      --card-soft: rgba(255, 255, 255, 0.86);
      --text: #0f172a;
      --muted: #5b6779;
      --border: rgba(15, 23, 42, 0.09);
      --shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
      --teal: #0f766e;
      --emerald: #059669;
      --amber: #d97706;
      --red: #dc2626;
      --slate: #475569;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.14), transparent 28%),
        radial-gradient(circle at top right, rgba(217, 119, 6, 0.12), transparent 24%),
        linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
    }
    .shell {
      max-width: 1320px;
      margin: 0 auto;
      padding: 28px 24px 40px;
    }
    .hero {
      position: relative;
      overflow: hidden;
      border-radius: 30px;
      padding: 30px 32px 28px;
      color: white;
      background:
        linear-gradient(135deg, #0f172a 0%, #0f766e 58%, #134e4a 100%);
      box-shadow: 0 30px 80px rgba(15, 23, 42, 0.18);
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -90px -130px auto;
      width: 320px;
      height: 320px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(45, 212, 191, 0.36), transparent 70%);
      filter: blur(12px);
      pointer-events: none;
    }
    .eyebrow {
      margin: 0 0 14px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 0.72rem;
      color: rgba(255, 255, 255, 0.72);
    }
    .hero h1 {
      margin: 0;
      max-width: 960px;
      font-size: clamp(2rem, 3.8vw, 3.3rem);
      line-height: 1.04;
      letter-spacing: -0.04em;
    }
    .hero p {
      margin: 14px 0 0;
      max-width: 980px;
      font-size: 1rem;
      line-height: 1.7;
      color: rgba(255, 255, 255, 0.84);
    }
    .hero-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.15);
      font-size: 0.8rem;
      color: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(8px);
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }
    .metric-card {
      background: var(--card-soft);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 16px 18px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
      border-top: 4px solid var(--accent);
    }
    .metric-card small {
      display: block;
      text-transform: uppercase;
      letter-spacing: 0.15em;
      font-size: 0.69rem;
      color: var(--muted);
    }
    .metric-card strong {
      display: block;
      margin-top: 8px;
      font-size: 1.5rem;
      line-height: 1.1;
      color: var(--text);
    }
    .metric-card span {
      display: block;
      margin-top: 6px;
      font-size: 0.82rem;
      color: var(--muted);
    }
    .chart-panel {
      margin-top: 18px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 16px;
    }
    .chart-panel h2 {
      margin: 0 0 14px;
      font-size: 1rem;
      letter-spacing: -0.02em;
    }
    .figure-wrap {
      border-radius: 22px;
      overflow: hidden;
      background: white;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }
    .panel {
      background: var(--card-soft);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 18px 18px 16px;
      box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
      backdrop-filter: blur(10px);
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 0.92rem;
      text-transform: uppercase;
      letter-spacing: 0.15em;
      color: var(--muted);
    }
    .panel ul {
      margin: 0;
      padding-left: 18px;
      color: var(--text);
      line-height: 1.65;
    }
    .panel li + li { margin-top: 8px; }
    .panel .muted {
      margin: 0;
      color: var(--muted);
      line-height: 1.65;
    }
    .panel-support { border-top: 4px solid var(--emerald); }
    .panel-warning { border-top: 4px solid var(--amber); }
    .panel-neutral { border-top: 4px solid var(--teal); }
    .turn-stack {
      display: grid;
      gap: 10px;
      margin-bottom: 14px;
    }
    .turn {
      padding: 12px 13px;
      border-radius: 18px;
      border: 1px solid var(--border);
      background: white;
    }
    .turn-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .turn-meta span {
      font-weight: 600;
      letter-spacing: 0.1em;
      color: inherit;
    }
    .turn p {
      margin: 0;
      line-height: 1.65;
      color: var(--text);
    }
    .turn-support {
      background: linear-gradient(180deg, rgba(5, 150, 105, 0.08), rgba(255, 255, 255, 0.96));
      border-color: rgba(5, 150, 105, 0.16);
    }
    .turn-challenge {
      background: linear-gradient(180deg, rgba(217, 119, 6, 0.1), rgba(255, 255, 255, 0.96));
      border-color: rgba(217, 119, 6, 0.18);
    }
    .turn-verdict {
      background: linear-gradient(180deg, rgba(15, 118, 110, 0.08), rgba(255, 255, 255, 0.96));
      border-color: rgba(15, 118, 110, 0.18);
    }
    .callout {
      margin-top: 14px;
      padding: 14px 14px 12px;
      border-radius: 18px;
      background: rgba(15, 118, 110, 0.06);
      border: 1px solid rgba(15, 118, 110, 0.12);
    }
    .callout strong {
      display: block;
      margin-bottom: 6px;
      color: var(--text);
    }
    .callout p {
      margin: 0;
      line-height: 1.65;
    }
    .question-list {
      margin-top: 14px;
    }
    .question-list strong {
      display: block;
      margin-bottom: 8px;
      color: var(--text);
    }
    .question-list ul {
      margin: 0;
      padding-left: 18px;
    }
    .question-list li + li { margin-top: 7px; }
    .footer {
      margin-top: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: space-between;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.6;
    }
    .footer code {
      background: rgba(15, 23, 42, 0.06);
      border: 1px solid rgba(15, 23, 42, 0.06);
      padding: 0.15rem 0.4rem;
      border-radius: 999px;
    }
    @media (max-width: 1100px) {
      .metric-grid, .detail-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 720px) {
      .shell { padding: 18px 12px 30px; }
      .hero { padding: 24px 20px; border-radius: 24px; }
      .metric-grid, .detail-grid {
        grid-template-columns: 1fr;
      }
      .chart-panel, .panel {
        border-radius: 20px;
      }
      .footer { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Riemann loop review</div>
      <h1>${headline}</h1>
      <p>${subhead}</p>
      <div class="hero-chips">
        <span class="chip">Refinement mode: ${refinement_mode}</span>
        <span class="chip">Best iteration: ${best_iteration}</span>
        <span class="chip">Best score: ${best_score}</span>
        <span class="chip">Holdout RMSE: ${holdout_rmse}</span>
        <span class="chip">Nearest-index hit rate: ${holdout_hit_rate}</span>
      </div>
    </section>

    <section class="metric-grid">
      ${metrics_html}
    </section>

    <section class="chart-panel">
      <h2>Visual summary</h2>
      <div class="figure-wrap">
        ${plot_html}
      </div>
    </section>

    ${detail_html}

    <div class="footer">
      <div>
        Generated from <code>${report_path}</code>
        ${analysis_path_note}
      </div>
      <div>
        ${analysis_summary}
      </div>
    </div>
  </div>
</body>
</html>"""

    analysis_path_note = ""
    if final_report_path:
        analysis_path_note = f" and review path <code>{escape(final_report_path)}</code>"

    headline = escape(conclusion)
    subhead = escape(
        (
            "The charts show the in-sample fit collapsing as spline capacity reaches the full training set, "
            "while the holdout diagnostics and debate summary reject a proof claim."
        )
        if analysis
        else "The charts show the saved loop history and any review artifacts that are available."
    )
    report_path = escape(str(report.get("source_report", DEFAULT_REPORT_PATH)))

    return _render_template(
        template,
        {
            "${headline}": headline,
            "${subhead}": subhead,
            "${refinement_mode}": escape(refinement_mode or "n/a"),
            "${best_iteration}": escape(_fmt_int(report.get("best_iteration"))),
            "${best_score}": escape(best_score),
            "${holdout_rmse}": escape(holdout_rmse),
            "${holdout_hit_rate}": escape(holdout_hit_rate),
            "${metrics_html}": metrics_html,
            "${plot_html}": figure_html,
            "${detail_html}": detail_html,
            "${report_path}": report_path,
            "${analysis_path_note}": analysis_path_note,
            "${analysis_summary}": escape(analysis_summary),
        },
    )


def write_dashboard(
    report_path: Path = DEFAULT_REPORT_PATH,
    output_path: Path | None = None,
) -> Path:
    """Render the dashboard HTML for the saved result."""

    report, analysis, debate = load_result_bundle(report_path)
    fig = build_dashboard_figure(report, analysis, debate)
    output = output_path or DEFAULT_OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    plot_html = to_html(
        fig,
        full_html=False,
        include_plotlyjs="inline",
        config={"displayModeBar": False, "responsive": True},
    )
    output.write_text(render_dashboard_html(report, analysis, debate, plot_html))
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a dashboard for the saved Riemann result.")
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to data/riemann/reports/final_report.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output HTML path (default data/riemann/reports/riemann_result_dashboard.html).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = write_dashboard(report_path=args.report, output_path=args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
