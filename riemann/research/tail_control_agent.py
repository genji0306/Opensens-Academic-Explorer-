"""Agent T — explicit-formula tail-control synthesis."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from riemann.core.config import REPORT_DIR

from .operator_language import (
    build_proof_skeleton,
    canonicalize_operator_claim,
    complexity_score,
)
from .schemas import HypothesisCandidate, NoveltyArtifact

_EXPLICIT_DATA = REPORT_DIR / "rh_explicit_data.json"
_STRIP_DATA = REPORT_DIR / "rh_strip_data.json"
_PROJECTION_DATA = REPORT_DIR / "rh_projection_data.json"


class TailControlAgent:
    """Emit explicit-formula tail-control artifacts instead of more bounded narration."""

    name = "T"

    def run(
        self,
        hypotheses: tuple[HypothesisCandidate, ...],
    ) -> tuple[NoveltyArtifact, ...]:
        explicit = self._read_json(_EXPLICIT_DATA)
        strip = self._read_json(_STRIP_DATA)
        projection = self._read_json(_PROJECTION_DATA)
        metrics = self._derive_metrics(explicit, strip, projection)

        artifacts: list[NoveltyArtifact] = []
        for hypothesis in hypotheses:
            if "explicit_formula" not in set(hypothesis.ingredient_families):
                continue
            digest = hypothesis.candidate_id.split("-")[-1]
            artifacts.append(self._tail_budget_artifact(hypothesis, digest, metrics))
            if {"explicit_formula", "xi_function"} <= set(hypothesis.ingredient_families):
                artifacts.append(self._xi_tail_bridge_artifact(hypothesis, digest, metrics))
        return tuple(artifacts)

    def _tail_budget_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics: dict[str, float],
    ) -> NoveltyArtifact:
        families = set(hypothesis.ingredient_families)
        family_bonus = 0.0
        if "xi_function" in families:
            family_bonus += 0.05
        if "hardy_z" in families:
            family_bonus += 0.04
        if families & {"hilbert_polya", "quantum_spectral"}:
            family_bonus += 0.03
        exclusion_bridge_score = max(
            0.0,
            min(
                1.0,
                0.54 * metrics["tail_budget_score"]
                + 0.28 * metrics["window_escape_score"]
                + 0.18 * metrics["symmetry_transfer_score"]
                + family_bonus,
            ),
        )

        validation_recipe = (
            "split the explicit formula into a checked finite window and an explicit remainder budget",
            "measure whether the remainder budget survives contour shift and critical-line symmetry without collapsing back to a sampled window",
            "only promote the branch if the remainder budget can be restated as an off-line-zero exclusion obligation",
        )
        failure_modes = (
            "finite_window_only",
            "explicit_formula_is_not_by_itself_a_proof",
            "tail_budget_needs_decay_bound",
        )
        canonical = canonicalize_operator_claim(
            operator_family="explicit_formula_tail_budget",
            operator_primitives=(
                "DIRICHLET_SUM",
                "CONTOUR_INT",
                "SHIFT_CONTOUR",
                "ZERO_COUNT",
                "BOUNDS",
                "SYMMETRIZE",
            ),
            input_types=(
                "scalar_analytic_function",
                "contour_expression",
                "inequality_statement",
            ),
            output_type="inequality_statement",
            assumptions=(
                *hypothesis.assumptions,
                "the explicit formula is rewritten as a checked window plus a remainder budget",
            ),
            invariances=("critical_line_symmetry", "tail_budget_monotonicity"),
        )
        complexity, terms = complexity_score(
            node_count=6,
            depth=4,
            primitive_families=4,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics["tail_budget_score"]),
            auxiliary_lemma_count=max(2, len(hypothesis.unresolved_proof_obligations)),
            branch_cut_penalty=0.08,
            contour_fragility_penalty=max(0.0, 1.0 - metrics["window_escape_score"]) * 0.20,
        )
        exact_claim = (
            "Any explicit-formula hypothesis promoted by the loop must be rewritten as a tail-budget "
            "statement: the verified finite window is only bookkeeping, and the real object is a "
            "remainder bound with explicit decay, error-budget, and contour-escape structure strong "
            "enough to feed a later off-line-zero exclusion step."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "prove the remainder budget survives contour shift and excludes off-line zeros",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        return NoveltyArtifact(
            artifact_id=f"t-tail-budget-{digest}",
            agent="T",
            title="Explicit-Formula Tail Budget",
            observation=(
                "The explicit-formula lane becomes actionable only after it stops reporting local prime/zero "
                "agreement and starts exposing a reusable remainder budget that can escape the sampled window."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "tail_budget_score": metrics["tail_budget_score"],
                "error_budget_score": metrics["error_budget_score"],
                "window_escape_score": metrics["window_escape_score"],
                "symmetry_transfer_score": metrics["symmetry_transfer_score"],
                "exclusion_bridge_score": exclusion_bridge_score,
            },
            operator_family="explicit_formula_tail_budget",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            failure_modes=failure_modes,
            supporting_paths=(
                str(_EXPLICIT_DATA),
                str(_STRIP_DATA),
                str(_PROJECTION_DATA),
            ),
        )

    def _xi_tail_bridge_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics: dict[str, float],
    ) -> NoveltyArtifact:
        xi_tail_bridge_score = max(
            0.0,
            min(
                1.0,
                0.38 * metrics["tail_budget_score"]
                + 0.26 * metrics["error_budget_score"]
                + 0.18 * metrics["window_escape_score"]
                + 0.18 * metrics["symmetry_transfer_score"],
            ),
        )
        coefficient_escape_score = max(
            0.0,
            min(
                1.0,
                0.42 * metrics["symmetry_transfer_score"]
                + 0.30 * metrics["gap_regularity"]
                + 0.16 * metrics["strip_alignment"]
                + 0.12 * metrics["projection_alignment"],
            ),
        )
        exclusion_return_score = max(
            0.0,
            min(
                1.0,
                0.40 * xi_tail_bridge_score
                + 0.34 * coefficient_escape_score
                + 0.26 * metrics["exclusion_bridge_score"],
            ),
        )
        validation_recipe = (
            "rewrite the explicit-formula remainder as a xi-facing regularity budget instead of a separate tail estimate",
            "measure whether the same budget improves both tail escape and coefficient-bridge margins",
            "only promote the branch if the shared budget can be restated as an exclusion-return step rather than another LP-style reformulation",
        )
        failure_modes = (
            "finite_window_only",
            "tail_budget_needs_decay_bound",
            "xi_tail_bridge_needs_exclusion_return",
        )
        canonical = canonicalize_operator_claim(
            operator_family="xi_tail_return_bridge",
            operator_primitives=(
                "DIRICHLET_SUM",
                "CONTOUR_INT",
                "XI_REGULARIZE",
                "COEFFICIENT_MAP",
                "TAIL_BOUND",
                "SYMMETRIZE",
            ),
            input_types=(
                "scalar_analytic_function",
                "entire_function_certificate",
                "inequality_statement",
            ),
            output_type="inequality_statement",
            assumptions=(
                *hypothesis.assumptions,
                "the explicit-formula remainder is transferred through xi-regularity before promotion",
            ),
            invariances=("critical_line_symmetry", "tail_to_xi_transfer"),
        )
        complexity, terms = complexity_score(
            node_count=6,
            depth=5,
            primitive_families=5,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - xi_tail_bridge_score),
            auxiliary_lemma_count=max(2, len(hypothesis.unresolved_proof_obligations)),
            branch_cut_penalty=0.08,
            contour_fragility_penalty=max(0.0, 1.0 - exclusion_return_score) * 0.18,
        )
        exact_claim = (
            "For explicit_formula + xi_function branches, the remainder budget should be promoted only after "
            "it survives a xi-facing transfer step that improves both tail control and coefficient/exclusion "
            "margins at once."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "show the xi-facing transfer strengthens both tail control and the coefficient bridge",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        return NoveltyArtifact(
            artifact_id=f"t-xi-tail-bridge-{digest}",
            agent="T",
            title="Xi Tail-Return Bridge",
            observation=(
                "The explicit-formula remainder should not stay as a separate tail estimate; it should return "
                "through xi-regularity as a shared budget that raises both tail-control and coefficient-bridge pressure."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "xi_tail_bridge_score": xi_tail_bridge_score,
                "coefficient_escape_score": coefficient_escape_score,
                "exclusion_return_score": exclusion_return_score,
                "symmetry_transfer_score": metrics["symmetry_transfer_score"],
            },
            operator_family="xi_tail_return_bridge",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            failure_modes=failure_modes,
            supporting_paths=(
                str(_EXPLICIT_DATA),
                str(_STRIP_DATA),
                str(_PROJECTION_DATA),
            ),
        )

    def _derive_metrics(
        self,
        explicit: dict,
        strip: dict,
        projection: dict,
    ) -> dict[str, float]:
        zeros = np.asarray(explicit.get("zeros", []), dtype=float)
        prime_powers = np.asarray(explicit.get("prime_powers", []), dtype=float)
        strip_zeros = np.asarray(strip.get("zeros", []), dtype=float)
        projection_zeros = np.asarray(projection.get("zeros", []), dtype=float)
        gram_points = np.asarray(projection.get("gram_points", []), dtype=float)
        sigma_grid = np.asarray(strip.get("sigma_grid", []), dtype=float)

        zero_support = float(max(0.0, min(1.0, zeros.size / 200.0)))
        prime_support = 0.0
        prime_weight_balance = 0.0
        if prime_powers.ndim == 2 and prime_powers.shape[1] >= 2:
            prime_support = float(max(0.0, min(1.0, prime_powers.shape[0] / 25.0)))
            weights = prime_powers[:, 1]
            scale = float(np.max(np.abs(weights))) or 1.0
            prime_weight_balance = float(max(0.0, min(1.0, 1.0 - float(np.std(weights / scale)) / 1.4)))

        if zeros.size > 2:
            gaps = np.diff(zeros[: min(40, zeros.size)])
            mean_gap = float(np.mean(gaps)) or 1.0
            gap_cv = float(np.std(gaps) / mean_gap) if mean_gap else 1.0
            gap_regularity = float(max(0.0, min(1.0, 1.0 - gap_cv / 1.4)))
        else:
            gap_regularity = 0.0

        window_span = max(float(explicit.get("x_max", 0.0)) - float(explicit.get("x_min", 0.0)), 0.0)
        window_span_score = float(max(0.0, min(1.0, window_span / 58.0)))
        strip_alignment = self._alignment_score(zeros, strip_zeros)
        projection_alignment = self._alignment_score(strip_zeros, projection_zeros)
        gram_coverage = float(
            max(0.0, min(1.0, gram_points.shape[0] / max(float(projection_zeros.size), 1.0)))
        )
        sigma_width = float(np.max(sigma_grid) - np.min(sigma_grid)) if sigma_grid.size else 0.0
        contour_width_score = float(max(0.0, min(1.0, sigma_width)))
        sigma_crit = float(strip.get("sigma_crit", 0.0))
        symmetry_transfer_score = float(max(0.0, min(1.0, 1.0 - min(1.0, abs(sigma_crit - 0.5) * 20.0))))

        tail_budget_score = float(
            max(
                0.0,
                min(
                    1.0,
                    0.24
                    + 0.18 * prime_support
                    + 0.16 * zero_support
                    + 0.14 * prime_weight_balance
                    + 0.14 * gap_regularity
                    + 0.10 * symmetry_transfer_score
                    + 0.08 * window_span_score,
                ),
            )
        )
        error_budget_score = float(
            max(
                0.0,
                min(
                    1.0,
                    0.20
                    + 0.18 * strip_alignment
                    + 0.16 * projection_alignment
                    + 0.14 * zero_support
                    + 0.12 * prime_support
                    + 0.10 * gram_coverage
                    + 0.10 * symmetry_transfer_score,
                ),
            )
        )
        window_escape_score = float(
            max(
                0.0,
                min(
                    1.0,
                    0.18
                    + 0.24 * window_span_score
                    + 0.18 * contour_width_score
                    + 0.16 * projection_alignment
                    + 0.12 * gram_coverage
                    + 0.12 * symmetry_transfer_score,
                ),
            )
        )

        return {
            "tail_budget_score": tail_budget_score,
            "error_budget_score": error_budget_score,
            "window_escape_score": window_escape_score,
            "symmetry_transfer_score": symmetry_transfer_score,
            "gap_regularity": gap_regularity,
            "strip_alignment": strip_alignment,
            "projection_alignment": projection_alignment,
            "gram_coverage": gram_coverage,
            "exclusion_bridge_score": float(
                max(
                    0.0,
                    min(
                        1.0,
                        0.40 * tail_budget_score
                        + 0.24 * error_budget_score
                        + 0.20 * window_escape_score
                        + 0.16 * symmetry_transfer_score,
                    ),
                )
            ),
        }

    def _alignment_score(self, lhs: np.ndarray, rhs: np.ndarray) -> float:
        m = min(lhs.size, rhs.size)
        if m == 0:
            return 0.0
        lhs = lhs[:m]
        rhs = rhs[:m]
        mean_gap = float(np.mean(np.diff(lhs))) if m > 1 else 1.0
        mean_gap = max(mean_gap, 1.0)
        drift = float(np.mean(np.abs(lhs - rhs)))
        return float(max(0.0, min(1.0, 1.0 - drift / mean_gap)))

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text())
