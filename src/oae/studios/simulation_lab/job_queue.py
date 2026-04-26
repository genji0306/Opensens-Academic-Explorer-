"""Value-scoring-aware simulation job queue.

The queue reorders :class:`SimulationJob`s by the recommendation score
from ``src.core.value_scoring``. When that module is unavailable (for
example in isolated tests) it falls back to the raw job priority.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

from src.oae.simulation.base import (
    SimulationRequest,
    SimulationResult,
)
from src.oae.simulation.lab import SimulationLab


@dataclass(frozen=True)
class SimulationJob:
    """Single submission: one request plus its scheduling score."""

    request: SimulationRequest
    base_priority: float = 0.5
    rationale: str = ""


@dataclass(frozen=True)
class QueueStats:
    """Queue lifecycle counters for diagnostics."""

    submitted: int
    completed: int
    failed: int


def _default_value_scorer(job: SimulationJob) -> float:
    try:
        from src.core.value_scoring import recommend_action  # type: ignore

        suggestion = recommend_action(
            candidate_id=job.request.candidate_id,
            simulation_priority=job.base_priority,
        )
        if isinstance(suggestion, dict) and "score" in suggestion:
            return float(suggestion["score"])
    except Exception:
        pass
    return job.base_priority


@dataclass
class SimulationJobQueue:
    """Priority queue that hands jobs to a :class:`SimulationLab`."""

    lab: SimulationLab = field(default_factory=SimulationLab)
    scorer: Callable[[SimulationJob], float] = field(default=_default_value_scorer)
    _heap: list[tuple[float, int, SimulationJob]] = field(default_factory=list)
    _counter: "itertools.count[int]" = field(default_factory=itertools.count)
    _completed: int = 0
    _failed: int = 0

    def submit(self, job: SimulationJob) -> None:
        score = self.scorer(job)
        # max-heap behaviour via negation
        heapq.heappush(self._heap, (-score, next(self._counter), job))

    def submit_many(self, jobs: Iterable[SimulationJob]) -> None:
        for job in jobs:
            self.submit(job)

    def __len__(self) -> int:
        return len(self._heap)

    def drain(self) -> list[SimulationResult]:
        results: list[SimulationResult] = []
        for _, _, job in self._sorted():
            result = self.lab.submit(job.request)
            if result.ok:
                self._completed += 1
            else:
                self._failed += 1
            results.append(result)
        self._heap.clear()
        return results

    def peek(self) -> SimulationJob | None:
        if not self._heap:
            return None
        return self._heap[0][2]

    def stats(self) -> QueueStats:
        return QueueStats(
            submitted=self._completed + self._failed + len(self._heap),
            completed=self._completed,
            failed=self._failed,
        )

    def _sorted(self) -> Iterator[tuple[float, int, SimulationJob]]:
        """Iterate jobs in descending score order without mutating heap order."""
        snapshot = list(self._heap)
        heapq.heapify(snapshot)
        while snapshot:
            yield heapq.heappop(snapshot)
