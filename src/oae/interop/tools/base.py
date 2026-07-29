"""Core tool abstractions for the Phase G broker."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ToolSpec:
    """Declarative tool metadata — the part a registry indexes on."""

    name: str
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    compact_token_budget: int = 2_000       # per call, compact mode
    cache_ttl_s: float = 3600.0
    requires_network: bool = False


@dataclass(frozen=True)
class ToolCall:
    """Single invocation of a tool."""

    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        payload = {"tool": self.tool, "arguments": self._canonical(self.arguments)}
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _canonical(obj: Any) -> Any:
        if isinstance(obj, Mapping):
            return {k: ToolCall._canonical(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (list, tuple)):
            return [ToolCall._canonical(x) for x in obj]
        return obj


@dataclass(frozen=True)
class ToolResult:
    """Output of a tool call, shaped for compact-mode consumption."""

    tool: str
    ok: bool
    content: str = ""                        # compact textual summary
    data: Mapping[str, Any] = field(default_factory=dict)
    citations: tuple[str, ...] = field(default_factory=tuple)
    tokens_estimated: int = 0
    cached: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "content": self.content,
            "data": dict(self.data),
            "citations": list(self.citations),
            "tokens_estimated": self.tokens_estimated,
            "cached": self.cached,
            "error": self.error,
        }


class Tool(Protocol):
    """Duck-type satisfied by every tool the broker knows about."""

    spec: ToolSpec

    def run(self, arguments: Mapping[str, Any]) -> ToolResult: ...
