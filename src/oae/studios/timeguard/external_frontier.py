"""External frontier discovery and seed-pack synthesis for Timeguard.

This lane is intentionally local-first. It accepts harvested claim files from
future OASIS / web collection layers, filters them through the current RH map,
and emits orchestrator-ready seed packs instead of treating raw online debate as
evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from src.oae.studios.timeguard.adapters.riemann import build_timeguard_context
from src.oae.studios.timeguard.forecast.timesfm_adapter import TimesFMAdapter
from src.oae.studios.timeguard.mirofish_discovery import run_klein_effort_discovery
from src.oae.studios.timeguard.oasis_adapter import load_oasis_claim_rows
from src.oae.studios.timeguard.ranking import rank_work_packages
from src.oae.studios.timeguard.schemas import (
    ExternalClaim,
    ExternalFrontierReport,
    FrontierDebateTurn,
    OrchestratorSeedPack,
)

_BULLET_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$")
_HEADING_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")

_ROUTE_PRIORITY = {
    "operator": 1.00,
    "explicit_formula": 0.95,
    "symmetrisation": 0.90,
    "tail_control": 0.86,
    "meta_research": 0.45,
    "equivalence_search": 0.30,
    "finite_data": 0.05,
    "unclear": 0.20,
}

_STATUS_PRIORITY = {
    "promote": 1.00,
    "needs_formalization": 0.75,
    "meta_only": 0.40,
    "avoid": 0.05,
}


def run_external_frontier_discovery(
    *,
    baseline_dir: str | Path,
    klein_dir: str | Path,
    support_docs: tuple[str | Path, ...] = (),
    claim_docs: tuple[str | Path, ...] = (),
    oasis_dbs: tuple[str | Path, ...] = (),
    output_dir: str | Path | None = None,
    top_seed_packs: int = 3,
) -> tuple[ExternalFrontierReport, dict[str, str] | None]:
    context = build_timeguard_context(
        baseline_dir,
        klein_dir,
        support_docs=support_docs,
    )
    effort_report, _ = run_klein_effort_discovery(
        klein_dir=klein_dir,
        support_docs=support_docs,
    )
    forecasts = (
        TimesFMAdapter().forecast_campaign(context.baseline),
        TimesFMAdapter().forecast_campaign(context.klein),
    )
    current_work_packages = rank_work_packages(context, forecasts, top_k=3)
    taboo_routes = _build_taboo_routes(context, effort_report)
    claims = _load_and_evaluate_claims(
        claim_docs=claim_docs,
        oasis_dbs=oasis_dbs,
        baseline_id=context.baseline.orchestrator_id,
        klein_id=context.klein.orchestrator_id,
        current_frontier=effort_report.current_frontier,
        taboo_routes=taboo_routes,
    )
    seed_packs = _build_seed_packs(
        claims,
        support_docs=support_docs,
        current_frontier=effort_report.current_frontier,
        current_work_packages=tuple(item.title for item in current_work_packages),
        taboo_routes=taboo_routes,
        top_k=top_seed_packs,
    )
    debate_turns = _build_frontier_debate(
        claims,
        current_frontier=effort_report.current_frontier,
        current_work_packages=tuple(item.title for item in current_work_packages),
        taboo_routes=taboo_routes,
        seed_packs=seed_packs,
    )
    warnings = _build_warnings(claim_docs, oasis_dbs, claims, seed_packs)
    report = ExternalFrontierReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        baseline_orchestrator_id=context.baseline.orchestrator_id,
        klein_orchestrator_id=context.klein.orchestrator_id,
        current_frontier=effort_report.current_frontier,
        current_work_packages=tuple(item.title for item in current_work_packages),
        taboo_routes=taboo_routes,
        external_claims=claims,
        debate_turns=debate_turns,
        seed_packs=seed_packs,
        warnings=warnings,
        evidence_refs=_dedupe(
            (
                context.baseline.summary_path,
                context.klein.summary_path,
                *(str(Path(path).resolve()) for path in claim_docs),
                *(str(Path(path).resolve()) for path in oasis_dbs),
                *effort_report.evidence_refs,
            )
        ),
    )
    if output_dir is None:
        return report, None
    return report, write_external_frontier_outputs(report, output_dir)


def write_external_frontier_outputs(
    report: ExternalFrontierReport,
    output_dir: str | Path,
) -> dict[str, str]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    claims_path = target / "external_claims.json"
    debate_path = target / "frontier_debate.json"
    seed_pack_path = target / "orchestrator_seed_pack.json"
    report_path = target / "external_frontier_report.md"

    _write_json(
        claims_path,
        {
            "generated_at": report.generated_at,
            "current_frontier": list(report.current_frontier),
            "taboo_routes": list(report.taboo_routes),
            "external_claims": [item.to_dict() for item in report.external_claims],
        },
    )
    _write_json(
        debate_path,
        {
            "generated_at": report.generated_at,
            "debate": [item.to_dict() for item in report.debate_turns],
        },
    )
    _write_json(
        seed_pack_path,
        {
            "generated_at": report.generated_at,
            "seed_packs": [item.to_dict() for item in report.seed_packs],
        },
    )
    report_path.write_text(render_external_frontier_markdown(report), encoding="utf-8")
    return {
        "claims": str(claims_path),
        "debate": str(debate_path),
        "seed_pack": str(seed_pack_path),
        "report": str(report_path),
    }


def render_external_frontier_markdown(report: ExternalFrontierReport) -> str:
    lines = [
        "# Timeguard External Frontier Report",
        "",
        f"Generated: {report.generated_at}",
        "",
        "## Current Posture",
        "",
        f"- Baseline orchestrator: {report.baseline_orchestrator_id}",
        f"- Klein orchestrator: {report.klein_orchestrator_id}",
        "- Current frontier:",
        *[f"  - {item}" for item in report.current_frontier],
        "- Current work packages:",
        *[f"  - {item}" for item in report.current_work_packages],
        "",
        "## What To Avoid",
        "",
        *[f"- {item}" for item in report.taboo_routes],
        "",
        "## External Claims",
        "",
    ]
    for claim in report.external_claims:
        lines.extend(
            [
                f"### {claim.claim_id}",
                "",
                f"- Source: [{claim.source_title}]({claim.source_locator})",
                f"- Source kind: {claim.source_kind} ({claim.source_tier})",
                f"- Status: {claim.status}",
                f"- Route family: {claim.route_family}",
                f"- Map relation: {claim.map_relation}",
                f"- Target orchestrator: {claim.target_orchestrator or 'none'}",
                f"- Proof object: {claim.proof_object or 'none'}",
                f"- Claim: {claim.claim_text}",
                "- Reasons:",
                *[f"  - {item}" for item in claim.reasons],
                "",
            ]
        )

    lines.extend(["## Synthetic Debate", ""])
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
        if turn.cautions:
            lines.extend(["- Cautions:", *[f"  - {item}" for item in turn.cautions]])
        lines.extend(
            [
                f"- Verdict: {turn.verdict}",
                "",
            ]
        )

    lines.extend(["## Seed Packs", ""])
    for pack in report.seed_packs:
        lines.extend(
            [
                f"### {pack.name}",
                "",
                f"- Target orchestrator: {pack.target_orchestrator}",
                f"- Route family: {pack.route_family}",
                f"- Proof object: {pack.proof_object}",
                f"- Confidence: {pack.confidence:.2f}",
                f"- Description: {pack.description}",
                "- Claim ids:",
                *[f"  - {item}" for item in pack.claim_ids],
                "- Seeds:",
                *[f"  - {item}" for item in pack.seeds],
                "- Prompt:",
                "",
                "```text",
                pack.prompt,
                "```",
                "",
            ]
        )

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def _load_and_evaluate_claims(
    *,
    claim_docs: tuple[str | Path, ...],
    oasis_dbs: tuple[str | Path, ...],
    baseline_id: str,
    klein_id: str,
    current_frontier: tuple[str, ...],
    taboo_routes: tuple[str, ...],
) -> tuple[ExternalClaim, ...]:
    raw_claims: list[dict[str, str]] = []
    for locator in claim_docs:
        raw_claims.extend(_load_claim_doc(Path(locator).resolve()))
    raw_claims.extend(load_oasis_claim_rows(oasis_dbs))
    claims: list[ExternalClaim] = []
    seen_text: set[str] = set()
    for item in raw_claims:
        normalized_text = _normalize_space(item["claim_text"]).lower()
        if normalized_text in seen_text:
            continue
        seen_text.add(normalized_text)
        route_family = _classify_route_family(normalized_text)
        source_kind = item["source_kind"]
        source_tier = _source_tier(source_kind, item["source_locator"])
        status, map_relation = _classify_status(route_family, normalized_text, source_tier)
        target_orchestrator = _target_orchestrator(
            route_family,
            claim_text=normalized_text,
            baseline_id=baseline_id,
            klein_id=klein_id,
        )
        claim = ExternalClaim(
            claim_id=_claim_id(item["source_title"], normalized_text),
            source_locator=item["source_locator"],
            source_title=item["source_title"],
            source_kind=source_kind,
            source_tier=source_tier,
            claim_text=item["claim_text"],
            route_family=route_family,
            proof_object=_proof_object(route_family),
            map_relation=map_relation,
            status=status,
            target_orchestrator=target_orchestrator,
            reasons=_claim_reasons(
                route_family,
                status=status,
                source_kind=source_kind,
                source_tier=source_tier,
                current_frontier=current_frontier,
                taboo_routes=taboo_routes,
            ),
            evidence_refs=(item["source_locator"],),
            confidence=_claim_confidence(route_family, status=status, source_tier=source_tier),
        )
        claims.append(claim)
    claims.sort(
        key=lambda item: (
            -_STATUS_PRIORITY.get(item.status, 0.0),
            -_ROUTE_PRIORITY.get(item.route_family, 0.0),
            -item.confidence,
            item.claim_id,
        )
    )
    return tuple(claims)


def _load_claim_doc(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text())
        return _load_json_claims(path, payload)
    text = path.read_text(encoding="utf-8")
    title = _doc_title(path, text)
    source_kind = _infer_source_kind(f"{title} {path}")
    source_locator = _first_url(text) or str(path)
    claims = _extract_markdown_claims(text)
    return [
        {
            "source_locator": source_locator,
            "source_title": title,
            "source_kind": source_kind,
            "claim_text": claim_text,
        }
        for claim_text in claims
    ]


def _load_json_claims(path: Path, payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, dict) and isinstance(payload.get("claims"), list):
        items = payload["claims"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [payload]
    else:
        items = []
    claims: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        claim_text = _normalize_space(
            str(item.get("claim") or item.get("text") or item.get("idea") or "")
        )
        if not claim_text:
            continue
        title = _normalize_space(str(item.get("title") or path.stem or f"claim-{index + 1}"))
        source_locator = _normalize_space(
            str(item.get("url") or item.get("source") or item.get("locator") or path)
        )
        source_kind = _infer_source_kind(
            " ".join(
                (
                    str(item.get("source_kind") or ""),
                    source_locator,
                    title,
                )
            )
        )
        claims.append(
            {
                "source_locator": source_locator,
                "source_title": title,
                "source_kind": source_kind,
                "claim_text": claim_text,
            }
        )
    return claims


def _extract_markdown_claims(text: str) -> list[str]:
    claims: list[str] = []
    for line in text.splitlines():
        match = _BULLET_PATTERN.match(line)
        if not match:
            continue
        candidate = _normalize_space(match.group(1))
        if len(candidate) >= 24:
            claims.append(candidate)
    if claims:
        return claims
    paragraphs = [
        _normalize_space(chunk)
        for chunk in text.split("\n\n")
        if _normalize_space(chunk) and not chunk.lstrip().startswith("#")
    ]
    return [item for item in paragraphs if len(item) >= 40]


def _doc_title(path: Path, text: str) -> str:
    match = _HEADING_PATTERN.search(text)
    if match:
        return _normalize_space(match.group(1))
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _first_url(text: str) -> str | None:
    match = _URL_PATTERN.search(text)
    if not match:
        return None
    return match.group(0)


def _infer_source_kind(value: str) -> str:
    lowered = value.lower()
    if "reddit" in lowered:
        return "reddit"
    if "mathoverflow" in lowered or "math overflow" in lowered:
        return "mathoverflow"
    if "arxiv" in lowered or "journal" in lowered or "paper" in lowered or "doi" in lowered:
        return "paper"
    if "blog" in lowered or "substack" in lowered:
        return "blog"
    if "forum" in lowered or "thread" in lowered:
        return "forum"
    return "note"


def _source_tier(source_kind: str, source_locator: str) -> str:
    locator = source_locator.lower()
    if source_kind.startswith("oasis_"):
        return "synthetic"
    if source_kind in {"paper", "mathoverflow"}:
        return "high"
    if source_kind in {"blog", "forum"}:
        return "medium"
    if source_kind == "reddit" or "reddit.com" in locator:
        return "low"
    return "medium"


def _classify_route_family(text: str) -> str:
    if any(token in text for token in ("weil-guinand", "weil", "guinand", "zero-sum", "zero sum", "prime-kernel", "prime kernel", "explicit formula", "zero-density", "zero density")):
        return "explicit_formula"
    if any(token in text for token in ("trace-class", "trace class", "self-adjoint", "self adjoint", "hilbert-pólya", "hilbert-polya", "toeplitz", "transfer operator", "operator")):
        return "operator"
    if any(token in text for token in ("functional equation", "self-dual", "self dual", "symmetrisation", "symmetrization", "pole locus", "involution", "möbius", "mobius")):
        return "symmetrisation"
    if any(token in text for token in ("tail control", "window-escape", "window escape", "error term", "explicit-formula tail")):
        return "tail_control"
    if any(token in text for token in ("padé", "pade", "hankel", "prony", "finite-data", "finite data", "rational reconstruction")):
        return "finite_data"
    if any(token in text for token in ("g9", "g-equivalent", "g equivalent", "winding number", "equivalent reformulation")):
        return "equivalence_search"
    if any(token in text for token in ("audit", "compare", "survey", "synthesize", "synthesise", "map", "frontier")):
        return "meta_research"
    return "unclear"


def _classify_status(route_family: str, text: str, source_tier: str) -> tuple[str, str]:
    if route_family == "finite_data":
        return "avoid", "duplicates_closed_route"
    if route_family == "equivalence_search":
        return "avoid", "equivalence_replay"
    if route_family in {"explicit_formula", "operator", "symmetrisation", "tail_control"}:
        if source_tier == "low":
            return "needs_formalization", "aligned_with_frontier"
        return "promote", "aligned_with_frontier"
    if route_family == "meta_research":
        return "meta_only", "frontier_audit"
    if "all coefficients at once" in text or "infinite-data" in text or "infinite data" in text:
        return "needs_formalization", "aligned_with_frontier"
    return "needs_formalization", "unclear_frontier_fit"


def _target_orchestrator(route_family: str, *, claim_text: str, baseline_id: str, klein_id: str) -> str:
    if route_family == "tail_control":
        return baseline_id
    if route_family == "explicit_formula" and any(token in claim_text for token in ("tail control", "error term", "window-escape", "window escape")):
        return baseline_id
    if route_family in {"explicit_formula", "operator", "symmetrisation"}:
        return klein_id
    if route_family == "meta_research":
        return "both"
    return klein_id


def _proof_object(route_family: str) -> str:
    return {
        "operator": "A trace-class or self-adjoint certificate that excludes off-line zeros without recycling an RH-equivalent positivity condition.",
        "explicit_formula": "A Weil-Guinand or prime-kernel zero-sum exclusion certificate with unconditional tail control.",
        "symmetrisation": "A self-dual functional-equation certificate for the pole locus of G(w) that does not collapse into another G-equivalent restatement.",
        "tail_control": "An explicit-formula tail and window-escape certificate that upgrades bounded checks into a reusable global exclusion step.",
        "meta_research": "A frontier audit identifying exactly which routes remain non-duplicate before another expensive orchestrator run.",
        "equivalence_search": "A genuinely non-equivalent reformulation, not another G1-G8 replay.",
    }.get(route_family, "A concrete proof object is still missing.")


def _claim_reasons(
    route_family: str,
    *,
    status: str,
    source_kind: str,
    source_tier: str,
    current_frontier: tuple[str, ...],
    taboo_routes: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = []
    if status == "avoid":
        reasons.append("This idea re-enters a route class that the current map already closed or downgraded.")
    elif status == "promote":
        reasons.append("This idea hits the current frontier instead of replaying a known dead branch.")
    elif status == "needs_formalization":
        reasons.append("The route class is still live, but the claim needs a precise proof object before it should drive a run.")
    else:
        reasons.append("This claim is useful for auditing the frontier, not as a direct orchestrator seed.")
    if route_family == "finite_data":
        reasons.append("AY already closed finite-data Padé/Hankel reconstruction as precision-equivalent to the existing wall.")
    if route_family == "equivalence_search":
        reasons.append("AV already says generic equivalent reformulations and G-style restatements collapse back into the RH-equivalence wall.")
    if route_family in {"explicit_formula", "operator", "symmetrisation"} and current_frontier:
        reasons.append(f"Current frontier anchor: {current_frontier[0]}")
    if source_tier == "low":
        reasons.append(f"Source tier is {source_tier} ({source_kind}), so this should be treated as idea-harvest only.")
    if source_tier == "synthetic":
        reasons.append("This came from an OASIS simulation, so it should be treated as synthetic hypothesis generation rather than external mathematical evidence.")
    if taboo_routes:
        reasons.append(f"Do not regress into taboo routes such as: {taboo_routes[0]}")
    return tuple(reasons)


def _claim_confidence(route_family: str, *, status: str, source_tier: str) -> float:
    tier_weight = {"high": 0.85, "medium": 0.70, "synthetic": 0.60, "low": 0.50}.get(source_tier, 0.60)
    return min(
        0.95,
        tier_weight
        * _STATUS_PRIORITY.get(status, 0.50)
        * (0.70 + 0.30 * _ROUTE_PRIORITY.get(route_family, 0.20)),
    )


def _build_seed_packs(
    claims: tuple[ExternalClaim, ...],
    *,
    support_docs: tuple[str | Path, ...],
    current_frontier: tuple[str, ...],
    current_work_packages: tuple[str, ...],
    taboo_routes: tuple[str, ...],
    top_k: int,
) -> tuple[OrchestratorSeedPack, ...]:
    groups: dict[tuple[str, str], list[ExternalClaim]] = {}
    for claim in claims:
        if claim.status not in {"promote", "needs_formalization"}:
            continue
        key = (claim.route_family, claim.target_orchestrator or "klein")
        groups.setdefault(key, []).append(claim)
    ranked_groups = sorted(
        groups.items(),
        key=lambda item: (
            -_group_score(item[1]),
            item[0][0],
            item[0][1],
        ),
    )
    seed_packs: list[OrchestratorSeedPack] = []
    support_seed_refs = _support_seed_refs(support_docs)
    for (route_family, target_orchestrator), group in ranked_groups[:top_k]:
        group.sort(key=lambda item: (-item.confidence, item.claim_id))
        claim_ids = tuple(item.claim_id for item in group)
        locators = _dedupe((*support_seed_refs, *(item.source_locator for item in group)))
        bibliography = tuple(
            {
                "family": route_family,
                "title": item.source_title,
                "locator": item.source_locator,
                "note": item.claim_text,
                "source_kind": item.source_kind,
                "source_tier": item.source_tier,
            }
            for item in group
        )
        pack_name = _seed_pack_name(route_family, target_orchestrator)
        prompt = _build_seed_prompt(
            route_family=route_family,
            target_orchestrator=target_orchestrator,
            current_frontier=current_frontier,
            current_work_packages=current_work_packages,
            taboo_routes=taboo_routes,
            claims=group,
        )
        seed_packs.append(
            OrchestratorSeedPack(
                name=pack_name,
                description=(
                    f"External frontier pack for {route_family.replace('_', ' ')} work after the current RH map closed the duplicate routes."
                ),
                target_orchestrator=target_orchestrator,
                route_family=route_family,
                proof_object=_proof_object(route_family),
                claim_ids=claim_ids,
                taboo_routes=taboo_routes,
                seeds=locators,
                allowlisted_domains=_dedupe(*(tuple(_claim_domains(item)) for item in group)),
                bibliography=bibliography,
                prompt=prompt,
                rationale=_seed_pack_rationale(group, current_frontier=current_frontier),
                evidence_refs=_dedupe(*(item.evidence_refs for item in group)),
                confidence=_group_confidence(group),
            )
        )
    return tuple(seed_packs)


def _group_score(group: list[ExternalClaim]) -> float:
    best = max(item.confidence for item in group)
    avg = sum(item.confidence for item in group) / len(group)
    route = _ROUTE_PRIORITY.get(group[0].route_family, 0.20)
    return 0.60 * best + 0.25 * avg + 0.15 * route


def _group_confidence(group: list[ExternalClaim]) -> float:
    return min(0.95, sum(item.confidence for item in group) / max(1, len(group)) + 0.05)


def _support_seed_refs(support_docs: tuple[str | Path, ...]) -> tuple[str, ...]:
    preferred_tokens = ("phase ay", "phase av", "klein orchestrator plan", "campaign synthesis")
    ordered: list[str] = []
    for locator in support_docs:
        value = str(Path(locator).resolve())
        normalized = value.lower().replace("-", " ").replace("_", " ")
        if any(token in normalized for token in preferred_tokens):
            ordered.append(value)
    if ordered:
        return tuple(ordered[:4])
    return tuple(str(Path(locator).resolve()) for locator in support_docs[:4])


def _claim_domains(claim: ExternalClaim) -> tuple[str, ...]:
    parsed = urlparse(claim.source_locator)
    if parsed.scheme and parsed.netloc:
        domain = parsed.netloc.lower()
        return (domain, f"www.{domain}" if not domain.startswith("www.") else domain)
    if claim.source_kind == "reddit":
        return ("reddit.com", "www.reddit.com")
    if claim.source_kind == "mathoverflow":
        return ("mathoverflow.net", "www.mathoverflow.net")
    return ()


def _seed_pack_name(route_family: str, target_orchestrator: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", route_family.lower()).strip("-")
    orchestrator_slug = re.sub(r"[^a-z0-9]+", "-", target_orchestrator.lower()).strip("-")
    return f"rh-external-{slug}-{orchestrator_slug}"


def _build_seed_prompt(
    *,
    route_family: str,
    target_orchestrator: str,
    current_frontier: tuple[str, ...],
    current_work_packages: tuple[str, ...],
    taboo_routes: tuple[str, ...],
    claims: list[ExternalClaim],
) -> str:
    what_has_been_done = _dedupe(
        (
            "The current campaign map already closed finite-data Padé/Hankel reconstruction and generic equivalent-reformulation loops.",
            *(item for item in current_frontier[:2]),
            *(item for item in current_work_packages[:2]),
        )
    )
    what_remains = _dedupe(
        (
            f"Run a {route_family.replace('_', ' ')} branch that produces: {_proof_object(route_family)}",
            "The new run must state why it is not another RH-equivalent replay or bounded local validation sweep.",
        )
    )
    claim_lines = [f"- {item.claim_text} [{item.source_kind}/{item.source_tier}]" for item in claims[:4]]
    return "\n".join(
        [
            f"Target orchestrator: {target_orchestrator}",
            f"Route family: {route_family}",
            "",
            "What has been done:",
            *[f"- {item}" for item in what_has_been_done],
            "",
            "What remains:",
            *[f"- {item}" for item in what_remains],
            "",
            "What to avoid:",
            *[f"- {item}" for item in taboo_routes],
            "",
            "External claim synthesis:",
            *claim_lines,
            "",
            "Required output:",
            f"- Produce a concrete proof object: {_proof_object(route_family)}",
            "- Name the exact obstruction it reduces.",
            "- State why the route is not another finite-data or equivalence-wall replay.",
        ]
    )


def _seed_pack_rationale(
    claims: list[ExternalClaim],
    *,
    current_frontier: tuple[str, ...],
) -> str:
    claim_text = "; ".join(item.claim_text for item in claims[:2])
    frontier_hint = current_frontier[0] if current_frontier else "No frontier label available."
    return (
        "This pack groups externally harvested claims that still align with the current RH frontier after route filtering. "
        + f"Frontier anchor: {frontier_hint} "
        + f"Representative claim synthesis: {claim_text}"
    )


def _build_frontier_debate(
    claims: tuple[ExternalClaim, ...],
    *,
    current_frontier: tuple[str, ...],
    current_work_packages: tuple[str, ...],
    taboo_routes: tuple[str, ...],
    seed_packs: tuple[OrchestratorSeedPack, ...],
) -> tuple[FrontierDebateTurn, ...]:
    promoted = tuple(item for item in claims if item.status in {"promote", "needs_formalization"})
    avoided = tuple(item for item in claims if item.status == "avoid")
    return (
        FrontierDebateTurn(
            role="Harvester",
            focus="What new external material adds beyond the current local RH map",
            findings=tuple(
                f"{item.claim_id}: {item.claim_text}"
                for item in promoted[:5]
            ),
            cautions=("External claims are ideas, not proof evidence.",),
            verdict=(
                "External harvesting is useful only when it proposes a route that survives duplicate-route filtering and names a proof object."
            ),
            evidence_refs=tuple(item.source_locator for item in promoted[:5]),
            confidence=0.74,
        ),
        FrontierDebateTurn(
            role="Cartographer",
            focus="Map external claims onto current frontier and closed-route taxonomy",
            findings=current_frontier[:4] + current_work_packages[:2],
            cautions=tuple(f"Avoid: {item}" for item in taboo_routes[:4]),
            verdict=(
                "The complete map should now act as a hard negative prior: new ideas must explain why they are not just finite-data, equivalence-wall, or same-lane replay."
            ),
            evidence_refs=tuple(item.source_locator for item in claims[:4]),
            confidence=0.82,
        ),
        FrontierDebateTurn(
            role="Skeptic",
            focus="Reject weak or duplicate online angles",
            findings=tuple(
                f"{item.claim_id}: {item.claim_text}"
                for item in avoided[:4]
            ),
            cautions=(
                "Low-tier sources should only seed hypotheses, never upgrade confidence by themselves.",
                "Do not let agents mutate the proof standard or self-reward on internal scores.",
            ),
            verdict=(
                "Most wasted cycles come from reopening routes that the map already closed. The skeptic's job is to stop that before another orchestrator run starts."
            ),
            evidence_refs=tuple(item.source_locator for item in avoided[:4]),
            confidence=0.86,
        ),
        FrontierDebateTurn(
            role="SeedBuilder",
            focus="Convert surviving external angles into orchestrator-ready seed packs",
            findings=tuple(pack.name for pack in seed_packs),
            cautions=tuple(f"Taboo: {item}" for item in taboo_routes[:3]),
            verdict=(
                "Only claims that survive route filtering and define a proof object should be converted into seed packs. Everything else belongs in audit notes."
            ),
            evidence_refs=tuple(ref for pack in seed_packs for ref in pack.evidence_refs),
            confidence=0.79,
        ),
        FrontierDebateTurn(
            role="Moderator",
            focus="Final posture for the next orchestrator cycle",
            findings=tuple(pack.name for pack in seed_packs[:3]),
            cautions=tuple(f"Watchpoint: {item}" for item in taboo_routes[:3]),
            verdict=(
                "Use the complete map as a constraint engine, not as a proof claim. Harvest external debate for angles, screen them hard, then run only the surviving seed packs."
            ),
            evidence_refs=tuple(ref for pack in seed_packs for ref in pack.evidence_refs),
            confidence=0.84,
        ),
    )


def _build_taboo_routes(context: Any, effort_report: Any) -> tuple[str, ...]:
    taboo = [
        "Reopen Padé/Hankel/Prony finite-data reconstruction as if AY had not already closed it.",
        "Spend another round on generic G-equivalent or winding-number restatements that collapse back into the AV equivalence wall.",
        "Run same-lane novelty sweeps without a new proof object or exclusion-grade artifact.",
        "Treat low-trust online discussion as evidence rather than as idea-harvest.",
    ]
    if context.baseline.repeated_failures.get("finite_window_only", 0):
        taboo.append("Recycle baseline finite-window-only tail-control loops without a window-escape certificate.")
    if any("same-lane" in failure or "same_lane" in failure for failure in effort_report.dominant_failures):
        taboo.append("Allow Klein same-lane loops to masquerade as structural novelty.")
    return tuple(taboo)


def _build_warnings(
    claim_docs: tuple[str | Path, ...],
    oasis_dbs: tuple[str | Path, ...],
    claims: tuple[ExternalClaim, ...],
    seed_packs: tuple[OrchestratorSeedPack, ...],
) -> tuple[str, ...]:
    warnings = []
    if not claim_docs and not oasis_dbs:
        warnings.append("No external claim docs or OASIS databases were supplied, so the frontier lane cannot contribute new angles yet.")
    elif not claim_docs:
        warnings.append("No external claim docs were supplied.")
    if claims and all(item.status == "avoid" for item in claims):
        warnings.append("All harvested claims collapsed into closed or low-value routes.")
    low_tier_count = sum(1 for item in claims if item.source_tier == "low")
    if claims and low_tier_count >= max(1, len(claims) // 2):
        warnings.append("Low-tier sources dominate the harvest, so any surviving angle should be treated as hypothesis generation only.")
    synthetic_count = sum(1 for item in claims if item.source_tier == "synthetic")
    if claims and synthetic_count >= max(1, len(claims) // 2):
        warnings.append("Synthetic OASIS claims dominate the harvest, so the result should be used as a simulation-driven idea filter rather than as evidence.")
    if not seed_packs:
        warnings.append("No orchestrator-ready seed pack survived screening.")
    return tuple(warnings)


def _claim_id(source_title: str, claim_text: str) -> str:
    digest = hashlib.sha1(f"{source_title}|{claim_text}".encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", source_title.lower()).strip("-") or "claim"
    return f"{slug}-{digest}"


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _dedupe(*value_sets: tuple[str, ...] | list[str] | str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for values in value_sets:
        if isinstance(values, str):
            iterable = (values,)
        else:
            iterable = values
        for value in iterable:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)
