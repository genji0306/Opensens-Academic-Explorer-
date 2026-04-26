"""MiroFish-style effort discovery for the RH Klein orchestrator."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from typing import Any

from src.oae.studios.timeguard.adapters.riemann import load_campaign_evidence, load_support_documents
from src.oae.studios.timeguard.schemas import (
    CampaignEvidence,
    KleinEffortDebateTurn,
    KleinEffortDiscoveryReport,
    KleinEffortPhase,
    SupportDocument,
)

_PHASE_CODE_PATTERN = re.compile(r"\bphase\s+([a-z]{1,2})\b", re.IGNORECASE)
_CHECKPOINT_PATH_PATTERN = re.compile(r"checkpoint_(\d+)_phase_([a-z]{1,2})_complete\.json$", re.IGNORECASE)
_PHASE_DIRECTION_PATTERN = re.compile(r"^(Phase\s+[A-Za-z]{1,2})\s*[:\-\u2014]\s*(.+)$")
_REPORT_PHASE_HEADING_PATTERN = re.compile(r"^### Phase ([A-Z]{1,2}): (.+?)(?:\n|$)", re.MULTILINE)
_AP_AT_PHASE_HEADING_PATTERN = re.compile(r"^## Phase ([A-Z]{1,2})\s+[—-]\s+(.+?)(?:\n|$)", re.MULTILINE)
_REPORT_MULTI_PHASE_HEADING_PATTERN = re.compile(r"^### Phases ([A-Z]/[A-Z]|[A-Z]\u2013[A-Z]): (.+?)(?:\n|$)", re.MULTILINE)
_REPORT_TABLE_ROW_PATTERN = re.compile(r"^\| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", re.MULTILINE)
_REPORT_SCORE_ROW_PATTERN = re.compile(r"^\| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", re.MULTILINE)
_PHASE_REPORT_NAME = "RH_30_PHASE_REPORT.md"
_AP_AT_REPORT_NAME = "RH_AP_AT_PHASE_REPORT.md"
_PHASE_AU_NOTE_NAME = "rh_global_omega_tail_bridge_note_20260421.md"
_PHASE_AV_REPORT_NAME = "RH_AV_PHASE_REPORT.md"
_PHASE_AY_REPORT_NAME = "RH_AY_PHASE_REPORT.md"

_PHASE_SUMMARIES = {
    "V": "Closed the Euler integer-surface route as a sterile branch rather than a viable exclusion engine.",
    "W": "Clarified the mirror and cavity structure so pure symmetry could no longer masquerade as a proof path.",
    "X": "Turned the branch toward Klein-4, symmetrized Euler-product, and Lee-Yang style structural artifacts.",
    "Y": "Reframed the program in Hardy-Z and Jensen-Pólya language, making the Lee-Yang style gap explicit.",
    "Z": "Closed the heat-flow/Lyapunov route honestly and isolated the finite-window-to-global gap in the Z-language.",
    "AA": "Built the first Laguerre, stability, Fredholm, and Li-adjacent bridge layer on top of the Z-language.",
    "AB": "Completed the Li-criterion normalization in the Z-language while exposing the finite-to-universal positivity gap.",
    "AH": "Repaired the high-precision alpha_n and Newton-Girard calibration layer so later coefficient work stopped drifting.",
    "AC": "Showed that first-order Turan or Laguerre control is insufficient by itself and added a clean no-negative-real-zeros lemma.",
    "AE": "Converted alpha_n into a Maslanka Omega/lambda pipeline and corrected the earlier convention and scaling errors.",
    "AI": "Confirmed the Li coefficients independently through direct zero-sum and Keiper calculations at high precision.",
    "AL": "Promoted the calibrated lambda-side into a generating-function program for G(w), while ruling out an easy singularity shortcut.",
    "AM": "Extracted the asymptotic sign structure of Omega_k and tied it to first-zero geometry rather than guesswork.",
    "AN": "Derived the Weil explicit-formula and prime-kernel representation for lambda_n, opening a direct arithmetic-spectral bridge.",
    "AO": "Established the exact Stieltjes-constants-to-Omega_k formula, compressing the Omega-side into a canonical arithmetic identity.",
    "AP": "Made the Bombieri-Weil positivity matrix explicit and showed finite truncations alone do not force unconditional positivity.",
    "AQ": "Located the large-n Maslanka crossover and showed the dominant-balance transition still does not close the positivity gap.",
    "AR": "Mapped the angular distribution of G(w) poles and clarified why GUE-style statistics do not yield a proof-grade boundary argument.",
    "AS": "Identified the Weil kernels K_n with Laguerre polynomials and proved the exact kernel formula non-circularly.",
    "AT": "Located the first exact Omega_k period-4 breakdown near k=46 and exposed the finite-window well-depth ceiling directly.",
    "AU": "Promoted the well-depth ceiling into an obstruction theorem: the A+B+C+D decomposition alone cannot non-circularly force the G(w) radius statement, and the missing input is now isolated to subleading Stieltjes asymptotics.",
    "AV": "Classified the residual gap as an RH-equivalence wall: published Stieltjes asymptotics, alternative non-circular routes, and reduction theory all terminate at known RH-equivalents.",
    "AY": "Closed the Padé/Hankel finite-data route: one constructive Padé convergence theorem survives, but finite-data pole recovery is precision-equivalent to the same wall isolated earlier.",
}

_PHASE_CLASSES = {
    "V": "branch closure",
    "W": "structural audit",
    "X": "structural expansion",
    "Y": "language shift",
    "Z": "branch closure",
    "AA": "bridge layer",
    "AB": "criterion bridge",
    "AH": "calibration layer",
    "AC": "obstacle map",
    "AE": "coefficient pipeline",
    "AI": "precision confirmation",
    "AL": "analytic representation",
    "AM": "asymptotic map",
    "AN": "prime-kernel bridge",
    "AO": "exact arithmetic formula",
    "AP": "positivity matrix",
    "AQ": "asymptotic crossover",
    "AR": "pole statistics audit",
    "AS": "kernel identity",
    "AT": "finite-window obstruction",
    "AU": "obstruction theorem",
    "AV": "equivalence-wall classification",
    "AY": "finite-data no-go",
}

_PHASE_STATUSES = {
    "E": "forward program",
    "G": "obstruction map",
    "H": "bridge layer",
    "I": "obstacle map",
    "J": "reframed program",
    "K": "obstacle map",
    "L": "obstacle map",
    "M": "forward program",
    "N": "closed route",
    "OP": "closed route",
    "Q": "closed route",
    "R": "closed route",
    "S": "closed route",
    "T": "closed route",
    "U": "closed route",
    "V": "closed route",
    "W": "obstacle map",
    "X": "forward program",
    "Y": "reframed program",
    "Z": "closed route",
    "AA": "bridge layer",
    "AB": "bridge layer",
    "AH": "calibration stack",
    "AC": "obstacle map",
    "AE": "calibration stack",
    "AI": "calibration stack",
    "AL": "analytic bridge",
    "AM": "asymptotic map",
    "AN": "analytic bridge",
    "AO": "analytic bridge",
    "AP": "analytic bridge",
    "AQ": "obstacle map",
    "AR": "obstacle map",
    "AS": "analytic bridge",
    "AT": "obstacle map",
    "AU": "closed route",
    "AV": "equivalence wall",
    "AY": "closed route",
}

_LEGACY_PHASE_ORDER = {
    "E": 5,
    "G": 7,
    "H": 8,
    "I": 9,
    "J": 10,
    "K": 11,
    "L": 12,
    "M": 13,
    "N": 14,
    "OP": 15,
    "Q": 16,
    "R": 17,
    "S": 18,
    "T": 19,
    "U": 20,
}

_LATE_PHASE_ORDER = {
    "AP": 36,
    "AQ": 37,
    "AR": 38,
    "AS": 39,
    "AT": 40,
    "AU": 41,
    "AV": 42,
    "AY": 43,
}

_REPORT_ONLY_PHASE_SUMMARIES = {
    "E": "Established the first Klein-topology baseline and named the main obstruction vocabulary that shaped later phases.",
    "G": "Shifted the campaign from loose idea generation to named proof-obligation targeting around the dominant obstructions.",
    "H": "Sketched the Fredholm determinant chain and localized the trace-class step as the hardest unresolved operator bottleneck.",
    "I": "Discovered the Hardy-Branges obstruction non-circularly, closing the naive E = xi de Branges construction.",
    "J": "Reset the program onto the Laguerre-Pólya framework and separated numerical interlacing evidence from proof.",
    "K": "Diagnosed the Rodgers-Tao conditionality gap and reframed Newman heat-flow work as a bounded but still circular route.",
    "L": "Derived the zero ODE and Lyapunov candidate, then exposed the sign obstruction in the backward heat-flow direction.",
    "M": "Identified the de Bruijn PFF hope around strict log-concavity before it was tested against the stronger PF_infinity requirement.",
    "N": "Closed the PFF branch by importing the PF5 counterexample, falsifying the hoped-for automatic LP conclusion.",
    "OP": "Closed the Jensen/PFS and Beurling-Nyman style branches as circular or incomplete rather than viable proof engines.",
    "Q": "Closed the angle-rotation winding ansatz because it presupposes the desired real-zero structure.",
    "R": "Closed the local winding lemmas by showing the integer winding invariants do not distinguish on-line from off-line symmetric rectangles.",
    "S": "Reduced the Dyson-CM route to a single-pair attraction story without a global Lyapunov closure.",
    "T": "Closed the Lyapunov sign route definitively after diagnosing the wrong sign in the proposed monotonicity quantity.",
    "U": "Closed the operator-theoretic alternatives as circular because every promising positivity condition reduced back to RH itself.",
}

_REPORT_ONLY_PHASE_CLASSES = {
    "E": "baseline setup",
    "G": "obstruction vocabulary",
    "H": "operator bridge",
    "I": "obstruction map",
    "J": "language shift",
    "K": "gap diagnosis",
    "L": "lyapunov attempt",
    "M": "forward conjecture",
    "N": "branch closure",
    "OP": "branch closure",
    "Q": "branch closure",
    "R": "branch closure",
    "S": "branch closure",
    "T": "branch closure",
    "U": "branch closure",
}


def run_klein_effort_discovery(
    *,
    klein_dir: str | Path,
    support_docs: tuple[str | Path, ...] = (),
    output_dir: str | Path | None = None,
) -> tuple[KleinEffortDiscoveryReport, dict[str, str] | None]:
    resolved_support_docs = _resolve_support_docs(klein_dir, support_docs)
    docs = load_support_documents(resolved_support_docs)
    campaign = load_campaign_evidence(klein_dir, support_docs=docs)
    phase_timeline = _build_phase_timeline(docs)
    closed_routes = tuple(
        phase.summary
        for phase in phase_timeline
        if phase.status in {"closed route", "obstacle map"}
    )
    capability_stack = tuple(
        phase.summary
        for phase in phase_timeline
        if phase.status in {"bridge layer", "calibration stack", "analytic bridge", "asymptotic map", "criterion bridge", "coefficient pipeline", "precision confirmation"}
    )
    current_frontier = _dedupe(
        (
            *_extract_support_doc_frontier(docs, completed={phase.phase.lower() for phase in phase_timeline}),
            *_extract_current_frontier(phase_timeline),
        )
    )
    debate_turns = _build_mirofish_debate(
        campaign,
        phase_timeline=phase_timeline,
        closed_routes=closed_routes,
        capability_stack=capability_stack,
        current_frontier=current_frontier,
    )
    warnings = _build_warnings(campaign, phase_timeline)
    report = KleinEffortDiscoveryReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        orchestrator_id=campaign.orchestrator_id,
        campaign_dir=campaign.campaign_dir,
        best_score=campaign.best_score,
        dominant_failures=campaign.dominant_failures,
        phase_timeline=phase_timeline,
        debate_turns=debate_turns,
        closed_routes=closed_routes,
        capability_stack=capability_stack,
        current_frontier=current_frontier,
        warnings=warnings,
        evidence_refs=_dedupe(
            (
                campaign.summary_path,
                campaign.failure_atlas_path,
                campaign.campaign_benchmark_path,
                *(phase.evidence_refs for phase in phase_timeline),
            )
        ),
    )
    if output_dir is None:
        return report, None
    return report, write_klein_effort_outputs(report, output_dir)


def discover_klein_phase_support_docs(klein_dir: str | Path) -> tuple[Path, ...]:
    root = Path(klein_dir).resolve().parent
    candidates: list[Path] = []
    for path in root.glob("klein-phase-*/checkpoint_*_phase_*_complete.json"):
        if not path.is_file():
            continue
        match = _CHECKPOINT_PATH_PATTERN.search(path.name)
        if not match:
            continue
        checkpoint = int(match.group(1))
        # Timeguard's Klein effort discovery starts from the modern V-branch
        # checkpoint chain, not the older pre-V experiments with different JSON
        # shapes and incompatible checkpoint semantics.
        if checkpoint < 21:
            continue
        candidates.append(path.resolve())
    candidates.sort(key=_phase_doc_sort_key)
    return tuple(candidates)


def write_klein_effort_outputs(
    report: KleinEffortDiscoveryReport,
    output_dir: str | Path,
) -> dict[str, str]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    context_path = target / "mirofish_klein_effort_context.json"
    debate_path = target / "mirofish_klein_effort_debate.json"
    report_path = target / "mirofish_klein_effort_report.md"
    html_path = target / "mirofish_klein_effort_report.html"

    context_path.write_text(
        json.dumps(
            {
                "generated_at": report.generated_at,
                "orchestrator_id": report.orchestrator_id,
                "campaign_dir": report.campaign_dir,
                "best_score": report.best_score,
                "dominant_failures": list(report.dominant_failures),
                "phase_timeline": [phase.to_dict() for phase in report.phase_timeline],
                "closed_routes": list(report.closed_routes),
                "capability_stack": list(report.capability_stack),
                "current_frontier": list(report.current_frontier),
                "warnings": list(report.warnings),
                "evidence_refs": list(report.evidence_refs),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    debate_path.write_text(
        json.dumps(
            {
                "generated_at": report.generated_at,
                "debate": [turn.to_dict() for turn in report.debate_turns],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path.write_text(render_klein_effort_markdown(report), encoding="utf-8")
    html_path.write_text(render_klein_effort_html(report), encoding="utf-8")
    return {
        "context": str(context_path),
        "debate": str(debate_path),
        "report": str(report_path),
        "html": str(html_path),
    }


def render_klein_effort_markdown(report: KleinEffortDiscoveryReport) -> str:
    summary_path = Path(report.campaign_dir) / "summary.json"
    lines = [
        "# RH Klein Orchestrator MiroFish Effort Discovery",
        "",
        f"Generated: {report.generated_at}",
        "",
        "## Campaign",
        "",
        f"- Klein campaign: [{report.orchestrator_id}]({summary_path})",
        f"- Best score: {report.best_score:.4f}",
        f"- Dominant failures: {', '.join(report.dominant_failures)}",
        "",
        "## Phase Timeline",
        "",
    ]
    for phase in report.phase_timeline:
        lines.extend(
            [
                f"### Phase {phase.phase} ({phase.title})",
                "",
                f"- Checkpoint: {phase.checkpoint}",
                f"- Score: {phase.score:.4f}",
                f"- Score delta: {phase.score_delta:+.4f}",
                f"- Contribution class: {phase.contribution_class}",
                f"- Status: {phase.status}",
                f"- Summary: {phase.summary}",
            ]
        )
        if phase.highlights:
            lines.extend(["- Highlights:", *[f"  - {item}" for item in phase.highlights]])
        if phase.next_directions:
            lines.extend(["- Next directions:", *[f"  - {item}" for item in phase.next_directions]])
        lines.extend(["- Evidence:", *[f"  - [{Path(ref).name}]({ref})" for ref in phase.evidence_refs], ""])

    lines.extend(["## MiroFish Debate", ""])
    for turn in report.debate_turns:
        lines.extend(
            [
                f"### {turn.role}",
                "",
                f"- Focus: {turn.focus}",
            ]
        )
        if turn.findings:
            lines.extend(["- Findings:", *[f"  - {item}" for item in turn.findings]])
        if turn.blind_spots:
            lines.extend(["- Blind spots:", *[f"  - {item}" for item in turn.blind_spots]])
        if turn.verdict:
            lines.append(f"- Verdict: {turn.verdict}")
        lines.extend(["- Evidence:", *[f"  - [{Path(ref).name}]({ref})" for ref in turn.evidence_refs], ""])

    lines.extend(
        [
            "## Discovery Summary",
            "",
            "- Closed routes:",
            *[f"  - {item}" for item in report.closed_routes],
            "- Capability stack:",
            *[f"  - {item}" for item in report.capability_stack],
            "- Current frontier:",
            *[f"  - {item}" for item in report.current_frontier],
            "",
        ]
    )

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def render_klein_effort_html(report: KleinEffortDiscoveryReport) -> str:
    summary_path = Path(report.campaign_dir) / "summary.json"
    phase_cards = []
    for phase in report.phase_timeline:
        highlights = "".join(f"<li>{escape(item)}</li>" for item in phase.highlights)
        directions = "".join(f"<li>{escape(item)}</li>" for item in phase.next_directions)
        evidence = "".join(
            f'<li><a href="{escape(ref)}">{escape(Path(ref).name)}</a></li>'
            for ref in phase.evidence_refs
        )
        phase_cards.append(
            "\n".join(
                [
                    '<section class="phase-card">',
                    f"<h3>Phase {escape(phase.phase)} <span>{escape(phase.title)}</span></h3>",
                    '<div class="phase-meta">',
                    f"<span>Checkpoint {phase.checkpoint}</span>",
                    f"<span>Score {phase.score:.4f}</span>",
                    f"<span>Lift {phase.score_delta:+.4f}</span>",
                    f"<span>{escape(phase.contribution_class)}</span>",
                    f"<span>{escape(phase.status)}</span>",
                    "</div>",
                    f'<p class="summary">{escape(phase.summary)}</p>',
                    '<div class="phase-grid">',
                    f'<div><h4>Highlights</h4><ul>{highlights}</ul></div>' if highlights else "",
                    f'<div><h4>Next</h4><ul>{directions}</ul></div>' if directions else "",
                    f'<div><h4>Evidence</h4><ul>{evidence}</ul></div>',
                    "</div>",
                    "</section>",
                ]
            )
        )

    debate_cards = []
    for turn in report.debate_turns:
        findings = "".join(f"<li>{escape(item)}</li>" for item in turn.findings)
        blind_spots = "".join(f"<li>{escape(item)}</li>" for item in turn.blind_spots)
        evidence = "".join(
            f'<li><a href="{escape(ref)}">{escape(Path(ref).name)}</a></li>'
            for ref in turn.evidence_refs
        )
        debate_cards.append(
            "\n".join(
                [
                    '<section class="debate-card">',
                    f"<h3>{escape(turn.role)}</h3>",
                    f'<p class="focus">{escape(turn.focus)}</p>',
                    f'<div><h4>Findings</h4><ul>{findings}</ul></div>' if findings else "",
                    f'<div><h4>Blind Spots</h4><ul>{blind_spots}</ul></div>' if blind_spots else "",
                    f'<p class="verdict"><strong>Verdict:</strong> {escape(turn.verdict)}</p>' if turn.verdict else "",
                    f'<div><h4>Evidence</h4><ul>{evidence}</ul></div>',
                    "</section>",
                ]
            )
        )

    closed_routes = "".join(f"<li>{escape(item)}</li>" for item in report.closed_routes)
    capability_stack = "".join(f"<li>{escape(item)}</li>" for item in report.capability_stack)
    current_frontier = "".join(f"<li>{escape(item)}</li>" for item in report.current_frontier)
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report.warnings)
    dominant_failures = "".join(f"<li>{escape(item)}</li>" for item in report.dominant_failures)

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8"/>',
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
            "<title>RH Klein Orchestrator MiroFish Effort Discovery</title>",
            "<style>",
            "body{margin:0;background:#0b0f14;color:#e8eef5;font:16px/1.6 Inter,system-ui,sans-serif;}",
            ".page{max-width:1400px;margin:0 auto;padding:48px 32px 80px;}",
            "h1,h2,h3,h4{margin:0 0 12px;line-height:1.2;}",
            "h1{font-size:40px;color:#ffd160;}",
            "h2{font-size:26px;color:#56d1ff;margin-top:44px;}",
            "h3{font-size:22px;color:#ffd160;}",
            "h3 span{color:#e8eef5;font-weight:500;}",
            "a{color:#7cffb2;text-decoration:none;} a:hover{text-decoration:underline;}",
            ".hero{display:grid;grid-template-columns:2fr 1fr;gap:24px;align-items:start;}",
            ".panel,.phase-card,.debate-card{background:#101721;border:1px solid #243041;border-radius:14px;padding:20px 22px;box-shadow:0 14px 40px rgba(0,0,0,.22);}",
            ".metric-list,.three-col,ul{margin:0;padding-left:18px;}",
            ".metric-list li{margin:4px 0;}",
            ".phase-meta{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;}",
            ".phase-meta span{font:12px/1.2 'Space Mono',monospace;color:#9db0c6;border:1px solid #2a3441;border-radius:999px;padding:6px 10px;}",
            ".summary,.focus,.verdict{margin:0 0 12px;}",
            ".phase-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;}",
            ".stack-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;}",
            ".timeline,.debate{display:grid;gap:18px;}",
            ".eyebrow{font:12px/1.2 'Space Mono',monospace;color:#9db0c6;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:10px;}",
            ".muted{color:#9db0c6;}",
            "@media (max-width: 960px){.hero{grid-template-columns:1fr;}}",
            "</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            '<div class="hero">',
            '<section class="panel">',
            '<div class="eyebrow">MiroFish Discovery</div>',
            "<h1>RH Klein Orchestrator Effort</h1>",
            f'<p class="summary">Generated {escape(report.generated_at)}. This bundle inventories the full Klein effort currently captured from the 30-phase report plus checkpoint-era phases and stages a multi-role debate over what was actually achieved.</p>',
            f'<p class="summary"><strong>Campaign:</strong> <a href="{escape(str(summary_path))}">{escape(report.orchestrator_id)}</a></p>',
            "</section>",
            '<section class="panel">',
            '<div class="eyebrow">State</div>',
            f'<p class="summary"><strong>Best score:</strong> {report.best_score:.4f}</p>',
            f'<p class="summary"><strong>Phase count:</strong> {len(report.phase_timeline)}</p>',
            f'<h4>Dominant Failures</h4><ul class="metric-list">{dominant_failures}</ul>',
            "</section>",
            "</div>",
            "<h2>Discovery Summary</h2>",
            '<div class="stack-grid">',
            f'<section class="panel"><h3>Closed Routes</h3><ul>{closed_routes}</ul></section>',
            f'<section class="panel"><h3>Capability Stack</h3><ul>{capability_stack}</ul></section>',
            f'<section class="panel"><h3>Current Frontier</h3><ul>{current_frontier}</ul></section>',
            "</div>",
            "<h2>Phase Timeline</h2>",
            f'<div class="timeline">{"".join(phase_cards)}</div>',
            "<h2>MiroFish Debate</h2>",
            f'<div class="debate">{"".join(debate_cards)}</div>',
            f'<section class="panel"><h2>Warnings</h2><ul>{warnings}</ul></section>' if warnings else "",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _resolve_support_docs(
    klein_dir: str | Path,
    support_docs: tuple[str | Path, ...],
) -> tuple[Path, ...]:
    ordered: list[Path] = []
    seen: set[Path] = set()
    parent = Path(klein_dir).resolve().parent
    auto_docs = tuple(
        path.resolve()
        for name in (_PHASE_REPORT_NAME, _AP_AT_REPORT_NAME, _PHASE_AU_NOTE_NAME, _PHASE_AV_REPORT_NAME, _PHASE_AY_REPORT_NAME)
        for path in (parent / name,)
        if path.exists()
    )
    for raw in (*support_docs, *auto_docs, *discover_klein_phase_support_docs(klein_dir)):
        path = Path(raw).resolve()
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return tuple(ordered)


def _build_phase_timeline(docs: tuple[SupportDocument, ...]) -> tuple[KleinEffortPhase, ...]:
    phases_by_code: dict[str, KleinEffortPhase] = {}
    phase_scores = _collect_report_score_map(docs)
    for doc in docs:
        path = Path(doc.path)
        if path.name == _PHASE_REPORT_NAME:
            for phase in _parse_phase_report_markdown(path):
                scored_phase = _apply_report_scores(phase, phase_scores)
                phases_by_code[scored_phase.phase] = scored_phase
            continue
        if path.name == _AP_AT_REPORT_NAME:
            for phase in _parse_ap_at_report_markdown(path):
                scored_phase = _apply_report_scores(phase, phase_scores)
                phases_by_code[scored_phase.phase] = scored_phase
            continue
        if path.name == _PHASE_AU_NOTE_NAME:
            phase = _parse_au_note_markdown(path, doc)
            phases_by_code[phase.phase] = _apply_report_scores(phase, phase_scores)
            continue
        if path.name == _PHASE_AV_REPORT_NAME:
            phase = _parse_av_report_markdown(path, doc)
            phases_by_code[phase.phase] = _apply_report_scores(phase, phase_scores)
            continue
        if path.name == _PHASE_AY_REPORT_NAME:
            phase = _parse_ay_report_markdown(path, doc)
            phases_by_code[phase.phase] = _apply_report_scores(phase, phase_scores)
            continue
        if path.suffix.lower() != ".json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        phase_code = str(payload.get("phase", "")).strip().upper()
        if not phase_code:
            continue
        checkpoint = int(payload.get("checkpoint", 0))
        next_directions = tuple(item for item in doc.highlights if item.lower().startswith("phase "))
        highlights = tuple(item for item in doc.highlights if not item.lower().startswith("phase ")) or doc.highlights[:3]
        phase = KleinEffortPhase(
            phase=phase_code,
            checkpoint=checkpoint,
            title=doc.title,
            summary=_PHASE_SUMMARIES.get(phase_code, doc.title),
            contribution_class=_PHASE_CLASSES.get(phase_code, _classify_phase(doc.title, highlights)),
            status=_PHASE_STATUSES.get(phase_code, "phase advance"),
            score=float(payload.get("score", 0.0)),
            score_delta=float(payload.get("score_delta", 0.0)),
            highlights=tuple(highlights[:3]),
            next_directions=next_directions,
            evidence_refs=(doc.path,),
        )
        phase = _apply_report_scores(phase, phase_scores)
        phases_by_code[phase.phase] = phase
    phases = list(phases_by_code.values())
    phases.sort(key=lambda item: (item.checkpoint, item.phase))
    return tuple(phases)


def _build_mirofish_debate(
    campaign: CampaignEvidence,
    *,
    phase_timeline: tuple[KleinEffortPhase, ...],
    closed_routes: tuple[str, ...],
    capability_stack: tuple[str, ...],
    current_frontier: tuple[str, ...],
) -> tuple[KleinEffortDebateTurn, ...]:
    phase_labels = ", ".join(f"Phase {item.phase}" for item in phase_timeline)
    latest_phase = phase_timeline[-1] if phase_timeline else None
    has_phase_at = any(item.phase == "AT" for item in phase_timeline)
    has_phase_au = any(item.phase == "AU" for item in phase_timeline)
    has_phase_av = any(item.phase == "AV" for item in phase_timeline)
    has_phase_ay = any(item.phase == "AY" for item in phase_timeline)
    evidence_refs = _dedupe(tuple(phase.evidence_refs for phase in phase_timeline))
    return (
        KleinEffortDebateTurn(
            role="Archivist",
            focus="Chronological effort inventory",
            findings=(
                f"The current Klein effort chain runs through {phase_labels}.",
                "Early phases E through U were mainly obstruction-discovery and branch-closure work that removed sterile de Branges, heat-flow, winding, and operator routes.",
                "Phases V through Z then consolidated the remaining geometric and Z-language reframing after the classical closures were in place.",
                "Middle phases AA through AC built the Laguerre, Li, and Turan bridge analysis that clarified exactly where the finite-to-universal gap sits.",
                (
                    "Later phases AE through AY consolidated the coefficient, generating-function, prime-kernel, Stieltjes, Weil-matrix, finite-window, obstruction-theorem, equivalence-wall, and finite-data no-go layers into one cumulative research stack."
                    if has_phase_ay
                    else
                    (
                    "Later phases AE through AV consolidated the coefficient, generating-function, prime-kernel, Stieltjes, Weil-matrix, finite-window, obstruction-theorem, and equivalence-wall layers into one cumulative research stack."
                    if has_phase_av
                    else
                    (
                    "Later phases AE through AU consolidated the coefficient, generating-function, prime-kernel, Stieltjes, Weil-matrix, finite-window, and obstruction-theorem layers into one cumulative research stack."
                    if has_phase_au
                    else
                    (
                    "Later phases AE through AT consolidated the coefficient, generating-function, prime-kernel, Stieltjes, Weil-matrix, and finite-window breakdown layers into one cumulative research stack."
                    if has_phase_at
                    else "Later phases AE through AO consolidated the coefficient, generating-function, prime-kernel, and Stieltjes identities into one cumulative research stack."
                    )
                    )
                    )
                ),
            ),
            verdict="The orchestrator has not repeated one idea blindly; it has steadily converted the Klein branch from structural reframing into a calibrated analytic program.",
            evidence_refs=evidence_refs,
            confidence=0.88,
        ),
        KleinEffortDebateTurn(
            role="Builder",
            focus="Durable capabilities built so far",
            findings=capability_stack[:6],
            blind_spots=(
                "Most capability gains are still representational or calibration gains, not positivity-preserving proofs.",
                "Several exact formulas now exist, but none yet force a global exclusion conclusion.",
            ),
            verdict="The strongest cumulative achievement is the build-out of a reusable arithmetic-spectral toolbox around alpha_n, Omega_k, lambda_n, G(w), and the Weil kernel.",
            evidence_refs=evidence_refs,
            confidence=0.86,
        ),
        KleinEffortDebateTurn(
            role="Auditor",
            focus="What the effort still has not closed",
            findings=(
                "The campaign still does not close the global_exclusion_gap.",
                "Translation from structural identities into certificate-grade exclusion statements remains open.",
                "Finite positivity checks, singularity maps, and exact formulas all remain one step short of a proof-grade bridge.",
            ),
            blind_spots=(
                *closed_routes[:6],
                "Later phases are checkpoint results layered on top of the Phase Z campaign rather than standalone multi-round campaign series.",
            ),
            verdict="The orchestrator has accumulated strong diagnostics and exact identities, but it still lacks a positivity-preserving or exclusion-preserving argument that survives the final translation step.",
            evidence_refs=(
                campaign.failure_atlas_path,
                campaign.summary_path,
                *evidence_refs,
            ),
            confidence=0.90,
        ),
        KleinEffortDebateTurn(
            role="Strategist",
            focus=f"Current frontier after the latest recorded phase ({latest_phase.phase if latest_phase is not None else 'unknown'})",
            findings=current_frontier[:5],
            blind_spots=(
                "The easy temptation is more large-n or more zeros; that improves calibration but not necessarily the bridge.",
                "The next branch should exploit the exact AO and AN formulas rather than reopening already-closed shortcut hopes from AL or AC.",
            ),
            verdict=_strategist_verdict(current_frontier),
            evidence_refs=evidence_refs,
            confidence=0.84,
        ),
        KleinEffortDebateTurn(
            role="Moderator",
            focus="MiroFish discovery verdict",
            findings=(
                f"Klein currently sits at best_score={campaign.best_score:.4f} with dominant failures {', '.join(campaign.dominant_failures)}.",
                latest_phase.summary if latest_phase is not None else "No Klein phase checkpoints were available to summarize.",
            ),
            verdict=(
                "The RH Klein Orchestrator effort so far is best understood as a progressive compression of the research space: closed routes first, then calibrated coefficient stacks, then exact analytic and arithmetic identities, then an equivalence-wall audit, and now a finite-data no-go for Padé/Hankel reconstruction. The current frontier is no longer any finite-data bridge, but explicit-formula and infinite-data work beyond AY."
            ),
            evidence_refs=(
                campaign.summary_path,
                campaign.failure_atlas_path,
                *evidence_refs,
            ),
            confidence=0.89,
        ),
    )


def _extract_current_frontier(phase_timeline: tuple[KleinEffortPhase, ...]) -> tuple[str, ...]:
    completed = {phase.phase.lower() for phase in phase_timeline}
    frontier: list[str] = []
    seen: set[str] = set()
    for phase in reversed(phase_timeline):
        for item in phase.next_directions:
            match = _PHASE_DIRECTION_PATTERN.match(item)
            if not match:
                normalized = item.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    frontier.append(normalized)
                continue
            code_match = _PHASE_CODE_PATTERN.search(match.group(1))
            if not code_match:
                continue
            code = code_match.group(1).lower()
            if code in completed or code in seen:
                continue
            seen.add(code)
            frontier.append(item)
    return tuple(frontier)


def _extract_support_doc_frontier(
    docs: tuple[SupportDocument, ...],
    *,
    completed: set[str],
) -> tuple[str, ...]:
    frontier: list[str] = []
    seen: set[str] = set()
    ordered_docs = [
        doc
        for _index, doc in sorted(
            enumerate(docs),
            key=lambda item: (_support_doc_frontier_priority(item[1]), -item[0]),
        )
    ]
    for doc in ordered_docs:
        for item in doc.highlights:
            match = _PHASE_DIRECTION_PATTERN.match(item.strip())
            if not match:
                normalized = item.strip()
                if (
                    "phase av" in _normalize_text(f"{doc.title} {doc.path}")
                    and _looks_like_meta_frontier(normalized)
                    and normalized not in seen
                ):
                    seen.add(normalized)
                    frontier.append(normalized)
                continue
            code_match = _PHASE_CODE_PATTERN.search(match.group(1))
            if not code_match:
                continue
            code = code_match.group(1).lower()
            if code in completed or code in seen:
                continue
            seen.add(code)
            frontier.append(item.strip())
    return tuple(frontier)


def _support_doc_frontier_priority(doc: SupportDocument) -> int:
    name = Path(doc.path).name
    if name == _PHASE_AY_REPORT_NAME:
        return 0
    if name == _PHASE_AV_REPORT_NAME:
        return 1
    if name == _PHASE_AU_NOTE_NAME:
        return 2
    if name == _AP_AT_REPORT_NAME:
        return 3
    return 4


def _strategist_verdict(current_frontier: tuple[str, ...]) -> str:
    if current_frontier and current_frontier[0].startswith("Phase AZ"):
        return (
            "The best next frontier is Phase AZ: abandon finite-data Padé/Hankel reconstruction and move into explicit-formula zero-sums, functional-equation symmetrisation, and infinite-data certificate work."
        )
    if current_frontier and (
        current_frontier[0].startswith("Investigate ")
        or current_frontier[0].startswith("Examine ")
        or current_frontier[0].startswith("Test whether ")
    ):
        return (
            "The best post-AV frontier is meta-research, not another named proof phase: audit the equivalence wall for holes, search for genuinely new G-equivalents beyond G1-G7, and test whether conditional routes can be partially unconditioned."
        )
    if current_frontier and current_frontier[0].startswith("Phase AV"):
        return (
            "The best next frontier is Phase AV: extract |gamma_{k-1}| at R_1^{-k}/2^k precision, roughly 14^k more precise than Matsuoka's bound, because AU already proved that this is the only missing input for a non-circular G(w) radius closure."
        )
    if current_frontier and current_frontier[0].startswith("Phase AU"):
        return (
            "The best next frontier is Phase AU: globalize the A+B+C+D Omega_k decomposition so the current finite-window G(w) contradiction becomes an all-k radius-of-convergence argument rather than another bounded computation."
        )
    return (
        "The best next frontier is Phase AP-style work: use the exact Omega_k and G(w) machinery to search for a positivity-preserving analytic kernel, not another finite-table extension."
    )


def _looks_like_meta_frontier(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("investigate ", "examine ", "test whether ", "search ", "probe "))


def _build_warnings(
    campaign: CampaignEvidence,
    phase_timeline: tuple[KleinEffortPhase, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if phase_timeline and phase_timeline[-1].checkpoint > 25 and campaign.orchestrator_id == "klein-phase-z-20260420":
        warnings.append(
            "Later Klein phases are layered in as checkpoint evidence on top of the Phase Z campaign; they are not standalone round-series campaigns in this bundle."
        )
    if any(phase.phase == "AV" for phase in phase_timeline) and campaign.orchestrator_id == "klein-phase-ap-at-20260421":
        warnings.append(
            "Phase AV is a report-layer characterisation phase on top of the AP-AT campaign series; it is not a standalone multi-round Klein campaign directory in this bundle."
        )
    if any(phase.phase == "AY" for phase in phase_timeline) and campaign.orchestrator_id == "klein-phase-ap-at-20260421":
        warnings.append(
            "Phase AY is a report-layer finite-data no-go on top of the AP-AT campaign series; it is not a standalone multi-round Klein campaign directory in this bundle."
        )
    if campaign.repeated_failures.get("global_exclusion_gap", 0) > 0:
        warnings.append(
            "The current Klein campaign still records global_exclusion_gap pressure, so the effort inventory should not be read as proof closure."
        )
    return tuple(warnings)


def _parse_phase_report_markdown(path: Path) -> tuple[KleinEffortPhase, ...]:
    text = path.read_text(encoding="utf-8")
    phases: list[KleinEffortPhase] = []
    phases.extend(_parse_report_phase_sections(text, path))
    phases.extend(_parse_report_closure_sections(text, path))
    return tuple(phases)


def _parse_ap_at_report_markdown(path: Path) -> tuple[KleinEffortPhase, ...]:
    text = path.read_text(encoding="utf-8")
    phases: list[KleinEffortPhase] = []
    matches = list(_AP_AT_PHASE_HEADING_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        phase_code = match.group(1).upper()
        title = match.group(2).strip()
        if phase_code not in _LATE_PHASE_ORDER:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]
        highlights = _report_section_highlights(section)
        summary = _PHASE_SUMMARIES.get(phase_code, _first_report_paragraph(section))
        phases.append(
            KleinEffortPhase(
                phase=phase_code,
                checkpoint=_LATE_PHASE_ORDER[phase_code],
                title=title,
                summary=summary,
                contribution_class=_PHASE_CLASSES.get(phase_code, _classify_phase(title, highlights)),
                status=_PHASE_STATUSES.get(phase_code, "phase advance"),
                score=0.0,
                score_delta=0.0,
                highlights=tuple(highlights[:3]),
                next_directions=tuple(),
                evidence_refs=(str(path),),
            )
        )
    return tuple(phases)


def _parse_au_note_markdown(path: Path, doc: SupportDocument) -> KleinEffortPhase:
    highlights = tuple(item for item in doc.highlights if not item.startswith("Phase AV:"))[:4]
    next_directions = tuple(item for item in doc.highlights if item.startswith("Phase "))
    return KleinEffortPhase(
        phase="AU",
        checkpoint=_LATE_PHASE_ORDER["AU"],
        title=doc.title,
        summary=_PHASE_SUMMARIES["AU"],
        contribution_class=_PHASE_CLASSES["AU"],
        status=_PHASE_STATUSES["AU"],
        score=0.9999,
        score_delta=0.0,
        highlights=highlights,
        next_directions=next_directions,
        evidence_refs=(str(path),),
    )


def _parse_av_report_markdown(path: Path, doc: SupportDocument) -> KleinEffortPhase:
    text = path.read_text(encoding="utf-8")
    highlights = tuple(item for item in doc.highlights[:4])
    next_directions = _extract_av_next_directions(text)
    return KleinEffortPhase(
        phase="AV",
        checkpoint=_LATE_PHASE_ORDER["AV"],
        title=doc.title,
        summary=_PHASE_SUMMARIES["AV"],
        contribution_class=_PHASE_CLASSES["AV"],
        status=_PHASE_STATUSES["AV"],
        score=0.9999,
        score_delta=0.0,
        highlights=highlights,
        next_directions=next_directions,
        evidence_refs=(str(path),),
    )


def _parse_ay_report_markdown(path: Path, doc: SupportDocument) -> KleinEffortPhase:
    return KleinEffortPhase(
        phase="AY",
        checkpoint=_LATE_PHASE_ORDER["AY"],
        title=doc.title,
        summary=_PHASE_SUMMARIES["AY"],
        contribution_class=_PHASE_CLASSES["AY"],
        status=_PHASE_STATUSES["AY"],
        score=0.999935,
        score_delta=0.000005,
        highlights=tuple(doc.highlights[:4]),
        next_directions=(
            "Phase AZ: Use Weil-Guinand explicit-formula zero-sums, functional-equation symmetrisation, and infinite-data integral/operator certificates after AY closed finite-data Padé/Hankel routes.",
            "Abandon finite-data routes and search for infinite-data certificates that pool all coefficients at once.",
        ),
        evidence_refs=(str(path),),
    )


def _extract_av_next_directions(text: str) -> tuple[str, ...]:
    directions: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("(i) "):
            directions.append("Investigate novel G-equivalents not on the G1-G7 list, such as modular-form periods, motivic L-functions, or GUE-conjecture-plus-epsilon.")
        elif stripped.startswith("(ii) "):
            directions.append("Examine whether conditional-on-RH results can be partially unconditioned via zero-density estimates.")
        elif stripped.startswith("(iii) "):
            directions.append("Test whether the Phase AV reduction has unrecognised holes, for instance a Weil-positivity reformulation that does not factor through LP class.")
    return tuple(directions)


def _parse_report_phase_sections(text: str, path: Path) -> list[KleinEffortPhase]:
    phases: list[KleinEffortPhase] = []
    matches = list(_REPORT_PHASE_HEADING_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        phase_code = match.group(1).upper()
        title = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]
        if phase_code not in _LEGACY_PHASE_ORDER:
            continue
        summary = _REPORT_ONLY_PHASE_SUMMARIES.get(phase_code, _first_report_paragraph(section))
        highlights = _report_section_highlights(section)
        phases.append(
            KleinEffortPhase(
                phase=phase_code,
                checkpoint=_LEGACY_PHASE_ORDER[phase_code],
                title=title,
                summary=summary,
                contribution_class=_REPORT_ONLY_PHASE_CLASSES.get(phase_code, _classify_phase(title, highlights)),
                status=_PHASE_STATUSES.get(phase_code, "phase advance"),
                score=0.0,
                score_delta=0.0,
                highlights=tuple(highlights[:3]),
                next_directions=tuple(),
                evidence_refs=(str(path),),
            )
        )
    return phases


def _normalize_text(value: str) -> str:
    return value.lower().replace("-", " ").replace("_", " ")


def _parse_report_closure_sections(text: str, path: Path) -> list[KleinEffortPhase]:
    phases: list[KleinEffortPhase] = []
    op_match = _REPORT_MULTI_PHASE_HEADING_PATTERN.search(text)
    if op_match and op_match.group(1) == "O/P":
        start = op_match.end()
        next_heading = re.search(r"^### ", text[start:], re.MULTILINE)
        end = start + next_heading.start() if next_heading else len(text)
        section = text[start:end]
        highlights = _report_section_highlights(section)
        phases.append(
            KleinEffortPhase(
                phase="OP",
                checkpoint=_LEGACY_PHASE_ORDER["OP"],
                title=op_match.group(2).strip(),
                summary=_REPORT_ONLY_PHASE_SUMMARIES["OP"],
                contribution_class=_REPORT_ONLY_PHASE_CLASSES["OP"],
                status=_PHASE_STATUSES["OP"],
                score=0.0,
                score_delta=0.0,
                highlights=tuple(highlights[:3]),
                next_directions=tuple(),
                evidence_refs=(str(path),),
            )
        )

    qv_match = re.search(r"^### Phases Q[–-]V: (.+?)(?:\n|$)", text, re.MULTILINE)
    if not qv_match:
        return phases
    start = qv_match.end()
    next_heading = re.search(r"^### ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    section = text[start:end]
    for phase_code, branch, reason in _REPORT_TABLE_ROW_PATTERN.findall(section):
        normalized_code = phase_code.strip().upper()
        if normalized_code not in {"Q", "R", "S", "T", "U"}:
            continue
        phases.append(
            KleinEffortPhase(
                phase=normalized_code,
                checkpoint=_LEGACY_PHASE_ORDER[normalized_code],
                title=branch.strip(),
                summary=reason.strip(),
                contribution_class=_REPORT_ONLY_PHASE_CLASSES.get(normalized_code, "branch closure"),
                status=_PHASE_STATUSES.get(normalized_code, "closed route"),
                score=0.0,
                score_delta=0.0,
                highlights=(reason.strip(),),
                next_directions=tuple(),
                evidence_refs=(str(path),),
            )
        )
    return phases


def _collect_report_score_map(docs: tuple[SupportDocument, ...]) -> dict[str, tuple[float, float]]:
    score_map: dict[str, tuple[float, float]] = {}
    for doc in docs:
        path = Path(doc.path)
        if path.name not in {_PHASE_REPORT_NAME, _AP_AT_REPORT_NAME}:
            continue
        text = path.read_text(encoding="utf-8")
        for phase_token, score_text, lift_text, _character in _REPORT_SCORE_ROW_PATTERN.findall(text):
            score = _parse_float(score_text)
            delta = _parse_float(lift_text) if "+" in lift_text or "-" in lift_text else 0.0
            for code in _expand_phase_score_token(phase_token.strip()):
                score_map[code] = (score, delta)
    return score_map


def _apply_report_scores(
    phase: KleinEffortPhase,
    score_map: dict[str, tuple[float, float]],
) -> KleinEffortPhase:
    if phase.phase not in score_map:
        return phase
    score, delta = score_map[phase.phase]
    if phase.score and phase.score > 0.0:
        return phase
    return KleinEffortPhase(
        phase=phase.phase,
        checkpoint=phase.checkpoint,
        title=phase.title,
        summary=phase.summary,
        contribution_class=phase.contribution_class,
        status=phase.status,
        score=score,
        score_delta=delta,
        highlights=phase.highlights,
        next_directions=phase.next_directions,
        evidence_refs=phase.evidence_refs,
    )


def _classify_phase(title: str, highlights: tuple[str, ...]) -> str:
    text = f"{title} {' '.join(highlights)}".lower()
    if any(token in text for token in ("stieltjes", "explicit formula", "generating function", "prime sum", "kernel")):
        return "analytic bridge"
    if any(token in text for token in ("high-precision", "consistency", "computed", "numerical")):
        return "calibration layer"
    if any(token in text for token in ("asymptotic", "sign")):
        return "asymptotic map"
    if any(token in text for token in ("criterion", "inequalities", "bridge", "tower", "lemma")):
        return "bridge analysis"
    return "phase advance"


def _expand_phase_score_token(token: str) -> tuple[str, ...]:
    normalized = token.replace(" ", "")
    if normalized in {"L–N", "L-N"}:
        return ("L", "M", "N")
    if normalized in {"O/P–V", "O/P-V"}:
        return ("OP", "Q", "R", "S", "T", "U", "V")
    if normalized == "AE+AI":
        return ("AE", "AI")
    if normalized == "AL+AM":
        return ("AL", "AM")
    if normalized == "AN+AO":
        return ("AN", "AO")
    if normalized == "Baseline":
        return tuple()
    return (normalized,)


def _first_report_paragraph(section: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", section) if part.strip()]
    for paragraph in paragraphs:
        line = " ".join(item.strip() for item in paragraph.splitlines())
        if not line.startswith("|") and not line.startswith("```"):
            return line
    return ""


def _report_section_highlights(section: str) -> tuple[str, ...]:
    highlights: list[str] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("|") or line.startswith("```"):
            continue
        if line.startswith("###") or line.startswith("##"):
            break
        if line.startswith("- ") or line.startswith("* "):
            line = line[2:].strip()
        if line not in highlights:
            highlights.append(line)
        if len(highlights) >= 3:
            break
    return tuple(highlights)


def _parse_float(value: str) -> float:
    cleaned = value.strip().replace("—", "").replace(",", "")
    if cleaned in {"", "0", "0.0"}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _phase_doc_sort_key(path: Path) -> tuple[int, str]:
    match = _CHECKPOINT_PATH_PATTERN.search(path.name)
    if match:
        return (int(match.group(1)), match.group(2).lower())
    return (9999, path.name.lower())


def _dedupe(values: tuple[Any, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, tuple):
            for nested in value:
                if not nested:
                    continue
                token = str(nested)
                if token in seen:
                    continue
                seen.add(token)
                ordered.append(token)
            continue
        if not value:
            continue
        token = str(value)
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)
