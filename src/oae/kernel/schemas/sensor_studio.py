"""Sensor Studio schemas — Known-SPE calibration primitives (Phase B).

Sensor Studio differs from the existing sensor discovery loop: the
search space is *measurement conditions*, not materials. These schemas
describe the fixed inputs (SPE, analyte, potentiostat) and the swept
variables (measurement conditions), plus the stability report that
drives convergence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Technique = Literal["CV", "DPV", "SWV", "EIS", "CA", "LSV", "OCP"]


@dataclass(frozen=True)
class SPECharacteristics:
    """Fixed characterization of a known screen-printed electrode."""

    spe_id: str
    working_material: str              # e.g. "nano_Au", "carbon", "Pt"
    working_area_mm2: float = 0.0
    reference: str = "Ag/AgCl"
    counter: str = "carbon"
    surface_modification: str = ""
    batch_id: str = ""
    known_cv_footprint: str = ""       # reference CV trace path
    notes: str = ""


@dataclass(frozen=True)
class TargetAnalyte:
    """Known analyte the user is trying to detect stably."""

    name: str
    formula: str = ""
    expected_concentration_range_uM: tuple[float, float] = (0.0, 0.0)
    matrix: str = "PBS"
    expected_redox_potential_v: float = 0.0
    expected_lod_uM: float = 0.0
    known_interferents: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PotentiostatSpec:
    """Capabilities and safe operating ranges for the Opensens device."""

    device_id: str = "opensens_ps1"
    firmware: str = ""
    potential_range_v: tuple[float, float] = (-2.0, 2.0)
    current_range_a: tuple[float, float] = (-1e-3, 1e-3)
    min_step_mv: float = 1.0
    max_scan_rate_mv_s: float = 1000.0
    supported_techniques: tuple[Technique, ...] = (
        "CV", "DPV", "SWV", "EIS", "CA",
    )


@dataclass(frozen=True)
class MeasurementCondition:
    """One trial condition in the condition sweep.

    A ``MeasurementCondition`` is what Sensor Studio treats as a
    "candidate" when running through ``MaterialDiscoveryLoop`` — the
    condition pack replaces the material family as the search space.
    """

    condition_id: str
    technique: Technique
    ph: float = 7.4
    ionic_strength_mM: float = 100.0
    temperature_c: float = 25.0
    buffer: str = "PBS"
    scan_rate_mv_s: float = 100.0
    potential_window_v: tuple[float, float] = (-0.5, 0.5)
    pulse_amplitude_mv: float = 50.0
    step_potential_mv: float = 5.0
    frequency_hz: float = 10.0
    equilibration_time_s: float = 2.0
    preconditioning_v: float = 0.0
    preconditioning_time_s: float = 0.0
    stirring_rpm: float = 0.0
    purge_gas: str = ""

    def key(self) -> tuple:
        """Return a hashable key for caching expected vs observed traces."""
        return (
            self.technique, self.ph, self.ionic_strength_mM,
            self.temperature_c, self.scan_rate_mv_s,
            self.potential_window_v, self.pulse_amplitude_mv,
            self.step_potential_mv, self.frequency_hz,
            self.equilibration_time_s, self.preconditioning_v,
            self.preconditioning_time_s,
        )


@dataclass(frozen=True)
class StabilityReport:
    """Stability objective values for a single condition.

    The StabilityObjective in Sensor Studio minimizes ``signal_cv`` and
    ``drift_per_repeat``, maximizes ``snr`` and ``linearity_r2``, and
    penalizes ``reference_delta`` (absolute gap from the known result).
    """

    condition_id: str
    signal_cv: float = 1.0             # coefficient of variation, lower better
    snr: float = 0.0                   # dB, higher better
    drift_per_repeat: float = 0.0      # relative, lower better
    reference_delta: float = 1.0       # 0.0 = perfect agreement
    lod_uM: float = 0.0
    linearity_r2: float = 0.0
    n_replicates: int = 0
    passed: bool = False

    def stability_score(self) -> float:
        """Combined stability score in [0.0, 1.0]."""
        cv_term = max(0.0, 1.0 - min(1.0, self.signal_cv))
        snr_term = max(0.0, min(1.0, self.snr / 40.0))
        drift_term = max(0.0, 1.0 - min(1.0, abs(self.drift_per_repeat)))
        agree_term = max(0.0, 1.0 - min(1.0, self.reference_delta))
        linearity_term = max(0.0, min(1.0, self.linearity_r2))
        weights = (0.30, 0.20, 0.15, 0.25, 0.10)
        values = (cv_term, snr_term, drift_term, agree_term, linearity_term)
        return sum(w * v for w, v in zip(weights, values))


@dataclass(frozen=True)
class CalibrationSession:
    """Immutable session binding fixed inputs to a condition search space."""

    session_id: str
    spe: SPECharacteristics
    analyte: TargetAnalyte
    device: PotentiostatSpec
    reference_result_path: str = ""
    max_runs: int = 30
    target_signal_cv: float = 0.05


@runtime_checkable
class ConditionPack(Protocol):
    """Protocol sibling of ``DomainPack`` for condition-space searches.

    Implementations live in ``oae.domains.electrochemistry`` (or future
    equivalents). They enumerate measurement conditions and score
    stability reports, reusing the existing ``MaterialDiscoveryLoop``
    without any loop-level changes.
    """

    name: str

    def seed_conditions(
        self,
        session: CalibrationSession,
        iteration: int,
    ) -> list[MeasurementCondition]:
        ...

    def score_stability(
        self,
        session: CalibrationSession,
        report: StabilityReport,
    ) -> float:
        ...
