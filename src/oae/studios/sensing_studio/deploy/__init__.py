"""Deployment Studio — export a converged sensing model."""
from __future__ import annotations

from src.oae.studios.sensing_studio.deploy.export import (
    DeploymentArtifact,
    export_model,
)

__all__ = ["DeploymentArtifact", "export_model"]
