"""Agent Q — disciplined quantum/spectral surrogate generation."""
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


class QuantumAgent:
    """Generate simulator-backed operator surrogates, not proof claims."""

    name = "Q"

    def run(
        self,
        hypotheses: tuple[HypothesisCandidate, ...],
    ) -> tuple[NoveltyArtifact, ...]:
        data = self._read_json(_EXPLICIT_DATA)
        zeros = np.asarray(data.get("zeros", []), dtype=float)
        prime_powers = np.asarray(data.get("prime_powers", []), dtype=float)
        metrics = self._derive_metrics(zeros, prime_powers)
        if metrics is None:
            return ()

        artifacts: list[NoveltyArtifact] = []
        for hypothesis in hypotheses:
            if not set(hypothesis.ingredient_families) & {
                "hilbert_polya",
                "quantum_spectral",
                "random_matrix",
            }:
                continue
            digest = hypothesis.candidate_id.split("-")[-1]
            artifacts.append(self._spectral_surrogate_artifact(hypothesis, digest, metrics))
        return tuple(artifacts)

    def _spectral_surrogate_artifact(
        self,
        hypothesis: HypothesisCandidate,
        digest: str,
        metrics: dict[str, float],
    ) -> NoveltyArtifact:
        validation_recipe = (
            "construct a symmetric Jacobi surrogate from the first normalized zero gaps",
            "verify the surrogate spectrum remains real and ordered under deterministic bounded perturbation",
            "compare normalized surrogate gap statistics against the observed zero-gap profile before promoting the claim",
        )
        failure_modes = (
            "finite_window_only",
            "surrogate_is_not_unique",
            "spectral_matching_is_not_a_proof",
        )
        canonical = canonicalize_operator_claim(
            operator_family="self_adjoint_gap_surrogate",
            operator_primitives=(
                "SELF_ADJOINT",
                "EIGENVALUE_MAP",
                "TRACE_FORMULA",
                "KERNEL_OPERATOR",
                "BOUNDS",
            ),
            input_types=("operator", "spectral_object"),
            output_type="spectral_object",
            assumptions=(
                *hypothesis.assumptions,
                "the Jacobi surrogate is only a simulator-backed proxy",
            ),
            invariances=("spectral_reality", "ordered_gap_structure"),
        )
        complexity, terms = complexity_score(
            node_count=5,
            depth=3,
            primitive_families=2,
            assumptions_count=len(hypothesis.assumptions) + 1,
            numerical_instability=max(0.0, 1.0 - metrics["perturbation_stability"]),
            auxiliary_lemma_count=max(2, len(hypothesis.unresolved_proof_obligations)),
            spectral_nonconstructiveness_penalty=0.20,
        )
        exact_claim = (
            "Any operator-style RH hypothesis promoted by the loop must admit a self-adjoint "
            "surrogate whose low-order spectrum stays real under bounded perturbation and whose "
            "normalized gap statistics remain close to the observed zero-gap profile."
        )
        proof = build_proof_skeleton(
            statement=exact_claim,
            canonical_signature=canonical["canonical_signature"],
            obligations=(
                *hypothesis.unresolved_proof_obligations,
                "upgrade the surrogate into a rigorous operator construction",
            ),
            validation_recipe=validation_recipe,
            failure_modes=failure_modes,
        )
        return NoveltyArtifact(
            artifact_id=f"q-jacobi-surrogate-{digest}",
            agent="Q",
            title="Jacobi Spectral Surrogate",
            observation=(
                "A deterministic symmetric Jacobi matrix built from normalized zero gaps gives a "
                "disciplined spectral proxy: the spectrum is real by construction, so what matters "
                "is how stable the ordered gaps remain and how closely they track the observed zeros."
            ),
            exact_claim=exact_claim,
            linked_hypothesis_id=hypothesis.candidate_id,
            validation_recipe=validation_recipe,
            measurable_features={
                "spectral_reality_score": metrics["spectral_reality_score"],
                "spacing_match_score": metrics["spacing_match_score"],
                "perturbation_stability": metrics["perturbation_stability"],
                "trace_balance_score": metrics["trace_balance_score"],
            },
            operator_family="self_adjoint_gap_surrogate",
            operator_primitives=tuple(canonical["operator_primitives"]),
            canonical_signature=canonical["canonical_signature"],
            operator_complexity=complexity,
            complexity_terms=terms,
            proof_skeleton=proof,
            failure_modes=failure_modes,
            supporting_paths=(str(_EXPLICIT_DATA),),
        )

    def _derive_metrics(
        self,
        zeros: np.ndarray,
        prime_powers: np.ndarray,
    ) -> dict[str, float] | None:
        if zeros.size < 8:
            return None
        n = min(24, zeros.size - 1)
        gaps = np.diff(zeros[: n + 1])
        mean_gap = float(np.mean(gaps)) or 1.0
        norm_gaps = gaps / mean_gap

        diag = norm_gaps - float(np.mean(norm_gaps))
        off_diag = 0.5 * np.sqrt(np.maximum(norm_gaps[:-1] * norm_gaps[1:], 0.0))
        jacobi = np.diag(diag)
        jacobi += np.diag(off_diag, k=1)
        jacobi += np.diag(off_diag, k=-1)
        eigenvalues = np.linalg.eigvalsh(jacobi)

        spectral_reality_score = 1.0
        eig_gaps = np.diff(eigenvalues)
        eig_gap_mean = float(np.mean(eig_gaps)) if eig_gaps.size else 1.0
        if eig_gaps.size:
            eig_norm_gaps = eig_gaps / (eig_gap_mean or 1.0)
            m = min(eig_norm_gaps.size, norm_gaps.size)
            spacing_drift = float(np.mean(np.abs(eig_norm_gaps[:m] - norm_gaps[:m])))
            spacing_match_score = float(max(0.0, min(1.0, 1.0 - spacing_drift)))
        else:
            spacing_match_score = 0.0

        perturb = jacobi + 0.05 * np.diag(np.sin(np.arange(jacobi.shape[0], dtype=float)))
        perturbed = np.linalg.eigvalsh(perturb)
        scale = float(np.std(eigenvalues)) or 1.0
        drift = float(np.mean(np.abs(perturbed - eigenvalues))) / scale
        perturbation_stability = float(max(0.0, min(1.0, 1.0 - drift)))

        trace_balance = abs(float(np.trace(jacobi))) / max(float(jacobi.shape[0]), 1.0)
        trace_balance_score = float(max(0.0, min(1.0, 1.0 - trace_balance)))

        prime_support = 0.0
        if prime_powers.ndim == 2 and prime_powers.shape[1] >= 2:
            prime_support = float(max(0.0, min(1.0, prime_powers.shape[0] / 25.0)))

        return {
            "spectral_reality_score": spectral_reality_score,
            "spacing_match_score": 0.75 * spacing_match_score + 0.25 * prime_support,
            "perturbation_stability": perturbation_stability,
            "trace_balance_score": trace_balance_score,
        }

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text())
