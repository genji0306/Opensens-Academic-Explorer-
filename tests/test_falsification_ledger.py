"""Tests for the Phase 4 falsification ledger."""
from __future__ import annotations

import pytest

from riemann.research.falsification_ledger import (
    FalsificationLedger,
    _FALSIFICATION_PENALTY_CAP,
    _FALSIFICATION_PENALTY_PER_HIT,
)


def test_empty_ledger_returns_zero_penalty() -> None:
    ledger = FalsificationLedger()
    assert ledger.penalty_for(("explicit_formula",), (29.5, 30.5)) == 0.0


def test_record_then_penalty_for_same_family_and_band() -> None:
    ledger = FalsificationLedger()
    ledger.record(
        round_index=1, candidate_id="c1",
        ingredient_families=("explicit_formula",),
        contradicted_window=(29.5, 30.5),
    )
    p = ledger.penalty_for(("explicit_formula",), (29.0, 30.0))
    assert p == pytest.approx(_FALSIFICATION_PENALTY_PER_HIT, abs=1e-9)


def test_penalty_does_not_apply_to_different_family() -> None:
    ledger = FalsificationLedger()
    ledger.record(
        round_index=1, candidate_id="c1",
        ingredient_families=("explicit_formula",),
        contradicted_window=(29.5, 30.5),
    )
    assert ledger.penalty_for(("hardy_z",), (29.5, 30.5)) == 0.0


def test_penalty_does_not_apply_to_different_band() -> None:
    ledger = FalsificationLedger()
    ledger.record(
        round_index=1, candidate_id="c1",
        ingredient_families=("explicit_formula",),
        contradicted_window=(29.5, 30.5),
    )
    assert ledger.penalty_for(("explicit_formula",), (75.0, 76.0)) == 0.0


def test_penalty_is_capped() -> None:
    ledger = FalsificationLedger()
    for i in range(20):
        ledger.record(
            round_index=i, candidate_id=f"c{i}",
            ingredient_families=("explicit_formula",),
            contradicted_window=(30.0, 30.5),
        )
    p = ledger.penalty_for(("explicit_formula",), (30.0, 30.5))
    assert p == pytest.approx(_FALSIFICATION_PENALTY_CAP, abs=1e-9)


def test_family_signature_is_canonical() -> None:
    ledger = FalsificationLedger()
    sig_a = ledger.family_signature(("hardy_z", "explicit_formula"))
    sig_b = ledger.family_signature(("explicit_formula", "hardy_z"))
    assert sig_a == sig_b == "explicit_formula+hardy_z"


def test_family_falsification_count_splits_multi_family_signature() -> None:
    ledger = FalsificationLedger()
    ledger.record(
        round_index=1, candidate_id="c1",
        ingredient_families=("hardy_z", "explicit_formula"),
        contradicted_window=(50.0, 50.5),
    )
    counts = ledger.family_falsification_count()
    assert counts["hardy_z"] == 1
    assert counts["explicit_formula"] == 1


def test_summary_aggregates_correctly() -> None:
    ledger = FalsificationLedger()
    ledger.record(round_index=1, candidate_id="c1", ingredient_families=("explicit_formula",), contradicted_window=(30.0, 30.5))
    ledger.record(round_index=2, candidate_id="c2", ingredient_families=("hardy_z", "explicit_formula"), contradicted_window=(50.0, 50.5))
    s = ledger.summary()
    assert s["total_falsifications"] == 2
    assert s["per_family_signature"]["explicit_formula"] == 1
    assert s["per_family_signature"]["explicit_formula+hardy_z"] == 1
    assert s["rounds_with_falsifications"] == [1, 2]


def test_to_dict_round_trips_for_persistence() -> None:
    ledger = FalsificationLedger()
    ledger.record(
        round_index=3, candidate_id="cX",
        ingredient_families=("xi_function",),
        contradicted_window=(40.1, 40.3),
    )
    d = ledger.to_dict()
    assert len(d["falsifications"]) == 1
    rec = d["falsifications"][0]
    assert rec["round_index"] == 3
    assert rec["family_signature"] == "xi_function"
    assert rec["contradicted_window"] == [40.1, 40.3]
