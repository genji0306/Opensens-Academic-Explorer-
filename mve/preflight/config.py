"""Shared local dependency paths for offline probes and future fleet configuration."""

from pathlib import Path


def local_paths(home=None):
    home = Path.home() if home is None else Path(home)
    base = home / "Developer/Opensens"
    desktop = (
        home
        / "Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer"
    )
    return {
        "base": base,
        "vision": desktop / ".claude/worktrees/rh-handover-opus-deepseek-dc7dc2",
        "jev": base / "rh-jev-harness",
        "atlas": base / "worktrees/oae-rh-atlas-p0-20260924",
        "lean": base / "Opensens Academic Explorer/lean",
        "root": Path(__file__).resolve().parents[2],
        "openjev_python": base / "runtimes/openjev-venv/bin/python3",
        "lean_binary": home / ".elan/toolchains/leanprover--lean4---v4.29.0/bin/lean",
        "codex": home / ".local/bin/codex",
    }


PATHS = local_paths()
