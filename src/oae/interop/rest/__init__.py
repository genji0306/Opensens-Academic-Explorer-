"""Phase I REST exposure manifest.

The existing FastAPI backend in ``backend/routers/`` serves the public
REST surface. Phase I only needs a machine-readable manifest of the
new endpoints (review / verification / dossier / sensing timeline /
benchmark) so the backend can import and mount them without cross-
importing the full ``src.oae`` tree.

The manifest is pure data: no FastAPI dependency, no Pydantic models.
"""
from __future__ import annotations

from .endpoints import (
    PhaseIEndpoint,
    PhaseIManifest,
    build_phase_i_manifest,
    default_manifest,
)

__all__ = [
    "PhaseIEndpoint",
    "PhaseIManifest",
    "build_phase_i_manifest",
    "default_manifest",
]
