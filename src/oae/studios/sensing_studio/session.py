"""Recursive sensing session state + hidden-label vault.

The session is the canonical carrier of recursive state: every round
produces a :class:`RoundState` that records its experiment plan,
observed signal features, priors, predictions, Observer score, and
routing decision. Rounds are append-only so the full history is
reconstructible from any serialized session.

Hidden labels live in :class:`HiddenLabelVault`, a strict read-gate
that refuses to disclose true values to any actor that is not
``"observer"``. Leakage of hidden labels corrupts the entire
experiment, so the vault is the only module allowed to return them and
every read is logged.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from src.oae.kernel.schemas import (
    CalibrationSession,
    MeasurementCondition,
    VerificationBundle,
)

logger = logging.getLogger("RecursiveSensingSession")


# ---------------------------------------------------------------------------
# Hidden-label vault
# ---------------------------------------------------------------------------


class HiddenLabelLeakError(RuntimeError):
    """Raised when a non-observer actor tries to read hidden labels."""


@dataclass
class HiddenLabelVault:
    """Strict read-gate for hidden ground truth.

    The vault stores sample-level true concentrations keyed by
    ``sample_id``. Only the literal actor string ``"observer"`` can
    read them, enforced at call time. Every read is appended to the
    access log so leakage can be audited post-hoc.
    """

    _labels: dict[str, float] = field(default_factory=dict)
    _access_log: list[dict[str, str]] = field(default_factory=list)
    _frozen: bool = False

    def deposit(self, sample_id: str, true_concentration: float) -> None:
        """Deposit a hidden label. Rejects writes after the vault is frozen."""
        if self._frozen:
            raise HiddenLabelLeakError(
                "cannot deposit into a frozen HiddenLabelVault"
            )
        self._labels[sample_id] = float(true_concentration)

    def deposit_batch(self, labels: Mapping[str, float]) -> None:
        for sample_id, value in labels.items():
            self.deposit(sample_id, value)

    def freeze(self) -> None:
        """Seal the vault. After freezing, no further deposits are allowed."""
        self._frozen = True

    def sample_ids(self) -> tuple[str, ...]:
        """Return the list of sealed sample ids (safe for any actor)."""
        return tuple(self._labels.keys())

    def reveal(self, sample_id: str, *, actor: str) -> float:
        """Return the hidden label for ``sample_id``.

        Only ``actor == "observer"`` is allowed. Any other actor raises
        :class:`HiddenLabelLeakError` and the attempt is logged.
        """
        if actor != "observer":
            self._access_log.append(
                {"sample_id": sample_id, "actor": actor, "status": "denied"}
            )
            raise HiddenLabelLeakError(
                f"actor {actor!r} is not allowed to read hidden labels"
            )
        if sample_id not in self._labels:
            self._access_log.append(
                {"sample_id": sample_id, "actor": actor, "status": "missing"}
            )
            raise KeyError(sample_id)
        self._access_log.append(
            {"sample_id": sample_id, "actor": actor, "status": "ok"}
        )
        return self._labels[sample_id]

    def reveal_all(self, *, actor: str) -> dict[str, float]:
        """Return the full label map to the Observer."""
        if actor != "observer":
            self._access_log.append(
                {"sample_id": "*", "actor": actor, "status": "denied"}
            )
            raise HiddenLabelLeakError(
                f"actor {actor!r} is not allowed to read hidden labels"
            )
        self._access_log.append(
            {"sample_id": "*", "actor": actor, "status": "ok"}
        )
        return dict(self._labels)

    @property
    def access_log(self) -> tuple[dict[str, str], ...]:
        return tuple(self._access_log)

    @property
    def is_frozen(self) -> bool:
        return self._frozen


# ---------------------------------------------------------------------------
# Round state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingRecord:
    """Immutable record of one routing decision made by the Observer."""

    round_index: int
    target: str                       # "model" | "signal" | "priors" | "experiment" | "stop"
    reason: str
    observer_score: float             # 0.0–1.0, higher is better


@dataclass
class RoundState:
    """State captured during one recursive round.

    A round is append-only from the orchestrator's perspective: once
    written, fields should not be mutated. The Observer's routing
    decision is added at the very end of the round by
    :meth:`record_routing`.
    """

    round_index: int
    conditions: tuple[MeasurementCondition, ...] = ()
    signal_feature_summary: dict[str, float] = field(default_factory=dict)
    prior_summary: dict[str, float] = field(default_factory=dict)
    predictions: dict[str, float] = field(default_factory=dict)
    prediction_uncertainty: dict[str, float] = field(default_factory=dict)
    observer_score: float = 0.0
    verification: Optional[VerificationBundle] = None
    routing: Optional[RoutingRecord] = None

    def record_routing(self, record: RoutingRecord) -> None:
        if self.routing is not None:
            raise RuntimeError(
                f"routing already recorded for round {self.round_index}"
            )
        self.routing = record

    def to_dict(self) -> dict:
        return {
            "round_index": self.round_index,
            "n_conditions": len(self.conditions),
            "condition_ids": [c.condition_id for c in self.conditions],
            "signal_feature_summary": dict(self.signal_feature_summary),
            "prior_summary": dict(self.prior_summary),
            "predictions": dict(self.predictions),
            "prediction_uncertainty": dict(self.prediction_uncertainty),
            "observer_score": self.observer_score,
            "verification": (
                {
                    "candidate_id": self.verification.candidate_id,
                    "credibility": (
                        self.verification.posterior.credibility_prob
                    ),
                    "conflict": self.verification.conflict(),
                    "coverage": self.verification.coverage(),
                }
                if self.verification is not None
                else None
            ),
            "routing": (
                {
                    "target": self.routing.target,
                    "reason": self.routing.reason,
                    "observer_score": self.routing.observer_score,
                }
                if self.routing is not None
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class RecursiveSensingSession:
    """Container for one end-to-end recursive sensing run.

    Wraps a :class:`CalibrationSession` (the immutable inputs) with
    mutable recursive state: rounds, hidden-label vault, convergence
    history, and the target acceptance criteria.
    """

    calibration: CalibrationSession
    target_observer_score: float = 0.95
    max_rounds: int = 8
    rounds: list[RoundState] = field(default_factory=list)
    vault: HiddenLabelVault = field(default_factory=HiddenLabelVault)
    session_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    # --- lifecycle -----------------------------------------------------

    def begin_round(self) -> RoundState:
        """Create a new round, append it, and return it for mutation."""
        state = RoundState(round_index=len(self.rounds))
        self.rounds.append(state)
        return state

    def latest(self) -> Optional[RoundState]:
        return self.rounds[-1] if self.rounds else None

    # --- queries -------------------------------------------------------

    def score_history(self) -> list[float]:
        return [r.observer_score for r in self.rounds]

    def routing_history(self) -> list[RoutingRecord]:
        return [r.routing for r in self.rounds if r.routing is not None]

    def has_converged(self) -> bool:
        latest = self.latest()
        if latest is None:
            return False
        return latest.observer_score >= self.target_observer_score

    # --- persistence ---------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "session_uuid": self.session_uuid,
            "calibration_session_id": self.calibration.session_id,
            "spe_id": self.calibration.spe.spe_id,
            "analyte": self.calibration.analyte.name,
            "target_observer_score": self.target_observer_score,
            "max_rounds": self.max_rounds,
            "rounds": [r.to_dict() for r in self.rounds],
            "n_vault_samples": len(self.vault.sample_ids()),
            "vault_frozen": self.vault.is_frozen,
        }

    def write_timeline(self, path: str | Path) -> Path:
        """Persist the recursive timeline (without hidden labels) to JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2))
        logger.info("wrote sensing studio timeline to %s", p)
        return p


__all__ = [
    "HiddenLabelLeakError",
    "HiddenLabelVault",
    "RecursiveSensingSession",
    "RoundState",
    "RoutingRecord",
]
