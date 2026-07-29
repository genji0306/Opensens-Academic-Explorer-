"""Declarative manifest of the Phase I REST endpoints."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

HTTPMethod = Literal["GET", "POST", "PUT", "DELETE"]


@dataclass(frozen=True)
class PhaseIEndpoint:
    """One endpoint in the Phase I REST surface."""

    path: str
    method: HTTPMethod
    summary: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    request_schema: str = ""
    response_schema: str = ""


@dataclass(frozen=True)
class PhaseIManifest:
    """Ordered manifest of every new endpoint Phase I exposes."""

    endpoints: tuple[PhaseIEndpoint, ...]

    def by_tag(self, tag: str) -> tuple[PhaseIEndpoint, ...]:
        return tuple(e for e in self.endpoints if tag in e.tags)

    def path_to_endpoint(self) -> dict[str, PhaseIEndpoint]:
        return {e.path: e for e in self.endpoints}

    def to_dicts(self) -> list[dict]:
        return [
            {
                "path": e.path,
                "method": e.method,
                "summary": e.summary,
                "tags": list(e.tags),
                "request_schema": e.request_schema,
                "response_schema": e.response_schema,
            }
            for e in self.endpoints
        ]


def build_phase_i_manifest() -> PhaseIManifest:
    """Return the canonical Phase I REST manifest."""
    endpoints = (
        PhaseIEndpoint(
            path="/api/v1/campaigns/{campaign_id}/review",
            method="GET",
            summary="Agent R review bundles for every promoted candidate.",
            tags=("review", "agent_r"),
            response_schema="ReviewBundleMap",
        ),
        PhaseIEndpoint(
            path="/api/v1/campaigns/{campaign_id}/verification",
            method="GET",
            summary="Snorkel verifier output per candidate plus run-level report.",
            tags=("verification", "snorkel"),
            response_schema="VerificationBundleMap",
        ),
        PhaseIEndpoint(
            path="/api/v1/candidates/{candidate_id}/dossier",
            method="GET",
            summary="Deterministic markdown dossier written by DossierWriter.",
            tags=("review", "dossier"),
            response_schema="DossierMarkdown",
        ),
        PhaseIEndpoint(
            path="/api/v1/sensing_sessions/{session_id}/timeline",
            method="GET",
            summary="Recursive sensing session timeline (round-by-round).",
            tags=("sensing", "timeline"),
            response_schema="SensingTimeline",
        ),
        PhaseIEndpoint(
            path="/api/v1/sensing_sessions/{session_id}/observer",
            method="GET",
            summary="Observer Studio scores + routing decisions for each round.",
            tags=("sensing", "observer"),
            response_schema="ObserverScorecard",
        ),
        PhaseIEndpoint(
            path="/api/v1/simulation/mof-1k",
            method="GET",
            summary="Metadata for the MOF-1k-relaxed synthetic dataset.",
            tags=("simulation", "dataset"),
            response_schema="SimulationDatasetMeta",
        ),
        PhaseIEndpoint(
            path="/api/v1/benchmarks/ranking",
            method="POST",
            summary="Run the Phase I ranking benchmark on demand.",
            tags=("benchmark",),
            response_schema="BenchmarkReport",
        ),
        PhaseIEndpoint(
            path="/api/v1/benchmarks/calibration",
            method="POST",
            summary="Run the Phase I cross-studio calibration suite.",
            tags=("benchmark", "calibration"),
            response_schema="CalibrationResult",
        ),
        PhaseIEndpoint(
            path="/api/v1/tools/provenance",
            method="GET",
            summary="Tool broker provenance log (last N entries).",
            tags=("tools", "provenance"),
            response_schema="ProvenanceLog",
        ),
    )
    return PhaseIManifest(endpoints=endpoints)


def default_manifest() -> PhaseIManifest:
    return build_phase_i_manifest()
