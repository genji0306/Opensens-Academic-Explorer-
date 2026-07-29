"""Curated seed packs for Agent C literature ingestion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DEFAULT_ALLOWLIST, PROJECT_ROOT, SEED_PACK_DIR
from .proof_attempts import materialize_proof_attempt_corpus

DEFAULT_SEED_PACKS = ("rh-core",)


def load_seed_pack(name: str) -> dict[str, Any]:
    _ensure_dynamic_seed_packs()
    slug = name.replace("-", "_")
    path = SEED_PACK_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown Riemann seed pack: {name}")
    payload = json.loads(path.read_text())
    payload["pack_path"] = str(path)
    return payload


def list_seed_packs() -> list[dict[str, Any]]:
    _ensure_dynamic_seed_packs()
    packs: list[dict[str, Any]] = []
    for path in sorted(SEED_PACK_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        packs.append(
            {
                "name": payload.get("name", path.stem),
                "description": payload.get("description", ""),
                "seed_count": len(payload.get("seeds", [])),
                "bibliography_count": len(payload.get("bibliography", [])),
                "path": str(path),
            }
        )
    return packs


def resolve_seed_inputs(
    pack_names: tuple[str, ...] = DEFAULT_SEED_PACKS,
    *,
    extra_seeds: tuple[str, ...] = (),
    extra_domains: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    seeds: list[str] = []
    domains: list[str] = []
    bibliography: list[dict[str, Any]] = []
    selected_packs: list[dict[str, Any]] = []

    for name in pack_names:
        pack = load_seed_pack(name)
        selected_packs.append(
            {
                "name": pack.get("name", name),
                "description": pack.get("description", ""),
                "pack_path": pack.get("pack_path", ""),
            }
        )
        for seed in pack.get("seeds", []):
            seeds.append(_resolve_locator(str(seed)))
        for domain in pack.get("allowlisted_domains", DEFAULT_ALLOWLIST):
            domains.append(str(domain))
        bibliography.extend(pack.get("bibliography", []))

    for seed in extra_seeds:
        seeds.append(_resolve_locator(seed))
    for domain in extra_domains:
        domains.append(domain)

    manifest = {
        "selected_packs": selected_packs,
        "seeds": _dedupe(seeds),
        "allowlisted_domains": _dedupe(domains or list(DEFAULT_ALLOWLIST)),
        "bibliography": bibliography,
    }
    return tuple(manifest["seeds"]), tuple(manifest["allowlisted_domains"]), manifest


def _resolve_locator(locator: str) -> str:
    if locator.startswith(("http://", "https://", "file://")):
        return locator
    path = Path(locator)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / locator).resolve())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _ensure_dynamic_seed_packs() -> None:
    materialize_proof_attempt_corpus()
