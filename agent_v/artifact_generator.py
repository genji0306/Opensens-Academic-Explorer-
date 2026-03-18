"""
Animated Artifact Generator — Structured naming for Sonnet-generated animations.

Naming convention:
    {material_type}_{date}_{round}.{ext}

Examples:
    superconductor_20260318_001.mp4
    cuprate_20260318_002.gif
    magnetic_20260318_001.mp4

Usage:
    from agent_v.artifact_generator import ArtifactGenerator

    gen = ArtifactGenerator(material_type="superconductor")
    path = gen.next_path("architecture_flow")        # superconductor_20260318_001_architecture_flow.mp4
    path = gen.next_path("pipeline_pulse", fmt="gif") # superconductor_20260318_002_pipeline_pulse.gif

    # Full suite
    gen.generate_suite()
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_v.config import EXPORTS_DIR, DATA_DIR

logger = logging.getLogger("ArtifactGenerator")

# Supported material types for naming
MATERIAL_TYPES = {
    "superconductor", "cuprate", "iron_pnictide", "iron_chalcogenide",
    "heavy_fermion", "hydride", "nickelate", "a15", "chevrel", "kagome",
    "magnetic", "crystal", "ternary_hydride", "flat_band", "mof_sc",
    "carbon_based", "topological", "infinite_layer", "engineered_cuprate",
    "2d_heterostructure", "mgb2_type",
}

# Animation template registry — maps template names to guideline sections
ANIMATION_TEMPLATES = [
    {"name": "architecture_flow",    "section": "5.1", "description": "Agent architecture with data flow arrows"},
    {"name": "pipeline_pulse",       "section": "5.2", "description": "Data packets flowing through pipeline"},
    {"name": "mechanism_tree",       "section": "5.3", "description": "6 Tc mechanisms branching tree"},
    {"name": "discovery_emergence",  "section": "5.4", "description": "Tc vs lambda scatter, progressive"},
    {"name": "family_race",          "section": "5.5", "description": "Bar chart race of family mean Tc"},
    {"name": "convergence_pulse",    "section": "5.6", "description": "Convergence score with heartbeat glow"},
    {"name": "top_countdown",        "section": "5.7", "description": "Top 20 candidates revealed #20→#1"},
    {"name": "score_radar",          "section": "5.8", "description": "RTAP score components animated radar"},
]


class ArtifactGenerator:
    """Manages animated artifact generation with structured naming.

    Naming: {material_type}_{date}_{round}_{template}.{ext}

    Tracks round numbers per (material_type, date) pair via a manifest
    file at data/exports/artifact_manifest.json.
    """

    def __init__(self, material_type: str = "superconductor",
                 export_dir: Optional[Path] = None,
                 fmt: str = "mp4"):
        self.material_type = material_type.lower().replace("-", "_")
        self.export_dir = export_dir or EXPORTS_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.default_fmt = fmt
        self.date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        self._manifest_path = self.export_dir / "artifact_manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Load or create the artifact manifest."""
        if self._manifest_path.exists():
            with open(self._manifest_path) as f:
                return json.load(f)
        return {"artifacts": [], "counters": {}}

    def _save_manifest(self):
        """Persist the manifest to disk."""
        with open(self._manifest_path, "w") as f:
            json.dump(self._manifest, f, indent=2)

    def _next_round(self) -> int:
        """Get the next round number for this (material_type, date) pair."""
        key = f"{self.material_type}_{self.date_str}"
        counters = self._manifest.setdefault("counters", {})
        current = counters.get(key, 0)
        counters[key] = current + 1
        return current + 1

    def next_path(self, template_name: str = "", fmt: Optional[str] = None) -> Path:
        """Generate the next artifact path with structured naming.

        Args:
            template_name: Animation template name (e.g., "architecture_flow").
            fmt: File format ("mp4" or "gif"). Defaults to self.default_fmt.

        Returns:
            Path like: data/exports/superconductor_20260318_001_architecture_flow.mp4
        """
        ext = fmt or self.default_fmt
        round_num = self._next_round()
        suffix = f"_{template_name}" if template_name else ""
        filename = f"{self.material_type}_{self.date_str}_{round_num:03d}{suffix}.{ext}"
        path = self.export_dir / filename

        # Record in manifest
        self._manifest.setdefault("artifacts", []).append({
            "filename": filename,
            "material_type": self.material_type,
            "date": self.date_str,
            "round": round_num,
            "template": template_name,
            "format": ext,
            "created": datetime.now(timezone.utc).isoformat(),
        })
        self._save_manifest()

        logger.info(f"Artifact path: {path}")
        return path

    def list_artifacts(self, material_type: Optional[str] = None,
                       date: Optional[str] = None) -> list[dict]:
        """List generated artifacts, optionally filtered."""
        arts = self._manifest.get("artifacts", [])
        if material_type:
            arts = [a for a in arts if a["material_type"] == material_type]
        if date:
            arts = [a for a in arts if a["date"] == date]
        return arts

    def generate_suite(self, templates: Optional[list[str]] = None,
                       fmt: Optional[str] = None) -> list[Path]:
        """Generate paths for a full animation suite.

        Args:
            templates: List of template names. Defaults to all 8 templates.
            fmt: File format. Defaults to self.default_fmt.

        Returns:
            List of output paths (files not yet created — caller renders).
        """
        names = templates or [t["name"] for t in ANIMATION_TEMPLATES]
        paths = []
        for name in names:
            paths.append(self.next_path(name, fmt=fmt))
        return paths

    @staticmethod
    def list_templates() -> list[dict]:
        """Return the list of available animation templates."""
        return ANIMATION_TEMPLATES.copy()


def artifact_path(material_type: str, template_name: str = "",
                  fmt: str = "mp4") -> Path:
    """Convenience function: get a single artifact path.

    Usage:
        path = artifact_path("cuprate", "convergence_pulse")
        # -> data/exports/cuprate_20260318_001_convergence_pulse.mp4
    """
    gen = ArtifactGenerator(material_type=material_type, fmt=fmt)
    return gen.next_path(template_name)
