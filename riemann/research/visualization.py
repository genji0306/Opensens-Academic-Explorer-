"""Interactive dashboard for recursive RH research campaigns."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.io import to_html
from plotly.subplots import make_subplots

NAVY = "#0f172a"
TEAL = "#0f766e"
EMERALD = "#059669"
AMBER = "#d97706"
BLUE = "#2563eb"
ROSE = "#e11d48"
SLATE = "#475569"
SURFACE = "#f8fafc"
CARD = "#ffffff"
BORDER = "rgba(15, 23, 42, 0.08)"
DEFAULT_ALL_RESULTS_OUTPUT = "operator_rh_all_results_dashboard.html"


def _agent_color(agent: str) -> str:
    return {
        "M": AMBER,
        "Q": EMERALD,
        "T": BLUE,
        "K": ROSE,
    }.get(agent, SLATE)


def _agent_css(agent: str) -> str:
    return {
        "M": "m",
        "Q": "q",
        "T": "t",
        "K": "k",
    }.get(agent, "warn")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_campaign_bundle(campaign_dir: Path) -> dict[str, Any]:
    summary = _read_json(campaign_dir / "summary.json")
    approach_map = _safe_read(campaign_dir / "approach_map.json")
    operator_language = _safe_read(campaign_dir / "operator_language_v0.json")
    calibration = _safe_read(campaign_dir / "operator_calibration.json")
    failure_atlas = _safe_read(campaign_dir / "failure_atlas.json")
    certificate_report = _safe_read(campaign_dir / "certificate_report.json")
    obligation_ledger = _safe_read(campaign_dir / "obligation_ledger.json")
    campaign_benchmark = _safe_read(campaign_dir / "campaign_benchmark.json")
    dead_end_library = _safe_read(campaign_dir / "dead_end_library.json")

    rounds: list[dict[str, Any]] = []
    for eval_path in sorted(campaign_dir.glob("round_*_evaluations.json")):
        stem = eval_path.name.replace("_evaluations.json", "")
        rounds.append(
            {
                "round_index": int(stem.split("_")[1]),
                "hypotheses": _safe_read(campaign_dir / f"{stem}_hypotheses.json", []),
                "novelty": _safe_read(campaign_dir / f"{stem}_novelty.json", []),
                "evaluations": _safe_read(eval_path, []),
                "proposals": _safe_read(campaign_dir / f"{stem}_proposals.json", []),
            }
        )
    return {
        "campaign_dir": str(campaign_dir),
        "summary": summary,
        "approach_map": approach_map,
        "operator_language": operator_language,
        "calibration": calibration,
        "failure_atlas": failure_atlas,
        "certificate_report": certificate_report,
        "obligation_ledger": obligation_ledger,
        "campaign_benchmark": campaign_benchmark,
        "dead_end_library": dead_end_library,
        "rounds": rounds,
    }


def build_campaign_figure(bundle: dict[str, Any]) -> go.Figure:
    summary = bundle["summary"]
    history = summary.get("history", [])
    rounds = bundle.get("rounds", [])
    round_lookup = {int(item["round_index"]): item for item in rounds}

    round_ids = [int(item.get("round_index", idx + 1)) for idx, item in enumerate(history)]
    best_scores = [float(item.get("best_score", 0.0)) for item in history]
    proof_target = float(summary.get("proof_target", 0.92))

    accepted_m: list[int] = []
    accepted_q: list[int] = []
    accepted_t: list[int] = []
    complexity: list[float] = []
    support: list[float] = []
    agents: list[str] = []
    labels: list[str] = []
    top_rows: list[tuple[str, str, float, int]] = []

    for round_id in round_ids:
        round_payload = round_lookup.get(round_id, {})
        novelties = round_payload.get("novelty", [])
        evaluations = round_payload.get("evaluations", [])
        accepted_ids = {
            novelty_id
            for evaluation in evaluations
            for novelty_id in evaluation.get("novelty_artifact_ids", [])
        }
        novelty_by_id = {item.get("artifact_id", ""): item for item in novelties}
        accepted_m.append(sum(1 for novelty_id in accepted_ids if novelty_by_id.get(novelty_id, {}).get("agent") == "M"))
        accepted_q.append(sum(1 for novelty_id in accepted_ids if novelty_by_id.get(novelty_id, {}).get("agent") == "Q"))
        accepted_t.append(sum(1 for novelty_id in accepted_ids if novelty_by_id.get(novelty_id, {}).get("agent") == "T"))

        for item in novelties:
            features = item.get("measurable_features", {})
            feature_values = [float(v) for v in features.values()]
            feature_support = sum(feature_values) / max(len(feature_values), 1) if feature_values else 0.0
            complexity.append(float(item.get("operator_complexity", 0.0)))
            support.append(feature_support)
            agents.append(str(item.get("agent", "?")))
            labels.append(str(item.get("title", item.get("artifact_id", "artifact"))))

        if evaluations:
            best = max(evaluations, key=lambda item: float(item.get("score", 0.0)))
            hypothesis = next(
                (
                    item
                    for item in round_payload.get("hypotheses", [])
                    if item.get("candidate_id") == best.get("candidate_id")
                ),
                {},
            )
            families = "+".join(hypothesis.get("ingredient_families", []))
            top_rows.append(
                (
                    str(best.get("candidate_id", "")),
                    families or "n/a",
                    float(best.get("score", 0.0)),
                    len(best.get("novelty_artifact_ids", [])),
                )
            )

    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{}, {}],
            [{}, {"type": "table"}],
        ],
        subplot_titles=(
            "Best Score By Round",
            "Accepted Operator Artifacts",
            "Artifact Complexity vs Support",
            "Best Candidate Per Round",
        ),
        horizontal_spacing=0.12,
        vertical_spacing=0.16,
    )

    fig.add_trace(
        go.Scatter(
            x=round_ids,
            y=best_scores,
            mode="lines+markers",
            line=dict(color=TEAL, width=3),
            marker=dict(size=9, color=TEAL),
            name="Best score",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=round_ids,
            y=[proof_target] * len(round_ids),
            mode="lines",
            line=dict(color=ROSE, width=2, dash="dash"),
            name="Proof target",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(x=round_ids, y=accepted_m, name="M accepted", marker_color=AMBER),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(x=round_ids, y=accepted_q, name="Q accepted", marker_color=EMERALD),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(x=round_ids, y=accepted_t, name="T accepted", marker_color=BLUE),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Scatter(
            x=complexity,
            y=support,
            mode="markers",
            marker=dict(
                size=11,
                color=[_agent_color(item) for item in agents],
                line=dict(color=NAVY, width=0.5),
            ),
            text=labels,
            hovertemplate="<b>%{text}</b><br>complexity=%{x:.2f}<br>support=%{y:.2f}<extra></extra>",
            name="Artifacts",
        ),
        row=2,
        col=1,
    )

    if top_rows:
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Candidate", "Families", "Score", "Accepted novelty"],
                    fill_color=NAVY,
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[
                        [row[0] for row in top_rows],
                        [row[1] for row in top_rows],
                        [f"{row[2]:.4f}" for row in top_rows],
                        [str(row[3]) for row in top_rows],
                    ],
                    fill_color=CARD,
                    align="left",
                    font=dict(color=NAVY, size=11),
                    height=28,
                ),
            ),
            row=2,
            col=2,
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=SURFACE,
        plot_bgcolor=CARD,
        barmode="stack",
        height=900,
        margin=dict(l=48, r=36, t=90, b=42),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
    )
    fig.update_xaxes(title_text="Round", row=1, col=1)
    fig.update_yaxes(title_text="Score", range=[0, 1], row=1, col=1)
    fig.update_xaxes(title_text="Round", row=1, col=2)
    fig.update_yaxes(title_text="Accepted artifacts", row=1, col=2)
    fig.update_xaxes(title_text="Operator complexity", row=2, col=1)
    fig.update_yaxes(title_text="Measured support", range=[0, 1], row=2, col=1)
    return fig


def _quantum_branch_rows(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for round_payload in rounds:
        round_index = int(round_payload.get("round_index", 0))
        hypotheses = {
            str(item.get("candidate_id", "")): item
            for item in round_payload.get("hypotheses", [])
        }
        evaluations = round_payload.get("evaluations", [])
        for evaluation in evaluations:
            candidate_id = str(evaluation.get("candidate_id", ""))
            hypothesis = hypotheses.get(candidate_id, {})
            checks = tuple(str(item) for item in hypothesis.get("compatibility_checks", ()))
            branch_token = next((item for item in checks if item.startswith("quantum_branch=")), "")
            if not branch_token:
                continue
            branch_name = branch_token.split("=", 1)[1]
            rows.append(
                {
                    "branch": branch_name,
                    "round_index": round_index,
                    "candidate_id": candidate_id,
                    "score": float(evaluation.get("score", 0.0)),
                    "families": tuple(str(item) for item in hypothesis.get("ingredient_families", ())),
                    "claim": str(hypothesis.get("claim", "")),
                    "risk_flags": tuple(str(item) for item in hypothesis.get("risk_flags", ())),
                    "unresolved_obligations": tuple(
                        str(item) for item in hypothesis.get("unresolved_proof_obligations", ())
                    ),
                    "novelty_artifact_ids": tuple(str(item) for item in evaluation.get("novelty_artifact_ids", ())),
                    "contradiction_summary": str(evaluation.get("contradiction_summary", "")),
                }
            )
    rows.sort(key=lambda item: (item["branch"], item["round_index"], item["candidate_id"]))
    return rows


def _quantum_branch_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        branch = row["branch"]
        entry = summary.setdefault(
            branch,
            {
                "branch": branch,
                "count": 0,
                "best_score": 0.0,
                "best_candidate_id": "",
                "best_round_index": 0,
                "avg_score_total": 0.0,
            },
        )
        entry["count"] += 1
        entry["avg_score_total"] += float(row["score"])
        if float(row["score"]) >= float(entry["best_score"]):
            entry["best_score"] = float(row["score"])
            entry["best_candidate_id"] = str(row["candidate_id"])
            entry["best_round_index"] = int(row["round_index"])
    ordered = []
    for entry in summary.values():
        count = max(1, int(entry["count"]))
        ordered.append(
            {
                **entry,
                "avg_score": float(entry["avg_score_total"]) / count,
            }
        )
    ordered.sort(key=lambda item: (-item["best_score"], item["branch"]))
    return ordered


def _certificate_margin_rows(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for round_payload in rounds:
        round_index = int(round_payload.get("round_index", 0))
        hypotheses = {
            str(item.get("candidate_id", "")): item
            for item in round_payload.get("hypotheses", [])
        }
        for evaluation in round_payload.get("evaluations", []):
            candidate_id = str(evaluation.get("candidate_id", ""))
            hypothesis = hypotheses.get(candidate_id, {})
            for check in evaluation.get("check_results", []):
                if str(check.get("category", "")) != "certificate":
                    continue
                metrics = {
                    str(key): float(value)
                    for key, value in (check.get("metrics", {}) or {}).items()
                    if isinstance(value, (int, float))
                }
                rows.append(
                    {
                        "lane": str(check.get("check_id", "")),
                        "round_index": round_index,
                        "candidate_id": candidate_id,
                        "score": float(metrics.get("score", 0.0)),
                        "passed": bool(check.get("passed", False)),
                        "families": tuple(str(item) for item in hypothesis.get("ingredient_families", ())),
                        "summary": str(check.get("summary", "")),
                        "detail_path": str(check.get("detail_path", "")),
                        "metrics": metrics,
                    }
                )
    rows.sort(key=lambda item: (item["lane"], item["round_index"], item["candidate_id"]))
    return rows


def _certificate_margin_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        lane = row["lane"]
        entry = summary.setdefault(
            lane,
            {
                "lane": lane,
                "count": 0,
                "passed_count": 0,
                "best_score": 0.0,
                "best_candidate_id": "",
                "best_round_index": 0,
                "avg_score_total": 0.0,
            },
        )
        entry["count"] += 1
        entry["passed_count"] += 1 if row["passed"] else 0
        entry["avg_score_total"] += float(row["score"])
        if float(row["score"]) >= float(entry["best_score"]):
            entry["best_score"] = float(row["score"])
            entry["best_candidate_id"] = str(row["candidate_id"])
            entry["best_round_index"] = int(row["round_index"])
    ordered = []
    for entry in summary.values():
        count = max(1, int(entry["count"]))
        ordered.append(
            {
                **entry,
                "avg_score": float(entry["avg_score_total"]) / count,
            }
        )
    ordered.sort(key=lambda item: (-item["best_score"], item["lane"]))
    return ordered


def _format_lane_label(value: str) -> str:
    return value.replace("_", " ")


def render_dashboard_html(bundle: dict[str, Any], plot_html: str) -> str:
    summary = bundle["summary"]
    operator_language = bundle.get("operator_language") or {}
    calibration = bundle.get("calibration") or {}
    failure_atlas = bundle.get("failure_atlas") or {}
    certificate_report = bundle.get("certificate_report") or {}
    obligation_ledger = bundle.get("obligation_ledger") or {}
    campaign_benchmark = bundle.get("campaign_benchmark") or {}
    dead_end_library = bundle.get("dead_end_library") or {}
    rounds = bundle.get("rounds", [])

    cards_html = "".join(_artifact_card(round_item) for round_item in rounds)
    quantum_rows = _quantum_branch_rows(rounds)
    quantum_summary = _quantum_branch_summary(quantum_rows)
    certificate_rows = _certificate_margin_rows(rounds)
    certificate_summary = _certificate_margin_summary(certificate_rows)
    quantum_summary_html = "".join(
        f"""
        <article class="branch-summary-card">
          <div class="branch-summary-kicker">{escape(item['branch'].replace('_', ' '))}</div>
          <strong>{item['best_score']:.4f}</strong>
          <div>best: <code>{escape(item['best_candidate_id'])}</code></div>
          <div>round {int(item['best_round_index'])} · avg {item['avg_score']:.4f} · candidates {int(item['count'])}</div>
        </article>
        """
        for item in quantum_summary
    )
    certificate_summary_html = "".join(
        f"""
        <article class="branch-summary-card">
          <div class="branch-summary-kicker">{escape(_format_lane_label(item['lane']))}</div>
          <strong>{item['best_score']:.4f}</strong>
          <div>best: <code>{escape(item['best_candidate_id'])}</code></div>
          <div>round {int(item['best_round_index'])} · avg {item['avg_score']:.4f} · pass {int(item['passed_count'])}/{int(item['count'])}</div>
        </article>
        """
        for item in certificate_summary
    )
    quantum_cards_html = "".join(
        f"""
        <article class="branch-card" data-branch="{escape(item['branch'])}" data-round="{int(item['round_index'])}">
          <div class="artifact-meta">
            <span class="pill q">{escape(item['branch'].replace('_', ' '))}</span>
            <span>Round {int(item['round_index'])}</span>
            <span>score {float(item['score']):.4f}</span>
          </div>
          <h3><code>{escape(item['candidate_id'])}</code></h3>
          <p>{escape(item['claim'])}</p>
          <div class="kv">
            <div>Families</div><strong>{escape(", ".join(item['families']) or "n/a")}</strong>
            <div>Accepted novelty</div><strong>{len(item['novelty_artifact_ids'])}</strong>
          </div>
          <details>
            <summary>Risk Flags</summary>
            <ul class="tight">{"".join(f"<li><code>{escape(flag)}</code></li>" for flag in item['risk_flags']) or "<li>none</li>"}</ul>
          </details>
          <details>
            <summary>Unresolved Obligations</summary>
            <ul class="tight">{"".join(f"<li><code>{escape(obligation)}</code></li>" for obligation in item['unresolved_obligations']) or "<li>none</li>"}</ul>
          </details>
          <details>
            <summary>Novelty Artifact IDs</summary>
            <ul class="tight">{"".join(f"<li><code>{escape(artifact)}</code></li>" for artifact in item['novelty_artifact_ids']) or "<li>none</li>"}</ul>
          </details>
          <details>
            <summary>Contradiction Summary</summary>
            <p>{escape(item['contradiction_summary'] or "none")}</p>
          </details>
        </article>
        """
        for item in quantum_rows
    )
    certificate_cards_html = "".join(
        f"""
        <article class="certificate-card" data-certificate-lane="{escape(item['lane'])}" data-round="{int(item['round_index'])}" data-passed="{escape('passed' if item['passed'] else 'failed')}">
          <div class="artifact-meta">
            <span class="pill {'q' if item['passed'] else 'm'}">{escape(_format_lane_label(item['lane']))}</span>
            <span>Round {int(item['round_index'])}</span>
            <span>{'passed' if item['passed'] else 'failed'}</span>
            <span>score {float(item['score']):.4f}</span>
          </div>
          <h3><code>{escape(item['candidate_id'])}</code></h3>
          <p>{escape(item['summary'])}</p>
          <div class="kv">
            <div>Families</div><strong>{escape(", ".join(item['families']) or "n/a")}</strong>
            <div>Detail Path</div><code>{escape(item['detail_path'] or 'n/a')}</code>
          </div>
          <details open>
            <summary>Margins</summary>
            <ul class="tight">
              {"".join(f"<li><code>{escape(key)}</code>: {float(value):.4f}</li>" for key, value in item['metrics'].items()) or "<li>none</li>"}
            </ul>
          </details>
        </article>
        """
        for item in certificate_rows
    )
    family_count = len((operator_language.get("primitive_families") or {}).keys())
    calibration_pct = 100.0 * float(calibration.get("coverage", 0.0))
    missing_tasks = calibration.get("missing_tasks", [])
    failure_items = sorted((failure_atlas.get("failure_counts") or {}).items(), key=lambda item: (-item[1], item[0]))[:8]
    failure_html = "".join(
        f"<li><span>{escape(name)}</span><strong>{count}</strong></li>" for name, count in failure_items
    ) or "<li><span>no recurring failures recorded</span><strong>0</strong></li>"
    unresolved_items = obligation_ledger.get("summary", {}).get("top_unresolved_obligations", [])
    unresolved_html = "".join(
        f"<li><span>{escape(str(item.get('obligation_class', '')))}</span><strong>{int(item.get('count', 0))}</strong></li>"
        for item in unresolved_items
    ) or "<li><span>no unresolved obligations recorded</span><strong>0</strong></li>"
    dead_end_items = dead_end_library.get("summary", {}).get("top_patterns", [])
    dead_end_html = "".join(
        f"<li><span>{escape(str(item.get('pattern_id', '')))}</span><strong>{int(item.get('count', 0))}</strong></li>"
        for item in dead_end_items
    ) or "<li><span>no repeated dead-end pattern recorded</span><strong>0</strong></li>"
    best_review = dict(summary.get("best_candidate_review", {}))
    review_strengths_html = "".join(
        f"<li>{escape(str(item))}</li>" for item in best_review.get("why_it_scored_well", ())
    ) or "<li>n/a</li>"
    review_limits_html = "".join(
        f"<li>{escape(str(item))}</li>" for item in best_review.get("why_it_is_not_a_proof", ())
    ) or "<li>n/a</li>"
    review_remaining_html = "".join(
        (
            f"<li><code>{escape(str(item.get('obligation_class', '')))}</code> "
            f"margin {float(item.get('best_margin', 0.0)):.3f} / {float(item.get('resolution_threshold', 0.0)):.3f}"
            f"<br>{escape(str(item.get('reason', '')))}</li>"
        )
        for item in best_review.get("remaining_obligations", [])
    ) or "<li>n/a</li>"
    mode_summary = campaign_benchmark.get("mode_summary", [])
    benchmark_html = "".join(
        f"<li><span>{escape(str(item.get('benchmark_mode', '')))}</span><strong>{float(item.get('best_score', 0.0)):.3f}</strong></li>"
        for item in mode_summary[:6]
    ) or "<li><span>no benchmark data</span><strong>0</strong></li>"
    benchmark_view = dict(campaign_benchmark.get("current_vs_comparable", {}))

    history = summary.get("history", [])
    round_options = "".join(
        f"<option value=\"{int(item.get('round_index', 0))}\">Round {int(item.get('round_index', 0))}</option>"
        for item in history
    )
    branch_options = "".join(
        f"<option value=\"{escape(item['branch'])}\">{escape(item['branch'].replace('_', ' '))}</option>"
        for item in quantum_summary
    )
    certificate_lane_options = "".join(
        f"<option value=\"{escape(item['lane'])}\">{escape(_format_lane_label(item['lane']))}</option>"
        for item in certificate_summary
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RH Research Campaign Dashboard</title>
  <style>
    :root {{
      --navy: {NAVY};
      --teal: {TEAL};
      --emerald: {EMERALD};
      --amber: {AMBER};
      --blue: {BLUE};
      --rose: {ROSE};
      --slate: {SLATE};
      --surface: {SURFACE};
      --card: {CARD};
      --border: {BORDER};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Avenir Next", system-ui, sans-serif;
      color: var(--navy);
      background:
        radial-gradient(circle at top left, rgba(217,119,6,0.10), transparent 28%),
        radial-gradient(circle at top right, rgba(5,150,105,0.10), transparent 26%),
        linear-gradient(180deg, #fffdf8 0%, var(--surface) 48%, #eef6f6 100%);
    }}
    main {{ max-width: 1400px; margin: 0 auto; padding: 32px 24px 64px; }}
    h1 {{ margin: 0 0 8px; font-size: 2.4rem; line-height: 1.05; }}
    p.lead {{ margin: 0; color: var(--slate); max-width: 920px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin: 28px 0;
    }}
    .card, .panel {{
      background: rgba(255,255,255,0.86);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 18px 48px rgba(15,23,42,0.06);
      backdrop-filter: blur(10px);
    }}
    .card {{ padding: 18px 18px 16px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 0.92rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--slate); }}
    .card strong {{ display: block; font-size: 1.7rem; margin-bottom: 4px; }}
    .panel {{ padding: 22px; margin-top: 18px; }}
    .panel h2 {{ margin: 0 0 10px; font-size: 1.1rem; }}
    .split {{
      display: grid;
      grid-template-columns: 1.25fr 0.75fr;
      gap: 18px;
      align-items: start;
      margin-top: 18px;
    }}
    .meta-list, .failure-list {{ list-style: none; padding: 0; margin: 0; }}
    .meta-list li, .failure-list li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
      font-size: 0.95rem;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 20px 0 14px;
      align-items: center;
    }}
    .controls button, .controls select {{
      border: 1px solid var(--border);
      background: white;
      color: var(--navy);
      border-radius: 999px;
      padding: 10px 14px;
      font: inherit;
      cursor: pointer;
    }}
    .controls button.active {{
      background: var(--navy);
      color: white;
      border-color: var(--navy);
    }}
    .artifact-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .artifact-card, .branch-card, .certificate-card {{
      border: 1px solid var(--border);
      border-radius: 18px;
      background: white;
      padding: 16px;
    }}
    .artifact-card h3, .branch-card h3, .certificate-card h3 {{ margin: 0 0 8px; font-size: 1.05rem; }}
    .branch-summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-top: 14px;
    }}
    .branch-summary-card {{
      border: 1px solid var(--border);
      border-radius: 18px;
      background: white;
      padding: 16px;
    }}
    .branch-summary-card strong {{
      display: block;
      font-size: 1.6rem;
      margin: 8px 0 6px;
    }}
    .branch-summary-kicker {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.78rem;
      color: var(--slate);
    }}
    .branch-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
      margin-top: 14px;
    }}
    .artifact-meta {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      font-size: 0.82rem;
      color: var(--slate);
      margin-bottom: 10px;
    }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    .pill.m {{ background: rgba(217,119,6,0.14); color: #92400e; }}
    .pill.q {{ background: rgba(5,150,105,0.14); color: #065f46; }}
    .pill.t {{ background: rgba(37,99,235,0.14); color: #1d4ed8; }}
    .pill.k {{ background: rgba(225,29,72,0.14); color: #be123c; }}
    .kv {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      font-size: 0.9rem;
      margin: 12px 0;
    }}
    details {{ margin-top: 10px; }}
    details summary {{ cursor: pointer; font-weight: 600; }}
    code {{
      font-family: "IBM Plex Mono", "SFMono-Regular", ui-monospace, monospace;
      font-size: 0.84rem;
      word-break: break-word;
    }}
    ul.tight {{ margin: 8px 0 0 18px; padding: 0; }}
    @media (max-width: 1100px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .split {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      .grid {{ grid-template-columns: 1fr; }}
      main {{ padding: 22px 14px 48px; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>RH Recursive Research Dashboard</h1>
    <p class="lead">
      Campaign <strong>{escape(summary.get("campaign_id", "unknown"))}</strong> tracked the operator-language
      loop across literature mapping, synthesis, bounded validation, and the upgraded geometric / spectral / tail-control novelty lanes.
    </p>

    <section class="grid">
      <article class="card">
        <h2>Best Score</h2>
        <strong>{float(summary.get("best_score", 0.0)):.4f}</strong>
        <div>Candidate: <code>{escape(summary.get("best_candidate_id", "n/a"))}</code></div>
      </article>
      <article class="card">
        <h2>Rounds</h2>
        <strong>{int(summary.get("rounds_run", 0))}</strong>
        <div>Termination: <code>{escape(summary.get("termination_reason", "n/a"))}</code></div>
      </article>
      <article class="card">
        <h2>Operator Families</h2>
        <strong>{family_count}</strong>
        <div>Calibration coverage: {calibration_pct:.1f}%</div>
      </article>
      <article class="card">
        <h2>Sources / Approaches</h2>
        <strong>{int(summary.get("source_count", 0))} / {int(summary.get("approach_count", 0))}</strong>
        <div>Resumed: {escape(str(summary.get("resumed", False)))}</div>
      </article>
      <article class="card">
        <h2>Benchmark Mode</h2>
        <strong>{escape(str(summary.get("benchmark_mode", "baseline")))}</strong>
        <div>Obligation reduction: {float(best_review.get("proof_obligation_reduction", 0.0)):.3f}</div>
      </article>
    </section>

    <section class="panel">
      <h2>Campaign Signals</h2>
      {plot_html}
    </section>

    <section class="split">
      <article class="panel">
        <h2>Operator Language</h2>
        <ul class="meta-list">
          <li><span>Version</span><strong>{escape(operator_language.get("version", "n/a"))}</strong></li>
          <li><span>Primitive families</span><strong>{family_count}</strong></li>
          <li><span>Normalization steps</span><strong>{len(operator_language.get("normalization_pipeline", []))}</strong></li>
          <li><span>Framework source</span><code>{escape(operator_language.get("framework_path", "n/a"))}</code></li>
          <li><span>Missing calibration tasks</span><strong>{len(missing_tasks)}</strong></li>
        </ul>
        <details open>
          <summary>Missing Calibration Tasks</summary>
          <ul class="tight">
            {"".join(f"<li><code>{escape(item)}</code></li>" for item in missing_tasks) or "<li>none</li>"}
          </ul>
        </details>
      </article>

      <article class="panel">
        <h2>Failure Atlas</h2>
        <ul class="failure-list">{failure_html}</ul>
      </article>
    </section>

    <section class="split">
      <article class="panel">
        <h2>Supervisor Review Pack</h2>
        <div class="kv">
          <div>Review candidate</div><code>{escape(str(best_review.get("candidate_id", "n/a")))}</code>
          <div>Families</div><strong>{escape(", ".join(best_review.get("ingredient_families", ())) or "n/a")}</strong>
          <div>Artifact quality</div><strong>{float(best_review.get("artifact_quality", 0.0)):.3f}</strong>
          <div>Next targeted check</div><code>{escape(str(best_review.get("next_targeted_check", {}).get("check_id", "n/a")))}</code>
        </div>
        <details open>
          <summary>Why It Scored Well</summary>
          <ul class="tight">{review_strengths_html}</ul>
        </details>
        <details open>
          <summary>Why It Is Still Not A Proof</summary>
          <ul class="tight">{review_limits_html}</ul>
        </details>
        <details>
          <summary>Remaining Obligations</summary>
          <ul class="tight">{review_remaining_html}</ul>
        </details>
      </article>

      <article class="panel">
        <h2>Program Pressure</h2>
        <ul class="meta-list">
          <li><span>Current overall rank</span><strong>{int(benchmark_view.get("current_rank_overall", 0))}</strong></li>
          <li><span>Comparable-group rank</span><strong>{int(benchmark_view.get("current_rank_in_group", 0))}</strong></li>
          <li><span>Comparable campaigns</span><strong>{int(benchmark_view.get("comparison_group_size", 0))}</strong></li>
          <li><span>Delta vs group best</span><strong>{float(benchmark_view.get("delta_vs_group_best_score", 0.0)):.4f}</strong></li>
        </ul>
        <details open>
          <summary>Top Unresolved Obligations</summary>
          <ul class="failure-list">{unresolved_html}</ul>
        </details>
        <details open>
          <summary>Repeated Dead-End Patterns</summary>
          <ul class="failure-list">{dead_end_html}</ul>
        </details>
      </article>
    </section>

    <section class="panel">
      <h2>Certificate Margin Review</h2>
      <p class="lead">
        Proof-oriented bounded lanes are now tracked directly in the orchestrator.
        <code>certificate_search</code> estimates explicit-formula exclusion margin,
        <code>explicit_formula_tail_control</code> tracks decay/error-budget/window-escape pressure,
        <code>variance_collapse_exclusion</code> tests whether critical-line concentration survives an exceptional-zero exclusion burden,
        <code>zero_atlas_xi_bridge</code> tests whether contour/atlas/pi-normalized zero structure supports a xi-based exclusion bridge,
        <code>zero_atlas_exclusion</code> tests whether that bridge actually yields off-line-zero exclusion,
        <code>xi_coefficient_bridge</code> tracks Li/Keiper and Jensen-style surrogate margins,
        <code>operator_non_surrogate_rigor</code> penalizes operator-surrogate branches,
        and <code>surface_return_certificate</code> checks that local support returns as a global exclusion obligation.
      </p>
      <div class="branch-summary-grid">
        {certificate_summary_html or "<p>No certificate margin checks were written for this campaign.</p>"}
      </div>
      <div class="controls">
        <button class="active" data-certificate-filter="all">All lanes</button>
        <button data-certificate-filter="certificate_search">Certificate Search</button>
        <button data-certificate-filter="explicit_formula_tail_control">Tail Control</button>
        <button data-certificate-filter="variance_collapse_exclusion">Variance Collapse</button>
        <button data-certificate-filter="zero_atlas_xi_bridge">Zero Atlas Bridge</button>
        <button data-certificate-filter="zero_atlas_exclusion">Zero Atlas Exclusion</button>
        <button data-certificate-filter="xi_coefficient_bridge">Xi Coefficient Bridge</button>
        <button data-certificate-filter="operator_non_surrogate_rigor">Operator Rigor</button>
        <button data-certificate-filter="surface_return_certificate">Surface Return</button>
        <select id="certificate-round-filter">
          <option value="all">All rounds</option>
          {round_options}
        </select>
        <select id="certificate-lane-filter">
          <option value="all">All lane names</option>
          {certificate_lane_options}
        </select>
        <select id="certificate-pass-filter">
          <option value="all">Passed and failed</option>
          <option value="passed">Passed only</option>
          <option value="failed">Failed only</option>
        </select>
      </div>
      <div class="branch-grid" id="certificate-grid">
        {certificate_cards_html or "<p>No certificate margin checks were written for this campaign.</p>"}
      </div>
    </section>

    <section class="panel">
      <h2>Quantum Branch Review</h2>
      <p class="lead">
        The quantum lane now surfaces two named branches: <code>operator_hard</code> for
        <code>hilbert_polya + quantum_spectral</code> and <code>operator_bridge</code> for
        <code>explicit_formula + quantum_spectral</code>.
      </p>
      <div class="branch-summary-grid">
        {quantum_summary_html or "<p>No quantum branch candidates were written for this campaign.</p>"}
      </div>
      <div class="controls">
        <button class="active" data-branch-filter="all">All branches</button>
        <button data-branch-filter="operator_hard">Operator Hard</button>
        <button data-branch-filter="operator_bridge">Operator Bridge</button>
        <select id="branch-round-filter">
          <option value="all">All rounds</option>
          {round_options}
        </select>
        <select id="branch-name-filter">
          <option value="all">All branch names</option>
          {branch_options}
        </select>
      </div>
      <div class="branch-grid" id="branch-grid">
        {quantum_cards_html or "<p>No quantum branch candidates were written for this campaign.</p>"}
      </div>
    </section>

    <section class="panel">
      <h2>Comparative Benchmark</h2>
      <ul class="failure-list">{benchmark_html}</ul>
    </section>

    <section class="panel">
      <h2>Interactive Operator Artifacts</h2>
      <div class="controls">
        <button class="active" data-agent-filter="all">All</button>
        <button data-agent-filter="M">Modeling (M)</button>
        <button data-agent-filter="Q">Quantum (Q)</button>
        <button data-agent-filter="T">Tail Control (T)</button>
        <select id="round-filter">
          <option value="all">All rounds</option>
          {round_options}
        </select>
      </div>
      <div class="artifact-grid" id="artifact-grid">
        {cards_html or "<p>No operator artifacts were written for this campaign.</p>"}
      </div>
    </section>
  </main>
  <script>
    const buttons = Array.from(document.querySelectorAll('[data-agent-filter]'));
    const roundFilter = document.getElementById('round-filter');
    const cards = Array.from(document.querySelectorAll('.artifact-card'));
    const branchButtons = Array.from(document.querySelectorAll('[data-branch-filter]'));
    const branchRoundFilter = document.getElementById('branch-round-filter');
    const branchNameFilter = document.getElementById('branch-name-filter');
    const branchCards = Array.from(document.querySelectorAll('.branch-card'));
    const certificateButtons = Array.from(document.querySelectorAll('[data-certificate-filter]'));
    const certificateRoundFilter = document.getElementById('certificate-round-filter');
    const certificateLaneFilter = document.getElementById('certificate-lane-filter');
    const certificatePassFilter = document.getElementById('certificate-pass-filter');
    const certificateCards = Array.from(document.querySelectorAll('.certificate-card'));

    function applyFilters() {{
      const active = document.querySelector('[data-agent-filter].active')?.dataset.agentFilter || 'all';
      const roundValue = roundFilter?.value || 'all';
      cards.forEach((card) => {{
        const matchAgent = active === 'all' || card.dataset.agent === active;
        const matchRound = roundValue === 'all' || card.dataset.round === roundValue;
        card.style.display = matchAgent && matchRound ? '' : 'none';
      }});
    }}

    function applyBranchFilters() {{
      const active = document.querySelector('[data-branch-filter].active')?.dataset.branchFilter || 'all';
      const roundValue = branchRoundFilter?.value || 'all';
      const branchValue = branchNameFilter?.value || 'all';
      branchCards.forEach((card) => {{
        const matchBranchButton = active === 'all' || card.dataset.branch === active;
        const matchBranchSelect = branchValue === 'all' || card.dataset.branch === branchValue;
        const matchRound = roundValue === 'all' || card.dataset.round === roundValue;
        card.style.display = matchBranchButton && matchBranchSelect && matchRound ? '' : 'none';
      }});
    }}

    function applyCertificateFilters() {{
      const active = document.querySelector('[data-certificate-filter].active')?.dataset.certificateFilter || 'all';
      const roundValue = certificateRoundFilter?.value || 'all';
      const laneValue = certificateLaneFilter?.value || 'all';
      const passValue = certificatePassFilter?.value || 'all';
      certificateCards.forEach((card) => {{
        const matchButton = active === 'all' || card.dataset.certificateLane === active;
        const matchLane = laneValue === 'all' || card.dataset.certificateLane === laneValue;
        const matchRound = roundValue === 'all' || card.dataset.round === roundValue;
        const matchPass = passValue === 'all' || card.dataset.passed === passValue;
        card.style.display = matchButton && matchLane && matchRound && matchPass ? '' : 'none';
      }});
    }}

    buttons.forEach((button) => {{
      button.addEventListener('click', () => {{
        buttons.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        applyFilters();
      }});
    }});
    branchButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        branchButtons.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        applyBranchFilters();
      }});
    }});
    certificateButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        certificateButtons.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        applyCertificateFilters();
      }});
    }});
    roundFilter?.addEventListener('change', applyFilters);
    branchRoundFilter?.addEventListener('change', applyBranchFilters);
    branchNameFilter?.addEventListener('change', applyBranchFilters);
    certificateRoundFilter?.addEventListener('change', applyCertificateFilters);
    certificateLaneFilter?.addEventListener('change', applyCertificateFilters);
    certificatePassFilter?.addEventListener('change', applyCertificateFilters);
    applyFilters();
    applyBranchFilters();
    applyCertificateFilters();
  </script>
</body>
</html>"""


def write_campaign_dashboard(campaign_dir: Path, output_path: Path | None = None) -> Path:
    bundle = load_campaign_bundle(campaign_dir)
    fig = build_campaign_figure(bundle)
    output = output_path or (campaign_dir / "research_dashboard.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    plot_html = to_html(
        fig,
        full_html=False,
        include_plotlyjs="inline",
        config={"displayModeBar": False, "responsive": True},
    )
    output.write_text(render_dashboard_html(bundle, plot_html), encoding="utf-8")
    return output


def discover_campaign_dirs(
    research_root: Path,
    pattern: str = "*",
) -> list[Path]:
    paths = []
    for path in sorted(research_root.glob(pattern)):
        if path.is_dir() and (path / "summary.json").exists():
            paths.append(path)
    return paths


def load_all_results_bundle(
    research_root: Path,
    pattern: str = "*",
) -> dict[str, Any]:
    bundles = []
    for campaign_dir in discover_campaign_dirs(research_root, pattern):
        bundle = load_campaign_bundle(campaign_dir)
        summary = bundle["summary"]
        calibration = bundle.get("calibration") or {}
        seed_manifest = _safe_read(campaign_dir / "seed_manifest.json", {})
        rounds = bundle.get("rounds", [])
        artifact_rows = []
        accepted_total = 0
        total_artifacts = 0
        for round_payload in rounds:
            accepted_ids = _accepted_artifact_ids(round_payload)
            accepted_total += len(accepted_ids)
            total_artifacts += len(round_payload.get("novelty", []))
            for item in round_payload.get("novelty", []):
                features = item.get("measurable_features", {})
                feature_values = [float(v) for v in features.values()]
                feature_support = sum(feature_values) / max(len(feature_values), 1) if feature_values else 0.0
                artifact_rows.append(
                    {
                        "campaign_id": summary.get("campaign_id", campaign_dir.name),
                        "round_index": int(round_payload.get("round_index", 0)),
                        "artifact_id": str(item.get("artifact_id", "")),
                        "title": str(item.get("title", "")),
                        "agent": str(item.get("agent", "?")),
                        "accepted": item.get("artifact_id") in accepted_ids,
                        "operator_complexity": float(item.get("operator_complexity", 0.0)),
                        "feature_support": feature_support,
                        "operator_family": str(item.get("operator_family", "")),
                        "failure_modes": tuple(item.get("failure_modes", ())),
                        "canonical_signature": str(item.get("canonical_signature", "")),
                        "measurable_features": dict(features),
                        "proof_skeleton": tuple(item.get("proof_skeleton", ())),
                        "supporting_paths": tuple(item.get("supporting_paths", ())),
                        "observation": str(item.get("observation", "")),
                    }
                )

        coverage = float(calibration.get("coverage", 0.0))
        bundle["seed_manifest"] = seed_manifest
        bundle["metrics"] = {
            "campaign_id": summary.get("campaign_id", campaign_dir.name),
            "campaign_dir": str(campaign_dir),
            "seed_pack_names": tuple(summary.get("seed_pack_names", ()) or seed_manifest.get("seed_pack_names", ())),
            "benchmark_mode": str(summary.get("benchmark_mode", "baseline")),
            "best_score": float(summary.get("best_score", 0.0)),
            "rounds_run": int(summary.get("rounds_run", 0)),
            "source_count": int(summary.get("source_count", 0)),
            "approach_count": int(summary.get("approach_count", 0)),
            "coverage": coverage,
            "fully_calibrated": coverage >= 0.999,
            "termination_reason": str(summary.get("termination_reason", "")),
            "best_candidate_id": str(summary.get("best_candidate_id", "")),
            "dashboard_path": str(summary.get("paths", {}).get("dashboard", "")),
            "benchmark_path": str(summary.get("paths", {}).get("campaign_benchmark", "")),
            "best_dossier_path": str(summary.get("best_dossier_path", "")),
            "best_obligation_reduction": float(summary.get("best_candidate_review", {}).get("proof_obligation_reduction", 0.0)),
            "top_unresolved_obligation_count": len(summary.get("top_unresolved_obligations", [])),
            "accepted_artifact_count": accepted_total,
            "artifact_count": total_artifacts,
            "artifact_rows": artifact_rows,
        }
        bundles.append(bundle)

    return {
        "research_root": str(research_root),
        "campaigns": bundles,
    }


def build_all_results_figure(all_results: dict[str, Any]) -> go.Figure:
    campaigns = all_results.get("campaigns", [])
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{}, {}],
            [{}, {}],
        ],
        subplot_titles=(
            "Campaign Best Scores",
            "Coverage, Sources, and Accepted Artifacts",
            "Round Trajectories",
            "Artifact Complexity vs Support",
        ),
        horizontal_spacing=0.12,
        vertical_spacing=0.16,
    )
    if not campaigns:
        fig.add_annotation(
            text="No operator-rh campaigns found.",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color=NAVY),
        )
        fig.update_layout(template="plotly_white", paper_bgcolor=SURFACE, plot_bgcolor=CARD, height=860)
        return fig

    labels = [item["metrics"]["campaign_id"] for item in campaigns]
    best_scores = [item["metrics"]["best_score"] for item in campaigns]
    coverage = [item["metrics"]["coverage"] for item in campaigns]
    accepted = [item["metrics"]["accepted_artifact_count"] for item in campaigns]
    sources = [item["metrics"]["source_count"] for item in campaigns]
    approaches = [item["metrics"]["approach_count"] for item in campaigns]
    calibrated_colors = [EMERALD if item["metrics"]["fully_calibrated"] else AMBER for item in campaigns]
    ordered_indices = sorted(range(len(campaigns)), key=lambda idx: (-best_scores[idx], labels[idx]))
    ordered_labels = [labels[idx] for idx in ordered_indices]
    ordered_scores = [best_scores[idx] for idx in ordered_indices]
    ordered_coverage = [coverage[idx] for idx in ordered_indices]
    ordered_accepted = [accepted[idx] for idx in ordered_indices]
    ordered_sources = [sources[idx] for idx in ordered_indices]
    ordered_approaches = [approaches[idx] for idx in ordered_indices]
    ordered_colors = [calibrated_colors[idx] for idx in ordered_indices]
    top_campaigns = {
        labels[idx]
        for idx in ordered_indices[: min(3, len(ordered_indices))]
    }

    fig.add_trace(
        go.Bar(
            x=ordered_scores,
            y=ordered_labels,
            orientation="h",
            marker_color=ordered_colors,
            text=[f"{score:.4f}" for score in ordered_scores],
            textposition="outside",
            cliponaxis=False,
            customdata=[
                [cov, acc, src, app]
                for cov, acc, src, app in zip(
                    ordered_coverage,
                    ordered_accepted,
                    ordered_sources,
                    ordered_approaches,
                )
            ],
            hovertemplate=(
                "<b>%{y}</b><br>best score=%{x:.4f}<br>"
                "coverage=%{customdata[0]:.2f}<br>accepted artifacts=%{customdata[1]}<br>"
                "sources=%{customdata[2]}<br>approaches=%{customdata[3]}<extra></extra>"
            ),
            name="Best score",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=coverage,
            y=best_scores,
            mode="markers",
            marker=dict(
                size=[max(12, 8 + value * 1.5) for value in sources],
                color=accepted,
                colorscale=[[0.0, AMBER], [1.0, EMERALD]],
                showscale=True,
                colorbar=dict(title="Accepted"),
                line=dict(color=NAVY, width=0.8),
            ),
            customdata=[
                [label, src, app, acc]
                for label, src, app, acc in zip(labels, sources, approaches, accepted)
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>coverage=%{x:.2f}<br>best score=%{y:.4f}<br>"
                "sources=%{customdata[1]}<br>approaches=%{customdata[2]}<br>"
                "accepted artifacts=%{customdata[3]}<extra></extra>"
            ),
            name="Campaigns",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    for bundle in campaigns:
        history = bundle["summary"].get("history", [])
        if not history:
            continue
        round_ids = [int(item.get("round_index", idx + 1)) for idx, item in enumerate(history)]
        score_series = [float(item.get("best_score", 0.0)) for item in history]
        fig.add_trace(
            go.Scatter(
                x=round_ids,
                y=score_series,
                mode="lines+markers",
                line=dict(
                    width=3.0 if bundle["metrics"]["campaign_id"] in top_campaigns else 1.8,
                ),
                marker=dict(size=8 if bundle["metrics"]["campaign_id"] in top_campaigns else 6),
                opacity=0.95 if bundle["metrics"]["campaign_id"] in top_campaigns else 0.38,
                name=bundle["metrics"]["campaign_id"],
                hovertemplate=(
                    f"<b>{escape(bundle['metrics']['campaign_id'])}</b><br>"
                    "round=%{x}<br>best score=%{y:.4f}<extra></extra>"
                ),
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    artifact_x = []
    artifact_y = []
    artifact_text = []
    artifact_color = []
    artifact_symbol = []
    for bundle in campaigns:
        for row in bundle["metrics"]["artifact_rows"]:
            artifact_x.append(row["operator_complexity"])
            artifact_y.append(row["feature_support"])
            artifact_text.append(
                (
                    f"{row['campaign_id']}<br>{row['title']}<br>"
                    f"agent={row['agent']} accepted={row['accepted']}"
                )
            )
            artifact_color.append(_agent_color(str(row["agent"])))
            artifact_symbol.append("circle" if row["accepted"] else "x")

    fig.add_trace(
        go.Scatter(
            x=artifact_x,
            y=artifact_y,
            mode="markers",
            marker=dict(
                size=10,
                color=artifact_color,
                symbol=artifact_symbol,
                line=dict(color=NAVY, width=0.5),
            ),
            text=artifact_text,
            hovertemplate="<b>%{text}</b><br>complexity=%{x:.2f}<br>support=%{y:.2f}<extra></extra>",
            name="Artifacts",
            showlegend=False,
        ),
        row=2,
        col=2,
    )

    dynamic_height = max(980, 860 + 22 * len(campaigns))
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=SURFACE,
        plot_bgcolor=CARD,
        height=dynamic_height,
        margin=dict(l=220, r=44, t=90, b=48),
        showlegend=False,
    )
    fig.update_xaxes(title_text="Best score", range=[0, 1], row=1, col=1)
    fig.update_yaxes(title_text="Campaign", automargin=True, row=1, col=1, categoryorder="array", categoryarray=ordered_labels[::-1])
    fig.update_xaxes(title_text="Calibration coverage", range=[0, 1.05], row=1, col=2)
    fig.update_yaxes(title_text="Best score", range=[0, 1], row=1, col=2)
    fig.update_xaxes(title_text="Round", row=2, col=1)
    fig.update_yaxes(title_text="Best score", range=[0, 1], row=2, col=1)
    fig.update_xaxes(title_text="Operator complexity", row=2, col=2)
    fig.update_yaxes(title_text="Measured support", range=[0, 1], row=2, col=2)
    return fig


def render_all_results_html(all_results: dict[str, Any], plot_html: str) -> str:
    campaigns = all_results.get("campaigns", [])
    if not campaigns:
        return (
            "<!doctype html><html><body><main style=\"font-family:system-ui;padding:24px\">"
            "No operator-rh campaigns found.</main></body></html>"
        )

    metrics = [item["metrics"] for item in campaigns]
    best = max(metrics, key=lambda item: item["best_score"])
    calibrated_count = sum(1 for item in metrics if item["fully_calibrated"])
    accepted_total = sum(item["accepted_artifact_count"] for item in metrics)
    campaign_cards = "".join(_campaign_overview_card(bundle) for bundle in campaigns)
    artifact_cards = "".join(_aggregate_artifact_cards(bundle) for bundle in campaigns)
    campaign_options = "".join(
        f"<option value=\"{escape(item['campaign_id'])}\">{escape(item['campaign_id'])}</option>"
        for item in metrics
    )
    pack_values = sorted({pack for item in metrics for pack in item["seed_pack_names"]})
    pack_options = "".join(f"<option value=\"{escape(pack)}\">{escape(pack)}</option>" for pack in pack_values)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RH Operator Campaign Atlas</title>
  <style>
    :root {{
      --navy: {NAVY};
      --teal: {TEAL};
      --emerald: {EMERALD};
      --amber: {AMBER};
      --rose: {ROSE};
      --slate: {SLATE};
      --surface: {SURFACE};
      --card: {CARD};
      --border: {BORDER};
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Avenir Next", system-ui, sans-serif;
      color: var(--navy);
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.10), transparent 26%),
        radial-gradient(circle at top right, rgba(217,119,6,0.10), transparent 28%),
        linear-gradient(180deg, #fffefb 0%, var(--surface) 44%, #eef6f6 100%);
    }}
    main {{ max-width: 1520px; margin: 0 auto; padding: 32px 24px 64px; }}
    h1 {{ margin: 0 0 8px; font-size: 2.5rem; line-height: 1.02; }}
    p.lead {{ margin: 0; color: var(--slate); max-width: 980px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin: 28px 0;
    }}
    .card, .panel {{
      background: rgba(255,255,255,0.86);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 18px 48px rgba(15,23,42,0.06);
      backdrop-filter: blur(10px);
    }}
    .card {{ padding: 18px 18px 16px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 0.92rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--slate); }}
    .card strong {{ display: block; font-size: 1.7rem; margin-bottom: 4px; }}
    .panel {{ padding: 22px; margin-top: 18px; }}
    .panel h2 {{ margin: 0 0 10px; font-size: 1.1rem; }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 16px 0 18px;
      align-items: center;
    }}
    .controls button, .controls select {{
      border: 1px solid var(--border);
      background: white;
      color: var(--navy);
      border-radius: 999px;
      padding: 10px 14px;
      font: inherit;
      cursor: pointer;
    }}
    .controls button.active {{
      background: var(--navy);
      color: white;
      border-color: var(--navy);
    }}
    .campaign-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
    }}
    .campaign-card, .artifact-card {{
      border: 1px solid var(--border);
      border-radius: 18px;
      background: white;
      padding: 16px;
    }}
    .artifact-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 14px;
    }}
    .meta {{
      display: inline-flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      font-size: 0.82rem;
      color: var(--slate);
      margin-bottom: 10px;
    }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    .pill.good {{ background: rgba(5,150,105,0.14); color: #065f46; }}
    .pill.warn {{ background: rgba(217,119,6,0.14); color: #92400e; }}
    .pill.m {{ background: rgba(217,119,6,0.14); color: #92400e; }}
    .pill.q {{ background: rgba(5,150,105,0.14); color: #065f46; }}
    .pill.t {{ background: rgba(37,99,235,0.14); color: #1d4ed8; }}
    .pill.k {{ background: rgba(225,29,72,0.14); color: #be123c; }}
    .kv {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      font-size: 0.9rem;
      margin: 12px 0;
    }}
    code {{
      font-family: "IBM Plex Mono", "SFMono-Regular", ui-monospace, monospace;
      font-size: 0.84rem;
      word-break: break-word;
    }}
    a.path {{ color: var(--teal); text-decoration: none; }}
    details {{ margin-top: 10px; }}
    details summary {{ cursor: pointer; font-weight: 600; }}
    ul.tight {{ margin: 8px 0 0 18px; padding: 0; }}
    @media (max-width: 1100px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 720px) {{
      .grid {{ grid-template-columns: 1fr; }}
      main {{ padding: 22px 14px 48px; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>RH Operator Campaign Atlas</h1>
    <p class="lead">
      This atlas aggregates every operator-language RH campaign under the research root. It is not a comparison-only
      view: it keeps the full campaign set visible, exposes calibration state, and lets you filter into campaign and
      artifact detail from a single interactive report.
    </p>

    <section class="grid">
      <article class="card">
        <h2>Campaigns</h2>
        <strong>{len(campaigns)}</strong>
        <div>Discovered under <code>{escape(str(all_results.get("research_root", "")))}</code></div>
      </article>
      <article class="card">
        <h2>Best Campaign</h2>
        <strong>{best["best_score"]:.4f}</strong>
        <div><code>{escape(best["campaign_id"])}</code></div>
      </article>
      <article class="card">
        <h2>Fully Calibrated</h2>
        <strong>{calibrated_count}</strong>
        <div>of {len(campaigns)} campaigns</div>
      </article>
      <article class="card">
        <h2>Accepted Artifacts</h2>
        <strong>{accepted_total}</strong>
        <div>Across M, Q, and T lanes</div>
      </article>
    </section>

    <section class="panel">
      <h2>All Campaign Signals</h2>
      <p class="lead" style="max-width:none;margin-bottom:16px;">
        Hover any bar, line, or marker to inspect full campaign identifiers. Dense inline labels were removed from the
        figure so the atlas stays readable once the campaign set grows.
      </p>
      {plot_html}
    </section>

    <section class="panel">
      <h2>Campaign Index</h2>
      <div class="controls">
        <button class="active" data-calibration-filter="all">All</button>
        <button data-calibration-filter="full">Fully calibrated</button>
        <button data-calibration-filter="partial">Partial calibration</button>
        <select id="campaign-select">
          <option value="all">All campaigns</option>
          {campaign_options}
        </select>
        <select id="pack-select">
          <option value="all">All seed packs</option>
          {pack_options}
        </select>
      </div>
      <div class="campaign-grid" id="campaign-grid">
        {campaign_cards}
      </div>
    </section>

    <section class="panel">
      <h2>Interactive Artifact Atlas</h2>
      <div class="controls">
        <button class="active" data-agent-filter="all">All lanes</button>
        <button data-agent-filter="M">Modeling (M)</button>
        <button data-agent-filter="Q">Quantum (Q)</button>
        <button data-agent-filter="T">Tail Control (T)</button>
        <button class="active" data-acceptance-filter="all">All artifacts</button>
        <button data-acceptance-filter="accepted">Accepted only</button>
        <button data-acceptance-filter="advisory">Advisory only</button>
      </div>
      <div class="artifact-grid" id="artifact-grid">
        {artifact_cards}
      </div>
    </section>
  </main>
  <script>
    const calibrationButtons = Array.from(document.querySelectorAll('[data-calibration-filter]'));
    const agentButtons = Array.from(document.querySelectorAll('[data-agent-filter]'));
    const acceptanceButtons = Array.from(document.querySelectorAll('[data-acceptance-filter]'));
    const campaignSelect = document.getElementById('campaign-select');
    const packSelect = document.getElementById('pack-select');
    const campaignCards = Array.from(document.querySelectorAll('.campaign-card'));
    const artifactCards = Array.from(document.querySelectorAll('.artifact-card'));

    function activeValue(selector, fallback) {{
      return document.querySelector(selector)?.dataset?.value || fallback;
    }}

    function getActiveCalibration() {{
      return document.querySelector('[data-calibration-filter].active')?.dataset.calibrationFilter || 'all';
    }}
    function getActiveAgent() {{
      return document.querySelector('[data-agent-filter].active')?.dataset.agentFilter || 'all';
    }}
    function getActiveAcceptance() {{
      return document.querySelector('[data-acceptance-filter].active')?.dataset.acceptanceFilter || 'all';
    }}

    function applyAllFilters() {{
      const calibration = getActiveCalibration();
      const agent = getActiveAgent();
      const acceptance = getActiveAcceptance();
      const campaign = campaignSelect?.value || 'all';
      const pack = packSelect?.value || 'all';

      campaignCards.forEach((card) => {{
        const matchCalibration =
          calibration === 'all' ||
          (calibration === 'full' && card.dataset.calibration === 'full') ||
          (calibration === 'partial' && card.dataset.calibration === 'partial');
        const matchCampaign = campaign === 'all' || card.dataset.campaign === campaign;
        const matchPack = pack === 'all' || (card.dataset.packs || '').split('|').includes(pack);
        card.style.display = matchCalibration && matchCampaign && matchPack ? '' : 'none';
      }});

      artifactCards.forEach((card) => {{
        const matchCalibration =
          calibration === 'all' ||
          (calibration === 'full' && card.dataset.calibration === 'full') ||
          (calibration === 'partial' && card.dataset.calibration === 'partial');
        const matchCampaign = campaign === 'all' || card.dataset.campaign === campaign;
        const matchPack = pack === 'all' || (card.dataset.packs || '').split('|').includes(pack);
        const matchAgent = agent === 'all' || card.dataset.agent === agent;
        const matchAcceptance = acceptance === 'all' || card.dataset.acceptance === acceptance;
        card.style.display = matchCalibration && matchCampaign && matchPack && matchAgent && matchAcceptance ? '' : 'none';
      }});
    }}

    calibrationButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        calibrationButtons.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        applyAllFilters();
      }});
    }});
    agentButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        agentButtons.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        applyAllFilters();
      }});
    }});
    acceptanceButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        acceptanceButtons.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        applyAllFilters();
      }});
    }});
    campaignSelect?.addEventListener('change', applyAllFilters);
    packSelect?.addEventListener('change', applyAllFilters);
    applyAllFilters();
  </script>
</body>
</html>"""


def write_all_results_dashboard(
    research_root: Path,
    output_path: Path | None = None,
    pattern: str = "*",
) -> Path:
    all_results = load_all_results_bundle(research_root, pattern)
    fig = build_all_results_figure(all_results)
    output = output_path or (research_root / DEFAULT_ALL_RESULTS_OUTPUT)
    output.parent.mkdir(parents=True, exist_ok=True)
    plot_html = to_html(
        fig,
        full_html=False,
        include_plotlyjs="inline",
        config={"displayModeBar": False, "responsive": True},
    )
    output.write_text(render_all_results_html(all_results, plot_html), encoding="utf-8")
    return output


def _accepted_artifact_ids(round_payload: dict[str, Any]) -> set[str]:
    return {
        novelty_id
        for evaluation in round_payload.get("evaluations", [])
        for novelty_id in evaluation.get("novelty_artifact_ids", [])
    }


def _campaign_overview_card(bundle: dict[str, Any]) -> str:
    metrics = bundle["metrics"]
    calibration = "full" if metrics["fully_calibrated"] else "partial"
    calibration_css = "good" if metrics["fully_calibrated"] else "warn"
    packs = "|".join(metrics["seed_pack_names"])
    pack_html = "".join(f"<span class=\"pill warn\">{escape(pack)}</span>" for pack in metrics["seed_pack_names"])
    dashboard_link = (
        f"<a class=\"path\" href=\"file://{escape(metrics['dashboard_path'])}\">campaign dashboard</a>"
        if metrics["dashboard_path"]
        else "n/a"
    )
    benchmark_link = (
        f"<a class=\"path\" href=\"file://{escape(metrics['benchmark_path'])}\">campaign benchmark</a>"
        if metrics["benchmark_path"]
        else "n/a"
    )
    dossier_link = (
        f"<a class=\"path\" href=\"file://{escape(metrics['best_dossier_path'])}\">best dossier</a>"
        if metrics["best_dossier_path"]
        else "n/a"
    )
    return f"""
    <article class="campaign-card"
      data-campaign="{escape(metrics['campaign_id'])}"
      data-calibration="{calibration}"
      data-packs="{escape(packs)}">
      <div class="meta">
        <span class="pill {calibration_css}">{'full calibration' if metrics['fully_calibrated'] else 'partial calibration'}</span>
        <span class="pill warn">{escape(metrics['benchmark_mode'])}</span>
        {pack_html}
      </div>
      <h3>{escape(metrics['campaign_id'])}</h3>
      <div class="kv">
        <div>Best score</div><strong>{metrics['best_score']:.4f}</strong>
        <div>Best candidate</div><code>{escape(metrics['best_candidate_id'])}</code>
        <div>Obligation reduction</div><strong>{metrics['best_obligation_reduction']:.3f}</strong>
        <div>Rounds</div><strong>{metrics['rounds_run']}</strong>
        <div>Sources / approaches</div><strong>{metrics['source_count']} / {metrics['approach_count']}</strong>
        <div>Top unresolved classes</div><strong>{metrics['top_unresolved_obligation_count']}</strong>
        <div>Accepted / total artifacts</div><strong>{metrics['accepted_artifact_count']} / {metrics['artifact_count']}</strong>
        <div>Termination</div><code>{escape(metrics['termination_reason'])}</code>
      </div>
      <details>
        <summary>Paths</summary>
        <ul class="tight">
          <li>{dashboard_link}</li>
          <li>{benchmark_link}</li>
          <li>{dossier_link}</li>
          <li><code>{escape(metrics['campaign_dir'])}</code></li>
        </ul>
      </details>
    </article>
    """


def _aggregate_artifact_cards(bundle: dict[str, Any]) -> str:
    metrics = bundle["metrics"]
    calibration = "full" if metrics["fully_calibrated"] else "partial"
    packs = "|".join(metrics["seed_pack_names"])
    html = []
    for row in metrics["artifact_rows"]:
        css = _agent_css(str(row["agent"]))
        acceptance = "accepted" if row["accepted"] else "advisory"
        feature_lines = "".join(
            f"<div>{escape(name.replace('_', ' '))}</div><strong>{float(value):.3f}</strong>"
            for name, value in row["measurable_features"].items()
        )
        skeleton = "".join(f"<li>{escape(step)}</li>" for step in row["proof_skeleton"])
        failures = "".join(f"<li><code>{escape(reason)}</code></li>" for reason in row["failure_modes"])
        paths = "".join(f"<li><code>{escape(path)}</code></li>" for path in row["supporting_paths"])
        html.append(
            f"""
            <article class="artifact-card"
              data-campaign="{escape(metrics['campaign_id'])}"
              data-calibration="{calibration}"
              data-packs="{escape(packs)}"
              data-agent="{escape(row['agent'])}"
              data-acceptance="{acceptance}">
              <div class="meta">
                <span class="pill {css}">{escape(row['agent'])}</span>
                <span>{escape(metrics['campaign_id'])}</span>
                <span>Round {row['round_index']}</span>
                <span>{acceptance}</span>
              </div>
              <h3>{escape(row['title'])}</h3>
              <p>{escape(row['observation'])}</p>
              <div class="kv">
                <div>Operator family</div><code>{escape(row['operator_family'])}</code>
                <div>Complexity</div><strong>{row['operator_complexity']:.2f}</strong>
                <div>Feature support</div><strong>{row['feature_support']:.3f}</strong>
                <div>Canonical signature</div><code>{escape(row['canonical_signature'])}</code>
              </div>
              <details>
                <summary>Measured Features</summary>
                <div class="kv">{feature_lines or "<div>n/a</div><strong>n/a</strong>"}</div>
              </details>
              <details>
                <summary>Proof Skeleton</summary>
                <ul class="tight">{skeleton or "<li>n/a</li>"}</ul>
              </details>
              <details>
                <summary>Failure Modes</summary>
                <ul class="tight">{failures or "<li>none</li>"}</ul>
              </details>
              <details>
                <summary>Supporting Paths</summary>
                <ul class="tight">{paths or "<li>n/a</li>"}</ul>
              </details>
            </article>
            """
        )
    return "".join(html)


def _artifact_card(round_payload: dict[str, Any]) -> str:
    round_index = int(round_payload.get("round_index", 0))
    evaluations = round_payload.get("evaluations", [])
    novelty = round_payload.get("novelty", [])
    accepted = {
        novelty_id
        for evaluation in evaluations
        for novelty_id in evaluation.get("novelty_artifact_ids", [])
    }
    html = []
    for item in novelty:
        agent = str(item.get("agent", "?"))
        css = _agent_css(agent)
        accepted_flag = "accepted" if item.get("artifact_id") in accepted else "advisory"
        features = item.get("measurable_features", {})
        feature_lines = "".join(
            f"<div>{escape(name.replace('_', ' '))}</div><strong>{float(value):.3f}</strong>"
            for name, value in features.items()
        )
        skeleton = "".join(f"<li>{escape(step)}</li>" for step in item.get("proof_skeleton", []))
        failures = "".join(f"<li><code>{escape(reason)}</code></li>" for reason in item.get("failure_modes", []))
        paths = "".join(f"<li><code>{escape(path)}</code></li>" for path in item.get("supporting_paths", []))
        html.append(
            f"""
            <article class="artifact-card" data-agent="{escape(agent)}" data-round="{round_index}">
              <div class="artifact-meta">
                <span class="pill {css}">{escape(agent)}</span>
                <span>Round {round_index}</span>
                <span>{accepted_flag}</span>
              </div>
              <h3>{escape(str(item.get("title", "artifact")))}</h3>
              <p>{escape(str(item.get("observation", "")))}</p>
              <div class="kv">
                <div>Complexity</div><strong>{float(item.get("operator_complexity", 0.0)):.2f}</strong>
                <div>Canonical signature</div><code>{escape(str(item.get("canonical_signature", "")))}</code>
              </div>
              <details>
                <summary>Measured Features</summary>
                <div class="kv">{feature_lines or "<div>n/a</div><strong>n/a</strong>"}</div>
              </details>
              <details>
                <summary>Proof Skeleton</summary>
                <ul class="tight">{skeleton or "<li>n/a</li>"}</ul>
              </details>
              <details>
                <summary>Failure Modes</summary>
                <ul class="tight">{failures or "<li>none</li>"}</ul>
              </details>
              <details>
                <summary>Supporting Paths</summary>
                <ul class="tight">{paths or "<li>n/a</li>"}</ul>
              </details>
            </article>
            """
        )
    return "".join(html)


def _safe_read(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return [] if default is None else default
    return _read_json(path)
