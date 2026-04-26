"""Two-tier cache (in-memory + optional on-disk) for the tool broker."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .base import ToolCall, ToolResult


@dataclass
class _Entry:
    result: ToolResult
    expires_at: float


@dataclass
class ToolCache:
    """LRU-ish cache with TTL. File persistence is opt-in."""

    persist_dir: Optional[Path] = None
    max_entries: int = 256
    _memory: dict[str, _Entry] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        if self.persist_dir is not None:
            self.persist_dir = Path(self.persist_dir)
            self.persist_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def get(self, call: ToolCall) -> Optional[ToolResult]:
        key = call.fingerprint()
        entry = self._memory.get(key)
        now = time.time()
        if entry is not None and entry.expires_at > now:
            self.hits += 1
            return ToolResult(**{**entry.result.to_dict(), "cached": True})
        if entry is not None:
            self._memory.pop(key, None)

        if self.persist_dir is not None:
            path = self.persist_dir / f"{key}.json"
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if payload.get("expires_at", 0) > now:
                        result = ToolResult(
                            tool=payload["result"]["tool"],
                            ok=payload["result"]["ok"],
                            content=payload["result"].get("content", ""),
                            data=payload["result"].get("data", {}),
                            citations=tuple(payload["result"].get("citations", [])),
                            tokens_estimated=payload["result"].get("tokens_estimated", 0),
                            cached=True,
                        )
                        self._memory[key] = _Entry(result=result, expires_at=payload["expires_at"])
                        self.hits += 1
                        return result
                except Exception:
                    pass
        self.misses += 1
        return None

    def put(self, call: ToolCall, result: ToolResult, ttl_s: float) -> None:
        key = call.fingerprint()
        expires_at = time.time() + max(0.0, ttl_s)
        self._memory[key] = _Entry(result=result, expires_at=expires_at)
        if len(self._memory) > self.max_entries:
            oldest = min(self._memory.items(), key=lambda kv: kv[1].expires_at)
            self._memory.pop(oldest[0], None)

        if self.persist_dir is not None:
            path = self.persist_dir / f"{key}.json"
            payload = {
                "expires_at": expires_at,
                "result": result.to_dict(),
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._memory)}
