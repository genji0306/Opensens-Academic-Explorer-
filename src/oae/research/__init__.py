"""Research memory, trace, and evidence graph (Phases B + C)."""
from __future__ import annotations

from .dossier_writer import DEFAULT_DOSSIER_ROOT, DossierWriter
from .evidence_graph import (
    CandidateNode,
    ClaimNode,
    ContradictionEdge,
    EvidenceGraph,
    EvidenceNode,
    GraphEdge,
    GraphNode,
    empty_graph,
)
from .memory import (
    DEFAULT_ROOT,
    DossierPointer,
    ResearchMemory,
    WorkingMemory,
    ingest_bundles,
)
from .harness import (
    HarnessLane,
    ResearchHarness,
    build_default_harnesses,
    build_riemann_harness,
    build_rtap_harness,
    build_sensing_studio_harness,
)
from .proof_engine import (
    DEFAULT_MODULES,
    ProofEngineResult,
    available_modules,
    build_proof_engine_plan,
    run_proof_engine,
)
from .trace import DEFAULT_TRACES_DIR, ResearchTrace, TraceEntry, TraceKind

__all__ = [
    # evidence graph
    "GraphNode",
    "GraphEdge",
    "CandidateNode",
    "ClaimNode",
    "EvidenceNode",
    "ContradictionEdge",
    "EvidenceGraph",
    "empty_graph",
    # memory
    "ResearchMemory",
    "WorkingMemory",
    "DossierPointer",
    "ingest_bundles",
    "DEFAULT_ROOT",
    # trace
    "ResearchTrace",
    "TraceEntry",
    "TraceKind",
    "DEFAULT_TRACES_DIR",
    # harness
    "HarnessLane",
    "ResearchHarness",
    "build_riemann_harness",
    "build_rtap_harness",
    "build_sensing_studio_harness",
    "build_default_harnesses",
    "DEFAULT_MODULES",
    "ProofEngineResult",
    "available_modules",
    "build_proof_engine_plan",
    "run_proof_engine",
    # dossier
    "DossierWriter",
    "DEFAULT_DOSSIER_ROOT",
]
