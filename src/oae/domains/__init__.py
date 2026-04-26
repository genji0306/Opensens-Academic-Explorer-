"""OAE domain packs (Phase D).

Re-exports the legacy :class:`DomainPack` protocol so that new packs
under ``src.oae.domains`` share one source of truth with the existing
``src.domains`` registry. New packs register themselves with that
registry on import — legacy callers pick them up automatically.
"""
from __future__ import annotations

from src.domains.base import (
    DomainPack,
    get_domain_pack,
    list_domain_packs,
    register_domain_pack,
)

__all__ = [
    "DomainPack",
    "get_domain_pack",
    "list_domain_packs",
    "register_domain_pack",
]
