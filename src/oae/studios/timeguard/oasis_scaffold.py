"""Scaffold generator for CAMEL-AI OASIS frontier simulations.

The scaffold does not assume OASIS is importable in the current environment.
Instead it writes:

- an OASIS-compatible Reddit profile JSON
- a manifest that captures the current RH frontier posture
- a prompt brief for human review
- a runner script for a separate OASIS environment
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from src.oae.studios.timeguard.adapters.riemann import build_timeguard_context
from src.oae.studios.timeguard.external_frontier import (
    run_external_frontier_discovery,
)
from src.oae.studios.timeguard.forecast.timesfm_adapter import TimesFMAdapter
from src.oae.studios.timeguard.mirofish_discovery import run_klein_effort_discovery
from src.oae.studios.timeguard.ranking import rank_work_packages
from src.oae.studios.timeguard.schemas import (
    OasisFrontierProfile,
    OasisFrontierScaffoldReport,
    OrchestratorSeedPack,
    WorkPackagePrediction,
)

_UPSTREAM_PYTHON_CONSTRAINT = ">=3.10,<3.12"
_LOCAL_PYTHON_CONSTRAINT = ">=3.10,<3.14"
_PY313_CAMEL_AI_VERSION = "0.2.90"
_PY313_PANDAS_VERSION = "2.3.3"
_PY313_SENTENCE_TRANSFORMERS_VERSION = "3.0.0"

_PROFILE_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "realname": "Ava Cartwright",
        "username": "frontier_archivist",
        "age": 34,
        "gender": "female",
        "mbti": "INTJ",
        "country": "US",
        "profession": "Mathematics Research Archivist",
        "debate_role": "Archivist",
        "tagline": "Maps what the campaign already proved and what it ruled out.",
    },
    {
        "realname": "Nikhil Rao",
        "username": "operator_bridge_builder",
        "age": 37,
        "gender": "male",
        "mbti": "ENTJ",
        "country": "India",
        "profession": "Operator Theory Researcher",
        "debate_role": "OperatorTheorist",
        "tagline": "Looks for infinite-data or operator certificates that survive the current wall.",
    },
    {
        "realname": "Claire Monroe",
        "username": "explicit_formula_watch",
        "age": 31,
        "gender": "female",
        "mbti": "ISTJ",
        "country": "UK",
        "profession": "Analytic Number Theory Researcher",
        "debate_role": "ExplicitFormulaAnalyst",
        "tagline": "Pushes Weil-Guinand and prime-kernel arguments to exclusion grade.",
    },
    {
        "realname": "Mateo Klein",
        "username": "symmetry_probe",
        "age": 29,
        "gender": "male",
        "mbti": "INFJ",
        "country": "Argentina",
        "profession": "Functional Equation Analyst",
        "debate_role": "SymmetrisationResearcher",
        "tagline": "Tests whether new symmetrisation ideas are genuine or just another equivalence replay.",
    },
    {
        "realname": "Lena Hart",
        "username": "tail_control_engineer",
        "age": 36,
        "gender": "female",
        "mbti": "ESTJ",
        "country": "Canada",
        "profession": "Explicit Formula Error Analyst",
        "debate_role": "TailControlEngineer",
        "tagline": "Keeps the baseline branch honest on tail control and window escape.",
    },
    {
        "realname": "Omar Feld",
        "username": "proof_auditor",
        "age": 41,
        "gender": "male",
        "mbti": "ISTP",
        "country": "Germany",
        "profession": "Proof Verification Consultant",
        "debate_role": "ProofAuditor",
        "tagline": "Rejects circular steps, hidden RH equivalences, and proof-object drift.",
    },
    {
        "realname": "Iris Novak",
        "username": "counterexample_skeptic",
        "age": 33,
        "gender": "female",
        "mbti": "INTP",
        "country": "Croatia",
        "profession": "Mathematical Logic Analyst",
        "debate_role": "Skeptic",
        "tagline": "Searches for holes, duplicate routes, and internal contradictions.",
    },
    {
        "realname": "Theo Park",
        "username": "equivalence_wall_watch",
        "age": 27,
        "gender": "male",
        "mbti": "ENTP",
        "country": "South Korea",
        "profession": "Reformulation Auditor",
        "debate_role": "EquivalenceAuditor",
        "tagline": "Flags proposals that just rename the AV wall instead of bypassing it.",
    },
    {
        "realname": "Maya Chen",
        "username": "seed_pack_builder",
        "age": 30,
        "gender": "female",
        "mbti": "ENFJ",
        "country": "Singapore",
        "profession": "Research Program Designer",
        "debate_role": "SeedBuilder",
        "tagline": "Converts live routes into orchestrator-ready runs and prompt seeds.",
    },
    {
        "realname": "Victor Hale",
        "username": "zero_sum_bridge",
        "age": 38,
        "gender": "male",
        "mbti": "INTJ",
        "country": "US",
        "profession": "Prime Sum and Zero Density Analyst",
        "debate_role": "ZeroSumResearcher",
        "tagline": "Looks for zero-sum certificates that do not rely on finite-data closure.",
    },
    {
        "realname": "Sofia Trent",
        "username": "frontier_moderator",
        "age": 35,
        "gender": "female",
        "mbti": "INFJ",
        "country": "Australia",
        "profession": "Research Strategy Moderator",
        "debate_role": "Moderator",
        "tagline": "Keeps the debate focused on what has been done, what remains, and what to avoid.",
    },
    {
        "realname": "Elias Ward",
        "username": "anomaly_hunter",
        "age": 32,
        "gender": "male",
        "mbti": "ENFP",
        "country": "Ireland",
        "profession": "Mathematical Idea Scout",
        "debate_role": "AnomalyHunter",
        "tagline": "Searches for truly new attack surfaces that survive the taboo list.",
    },
)


def run_oasis_frontier_scaffold(
    *,
    baseline_dir: str | Path,
    klein_dir: str | Path,
    support_docs: tuple[str | Path, ...] = (),
    claim_docs: tuple[str | Path, ...] = (),
    oasis_dbs: tuple[str | Path, ...] = (),
    output_dir: str | Path | None = None,
    agent_count: int = 12,
    top_seed_packs: int = 3,
) -> tuple[OasisFrontierScaffoldReport, dict[str, str] | None]:
    baseline_dir = Path(baseline_dir).resolve()
    klein_dir = Path(klein_dir).resolve()
    resolved_support_docs = tuple(str(Path(path).resolve()) for path in support_docs)
    context = build_timeguard_context(
        baseline_dir,
        klein_dir,
        support_docs=tuple(Path(path) for path in resolved_support_docs),
    )
    forecasts = (
        TimesFMAdapter().forecast_campaign(context.baseline),
        TimesFMAdapter().forecast_campaign(context.klein),
    )
    work_packages = rank_work_packages(context, forecasts, top_k=max(3, top_seed_packs))
    effort_report, _ = run_klein_effort_discovery(
        klein_dir=klein_dir,
        support_docs=tuple(Path(path) for path in resolved_support_docs),
    )
    frontier_report, _ = run_external_frontier_discovery(
        baseline_dir=baseline_dir,
        klein_dir=klein_dir,
        support_docs=tuple(Path(path) for path in resolved_support_docs),
        claim_docs=claim_docs,
        oasis_dbs=oasis_dbs,
        top_seed_packs=top_seed_packs,
    )
    seed_packs = frontier_report.seed_packs or _build_fallback_seed_packs(
        work_packages,
        current_frontier=frontier_report.current_frontier or effort_report.current_frontier,
        taboo_routes=frontier_report.taboo_routes,
        support_docs=tuple(Path(path) for path in resolved_support_docs),
        top_k=top_seed_packs,
    )
    profiles = _build_profiles(
        seed_packs=seed_packs,
        current_frontier=frontier_report.current_frontier or effort_report.current_frontier,
        closed_routes=effort_report.closed_routes,
        taboo_routes=frontier_report.taboo_routes,
        capability_stack=effort_report.capability_stack,
        agent_count=agent_count,
    )
    simulation_topic = _simulation_topic(effort_report.current_frontier, work_packages)
    seed_posts = _build_seed_posts(
        current_frontier=frontier_report.current_frontier or effort_report.current_frontier,
        current_work_packages=tuple(item.title for item in work_packages),
        closed_routes=effort_report.closed_routes,
        taboo_routes=frontier_report.taboo_routes,
        seed_packs=seed_packs,
    )
    warnings = _dedupe(
        frontier_report.warnings,
        (
            (
                f"OASIS upstream currently declares Python {_UPSTREAM_PYTHON_CONSTRAINT}. "
                f"This scaffold adds a patched Reddit-focused Python 3.13 path instead of assuming upstream metadata is already updated."
            ),
            (
                f"The generated Python 3.13 helper patches the OASIS clone to camel-ai {_PY313_CAMEL_AI_VERSION}, "
                f"uses pandas {_PY313_PANDAS_VERSION}, and skips the old unstructured==0.13.7 pin because it blocks Python 3.13 and is not required for the Reddit simulation path."
            ),
        ),
    )
    report = OasisFrontierScaffoldReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        baseline_orchestrator_id=context.baseline.orchestrator_id,
        klein_orchestrator_id=context.klein.orchestrator_id,
        baseline_campaign_dir=str(baseline_dir),
        klein_campaign_dir=str(klein_dir),
        simulation_topic=simulation_topic,
        recommended_python=_LOCAL_PYTHON_CONSTRAINT,
        support_docs=resolved_support_docs,
        current_frontier=frontier_report.current_frontier or effort_report.current_frontier,
        current_work_packages=tuple(item.title for item in work_packages),
        closed_routes=effort_report.closed_routes,
        capability_stack=effort_report.capability_stack,
        taboo_routes=frontier_report.taboo_routes,
        seed_packs=seed_packs,
        profiles=profiles,
        seed_posts=seed_posts,
        warnings=warnings,
        evidence_refs=_dedupe(
            context.evidence_refs,
            effort_report.evidence_refs,
            frontier_report.evidence_refs,
        ),
    )
    if output_dir is None:
        return report, None
    return report, write_oasis_frontier_outputs(report, output_dir)


def run_oasis_frontier_review(
    *,
    manifest_path: str | Path,
    oasis_dbs: tuple[str | Path, ...],
    output_dir: str | Path | None = None,
    top_seed_packs: int = 3,
) -> tuple[Any, dict[str, str] | None]:
    manifest = _load_scaffold_manifest(manifest_path)
    report, outputs = run_external_frontier_discovery(
        baseline_dir=manifest["baseline_campaign_dir"],
        klein_dir=manifest["klein_campaign_dir"],
        support_docs=tuple(manifest["support_docs"]),
        oasis_dbs=oasis_dbs,
        output_dir=output_dir,
        top_seed_packs=top_seed_packs,
    )
    if output_dir is None:
        return report, outputs
    review_meta_path = Path(output_dir).resolve() / "oasis_frontier_review.json"
    review_meta_path.write_text(
        json.dumps(
            {
                "manifest_path": str(Path(manifest_path).resolve()),
                "oasis_dbs": [str(Path(path).resolve()) for path in oasis_dbs],
                "baseline_campaign_dir": manifest["baseline_campaign_dir"],
                "klein_campaign_dir": manifest["klein_campaign_dir"],
                "support_docs": manifest["support_docs"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    outputs = dict(outputs or {})
    outputs["review_meta"] = str(review_meta_path)
    return report, outputs


def write_oasis_frontier_outputs(
    report: OasisFrontierScaffoldReport,
    output_dir: str | Path,
) -> dict[str, str]:
    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    profiles_path = target / "oasis_frontier_profiles.json"
    manifest_path = target / "oasis_frontier_manifest.json"
    prompt_path = target / "oasis_frontier_prompt.txt"
    runner_path = target / "run_oasis_frontier.py"
    review_path = target / "review_oasis_frontier.sh"
    install_path = target / "install_oasis_py313_reddit.sh"
    offline_path = target / "simulate_oasis_frontier_offline.sh"
    report_path = target / "oasis_frontier_report.md"

    profiles_path.write_text(
        json.dumps([item.to_dict() for item in report.profiles], indent=2),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": report.generated_at,
                "baseline_orchestrator_id": report.baseline_orchestrator_id,
                "klein_orchestrator_id": report.klein_orchestrator_id,
                "baseline_campaign_dir": report.baseline_campaign_dir,
                "klein_campaign_dir": report.klein_campaign_dir,
                "simulation_topic": report.simulation_topic,
                "recommended_python": report.recommended_python,
                "support_docs": list(report.support_docs),
                "profile_count": len(report.profiles),
                "current_frontier": list(report.current_frontier),
                "current_work_packages": list(report.current_work_packages),
                "closed_routes": list(report.closed_routes),
                "capability_stack": list(report.capability_stack),
                "taboo_routes": list(report.taboo_routes),
                "seed_packs": [item.to_dict() for item in report.seed_packs],
                "seed_posts": list(report.seed_posts),
                "prompt_path": str(prompt_path),
                "profiles_path": str(profiles_path),
                "runner_path": str(runner_path),
                "review_path": str(review_path),
                "install_path": str(install_path),
                "offline_path": str(offline_path),
                "warnings": list(report.warnings),
                "evidence_refs": list(report.evidence_refs),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    prompt_path.write_text(render_oasis_frontier_prompt(report), encoding="utf-8")
    runner_path.write_text(_render_oasis_runner(report), encoding="utf-8")
    review_path.write_text(_render_oasis_review_script(report), encoding="utf-8")
    install_path.write_text(_render_oasis_install_script(report), encoding="utf-8")
    offline_path.write_text(_render_oasis_offline_script(report), encoding="utf-8")
    report_path.write_text(render_oasis_frontier_markdown(report), encoding="utf-8")
    return {
        "profiles": str(profiles_path),
        "manifest": str(manifest_path),
        "prompt": str(prompt_path),
        "runner": str(runner_path),
        "review": str(review_path),
        "install": str(install_path),
        "offline": str(offline_path),
        "report": str(report_path),
    }


def render_oasis_frontier_prompt(report: OasisFrontierScaffoldReport) -> str:
    lines = [
        f"Simulation topic: {report.simulation_topic}",
        "",
        "What has been done:",
        *[f"- {item}" for item in report.closed_routes[:6]],
        "",
        "What remains:",
        *[f"- {item}" for item in report.current_frontier[:4]],
        *[f"- {item}" for item in report.current_work_packages[:3]],
        "",
        "What to avoid:",
        *[f"- {item}" for item in report.taboo_routes],
        "",
        "Active seed packs:",
    ]
    for pack in report.seed_packs:
        lines.extend(
            [
                f"- {pack.name}: {pack.description}",
                f"  Proof object: {pack.proof_object}",
                f"  Target orchestrator: {pack.target_orchestrator}",
            ]
        )
    lines.extend(
        [
            "",
            "Debate rules:",
            "- Every post must name the route family it is exploring.",
            "- Every candidate idea must state the proof object it is trying to produce.",
            "- Every candidate idea must explain why it is not another finite-data or equivalence-wall replay.",
            "- Synthetic and low-trust sources can seed hypotheses, but they do not count as mathematical evidence.",
            "",
            "Required synthesis output:",
            "- What has been done.",
            "- What remains.",
            "- What to avoid.",
            "- One to three orchestrator-ready seed packs with explicit proof objects.",
        ]
    )
    return "\n".join(lines)


def render_oasis_frontier_markdown(report: OasisFrontierScaffoldReport) -> str:
    lines = [
        "# OASIS Frontier Scaffold",
        "",
        f"Generated: {report.generated_at}",
        "",
        "## Posture",
        "",
        f"- Baseline orchestrator: {report.baseline_orchestrator_id}",
        f"- Klein orchestrator: {report.klein_orchestrator_id}",
        f"- Simulation topic: {report.simulation_topic}",
        f"- Recommended OASIS Python: {report.recommended_python}",
        f"- Profile count: {len(report.profiles)}",
        "",
        "## What Has Been Done",
        "",
        *[f"- {item}" for item in report.closed_routes[:8]],
        "",
        "## What Remains",
        "",
        *[f"- {item}" for item in report.current_frontier[:4]],
        *[f"- {item}" for item in report.current_work_packages[:3]],
        "",
        "## What To Avoid",
        "",
        *[f"- {item}" for item in report.taboo_routes],
        "",
        "## Seed Packs",
        "",
    ]
    for pack in report.seed_packs:
        lines.extend(
            [
                f"### {pack.name}",
                "",
                f"- Target orchestrator: {pack.target_orchestrator}",
                f"- Route family: {pack.route_family}",
                f"- Confidence: {pack.confidence:.2f}",
                f"- Description: {pack.description}",
                f"- Proof object: {pack.proof_object}",
                "",
            ]
        )
    lines.extend(
        [
            "## Warnings",
            "",
            *[f"- {item}" for item in report.warnings],
            "",
        ]
    )
    return "\n".join(lines)


def _build_fallback_seed_packs(
    work_packages: tuple[WorkPackagePrediction, ...],
    *,
    current_frontier: tuple[str, ...],
    taboo_routes: tuple[str, ...],
    support_docs: tuple[str | Path, ...],
    top_k: int,
) -> tuple[OrchestratorSeedPack, ...]:
    references = tuple(str(Path(path).resolve()) for path in support_docs[:4])
    packs: list[OrchestratorSeedPack] = []
    for item in work_packages[:top_k]:
        route_family = _route_family(item.title, item.why_now)
        seeds = _dedupe(
            references,
            item.evidence_refs,
            current_frontier[:2],
        )
        packs.append(
            OrchestratorSeedPack(
                name=_seed_pack_name(item.title, item.target_orchestrator),
                description=item.why_now,
                target_orchestrator=item.target_orchestrator,
                route_family=route_family,
                proof_object=_proof_object(route_family),
                claim_ids=(),
                taboo_routes=taboo_routes,
                seeds=seeds,
                allowlisted_domains=(),
                bibliography=tuple(
                    {
                        "family": route_family,
                        "title": item.title,
                        "locator": ref,
                        "note": item.why_now,
                        "source_kind": "local_map",
                        "source_tier": "high",
                    }
                    for ref in references[:2]
                ),
                prompt=_fallback_seed_prompt(
                    item,
                    current_frontier=current_frontier,
                    taboo_routes=taboo_routes,
                ),
                rationale=(
                    "This pack was synthesized from the current Timeguard ranking because no external claim pack survived screening yet."
                ),
                evidence_refs=_dedupe(item.evidence_refs, references),
                confidence=max(0.58, item.confidence),
            )
        )
    return tuple(packs)


def _fallback_seed_prompt(
    work_package: WorkPackagePrediction,
    *,
    current_frontier: tuple[str, ...],
    taboo_routes: tuple[str, ...],
) -> str:
    return "\n".join(
        [
            f"Target orchestrator: {work_package.target_orchestrator}",
            f"Route family: {_route_family(work_package.title, work_package.why_now)}",
            "",
            "What has been done:",
            "- The current campaign already mapped and closed multiple finite-data and equivalence-wall replays.",
            *[f"- {item}" for item in current_frontier[:2]],
            "",
            "What remains:",
            f"- {work_package.title}",
            f"- {work_package.why_now}",
            "",
            "What to avoid:",
            *[f"- {item}" for item in taboo_routes],
            "",
            "Required output:",
            f"- Produce: {_proof_object(_route_family(work_package.title, work_package.why_now))}",
            "- State the exact obstruction reduced by this run.",
            "- Explain why the route is not another closed replay.",
        ]
    )


def _build_profiles(
    *,
    seed_packs: tuple[OrchestratorSeedPack, ...],
    current_frontier: tuple[str, ...],
    closed_routes: tuple[str, ...],
    taboo_routes: tuple[str, ...],
    capability_stack: tuple[str, ...],
    agent_count: int,
) -> tuple[OasisFrontierProfile, ...]:
    count = max(3, agent_count)
    profiles: list[OasisFrontierProfile] = []
    for index in range(count):
        template = _PROFILE_TEMPLATES[index % len(_PROFILE_TEMPLATES)]
        seed_pack = seed_packs[index % len(seed_packs)] if seed_packs else None
        route_family = seed_pack.route_family if seed_pack else "meta_research"
        focus = (
            seed_pack.description
            if seed_pack is not None
            else (
                current_frontier[index % len(current_frontier)]
                if current_frontier
                else "frontier audit"
            )
        )
        taboo = taboo_routes[index % max(1, len(taboo_routes))] if taboo_routes else "Do not reopen closed routes."
        closed = closed_routes[index % max(1, len(closed_routes))] if closed_routes else "The campaign already closed several duplicate routes."
        capability = capability_stack[index % max(1, len(capability_stack))] if capability_stack else "No capability stack item available."
        username = template["username"]
        realname = template["realname"]
        if index >= len(_PROFILE_TEMPLATES):
            suffix = index + 1
            username = f"{username}_{suffix}"
            realname = f"{realname} {suffix}"
        bio = _normalize_space(
            f"{template['tagline']} Focused on {focus} while avoiding replay of {taboo.lower()}"
        )
        persona = _normalize_space(
            f"{realname} works as a {template['profession']} and joins RH frontier discussions to test {focus}. "
            f"They know the campaign already established: {closed}. "
            f"Their live debate role is {template['debate_role']}, and they keep returning to the current capability stack item '{capability}'. "
            f"They refuse to reopen {taboo.lower()} and insist that every promising angle names a proof object such as {_proof_object(route_family)}."
        )
        profiles.append(
            OasisFrontierProfile(
                realname=realname,
                username=username,
                bio=bio,
                persona=persona,
                age=int(template["age"]),
                gender=str(template["gender"]),
                mbti=str(template["mbti"]),
                country=str(template["country"]),
                profession=str(template["profession"]),
                interested_topics=_topics_for_route(route_family),
                debate_role=str(template["debate_role"]),
                seed_focus=focus,
                evidence_refs=seed_pack.evidence_refs if seed_pack is not None else (),
            )
        )
    return tuple(profiles)


def _build_seed_posts(
    *,
    current_frontier: tuple[str, ...],
    current_work_packages: tuple[str, ...],
    closed_routes: tuple[str, ...],
    taboo_routes: tuple[str, ...],
    seed_packs: tuple[OrchestratorSeedPack, ...],
) -> tuple[str, ...]:
    posts = [
        "\n".join(
            [
                "RH frontier overview:",
                *[f"- {item}" for item in current_frontier[:3]],
                *[f"- Ranked work: {item}" for item in current_work_packages[:2]],
            ]
        ),
        "\n".join(
            [
                "What has been done:",
                *[f"- {item}" for item in closed_routes[:5]],
            ]
        ),
        "\n".join(
            [
                "What to avoid:",
                *[f"- {item}" for item in taboo_routes[:4]],
            ]
        ),
    ]
    for pack in seed_packs[:3]:
        posts.append(
            "\n".join(
                [
                    f"Seed pack: {pack.name}",
                    f"- Route family: {pack.route_family}",
                    f"- Target orchestrator: {pack.target_orchestrator}",
                    f"- Proof object: {pack.proof_object}",
                    f"- Prompt anchor: {pack.description}",
                ]
            )
        )
    return tuple(posts)


def _simulation_topic(
    current_frontier: tuple[str, ...],
    work_packages: tuple[WorkPackagePrediction, ...],
) -> str:
    frontier = current_frontier[0] if current_frontier else "Unnamed frontier"
    top_work = work_packages[0].title if work_packages else "frontier audit"
    return f"{frontier} after the current RH map, focused on {top_work}"


def _topics_for_route(route_family: str) -> tuple[str, ...]:
    return {
        "operator": ("Operator Theory", "Spectral Analysis"),
        "explicit_formula": ("Analytic Number Theory", "Prime Sums"),
        "symmetrisation": ("Functional Equations", "Complex Analysis"),
        "tail_control": ("Explicit Formula", "Asymptotic Bounds"),
        "meta_research": ("Research Strategy", "Proof Auditing"),
        "equivalence_search": ("Reformulations", "Proof Theory"),
    }.get(route_family, ("Analytic Number Theory", "Research Strategy"))


def _seed_pack_name(title: str, target_orchestrator: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    orchestrator = re.sub(r"[^a-z0-9]+", "-", target_orchestrator.lower()).strip("-")
    return f"oasis-{orchestrator}-{slug[:48]}"


def _route_family(*texts: str) -> str:
    lowered = " ".join(item.lower() for item in texts)
    if any(token in lowered for token in ("weil", "guinand", "zero-sum", "zero sum", "prime-kernel", "prime kernel", "explicit formula", "zero-density", "zero density")):
        return "explicit_formula"
    if any(token in lowered for token in ("operator", "self-adjoint", "self adjoint", "trace-class", "trace class", "hilbert-polya", "hilbert-polya")):
        return "operator"
    if any(token in lowered for token in ("functional equation", "symmetr", "self-dual", "self dual", "pole locus", "mobius", "moebius")):
        return "symmetrisation"
    if any(token in lowered for token in ("tail control", "window-escape", "window escape", "error term")):
        return "tail_control"
    if any(token in lowered for token in ("audit", "map", "frontier", "avoid", "replay")):
        return "meta_research"
    return "explicit_formula"


def _proof_object(route_family: str) -> str:
    return {
        "operator": "A trace-class or self-adjoint exclusion certificate that does not smuggle RH back in through an equivalent positivity statement.",
        "explicit_formula": "A Weil-Guinand or prime-kernel zero-sum certificate with unconditional tail control.",
        "symmetrisation": "A self-dual functional-equation certificate that changes the obstruction set instead of renaming the current wall.",
        "tail_control": "A reusable window-escape and explicit-formula tail certificate.",
        "meta_research": "A frontier audit that identifies one genuinely new route and proves it is not a closed replay.",
        "equivalence_search": "A genuinely non-equivalent reformulation with a new proof object.",
    }.get(route_family, "A concrete proof object is still missing.")


def _render_oasis_runner(report: OasisFrontierScaffoldReport) -> str:
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType, ModelType

    import oasis
    from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph
except Exception as exc:
    raise SystemExit(
        "OASIS runtime imports failed. "
        "For Python 3.13, run ./install_oasis_py313_reddit.sh against an OASIS clone first, "
        "then execute this runner inside that prepared environment."
    ) from exc

BASE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = BASE_DIR / "oasis_frontier_manifest.json"
PROFILES_PATH = BASE_DIR / "oasis_frontier_profiles.json"
DB_PATH = BASE_DIR / "oasis_frontier_simulation.db"


async def main(steps: int = 3) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=ModelType.GPT_4O_MINI,
    )
    available_actions = ActionType.get_default_reddit_actions()
    agent_graph = await generate_reddit_agent_graph(
        profile_path=str(PROFILES_PATH),
        model=model,
        available_actions=available_actions,
    )

    os.environ["OASIS_DB_PATH"] = str(DB_PATH.resolve())
    if DB_PATH.exists():
        DB_PATH.unlink()

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=str(DB_PATH),
    )

    await env.reset()
    initial_actions = {{}}
    for index, content in enumerate(manifest.get("seed_posts", [])):
        agent = env.agent_graph.get_agent(index % max(1, manifest.get("profile_count", 1)))
        initial_actions.setdefault(agent, []).append(
            ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={{"content": content}},
            )
        )
    if initial_actions:
        await env.step(initial_actions)

    for _ in range(steps):
        actions = {{
            agent: LLMAction()
            for _, agent in env.agent_graph.get_agents()
        }}
        await env.step(actions)

    await env.close()


if __name__ == "__main__":
    asyncio.run(main())
'''


def _render_oasis_install_script(report: OasisFrontierScaffoldReport) -> str:
    return f'''#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 /path/to/oasis-clone [/path/to/venv]" >&2
  exit 2
fi

OASIS_REPO="$(cd "$1" && pwd)"
VENV_DIR="${{2:-$OASIS_REPO/.venv-py313-reddit}}"

if [[ ! -f "$OASIS_REPO/pyproject.toml" ]]; then
  echo "expected OASIS clone with pyproject.toml at $OASIS_REPO" >&2
  exit 2
fi

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel

export OASIS_REPO
python - <<'PY'
import os
from pathlib import Path
import re

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"could not patch {{label}} in OASIS source")
    return text.replace(old, new, 1)

repo = Path(os.environ["OASIS_REPO"])
pyproject = repo / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")
text, python_count = re.subn(
    r'^python\\s*=\\s*"[^"]+"',
    'python = "{_LOCAL_PYTHON_CONSTRAINT}"',
    text,
    count=1,
    flags=re.MULTILINE,
)
text, camel_count = re.subn(
    r'^camel-ai\\s*=\\s*"[^"]+"',
    'camel-ai = ">={_PY313_CAMEL_AI_VERSION},<0.3"',
    text,
    count=1,
    flags=re.MULTILINE,
)
if python_count == 0:
    raise SystemExit("could not find python constraint in OASIS pyproject.toml")
if camel_count == 0:
    raise SystemExit("could not find camel-ai pin in OASIS pyproject.toml")
pyproject.write_text(text, encoding="utf-8")

recsys = repo / "oasis" / "social_platform" / "recsys.py"
recsys_text = recsys.read_text(encoding="utf-8")
recsys_text = replace_once(
    recsys_text,
    """import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .process_recsys_posts import (generate_post_vector,
                                   generate_post_vector_openai)
from .typing import ActionType, RecsysType
""",
    """import numpy as np

try:
    import torch
except Exception:
    torch = None

from .typing import ActionType, RecsysType
""",
    "recsys imports",
)
recsys_text = replace_once(
    recsys_text,
    """# Initially set to None, to be assigned once again in the recsys function
model = None
twhin_tokenizer = None
twhin_model = None
""",
    """# Initially set to None, to be assigned once again in the recsys function
model = None
twhin_tokenizer = None
twhin_model = None


def _require_torch():
    if torch is None:
        raise ImportError(
            "torch is required for the Twitter/TwHIN recommendation paths. "
            "The Python 3.13 Reddit helper intentionally leaves it optional."
        )


def _get_sentence_transformer():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer


def _get_cosine_similarity():
    from sklearn.metrics.pairwise import cosine_similarity
    return cosine_similarity


def _get_post_vector_functions():
    from .process_recsys_posts import (
        generate_post_vector,
        generate_post_vector_openai,
    )
    return generate_post_vector, generate_post_vector_openai
""",
    "recsys helper block",
)
recsys_text = replace_once(
    recsys_text,
    """# Create the TF-IDF model
tfidf_vectorizer = TfidfVectorizer()
# Prepare the twhin model
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
""",
    """# Create the TF-IDF model lazily for non-Reddit recommendation paths.
tfidf_vectorizer = None
# Prepare the twhin model
device = (
    torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch is not None else "cpu"
)
""",
    "recsys device block",
)
recsys_text = replace_once(
    recsys_text,
    """def load_model(model_name):
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if model_name == 'paraphrase-MiniLM-L6-v2':
            return SentenceTransformer(model_name,
                                       device=device,
                                       cache_folder="./models")
""",
    """def load_model(model_name):
    try:
        _require_torch()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if model_name == 'paraphrase-MiniLM-L6-v2':
            sentence_transformer_cls = _get_sentence_transformer()
            return sentence_transformer_cls(model_name,
                                            device=device,
                                            cache_folder="./models")
""",
    "recsys load_model block",
)
recsys_text = replace_once(
    recsys_text,
    """# Move model to GPU if available
device = 'cuda' if torch.cuda.is_available() else 'cpu'
""",
    """# Move model to GPU if available
device = 'cuda' if torch is not None and torch.cuda.is_available() else 'cpu'
""",
    "recsys runtime device block",
)
recsys_text = replace_once(
    recsys_text,
    """        if use_openai_embedding:
            all_post_vector_list = generate_post_vector_openai(corpus,
                                                               batch_size=1000)
        else:
            all_post_vector_list = generate_post_vector(twhin_model,
                                                        twhin_tokenizer,
                                                        corpus,
                                                        batch_size=1000)
""",
    """        generate_post_vector, generate_post_vector_openai = _get_post_vector_functions()
        if use_openai_embedding:
            all_post_vector_list = generate_post_vector_openai(corpus,
                                                               batch_size=1000)
        else:
            all_post_vector_list = generate_post_vector(twhin_model,
                                                        twhin_tokenizer,
                                                        corpus,
                                                        batch_size=1000)
""",
    "recsys post vector block",
)
recsys_text = replace_once(
    recsys_text,
    """        cosine_similarities = cosine_similarity(user_vector, posts_vector)
""",
    """        cosine_similarity = _get_cosine_similarity()
        cosine_similarities = cosine_similarity(user_vector, posts_vector)
""",
    "recsys cosine block",
)
recsys.write_text(recsys_text, encoding="utf-8")
PY

python -m pip install --no-deps -e "$OASIS_REPO"
python -m pip install \\
  "camel-ai=={_PY313_CAMEL_AI_VERSION}" \\
  "pandas=={_PY313_PANDAS_VERSION}" \\
  "neo4j==5.23.0" \\
  "igraph==0.11.6" \\
  "cairocffi==1.7.1" \\
  "prance==23.6.21.0" \\
  "openapi-spec-validator==0.7.1" \\
  "slack_sdk==3.31.0" \\
  "requests_oauthlib==2.0.0"

echo
echo "Prepared OASIS Reddit runtime for Python 3.13 in $VENV_DIR"
echo "Note: this helper targets the Reddit simulation path."
echo "It patches OASIS recsys imports to load Twitter/TwHIN-only dependencies lazily,"
echo "so Python 3.13 Reddit runs do not require sentence-transformers/torch or unstructured."
echo "Activate with: source '$VENV_DIR/bin/activate'"
'''


def _render_oasis_review_script(report: OasisFrontierScaffoldReport) -> str:
    return '''#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST_PATH="$BASE_DIR/oasis_frontier_manifest.json"
DB_PATH="${1:-$BASE_DIR/oasis_frontier_simulation.db}"
OUTPUT_DIR="${2:-$BASE_DIR/oasis_frontier_review}"

timeguard review-oasis-frontier \
  --manifest "$MANIFEST_PATH" \
  --oasis-db "$DB_PATH" \
  --output-dir "$OUTPUT_DIR"
'''


def _render_oasis_offline_script(report: OasisFrontierScaffoldReport) -> str:
    return '''#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST_PATH="$BASE_DIR/oasis_frontier_manifest.json"
OUTPUT_DIR="${1:-$BASE_DIR/oasis_frontier_offline_run}"

timeguard simulate-oasis-frontier-offline \
  --manifest "$MANIFEST_PATH" \
  --output-dir "$OUTPUT_DIR"
'''


def _load_scaffold_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = ("baseline_campaign_dir", "klein_campaign_dir", "support_docs")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(
            f"OASIS scaffold manifest is missing required fields: {', '.join(missing)}"
        )
    return {
        "baseline_campaign_dir": str(Path(payload["baseline_campaign_dir"]).resolve()),
        "klein_campaign_dir": str(Path(payload["klein_campaign_dir"]).resolve()),
        "support_docs": [str(Path(item).resolve()) for item in payload.get("support_docs", [])],
    }


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
