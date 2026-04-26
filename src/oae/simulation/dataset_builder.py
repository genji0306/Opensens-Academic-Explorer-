"""Synthetic dataset builder — Phase H deliverable.

Builds reproducible datasets from any :class:`SimulationLab`. The
flagship artefact is ``MOF-1k-relaxed``: one thousand MOF candidates
seeded from the Phase D :class:`MOFPack`, each stamped with a
deterministic MACE-stub relaxation and an analytical electrochem CV
baseline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .base import SimulationKind, SimulationRequest, SimulationResult
from .lab import SimulationLab


@dataclass(frozen=True)
class SimulationDataset:
    """Immutable wrapper over a list of simulation results."""

    name: str
    results: tuple[SimulationResult, ...]
    metadata: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.results)

    def iter_by_kind(self, kind: SimulationKind) -> Iterator[SimulationResult]:
        return (r for r in self.results if r.request.kind == kind)

    def to_jsonl(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for result in self.results:
                fh.write(json.dumps(result.to_dict()) + "\n")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size": len(self.results),
            "metadata": dict(self.metadata),
            "backends": sorted({r.backend for r in self.results}),
        }


@dataclass
class DatasetBuilder:
    """Submit batches to the lab and collect them into datasets."""

    lab: SimulationLab = field(default_factory=SimulationLab)

    def build(
        self,
        name: str,
        requests: Iterable[SimulationRequest],
        metadata: dict | None = None,
    ) -> SimulationDataset:
        batch = self.lab.submit_batch(requests)
        return SimulationDataset(
            name=name,
            results=batch.results,
            metadata={
                "backend_counts": dict(batch.backend_counts),
                **(metadata or {}),
            },
        )


# ---------------------------------------------------------------------------
# MOF-1k seed
# ---------------------------------------------------------------------------


def _mof_compositions() -> list[tuple[str, str]]:
    """Return (composition, family) pairs for the MOF-1k seed.

    Uses Phase D's ``MOFPack`` families when the domain pack is
    available, otherwise falls back to a small built-in set so the
    dataset builder is exercisable even in minimal environments.
    """
    try:
        from src.oae.domains.mof import MOFPack

        pack = MOFPack()
        families = [getattr(f, "name", "") for f in getattr(pack, "families", ())]
        families = [f for f in families if f]
    except Exception:
        families = []

    if not families:
        families = [
            "ZIF", "UiO", "PCN", "MIL", "HKUST",
            "IRMOF", "MOF-74", "NU", "CAU", "porphyrin-MOF",
        ]

    compositions: list[tuple[str, str]] = []
    per_family = max(1, 1000 // len(families))
    for family in families:
        for i in range(per_family):
            compositions.append((f"{family}-{i:03d}", family))
        if len(compositions) >= 1000:
            break
    return compositions[:1000]


def build_mof_1k_seed(
    lab: SimulationLab | None = None,
    *,
    limit: int | None = None,
) -> SimulationDataset:
    """Build a deterministic MOF-1k-relaxed dataset.

    Parameters
    ----------
    lab:
        Optional simulation lab. Defaults to a fresh offline lab.
    limit:
        Truncate the output to the first N candidates. Useful for CI —
        the full 1k dataset builds in ~0.2 s on a laptop but tests can
        hit a smaller slice for speed.
    """
    lab = lab or SimulationLab()
    compositions = _mof_compositions()
    if limit is not None:
        compositions = compositions[: int(limit)]

    requests: list[SimulationRequest] = []
    for cid, family in compositions:
        requests.append(
            SimulationRequest(
                kind="relaxation",
                candidate_id=cid,
                composition=cid,
                family=family,
            )
        )
        requests.append(
            SimulationRequest(
                kind="cv_baseline",
                candidate_id=cid,
                composition=cid,
                family=family,
                parameters={
                    "concentration_M": 1e-3,
                    "scan_rate_V_s": 0.1,
                },
            )
        )

    builder = DatasetBuilder(lab=lab)
    return builder.build(
        name="MOF-1k-relaxed",
        requests=requests,
        metadata={
            "n_candidates": len(compositions),
            "per_candidate_kinds": ["relaxation", "cv_baseline"],
        },
    )
