"""Agent K — Klein-topology novelty generation for RH research."""
from __future__ import annotations

from .autoformalizer import formalize
from .klein_topology import compute_klein_metrics
from .operator_language import (
    build_proof_skeleton,
    canonicalize_operator_claim,
    complexity_score,
)
from .schemas import HypothesisCandidate, NoveltyArtifact


class KleinAgent:
    """Generate topology-aware round-trip artifacts for cross-lane RH hypotheses."""

    name = "K"

    def run(
        self,
        hypotheses: tuple[HypothesisCandidate, ...],
        *,
        campaign_failure_counts: dict[str, int] | None = None,
    ) -> tuple[NoveltyArtifact, ...]:
        artifacts: list[NoveltyArtifact] = []
        for hypothesis in hypotheses:
            metrics = compute_klein_metrics(
                hypothesis,
                campaign_failure_counts=campaign_failure_counts or {},
            )
            if metrics.bridge_score < 0.45:
                continue
            digest = hypothesis.candidate_id.split("-")[-1]
            artifacts.append(self._surface_return_artifact(hypothesis, digest, metrics))
            if metrics.dominant_obstructions:
                artifacts.append(self._obstruction_cycle_artifact(hypothesis, digest, metrics))
        return tuple(artifacts)

    def _surface_return_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics,
    ) -> NoveltyArtifact:
        validation_recipe = (
            "pick one local critical-line invariant from the depth lane",
            "transport it through xi-function or explicit-formula constraints without losing canonical form",
            "accept the branch only if the returned claim is a stricter off-line-zero exclusion obligation",
        )
        failure_modes = tuple(
            metrics.dominant_obstructions
            or ("finite_window_only", "translation_gap", "global_exclusion_gap")
        )
        canonical = canonicalize_operator_claim(
            operator_family="klein_surface_return",
            operator_primitives=(
                "CRITICAL_RESTRICTION",
                "ARG_VARIATION",
                "XI",
                "ZETA",
                "BOUNDS",
                "DUALIZE",
            ),
            input_types=("zero_statistics_object", "scalar_analytic_function"),
            output_type="inequality_statement",
            assumptions=(
                *hypothesis.assumptions,
                "a valid proof lane must return from local evidence to a global exclusion claim",
            ),
            invariances=("round_trip_canonicality", "surface_depth_reintegration"),
        )
        complexity, terms = complexity_score(
            node_count=6,
            depth=4,
            primitive_families=4,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics.total_score),
            auxiliary_lemma_count=max(2, len(hypothesis.unresolved_proof_obligations)),
            contour_fragility_penalty=0.05,
        )
        exact_claim = (
            "Any Klein-mode RH branch must carry one local critical-line invariant through the "
            "surface analytic lane and return with a stronger off-line-zero exclusion certificate, "
            "not merely another local match or descriptive identity."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "close the round trip from local invariant to global exclusion step",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        surface_obligations = (
            *hypothesis.unresolved_proof_obligations,
            "close the round trip from local invariant to global exclusion step",
        )
        formal = formalize(
            exact_claim,
            obligations=tuple(surface_obligations),
            candidate_id=f"k-surface-return-{digest}",
        )
        lean_skeleton = formal.lean_source
        return NoveltyArtifact(
            artifact_id=f"k-surface-return-{digest}",
            agent="K",
            title="Klein Surface Return",
            observation=(
                "The hypothesis spans both a depth-local lane and a surface-rigor lane, so it can "
                "be tested as a true round-trip branch instead of another one-way heuristic."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "surface_ratio": metrics.surface_ratio,
                "depth_ratio": metrics.depth_ratio,
                "bridge_score": metrics.bridge_score,
                "reintegration_score": metrics.reintegration_score,
                "homology_signal": metrics.homology_signal,
            },
            operator_family="klein_surface_return",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            lean_skeleton=lean_skeleton,
            failure_modes=failure_modes,
        )

    def _obstruction_cycle_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics,
    ) -> NoveltyArtifact:
        validation_recipe = (
            "compare the hypothesis against the current failure atlas",
            "name the dominant obstruction classes that still survive the branch",
            "treat the branch as progress only if at least one persistent obstruction class is reduced or eliminated",
        )
        failure_modes = tuple(metrics.dominant_obstructions)
        canonical = canonicalize_operator_claim(
            operator_family="klein_obstruction_cycle",
            operator_primitives=(
                "ZERO_COUNT",
                "BOUNDS",
                "TRACE_FORMULA",
                "RESTRICT",
                "DUALIZE",
            ),
            input_types=("inequality_statement", "spectral_object"),
            output_type="inequality_statement",
            assumptions=(
                *hypothesis.assumptions,
                "persistent failure classes are treated as named obstructions, not generic bad luck",
            ),
            invariances=("obstruction_class_tracking",),
        )
        complexity, terms = complexity_score(
            node_count=5,
            depth=3,
            primitive_families=3,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics.homology_signal),
            auxiliary_lemma_count=max(1, len(metrics.dominant_obstructions)),
            spectral_nonconstructiveness_penalty=0.05,
        )
        exact_claim = (
            "A Klein-mode RH branch only counts as real progress if it kills at least one named "
            "persistent obstruction class instead of collecting another bounded local success."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                *metrics.dominant_obstructions,
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        obstruction_obligations = (
            *hypothesis.unresolved_proof_obligations,
            *metrics.dominant_obstructions,
        )
        formal = formalize(
            exact_claim,
            obligations=tuple(obstruction_obligations),
            candidate_id=f"k-obstruction-cycle-{digest}",
        )
        lean_skeleton = formal.lean_source
        return NoveltyArtifact(
            artifact_id=f"k-obstruction-cycle-{digest}",
            agent="K",
            title="Klein Obstruction Cycle",
            observation=(
                "The failure atlas is treated as a topological map of recurring holes in the search "
                "space. The branch is only interesting if it collapses one of them."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "obstruction_score": metrics.obstruction_score,
                "homology_signal": metrics.homology_signal,
                "noise_penalty": max(0.0, 1.0 - metrics.noise_penalty),
                "total_score": metrics.total_score,
            },
            operator_family="klein_obstruction_cycle",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            lean_skeleton=lean_skeleton,
            failure_modes=failure_modes,
        )
