"""Promote reviewed Timeguard frontier packs into real RH orchestrator runs."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from riemann.research.config import RESEARCH_DIR, RiemannResearchConfig
from riemann.research.orchestrator import run_campaign
from riemann.research.seed_pack import resolve_seed_inputs

from src.oae.studios.timeguard.oasis_adapter import load_oasis_claim_rows
from src.oae.studios.timeguard.schemas import ExternalSeedPackLaunchReport, OrchestratorSeedPack

_ROUTE_BASE_PACKS = {
    "operator": ("rh-spectral",),
    "symmetrisation": ("rh-spectral",),
    "explicit_formula": ("rh-classical",),
    "tail_control": ("rh-classical",),
    "finite_data": ("rh-classical",),
    "meta_research": ("rh-proof-attempts",),
    "equivalence_search": ("rh-proof-attempts", "rh-core"),
    "unclear": ("rh-core",),
}

_ROUTE_ALIGNMENT = {
    "operator": "quantum_spectral",
    "symmetrisation": "xi_function",
    "explicit_formula": "explicit_formula",
    "tail_control": "explicit_formula",
    "finite_data": "xi_function",
    "meta_research": "general_analytic",
    "equivalence_search": "xi_function",
    "unclear": "general_analytic",
}

_ROUTE_PRIMER = {
    "operator": (
        "Self-adjoint spectral operators, trace-class certificates, Hilbert-Polya structure, "
        "and off-line zero exclusion should stay central in this run."
    ),
    "symmetrisation": (
        "Functional-equation symmetrisation, xi-function structure, self-dual transforms, "
        "and entire-function constraints should stay central in this run."
    ),
    "explicit_formula": (
        "The explicit formula, Weil-Guinand zero sums, prime-kernel identities, tail control, "
        "and off-line zero exclusion should stay central in this run."
    ),
    "tail_control": (
        "Tail bounds, window-escape certificates, explicit-formula remainder control, "
        "and prime oscillation consistency should stay central in this run."
    ),
}


def run_external_seed_pack_launch(
    *,
    seed_pack_file: str | Path,
    output_dir: str | Path,
    pack_name: str | None = None,
    pack_index: int = 1,
    campaign_id: str | None = None,
    research_root: str | Path | None = None,
    base_seed_packs: tuple[str, ...] | None = None,
    max_sources: int = 64,
    max_rounds: int = 3,
    max_hypotheses_per_round: int = 6,
    max_worker_runs_per_round: int = 12,
    patience: int = 2,
    proof_target: float = 0.92,
    verbose: bool = False,
) -> tuple[ExternalSeedPackLaunchReport, dict[str, str]]:
    source_path = Path(seed_pack_file).resolve()
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    selected = _select_seed_pack(
        payload.get("seed_packs", ()),
        pack_name=pack_name,
        pack_index=pack_index,
    )
    pack = _coerce_seed_pack(selected)
    launch_root = Path(output_dir).resolve()
    launch_root.mkdir(parents=True, exist_ok=True)
    materialized_dir = launch_root / "materialized_seeds"
    materialized_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    adjacent_context = _adjacent_context_docs(source_path)
    generated_briefing = _write_frontier_briefing(
        materialized_dir / "frontier_briefing.md",
        pack=pack,
        adjacent_context=adjacent_context,
    )
    generated_bibliography = _write_bibliography_note(
        materialized_dir / "frontier_bibliography.md",
        pack=pack,
    )
    generated_taboos = _write_taboo_note(
        materialized_dir / "frontier_taboos.md",
        pack=pack,
    )
    generated_primer = _write_route_family_primer(
        materialized_dir / "route_family_primer.md",
        pack=pack,
    )

    materialized_seeds: list[str] = [
        str(generated_briefing),
        str(generated_bibliography),
        str(generated_taboos),
        str(generated_primer),
    ]
    direct_seeds: list[str] = [str(path) for path in adjacent_context]
    oas_lookup = _build_oasis_lookup(pack.seeds, pack.bibliography)

    for locator in pack.seeds:
        if _looks_like_oasis_locator(locator):
            note_path = _materialize_oasis_locator(
                locator,
                oas_lookup,
                pack=pack,
                target_dir=materialized_dir,
            )
            if note_path is None:
                warnings.append(f"Could not materialize OASIS locator: {locator}")
                continue
            materialized_seeds.append(str(note_path))
            continue
        if _is_existing_local_path(locator):
            direct_seeds.append(str(Path(locator).resolve()))
            continue
        if _is_supported_remote_locator(locator):
            direct_seeds.append(locator)
            continue
        warnings.append(f"Skipped unresolved seed locator: {locator}")

    chosen_base_packs = base_seed_packs or _ROUTE_BASE_PACKS.get(pack.route_family, ("rh-core",))
    seeds, allowlisted_domains, resolved_manifest = resolve_seed_inputs(
        tuple(chosen_base_packs),
        extra_seeds=tuple(_dedupe((*direct_seeds, *materialized_seeds))),
        extra_domains=pack.allowlisted_domains,
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    actual_campaign_id = campaign_id or _default_campaign_id(pack.name)
    actual_research_root = Path(research_root).resolve() if research_root is not None else RESEARCH_DIR
    topology_mode = _infer_topology_mode(pack.target_orchestrator)
    cfg = RiemannResearchConfig(
        campaign_id=actual_campaign_id,
        research_root=actual_research_root,
        seed_pack_names=tuple(chosen_base_packs),
        crawl_seeds=seeds,
        allowlisted_domains=allowlisted_domains,
        max_sources=max_sources,
        max_rounds=max_rounds,
        max_hypotheses_per_round=max_hypotheses_per_round,
        max_worker_runs_per_round=max_worker_runs_per_round,
        patience=patience,
        proof_target=proof_target,
        topology_mode=topology_mode,
        preferred_route_family=pack.route_family,
        route_lock_strict=True,
    )
    summary = run_campaign(cfg, verbose=verbose)

    materialized_pack_path = launch_root / "materialized_seed_pack.json"
    launch_manifest_path = launch_root / "external_seed_launch_manifest.json"
    launch_report_path = launch_root / "external_seed_launch_report.md"

    materialized_pack_payload = {
        "name": f"{pack.name}-materialized",
        "description": (
            "Materialized external frontier pack converted into local markdown seeds "
            "for direct RH orchestrator ingestion."
        ),
        "allowlisted_domains": list(allowlisted_domains),
        "seeds": list(_dedupe((*direct_seeds, *materialized_seeds))),
        "bibliography": list(pack.bibliography),
    }
    _write_json(materialized_pack_path, materialized_pack_payload)
    manifest_payload = {
        "generated_at": generated_at,
        "source_seed_pack_file": str(source_path),
        "selected_pack": pack.to_dict(),
        "base_seed_packs": list(chosen_base_packs),
        "topology_mode": topology_mode,
        "preferred_route_family": pack.route_family,
        "route_lock_strict": True,
        "campaign_id": actual_campaign_id,
        "campaign_dir": str(cfg.campaign_dir),
        "summary_path": str(cfg.summary_path),
        "materialized_seed_paths": materialized_seeds,
        "direct_seed_paths": direct_seeds,
        "effective_seed_manifest": resolved_manifest,
        "warnings": warnings,
    }
    _write_json(launch_manifest_path, manifest_payload)

    report = ExternalSeedPackLaunchReport(
        generated_at=generated_at,
        source_seed_pack_file=str(source_path),
        selected_pack_name=pack.name,
        campaign_id=actual_campaign_id,
        topology_mode=topology_mode,
        base_seed_packs=tuple(chosen_base_packs),
        materialized_seed_paths=tuple(materialized_seeds),
        direct_seed_paths=tuple(direct_seeds),
        launch_bundle_dir=str(launch_root),
        campaign_dir=str(cfg.campaign_dir),
        summary_path=str(cfg.summary_path),
        best_score=float(summary.get("best_score", 0.0) or 0.0),
        converged=bool(summary.get("converged", False)),
        warnings=tuple(warnings),
        evidence_refs=_dedupe(
            (
                str(source_path),
                *pack.evidence_refs,
                *tuple(adjacent_context),
                *materialized_seeds,
                str(cfg.summary_path),
            )
        ),
    )
    launch_report_path.write_text(
        render_external_seed_launch_markdown(report, pack=pack, summary=summary),
        encoding="utf-8",
    )
    outputs = {
        "launch_manifest": str(launch_manifest_path),
        "materialized_pack": str(materialized_pack_path),
        "launch_report": str(launch_report_path),
        "summary": str(cfg.summary_path),
        "campaign_dir": str(cfg.campaign_dir),
    }
    return report, outputs


def render_external_seed_launch_markdown(
    report: ExternalSeedPackLaunchReport,
    *,
    pack: OrchestratorSeedPack,
    summary: dict[str, Any],
) -> str:
    lines = [
        "# Timeguard External Seed Launch",
        "",
        f"Generated: {report.generated_at}",
        "",
        "## Selected Pack",
        "",
        f"- Name: {pack.name}",
        f"- Target orchestrator: {pack.target_orchestrator}",
        f"- Route family: {pack.route_family}",
        f"- Proof object: {pack.proof_object}",
        f"- Confidence: {pack.confidence:.3f}",
        "",
        "## Launch Configuration",
        "",
        f"- Campaign id: {report.campaign_id}",
        f"- Topology mode: {report.topology_mode}",
        f"- Preferred route family: {pack.route_family}",
        f"- Base seed packs: {', '.join(report.base_seed_packs) if report.base_seed_packs else 'none'}",
        f"- Materialized seeds: {len(report.materialized_seed_paths)}",
        f"- Direct seeds: {len(report.direct_seed_paths)}",
        "",
        "## Campaign Result",
        "",
        f"- Best score: {report.best_score:.4f}",
        f"- Converged: {report.converged}",
        f"- Rounds run: {summary.get('rounds_run', 0)}",
        f"- Best candidate: {summary.get('best_candidate_id') or 'n/a'}",
        f"- Summary: {report.summary_path}",
        "",
        "## Why This Run Exists",
        "",
        f"- {pack.rationale}",
        "- This launch converts synthetic reviewed claims into concrete markdown seeds, but the synthetic claims remain idea-harvest rather than mathematical evidence.",
        "",
        "## Taboo Routes",
        "",
        *[f"- {item}" for item in pack.taboo_routes],
        "",
    ]
    if report.warnings:
        lines.extend(["## Warnings", "", *[f"- {item}" for item in report.warnings], ""])
    return "\n".join(lines).rstrip() + "\n"


def _select_seed_pack(
    raw_seed_packs: Any,
    *,
    pack_name: str | None,
    pack_index: int,
) -> dict[str, Any]:
    if not isinstance(raw_seed_packs, list) or not raw_seed_packs:
        raise ValueError("No seed packs were found in the supplied external frontier bundle.")
    if pack_name:
        for item in raw_seed_packs:
            if str(item.get("name", "")) == pack_name:
                return item
        raise ValueError(f"Unknown external seed pack: {pack_name}")
    index = max(1, pack_index) - 1
    if index >= len(raw_seed_packs):
        raise ValueError(f"Seed pack index {pack_index} is out of range for {len(raw_seed_packs)} packs.")
    return raw_seed_packs[index]


def _coerce_seed_pack(payload: dict[str, Any]) -> OrchestratorSeedPack:
    return OrchestratorSeedPack(
        name=str(payload.get("name", "")),
        description=str(payload.get("description", "")),
        target_orchestrator=str(payload.get("target_orchestrator", "")),
        route_family=str(payload.get("route_family", "unclear")),
        proof_object=str(payload.get("proof_object", "")),
        claim_ids=tuple(str(item) for item in payload.get("claim_ids", ())),
        taboo_routes=tuple(str(item) for item in payload.get("taboo_routes", ())),
        seeds=tuple(str(item) for item in payload.get("seeds", ())),
        allowlisted_domains=tuple(str(item) for item in payload.get("allowlisted_domains", ())),
        bibliography=tuple(dict(item) for item in payload.get("bibliography", ())),
        prompt=str(payload.get("prompt", "")),
        rationale=str(payload.get("rationale", "")),
        evidence_refs=tuple(str(item) for item in payload.get("evidence_refs", ())),
        confidence=float(payload.get("confidence", 0.0) or 0.0),
    )


def _adjacent_context_docs(seed_pack_file: Path) -> tuple[str, ...]:
    candidates = (
        seed_pack_file.parent / "external_frontier_report.md",
    )
    return tuple(str(path.resolve()) for path in candidates if path.exists())


def _write_frontier_briefing(
    path: Path,
    *,
    pack: OrchestratorSeedPack,
    adjacent_context: tuple[str, ...],
) -> Path:
    alignment = _ROUTE_ALIGNMENT.get(pack.route_family, "general_analytic")
    lines = [
        "# Frontier Launch Briefing",
        "",
        f"Orchestrator family alignment: {alignment}",
        f"Target orchestrator: {pack.target_orchestrator}",
        f"Route family: {pack.route_family}",
        f"Proof object: {pack.proof_object}",
        f"Pack confidence: {pack.confidence:.3f}",
        "",
        "This note exists to preserve the filtered Timeguard debate context when the pack is promoted into a real RH orchestrator run.",
        "",
        "## Rationale",
        "",
        pack.rationale or "No rationale supplied.",
        "",
        "## Prompt",
        "",
        pack.prompt or "No prompt supplied.",
        "",
        "## Taboo Routes",
        "",
        *[f"- {item}" for item in pack.taboo_routes],
        "",
    ]
    if adjacent_context:
        lines.extend(["## Adjacent Review Context", "", *[f"- {item}" for item in adjacent_context], ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _write_bibliography_note(path: Path, *, pack: OrchestratorSeedPack) -> Path:
    lines = [
        "# Frontier Source Register",
        "",
        f"Orchestrator family alignment: {_ROUTE_ALIGNMENT.get(pack.route_family, 'general_analytic')}",
        f"Target orchestrator: {pack.target_orchestrator}",
        "",
    ]
    for item in pack.bibliography:
        title = str(item.get("title", "untitled"))
        locator = str(item.get("locator", ""))
        note = str(item.get("note", ""))
        lines.extend(
            [
                f"## {title}",
                "",
                f"- Locator: {locator}",
                f"- Family: {item.get('family', pack.route_family)}",
                f"- Note: {note}",
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _write_taboo_note(path: Path, *, pack: OrchestratorSeedPack) -> Path:
    lines = [
        "# Frontier Taboo Routes",
        "",
        "Orchestrator family alignment: general_analytic",
        f"Target orchestrator: {pack.target_orchestrator}",
        "",
        "These are the routes the launch should not reopen unless the run explicitly states a concrete bypass.",
        "",
        *[f"- {item}" for item in pack.taboo_routes],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_route_family_primer(path: Path, *, pack: OrchestratorSeedPack) -> Path:
    alignment = _ROUTE_ALIGNMENT.get(pack.route_family, "general_analytic")
    primer = _ROUTE_PRIMER.get(
        pack.route_family,
        "Keep the run tied to a concrete proof object and avoid generic restatement drift.",
    )
    lines = [
        "# Route Family Primer",
        "",
        f"Orchestrator family alignment: {alignment}",
        f"Target orchestrator: {pack.target_orchestrator}",
        f"Route family: {pack.route_family}",
        "",
        primer,
        "",
        "Route lock:",
        f"- Preferred proof object: {pack.proof_object}",
        "- Avoid collapsing back into finite-data replay or generic equivalence restatement.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _build_oasis_lookup(
    seed_locators: tuple[str, ...],
    bibliography: tuple[dict[str, Any], ...],
) -> dict[str, dict[str, str]]:
    db_paths: list[Path] = []
    for locator in seed_locators:
        if _looks_like_oasis_locator(locator):
            db_paths.append(Path(locator.split("#", 1)[0]).resolve())
    rows = load_oasis_claim_rows(tuple(_dedupe(tuple(str(path) for path in db_paths))))
    lookup = {row["source_locator"]: dict(row) for row in rows}
    for item in bibliography:
        locator = str(item.get("locator", ""))
        if locator and locator not in lookup:
            lookup[locator] = {
                "source_locator": locator,
                "source_title": str(item.get("title", Path(locator).name or "Generated frontier note")),
                "source_kind": str(item.get("source_kind", "generated_frontier_note")),
                "claim_text": str(item.get("note", "")),
            }
    return lookup


def _materialize_oasis_locator(
    locator: str,
    lookup: dict[str, dict[str, str]],
    *,
    pack: OrchestratorSeedPack,
    target_dir: Path,
) -> Path | None:
    row = lookup.get(locator)
    if row is None:
        return None
    kind, local_id = _split_oasis_locator(locator)
    safe_stem = _slugify(f"{kind}-{local_id}")
    path = target_dir / f"{safe_stem}.md"
    alignment = _ROUTE_ALIGNMENT.get(pack.route_family, "general_analytic")
    lines = [
        f"# {row.get('source_title', safe_stem)}",
        "",
        f"Orchestrator family alignment: {alignment}",
        f"Target orchestrator: {pack.target_orchestrator}",
        f"Route family: {pack.route_family}",
        f"Proof object: {pack.proof_object}",
        f"Original locator: {locator}",
        "",
        "This source was materialized from an OASIS SQLite reference so the RH corpus agent can ingest it as text.",
        "Treat the claim as synthetic idea-harvest only, not as mathematical evidence.",
        "",
        "## Surviving Claim",
        "",
        str(row.get("claim_text", "")).strip() or "No claim text available.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _split_oasis_locator(locator: str) -> tuple[str, str]:
    fragment = locator.split("#", 1)[1] if "#" in locator else locator
    kind, _, local_id = fragment.partition(":")
    return kind or "oasis", local_id or "entry"


def _is_existing_local_path(locator: str) -> bool:
    if locator.startswith(("http://", "https://", "file://")):
        return False
    if "#" in locator:
        return False
    return Path(locator).expanduser().exists()


def _is_supported_remote_locator(locator: str) -> bool:
    scheme = urlparse(locator).scheme.lower()
    return scheme in {"http", "https", "file"}


def _looks_like_oasis_locator(locator: str) -> bool:
    if "#post:" in locator or "#comment:" in locator or "#trace:" in locator:
        return Path(locator.split("#", 1)[0]).suffix.lower() in {".db", ".sqlite", ".sqlite3"}
    return False


def _infer_topology_mode(target_orchestrator: str) -> str:
    return "klein" if "klein" in target_orchestrator.lower() else "baseline"


def _default_campaign_id(pack_name: str) -> str:
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{_slugify(pack_name)}-launch-{date_tag}"


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "seed-pack"


def _dedupe(values: tuple[str, ...] | list[str] | tuple[Any, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value)
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
