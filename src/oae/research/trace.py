"""Research trace — append-only provenance log for Agent R runs.

Each :class:`TraceEntry` records one significant action during review:
a retrieval call, a ranking decision, a rationale, or a tool invocation.
Traces are written as JSONL under ``data/research_memory/traces/`` so
they can be replayed, diffed across campaigns, and surfaced in dossiers.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

logger = logging.getLogger("ResearchTrace")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRACES_DIR = PROJECT_ROOT / "data" / "research_memory" / "traces"


TraceKind = Literal[
    "prompt",
    "retrieval",
    "tool_call",
    "rationale",
    "decision",
    "error",
]


@dataclass(frozen=True)
class TraceEntry:
    """One entry in the research trace log."""

    timestamp: str
    session_id: str
    candidate_id: str
    kind: TraceKind
    payload: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass
class ResearchTrace:
    """Append-only logger that persists to JSONL on flush.

    The trace is safe to use in tests by passing ``auto_persist=False``
    and inspecting ``entries`` directly.
    """

    session_id: str = "default"
    entries: list[TraceEntry] = field(default_factory=list)
    traces_dir: Path = field(default_factory=lambda: DEFAULT_TRACES_DIR)
    auto_persist: bool = False

    # --- logging API --------------------------------------------------

    def log(
        self,
        *,
        candidate_id: str,
        kind: TraceKind,
        payload: dict[str, object] | None = None,
    ) -> TraceEntry:
        entry = TraceEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=self.session_id,
            candidate_id=candidate_id,
            kind=kind,
            payload=dict(payload or {}),
        )
        self.entries.append(entry)
        if self.auto_persist:
            self._append_to_disk(entry)
        return entry

    def log_prompt(self, candidate_id: str, prompt: str) -> TraceEntry:
        return self.log(
            candidate_id=candidate_id,
            kind="prompt",
            payload={"prompt": prompt},
        )

    def log_retrieval(
        self,
        candidate_id: str,
        source: str,
        n_hits: int,
    ) -> TraceEntry:
        return self.log(
            candidate_id=candidate_id,
            kind="retrieval",
            payload={"source": source, "n_hits": n_hits},
        )

    def log_tool_call(
        self,
        candidate_id: str,
        tool: str,
        duration_ms: float,
    ) -> TraceEntry:
        return self.log(
            candidate_id=candidate_id,
            kind="tool_call",
            payload={"tool": tool, "duration_ms": duration_ms},
        )

    def log_rationale(
        self,
        candidate_id: str,
        rationale: str,
    ) -> TraceEntry:
        return self.log(
            candidate_id=candidate_id,
            kind="rationale",
            payload={"rationale": rationale},
        )

    def log_decision(
        self,
        candidate_id: str,
        decision: str,
        reason: str,
    ) -> TraceEntry:
        return self.log(
            candidate_id=candidate_id,
            kind="decision",
            payload={"decision": decision, "reason": reason},
        )

    # --- queries ------------------------------------------------------

    def entries_for(self, candidate_id: str) -> tuple[TraceEntry, ...]:
        return tuple(e for e in self.entries if e.candidate_id == candidate_id)

    def entries_of_kind(self, kind: TraceKind) -> tuple[TraceEntry, ...]:
        return tuple(e for e in self.entries if e.kind == kind)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.entries:
            counts[entry.kind] = counts.get(entry.kind, 0) + 1
        counts["total"] = len(self.entries)
        return counts

    # --- persistence --------------------------------------------------

    def flush(self) -> Path:
        """Write the entire trace to a JSONL file and return its path."""
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        path = self.traces_dir / f"{self.session_id}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for entry in self.entries:
                fh.write(entry.to_json() + "\n")
        return path

    def _append_to_disk(self, entry: TraceEntry) -> None:
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        path = self.traces_dir / f"{self.session_id}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
