"""Dossier writer — emit a human-readable markdown file per candidate.

The dossier is Tier-A research memory: a self-contained document that
captures the review outcome for a single candidate. It is produced by
:class:`DossierWriter`, which takes a :class:`ReviewBundle` and an
optional :class:`ResearchTrace`, and writes a markdown file under
``data/research_memory/dossiers/<campaign>/<candidate>.md``.

Design rules:
  * Markdown only — no HTML, no escaping dances.
  * Deterministic output so tests can diff exact strings.
  * All paths returned as :class:`pathlib.Path` so callers can persist
    the pointer in :class:`ResearchMemory`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.oae.kernel.schemas import ReviewBundle
from src.oae.research.memory import (
    DEFAULT_ROOT,
    DossierPointer,
    ResearchMemory,
)
from src.oae.research.trace import ResearchTrace

logger = logging.getLogger("DossierWriter")

DEFAULT_DOSSIER_ROOT = DEFAULT_ROOT / "dossiers"


@dataclass
class DossierWriter:
    """Render review bundles as markdown dossiers on disk."""

    root: Path = field(default_factory=lambda: DEFAULT_DOSSIER_ROOT)

    # --- public API ---------------------------------------------------

    def write(
        self,
        bundle: ReviewBundle,
        *,
        campaign_id: str = "default",
        family: str = "",
        trace: ResearchTrace | None = None,
        memory: ResearchMemory | None = None,
    ) -> DossierPointer:
        """Write a dossier for ``bundle`` and return a pointer to it."""
        target_dir = self.root / _safe(campaign_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{_safe(bundle.candidate_id)}.md"

        content = self.render(
            bundle,
            campaign_id=campaign_id,
            family=family,
            trace=trace,
        )
        path.write_text(content, encoding="utf-8")

        pointer = DossierPointer(
            candidate_id=bundle.candidate_id,
            path=str(path),
            campaign_id=campaign_id,
            family=family,
        )
        if memory is not None:
            memory.register_dossier(pointer)
        return pointer

    # --- rendering ----------------------------------------------------

    def render(
        self,
        bundle: ReviewBundle,
        *,
        campaign_id: str = "default",
        family: str = "",
        trace: ResearchTrace | None = None,
    ) -> str:
        """Render a :class:`ReviewBundle` as a deterministic markdown string."""
        lines: list[str] = []
        lines.append(f"# Candidate Dossier — {bundle.candidate_id}")
        lines.append("")
        lines.append(f"- **Campaign:** {campaign_id}")
        if family:
            lines.append(f"- **Family:** {family}")
        lines.append(
            f"- **Theory alignment:** {bundle.theory_alignment_score():.3f}"
        )
        lines.append(
            f"- **Contradiction penalty:** {bundle.contradiction_penalty():.3f}"
        )
        lines.append(
            f"- **Experiment readiness:** "
            f"{bundle.experiment_readiness_score():.3f}"
        )
        lines.append(f"- **Review confidence:** {bundle.review_confidence:.3f}")
        lines.append("")

        lines.append("## Ranked Mechanisms")
        lines.append("")
        if not bundle.ranked_mechanisms:
            lines.append("_No mechanisms matched this candidate._")
            lines.append("")
        else:
            for mech in bundle.ranked_mechanisms:
                lines.append(
                    f"{mech.rank}. **{mech.mechanism}** "
                    f"(p={mech.probability:.3f})"
                )
                if mech.discriminating_experiment:
                    lines.append(
                        f"   - Discriminating experiment: "
                        f"{mech.discriminating_experiment}"
                    )
            lines.append("")

        lines.append("## Theory Cards")
        lines.append("")
        if not bundle.theory_cards:
            lines.append("_No theory cards produced._")
            lines.append("")
        else:
            for idx, card in enumerate(bundle.theory_cards, start=1):
                lines.append(f"### {idx}. {card.claim}")
                lines.append("")
                lines.append(f"- Mechanism: `{card.mechanism}`")
                if card.conditions:
                    lines.append(f"- Conditions: {card.conditions}")
                lines.append(
                    f"- Support: {card.support_level} "
                    f"({card.support_score:.2f})"
                )
                lines.append(
                    f"- Contradiction: {card.contradiction_level} "
                    f"({card.contradiction_score:.2f})"
                )
                if card.citations:
                    lines.append("- Citations:")
                    for cite in card.citations:
                        title = cite.title or cite.source
                        lines.append(f"    - {cite.source} — {title}")
                lines.append("")

        lines.append("## Recommended Checks")
        lines.append("")
        if bundle.recommended_checks:
            for check in bundle.recommended_checks:
                lines.append(f"- [ ] {check}")
        else:
            lines.append("_None._")
        lines.append("")

        if trace is not None:
            entries = trace.entries_for(bundle.candidate_id)
            lines.append("## Research Trace")
            lines.append("")
            if not entries:
                lines.append("_No trace entries recorded for this candidate._")
            else:
                for entry in entries:
                    lines.append(
                        f"- `{entry.timestamp}` **{entry.kind}** — "
                        f"{entry.payload}"
                    )
            lines.append("")

        if bundle.provenance:
            lines.append("## Provenance")
            lines.append("")
            for key, value in sorted(bundle.provenance.items()):
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        return "\n".join(lines)


def _safe(value: str) -> str:
    """Return a filesystem-safe slug for ``value``."""
    if not value:
        return "unknown"
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)
