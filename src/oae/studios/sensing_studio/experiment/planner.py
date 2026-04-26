"""Agent LS — experiment design and condition planner.

The planner enumerates :class:`MeasurementCondition` sweeps over the
canonical matrix dimensions (pH, ionic strength, temperature,
interferent profile, scan rate) and binds them to sample ids that the
Observer can validate against its hidden-label vault.

The planner is deterministic so tests, CI, and replay scenarios all
produce identical plans from the same :class:`CalibrationSession`. It
also exposes :meth:`expand_coverage` for the recursive feedback loop:
when the Observer routes a failure to "insufficient coverage", the
planner injects new conditions orthogonal to the failing ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from src.oae.kernel.schemas import (
    CalibrationSession,
    MeasurementCondition,
    TargetAnalyte,
)

# ---------------------------------------------------------------------------
# Plan types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanSample:
    """A single experimental sample — condition × target concentration.

    The Observer holds the mapping from ``sample_id`` to true
    concentration in its :class:`HiddenLabelVault`; the planner only
    knows that there exists a sample with this id and this condition.
    """

    sample_id: str
    condition: MeasurementCondition


@dataclass(frozen=True)
class ExperimentPlan:
    """Ordered batch of samples for one recursive round."""

    round_index: int
    samples: tuple[PlanSample, ...]
    rationale: str = ""

    @property
    def conditions(self) -> tuple[MeasurementCondition, ...]:
        """Return the unique conditions in this plan (dedup by condition_id)."""
        seen: dict[str, MeasurementCondition] = {}
        for s in self.samples:
            seen.setdefault(s.condition.condition_id, s.condition)
        return tuple(seen.values())


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


@dataclass
class ExperimentPlanner:
    """Deterministic condition-space planner for the Sensing Studio loop.

    Parameters
    ----------
    ph_grid:
        pH values to sweep in the default plan.
    ionic_strength_grid_mM:
        Ionic strength values (mM) to sweep.
    temperature_grid_c:
        Temperatures (°C) to sweep.
    technique:
        Default electrochemical technique. Overrides may be provided
        per-round by the orchestrator.
    max_samples_per_round:
        Hard cap on samples per recursive round to keep CI fast.
    """

    ph_grid: tuple[float, ...] = (6.0, 7.4, 8.0)
    ionic_strength_grid_mM: tuple[float, ...] = (50.0, 150.0)
    temperature_grid_c: tuple[float, ...] = (25.0,)
    technique: str = "DPV"
    max_samples_per_round: int = 12

    # --- public API ---------------------------------------------------

    def initial_plan(
        self,
        session: CalibrationSession,
        concentrations_uM: Sequence[float],
    ) -> ExperimentPlan:
        """Build the first-round plan from a calibration session.

        ``concentrations_uM`` is the ordered list of true concentrations
        the Observer will bind to the returned samples. The planner
        itself never sees the mapping; it only generates sample ids.
        """
        conditions = self._default_conditions(session.analyte)
        samples = self._bind_samples(
            conditions,
            concentrations_uM,
            round_index=0,
        )
        return ExperimentPlan(
            round_index=0,
            samples=samples,
            rationale=(
                f"initial sweep: {len(conditions)} conditions × "
                f"{len(concentrations_uM)} samples"
            ),
        )

    def expand_coverage(
        self,
        session: CalibrationSession,
        previous_plan: ExperimentPlan,
        concentrations_uM: Sequence[float],
        extra_ph: Iterable[float] = (),
        extra_ionic_mM: Iterable[float] = (),
    ) -> ExperimentPlan:
        """Return a new plan that extends coverage orthogonally.

        Used when the Observer routes a failure to "inadequate
        experiment coverage". The planner injects conditions at pH /
        ionic-strength values not previously visited and rebinds a
        fresh set of samples for the next round.
        """
        used_ph = {round(c.ph, 3) for c in previous_plan.conditions}
        used_is = {
            round(c.ionic_strength_mM, 3)
            for c in previous_plan.conditions
        }
        new_ph = [p for p in extra_ph if round(p, 3) not in used_ph]
        new_is = [i for i in extra_ionic_mM if round(i, 3) not in used_is]

        extra_conditions: list[MeasurementCondition] = []
        idx = 0
        for p in new_ph or [self.ph_grid[0]]:
            for i in new_is or [self.ionic_strength_grid_mM[0]]:
                extra_conditions.append(
                    MeasurementCondition(
                        condition_id=(
                            f"expand_r{previous_plan.round_index + 1}_c{idx}"
                        ),
                        technique=self.technique,  # type: ignore[arg-type]
                        ph=p,
                        ionic_strength_mM=i,
                        temperature_c=self.temperature_grid_c[0],
                    )
                )
                idx += 1

        samples = self._bind_samples(
            tuple(extra_conditions),
            concentrations_uM,
            round_index=previous_plan.round_index + 1,
        )
        return ExperimentPlan(
            round_index=previous_plan.round_index + 1,
            samples=samples,
            rationale=(
                f"expanded coverage with {len(extra_conditions)} "
                f"new conditions"
            ),
        )

    # --- internals ----------------------------------------------------

    def _default_conditions(
        self,
        analyte: TargetAnalyte,
    ) -> tuple[MeasurementCondition, ...]:
        conditions: list[MeasurementCondition] = []
        idx = 0
        for ph in self.ph_grid:
            for ionic in self.ionic_strength_grid_mM:
                for temp in self.temperature_grid_c:
                    conditions.append(
                        MeasurementCondition(
                            condition_id=f"init_c{idx}",
                            technique=self.technique,  # type: ignore[arg-type]
                            ph=ph,
                            ionic_strength_mM=ionic,
                            temperature_c=temp,
                            buffer=analyte.matrix or "PBS",
                            potential_window_v=(
                                analyte.expected_redox_potential_v - 0.3,
                                analyte.expected_redox_potential_v + 0.3,
                            ),
                        )
                    )
                    idx += 1
        return tuple(conditions)

    def _bind_samples(
        self,
        conditions: Sequence[MeasurementCondition],
        concentrations_uM: Sequence[float],
        *,
        round_index: int,
    ) -> tuple[PlanSample, ...]:
        samples: list[PlanSample] = []
        for ci, cond in enumerate(conditions):
            for si in range(len(concentrations_uM)):
                sample_id = f"r{round_index}_c{ci}_s{si}"
                samples.append(PlanSample(sample_id=sample_id, condition=cond))
                if len(samples) >= self.max_samples_per_round:
                    return tuple(samples)
        return tuple(samples)


__all__ = ["ExperimentPlan", "ExperimentPlanner", "PlanSample"]
