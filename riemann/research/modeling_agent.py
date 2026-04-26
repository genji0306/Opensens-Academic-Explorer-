"""Agent M — operator-grade geometric modelling from the RH report bundle."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from riemann.core.config import REPORT_DIR

from .operator_language import (
    build_proof_skeleton,
    canonicalize_operator_claim,
    complexity_score,
)
from .schemas import HypothesisCandidate, NoveltyArtifact

_PROJECTION_DATA = REPORT_DIR / "rh_projection_data.json"
_STRIP_DATA = REPORT_DIR / "rh_strip_data.json"
_EXPLICIT_DATA = REPORT_DIR / "rh_explicit_data.json"


class ModelingAgent:
    """Translate projection intuition into canonical, testable operator claims."""

    name = "M"

    def run(
        self,
        hypotheses: tuple[HypothesisCandidate, ...],
    ) -> tuple[NoveltyArtifact, ...]:
        projection = self._read_json(_PROJECTION_DATA)
        strip = self._read_json(_STRIP_DATA)
        explicit = self._read_json(_EXPLICIT_DATA)
        metrics = self._derive_metrics(projection, strip, explicit)

        artifacts: list[NoveltyArtifact] = []
        for hypothesis in hypotheses:
            families = set(hypothesis.ingredient_families)
            if not families & {"geometric_visualization", "hardy_z", "explicit_formula"}:
                if not families & {"xi_function", "random_matrix"}:
                    continue
            digest = hypothesis.candidate_id.split("-")[-1]
            if families & {"geometric_visualization", "hardy_z", "explicit_formula"}:
                artifacts.extend(
                    (
                        self._phase_lock_artifact(hypothesis, digest, metrics),
                        self._energy_well_artifact(hypothesis, digest, metrics),
                    )
                )
            if families & {"geometric_visualization", "xi_function", "random_matrix"}:
                artifacts.append(self._zero_atlas_artifact(hypothesis, digest, metrics))
        return tuple(artifacts)

    def _phase_lock_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics: dict[str, float],
    ) -> NoveltyArtifact:
        validation_recipe = (
            "reconstruct Re zeta and Im zeta from Z(t) and theta(t) across the sampled wall curve",
            "verify the Re/Im wall zero set matches the sampled Hardy-Z zero set",
            "confirm Gram-point phase landmarks remain ordered across the sampled interval",
        )
        failure_modes = (
            "finite_window_only",
            "critical_line_identity_is_classical",
        )
        canonical = canonicalize_operator_claim(
            operator_family="phase_amplitude_projection",
            operator_primitives=(
                "CRITICAL_RESTRICTION",
                "Z_FUNCTION",
                "ARG_VARIATION",
                "GRAM_POINT",
                "MULTIPLY",
                "DUALIZE",
            ),
            input_types=("scalar_analytic_function", "zero_statistics_object"),
            output_type="zero_statistics_object",
            assumptions=(
                *hypothesis.assumptions,
                "critical-line wall projections are read as sampled operator outputs",
            ),
            invariances=("critical_line_phase_lock", "shared_zero_crossings"),
        )
        complexity, terms = complexity_score(
            node_count=6,
            depth=3,
            primitive_families=3,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics["phase_reconstruction_score"]),
            auxiliary_lemma_count=max(1, len(hypothesis.unresolved_proof_obligations)),
            branch_cut_penalty=0.10,
        )
        exact_claim = (
            "Any geometric RH hypothesis promoted by the loop must preserve the critical-line "
            "phase-amplitude decomposition Re zeta = Z cos theta and Im zeta = -Z sin theta, "
            "with the same sampled zero set appearing across both wall traces and Hardy-Z."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "extend sampled phase lock into an analytic invariant",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        return NoveltyArtifact(
            artifact_id=f"m-phase-lock-{digest}",
            agent="M",
            title="Phase-Amplitude Operator Lock",
            observation=(
                "The projection bundle supports the clean critical-line identity: the real and "
                "imaginary wall traces share the same Hardy-Z amplitude and differ only by the "
                "orthogonal phase rotation theta(t)."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "phase_reconstruction_score": metrics["phase_reconstruction_score"],
                "wall_zero_alignment": metrics["wall_zero_alignment"],
                "gram_phase_coverage": metrics["gram_phase_coverage"],
            },
            operator_family="phase_amplitude_projection",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            failure_modes=failure_modes,
            supporting_paths=(
                str(_PROJECTION_DATA),
                str(_STRIP_DATA),
            ),
        )

    def _energy_well_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics: dict[str, float],
    ) -> NoveltyArtifact:
        validation_recipe = (
            "locate sampled zero ordinates in the strip grid",
            "compare the critical-line log-abs valley depth against the nearest off-line sigma slices",
            "treat any candidate well-depth law as advisory until it is restated as a bound that excludes off-line zeros",
        )
        failure_modes = (
            "finite_window_only",
            "well_depth_needs_analytic_bound",
        )
        canonical = canonicalize_operator_claim(
            operator_family="critical_line_energy_well",
            operator_primitives=(
                "ENERGY",
                "CRITICAL_RESTRICTION",
                "ZERO_COUNT",
                "SYMMETRIZE",
                "BOUNDS",
            ),
            input_types=("scalar_analytic_function", "inequality_statement"),
            output_type="inequality_statement",
            assumptions=(
                *hypothesis.assumptions,
                "critical-line wells are compared only against neighboring sigma slices",
            ),
            invariances=("critical_line_localization",),
        )
        complexity, terms = complexity_score(
            node_count=5,
            depth=3,
            primitive_families=3,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics["critical_well_score"]),
            auxiliary_lemma_count=max(2, len(hypothesis.unresolved_proof_obligations)),
            contour_fragility_penalty=0.05,
        )
        exact_claim = (
            "Any geometric 'energy well' picture is only actionable if it yields a bounded "
            "critical-line localization statement: sampled wells at the known zero ordinates must "
            "stay deeper on sigma = 1/2 than on adjacent sigma slices, and that pattern must then "
            "be upgraded into a theorem-level exclusion bound."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "prove sampled well depth implies a global exclusion argument",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        return NoveltyArtifact(
            artifact_id=f"m-energy-well-{digest}",
            agent="M",
            title="Critical-Line Energy Well",
            observation=(
                "The strip bundle lets the visual 'energy well' intuition be measured instead of "
                "just narrated: at sampled zero ordinates the critical-line slice can be compared "
                "directly to its nearest off-line neighbors."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "critical_well_score": metrics["critical_well_score"],
                "critical_localization_score": metrics["critical_localization_score"],
                "phase_energy_bridge": metrics["phase_energy_bridge"],
            },
            operator_family="critical_line_energy_well",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            failure_modes=failure_modes,
            supporting_paths=(
                str(_STRIP_DATA),
                str(_EXPLICIT_DATA),
            ),
        )

    def _zero_atlas_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics: dict[str, float],
    ) -> NoveltyArtifact:
        validation_recipe = (
            "reconstruct the contour-intersection atlas from the Re zeta / Im zeta wall traces and confirm the sampled zero ordinates match across views",
            "check that the sampled zero ordinates obey the 2pi-normalized Riemann-von-Mangoldt counting law at the atlas scale, not a fake Bernoulli-style closed form",
            "treat any RH-style t_k sum identity as advisory until the zero-sum tail is justified analytically rather than by a finite table of ordinates",
        )
        failure_modes = (
            "finite_window_only",
            "counting_law_needs_explicit_error_bound",
            "zero_sum_relation_needs_tail_control",
        )
        canonical = canonicalize_operator_claim(
            operator_family="zero_ordinate_pi_atlas",
            operator_primitives=(
                "XI",
                "ZERO_COUNT",
                "CRITICAL_RESTRICTION",
                "GRAM_POINT",
                "BOUNDS",
                "SYMMETRIZE",
            ),
            input_types=("scalar_analytic_function", "zero_statistics_object", "asymptotic_statement"),
            output_type="zero_statistics_object",
            assumptions=(
                *hypothesis.assumptions,
                "zero-ordinate pictures are only promoted after 2pi normalization and count-law calibration",
            ),
            invariances=("zero_counting_scale", "contour_zero_intersection", "critical_line_zero_pairing"),
        )
        complexity, terms = complexity_score(
            node_count=6,
            depth=3,
            primitive_families=4,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics["zero_atlas_score"]),
            auxiliary_lemma_count=max(2, len(hypothesis.unresolved_proof_obligations) + 1),
            contour_fragility_penalty=0.06,
        )
        exact_claim = (
            "Any visual or statistical RH atlas promoted by the loop must preserve three pieces of structure "
            "at once: contour-zero intersections, the 2pi-normalized zero counting law, and any xi-based "
            "zero-sum identity it invokes. Individual ordinates t_k are not promoted as Bernoulli/pi closed forms."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "turn the 2pi-normalized counting fit into an explicit error-bound theorem",
                "justify any t_k zero-sum identity with global tail control",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        return NoveltyArtifact(
            artifact_id=f"m-zero-atlas-{digest}",
            agent="M",
            title="Pi-Normalized Zero Atlas",
            observation=(
                "The contour and line plots become mathematically useful only after normalization: pi enters "
                "through the xi/gamma scaling and the 2pi zero-count law, while the sampled ordinates t_k can "
                "also be tested against RH-style zero-sum identities such as partial Z(1) data."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "zero_atlas_score": metrics["zero_atlas_score"],
                "counting_law_score": metrics["counting_law_score"],
                "pi_normalization_score": metrics["pi_normalization_score"],
                "li_partial_sum_score": metrics["li_partial_sum_score"],
                "partial_z1_sum": metrics["partial_z1_sum"],
            },
            operator_family="zero_ordinate_pi_atlas",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            failure_modes=failure_modes,
            supporting_paths=(
                str(_PROJECTION_DATA),
                str(_STRIP_DATA),
                str(_EXPLICIT_DATA),
            ),
        )

    def _derive_metrics(
        self,
        projection: dict,
        strip: dict,
        explicit: dict,
    ) -> dict[str, float]:
        curve = np.asarray(projection.get("curve", []), dtype=float)
        projection_zeros = np.asarray(projection.get("zeros", []), dtype=float)
        strip_zeros = np.asarray(strip.get("zeros", []), dtype=float)
        explicit_zeros = np.asarray(explicit.get("zeros", []), dtype=float)
        gram_points = np.asarray(projection.get("gram_points", []), dtype=float)

        phase_reconstruction_score = 0.0
        if curve.ndim == 2 and curve.shape[1] >= 5:
            re_vals = curve[:, 1]
            im_vals = curve[:, 2]
            z_vals = curve[:, 3]
            theta_vals = curve[:, 4]
            re_pred = z_vals * np.cos(theta_vals)
            im_pred = -z_vals * np.sin(theta_vals)
            scale = float(np.mean(np.abs(z_vals))) or 1.0
            rmse = float(np.sqrt(np.mean((re_vals - re_pred) ** 2 + (im_vals - im_pred) ** 2))) / scale
            phase_reconstruction_score = float(max(0.0, min(1.0, 1.0 - rmse)))

        wall_zero_alignment = self._alignment_score(projection_zeros, strip_zeros)

        gram_ord = gram_points[:, 1] if gram_points.ndim == 2 and gram_points.shape[1] >= 2 else gram_points
        gram_phase_coverage = float(
            max(0.0, min(1.0, gram_ord.size / max(float(projection_zeros.size), 1.0)))
        )

        critical_well_score = self._critical_well_score(strip)
        counting_law_score = self._counting_law_score(explicit_zeros)
        pi_normalization_score, normalized_gap_mean, normalized_gap_cv = self._pi_normalization_score(explicit_zeros)
        li_partial_sum_score, partial_z1_sum = self._li_partial_sum_score(explicit_zeros)
        explicit_support = float(max(0.0, min(1.0, explicit_zeros.size / 100.0)))
        critical_localization_score = 0.5 * (wall_zero_alignment + explicit_support)
        phase_energy_bridge = 0.5 * (phase_reconstruction_score + critical_well_score)
        zero_atlas_score = float(
            max(
                0.0,
                min(
                    1.0,
                    0.30 * wall_zero_alignment
                    + 0.25 * counting_law_score
                    + 0.20 * pi_normalization_score
                    + 0.25 * li_partial_sum_score,
                ),
            )
        )

        return {
            "phase_reconstruction_score": phase_reconstruction_score,
            "wall_zero_alignment": wall_zero_alignment,
            "gram_phase_coverage": gram_phase_coverage,
            "critical_well_score": critical_well_score,
            "critical_localization_score": critical_localization_score,
            "phase_energy_bridge": phase_energy_bridge,
            "counting_law_score": counting_law_score,
            "pi_normalization_score": pi_normalization_score,
            "normalized_gap_mean": normalized_gap_mean,
            "normalized_gap_cv": normalized_gap_cv,
            "li_partial_sum_score": li_partial_sum_score,
            "partial_z1_sum": partial_z1_sum,
            "zero_atlas_score": zero_atlas_score,
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

    def _critical_well_score(self, strip: dict) -> float:
        sigma_grid = np.asarray(strip.get("sigma_grid", []), dtype=float)
        t_grid = np.asarray(strip.get("t_grid", []), dtype=float)
        log_abs = np.asarray(strip.get("log_abs", []), dtype=float)
        zeros = np.asarray(strip.get("zeros", []), dtype=float)
        if sigma_grid.ndim != 1 or t_grid.ndim != 1 or log_abs.ndim != 2 or zeros.size == 0:
            return 0.0
        crit_idx = int(np.argmin(np.abs(sigma_grid - 0.5)))
        if crit_idx <= 0 or crit_idx >= log_abs.shape[0] - 1:
            return 0.0
        neighbor_rows = (crit_idx - 1, crit_idx + 1)
        clip_range = float(strip.get("clip_hi", 1.0) - strip.get("clip_lo", -1.0)) or 1.0
        wells = []
        for zero in zeros:
            t_idx = int(np.argmin(np.abs(t_grid - zero)))
            crit_val = float(log_abs[crit_idx, t_idx])
            neighbor_val = float(np.mean([log_abs[row, t_idx] for row in neighbor_rows]))
            wells.append(max(0.0, neighbor_val - crit_val) / clip_range)
        if not wells:
            return 0.0
        return float(max(0.0, min(1.0, float(np.mean(wells)))))

    def _counting_law_score(self, zeros: np.ndarray) -> float:
        if zeros.size == 0:
            return 0.0
        residuals = []
        for idx, ordinate in enumerate(zeros, start=1):
            if ordinate <= 2.0 * math.pi:
                continue
            main_term = ordinate / (2.0 * math.pi) * math.log(ordinate / (2.0 * math.pi))
            main_term -= ordinate / (2.0 * math.pi)
            main_term += 0.875
            residuals.append(abs(idx - main_term))
        if not residuals:
            return 0.0
        mean_residual = float(np.mean(residuals))
        return float(max(0.0, min(1.0, 1.0 - mean_residual / 2.5)))

    def _pi_normalization_score(self, zeros: np.ndarray) -> tuple[float, float, float]:
        if zeros.size < 2:
            return 0.0, 0.0, 0.0
        normalized_gaps = []
        for left, right in zip(zeros[:-1], zeros[1:]):
            if left <= 2.0 * math.pi:
                continue
            local_mean_gap = 2.0 * math.pi / max(math.log(left / (2.0 * math.pi)), 1e-6)
            normalized_gaps.append((right - left) / local_mean_gap)
        if not normalized_gaps:
            return 0.0, 0.0, 0.0
        mean_gap = float(np.mean(normalized_gaps))
        gap_cv = float(np.std(normalized_gaps) / max(mean_gap, 1e-6))
        score = max(0.0, min(1.0, 1.0 - abs(mean_gap - 1.0) - 0.35 * min(gap_cv, 1.0)))
        return float(score), mean_gap, gap_cv

    def _li_partial_sum_score(self, zeros: np.ndarray) -> tuple[float, float]:
        if zeros.size == 0:
            return 0.0, 0.0
        partial_sum = float(np.sum(4.0 / (1.0 + 4.0 * zeros * zeros)))
        reference = 0.0230957
        diff = abs(partial_sum - reference)
        score = max(0.0, min(1.0, 1.0 - diff / 0.02))
        return float(score), partial_sum

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text())
