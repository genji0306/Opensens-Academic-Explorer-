"""Map historical RH proof-attempt literature onto orchestrator approaches and hypotheses."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.io import to_html

from .proof_attempts import PROOF_ATTEMPTS_CATALOG_PATH, load_attempt_catalog

SLATE = "#0f172a"
TEAL = "#0f766e"
EMERALD = "#059669"
AMBER = "#d97706"
ROSE = "#e11d48"
SURFACE = "#f8fafc"
CARD = "#ffffff"
LITERATURE_MAP_FILE = "attempt_connection_map.json"
LITERATURE_DASHBOARD_FILE = "attempt_connection_dashboard.html"


def build_literature_connection_map(
    campaign_dir: Path,
    *,
    catalog_path: Path | None = None,
) -> dict[str, Any] | None:
    summary_path = campaign_dir / "summary.json"
    approach_map_path = campaign_dir / "approach_map.json"
    if not summary_path.exists() or not approach_map_path.exists():
        return None

    target_catalog = catalog_path or PROOF_ATTEMPTS_CATALOG_PATH
    if not target_catalog.exists():
        return None

    summary = _read_json(summary_path)
    approach_map = _read_json(approach_map_path)
    catalog = load_attempt_catalog(target_catalog)
    rounds = _load_rounds(campaign_dir)

    sources = {item["source_id"]: item for item in approach_map.get("sources", [])}
    approaches = approach_map.get("approaches", [])
    hypotheses_by_id = {
        hypothesis["candidate_id"]: {"round_index": round_item["round_index"], **hypothesis}
        for round_item in rounds
        for hypothesis in round_item["hypotheses"]
    }
    evaluations_by_id = {
        evaluation["candidate_id"]: {"round_index": round_item["round_index"], **evaluation}
        for round_item in rounds
        for evaluation in round_item["evaluations"]
    }
    novelty_by_candidate = {
        evaluation["candidate_id"]: tuple(evaluation.get("novelty_artifact_ids", ()))
        for round_item in rounds
        for evaluation in round_item["evaluations"]
    }

    attempt_source_ids: dict[str, str] = {}
    for source_id, source in sources.items():
        stem = Path(str(source.get("locator", ""))).stem
        if stem:
            attempt_source_ids[stem] = source_id

    attempt_rows: list[dict[str, Any]] = []
    family_rollup: dict[str, dict[str, Any]] = {}
    attempt_nodes: list[str] = []
    family_nodes: list[str] = []
    hypothesis_nodes: list[str] = []
    links_source: list[int] = []
    links_target: list[int] = []
    links_value: list[float] = []

    for attempt in catalog.get("attempts", []):
        attempt_id = str(attempt["attempt_id"])
        title = str(attempt["title"])
        family = str(attempt["orchestrator_family"])
        source_id = attempt_source_ids.get(attempt_id, "")
        mapped_approaches = [
            approach
            for approach in approaches
            if source_id and source_id in approach.get("cited_sources", [])
        ]
        mapped_approach_ids = [item["approach_id"] for item in mapped_approaches]
        baseline = max((float(item.get("observer_scores", {}).get("baseline_proximity", 0.0)) for item in mapped_approaches), default=0.0)

        hypothesis_hits: list[dict[str, Any]] = []
        quantum_branch_hits: list[dict[str, Any]] = []
        best_score = 0.0
        best_candidate_id = ""
        best_local_connections: list[str] = []
        for candidate_id, hypothesis in hypotheses_by_id.items():
            ingredient_ids = set(hypothesis.get("ingredient_approach_ids", ()))
            if not ingredient_ids.intersection(mapped_approach_ids):
                continue
            evaluation = evaluations_by_id.get(candidate_id, {})
            score = float(evaluation.get("score", 0.0))
            best_score = max(best_score, score)
            if score >= best_score:
                best_candidate_id = candidate_id
                best_local_connections = _local_connection_titles(
                    hypothesis,
                    approaches=approaches,
                    sources=sources,
                    exclude_source_ids={source_id},
                )
            quantum_branch = _extract_quantum_branch(hypothesis)
            hypothesis_hits.append(
                {
                    "candidate_id": candidate_id,
                    "round_index": int(hypothesis.get("round_index", 0)),
                    "score": score,
                    "ingredient_families": tuple(hypothesis.get("ingredient_families", ())),
                    "compatibility_checks": tuple(hypothesis.get("compatibility_checks", ())),
                    "quantum_branch": quantum_branch,
                    "novelty_artifact_ids": tuple(novelty_by_candidate.get(candidate_id, ())),
                    "claim": str(hypothesis.get("claim", "")),
                }
            )
            if quantum_branch:
                quantum_branch_hits.append(
                    {
                        "candidate_id": candidate_id,
                        "round_index": int(hypothesis.get("round_index", 0)),
                        "score": score,
                        "quantum_branch": quantum_branch,
                        "ingredient_families": tuple(hypothesis.get("ingredient_families", ())),
                        "novelty_artifact_ids": tuple(novelty_by_candidate.get(candidate_id, ())),
                        "claim": str(hypothesis.get("claim", "")),
                    }
                )

        hypothesis_hits.sort(key=lambda item: (-item["score"], item["candidate_id"]))
        hypothesis_hits = hypothesis_hits[:3]
        quantum_branch_hits.sort(key=lambda item: (-item["score"], item["candidate_id"]))
        quantum_branch_hits = quantum_branch_hits[:4]
        connection_strength = min(1.0, 0.55 * baseline + 0.45 * best_score)
        row = {
            "attempt_id": attempt_id,
            "title": title,
            "historical_family": attempt["historical_family"],
            "orchestrator_family": family,
            "status": attempt["status"],
            "summary": attempt["summary"],
            "mechanism": attempt["mechanism"],
            "why_not_proof": attempt["why_not_proof"],
            "connection_note": attempt["connection_note"],
            "keywords": attempt["keywords"],
            "source_ids": attempt["source_ids"],
            "sources": [catalog["source_registry"][item] for item in attempt["source_ids"]],
            "mapped_source_id": source_id,
            "mapped_approach_ids": mapped_approach_ids,
            "baseline_proximity": baseline,
            "best_hypothesis_score": best_score,
            "best_hypothesis_id": best_candidate_id,
            "top_hypotheses": hypothesis_hits,
            "quantum_branch_hits": quantum_branch_hits,
            "local_oae_connections": best_local_connections,
            "connection_strength": connection_strength,
        }
        attempt_rows.append(row)

        family_entry = family_rollup.setdefault(
            family,
            {
                "family": family,
                "attempt_count": 0,
                "mapped_attempt_count": 0,
                "best_score": 0.0,
                "attempt_ids": [],
            },
        )
        family_entry["attempt_count"] += 1
        if mapped_approach_ids:
            family_entry["mapped_attempt_count"] += 1
        family_entry["best_score"] = max(float(family_entry["best_score"]), best_score)
        family_entry["attempt_ids"].append(attempt_id)

        attempt_node = f"attempt:{title}"
        family_node = f"family:{family}"
        if attempt_node not in attempt_nodes:
            attempt_nodes.append(attempt_node)
        if family_node not in family_nodes:
            family_nodes.append(family_node)
        links_source.append(_node_index(attempt_node, attempt_nodes, family_nodes, hypothesis_nodes))
        links_target.append(_node_index(family_node, attempt_nodes, family_nodes, hypothesis_nodes))
        links_value.append(1.0)

        if best_candidate_id:
            hypothesis_node = f"hyp:{best_candidate_id}"
            if hypothesis_node not in hypothesis_nodes:
                hypothesis_nodes.append(hypothesis_node)
            links_source.append(_node_index(family_node, attempt_nodes, family_nodes, hypothesis_nodes))
            links_target.append(_node_index(hypothesis_node, attempt_nodes, family_nodes, hypothesis_nodes))
            links_value.append(max(best_score, 0.05))

    attempt_rows.sort(key=lambda item: (-item["connection_strength"], item["attempt_id"]))
    family_rows = sorted(family_rollup.values(), key=lambda item: (-item["best_score"], item["family"]))
    quantum_branch_summary = _quantum_branch_summary(attempt_rows)
    payload = {
        "campaign_id": summary.get("campaign_id", campaign_dir.name),
        "campaign_dir": str(campaign_dir),
        "catalog_path": str(target_catalog),
        "summary_path": str(summary_path),
        "approach_map_path": str(approach_map_path),
        "literature_attempt_count": len(attempt_rows),
        "mapped_attempt_count": sum(1 for item in attempt_rows if item["mapped_approach_ids"]),
        "rounds_run": int(summary.get("rounds_run", 0)),
        "best_candidate_id": str(summary.get("best_candidate_id", "")),
        "best_score": float(summary.get("best_score", 0.0)),
        "quantum_branch_summary": quantum_branch_summary,
        "attempts": attempt_rows,
        "families": family_rows,
        "sankey": {
            "nodes": attempt_nodes + family_nodes + hypothesis_nodes,
            "sources": links_source,
            "targets": links_target,
            "values": links_value,
        },
    }
    return payload


def write_literature_connection_outputs(
    campaign_dir: Path,
    *,
    catalog_path: Path | None = None,
) -> dict[str, str] | None:
    payload = build_literature_connection_map(campaign_dir, catalog_path=catalog_path)
    if payload is None:
        return None

    json_path = campaign_dir / LITERATURE_MAP_FILE
    html_path = campaign_dir / LITERATURE_DASHBOARD_FILE
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    html_path.write_text(render_literature_connection_html(payload), encoding="utf-8")
    return {
        "literature_connection_map": str(json_path),
        "literature_connection_dashboard": str(html_path),
        "proof_attempt_catalog": payload["catalog_path"],
    }


def render_literature_connection_html(payload: dict[str, Any]) -> str:
    plot_html = to_html(
        build_literature_connection_figure(payload),
        include_plotlyjs="inline",
        full_html=False,
        config={"displayModeBar": True, "responsive": True},
    )
    attempts_html = "".join(_attempt_card(item) for item in payload.get("attempts", []))
    quantum_summary = payload.get("quantum_branch_summary", [])
    quantum_summary_html = "".join(
        f"""
        <article class="branch-summary-card interactive" data-branch="{escape(item['branch'])}" tabindex="0" role="button">
          <div class="branch-summary-kicker">{escape(item['branch'].replace('_', ' '))}</div>
          <strong>{item['best_score']:.4f}</strong>
          <div>best: <code>{escape(item['best_candidate_id'])}</code></div>
          <div>attempts {int(item['attempt_count'])} · avg {item['avg_score']:.4f}</div>
        </article>
        """
        for item in quantum_summary
    )
    family_options = "".join(
        f"<option value=\"{escape(item['family'])}\">{escape(item['family'])}</option>"
        for item in payload.get("families", [])
    )
    status_options = "".join(
        f"<option value=\"{escape(status)}\">{escape(status)}</option>"
        for status in sorted({item["status"] for item in payload.get("attempts", [])})
    )
    branch_options = "".join(
        f"<option value=\"{escape(item['branch'])}\">{escape(item['branch'])}</option>"
        for item in quantum_summary
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RH Literature Connection Map</title>
  <style>
    :root {{
      --navy: {SLATE};
      --teal: {TEAL};
      --emerald: {EMERALD};
      --amber: {AMBER};
      --rose: {ROSE};
      --surface: {SURFACE};
      --card: {CARD};
      --border: rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #eff6ff 0%, var(--surface) 30%, #eef2ff 100%);
      color: var(--navy);
    }}
    main {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 32px 24px 64px;
    }}
    .hero {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-bottom: 24px;
    }}
    .metric, .panel, .attempt-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 20px 40px rgba(15, 23, 42, 0.06);
    }}
    .metric {{
      padding: 18px 20px;
    }}
    .metric .value {{
      font-size: 1.8rem;
      font-weight: 700;
      margin-top: 8px;
    }}
    .panel {{
      padding: 20px 22px;
      margin-bottom: 20px;
    }}
    .filters {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin-bottom: 20px;
    }}
    input, select {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: #fff;
      color: var(--navy);
    }}
    .cards {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    .attempt-card {{
      padding: 18px 20px;
    }}
    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0;
    }}
    .tag {{
      font-size: 0.78rem;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.10);
      color: var(--teal);
    }}
    .sources, .hypotheses {{
      margin-top: 12px;
      display: grid;
      gap: 10px;
    }}
    .branch-summary-grid {{
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin-top: 14px;
    }}
    .branch-summary-card {{
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(15, 23, 42, 0.03);
      border: 1px solid var(--border);
    }}
    .branch-summary-card.interactive {{
      cursor: pointer;
      transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    .branch-summary-card.interactive:hover,
    .branch-summary-card.interactive:focus {{
      transform: translateY(-1px);
      border-color: rgba(15, 118, 110, 0.45);
      box-shadow: 0 14px 24px rgba(15, 23, 42, 0.08);
      outline: none;
    }}
    .branch-summary-card.active {{
      border-color: rgba(225, 29, 72, 0.45);
      box-shadow: 0 14px 28px rgba(225, 29, 72, 0.10);
    }}
    .branch-summary-card strong {{
      display: block;
      font-size: 1.5rem;
      margin: 8px 0 6px;
    }}
    .branch-summary-kicker {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.76rem;
      color: var(--navy);
    }}
    .source-row, .hyp-row {{
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(15, 23, 42, 0.03);
    }}
    a {{
      color: var(--rose);
      text-decoration: none;
    }}
    .muted {{ color: #475569; }}
    .strong {{ font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="metric"><div class="muted">Campaign</div><div class="value">{escape(payload['campaign_id'])}</div></div>
      <div class="metric"><div class="muted">Literature attempts</div><div class="value">{payload['literature_attempt_count']}</div></div>
      <div class="metric"><div class="muted">Mapped attempts</div><div class="value">{payload['mapped_attempt_count']}</div></div>
      <div class="metric"><div class="muted">Campaign best score</div><div class="value">{payload['best_score']:.4f}</div></div>
    </section>
    <section class="panel">
      <h2>Connection Graph</h2>
      <p class="muted">
        Historical proof-attempt families are mapped into the orchestrator's internal family taxonomy and then into the
        highest-scoring hypotheses that actually used the ingested approach cards.
      </p>
      {plot_html}
    </section>
    <section class="panel">
      <h2>Quantum Branch Connections</h2>
      <p class="muted">
        Quantum-linked literature attempts can now expose separate <code>operator_hard</code> and
        <code>operator_bridge</code> hypothesis links inside the mapping itself.
      </p>
      <div class="branch-summary-grid">
        {quantum_summary_html or "<p class=\"muted\">No quantum branch links were detected for this campaign.</p>"}
      </div>
    </section>
    <section class="panel">
      <h2>Attempt Atlas</h2>
      <div class="filters">
        <input id="search" type="search" placeholder="Search title, family, keyword" />
        <select id="family-filter">
          <option value="">All orchestrator families</option>
          {family_options}
        </select>
        <select id="status-filter">
          <option value="">All statuses</option>
          {status_options}
        </select>
        <select id="branch-filter">
          <option value="">All quantum branches</option>
          {branch_options}
        </select>
      </div>
      <div class="cards" id="attempt-cards">
        {attempts_html}
      </div>
    </section>
  </main>
  <script>
    const cards = Array.from(document.querySelectorAll(".attempt-card"));
    const search = document.getElementById("search");
    const family = document.getElementById("family-filter");
    const status = document.getElementById("status-filter");
    const branch = document.getElementById("branch-filter");
    const branchCards = Array.from(document.querySelectorAll(".branch-summary-card[data-branch]"));
    function applyFilters() {{
      const searchText = search.value.trim().toLowerCase();
      const familyValue = family.value;
      const statusValue = status.value;
      const branchValue = branch.value;
      cards.forEach((card) => {{
        const haystack = card.dataset.search;
        const branches = (card.dataset.quantumBranches || "").split(",").filter(Boolean);
        const matchesSearch = !searchText || haystack.includes(searchText);
        const matchesFamily = !familyValue || card.dataset.family === familyValue;
        const matchesStatus = !statusValue || card.dataset.status === statusValue;
        const matchesBranch = !branchValue || branches.includes(branchValue);
        card.style.display = matchesSearch && matchesFamily && matchesStatus && matchesBranch ? "" : "none";
      }});
      branchCards.forEach((card) => {{
        card.classList.toggle("active", !!branchValue && card.dataset.branch === branchValue);
      }});
    }}
    function setBranchFilter(value) {{
      branch.value = value;
      applyFilters();
    }}
    search.addEventListener("input", applyFilters);
    family.addEventListener("change", applyFilters);
    status.addEventListener("change", applyFilters);
    branch.addEventListener("change", applyFilters);
    branchCards.forEach((card) => {{
      card.addEventListener("click", () => {{
        setBranchFilter(card.dataset.branch === branch.value ? "" : card.dataset.branch);
      }});
      card.addEventListener("keydown", (event) => {{
        if (event.key === "Enter" || event.key === " ") {{
          event.preventDefault();
          setBranchFilter(card.dataset.branch === branch.value ? "" : card.dataset.branch);
        }}
      }});
    }});
  </script>
</body>
</html>
"""


def build_literature_connection_figure(payload: dict[str, Any]) -> go.Figure:
    nodes = payload.get("sankey", {}).get("nodes", [])
    sources = payload.get("sankey", {}).get("sources", [])
    targets = payload.get("sankey", {}).get("targets", [])
    values = payload.get("sankey", {}).get("values", [])
    colors = []
    for node in nodes:
        if str(node).startswith("attempt:"):
            colors.append(AMBER)
        elif str(node).startswith("family:"):
            colors.append(TEAL)
        else:
            colors.append(EMERALD)

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=16,
                thickness=18,
                line=dict(color=SLATE, width=0.4),
                label=[node.split(":", 1)[1] for node in nodes],
                color=colors,
            ),
            link=dict(source=sources, target=targets, value=values, color="rgba(15, 118, 110, 0.18)"),
        )
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=SURFACE,
        plot_bgcolor=CARD,
        margin=dict(l=24, r=24, t=40, b=20),
        height=720,
    )
    return fig


def _attempt_card(item: dict[str, Any]) -> str:
    sources_html = "".join(
        f"<div class=\"source-row\"><div class=\"strong\">{escape(source['title'])}</div>"
        f"<div class=\"muted\">{escape(', '.join(source['authors']))} ({int(source['year'])})</div>"
        f"<div><a href=\"{escape(source['url'])}\" target=\"_blank\" rel=\"noreferrer\">{escape(source['url'])}</a></div></div>"
        for source in item.get("sources", [])
    )
    hypotheses = item.get("top_hypotheses", [])
    hypotheses_html = "".join(
        f"<div class=\"hyp-row\"><div class=\"strong\">{escape(hit['candidate_id'])}</div>"
        f"<div class=\"muted\">round {int(hit['round_index'])} | score {float(hit['score']):.4f}</div>"
        f"<div>{escape(', '.join(hit['ingredient_families']))}</div></div>"
        for hit in hypotheses
    ) or "<div class=\"hyp-row\"><div class=\"muted\">No hypothesis used this attempt directly in the bounded run.</div></div>"
    quantum_hits = item.get("quantum_branch_hits", [])
    quantum_branches = sorted(
        {
            str(hit.get("quantum_branch", ""))
            for hit in quantum_hits
            if str(hit.get("quantum_branch", ""))
        }
    )
    quantum_html = "".join(
        f"<div class=\"hyp-row\"><div class=\"strong\">{escape(hit['quantum_branch'])}</div>"
        f"<div class=\"muted\">{escape(hit['candidate_id'])} | round {int(hit['round_index'])} | score {float(hit['score']):.4f}</div>"
        f"<div>{escape(', '.join(hit['ingredient_families']))}</div></div>"
        for hit in quantum_hits
    )
    local_connections = item.get("local_oae_connections", [])
    local_html = "".join(f"<span class=\"tag\">{escape(title)}</span>" for title in local_connections) or "<span class=\"tag\">no local OAE peer source</span>"
    tags = (
        f"<span class=\"tag\">{escape(item['historical_family'])}</span>"
        f"<span class=\"tag\">{escape(item['orchestrator_family'])}</span>"
        f"<span class=\"tag\">{escape(item['status'])}</span>"
        f"<span class=\"tag\">strength {float(item['connection_strength']):.2f}</span>"
    )
    search_text = " ".join(
        [
            item["title"],
            item["historical_family"],
            item["orchestrator_family"],
            item["status"],
            *item.get("keywords", []),
        ]
    ).lower()
    parts = [
        f"<article class=\"attempt-card\" data-family=\"{escape(item['orchestrator_family'])}\" "
        f"data-status=\"{escape(item['status'])}\" data-search=\"{escape(search_text)}\" "
        f"data-quantum-branches=\"{escape(','.join(quantum_branches))}\">",
        f"<h3>{escape(item['title'])}</h3>",
        f"<p class=\"muted\">{escape(item['summary'])}</p>",
        f"<div class=\"tags\">{tags}</div>",
        f"<p><span class=\"strong\">Mechanism:</span> {escape(item['mechanism'])}</p>",
        f"<p><span class=\"strong\">Gap:</span> {escape(item['why_not_proof'])}</p>",
        f"<p><span class=\"strong\">OAE connection:</span> {escape(item['connection_note'])}</p>",
        f"<div class=\"tags\">{local_html}</div>",
        f"<div class=\"hypotheses\"><div class=\"strong\">Top connected hypotheses</div>{hypotheses_html}</div>",
    ]
    if quantum_hits:
        parts.append(
            f"<div class=\"hypotheses\"><div class=\"strong\">Quantum branch links</div>{quantum_html}</div>"
        )
    parts.extend(
        [
            f"<div class=\"sources\"><div class=\"strong\">Representative sources</div>{sources_html}</div>",
            "</article>",
        ]
    )
    return "".join(parts)


def _load_rounds(campaign_dir: Path) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    for eval_path in sorted(campaign_dir.glob("round_*_evaluations.json")):
        stem = eval_path.name.replace("_evaluations.json", "")
        rounds.append(
            {
                "round_index": int(stem.split("_")[1]),
                "hypotheses": _safe_read(campaign_dir / f"{stem}_hypotheses.json", []),
                "evaluations": _safe_read(eval_path, []),
            }
        )
    return rounds


def _node_index(
    node: str,
    attempt_nodes: list[str],
    family_nodes: list[str],
    hypothesis_nodes: list[str],
) -> int:
    nodes = attempt_nodes + family_nodes + hypothesis_nodes
    return nodes.index(node)


def _local_connection_titles(
    hypothesis: dict[str, Any],
    *,
    approaches: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    exclude_source_ids: set[str],
) -> list[str]:
    titles: list[str] = []
    approach_by_id = {item["approach_id"]: item for item in approaches}
    for approach_id in hypothesis.get("ingredient_approach_ids", ()):
        approach = approach_by_id.get(approach_id, {})
        for source_id in approach.get("cited_sources", ()):
            if source_id in exclude_source_ids:
                continue
            source = sources.get(source_id, {})
            locator = str(source.get("locator", ""))
            if "/data/riemann/reports/" not in locator and "rh_operator_calibration" not in locator:
                continue
            title = str(source.get("title", Path(locator).name))
            if title not in titles:
                titles.append(title)
    return titles[:6]


def _extract_quantum_branch(hypothesis: dict[str, Any]) -> str:
    for token in hypothesis.get("compatibility_checks", ()):
        value = str(token)
        if value.startswith("quantum_branch="):
            return value.split("=", 1)[1]
    return ""


def _quantum_branch_summary(attempt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for attempt in attempt_rows:
        attempt_id = str(attempt.get("attempt_id", ""))
        for hit in attempt.get("quantum_branch_hits", ()):
            branch = str(hit.get("quantum_branch", ""))
            candidate_id = str(hit.get("candidate_id", ""))
            if not branch or (branch, candidate_id) in seen_pairs:
                continue
            seen_pairs.add((branch, candidate_id))
            entry = summary.setdefault(
                branch,
                {
                    "branch": branch,
                    "attempt_count": 0,
                    "best_score": 0.0,
                    "best_candidate_id": "",
                    "avg_score_total": 0.0,
                },
            )
            entry["attempt_count"] += 1
            entry["avg_score_total"] += float(hit.get("score", 0.0))
            if float(hit.get("score", 0.0)) >= float(entry["best_score"]):
                entry["best_score"] = float(hit.get("score", 0.0))
                entry["best_candidate_id"] = candidate_id
    rows = []
    for entry in summary.values():
        count = max(1, int(entry["attempt_count"]))
        rows.append({**entry, "avg_score": float(entry["avg_score_total"]) / count})
    rows.sort(key=lambda item: (-item["best_score"], item["branch"]))
    return rows


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return _read_json(path)
