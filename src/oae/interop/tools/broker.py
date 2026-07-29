"""Tool broker — Phase G entry point.

The broker sits between Agent R (or any other consumer) and a registry
of ``Tool`` objects. It enforces a whitelist, caches results, truncates
payloads to fit a compact-mode token budget, and appends a provenance
record to a JSONL log for every call.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional

from .base import Tool, ToolCall, ToolResult
from .cache import ToolCache

logger = logging.getLogger("ToolBroker")


class ToolBrokerError(RuntimeError):
    """Raised on broker-level failures (denied tools, bad arguments)."""


@dataclass
class BrokerConfig:
    """Configuration for the ToolBroker."""

    whitelist: frozenset[str] = field(default_factory=frozenset)
    compact_mode: bool = True
    max_total_tokens: int = 12_000      # Phase E/G exit criterion
    allow_network: bool = False         # offline-first default
    provenance_path: Optional[Path] = None
    cache_dir: Optional[Path] = None


@dataclass
class ToolBroker:
    """Whitelist-enforcing, cache-backed, provenance-logged tool broker."""

    config: BrokerConfig = field(default_factory=BrokerConfig)
    tools: dict[str, Tool] = field(default_factory=dict)
    cache: ToolCache = field(default_factory=ToolCache)
    _tokens_used: int = 0
    _provenance: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.config.cache_dir is not None and self.cache.persist_dir is None:
            self.cache = ToolCache(persist_dir=Path(self.config.cache_dir))

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def register(self, tool: Tool) -> None:
        name = tool.spec.name
        if self.config.whitelist and name not in self.config.whitelist:
            raise ToolBrokerError(f"tool {name!r} is not on the whitelist")
        if tool.spec.requires_network and not self.config.allow_network:
            logger.debug("registering network tool %s in offline broker", name)
        self.tools[name] = tool

    def register_all(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def available_tools(self) -> list[str]:
        return sorted(self.tools.keys())

    # ------------------------------------------------------------------
    # Call path
    # ------------------------------------------------------------------

    def call(self, tool_name: str, **arguments) -> ToolResult:
        if tool_name not in self.tools:
            raise ToolBrokerError(f"unknown tool: {tool_name}")
        tool = self.tools[tool_name]

        if self.config.whitelist and tool_name not in self.config.whitelist:
            raise ToolBrokerError(f"tool {tool_name!r} not on whitelist")

        if tool.spec.requires_network and not self.config.allow_network:
            raise ToolBrokerError(
                f"tool {tool_name!r} requires network but broker is offline"
            )

        call = ToolCall(tool=tool_name, arguments=dict(arguments))
        cached = self.cache.get(call)
        if cached is not None:
            self._log_provenance(call, cached, from_cache=True)
            return cached

        t0 = time.time()
        try:
            result = tool.run(call.arguments)
        except Exception as exc:  # broker must never crash the loop
            logger.warning("tool %s raised %s", tool_name, exc)
            result = ToolResult(tool=tool_name, ok=False, error=str(exc))

        if self.config.compact_mode:
            result = self._compact(tool, result)

        self._tokens_used += result.tokens_estimated
        if self._tokens_used > self.config.max_total_tokens:
            logger.warning(
                "tool broker exceeded compact-mode budget: %d / %d tokens",
                self._tokens_used, self.config.max_total_tokens,
            )

        self.cache.put(call, result, ttl_s=tool.spec.cache_ttl_s)
        self._log_provenance(call, result, elapsed=time.time() - t0)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compact(self, tool: Tool, result: ToolResult) -> ToolResult:
        budget = tool.spec.compact_token_budget
        if result.tokens_estimated <= budget and len(result.content) <= budget * 4:
            return result

        max_chars = budget * 4
        content = result.content
        if len(content) > max_chars:
            content = content[: max_chars - 3] + "..."
        tokens = max(1, len(content) // 4)
        return ToolResult(
            tool=result.tool,
            ok=result.ok,
            content=content,
            data=result.data,
            citations=result.citations,
            tokens_estimated=tokens,
            cached=result.cached,
            error=result.error,
        )

    def _log_provenance(
        self,
        call: ToolCall,
        result: ToolResult,
        *,
        from_cache: bool = False,
        elapsed: float = 0.0,
    ) -> None:
        record = {
            "ts": time.time(),
            "tool": call.tool,
            "fingerprint": call.fingerprint(),
            "arguments": dict(call.arguments),
            "ok": result.ok,
            "cached": from_cache or result.cached,
            "tokens_estimated": result.tokens_estimated,
            "citations": list(result.citations),
            "elapsed_s": round(elapsed, 4),
        }
        self._provenance.append(record)
        if self.config.provenance_path is not None:
            path = Path(self.config.provenance_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

    def provenance(self) -> list[dict]:
        return list(self._provenance)

    def reset_budget(self) -> None:
        self._tokens_used = 0
