"""Agent Ob — baseline approach scoring, recursive review, and routing."""
from __future__ import annotations

from dataclasses import replace

from src.oae.kernel.schemas import Citation, RankedMechanism, ReviewBundle, TheoryCard

from .config import RiemannResearchConfig
from .dead_end_library import classify_dead_end_patterns, dead_end_penalty
from .obligation_ledger import build_candidate_obligation_snapshot
from .schemas import (
    AlgorithmExecution,
    AlgorithmProposal,
    ApproachCard,
    EvaluationComponents,
    HypothesisCandidate,
    NoveltyArtifact,
    ResearchEvaluation,
    RoutingDecision,
)

_BASELINE_PROXIMITY = {
    "hilbert_polya": 0.78,
    "explicit_formula": 0.74,
    "xi_function": 0.68,
    "de_branges": 0.64,
    "hardy_z": 0.58,
    "random_matrix": 0.52,
    "mollifier_moment": 0.48,
    "quantum_spectral": 0.42,
    "geometric_visualization": 0.36,
    "general_analytic": 0.30,
}


class ObserverAgent:
    """Score approaches and recursive campaign rounds against proof-oriented goals."""

    name = "Ob"

    def score_approaches(self, approaches: tuple[ApproachCard, ...]) -> tuple[ApproachCard, ...]:
        scored = []
        for card in approaches:
            contradiction = min(1.0, 0.12 * len(card.known_blockers))
            baseline = max(0.0, _BASELINE_PROXIMITY.get(card.family, 0.30) - 0.04 * len(card.proof_obligations))
            scored.append(
                replace(
                    card,
                    observer_scores={
                        **card.observer_scores,
                        "baseline_proximity": baseline,
                        "contradiction_burden": contradiction,
                        "unresolved_obligation_count": float(len(card.proof_obligations)),
                    },
                )
            )
        return tuple(sorted(scored, key=lambda item: (-item.observer_scores["baseline_proximity"], item.approach_id)))

    def evaluate(
        self,
        hypothesis: HypothesisCandidate,
        proposal: AlgorithmProposal,
        execution: AlgorithmExecution,
        *,
        approaches_by_id: dict[str, ApproachCard],
        novelty_artifacts: tuple[NoveltyArtifact, ...],
        round_index: int,
        previous_best_score: float,
        cfg: RiemannResearchConfig,
    ) -> ResearchEvaluation:
        passed_checks = [item for item in execution.executed_checks if item.passed]
        accepted_novelty = [
            artifact.artifact_id
            for artifact in novelty_artifacts
            if artifact.artifact_id in proposal.modelling_tasks and artifact.is_testable
        ]
        failed_certificate_checks = tuple(
            item.check_id
            for item in execution.executed_checks
            if item.category == "certificate" and not item.passed
        )
        passed_certificate_checks = tuple(
            item.check_id
            for item in execution.executed_checks
            if item.category == "certificate" and item.passed
        )
        dead_end_patterns = classify_dead_end_patterns(
            ingredient_families=hypothesis.ingredient_families,
            raw_obligations=hypothesis.unresolved_proof_obligations,
            risk_flags=hypothesis.risk_flags,
            novelty_failure_modes=(
                mode
                for artifact in novelty_artifacts
                for mode in artifact.failure_modes
            ),
            failed_certificate_checks=failed_certificate_checks,
            passed_certificate_checks=passed_certificate_checks,
            claim_text=hypothesis.claim,
            approach_text=(
                f"{approaches_by_id[approach_id].summary}\n{approaches_by_id[approach_id].core_claim}"
                for approach_id in hypothesis.ingredient_approach_ids
                if approach_id in approaches_by_id
            ),
        )
        obligation_snapshot = build_candidate_obligation_snapshot(
            candidate_id=hypothesis.candidate_id,
            round_index=round_index,
            raw_obligations=hypothesis.unresolved_proof_obligations,
            check_results=tuple(item.to_dict() for item in execution.executed_checks),
            score=previous_best_score,
            dead_end_patterns=dead_end_patterns,
        )
        rejected_novelty = list(proposal.rejected_novelty_ids)
        proof_reduction = float(obligation_snapshot["proof_obligation_reduction"])
        contradiction_penalty = min(
            1.0,
            0.10 * len(hypothesis.risk_flags)
            + 0.15 * len(rejected_novelty)
            + 0.20 * max(0.0, 0.60 - execution.consistency_with_known_results)
            + dead_end_penalty(dead_end_patterns),
        )
        novelty_score = min(1.0, len(accepted_novelty) / max(1, len(proposal.modelling_tasks)))

        components = EvaluationComponents(
            proof_obligation_reduction=proof_reduction,
            consistency_with_known_results=execution.consistency_with_known_results,
            reproducibility=execution.reproducibility,
            contradiction_penalty=contradiction_penalty,
            numerical_support=execution.numerical_support,
            novelty=novelty_score,
            visualization_coherence=novelty_score if any(item.startswith("m-") for item in accepted_novelty) else 0.0,
        )
        score = self._composite_score(components, cfg)

        resolved = tuple(
            item["obligation_class"]
            for item in obligation_snapshot["obligation_reports"]
            if item["status"] == "resolved"
        )
        unresolved = tuple(
            item["obligation_class"]
            for item in obligation_snapshot["obligation_reports"]
            if item["status"] != "resolved"
        )
        recommended_actions = self._recommended_actions(
            components,
            hypothesis,
            accepted_novelty,
            failed_certificate_checks,
            dead_end_patterns,
        )
        contradiction_parts = list(hypothesis.risk_flags)
        contradiction_parts.extend(f"failed_certificate:{item}" for item in failed_certificate_checks)
        contradiction_parts.extend(f"dead_end:{item}" for item in dead_end_patterns)
        contradiction_summary = "; ".join(contradiction_parts or ("none",))
        return ResearchEvaluation(
            candidate_id=hypothesis.candidate_id,
            round_index=round_index,
            score=score,
            components=components,
            contradiction_summary=contradiction_summary,
            progress_delta=score - max(previous_best_score, 0.0),
            unresolved_obligations=unresolved,
            resolved_obligations=resolved,
            check_results=execution.executed_checks,
            novelty_artifact_ids=tuple(accepted_novelty),
            recommended_actions=recommended_actions,
            dead_end_patterns=dead_end_patterns,
            promoted=score >= cfg.proof_target and contradiction_penalty < 0.30,
        )

    def route(
        self,
        evaluations: tuple[ResearchEvaluation, ...],
        *,
        no_improve_count: int,
        cfg: RiemannResearchConfig,
    ) -> RoutingDecision:
        if not evaluations:
            return RoutingDecision(
                target="stop",
                reason="No hypotheses were produced for review.",
                continue_loop=False,
                stop_reason="empty_round",
            )
        best = max(evaluations, key=lambda item: item.score)
        if best.promoted:
            return RoutingDecision(
                target="stop",
                reason="Proof-progress target reached with acceptable contradiction burden.",
                continue_loop=False,
                stop_reason="proof_target_reached",
            )
        if no_improve_count >= cfg.patience:
            return RoutingDecision(
                target="stop",
                reason="No improvement budget exhausted.",
                continue_loop=False,
                stop_reason="patience_exhausted",
            )

        feedback: dict[str, tuple[str, ...]] = {}
        if best.components.proof_obligation_reduction < 0.40:
            feedback["C"] = (
                "pull additional sources around the unresolved obligations",
                "prefer approaches with fewer theorem-sized gaps",
            )
            feedback["A"] = (
                "synthesize narrower hypotheses with fewer unresolved obligations",
            )
        if best.components.consistency_with_known_results < 0.65:
            feedback["B"] = (
                "strengthen critical-line and explicit-formula checks",
                "reject hypotheses that only survive soft heuristics",
            )
        if "explicit_formula_tail_control" in best.unresolved_obligations:
            feedback["B"] = feedback.get("B", ()) + (
                "split tail-control work from exclusion work and raise explicit-formula tail margins directly",
            )
            feedback["T"] = feedback.get("T", ()) + (
                "emit a tail-budget decomposition with explicit decay, error-budget, and window-escape obligations",
                "only promote tail-control artifacts that can be translated back into exclusion work",
            )
        if {
            "explicit_formula_tail_control",
            "xi_coefficient_exclusion_bridge",
        } <= set(best.unresolved_obligations):
            feedback["B"] = feedback.get("B", ()) + (
                "for explicit_formula + xi_function branches, require a shared xi-tail bridge instead of treating tail control and coefficient bridging as separate near-miss checks",
            )
            feedback["T"] = feedback.get("T", ()) + (
                "emit a xi-facing tail-return bridge that improves both the remainder budget and the coefficient bridge at once",
            )
        if "statistical_to_theorem_upgrade" in best.unresolved_obligations:
            feedback["A"] = feedback.get("A", ()) + (
                "pair statistical lanes with explicit-formula or xi-function exclusion scaffolds before promotion",
            )
            feedback["B"] = feedback.get("B", ()) + (
                "treat critical-line concentration as advisory until it produces an exclusion margin against exceptional off-line zeros",
            )
        if "visual_or_surrogate_translation" in best.unresolved_obligations:
            feedback["M"] = feedback.get("M", ()) + (
                "promote contour intersections and 2pi-normalized zero atlases into xi-facing invariants instead of descriptive plots",
            )
            feedback["B"] = feedback.get("B", ()) + (
                "treat atlas-level pi normalization and zero sums as advisory until they support a xi-based exclusion bridge",
            )
        if "lp_equivalent_reformulation" in best.dead_end_patterns:
            feedback["C"] = feedback.get("C", ()) + (
                "pull sources on unconditional Lyapunov, transport, entropy, or dissipation functionals that do not just restate LP-class or de Branges membership",
            )
            feedback["A"] = feedback.get("A", ()) + (
                "avoid branches that merely restate RH as LP-class, Hermite-Biehler, or de Branges membership unless they also add an independent exclusion or dissipation mechanism",
            )
        if "conditional_heat_flow_monotonicity" in best.dead_end_patterns:
            feedback["A"] = feedback.get("A", ()) + (
                "prefer unconditional backward-heat-flow invariants over Rodgers-Tao, zero-ODE, or conditional real-zero monotonicity restatements",
            )
            feedback["B"] = feedback.get("B", ()) + (
                "reject heat-flow monotonicity claims unless they remain valid off the real-zero locus and yield a measurable certificate margin",
            )
            feedback["T"] = feedback.get("T", ()) + (
                "pair any heat-flow branch with explicit global error, tail, or escape control instead of local zero-motion numerics alone",
            )
        if best.components.contradiction_penalty > 0.35:
            feedback["A"] = feedback.get("A", ()) + (
                "drop contradictory assumption mixes",
            )
        if best.components.numerical_support < 0.70:
            feedback["B"] = feedback.get("B", ()) + (
                "rerun the numeric worker with a stronger support threshold",
            )
        if not best.novelty_artifact_ids:
            feedback["M"] = (
                "translate visuals into measurable invariants only",
                "emit canonical operator signatures with explicit proof-skeleton obligations",
            )
            feedback["Q"] = (
                "emit only simulator-backed claims with explicit validation recipes",
                "prefer bounded self-adjoint surrogates over generic quantum analogies",
            )
            feedback["T"] = feedback.get("T", ()) + (
                "emit tail-budget artifacts instead of more descriptive explicit-formula summaries",
            )
        if not feedback:
            feedback["A"] = (
                "convert the current best evidence package into a stronger exclusion argument",
            )
        if cfg.topology_mode == "klein":
            feedback["A"] = feedback.get("A", ()) + (
                "force the next branch to pair a surface-rigor lane with a depth-local lane",
            )
            feedback["B"] = feedback.get("B", ()) + (
                "require a surface-return certificate before treating the branch as progress",
            )
        return RoutingDecision(
            target="iterate",
            reason="Continue the recursive review/testing loop.",
            continue_loop=True,
            feedback=feedback,
        )

    def build_review_bundle(
        self,
        evaluation: ResearchEvaluation,
        hypothesis: HypothesisCandidate,
        proposal: AlgorithmProposal,
        *,
        approaches_by_id: dict[str, ApproachCard],
        sources_by_id: dict[str, object],
    ) -> ReviewBundle:
        citations = []
        for approach_id in hypothesis.ingredient_approach_ids:
            for source_id in approaches_by_id[approach_id].cited_sources:
                source = sources_by_id[source_id]
                citations.append(
                    Citation(
                        source=source.locator,
                        title=source.title,
                        year=source.year,
                        authors=source.authors,
                        confidence=1.0,
                    )
                )
        citations_tuple = tuple(citations)
        support_level = "strong" if evaluation.score >= 0.80 else "moderate" if evaluation.score >= 0.60 else "weak"
        contradiction_level = "blocking" if evaluation.components.contradiction_penalty >= 0.60 else "major" if evaluation.components.contradiction_penalty >= 0.40 else "minor" if evaluation.components.contradiction_penalty > 0 else "none"
        mechanism = " + ".join(hypothesis.ingredient_families)
        card = TheoryCard(
            claim=hypothesis.claim,
            mechanism=mechanism,
            conditions=f"round {evaluation.round_index}",
            support_level=support_level,
            contradiction_level=contradiction_level,
            support_score=evaluation.score,
            contradiction_score=evaluation.components.contradiction_penalty,
            citations=citations_tuple,
            tags=hypothesis.ingredient_families,
        )
        ranked = RankedMechanism(
            mechanism=mechanism,
            rank=1,
            probability=evaluation.score,
            discriminating_experiment=" / ".join(item.check_id for item in evaluation.check_results[:3]),
            theory_cards=(card,),
        )
        return ReviewBundle(
            candidate_id=evaluation.candidate_id,
            theory_cards=(card,),
            ranked_mechanisms=(ranked,),
            support_score=evaluation.score,
            contradiction_score=evaluation.components.contradiction_penalty,
            novelty_with_support_score=evaluation.components.novelty,
            review_confidence=evaluation.components.reproducibility,
            recommended_checks=evaluation.recommended_actions or tuple(item.check_id for item in evaluation.check_results if not item.passed),
            citations=citations_tuple,
            provenance={
                "round": str(evaluation.round_index),
                "proposal_id": proposal.proposal_id,
                "agents": "C,A,B,M,Q,K,Ob" if any(item.startswith("k-") for item in evaluation.novelty_artifact_ids) else "C,A,B,M,Q,Ob",
            },
        )

    def _recommended_actions(
        self,
        components: EvaluationComponents,
        hypothesis: HypothesisCandidate,
        accepted_novelty: list[str],
        failed_certificate_checks: tuple[str, ...],
        dead_end_patterns: tuple[str, ...],
    ) -> tuple[str, ...]:
        actions: list[str] = []
        if components.proof_obligation_reduction < 0.40:
            actions.append("reduce unresolved proof obligations before promotion")
        if components.consistency_with_known_results < 0.65:
            actions.append("add stronger explicit-formula and critical-line checks")
        if failed_certificate_checks:
            actions.append("raise certificate margins and convert bounded evidence into a global exclusion argument")
        if "explicit_formula_tail_control" in failed_certificate_checks:
            actions.append("separate explicit-formula tail control from off-line exclusion and tighten the tail bound directly")
        if "zero_atlas_xi_bridge" in failed_certificate_checks:
            actions.append("turn the zero atlas into a xi-facing invariant with explicit count-law and zero-sum tail control")
        if "zero_atlas_exclusion" in failed_certificate_checks:
            actions.append("convert the xi-facing atlas into an actual off-line-zero exclusion margin")
        if not accepted_novelty and any(
            family in {"geometric_visualization", "quantum_spectral"} for family in hypothesis.ingredient_families
        ):
            actions.append("restate novelty as a falsifiable invariant or operator constraint")
            actions.append("keep the operator language low-complexity and canonical")
        if components.contradiction_penalty > 0.35:
            actions.append("drop incompatible assumptions")
        if dead_end_patterns:
            actions.append("avoid repeating known dead-end branches before promotion")
        return tuple(actions or ("continue bounded validation",))

    def _composite_score(
        self,
        components: EvaluationComponents,
        cfg: RiemannResearchConfig,
    ) -> float:
        raw = (
            cfg.weight_proof_obligation_reduction * components.proof_obligation_reduction
            + cfg.weight_consistency_with_known_results * components.consistency_with_known_results
            + cfg.weight_reproducibility * components.reproducibility
            + cfg.weight_numerical_support * components.numerical_support
            + cfg.weight_novelty * components.novelty
            + cfg.weight_visualization_coherence * components.visualization_coherence
            - cfg.weight_contradiction_penalty * components.contradiction_penalty
        )
        return max(0.0, min(1.0, raw))
