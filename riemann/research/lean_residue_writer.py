"""Per-round Lean skeleton writer — produces lean residue so Gate 1 passes (Phase 1 enabler)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

_VALID_CHARS = re.compile(r"[^A-Za-z0-9_]+")
_LEADING_DIGIT = re.compile(r"^(\d)")


def slugify(value: str) -> str:
    """Sanitize a string into a valid Lean identifier fragment.

    Keeps [A-Za-z0-9_], replaces other character runs with a single underscore,
    strips leading/trailing underscores, and prefixes a leading digit with `_`.
    """
    if not value:
        return "_"
    cleaned = _VALID_CHARS.sub("_", value).strip("_")
    if not cleaned:
        return "_"
    if _LEADING_DIGIT.match(cleaned):
        cleaned = f"_{cleaned}"
    return cleaned


def _resolve_target_dir(lean_rh_root: Path, campaign_id: str, round_index: int) -> Path:
    return (
        lean_rh_root
        / "Lemmas"
        / f"auto_{slugify(campaign_id)}"
        / f"round_{round_index:03d}"
    )


def _wrap_source(lean_source: str) -> str:
    stripped = lean_source.lstrip()
    if stripped.startswith("import"):
        return lean_source if lean_source.endswith("\n") else lean_source + "\n"
    body = lean_source.rstrip("\n")
    return f"import Mathlib\nnamespace RH.Auto\n\n{body}\n\nend RH.Auto\n"


def write_round_skeletons(
    *,
    lean_rh_root: Path,
    campaign_id: str,
    round_index: int,
    candidate_skeletons: list[tuple[str, str]],
) -> list[Path]:
    """Persist per-candidate Lean skeleton sources for a single round.

    Idempotent: existing files are skipped. Returns paths actually written this call.
    """
    target_dir = _resolve_target_dir(lean_rh_root, campaign_id, round_index)
    target_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for candidate_id, lean_source in candidate_skeletons:
        if not lean_source or not lean_source.strip():
            continue
        filename = f"{slugify(candidate_id)}.lean"
        dest = target_dir / filename
        if dest.exists():
            continue
        dest.write_text(_wrap_source(lean_source), encoding="utf-8")
        written.append(dest)
    return written


def cleanup_campaign_residue(lean_rh_root: Path, campaign_id: str) -> int:
    """Remove the auto-generated residue tree for a campaign. Returns file count removed."""
    campaign_dir = lean_rh_root / "Lemmas" / f"auto_{slugify(campaign_id)}"
    if not campaign_dir.exists():
        return 0
    removed = sum(1 for _ in campaign_dir.rglob("*.lean"))
    shutil.rmtree(campaign_dir)
    return removed
