"""Potentiostat bridge protocol — abstraction over real / replay sources.

Every Sensing Studio measurement flows through a
:class:`PotentiostatBridge`. The bridge normalises each physical
measurement into a :class:`MeasurementRecord` that carries the voltage
and current traces plus the condition key. Two implementations ship
in Phase F:

* :class:`CSVReplayDriver` (in :mod:`csv_replay`): mandatory for CI,
  loads voltage/current traces from on-disk CSV files.
* :class:`OEPSPotentiostatAdapter`: optional stub for real Opensens
  OEPS hardware. Phase F ships a safe stub that raises
  :class:`NotImplementedError` unless a concrete driver is injected.

The protocol keeps the orchestrator hardware-agnostic: the predictive
model, observer, and signal analyzer only ever see
``MeasurementRecord`` instances.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol, runtime_checkable

from src.oae.kernel.schemas import MeasurementCondition


# ---------------------------------------------------------------------------
# Normalised record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeasurementRecord:
    """One normalised measurement trace for one sample.

    ``voltage_v`` and ``current_a`` are parallel sequences; metadata
    carries free-form instrument notes that the signal analyzer may
    use but is not required to understand.
    """

    sample_id: str
    condition: MeasurementCondition
    voltage_v: tuple[float, ...]
    current_a: tuple[float, ...]
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.voltage_v) != len(self.current_a):
            raise ValueError(
                f"voltage/current length mismatch for sample {self.sample_id}: "
                f"{len(self.voltage_v)} vs {len(self.current_a)}"
            )

    @property
    def n_points(self) -> int:
        return len(self.voltage_v)


# ---------------------------------------------------------------------------
# Bridge protocol + adapters
# ---------------------------------------------------------------------------


@runtime_checkable
class PotentiostatBridge(Protocol):
    """Shared protocol every ingest source implements.

    The orchestrator asks ``fetch`` for a batch of sample ids; the
    bridge returns one :class:`MeasurementRecord` per id. Missing ids
    are simply omitted from the result — the orchestrator treats a
    missing measurement as a failed trial and routes accordingly.
    """

    name: str

    def fetch(
        self,
        sample_ids: Iterable[str],
    ) -> tuple[MeasurementRecord, ...]:
        ...


@dataclass
class OEPSPotentiostatAdapter:
    """Stub adapter for the Opensens OEPS potentiostat.

    Real OEPS integration requires the hardware-side Python client,
    which is out of scope for offline CI. This stub exists so the
    orchestrator can type-check against the protocol. Injecting a
    real driver is as simple as passing a callable ``real_fetch``
    that returns ``tuple[MeasurementRecord, ...]``.
    """

    name: str = "oeps_ps1"
    real_fetch: object | None = None  # Optional[Callable[[Iterable[str]], ...]]

    def fetch(
        self,
        sample_ids: Iterable[str],
    ) -> tuple[MeasurementRecord, ...]:
        if self.real_fetch is None:
            raise NotImplementedError(
                "OEPSPotentiostatAdapter is a stub. Inject a real driver "
                "via real_fetch= or use CSVReplayDriver for offline runs."
            )
        # Duck-typed callable injected by an integrator.
        return tuple(self.real_fetch(sample_ids))  # type: ignore[misc]


__all__ = [
    "MeasurementRecord",
    "OEPSPotentiostatAdapter",
    "PotentiostatBridge",
]
