"""Recursive RH research orchestrator.

This package adds a meta-orchestrator above the existing numeric Riemann
zero loop. The original ``riemann.orchestrator.run()`` remains intact and is
used here as one validation worker among literature mapping, hypothesis
synthesis, modelling, and observer review.
"""
from __future__ import annotations

from .config import RiemannResearchConfig
from .orchestrator import run_campaign
from .seed_pack import list_seed_packs, load_seed_pack, resolve_seed_inputs

__all__ = [
    "RiemannResearchConfig",
    "run_campaign",
    "load_seed_pack",
    "list_seed_packs",
    "resolve_seed_inputs",
]
