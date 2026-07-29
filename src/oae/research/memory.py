"""Three-tier research memory (LabClaw-inspired).

The research memory stores the *why* behind promoted candidates across
campaigns. It has three tiers, each with a distinct role:

1. **Tier A — dossiers**: human-readable markdown files per candidate,
   written by :mod:`src.oae.research.dossier_writer`. This module
   records which dossier paths exist per candidate.

2. **Tier B — claim graph**: a persistent
   :class:`~src.oae.research.EvidenceGraph` of candidates, claims, and
   sources with supports/contradicts edges.

3. **Tier C — working memory**: short-lived, per-session scratch used
   by Agent R while reviewing a batch. Cleared automatically at session
   end; never persisted.

All tiers operate on JSON or markdown files under ``data/research_memory``
so nothing external is required for Phase C testing. Everything is
pure Python + stdlib.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from src.oae.kernel.schemas import ReviewBundle, TheoryCard
from src.oae.research.evidence_graph import (
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    empty_graph,
)

logger = logging.getLogger("ResearchMemory")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = PROJECT_ROOT / "data" / "research_memory"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DossierPointer:
    """A Tier-A pointer from a candidate to its markdown dossier."""

    candidate_id: str
    path: str
    campaign_id: str = ""
    family: str = ""


@dataclass
class WorkingMemory:
    """Tier-C scratch memory for the current review session.

    Deliberately mutable: this is ephemeral per-campaign context that
    Agent R reads and writes while processing a batch. Never persisted.
    """

    session_id: str
    scratch: dict[str, object] = field(default_factory=dict)

    def put(self, key: str, value: object) -> None:
        self.scratch[key] = value

    def get(self, key: str, default: object = None) -> object:
        return self.scratch.get(key, default)

    def clear(self) -> None:
        self.scratch.clear()


# ---------------------------------------------------------------------------
# Research memory store
# ---------------------------------------------------------------------------


@dataclass
class ResearchMemory:
    """Persistent store for Tiers A and B with an in-process Tier C.

    Persistence is opt-in: pass ``auto_persist=False`` for tests and
    in-memory runs. When enabled, the claim graph is written to
    ``data/research_memory/claim_graph.json`` on every mutation and the
    dossier index to ``data/research_memory/dossier_index.json``.
    """

    root: Path = field(default_factory=lambda: DEFAULT_ROOT)
    auto_persist: bool = False
    graph: EvidenceGraph = field(default_factory=empty_graph)
    dossiers: dict[str, DossierPointer] = field(default_factory=dict)
    working: WorkingMemory = field(
        default_factory=lambda: WorkingMemory(session_id="default")
    )

    # --- Tier A — dossier index --------------------------------------

    def register_dossier(self, pointer: DossierPointer) -> None:
        self.dossiers[pointer.candidate_id] = pointer
        if self.auto_persist:
            self._persist_dossier_index()

    def dossier_for(self, candidate_id: str) -> DossierPointer | None:
        return self.dossiers.get(candidate_id)

    # --- Tier B — claim graph ----------------------------------------

    def ingest_review_bundle(
        self,
        bundle: ReviewBundle,
        *,
        candidate_label: str = "",
    ) -> None:
        """Fold a :class:`ReviewBundle` into the persistent claim graph.

        Adds a candidate node, one claim node per theory card, and an
        appropriate supports/contradicts edge based on net support.
        """
        graph = self.graph
        cand_node = GraphNode(
            node_id=bundle.candidate_id,
            kind="candidate",
            label=candidate_label or bundle.candidate_id,
        )
        graph = graph.add_node(cand_node)

        for idx, card in enumerate(bundle.theory_cards):
            claim_id = f"{bundle.candidate_id}::claim::{idx}::{card.mechanism}"
            claim_node = GraphNode(
                node_id=claim_id,
                kind="claim",
                label=card.claim,
                attributes={
                    "mechanism": card.mechanism,
                    "conditions": card.conditions,
                },
            )
            graph = graph.add_node(claim_node)
            supports = card.net_support() >= 0.0
            graph = graph.link_claim(
                bundle.candidate_id,
                claim_id,
                supports=supports,
                weight=abs(card.net_support()),
            )
            for cite in card.citations:
                src_id = f"source::{cite.source}"
                if not graph.has_node(src_id):
                    graph = graph.add_node(
                        GraphNode(
                            node_id=src_id,
                            kind="source",
                            label=cite.title or cite.source,
                            attributes={"source": cite.source},
                        )
                    )
                graph = graph.add_edge(
                    GraphEdge(
                        src=claim_id,
                        dst=src_id,
                        kind="cites",
                        weight=max(0.0, min(1.0, cite.confidence)),
                    )
                )

        self.graph = graph
        if self.auto_persist:
            self._persist_graph()

    def claims_for(self, candidate_id: str) -> tuple[GraphNode, ...]:
        """Return every claim node linked to a candidate."""
        edges = self.graph.edges_to(candidate_id)
        claim_ids = {e.src for e in edges if e.kind in ("supports", "contradicts")}
        return tuple(
            n for n in self.graph.nodes_of_kind("claim") if n.node_id in claim_ids
        )

    def cards_for(self, candidate_id: str) -> tuple[TheoryCard, ...]:
        """Reconstruct minimal :class:`TheoryCard` stubs for quick lookup.

        This returns a lossy reconstruction (no citations) suitable for
        UI summaries — full fidelity lives in the original bundles.
        """
        claims = self.claims_for(candidate_id)
        cards: list[TheoryCard] = []
        for claim in claims:
            cards.append(
                TheoryCard(
                    claim=claim.label,
                    mechanism=claim.attributes.get("mechanism", ""),
                    conditions=claim.attributes.get("conditions", ""),
                )
            )
        return tuple(cards)

    # --- Tier C — working memory -------------------------------------

    def start_session(self, session_id: str) -> WorkingMemory:
        self.working = WorkingMemory(session_id=session_id)
        return self.working

    def end_session(self) -> None:
        self.working.clear()

    # --- persistence --------------------------------------------------

    def flush(self) -> None:
        """Explicitly persist Tier A index and Tier B graph to disk."""
        self._persist_dossier_index()
        self._persist_graph()

    def _persist_dossier_index(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "dossier_index.json"
        payload = [
            {
                "candidate_id": p.candidate_id,
                "path": p.path,
                "campaign_id": p.campaign_id,
                "family": p.family,
            }
            for p in self.dossiers.values()
        ]
        path.write_text(json.dumps(payload, indent=2))

    def _persist_graph(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "claim_graph.json"
        payload = {
            "nodes": [
                {
                    "id": n.node_id,
                    "kind": n.kind,
                    "label": n.label,
                    "attributes": n.attributes,
                }
                for n in self.graph.nodes
            ],
            "edges": [
                {
                    "src": e.src,
                    "dst": e.dst,
                    "kind": e.kind,
                    "weight": e.weight,
                    "attributes": e.attributes,
                }
                for e in self.graph.edges
            ],
        }
        path.write_text(json.dumps(payload, indent=2))

    # --- queries ------------------------------------------------------

    def summary(self) -> dict[str, int]:
        """Return a cheap overview of memory contents."""
        return {
            "dossiers": len(self.dossiers),
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "candidates": len(self.graph.nodes_of_kind("candidate")),
            "claims": len(self.graph.nodes_of_kind("claim")),
            "sources": len(self.graph.nodes_of_kind("source")),
        }


def ingest_bundles(
    memory: ResearchMemory,
    bundles: Iterable[ReviewBundle],
) -> None:
    """Fold an iterable of review bundles into a memory store."""
    for bundle in bundles:
        memory.ingest_review_bundle(bundle)
