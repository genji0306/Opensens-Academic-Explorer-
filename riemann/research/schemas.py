"""Schemas exchanged by the recursive RH research agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal


SourceKind = Literal["local_file", "url"]
ArtifactAgent = Literal["M", "Q", "T", "K"]
RoutingTarget = Literal["stop", "iterate"]


def _jsonify(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _jsonify(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    return value


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    locator: str
    title: str
    authors: tuple[str, ...] = field(default_factory=tuple)
    year: int | None = None
    source_kind: SourceKind = "local_file"
    retrieval_hash: str = ""
    cache_path: str = ""
    provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class ApproachCard:
    approach_id: str
    family: str
    core_claim: str
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    mechanism: str = ""
    proof_obligations: tuple[str, ...] = field(default_factory=tuple)
    known_blockers: tuple[str, ...] = field(default_factory=tuple)
    cited_sources: tuple[str, ...] = field(default_factory=tuple)
    executable_checks: tuple[str, ...] = field(default_factory=tuple)
    observer_scores: dict[str, float] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class HypothesisCandidate:
    candidate_id: str
    claim: str
    ingredient_approach_ids: tuple[str, ...]
    ingredient_families: tuple[str, ...]
    compatibility_checks: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    unresolved_proof_obligations: tuple[str, ...] = field(default_factory=tuple)
    predicted_consequences: tuple[str, ...] = field(default_factory=tuple)
    risk_flags: tuple[str, ...] = field(default_factory=tuple)
    synthesis_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class NoveltyArtifact:
    artifact_id: str
    agent: ArtifactAgent
    title: str
    observation: str
    exact_claim: str = ""
    linked_hypothesis_id: str = ""
    validation_recipe: tuple[str, ...] = field(default_factory=tuple)
    measurable_features: dict[str, float] = field(default_factory=dict)
    operator_family: str = ""
    operator_primitives: tuple[str, ...] = field(default_factory=tuple)
    canonical_signature: str = ""
    operator_complexity: float = 0.0
    complexity_terms: dict[str, float] = field(default_factory=dict)
    proof_skeleton: tuple[str, ...] = field(default_factory=tuple)
    lean_skeleton: str = ""
    failure_modes: tuple[str, ...] = field(default_factory=tuple)
    supporting_paths: tuple[str, ...] = field(default_factory=tuple)
    advisory_only: bool = True

    @property
    def is_testable(self) -> bool:
        return bool(self.exact_claim and self.validation_recipe)

    def to_dict(self) -> dict[str, Any]:
        payload = _jsonify(self)
        payload["is_testable"] = self.is_testable
        return payload


@dataclass(frozen=True)
class AlgorithmProposal:
    proposal_id: str
    hypothesis_id: str
    numeric_tasks: tuple[str, ...] = field(default_factory=tuple)
    logical_checks: tuple[str, ...] = field(default_factory=tuple)
    explicit_formula_checks: tuple[str, ...] = field(default_factory=tuple)
    certificate_checks: tuple[str, ...] = field(default_factory=tuple)
    modelling_tasks: tuple[str, ...] = field(default_factory=tuple)
    rejected_novelty_ids: tuple[str, ...] = field(default_factory=tuple)
    success_criteria: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class WorkerCheckResult:
    check_id: str
    category: str
    passed: bool
    summary: str
    metrics: dict[str, float] = field(default_factory=dict)
    detail_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class AlgorithmExecution:
    proposal_id: str
    hypothesis_id: str
    executed_checks: tuple[WorkerCheckResult, ...] = field(default_factory=tuple)
    numerical_support: float = 0.0
    reproducibility: float = 0.0
    consistency_with_known_results: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class EvaluationComponents:
    proof_obligation_reduction: float
    consistency_with_known_results: float
    reproducibility: float
    contradiction_penalty: float
    numerical_support: float
    novelty: float
    visualization_coherence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class ResearchEvaluation:
    candidate_id: str
    round_index: int
    score: float
    components: EvaluationComponents
    contradiction_summary: str
    progress_delta: float
    unresolved_obligations: tuple[str, ...] = field(default_factory=tuple)
    resolved_obligations: tuple[str, ...] = field(default_factory=tuple)
    check_results: tuple[WorkerCheckResult, ...] = field(default_factory=tuple)
    novelty_artifact_ids: tuple[str, ...] = field(default_factory=tuple)
    recommended_actions: tuple[str, ...] = field(default_factory=tuple)
    dead_end_patterns: tuple[str, ...] = field(default_factory=tuple)
    promoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class RoutingDecision:
    target: RoutingTarget
    reason: str
    continue_loop: bool
    feedback: dict[str, tuple[str, ...]] = field(default_factory=dict)
    stop_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class CorpusIngestionResult:
    sources: tuple[SourceRecord, ...]
    approaches: tuple[ApproachCard, ...]
    skipped: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class CampaignRoundRecord:
    round_index: int
    hypotheses: tuple[HypothesisCandidate, ...]
    proposals: tuple[AlgorithmProposal, ...]
    novelty_artifacts: tuple[NoveltyArtifact, ...]
    evaluations: tuple[ResearchEvaluation, ...]
    routing: RoutingDecision

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)
