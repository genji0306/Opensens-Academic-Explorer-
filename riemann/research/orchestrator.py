"""Recursive campaign orchestrator for RH research."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from src.oae.research import (
    DossierPointer,
    DossierWriter,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    ResearchMemory,
    ResearchTrace,
    TraceEntry,
)

from .algorithm_agent import AlgorithmAgent
from .benchmark import build_campaign_benchmark
from .certificate_program import build_certificate_report
from .config import RiemannResearchConfig, ensure_dirs
from .corpus_agent import CorpusAgent
from .dead_end_library import build_dead_end_library_artifact, dead_end_definitions
from .hypothesis_agent import HypothesisAgent
from .klein_agent import KleinAgent
from .klein_topology import klein_feedback_from_failure_counts
from .literature_mapping import write_literature_connection_outputs
from .modeling_agent import ModelingAgent
from .observer_agent import ObserverAgent
from .operator_language import (
    build_calibration_report,
    build_operator_language_spec,
    merge_feedback,
)
from .obligation_ledger import build_campaign_obligation_ledger
from .proof_attempts import materialize_proof_attempt_corpus
from .quantum_agent import QuantumAgent
from .schemas import ApproachCard, CampaignRoundRecord, SourceRecord
from .seed_pack import resolve_seed_inputs
from .tail_control_agent import TailControlAgent
from .lean_residue import LeanResidueLedger
from .lean_residue_writer import write_round_skeletons
from .certificate_program import _generate_lean_skeleton
from .external_eval import ExternalEvaluator


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _read_json(path)


def _as_tuple(values: Any) -> tuple[Any, ...]:
    if isinstance(values, tuple):
        return values
    if isinstance(values, list):
        return tuple(values)
    if values is None:
        return ()
    return (values,)


def _source_from_dict(payload: dict[str, Any]) -> SourceRecord:
    return SourceRecord(
        source_id=str(payload.get("source_id", "")),
        locator=str(payload.get("locator", "")),
        title=str(payload.get("title", "")),
        authors=tuple(payload.get("authors", ())),
        year=payload.get("year"),
        source_kind=str(payload.get("source_kind", "local_file")),
        retrieval_hash=str(payload.get("retrieval_hash", "")),
        cache_path=str(payload.get("cache_path", "")),
        provenance=dict(payload.get("provenance", {})),
    )


def _approach_from_dict(payload: dict[str, Any]) -> ApproachCard:
    return ApproachCard(
        approach_id=str(payload.get("approach_id", "")),
        family=str(payload.get("family", "")),
        core_claim=str(payload.get("core_claim", "")),
        assumptions=tuple(payload.get("assumptions", ())),
        mechanism=str(payload.get("mechanism", "")),
        proof_obligations=tuple(payload.get("proof_obligations", ())),
        known_blockers=tuple(payload.get("known_blockers", ())),
        cited_sources=tuple(payload.get("cited_sources", ())),
        executable_checks=tuple(payload.get("executable_checks", ())),
        observer_scores={str(k): float(v) for k, v in dict(payload.get("observer_scores", {})).items()},
        summary=str(payload.get("summary", "")),
    )


def _load_memory(root: Path, session_id: str) -> ResearchMemory:
    memory = ResearchMemory(root=root, auto_persist=False)
    dossier_index_path = root / "dossier_index.json"
    if dossier_index_path.exists():
        payload = json.loads(dossier_index_path.read_text())
        memory.dossiers = {
            str(item["candidate_id"]): DossierPointer(
                candidate_id=str(item["candidate_id"]),
                path=str(item["path"]),
                campaign_id=str(item.get("campaign_id", "")),
                family=str(item.get("family", "")),
            )
            for item in payload
        }

    graph_path = root / "claim_graph.json"
    if graph_path.exists():
        payload = json.loads(graph_path.read_text())
        nodes = tuple(
            GraphNode(
                node_id=str(node["id"]),
                kind=str(node["kind"]),
                label=str(node.get("label", "")),
                attributes={str(k): str(v) for k, v in dict(node.get("attributes", {})).items()},
            )
            for node in payload.get("nodes", [])
        )
        edges = tuple(
            GraphEdge(
                src=str(edge["src"]),
                dst=str(edge["dst"]),
                kind=str(edge["kind"]),
                weight=float(edge.get("weight", 1.0)),
                attributes={str(k): str(v) for k, v in dict(edge.get("attributes", {})).items()},
            )
            for edge in payload.get("edges", [])
        )
        memory.graph = EvidenceGraph(nodes=nodes, edges=edges)

    memory.start_session(session_id)
    return memory


def _load_trace(cfg: RiemannResearchConfig) -> ResearchTrace:
    trace = ResearchTrace(session_id=cfg.campaign_id, traces_dir=cfg.traces_dir, auto_persist=False)
    path = cfg.traces_dir / f"{cfg.campaign_id}.jsonl"
    if not path.exists():
        return trace
    entries: list[TraceEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        entries.append(
            TraceEntry(
                timestamp=str(payload["timestamp"]),
                session_id=str(payload["session_id"]),
                candidate_id=str(payload["candidate_id"]),
                kind=str(payload["kind"]),
                payload=dict(payload.get("payload", {})),
            )
        )
    trace.entries = entries
    return trace


def _load_checkpoint_payloads(cfg: RiemannResearchConfig) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(cfg.checkpoints_dir.glob("round_*.json")):
        try:
            payload = _read_json(path)
        except json.JSONDecodeError:
            continue
        payload["_path"] = str(path)
        payloads.append(payload)
    return payloads


def _history_from_checkpoints(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for payload in payloads:
        evaluations = payload.get("evaluations", [])
        best = max(evaluations, key=lambda item: float(item.get("score", 0.0)), default={})
        history.append(
            {
                "round_index": int(payload.get("round_index", 0)),
                "best_candidate_id": str(best.get("candidate_id", "")),
                "best_score": float(best.get("score", 0.0)),
                "routing": dict(payload.get("routing", {})),
                "checkpoint_path": str(payload.get("_path", "")),
            }
        )
    return history


def _no_improve_count(history: list[dict[str, Any]]) -> int:
    best_score = -1.0
    no_improve = 0
    for item in history:
        score = float(item.get("best_score", 0.0))
        if score > best_score + 1e-6:
            best_score = score
            no_improve = 0
        else:
            no_improve += 1
    return no_improve


def _family_usage_from_checkpoints(payloads: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for payload in payloads:
        for hypothesis in payload.get("hypotheses", []):
            for family in hypothesis.get("ingredient_families", ()):
                token = str(family)
                counts[token] = counts.get(token, 0) + 1
    return counts


def _resume_state(cfg: RiemannResearchConfig) -> dict[str, Any] | None:
    if not cfg.resume:
        return None

    approach_map = _read_json_if_exists(cfg.approach_map_path)
    summary = _read_json_if_exists(cfg.summary_path)
    checkpoints = _load_checkpoint_payloads(cfg)
    if approach_map is None and not checkpoints and summary is None:
        return None

    sources = tuple(_source_from_dict(item) for item in (approach_map or {}).get("sources", ()))
    approaches = tuple(_approach_from_dict(item) for item in (approach_map or {}).get("approaches", ()))
    skipped = tuple((approach_map or {}).get("skipped", ()))
    history = list(summary.get("history", [])) if summary else _history_from_checkpoints(checkpoints)
    if not history and checkpoints:
        history = _history_from_checkpoints(checkpoints)
    last_completed_round = max((int(item.get("round_index", 0)) for item in history), default=0)

    feedback: dict[str, tuple[str, ...]] = {}
    if history:
        raw_feedback = history[-1].get("routing", {}).get("feedback", {})
        feedback = {str(k): tuple(v) for k, v in dict(raw_feedback).items()}

    prior_eval_summaries: tuple[dict[str, Any], ...] = ()
    if checkpoints:
        last_payload = max(checkpoints, key=lambda item: int(item.get("round_index", 0)))
        hypothesis_map = {
            str(item.get("candidate_id", "")): item
            for item in last_payload.get("hypotheses", [])
        }
        prior_eval_summaries = tuple(
            {
                "candidate_id": str(item.get("candidate_id", "")),
                "score": float(item.get("score", 0.0)),
                "ingredient_approach_ids": tuple(
                    hypothesis_map.get(str(item.get("candidate_id", "")), {}).get("ingredient_approach_ids", ())
                ),
            }
            for item in last_payload.get("evaluations", [])
        )

    best_score = float(summary.get("best_score", 0.0)) if summary else max(
        (float(item.get("best_score", 0.0)) for item in history),
        default=0.0,
    )
    best_candidate_id = str(summary.get("best_candidate_id", "")) if summary else next(
        (
            str(item.get("best_candidate_id", ""))
            for item in history
            if float(item.get("best_score", 0.0)) >= best_score - 1e-6
        ),
        "",
    )
    best_dossier_path = str(summary.get("best_dossier_path", "")) if summary else (
        (cfg.dossiers_dir / cfg.campaign_id / f"{best_candidate_id}.md").as_posix() if best_candidate_id else ""
    )
    total_hypotheses = int(summary.get("total_hypotheses", 0)) if summary else sum(
        len(payload.get("hypotheses", [])) for payload in checkpoints
    )
    converged = bool(summary.get("converged", False)) if summary else any(
        item.get("routing", {}).get("stop_reason") == "proof_target_reached"
        for item in history
    )
    termination_reason = str(summary.get("termination_reason", "")) if summary else ""
    family_usage = dict(summary.get("family_usage", {})) if summary and summary.get("family_usage") else _family_usage_from_checkpoints(checkpoints)

    return {
        "sources": sources,
        "approaches": approaches,
        "skipped": skipped,
        "summary": summary or {},
        "history": history,
        "last_completed_round": last_completed_round,
        "prior_eval_summaries": prior_eval_summaries,
        "feedback": feedback,
        "no_improve_count": _no_improve_count(history),
        "best_score": best_score,
        "best_candidate_id": best_candidate_id,
        "best_dossier_path": best_dossier_path,
        "total_hypotheses": total_hypotheses,
        "converged": converged,
        "termination_reason": termination_reason,
        "family_usage": family_usage,
    }


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in cleaned.split("_") if part)


def _load_campaign_rounds(campaign_dir: Path) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    for eval_path in sorted(campaign_dir.glob("round_*_evaluations.json")):
        stem = eval_path.name.replace("_evaluations.json", "")
        rounds.append(
            {
                "round_index": int(stem.split("_")[1]),
                "hypotheses": _read_json_if_exists(campaign_dir / f"{stem}_hypotheses.json") or [],
                "proposals": _read_json_if_exists(campaign_dir / f"{stem}_proposals.json") or [],
                "novelty": _read_json_if_exists(campaign_dir / f"{stem}_novelty.json") or [],
                "evaluations": _read_json_if_exists(eval_path) or [],
            }
        )
    return rounds


def _artifact_quality(round_payload: dict[str, Any], evaluation: dict[str, Any]) -> float:
    candidate_id = str(evaluation.get("candidate_id", ""))
    accepted_ids = {str(item) for item in evaluation.get("novelty_artifact_ids", ())}
    linked = [
        item
        for item in round_payload.get("novelty", [])
        if str(item.get("linked_hypothesis_id", "")) in {"", candidate_id}
    ]
    if not linked:
        return 0.0

    quality_scores: list[float] = []
    accepted_count = 0
    for artifact in linked:
        feature_values = [
            float(value)
            for value in dict(artifact.get("measurable_features", {}) or {}).values()
            if isinstance(value, (int, float))
        ]
        feature_support = sum(feature_values) / max(len(feature_values), 1) if feature_values else 0.0
        structure_terms = (
            1.0 if artifact.get("canonical_signature") else 0.0,
            min(1.0, len(artifact.get("operator_primitives", ())) / 4.0),
            min(1.0, len(artifact.get("proof_skeleton", ())) / 4.0),
        )
        structure_score = sum(structure_terms) / len(structure_terms)
        complexity_score = max(0.0, min(1.0, 1.0 - float(artifact.get("operator_complexity", 0.0)) / 6.0))
        quality = 0.45 * feature_support + 0.30 * structure_score + 0.25 * complexity_score
        if str(artifact.get("artifact_id", "")) in accepted_ids:
            accepted_count += 1
            quality_scores.append(quality)
    accepted_ratio = accepted_count / max(len(linked), 1)
    accepted_quality = sum(quality_scores) / max(len(quality_scores), 1) if quality_scores else 0.0
    return max(0.0, min(1.0, 0.55 * accepted_ratio + 0.45 * accepted_quality))


def _targeted_check_for_obligation(obligation_class: str) -> tuple[str, str]:
    mapping = {
        "explicit_formula_tail_control": (
            "explicit_formula_tail_control",
            "The explicit-formula lane still needs a stronger tail/error-term margin.",
        ),
        "off_line_zero_exclusion": (
            "certificate_search",
            "The current branch still lacks a usable off-line-zero exclusion margin.",
        ),
        "xi_coefficient_exclusion_bridge": (
            "xi_coefficient_bridge",
            "Xi/coefficient evidence still needs a stronger exclusion bridge.",
        ),
        "operator_non_surrogate_rigor": (
            "operator_non_surrogate_rigor",
            "Operator evidence is still surrogate-heavy and needs a more rigorous certificate.",
        ),
        "operator_uniqueness": (
            "operator_non_surrogate_rigor",
            "Operator uniqueness pressure remains too weak to support promotion.",
        ),
        "critical_line_to_global_exclusion": (
            "surface_return_certificate",
            "Critical-line control has not yet returned as a global exclusion argument.",
        ),
        "space_construction_and_positivity": (
            "space_construction_consistency",
            "Function-space construction and positivity conditions still remain open.",
        ),
        "visual_or_surrogate_translation": (
            "zero_atlas_xi_bridge",
            "The branch still needs a xi-facing invariant instead of a descriptive atlas or surrogate picture.",
        ),
        "statistical_to_theorem_upgrade": (
            "variance_collapse_exclusion",
            "Critical-line concentration still needs to survive an exceptional-zero exclusion check.",
        ),
    }
    return mapping.get(
        obligation_class,
        ("certificate_search", "The branch still needs a stronger exclusion-oriented certificate."),
    )


def _targeted_check_for_dead_end(pattern_id: str) -> tuple[str, str]:
    mapping = {
        "finite_window_well_depth": (
            "explicit_formula_tail_control",
            "The branch still needs a stronger tail/global escape margin beyond finite-window evidence.",
        ),
        "descriptive_visualization_only": (
            "zero_atlas_xi_bridge",
            "The atlas still needs a stronger invariant-to-certificate translation step.",
        ),
        "statistical_constancy_without_exclusion": (
            "variance_collapse_exclusion",
            "Statistical concentration still needs a theorem-level exclusion upgrade.",
        ),
        "d_phi_subcritical_exclusion_return": (
            "d_phi_formalization",
            "D_phi needs stronger xi-bridge, quartet-exclusion, and tail-recombination submargins before promotion.",
        ),
    }
    return mapping.get(pattern_id, ("certificate_search", "The branch still needs a stronger exclusion-oriented certificate."))


def _concrete_certificate_blockers(
    *,
    open_reports: list[dict[str, Any]],
    dead_end_pattern_ids: tuple[str, ...],
    why_it_is_not_a_proof: list[str],
    next_check_id: str,
) -> list[str]:
    blockers: list[str] = []
    if open_reports:
        blockers.append("unresolved_obligations")
    if dead_end_pattern_ids:
        blockers.append("dead_end_patterns")
    normalized_check_id = str(next_check_id).strip().lower()
    if normalized_check_id and normalized_check_id not in {"n/a", "none", "complete"}:
        blockers.append(f"pending_targeted_check:{next_check_id}")
    if why_it_is_not_a_proof:
        blockers.append("review_not_proof")
    return blockers


def _build_best_candidate_review(
    *,
    summary: dict[str, Any],
    rounds: list[dict[str, Any]],
    certificate_report: dict[str, Any],
    obligation_ledger: dict[str, Any],
    dead_end_library: dict[str, Any],
    failure_atlas: dict[str, Any],
) -> dict[str, Any]:
    best_candidate_id = str(summary.get("best_candidate_id", ""))
    best_round_payload: dict[str, Any] = {}
    best_evaluation: dict[str, Any] = {}
    best_hypothesis: dict[str, Any] = {}
    for round_payload in rounds:
        for evaluation in round_payload.get("evaluations", []):
            if str(evaluation.get("candidate_id", "")) != best_candidate_id:
                continue
            if not best_evaluation or float(evaluation.get("score", 0.0)) >= float(best_evaluation.get("score", 0.0)):
                best_round_payload = round_payload
                best_evaluation = evaluation
                best_hypothesis = next(
                    (
                        item
                        for item in round_payload.get("hypotheses", [])
                        if str(item.get("candidate_id", "")) == best_candidate_id
                    ),
                    {},
                )
    if not best_evaluation:
        return {}

    certificate_snapshot = next(
        (
            item
            for item in certificate_report.get("candidate_reports", [])
            if str(item.get("candidate_id", "")) == best_candidate_id
        ),
        {},
    )
    obligation_snapshot = next(
        (
            item
            for item in obligation_ledger.get("candidates", [])
            if str(item.get("candidate_id", "")) == best_candidate_id
        ),
        {},
    )
    dead_end_hits = next(
        (
            item
            for item in dead_end_library.get("campaign_hits", [])
            if str(item.get("candidate_id", "")) == best_candidate_id
        ),
        {},
    )
    failure_lookup = {
        str(item["pattern_id"]): item
        for item in dead_end_definitions()
    }
    open_reports = [
        item
        for item in obligation_snapshot.get("obligation_reports", [])
        if str(item.get("status", "")) != "resolved"
    ]
    next_obligation = open_reports[0] if open_reports else {}
    if next_obligation:
        next_check_id, next_check_reason = _targeted_check_for_obligation(str(next_obligation.get("obligation_class", "")))
    elif dead_end_hits.get("pattern_ids"):
        next_check_id, next_check_reason = _targeted_check_for_dead_end(str(dead_end_hits.get("pattern_ids", ("",))[0]))
    else:
        next_check_id, next_check_reason = (
            "n/a",
            "The review layer does not currently expose a higher-priority unresolved certificate.",
        )
    components = dict(best_evaluation.get("components", {}) or {})
    artifact_quality = _artifact_quality(best_round_payload, best_evaluation)

    why_it_scored_well: list[str] = []
    if float(components.get("consistency_with_known_results", 0.0)) >= 0.65:
        why_it_scored_well.append("It stays reasonably consistent with the current explicit-formula and critical-line checks.")
    if float(obligation_snapshot.get("proof_obligation_reduction", 0.0)) > 0.0:
        why_it_scored_well.append(
            f"It resolves {len(obligation_snapshot.get('resolved_obligation_classes', ()))}/"
            f"{max(len(obligation_snapshot.get('introduced_obligation_classes', ())), 1)} normalized obligation classes."
        )
    if float(components.get("numerical_support", 0.0)) >= 0.80:
        why_it_scored_well.append("It inherits strong bounded numerical support from the existing Riemann loop.")
    if float(certificate_snapshot.get("margin_summary", {}).get("best_margin", 0.0)) >= 0.60:
        why_it_scored_well.append("At least one certificate lane reached a nontrivial margin instead of descriptive-only output.")
    if not why_it_scored_well:
        why_it_scored_well.append("It is currently the least contradictory branch in the saved campaign traces.")

    why_it_is_not_a_proof = [
        str(item.get("reason", "An obligation remains unresolved."))
        for item in open_reports[:4]
    ]
    for pattern_id in dead_end_hits.get("pattern_ids", ()):
        reason = failure_lookup.get(str(pattern_id), {}).get("rejection_reason")
        if reason and reason not in why_it_is_not_a_proof:
            why_it_is_not_a_proof.append(str(reason))
    dominant_failures = [
        {"failure_class": name, "count": count}
        for name, count in sorted(
            dict(failure_atlas.get("failure_counts", {})).items(),
            key=lambda item: (-item[1], item[0]),
        )[:5]
    ]
    if not why_it_is_not_a_proof:
        why_it_is_not_a_proof.append("The branch still falls short of a theorem-level exclusion argument.")
    dead_end_pattern_ids = tuple(str(pattern_id) for pattern_id in dead_end_hits.get("pattern_ids", ()))
    concrete_certificate_blockers = _concrete_certificate_blockers(
        open_reports=open_reports,
        dead_end_pattern_ids=dead_end_pattern_ids,
        why_it_is_not_a_proof=why_it_is_not_a_proof,
        next_check_id=next_check_id,
    )

    return {
        "candidate_id": best_candidate_id,
        "round_index": int(best_evaluation.get("round_index", 0) or best_round_payload.get("round_index", 0)),
        "score": float(best_evaluation.get("score", 0.0)),
        "ingredient_families": tuple(str(item) for item in best_hypothesis.get("ingredient_families", ())),
        "proof_obligation_reduction": float(obligation_snapshot.get("proof_obligation_reduction", 0.0)),
        "artifact_quality": artifact_quality,
        "why_it_scored_well": why_it_scored_well,
        "why_it_is_not_a_proof": why_it_is_not_a_proof,
        "concrete_certificate_ready": not concrete_certificate_blockers,
        "concrete_certificate_blockers": concrete_certificate_blockers,
        "remaining_obligations": open_reports,
        "dead_end_patterns": [
            {
                "pattern_id": str(pattern_id),
                "rejection_reason": str(failure_lookup.get(str(pattern_id), {}).get("rejection_reason", "")),
            }
            for pattern_id in dead_end_pattern_ids
        ],
        "next_targeted_check": {
            "check_id": next_check_id,
            "reason": next_check_reason,
        },
        "certificate_summary": dict(certificate_snapshot.get("margin_summary", {})),
        "dominant_failure_classes": dominant_failures,
    }


def _postprocess_campaign_outputs(
    cfg: RiemannResearchConfig,
    summary: dict[str, Any],
) -> dict[str, Any]:
    rounds = _load_campaign_rounds(cfg.campaign_dir)
    failure_atlas = _read_json_if_exists(cfg.failure_atlas_path) or {
        "campaign_id": cfg.campaign_id,
        "failure_counts": {},
        "rounds": [],
    }
    dead_end_library = build_dead_end_library_artifact(
        campaign_id=cfg.campaign_id,
        rounds=rounds,
    )
    certificate_report = build_certificate_report(
        campaign_id=cfg.campaign_id,
        rounds=rounds,
    )
    obligation_ledger = build_campaign_obligation_ledger(
        campaign_id=cfg.campaign_id,
        rounds=rounds,
        research_root=cfg.research_root,
        campaign_dir=cfg.campaign_dir,
    )

    summary = dict(summary)
    summary.setdefault("paths", {})
    summary["top_unresolved_obligations"] = obligation_ledger.get("summary", {}).get("top_unresolved_obligations", [])
    summary["dominant_failure_classes"] = [
        {"failure_class": name, "count": count}
        for name, count in sorted(
            dict(failure_atlas.get("failure_counts", {})).items(),
            key=lambda item: (-item[1], item[0]),
        )[:8]
    ]
    summary["certificate_margin_summary"] = dict(certificate_report.get("summary", {}))
    summary["best_candidate_review"] = _build_best_candidate_review(
        summary=summary,
        rounds=rounds,
        certificate_report=certificate_report,
        obligation_ledger=obligation_ledger,
        dead_end_library=dead_end_library,
        failure_atlas=failure_atlas,
    )
    benchmark = build_campaign_benchmark(
        research_root=cfg.research_root,
        current_campaign_dir=cfg.campaign_dir,
        current_summary=summary,
        current_certificate_report=certificate_report,
        current_obligation_ledger=obligation_ledger,
        current_failure_atlas=failure_atlas,
    )
    summary["benchmark_mode"] = str(benchmark.get("benchmark_mode", "baseline"))
    summary["paths"].update(
        {
            "certificate_report": str(cfg.certificate_report_path),
            "obligation_ledger": str(cfg.obligation_ledger_path),
            "campaign_benchmark": str(cfg.campaign_benchmark_path),
            "dead_end_library": str(cfg.dead_end_library_path),
        }
    )

    _write_json(cfg.dead_end_library_path, dead_end_library)
    _write_json(cfg.certificate_report_path, certificate_report)
    _write_json(cfg.obligation_ledger_path, obligation_ledger)
    _write_json(cfg.campaign_benchmark_path, benchmark)
    return summary


def _collect_round_failure_counts(
    hypotheses: tuple[Any, ...],
    proposals: tuple[Any, ...],
    novelties: tuple[Any, ...],
    evaluations: tuple[Any, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {}

    def add(token: str) -> None:
        normalized = _slug(token)
        if not normalized:
            return
        counts[normalized] = counts.get(normalized, 0) + 1

    for hypothesis in hypotheses:
        for item in getattr(hypothesis, "risk_flags", ()):
            add(item)
        for item in getattr(hypothesis, "unresolved_proof_obligations", ()):
            add(f"obligation:{item}")
    for proposal in proposals:
        for item in getattr(proposal, "rejected_novelty_ids", ()):
            add(f"rejected_novelty:{item}")
    for artifact in novelties:
        for item in getattr(artifact, "failure_modes", ()):
            add(item)
    for evaluation in evaluations:
        summary = str(getattr(evaluation, "contradiction_summary", ""))
        for chunk in summary.split(";"):
            add(chunk)
        for item in getattr(evaluation, "recommended_actions", ()):
            add(f"action:{item}")
    return counts


def _feedback_from_failure_counts(failure_counts: dict[str, int]) -> dict[str, tuple[str, ...]]:
    feedback: dict[str, tuple[str, ...]] = {}
    keys = set(failure_counts)
    if {"finite_window_only", "well_depth_needs_analytic_bound", "critical_line_identity_is_classical"} & keys:
        feedback["M"] = (
            "convert sampled geometry into an analytic bound or exclusion lemma",
            "prefer low-complexity critical-line invariants over descriptive renderings",
        )
    if {
        "finite_window_only",
        "explicit_formula_is_not_by_itself_a_proof",
        "tail_budget_needs_decay_bound",
        "failed_certificate_explicit_formula_tail_control",
    } & keys:
        feedback["T"] = (
            "emit explicit-formula tail budgets with separate decay, error-budget, and window-escape structure",
            "turn finite-window explicit-formula evidence into reusable contour-shift obligations",
        )
    if {"surrogate_is_not_unique", "spectral_matching_is_not_a_proof"} & keys:
        feedback["Q"] = (
            "add uniqueness or exclusion constraints to the spectral surrogate lane",
            "reduce reliance on operator analogies that do not change proof obligations",
        )
    if {"counting_law_needs_explicit_error_bound", "zero_sum_relation_needs_tail_control"} & keys:
        feedback["M"] = feedback.get("M", ()) + (
            "promote the zero atlas only if the 2pi-normalized count law becomes a measurable invariant",
        )
        feedback["B"] = feedback.get("B", ()) + (
            "treat any pi or zero-sum relation as a tail-controlled certificate problem, not a closed-form guess for individual ordinates",
        )
    if "failed_certificate_zero_atlas_xi_bridge" in keys:
        feedback["A"] = feedback.get("A", ()) + (
            "pair xi-function lanes with the zero atlas only when the atlas adds a real exclusion bridge",
        )
        feedback["M"] = feedback.get("M", ()) + (
            "promote contour and 2pi-normalized atlas structure into a xi-facing invariant rather than a picture-driven cue",
        )
        feedback["B"] = feedback.get("B", ()) + (
            "raise the zero-atlas bridge from bounded zero tables to an explicit xi-based exclusion step",
        )
    if any(key.startswith("obligation_") for key in keys) or "large_obligation_load" in keys:
        feedback["A"] = (
            "narrow the next synthesis batch to smaller proof-skeleton obligations",
        )
    if (
        "critical_line_identities_are_classical_and_do_not_exclude_off_line_zeros" in keys
        or "prove_sampled_well_depth_implies_a_global_exclusion_argument" in keys
    ):
        feedback["B"] = (
            "prioritize falsification checks around off-line-zero exclusion claims",
        )
    if {
        "failed_certificate_certificate_search",
        "failed_certificate_explicit_formula_tail_control",
        "failed_certificate_xi_coefficient_bridge",
    } & keys:
        feedback["B"] = feedback.get("B", ()) + (
            "tighten certificate margins and replace bounded windows with explicit tail-control arguments",
        )
    if "failed_certificate_variance_collapse_exclusion" in keys:
        feedback["A"] = feedback.get("A", ()) + (
            "pair random-matrix or statistical branches with explicit-formula or xi-function exclusion scaffolds before promotion",
        )
        feedback["B"] = feedback.get("B", ()) + (
            "force statistical concentration claims to produce exceptional-zero exclusion pressure, not just sampled-line agreement",
        )
    return feedback


def run_campaign(
    cfg: RiemannResearchConfig,
    *,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run the recursive RH research/testing campaign."""

    ensure_dirs(cfg)
    materialize_proof_attempt_corpus()
    trace = _load_trace(cfg) if cfg.resume else ResearchTrace(session_id=cfg.campaign_id, traces_dir=cfg.traces_dir, auto_persist=False)
    memory = _load_memory(cfg.memory_dir, cfg.campaign_id) if cfg.resume else ResearchMemory(root=cfg.memory_dir, auto_persist=False)
    if not cfg.resume:
        memory.start_session(cfg.campaign_id)
    dossier_writer = DossierWriter(root=cfg.dossiers_dir)

    agent_c = CorpusAgent()
    agent_a = HypothesisAgent()
    agent_b = AlgorithmAgent()
    agent_m = ModelingAgent()
    agent_q = QuantumAgent()
    agent_t = TailControlAgent()
    agent_k = KleinAgent()
    agent_ob = ObserverAgent()
    operator_language = build_operator_language_spec(cfg.operator_framework_path)
    _write_json(cfg.operator_language_path, operator_language)

    seed_manifest = {
        "seed_pack_names": list(cfg.seed_pack_names),
        "crawl_seeds": list(cfg.crawl_seeds),
        "allowlisted_domains": list(cfg.allowlisted_domains),
        "operator_framework_path": str(cfg.operator_framework_path),
        "topology_mode": cfg.topology_mode,
        "preferred_route_family": cfg.preferred_route_family,
        "route_lock_strict": cfg.route_lock_strict,
        "bibliography": [],
    }
    if cfg.seed_pack_names:
        _, _, pack_manifest = resolve_seed_inputs(cfg.seed_pack_names)
        seed_manifest = {
            **pack_manifest,
            "seed_pack_names": list(cfg.seed_pack_names),
            "crawl_seeds": list(cfg.crawl_seeds),
            "allowlisted_domains": list(cfg.allowlisted_domains),
            "topology_mode": cfg.topology_mode,
            "preferred_route_family": cfg.preferred_route_family,
            "route_lock_strict": cfg.route_lock_strict,
        }
    _write_json(cfg.seed_manifest_path, seed_manifest)

    resume_state = _resume_state(cfg)
    resumed = resume_state is not None
    resumed_from_round = int(resume_state["last_completed_round"]) if resume_state else 0

    if resume_state and resume_state["converged"]:
        summary = dict(resume_state["summary"])
        summary.setdefault("topology_mode", cfg.topology_mode)
        summary["resumed"] = True
        summary["resumed_from_round"] = resumed_from_round
        summary.setdefault("paths", {})
        summary["paths"]["seed_manifest"] = str(cfg.seed_manifest_path)
        summary["paths"]["operator_language"] = str(cfg.operator_language_path)
        summary = _postprocess_campaign_outputs(cfg, summary)
        _write_json(cfg.summary_path, summary)
        return summary

    if resume_state and resumed_from_round >= cfg.max_rounds:
        summary = dict(resume_state["summary"])
        if not summary:
            summary = {
                "campaign_id": cfg.campaign_id,
                "history": resume_state["history"],
                "best_score": resume_state["best_score"],
                "best_candidate_id": resume_state["best_candidate_id"],
                "converged": False,
            }
        summary.setdefault("topology_mode", cfg.topology_mode)
        summary["termination_reason"] = "already_reached_max_rounds"
        summary["resumed"] = True
        summary["resumed_from_round"] = resumed_from_round
        summary.setdefault("paths", {})
        summary["paths"]["seed_manifest"] = str(cfg.seed_manifest_path)
        summary["paths"]["operator_language"] = str(cfg.operator_language_path)
        summary = _postprocess_campaign_outputs(cfg, summary)
        _write_json(cfg.summary_path, summary)
        return summary

    if resume_state and resume_state["approaches"]:
        sources = resume_state["sources"]
        approaches = resume_state["approaches"]
        skipped = resume_state["skipped"]
    else:
        corpus = agent_c.run(cfg, trace=trace)
        approaches = agent_ob.score_approaches(corpus.approaches)
        sources = corpus.sources
        skipped = corpus.skipped
        _write_json(
            cfg.approach_map_path,
            {
                "campaign_id": cfg.campaign_id,
                "sources": [item.to_dict() for item in sources],
                "approaches": [item.to_dict() for item in approaches],
                "skipped": list(skipped),
            },
        )

    if resume_state and not cfg.approach_map_path.exists():
        _write_json(
            cfg.approach_map_path,
            {
                "campaign_id": cfg.campaign_id,
                "sources": [item.to_dict() for item in sources],
                "approaches": [item.to_dict() for item in approaches],
                "skipped": list(skipped),
            },
        )

    sources_by_id = {item.source_id: item for item in sources}
    approaches_by_id = {item.approach_id: item for item in approaches}
    operator_calibration = build_calibration_report(approaches, cfg.operator_framework_path)
    _write_json(cfg.operator_calibration_path, operator_calibration)

    history: list[dict[str, Any]] = list(resume_state["history"]) if resume_state else []
    prior_eval_summaries: tuple[dict[str, Any], ...] = resume_state["prior_eval_summaries"] if resume_state else ()
    feedback: dict[str, tuple[str, ...]] = resume_state["feedback"] if resume_state else {}
    no_improve_count = int(resume_state["no_improve_count"]) if resume_state else 0
    best_score = float(resume_state["best_score"]) if resume_state else -1.0
    best_candidate_id = str(resume_state["best_candidate_id"]) if resume_state else ""
    best_dossier_path = str(resume_state["best_dossier_path"]) if resume_state else ""
    total_hypotheses = int(resume_state["total_hypotheses"]) if resume_state else 0
    family_usage: dict[str, int] = dict(resume_state["family_usage"]) if resume_state else {}
    termination_reason = "max_rounds_exhausted"
    converged = False
    failure_history: list[dict[str, Any]] = []
    campaign_failure_counts: dict[str, int] = {}

    lean_ledger = LeanResidueLedger(cfg.lean_rh_root)
    lean_snapshot_before = lean_ledger.snapshot()
    lean_residue_log: list[dict[str, Any]] = []
    external_evaluator = ExternalEvaluator()
    external_eval_log: list[dict[str, Any]] = []

    for round_index in range(resumed_from_round + 1, cfg.max_rounds + 1):
        hypotheses = agent_a.run(
            approaches,
            round_index=round_index,
            max_hypotheses=cfg.max_hypotheses_per_round,
            topology_mode=cfg.topology_mode,
            prior_evaluations=prior_eval_summaries,
            feedback=feedback,
            family_usage=family_usage,
            family_coverage_round_limit=cfg.family_coverage_round_limit,
            overused_family_penalty_start_round=cfg.overused_family_penalty_start_round,
            overused_family_penalty_threshold=cfg.overused_family_penalty_threshold,
            overused_family_penalty_scale=cfg.overused_family_penalty_scale,
            overused_family_penalty_cap=cfg.overused_family_penalty_cap,
            preferred_route_family=cfg.preferred_route_family,
            route_lock_strict=cfg.route_lock_strict,
            route_lock_bonus_primary=cfg.route_lock_bonus_primary,
            route_lock_bonus_support=cfg.route_lock_bonus_support,
            route_lock_penalty_off_route=cfg.route_lock_penalty_off_route,
        )
        total_hypotheses += len(hypotheses)
        for hypothesis in hypotheses:
            for family in hypothesis.ingredient_families:
                family_usage[family] = family_usage.get(family, 0) + 1
        novelties = agent_m.run(hypotheses) + agent_q.run(hypotheses) + agent_t.run(hypotheses)
        if cfg.topology_mode in ("klein", "hyperloop"):
            novelties += agent_k.run(
                hypotheses,
                campaign_failure_counts=campaign_failure_counts,
            )
        proposals = agent_b.plan(hypotheses, novelties)
        executions = agent_b.execute(
            proposals,
            hypotheses,
            novelties,
            cfg,
            round_index=round_index,
            trace=trace,
        )
        execution_by_id = {item.hypothesis_id: item for item in executions}
        proposal_by_id = {item.hypothesis_id: item for item in proposals}

        evaluations = []
        round_dossier_paths: dict[str, str] = {}
        for hypothesis in hypotheses:
            proposal = proposal_by_id[hypothesis.candidate_id]
            execution = execution_by_id[hypothesis.candidate_id]
            linked_novelties = tuple(
                artifact
                for artifact in novelties
                if artifact.linked_hypothesis_id in {"", hypothesis.candidate_id}
            )
            evaluation = agent_ob.evaluate(
                hypothesis,
                proposal,
                execution,
                approaches_by_id=approaches_by_id,
                novelty_artifacts=linked_novelties,
                round_index=round_index,
                previous_best_score=best_score,
                cfg=cfg,
            )
            evaluations.append(evaluation)
            review_bundle = agent_ob.build_review_bundle(
                evaluation,
                hypothesis,
                proposal,
                approaches_by_id=approaches_by_id,
                sources_by_id=sources_by_id,
            )
            memory.ingest_review_bundle(review_bundle)
            pointer = dossier_writer.write(
                review_bundle,
                campaign_id=cfg.campaign_id,
                family="riemann",
                trace=trace,
                memory=memory,
            )
            round_dossier_paths[hypothesis.candidate_id] = pointer.path
            trace.log_decision(
                hypothesis.candidate_id,
                decision="promote" if evaluation.promoted else "iterate",
                reason=f"score={evaluation.score:.4f}",
            )
            if evaluation.score > best_score:
                best_dossier_path = pointer.path

        evaluations_tuple = tuple(sorted(evaluations, key=lambda item: (-item.score, item.candidate_id)))
        round_best_score = evaluations_tuple[0].score if evaluations_tuple else -1.0
        if round_best_score > best_score + 1e-6:
            best_score = round_best_score
            best_candidate_id = evaluations_tuple[0].candidate_id
            best_dossier_path = round_dossier_paths.get(best_candidate_id, best_dossier_path)
            no_improve_count = 0
        else:
            no_improve_count += 1

        routing = agent_ob.route(
            evaluations_tuple,
            no_improve_count=no_improve_count,
            cfg=cfg,
        )
        round_failure_counts = _collect_round_failure_counts(hypotheses, proposals, novelties, evaluations_tuple)
        failure_history.append(
            {
                "round_index": round_index,
                "failure_counts": round_failure_counts,
            }
        )
        for key, value in round_failure_counts.items():
            campaign_failure_counts[key] = campaign_failure_counts.get(key, 0) + value
        routing = replace(
            routing,
            feedback=merge_feedback(routing.feedback, _feedback_from_failure_counts(round_failure_counts)),
        )
        if cfg.topology_mode in ("klein", "hyperloop"):
            routing = replace(
                routing,
                feedback=merge_feedback(routing.feedback, klein_feedback_from_failure_counts(round_failure_counts)),
            )
        round_record = CampaignRoundRecord(
            round_index=round_index,
            hypotheses=hypotheses,
            proposals=proposals,
            novelty_artifacts=novelties,
            evaluations=evaluations_tuple,
            routing=routing,
        )
        _write_json(
            cfg.campaign_dir / f"round_{round_index:03d}_hypotheses.json",
            [item.to_dict() for item in hypotheses],
        )
        _write_json(
            cfg.campaign_dir / f"round_{round_index:03d}_proposals.json",
            [item.to_dict() for item in proposals],
        )
        _write_json(
            cfg.campaign_dir / f"round_{round_index:03d}_novelty.json",
            [item.to_dict() for item in novelties],
        )
        _write_json(
            cfg.campaign_dir / f"round_{round_index:03d}_evaluations.json",
            [item.to_dict() for item in evaluations_tuple],
        )
        # Persist per-candidate Lean skeletons so the residue ledger sees new decls each round.
        hypothesis_lookup = {item.candidate_id: item for item in hypotheses}
        candidate_skeletons: list[tuple[str, str]] = []
        external_candidate_records: list[dict[str, Any]] = []
        for evaluation in evaluations_tuple:
            hypothesis = hypothesis_lookup.get(evaluation.candidate_id)
            obligations = (
                tuple(getattr(hypothesis, "unresolved_proof_obligations", ()))
                if hypothesis is not None
                else ()
            )
            obligation_snapshot = {
                "open_obligation_classes": {ob: 1 for ob in obligations},
            }
            # Suffix with campaign_id + round so decl names stay unique across both rounds
            # AND across campaigns that share the same seed-derived candidate IDs.
            campaign_tag = "".join(ch if ch.isalnum() else "_" for ch in cfg.campaign_id)[:32]
            unique_candidate_id = f"{evaluation.candidate_id}_c{campaign_tag}_r{round_index:03d}"
            # Build ingredient_families BEFORE the skeleton so Phase 2 reasoning-derived
            # window can use them.
            ingredient_families = tuple(
                getattr(hypothesis, "ingredient_families", ())
            ) if hypothesis is not None else ()
            skeleton = _generate_lean_skeleton(
                unique_candidate_id,
                obligation_snapshot,
                ingredient_families=ingredient_families,
            )
            candidate_skeletons.append((unique_candidate_id, skeleton))
            external_candidate_records.append({
                "candidate_id": evaluation.candidate_id,
                "ingredient_families": ingredient_families,
                "closed_obligation_count": 0,  # baseline floor; real closures are tracked elsewhere
                "open_obligation_count": len(obligations),
                "lean_skeleton": skeleton,
            })
        if candidate_skeletons:
            write_round_skeletons(
                lean_rh_root=cfg.lean_rh_root,
                campaign_id=cfg.campaign_id,
                round_index=round_index,
                candidate_skeletons=candidate_skeletons,
            )
        lean_snapshot_after = lean_ledger.snapshot()
        lean_delta = lean_ledger.diff(lean_snapshot_before, lean_snapshot_after)
        persistent_obstruction_count = len(campaign_failure_counts)
        lean_gate_passed, lean_gate_reason = lean_ledger.gate(
            lean_delta, persistent_obstruction_count=persistent_obstruction_count
        )
        lean_residue_entry = {
            "round_index": round_index,
            "delta": lean_ledger.to_dict(lean_delta),
            "gate_passed": lean_gate_passed,
            "gate_reason": lean_gate_reason,
        }
        lean_residue_log.append(lean_residue_entry)
        lean_snapshot_before = lean_snapshot_after
        if not lean_gate_passed and verbose:
            print(f"  [lean] RESIDUE_GATE_FAIL round {round_index}: {lean_gate_reason}")
        # External Odlyzko consistency benchmark — runs every round, all topology modes.
        # Provides the moving-target external scorecard that Gate 7 requires.
        external_report = external_evaluator.run(
            campaign_id=cfg.campaign_id,
            internal_score=round_best_score if evaluations_tuple else 0.0,
            lean_candidates=external_candidate_records,
        )
        odlyzko_result = next(
            (r for r in external_report.external_scores if r.benchmark_id == "odlyzko_zero_consistency"),
            None,
        )
        external_eval_log.append({
            "round_index": round_index,
            "internal_score": external_report.internal_score,
            "odlyzko_score": odlyzko_result.score if odlyzko_result else 0.0,
            "odlyzko_available": odlyzko_result.available if odlyzko_result else False,
            "odlyzko_details": dict(odlyzko_result.details) if odlyzko_result else {},
            "mean_external": external_report.mean_external,
            "replan_triggered": external_report.replan_triggered,
            "replan_reason": external_report.replan_reason,
        })
        if verbose and odlyzko_result and odlyzko_result.available:
            print(
                f"  [external] odlyzko_score={odlyzko_result.score:.4f} "
                f"(internal={external_report.internal_score:.4f}, "
                f"contradicted={odlyzko_result.details.get('contradicted_count', 0)})"
            )
        checkpoint_path = cfg.checkpoints_dir / f"round_{round_index:03d}.json"
        if cfg.checkpoint_every_round:
            _write_json(checkpoint_path, round_record.to_dict())

        round_payload = {
            "round_index": round_index,
            "best_candidate_id": evaluations_tuple[0].candidate_id if evaluations_tuple else "",
            "best_score": round_best_score if evaluations_tuple else 0.0,
            "routing": routing.to_dict(),
            "checkpoint_path": str(checkpoint_path),
        }
        history.append(round_payload)
        hypothesis_by_id = {item.candidate_id: item for item in hypotheses}
        prior_eval_summaries = tuple(
            {
                "candidate_id": item.candidate_id,
                "score": item.score,
                "ingredient_approach_ids": hypothesis_by_id[item.candidate_id].ingredient_approach_ids,
            }
            for item in evaluations_tuple
        )
        feedback = routing.feedback

        if verbose:
            print(
                f"round {round_index:>2}  hypotheses={len(hypotheses):>2}  "
                f"best={round_best_score:.4f}  feedback={','.join(sorted(routing.feedback)) or '-'}"
            )

        if routing.target == "stop":
            termination_reason = routing.stop_reason or routing.reason
            converged = routing.stop_reason == "proof_target_reached"
            break
    else:
        termination_reason = "max_rounds_exhausted"

    memory.flush()
    memory.end_session()
    trace_path = trace.flush()
    summary = {
        "campaign_id": cfg.campaign_id,
        "proof_target": cfg.proof_target,
        "topology_mode": cfg.topology_mode,
        "preferred_route_family": cfg.preferred_route_family,
        "route_lock_strict": cfg.route_lock_strict,
        "seed_pack_names": list(cfg.seed_pack_names),
        "source_count": len(sources),
        "skipped_source_count": len(skipped),
        "approach_count": len(approaches),
        "rounds_run": len(history),
        "total_hypotheses": total_hypotheses,
        "best_score": max(best_score, 0.0),
        "best_candidate_id": best_candidate_id,
        "best_dossier_path": best_dossier_path,
        "converged": converged,
        "termination_reason": termination_reason,
        "resumed": resumed,
        "resumed_from_round": resumed_from_round,
        "family_usage": dict(sorted(family_usage.items())),
        "history": history,
        "lean_residue_gate_failures": sum(1 for e in lean_residue_log if not e["gate_passed"]),
        "lean_residue_log": lean_residue_log,
        "external_eval_log": external_eval_log,
        "external_eval_summary": {
            "rounds_evaluated": len(external_eval_log),
            "mean_odlyzko_score": (
                sum(e["odlyzko_score"] for e in external_eval_log) / len(external_eval_log)
                if external_eval_log else 0.0
            ),
            "max_odlyzko_score": (
                max((e["odlyzko_score"] for e in external_eval_log), default=0.0)
            ),
            "replan_triggered_count": sum(1 for e in external_eval_log if e["replan_triggered"]),
            "internal_external_gap": (
                (sum(e["internal_score"] for e in external_eval_log)
                 - sum(e["odlyzko_score"] for e in external_eval_log))
                / len(external_eval_log) if external_eval_log else 0.0
            ),
        },
        "memory_summary": memory.summary(),
        "trace_path": str(trace_path),
        "paths": {
            "campaign_dir": str(cfg.campaign_dir),
            "approach_map": str(cfg.approach_map_path),
            "summary": str(cfg.summary_path),
            "seed_manifest": str(cfg.seed_manifest_path),
            "operator_language": str(cfg.operator_language_path),
            "operator_calibration": str(cfg.operator_calibration_path),
            "failure_atlas": str(cfg.failure_atlas_path),
            "certificate_report": str(cfg.certificate_report_path),
            "obligation_ledger": str(cfg.obligation_ledger_path),
            "campaign_benchmark": str(cfg.campaign_benchmark_path),
            "dead_end_library": str(cfg.dead_end_library_path),
            "lean_residue": str(cfg.lean_residue_path),
            "checkpoints_dir": str(cfg.checkpoints_dir),
            "dossiers_dir": str(cfg.dossiers_dir),
        },
    }
    _write_json(cfg.lean_residue_path, lean_residue_log)
    _write_json(
        cfg.failure_atlas_path,
        {
            "campaign_id": cfg.campaign_id,
            "failure_counts": campaign_failure_counts,
            "rounds": failure_history,
        },
    )
    summary = _postprocess_campaign_outputs(cfg, summary)
    _write_json(cfg.summary_path, summary)
    try:
        from .visualization import write_all_results_dashboard, write_campaign_dashboard

        dashboard_path = write_campaign_dashboard(cfg.campaign_dir, cfg.dashboard_path)
        summary["paths"]["dashboard"] = str(dashboard_path)
        all_results_path = write_all_results_dashboard(cfg.research_root)
        summary["paths"]["all_results_dashboard"] = str(all_results_path)
    except Exception as exc:  # pragma: no cover - dashboard depends on optional viz stack
        summary["paths"]["dashboard_error"] = str(exc)
    literature_paths = write_literature_connection_outputs(cfg.campaign_dir)
    if literature_paths is not None:
        summary["paths"].update(literature_paths)
    try:
        from .graph_builder import build_graph
        from pathlib import Path as _Path
        import json as _json

        _graph_out = _Path(__file__).parent.parent.parent / "data" / "riemann" / "reports" / "rh_graph.json"
        _graph = build_graph(cfg.research_root)
        _graph_out.write_text(_json.dumps(_graph, indent=2, ensure_ascii=False), encoding="utf-8")
        summary["paths"]["rh_graph"] = str(_graph_out)
    except Exception as exc:  # pragma: no cover - graph builder is optional
        summary["paths"]["rh_graph_error"] = str(exc)
    _write_json(cfg.summary_path, summary)
    return summary
