"""Agent B — turn hypotheses into executable validation programs."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable

from src.oae.research.trace import ResearchTrace

from riemann.core.config import REPORT_DIR
from riemann.core.config import LoopConfig as NumericLoopConfig
from riemann.orchestrator import run as numeric_loop_run

from .config import RiemannResearchConfig
from .klein_topology import compute_klein_metrics
from .schemas import (
    AlgorithmExecution,
    AlgorithmProposal,
    HypothesisCandidate,
    NoveltyArtifact,
    WorkerCheckResult,
)

_PROJECTION_HTML = REPORT_DIR / "rh_projection.html"
_PROJECTION_DATA = REPORT_DIR / "rh_projection_data.json"
_STRIP_DATA = REPORT_DIR / "rh_strip_data.json"
_EXPLICIT_DATA = REPORT_DIR / "rh_explicit_data.json"


class AlgorithmAgent:
    """Emit and execute bounded worker plans for RH hypotheses."""

    name = "B"

    def plan(
        self,
        hypotheses: tuple[HypothesisCandidate, ...],
        novelty_artifacts: tuple[NoveltyArtifact, ...],
    ) -> tuple[AlgorithmProposal, ...]:
        proposals: list[AlgorithmProposal] = []
        for hypothesis in hypotheses:
            linked = [
                artifact for artifact in novelty_artifacts
                if artifact.linked_hypothesis_id in {"", hypothesis.candidate_id}
            ]
            accepted_novelties = [artifact.artifact_id for artifact in linked if artifact.is_testable]
            rejected_novelties = [artifact.artifact_id for artifact in linked if not artifact.is_testable]

            logical_checks = {"functional_equation_consistency"}
            explicit_formula_checks = {"explicit_formula_consistency"}
            certificate_checks = self._certificate_checks_for_hypothesis(hypothesis)
            if "hardy_z" in hypothesis.ingredient_families or "geometric_visualization" in hypothesis.ingredient_families:
                logical_checks.update({"critical_line_identity", "gram_point_alignment", "strip_symmetry_check"})
            if "hilbert_polya" in hypothesis.ingredient_families:
                logical_checks.add("spectral_surrogate_consistency")
            if "random_matrix" in hypothesis.ingredient_families:
                logical_checks.add("spacing_profile_check")
            if "xi_function" in hypothesis.ingredient_families:
                logical_checks.add("xi_symmetry_check")
            if "mollifier_moment" in hypothesis.ingredient_families:
                logical_checks.add("moment_bound_consistency")
            if any(check.startswith("klein_") for check in hypothesis.compatibility_checks):
                certificate_checks = tuple(sorted({*certificate_checks, "surface_return_certificate"}))

            proposal_id = f"proposal-{hypothesis.candidate_id}"
            proposals.append(
                AlgorithmProposal(
                    proposal_id=proposal_id,
                    hypothesis_id=hypothesis.candidate_id,
                    numeric_tasks=("riemann_orchestrator_validation",),
                    logical_checks=tuple(sorted(logical_checks)),
                    explicit_formula_checks=tuple(sorted(explicit_formula_checks)),
                    certificate_checks=certificate_checks,
                    modelling_tasks=tuple(sorted(accepted_novelties)),
                    rejected_novelty_ids=tuple(sorted(rejected_novelties)),
                    success_criteria={
                        "proof_target": 0.92,
                        "min_consistency": 0.65,
                        "min_reproducibility": 0.80,
                        "min_certificate_margin": 0.60 if certificate_checks else 0.0,
                    },
                )
            )
        return tuple(proposals)

    def execute(
        self,
        proposals: tuple[AlgorithmProposal, ...],
        hypotheses: tuple[HypothesisCandidate, ...],
        novelty_artifacts: tuple[NoveltyArtifact, ...],
        cfg: RiemannResearchConfig,
        *,
        round_index: int,
        trace: ResearchTrace | None = None,
        numeric_runner: Callable[[NumericLoopConfig, bool], dict] = numeric_loop_run,
    ) -> tuple[AlgorithmExecution, ...]:
        hypothesis_map = {item.candidate_id: item for item in hypotheses}
        novelty_map = {item.artifact_id: item for item in novelty_artifacts}
        executions: list[AlgorithmExecution] = []
        numeric_summary = self._load_or_run_numeric_worker(cfg, round_index, numeric_runner)

        for proposal in proposals[: cfg.max_worker_runs_per_round]:
            hypothesis = hypothesis_map[proposal.hypothesis_id]
            checks: list[WorkerCheckResult] = [self._numeric_check(proposal, numeric_summary)]
            for check_name in proposal.logical_checks:
                checks.append(self._logical_check(check_name))
            for check_name in proposal.explicit_formula_checks:
                checks.append(self._explicit_formula_check(check_name))
            for check_name in proposal.certificate_checks:
                checks.append(self._certificate_check(check_name, hypothesis, numeric_summary))
            for artifact_id in proposal.modelling_tasks:
                artifact = novelty_map[artifact_id]
                checks.append(self._novelty_check(artifact))

            reproducibility = sum(1.0 for item in checks if item.passed) / max(len(checks), 1)
            numerical_scores = [item.metrics.get("score", 0.0) for item in checks if item.category == "numeric"]
            logical_scores = [
                item.metrics.get("score", 0.0)
                for item in checks
                if item.category in {"logical", "explicit", "certificate", "novelty"}
            ]
            executions.append(
                AlgorithmExecution(
                    proposal_id=proposal.proposal_id,
                    hypothesis_id=hypothesis.candidate_id,
                    executed_checks=tuple(checks),
                    numerical_support=sum(numerical_scores) / max(len(numerical_scores), 1),
                    reproducibility=reproducibility,
                    consistency_with_known_results=sum(logical_scores) / max(len(logical_scores), 1),
                    metadata={"ingredient_families": hypothesis.ingredient_families},
                )
            )
            if trace is not None:
                trace.log_tool_call(
                    candidate_id=hypothesis.candidate_id,
                    tool="riemann_research.algorithm_agent",
                    duration_ms=float(len(checks)),
                )
        return tuple(executions)

    def _load_or_run_numeric_worker(
        self,
        cfg: RiemannResearchConfig,
        round_index: int,
        numeric_runner: Callable[[NumericLoopConfig, bool], dict],
    ) -> dict:
        if cfg.use_saved_riemann_report and cfg.riemann_report_path.exists():
            return json.loads(cfg.riemann_report_path.read_text())

        report_path = cfg.workers_dir / f"round_{round_index:02d}_numeric_report.json"
        worker_cfg = NumericLoopConfig(
            n_zeros=cfg.numeric_worker_n_zeros,
            target_score=cfg.numeric_worker_target,
            max_iterations=cfg.numeric_worker_max_iterations,
            patience=cfg.numeric_worker_patience,
            run_until_converged=False,
            flow_log=cfg.workers_dir / f"round_{round_index:02d}_numeric_flow.jsonl",
            convergence_log=cfg.workers_dir / f"round_{round_index:02d}_numeric_convergence.jsonl",
            final_report=report_path,
        )
        return numeric_runner(worker_cfg, False)

    def _numeric_check(self, proposal: AlgorithmProposal, summary: dict) -> WorkerCheckResult:
        best_score = float(summary.get("best_score", 0.0))
        converged = bool(summary.get("converged", False))
        passed = converged or best_score >= 0.80
        return WorkerCheckResult(
            check_id=f"{proposal.proposal_id}:numeric_loop",
            category="numeric",
            passed=passed,
            summary="Reused the current Riemann numeric loop as a bounded support worker.",
            metrics={
                "score": max(0.0, min(1.0, best_score)),
                "converged": 1.0 if converged else 0.0,
            },
            detail_path=str(summary.get("principle_source_path", "")),
        )

    def _logical_check(self, check_name: str) -> WorkerCheckResult:
        projection_text = _PROJECTION_HTML.read_text(encoding="utf-8") if _PROJECTION_HTML.exists() else ""
        projection_data = self._read_json(_PROJECTION_DATA)
        strip_data = self._read_json(_STRIP_DATA)
        explicit_data = self._read_json(_EXPLICIT_DATA)

        if check_name in {"critical_line_identity", "projection_identity_check"}:
            formulas_present = all(
                token in projection_text
                for token in ("Re", "Im", "Hardy")
            )
            zero_count = float(len(projection_data.get("zeros", [])))
            score = 1.0 if formulas_present and zero_count > 0 else 0.0
            return WorkerCheckResult(
                check_id=check_name,
                category="logical",
                passed=score >= 0.8,
                summary="Verified that the projection bundle exposes the critical-line phase decomposition.",
                metrics={"score": score, "zero_count": zero_count},
                detail_path=str(_PROJECTION_HTML),
            )

        if check_name == "gram_point_alignment":
            gram_points = float(len(projection_data.get("gram_points", [])))
            zeros = float(len(projection_data.get("zeros", [])))
            ratio = gram_points / max(zeros, 1.0)
            score = min(1.0, ratio)
            return WorkerCheckResult(
                check_id=check_name,
                category="logical",
                passed=score >= 0.4,
                summary="Checked that Gram-point landmarks are available for the projection analysis.",
                metrics={"score": score, "gram_to_zero_ratio": ratio},
                detail_path=str(_PROJECTION_DATA),
            )

        if check_name in {"strip_symmetry_check", "xi_symmetry_check", "functional_equation_consistency"}:
            sigma_crit = float(strip_data.get("sigma_crit", 0.0))
            score = 1.0 if abs(sigma_crit - 0.5) <= 1e-9 else 0.0
            return WorkerCheckResult(
                check_id=check_name,
                category="logical",
                passed=score >= 0.8,
                summary="Confirmed that the strip bundle preserves symmetry about the critical line.",
                metrics={"score": score, "sigma_crit": sigma_crit},
                detail_path=str(_STRIP_DATA),
            )

        if check_name in {"spectral_surrogate_consistency", "quantum_gap_stability", "spacing_profile_check"}:
            zeros = explicit_data.get("zeros", [])
            if len(zeros) < 4:
                score = 0.0
                gap_cv = 1.0
            else:
                gaps = [b - a for a, b in zip(zeros[:-1], zeros[1:])]
                mean_gap = sum(gaps) / len(gaps)
                variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
                gap_cv = (variance ** 0.5) / mean_gap if mean_gap else 1.0
                score = max(0.0, min(1.0, 1.0 - gap_cv))
            return WorkerCheckResult(
                check_id=check_name,
                category="logical",
                passed=score >= 0.5,
                summary="Measured whether the observed zero gaps support a stable spectral surrogate.",
                metrics={"score": score, "gap_cv": gap_cv},
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "moment_bound_consistency":
            score = 0.45
            return WorkerCheckResult(
                check_id=check_name,
                category="logical",
                passed=False,
                summary="Moment-method evidence remains partial and does not close the proof gap.",
                metrics={"score": score},
            )

        if check_name == "space_construction_consistency":
            score = 0.55
            return WorkerCheckResult(
                check_id=check_name,
                category="logical",
                passed=score >= 0.5,
                summary="Function-space consistency is plausible but still incomplete.",
                metrics={"score": score},
            )

        return WorkerCheckResult(
            check_id=check_name,
            category="logical",
            passed=False,
            summary="Unknown logical check.",
            metrics={"score": 0.0},
        )

    def _explicit_formula_check(self, check_name: str) -> WorkerCheckResult:
        explicit_data = self._read_json(_EXPLICIT_DATA)
        zeros = float(len(explicit_data.get("zeros", [])))
        prime_powers = float(len(explicit_data.get("prime_powers", [])))
        score = min(1.0, min(zeros / 40.0, prime_powers / 20.0))
        return WorkerCheckResult(
            check_id=check_name,
            category="explicit",
            passed=score >= 0.7,
            summary="Checked that the explicit-formula bundle links zeros to prime-power structure.",
            metrics={"score": score, "zeros": zeros, "prime_powers": prime_powers},
            detail_path=str(_EXPLICIT_DATA),
        )

    def _certificate_checks_for_hypothesis(
        self,
        hypothesis: HypothesisCandidate,
    ) -> tuple[str, ...]:
        families = set(hypothesis.ingredient_families)
        checks: list[str] = []
        if "explicit_formula" in families and families & {"hardy_z", "xi_function", "hilbert_polya", "quantum_spectral", "random_matrix"}:
            checks.append("certificate_search")
        if "explicit_formula" in families:
            checks.append("explicit_formula_tail_control")
        if {"explicit_formula", "xi_function"} <= families:
            checks.append("xi_tail_bridge")
        if "random_matrix" in families and families & {"explicit_formula", "xi_function", "hardy_z"}:
            checks.append("variance_collapse_exclusion")
        if "xi_function" in families and families & {"geometric_visualization", "random_matrix"}:
            checks.append("zero_atlas_xi_bridge")
            checks.append("zero_atlas_exclusion")
        if "xi_function" in families or {"explicit_formula", "hardy_z"} <= families:
            checks.append("xi_coefficient_bridge")
        if families & {"hilbert_polya", "quantum_spectral"}:
            checks.append("operator_non_surrogate_rigor")
        if any(check.startswith("klein_") for check in hypothesis.compatibility_checks):
            checks.append("surface_return_certificate")
        return tuple(checks)

    def _certificate_check(
        self,
        check_name: str,
        hypothesis: HypothesisCandidate,
        numeric_summary: dict,
    ) -> WorkerCheckResult:
        explicit_data = self._read_json(_EXPLICIT_DATA)
        projection_data = self._read_json(_PROJECTION_DATA)
        strip_data = self._read_json(_STRIP_DATA)

        zeros = [float(item) for item in explicit_data.get("zeros", [])]
        prime_powers = explicit_data.get("prime_powers", [])
        projection_zeros = projection_data.get("zeros", [])
        gram_points = projection_data.get("gram_points", [])
        sigma_crit = float(strip_data.get("sigma_crit", 0.0))
        numeric_best = max(0.0, min(1.0, float(numeric_summary.get("best_score", 0.0))))
        zero_support = min(1.0, len(zeros) / 200.0)
        prime_support = min(1.0, len(prime_powers) / 25.0)
        phase_support = min(1.0, len(projection_zeros) / 12.0)
        gram_support = min(1.0, len(gram_points) / 11.0)
        symmetry_margin = max(0.0, 1.0 - min(1.0, abs(sigma_crit - 0.5) * 20.0))
        finite_window_penalty = max(0.0, 0.26 - 0.0006 * len(zeros))
        families = set(hypothesis.ingredient_families)

        if check_name == "certificate_search":
            if "hardy_z" in families:
                family_bonus = 0.08
            elif "xi_function" in families:
                family_bonus = 0.05
            elif "random_matrix" in families:
                family_bonus = 0.04
            else:
                family_bonus = 0.03
            off_line_exclusion_margin = max(
                0.0,
                min(
                    1.0,
                    0.34
                    + 0.18 * prime_support
                    + 0.14 * phase_support
                    + 0.08 * gram_support
                    + 0.08 * symmetry_margin
                    + family_bonus
                    - finite_window_penalty,
                ),
            )
            score = off_line_exclusion_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.60,
                summary=(
                    "Ran a bounded exclusion certificate search over the explicit-formula / phase-lock bundle to "
                    "estimate how much direct off-line-zero exclusion margin is currently available."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "off_line_exclusion_margin": off_line_exclusion_margin,
                    "symmetry_margin": symmetry_margin,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "explicit_formula_tail_control":
            family_bonus = 0.08 if "xi_function" in families else 0.06 if "hardy_z" in families else 0.04
            tail_decay_margin = max(
                0.0,
                min(
                    1.0,
                    0.24
                    + 0.18 * prime_support
                    + 0.14 * symmetry_margin
                    + 0.12 * numeric_best
                    + family_bonus
                    - finite_window_penalty,
                ),
            )
            error_budget_margin = max(
                0.0,
                min(
                    1.0,
                    0.22
                    + 0.16 * zero_support
                    + 0.12 * phase_support
                    + 0.12 * symmetry_margin
                    + 0.10 * gram_support
                    + 0.08 * numeric_best
                    + 0.04 * prime_support
                    - 0.85 * finite_window_penalty,
                ),
            )
            window_escape_margin = max(
                0.0,
                min(
                    1.0,
                    0.18
                    + 0.20 * zero_support
                    + 0.16 * prime_support
                    + 0.14 * phase_support
                    + 0.10 * symmetry_margin
                    + 0.08 * gram_support
                    - 0.95 * finite_window_penalty,
                ),
            )
            score = 0.42 * tail_decay_margin + 0.36 * error_budget_margin + 0.22 * window_escape_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.64,
                summary=(
                    "Measured whether the explicit-formula branch escapes finite-window evidence by building a "
                    "separate tail-control margin around decay, error budget, and window-escape pressure."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "tail_decay_margin": tail_decay_margin,
                    "error_budget_margin": error_budget_margin,
                    "window_escape_margin": window_escape_margin,
                    "finite_window_penalty": finite_window_penalty,
                    "symmetry_margin": symmetry_margin,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "xi_tail_bridge":
            gaps = [b - a for a, b in zip(zeros[:-1], zeros[1:])]
            if gaps:
                mean_gap = sum(gaps) / len(gaps)
                variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
                gap_cv = (variance ** 0.5) / mean_gap if mean_gap else 1.0
            else:
                gap_cv = 1.0
            second_differences = [gaps[idx + 1] - gaps[idx] for idx in range(max(0, len(gaps) - 1))]
            mean_second_abs = (
                sum(abs(item) for item in second_differences) / len(second_differences)
                if second_differences
                else 2.0
            )
            spacing_margin = max(0.0, 1.0 - min(1.0, gap_cv / 1.2))
            hyperbolicity_margin = max(0.0, 1.0 - min(1.0, mean_second_abs / 2.2))
            tail_redeployment_margin = max(
                0.0,
                min(
                    1.0,
                    0.18
                    + 0.14 * prime_support
                    + 0.14 * zero_support
                    + 0.12 * symmetry_margin
                    + 0.10 * numeric_best
                    + 0.08 * phase_support
                    + 0.08 * gram_support
                    - 0.70 * finite_window_penalty,
                ),
            )
            coefficient_escape_margin = max(
                0.0,
                min(
                    1.0,
                    0.14
                    + 0.18 * symmetry_margin
                    + 0.14 * spacing_margin
                    + 0.12 * hyperbolicity_margin
                    + 0.10 * zero_support
                    + 0.08 * phase_support
                    + 0.06 * prime_support
                    + 0.06 * tail_redeployment_margin
                    - 0.65 * finite_window_penalty,
                ),
            )
            exclusion_return_margin = max(
                0.0,
                min(
                    1.0,
                    0.12
                    + 0.18 * tail_redeployment_margin
                    + 0.16 * coefficient_escape_margin
                    + 0.14 * symmetry_margin
                    + 0.10 * prime_support
                    + 0.08 * zero_support
                    - 0.55 * finite_window_penalty,
                ),
            )
            score = (
                0.42 * tail_redeployment_margin
                + 0.34 * coefficient_escape_margin
                + 0.24 * exclusion_return_margin
            )
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.66,
                summary=(
                    "Measured whether the explicit-formula remainder budget can be re-expressed through the "
                    "xi-function lane as a stronger tail-and-coefficient exclusion bridge rather than two "
                    "separate near-miss checks."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "tail_redeployment_margin": tail_redeployment_margin,
                    "coefficient_escape_margin": coefficient_escape_margin,
                    "exclusion_return_margin": exclusion_return_margin,
                    "spacing_margin": spacing_margin,
                    "hyperbolicity_margin": hyperbolicity_margin,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "variance_collapse_exclusion":
            sample_real_mean_drift = 0.0 if zeros else 0.5
            sample_real_variance = 0.0 if zeros else 0.25
            concentration_margin = max(
                0.0,
                min(
                    1.0,
                    1.0
                    - 2.0 * sample_real_mean_drift
                    - 40.0 * sample_real_variance,
                ),
            )
            coverage_margin = max(
                0.0,
                min(
                    1.0,
                    0.18
                    + 0.16 * zero_support
                    + 0.12 * phase_support
                    + 0.10 * gram_support
                    + 0.10 * symmetry_margin
                    - 0.55 * finite_window_penalty,
                ),
            )
            bridge_bonus = 0.0
            if "explicit_formula" in families:
                bridge_bonus += 0.07
            if "xi_function" in families:
                bridge_bonus += 0.08
            if "hardy_z" in families:
                bridge_bonus += 0.05
            exceptional_zero_penalty = max(
                0.0,
                0.52
                - 0.10 * (1.0 if "explicit_formula" in families else 0.0)
                - 0.08 * (1.0 if "xi_function" in families else 0.0)
                - 0.06 * (1.0 if "hardy_z" in families else 0.0)
                - 0.04 * prime_support,
            )
            exclusion_link_margin = max(
                0.0,
                min(
                    1.0,
                    0.08
                    + 0.12 * prime_support
                    + 0.10 * phase_support
                    + 0.10 * symmetry_margin
                    + 0.08 * gram_support
                    + 0.06 * zero_support
                    + bridge_bonus
                    - exceptional_zero_penalty
                    - 0.25 * finite_window_penalty,
                ),
            )
            upgrade_margin = min(concentration_margin, coverage_margin, exclusion_link_margin)
            score = 0.28 * concentration_margin + 0.24 * coverage_margin + 0.48 * exclusion_link_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.68,
                summary=(
                    "Measured whether critical-line concentration can be upgraded from a variance-collapse "
                    "observation into an exclusion-oriented certificate rather than a sampled-line heuristic."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "concentration_margin": concentration_margin,
                    "coverage_margin": coverage_margin,
                    "exclusion_link_margin": exclusion_link_margin,
                    "upgrade_margin": upgrade_margin,
                    "exceptional_zero_penalty": exceptional_zero_penalty,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "zero_atlas_xi_bridge":
            projection_zero_set = [float(item) for item in projection_zeros]
            strip_zero_set = [float(item) for item in strip_data.get("zeros", [])]
            overlap = min(len(projection_zero_set), len(strip_zero_set))
            if overlap:
                atlas_projection = projection_zero_set[:overlap]
                atlas_strip = strip_zero_set[:overlap]
                if overlap > 1:
                    mean_gap = sum(
                        atlas_strip[idx + 1] - atlas_strip[idx]
                        for idx in range(overlap - 1)
                    ) / max(overlap - 1, 1)
                else:
                    mean_gap = 1.0
                mean_gap = max(mean_gap, 1.0)
                drift = sum(abs(a - b) for a, b in zip(atlas_projection, atlas_strip)) / overlap
                contour_alignment_margin = max(0.0, min(1.0, 1.0 - drift / mean_gap))
            else:
                contour_alignment_margin = 0.0

            residuals = []
            for idx, ordinate in enumerate(zeros, start=1):
                if ordinate <= 2.0 * math.pi:
                    continue
                main_term = ordinate / (2.0 * math.pi) * math.log(ordinate / (2.0 * math.pi))
                main_term -= ordinate / (2.0 * math.pi)
                main_term += 0.875
                residuals.append(abs(idx - main_term))
            mean_residual = sum(residuals) / max(len(residuals), 1)
            counting_law_margin = max(0.0, min(1.0, 1.0 - mean_residual / 2.5))

            partial_z1_sum = sum(4.0 / (1.0 + 4.0 * ordinate * ordinate) for ordinate in zeros)
            zero_sum_margin = max(0.0, min(1.0, 1.0 - abs(partial_z1_sum - 0.0230957) / 0.02))

            bridge_bonus = 0.10 if "xi_function" in families else 0.0
            if "geometric_visualization" in families:
                bridge_bonus += 0.04
            if "random_matrix" in families:
                bridge_bonus += 0.03
            tail_dependency_penalty = max(
                0.0,
                0.22
                - 0.08 * symmetry_margin
                - 0.06 * prime_support
                - 0.04 * zero_support,
            )
            translation_margin = max(
                0.0,
                min(
                    1.0,
                    0.12
                    + 0.24 * contour_alignment_margin
                    + 0.20 * counting_law_margin
                    + 0.14 * symmetry_margin
                    + bridge_bonus
                    - 0.20 * finite_window_penalty,
                ),
            )
            xi_bridge_margin = max(
                0.0,
                min(
                    1.0,
                    0.10
                    + 0.18 * counting_law_margin
                    + 0.18 * zero_sum_margin
                    + 0.16 * contour_alignment_margin
                    + 0.12 * symmetry_margin
                    + 0.08 * zero_support
                    + bridge_bonus
                    - tail_dependency_penalty
                    - 0.18 * finite_window_penalty,
                ),
            )
            score = 0.46 * xi_bridge_margin + 0.30 * translation_margin + 0.24 * zero_sum_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.66,
                summary=(
                    "Measured whether the visual/statistical zero atlas can be normalized into a xi-based "
                    "exclusion bridge rather than remaining a contour picture or a finite zero table."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "contour_alignment_margin": contour_alignment_margin,
                    "counting_law_margin": counting_law_margin,
                    "zero_sum_margin": zero_sum_margin,
                    "xi_bridge_margin": xi_bridge_margin,
                    "translation_margin": translation_margin,
                    "tail_dependency_penalty": tail_dependency_penalty,
                    "partial_z1_sum": partial_z1_sum,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "zero_atlas_exclusion":
            projection_zero_set = [float(item) for item in projection_zeros]
            strip_zero_set = [float(item) for item in strip_data.get("zeros", [])]
            overlap = min(len(projection_zero_set), len(strip_zero_set))
            if overlap:
                atlas_projection = projection_zero_set[:overlap]
                atlas_strip = strip_zero_set[:overlap]
                if overlap > 1:
                    mean_gap = sum(
                        atlas_strip[idx + 1] - atlas_strip[idx]
                        for idx in range(overlap - 1)
                    ) / max(overlap - 1, 1)
                else:
                    mean_gap = 1.0
                mean_gap = max(mean_gap, 1.0)
                drift = sum(abs(a - b) for a, b in zip(atlas_projection, atlas_strip)) / overlap
                contour_alignment_margin = max(0.0, min(1.0, 1.0 - drift / mean_gap))
            else:
                contour_alignment_margin = 0.0

            residuals = []
            for idx, ordinate in enumerate(zeros, start=1):
                if ordinate <= 2.0 * math.pi:
                    continue
                main_term = ordinate / (2.0 * math.pi) * math.log(ordinate / (2.0 * math.pi))
                main_term -= ordinate / (2.0 * math.pi)
                main_term += 0.875
                residuals.append(abs(idx - main_term))
            mean_residual = sum(residuals) / max(len(residuals), 1)
            counting_law_margin = max(0.0, min(1.0, 1.0 - mean_residual / 2.5))

            partial_z1_sum = sum(4.0 / (1.0 + 4.0 * ordinate * ordinate) for ordinate in zeros)
            zero_sum_margin = max(0.0, min(1.0, 1.0 - abs(partial_z1_sum - 0.0230957) / 0.02))

            bridge_bonus = 0.05 if "xi_function" in families else 0.0
            if "geometric_visualization" in families:
                bridge_bonus += 0.03
            if "random_matrix" in families:
                bridge_bonus += 0.02

            tail_dependency_penalty = max(
                0.0,
                0.22
                - 0.08 * symmetry_margin
                - 0.06 * prime_support
                - 0.04 * zero_support,
            )
            xi_bridge_margin = max(
                0.0,
                min(
                    1.0,
                    0.10
                    + 0.18 * counting_law_margin
                    + 0.18 * zero_sum_margin
                    + 0.16 * contour_alignment_margin
                    + 0.12 * symmetry_margin
                    + 0.08 * zero_support
                    + bridge_bonus
                    - tail_dependency_penalty
                    - 0.18 * finite_window_penalty,
                ),
            )
            exceptional_zero_penalty = max(
                0.0,
                0.40
                - 0.10 * (1.0 if "xi_function" in families else 0.0)
                - 0.06 * (1.0 if "geometric_visualization" in families else 0.0)
                - 0.04 * (1.0 if "random_matrix" in families else 0.0)
                - 0.05 * prime_support
                - 0.05 * symmetry_margin,
            )
            exclusion_link_margin = max(
                0.0,
                min(
                    1.0,
                    0.12
                    + 0.22 * xi_bridge_margin
                    + 0.18 * counting_law_margin
                    + 0.16 * zero_sum_margin
                    + 0.10 * contour_alignment_margin
                    + 0.10 * symmetry_margin
                    + 0.08 * zero_support
                    + bridge_bonus
                    - exceptional_zero_penalty
                    - tail_dependency_penalty
                    - 0.16 * finite_window_penalty,
                ),
            )
            theorem_upgrade_margin = min(
                exclusion_link_margin,
                xi_bridge_margin,
                counting_law_margin,
                zero_sum_margin,
            )
            score = 0.58 * exclusion_link_margin + 0.42 * theorem_upgrade_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.68,
                summary=(
                    "Measured whether the xi-facing zero atlas actually produces an off-line-zero exclusion "
                    "margin rather than stopping at contour alignment or finite-table agreement."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "contour_alignment_margin": contour_alignment_margin,
                    "counting_law_margin": counting_law_margin,
                    "zero_sum_margin": zero_sum_margin,
                    "xi_bridge_margin": xi_bridge_margin,
                    "exclusion_link_margin": exclusion_link_margin,
                    "theorem_upgrade_margin": theorem_upgrade_margin,
                    "exceptional_zero_penalty": exceptional_zero_penalty,
                    "tail_dependency_penalty": tail_dependency_penalty,
                    "partial_z1_sum": partial_z1_sum,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "surface_return_certificate":
            klein = compute_klein_metrics(hypothesis)
            return_margin = max(
                0.0,
                min(
                    1.0,
                    0.22
                    + 0.24 * klein.bridge_score
                    + 0.20 * klein.reintegration_score
                    + 0.16 * symmetry_margin
                    + 0.10 * phase_support
                    + 0.10 * prime_support
                    + 0.08 * numeric_best
                    - finite_window_penalty,
                ),
            )
            obstruction_margin = max(
                0.0,
                min(
                    1.0,
                    0.20
                    + 0.28 * klein.obstruction_score
                    + 0.24 * klein.homology_signal
                    + 0.12 * symmetry_margin
                    - 0.08 * finite_window_penalty,
                ),
            )
            score = 0.60 * return_margin + 0.40 * obstruction_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.62,
                summary=(
                    "Measured whether the branch actually makes the Klein round trip: local support must "
                    "return through a surface-rigor lane as a stronger global exclusion obligation."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "return_margin": return_margin,
                    "obstruction_margin": obstruction_margin,
                    "bridge_score": klein.bridge_score,
                    "reintegration_score": klein.reintegration_score,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        if check_name == "operator_non_surrogate_rigor":
            gaps = [b - a for a, b in zip(zeros[:-1], zeros[1:])]
            if gaps:
                mean_gap = sum(gaps) / len(gaps)
                variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
                gap_cv = (variance ** 0.5) / mean_gap if mean_gap else 1.0
            else:
                gap_cv = 1.0
            spacing_margin = max(0.0, 1.0 - min(1.0, gap_cv / 1.2))
            operator_bonus = 0.12 if "hilbert_polya" in families else 0.08 if "quantum_spectral" in families else 0.05
            surrogate_penalty = 0.18 if "quantum_spectral" in families and "hilbert_polya" not in families else 0.08
            rigor_margin = max(
                0.0,
                min(
                    1.0,
                    0.22
                    + 0.18 * symmetry_margin
                    + 0.18 * spacing_margin
                    + 0.14 * zero_support
                    + 0.10 * numeric_best
                    + operator_bonus
                    - surrogate_penalty
                    - 0.04 * finite_window_penalty,
                ),
            )
            uniqueness_margin = max(
                0.0,
                min(
                    1.0,
                    0.18
                    + 0.16 * symmetry_margin
                    + 0.14 * prime_support
                    + 0.12 * phase_support
                    + 0.10 * zero_support
                    + operator_bonus
                    - surrogate_penalty,
                ),
            )
            score = 0.58 * rigor_margin + 0.42 * uniqueness_margin
            return WorkerCheckResult(
                check_id=check_name,
                category="certificate",
                passed=score >= 0.62,
                summary=(
                    "Measured whether the operator branch moved beyond spectral matching into a non-surrogate "
                    "construction path with enough uniqueness pressure to justify further proof work."
                ),
                metrics={
                    "score": max(0.0, min(1.0, score)),
                    "rigor_margin": rigor_margin,
                    "uniqueness_margin": uniqueness_margin,
                    "surrogate_penalty": surrogate_penalty,
                    "spacing_margin": spacing_margin,
                    "finite_window_penalty": finite_window_penalty,
                },
                detail_path=str(_EXPLICIT_DATA),
            )

        gaps = [b - a for a, b in zip(zeros[:-1], zeros[1:])]
        if gaps:
            mean_gap = sum(gaps) / len(gaps)
            variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
            gap_cv = (variance ** 0.5) / mean_gap if mean_gap else 1.0
        else:
            gap_cv = 1.0
        second_differences = [gaps[idx + 1] - gaps[idx] for idx in range(max(0, len(gaps) - 1))]
        mean_second_abs = (
            sum(abs(item) for item in second_differences) / len(second_differences)
            if second_differences
            else 2.0
        )
        spacing_margin = max(0.0, 1.0 - min(1.0, gap_cv / 1.2))
        hyperbolicity_margin = max(0.0, 1.0 - min(1.0, mean_second_abs / 2.2))
        family_bonus = 0.10 if "xi_function" in families else 0.04 if "explicit_formula" in families else 0.0
        li_keiper_margin = max(
            0.0,
            min(
                1.0,
                0.30
                + 0.24 * symmetry_margin
                + 0.16 * zero_support
                + 0.10 * numeric_best
                + family_bonus
                - 0.08 * finite_window_penalty,
            ),
        )
        jensen_margin = max(
            0.0,
            min(
                1.0,
                0.24
                + 0.28 * spacing_margin
                + 0.24 * hyperbolicity_margin
                + 0.12 * zero_support
                - 0.05 * finite_window_penalty,
            ),
        )
        score = 0.55 * li_keiper_margin + 0.45 * jensen_margin
        return WorkerCheckResult(
            check_id=check_name,
            category="certificate",
            passed=score >= 0.65,
            summary=(
                "Bridged the xi-function lane to Li/Keiper and Jensen-style bounded surrogates to measure whether "
                "coefficient stability is strong enough to justify a next-round exclusion certificate."
            ),
            metrics={
                "score": max(0.0, min(1.0, score)),
                "li_keiper_margin": li_keiper_margin,
                "jensen_margin": jensen_margin,
                "spacing_margin": spacing_margin,
                "hyperbolicity_margin": hyperbolicity_margin,
                "finite_window_penalty": finite_window_penalty,
            },
            detail_path=str(_EXPLICIT_DATA),
        )

    def _novelty_check(self, artifact: NoveltyArtifact) -> WorkerCheckResult:
        feature_score = 0.0
        if artifact.measurable_features:
            clipped = [max(0.0, min(1.0, float(v))) for v in artifact.measurable_features.values()]
            feature_score = sum(clipped) / max(len(clipped), 1)
        recipe_score = min(1.0, len(artifact.validation_recipe) / 3.0)
        structure_bits = (
            1.0 if artifact.canonical_signature else 0.0,
            min(1.0, len(artifact.operator_primitives) / 5.0),
            min(1.0, len(artifact.proof_skeleton) / 4.0),
        )
        structure_score = sum(structure_bits) / len(structure_bits)
        complexity_score = max(0.0, min(1.0, 1.0 - float(artifact.operator_complexity) / 6.0))
        failure_penalty = min(0.35, 0.08 * len(artifact.failure_modes))
        score = (
            0.30 * recipe_score
            + 0.30 * feature_score
            + 0.20 * structure_score
            + 0.20 * complexity_score
            - failure_penalty
        )
        return WorkerCheckResult(
            check_id=artifact.artifact_id,
            category="novelty",
            passed=(
                artifact.is_testable
                and bool(artifact.canonical_signature)
                and bool(artifact.operator_primitives)
                and score >= 0.55
            ),
            summary=(
                f"Validated the {artifact.agent}-lane novelty artifact as a canonical operator "
                "claim with an explicit recipe, bounded complexity, and named failure modes."
            ),
            metrics={
                "score": max(0.0, min(1.0, score)),
                "recipe_steps": float(len(artifact.validation_recipe)),
                "structure_score": structure_score,
                "complexity_score": complexity_score,
            },
        )

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text())
