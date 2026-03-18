"""
OAE Laboratory Protocol Registry — Discovers and serves protocol definitions.
"""
from __future__ import annotations

import logging
from typing import Optional

from laboratory.protocol import LabProtocol

logger = logging.getLogger("Laboratory.Registry")

# Registry of all built-in protocols (populated by imports below)
_PROTOCOLS: dict[str, LabProtocol] = {}


def register_protocol(protocol: LabProtocol):
    """Register a protocol in the global registry."""
    _PROTOCOLS[protocol.protocol_id] = protocol


def get_protocol(protocol_id: str) -> Optional[LabProtocol]:
    """Look up a protocol by ID."""
    _ensure_loaded()
    return _PROTOCOLS.get(protocol_id)


def list_protocols() -> list[dict]:
    """List all available protocols as summary dicts."""
    _ensure_loaded()
    return [
        {
            "protocol_id": p.protocol_id,
            "name": p.name,
            "description": p.description,
            "material_type": p.material_type,
            "n_stages": len(p.stages),
        }
        for p in _PROTOCOLS.values()
    ]


def _ensure_loaded():
    """Lazy-load all built-in protocols on first access."""
    if _PROTOCOLS:
        return
    try:
        from laboratory.protocols import discovery
        from laboratory.protocols import structure_prediction
        from laboratory.protocols import xrd_analysis
        from laboratory.protocols import magnetic_study
        from laboratory.protocols import rtap_exploration
        from laboratory.protocols import verification
    except ImportError as e:
        logger.warning(f"Failed to load some protocols: {e}")
