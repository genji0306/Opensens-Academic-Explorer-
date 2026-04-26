"""Evidence graph — candidate → claim → source → contradiction edges.

An append-only graph that research memory uses to track *why* a
candidate was promoted or rejected across campaigns. Nodes and edges
are frozen dataclasses; the graph itself offers immutable updates via
``add_*`` methods that return a new graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

NodeKind = Literal["candidate", "claim", "source"]
EdgeKind = Literal["supports", "contradicts", "cites", "derived_from"]


@dataclass(frozen=True)
class GraphNode:
    """A node in the evidence graph."""

    node_id: str
    kind: NodeKind
    label: str = ""
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """A directed, typed edge between two nodes."""

    src: str
    dst: str
    kind: EdgeKind
    weight: float = 1.0
    attributes: dict[str, str] = field(default_factory=dict)


# Aliases for the specific node types the plan calls out explicitly.
CandidateNode = GraphNode
ClaimNode = GraphNode
EvidenceNode = GraphNode
ContradictionEdge = GraphEdge


@dataclass(frozen=True)
class EvidenceGraph:
    """Append-only directed graph of candidates, claims, and sources.

    All mutations return a new ``EvidenceGraph``; the original is left
    untouched. This keeps the loop safe from accidental shared state.
    """

    nodes: tuple[GraphNode, ...] = field(default_factory=tuple)
    edges: tuple[GraphEdge, ...] = field(default_factory=tuple)

    # ----- queries -----

    def has_node(self, node_id: str) -> bool:
        return any(n.node_id == node_id for n in self.nodes)

    def get_node(self, node_id: str) -> GraphNode | None:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def nodes_of_kind(self, kind: NodeKind) -> tuple[GraphNode, ...]:
        return tuple(n for n in self.nodes if n.kind == kind)

    def edges_from(self, node_id: str) -> tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.src == node_id)

    def edges_to(self, node_id: str) -> tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.dst == node_id)

    def contradictions_for(self, candidate_id: str) -> tuple[GraphEdge, ...]:
        """Return every contradiction edge incident to ``candidate_id``."""
        return tuple(
            e for e in self.edges
            if e.kind == "contradicts" and candidate_id in (e.src, e.dst)
        )

    # ----- immutable builders -----

    def add_node(self, node: GraphNode) -> "EvidenceGraph":
        if self.has_node(node.node_id):
            return self
        return replace(self, nodes=self.nodes + (node,))

    def add_edge(self, edge: GraphEdge) -> "EvidenceGraph":
        # Only add edges whose endpoints exist; enforces graph integrity.
        if not (self.has_node(edge.src) and self.has_node(edge.dst)):
            raise ValueError(
                f"Cannot add edge {edge.src}->{edge.dst}: missing endpoint"
            )
        return replace(self, edges=self.edges + (edge,))

    def link_claim(
        self,
        candidate_id: str,
        claim_id: str,
        *,
        supports: bool = True,
        weight: float = 1.0,
    ) -> "EvidenceGraph":
        """Attach an existing claim node to an existing candidate node."""
        kind: EdgeKind = "supports" if supports else "contradicts"
        edge = GraphEdge(src=claim_id, dst=candidate_id, kind=kind, weight=weight)
        return self.add_edge(edge)


def empty_graph() -> EvidenceGraph:
    """Return a fresh empty evidence graph."""
    return EvidenceGraph()
