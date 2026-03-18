"""
OAE Data Registry — Centralized index for all material entries.

Maintains a JSON index at data/registry.json tracking materials across
sources (agent_cs, agent_pb, nemad, mc3d, icsd, user) and types
(superconductor, magnetic, crystal, general).
"""
from __future__ import annotations

import json
import logging
import hashlib
from pathlib import Path
from typing import Optional

from src.core.config import DATA_DIR

logger = logging.getLogger(__name__)

REGISTRY_PATH = DATA_DIR / "registry.json"


class DataRegistry:
    """Centralized material entry index with JSON persistence."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path or REGISTRY_PATH
        self._entries: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._entries = {e["material_id"]: e for e in data.get("entries", [])}
            except (json.JSONDecodeError, KeyError):
                logger.warning("Corrupt registry at %s — starting fresh", self._path)
                self._entries = {}
        else:
            self._entries = {}

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "count": len(self._entries),
            "entries": list(self._entries.values()),
        }
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, entry: dict) -> str:
        """Add a material entry. Returns material_id."""
        mid = entry.get("material_id") or self._generate_id(entry)
        entry["material_id"] = mid
        self._entries[mid] = entry
        return mid

    def get(self, material_id: str) -> Optional[dict]:
        return self._entries.get(material_id)

    def remove(self, material_id: str) -> bool:
        return self._entries.pop(material_id, None) is not None

    def update(self, material_id: str, **kwargs) -> bool:
        entry = self._entries.get(material_id)
        if entry is None:
            return False
        entry.update(kwargs)
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_by_composition(self, composition: str) -> list[dict]:
        comp_lower = composition.lower()
        return [e for e in self._entries.values()
                if e.get("composition", "").lower() == comp_lower]

    def find_by_type(self, material_type: str) -> list[dict]:
        return [e for e in self._entries.values()
                if e.get("material_type") == material_type]

    def find_by_source(self, source: str) -> list[dict]:
        return [e for e in self._entries.values()
                if e.get("source") == source]

    def find_by_family(self, family: str) -> list[dict]:
        return [e for e in self._entries.values()
                if family in e.get("tags", [])]

    def all_entries(self) -> list[dict]:
        return list(self._entries.values())

    @property
    def count(self) -> int:
        return len(self._entries)

    def stats(self) -> dict:
        """Summary statistics."""
        types: dict[str, int] = {}
        sources: dict[str, int] = {}
        for e in self._entries.values():
            t = e.get("material_type", "unknown")
            s = e.get("source", "unknown")
            types[t] = types.get(t, 0) + 1
            sources[s] = sources.get(s, 0) + 1
        return {"total": len(self._entries), "by_type": types, "by_source": sources}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_id(entry: dict) -> str:
        key = f"{entry.get('composition', '')}-{entry.get('source', '')}-{entry.get('material_type', '')}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"DataRegistry({len(self._entries)} entries)"
