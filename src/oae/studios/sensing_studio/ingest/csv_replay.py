"""CSV replay driver for Sensing Studio.

The replay driver reads a manifest JSON file that maps ``sample_id``
to a CSV trace on disk. Each CSV has two columns: ``voltage_v`` and
``current_a``. The manifest also carries the full
:class:`MeasurementCondition` payload per sample so the orchestrator
can round-trip without side information.

CSV replay is the only ingest path the CI runs against. Real hardware
is wired behind the same :class:`PotentiostatBridge` protocol so
replacing the driver never requires changes outside
``ingest/``.

Manifest format (JSON)::

    {
        "samples": [
            {
                "sample_id": "r0_c0_s0",
                "trace_path": "traces/r0_c0_s0.csv",
                "condition": {
                    "condition_id": "init_c0",
                    "technique": "DPV",
                    "ph": 7.4,
                    "ionic_strength_mM": 100.0,
                    ...
                },
                "metadata": {"operator": "lab_bot_1"}
            },
            ...
        ]
    }
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from src.oae.kernel.schemas import MeasurementCondition
from src.oae.studios.sensing_studio.ingest.bridge import MeasurementRecord

logger = logging.getLogger("CSVReplayDriver")


@dataclass
class CSVReplayDriver:
    """File-backed :class:`PotentiostatBridge` used for offline runs.

    Instances load a manifest from disk eagerly so that ``fetch`` is
    a pure dict lookup. Missing sample ids are silently dropped — the
    orchestrator treats a missing record as a failed trial.
    """

    manifest_path: Path
    name: str = "csv_replay"
    _records: dict[str, MeasurementRecord] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.manifest_path = Path(self.manifest_path)
        if not self.manifest_path.exists():
            raise FileNotFoundError(self.manifest_path)
        self._records = self._load_manifest()
        logger.info(
            "loaded %d CSV replay records from %s",
            len(self._records),
            self.manifest_path,
        )

    # --- public API ---------------------------------------------------

    def fetch(
        self,
        sample_ids: Iterable[str],
    ) -> tuple[MeasurementRecord, ...]:
        return tuple(
            self._records[sid] for sid in sample_ids if sid in self._records
        )

    @property
    def sample_ids(self) -> tuple[str, ...]:
        return tuple(self._records.keys())

    # --- loaders ------------------------------------------------------

    def _load_manifest(self) -> dict[str, MeasurementRecord]:
        with self.manifest_path.open() as handle:
            payload = json.load(handle)
        records: dict[str, MeasurementRecord] = {}
        base_dir = self.manifest_path.parent
        for entry in payload.get("samples", []):
            sample_id = str(entry["sample_id"])
            trace_path = base_dir / entry["trace_path"]
            voltage, current = _read_trace_csv(trace_path)
            condition = _build_condition(entry["condition"])
            records[sample_id] = MeasurementRecord(
                sample_id=sample_id,
                condition=condition,
                voltage_v=voltage,
                current_a=current,
                metadata=dict(entry.get("metadata") or {}),
            )
        return records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_trace_csv(path: Path) -> tuple[tuple[float, ...], tuple[float, ...]]:
    voltage: list[float] = []
    current: list[float] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            voltage.append(float(row["voltage_v"]))
            current.append(float(row["current_a"]))
    return tuple(voltage), tuple(current)


def _build_condition(payload: dict) -> MeasurementCondition:
    allowed = {
        "condition_id",
        "technique",
        "ph",
        "ionic_strength_mM",
        "temperature_c",
        "buffer",
        "scan_rate_mv_s",
        "potential_window_v",
        "pulse_amplitude_mv",
        "step_potential_mv",
        "frequency_hz",
        "equilibration_time_s",
        "preconditioning_v",
        "preconditioning_time_s",
        "stirring_rpm",
        "purge_gas",
    }
    kwargs: dict[str, object] = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "potential_window_v" and isinstance(value, list):
            kwargs[key] = (float(value[0]), float(value[1]))
        else:
            kwargs[key] = value
    return MeasurementCondition(**kwargs)  # type: ignore[arg-type]


__all__ = ["CSVReplayDriver"]
