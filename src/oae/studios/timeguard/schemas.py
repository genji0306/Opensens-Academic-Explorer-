"""Schemas for the Timeguard RH debate and forecast studio."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal


DebateRole = Literal[
    "BaselineAdvocate",
    "KleinAdvocate",
    "Skeptic",
    "Forecaster",
    "Moderator",
]
DebateTarget = Literal["baseline", "klein", "both"]


def _jsonify(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _jsonify(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    return value


@dataclass(frozen=True)
class SupportDocument:
    path: str
    title: str
    highlights: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class ComparableCampaign:
    campaign_id: str
    campaign_dir: str = ""
    topology_mode: str = "baseline"
    benchmark_mode: str = ""
    best_score: float = 0.0
    dominant_failures: tuple[str, ...] = field(default_factory=tuple)
    comparable_to_current: bool = False
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class RoundSignal:
    round_index: int
    best_candidate_id: str
    best_score: float
    topology_mode: str
    top_families: tuple[str, ...] = field(default_factory=tuple)
    unresolved_obligations: tuple[str, ...] = field(default_factory=tuple)
    resolved_obligations: tuple[str, ...] = field(default_factory=tuple)
    dead_end_patterns: tuple[str, ...] = field(default_factory=tuple)
    dominant_failures: tuple[str, ...] = field(default_factory=tuple)
    resolved_obligation_count: int = 0
    unresolved_obligation_count: int = 0
    novelty_count: int = 0
    certificate_count: int = 0
    certificate_pass_count: int = 0
    cross_lane_count: int = 0
    artifact_mix: dict[str, int] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)
    repeated_dead_end_counts: dict[str, int] = field(default_factory=dict)
    routing_feedback: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    @property
    def certificate_pass_rate(self) -> float:
        if self.certificate_count <= 0:
            return 0.0
        return self.certificate_pass_count / self.certificate_count

    def to_dict(self) -> dict[str, Any]:
        payload = _jsonify(self)
        payload["certificate_pass_rate"] = self.certificate_pass_rate
        return payload


@dataclass(frozen=True)
class CampaignEvidence:
    orchestrator_id: str
    topology_mode: str
    campaign_dir: str
    summary_path: str
    failure_atlas_path: str
    campaign_benchmark_path: str
    best_score: float
    best_candidate_id: str
    support_docs: tuple[SupportDocument, ...] = field(default_factory=tuple)
    round_signals: tuple[RoundSignal, ...] = field(default_factory=tuple)
    dominant_failures: tuple[str, ...] = field(default_factory=tuple)
    repeated_failures: dict[str, int] = field(default_factory=dict)
    repeated_dead_ends: dict[str, int] = field(default_factory=dict)
    repeated_obligations: dict[str, int] = field(default_factory=dict)
    comparable_campaigns: tuple[ComparableCampaign, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class OrchestratorScorecard:
    orchestrator_id: str
    topology_mode: str
    rounds: int
    best_score: float
    achievements: tuple[str, ...] = field(default_factory=tuple)
    remaining_work: tuple[str, ...] = field(default_factory=tuple)
    pros: tuple[str, ...] = field(default_factory=tuple)
    cons: tuple[str, ...] = field(default_factory=tuple)
    dominant_failures: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class DebateTurn:
    role: DebateRole
    target: DebateTarget
    achievements: tuple[str, ...] = field(default_factory=tuple)
    remaining_work: tuple[str, ...] = field(default_factory=tuple)
    pros: tuple[str, ...] = field(default_factory=tuple)
    cons: tuple[str, ...] = field(default_factory=tuple)
    verdict: str = ""
    next_work_packages: tuple[str, ...] = field(default_factory=tuple)
    trajectory_forecast: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class KleinEffortPhase:
    phase: str
    checkpoint: int
    title: str
    summary: str
    contribution_class: str
    status: str
    score: float = 0.0
    score_delta: float = 0.0
    highlights: tuple[str, ...] = field(default_factory=tuple)
    next_directions: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class KleinEffortDebateTurn:
    role: str
    focus: str
    findings: tuple[str, ...] = field(default_factory=tuple)
    blind_spots: tuple[str, ...] = field(default_factory=tuple)
    verdict: str = ""
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class MetricForecast:
    orchestrator_id: str
    topology_mode: str
    backend: str
    horizon: int
    confidence: float
    point_forecast: dict[str, tuple[float, ...]] = field(default_factory=dict)
    quantile_forecast: dict[str, dict[str, tuple[float, ...]]] = field(default_factory=dict)
    selected_dead_end_metrics: tuple[str, ...] = field(default_factory=tuple)
    auxiliary_campaign_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class WorkPackagePrediction:
    title: str
    why_now: str
    target_orchestrator: str
    expected_metric_delta: dict[str, float] = field(default_factory=dict)
    blocking_obligations: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    ranking_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class TimeguardContext:
    baseline: CampaignEvidence
    klein: CampaignEvidence
    support_docs: tuple[SupportDocument, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class TimeguardReport:
    generated_at: str
    context: TimeguardContext
    scorecards: tuple[OrchestratorScorecard, ...]
    debate_turns: tuple[DebateTurn, ...]
    forecasts: tuple[MetricForecast, ...]
    work_packages: tuple[WorkPackagePrediction, ...]
    phase_roadmap: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class KleinEffortDiscoveryReport:
    generated_at: str
    orchestrator_id: str
    campaign_dir: str
    best_score: float
    dominant_failures: tuple[str, ...] = field(default_factory=tuple)
    phase_timeline: tuple[KleinEffortPhase, ...] = field(default_factory=tuple)
    debate_turns: tuple[KleinEffortDebateTurn, ...] = field(default_factory=tuple)
    closed_routes: tuple[str, ...] = field(default_factory=tuple)
    capability_stack: tuple[str, ...] = field(default_factory=tuple)
    current_frontier: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class ExternalClaim:
    claim_id: str
    source_locator: str
    source_title: str
    source_kind: str
    source_tier: str
    claim_text: str
    route_family: str
    proof_object: str
    map_relation: str
    status: str
    target_orchestrator: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class FrontierDebateTurn:
    role: str
    focus: str
    findings: tuple[str, ...] = field(default_factory=tuple)
    cautions: tuple[str, ...] = field(default_factory=tuple)
    verdict: str = ""
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class OrchestratorSeedPack:
    name: str
    description: str
    target_orchestrator: str
    route_family: str
    proof_object: str
    claim_ids: tuple[str, ...] = field(default_factory=tuple)
    taboo_routes: tuple[str, ...] = field(default_factory=tuple)
    seeds: tuple[str, ...] = field(default_factory=tuple)
    allowlisted_domains: tuple[str, ...] = field(default_factory=tuple)
    bibliography: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    prompt: str = ""
    rationale: str = ""
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class OasisFrontierProfile:
    realname: str
    username: str
    bio: str
    persona: str
    age: int
    gender: str
    mbti: str
    country: str
    profession: str
    interested_topics: tuple[str, ...] = field(default_factory=tuple)
    debate_role: str = ""
    seed_focus: str = ""
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class ExternalFrontierReport:
    generated_at: str
    baseline_orchestrator_id: str
    klein_orchestrator_id: str
    current_frontier: tuple[str, ...] = field(default_factory=tuple)
    current_work_packages: tuple[str, ...] = field(default_factory=tuple)
    taboo_routes: tuple[str, ...] = field(default_factory=tuple)
    external_claims: tuple[ExternalClaim, ...] = field(default_factory=tuple)
    debate_turns: tuple[FrontierDebateTurn, ...] = field(default_factory=tuple)
    seed_packs: tuple[OrchestratorSeedPack, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class ExternalSeedPackLaunchReport:
    generated_at: str
    source_seed_pack_file: str
    selected_pack_name: str
    campaign_id: str
    topology_mode: str
    base_seed_packs: tuple[str, ...] = field(default_factory=tuple)
    materialized_seed_paths: tuple[str, ...] = field(default_factory=tuple)
    direct_seed_paths: tuple[str, ...] = field(default_factory=tuple)
    launch_bundle_dir: str = ""
    campaign_dir: str = ""
    summary_path: str = ""
    best_score: float = 0.0
    converged: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class OasisFrontierScaffoldReport:
    generated_at: str
    baseline_orchestrator_id: str
    klein_orchestrator_id: str
    baseline_campaign_dir: str
    klein_campaign_dir: str
    simulation_topic: str
    recommended_python: str
    support_docs: tuple[str, ...] = field(default_factory=tuple)
    current_frontier: tuple[str, ...] = field(default_factory=tuple)
    current_work_packages: tuple[str, ...] = field(default_factory=tuple)
    closed_routes: tuple[str, ...] = field(default_factory=tuple)
    capability_stack: tuple[str, ...] = field(default_factory=tuple)
    taboo_routes: tuple[str, ...] = field(default_factory=tuple)
    seed_packs: tuple[OrchestratorSeedPack, ...] = field(default_factory=tuple)
    profiles: tuple[OasisFrontierProfile, ...] = field(default_factory=tuple)
    seed_posts: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)


@dataclass(frozen=True)
class OasisOfflineSimulationReport:
    generated_at: str
    manifest_path: str
    db_path: str
    profile_count: int
    post_count: int
    comment_count: int
    trace_count: int
    warnings: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _jsonify(self)
