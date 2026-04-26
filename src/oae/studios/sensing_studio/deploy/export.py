"""Deployment export for converged sensing models.

Phase F ships a minimal JSON export. Later phases can layer an
inference API, an ONNX bundle, or a REST surface on top without
changing the underlying deployment artifact.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.oae.studios.sensing_studio.model.predictive import PredictiveModel
from src.oae.studios.sensing_studio.session import RecursiveSensingSession


@dataclass(frozen=True)
class DeploymentArtifact:
    """Summary of an exported model + session provenance."""

    path: Path
    session_uuid: str
    observer_score: float
    feature_strategy: str


def export_model(
    session: RecursiveSensingSession,
    model: PredictiveModel,
    root: str | Path,
) -> DeploymentArtifact:
    """Serialize ``model`` + session headline metrics to JSON."""
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    out = root_path / f"{session.session_uuid}.json"

    latest = session.latest()
    observer_score = latest.observer_score if latest else 0.0

    payload = {
        "session_uuid": session.session_uuid,
        "spe_id": session.calibration.spe.spe_id,
        "analyte": session.calibration.analyte.name,
        "observer_score": observer_score,
        "n_rounds": len(session.rounds),
        "model": {
            "feature_strategy": model.feature_strategy,
            "slope": model.slope,
            "intercept": model.intercept,
            "rmse_log": model.rmse_log,
            "theory_offset": model.theory_offset,
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    return DeploymentArtifact(
        path=out,
        session_uuid=session.session_uuid,
        observer_score=observer_score,
        feature_strategy=model.feature_strategy,
    )


__all__ = ["DeploymentArtifact", "export_model"]
