"""Offline report contracts, written before the implementation."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from mve.reporting.ledger import summarize_budget
from mve.reporting.gates import SPECS, evaluate_gate, g3_checks, relation_table
from mve.reporting.sources import Evidence
from mve.reporting.current import build_report
from mve.reporting.render import markdown, serialize

ROOT = Path(__file__).resolve().parents[2]
BASE = "ea621a8918e"
LIVE = json.loads((ROOT / "docs/mve/reviews/wp0b-live/ledger.json").read_text())


def ledger(*rows, frozen=False, events=(), quota=()):
    return {
        "attempts": list(rows),
        "frozen": frozen,
        "events": list(events),
        "quota": list(quota),
        "configuration": {
            "caps": {"P0": 2_000_000, "P1": 8_000_000, "aggregate": 20_000_000},
            "window": "test-window",
            "prices": {},
        },
    }


def attempt(ident, state, reserved=100, actual=None, phase="P1"):
    return {
        "id": ident,
        "phase": phase,
        "state": state,
        "reserved": reserved,
        "actual": actual,
        "wave": "fixture",
        "receipt": None,
    }


def test_live_charge_carried_once_with_both_origins_retained():
    live_row = LIVE["attempts"][0]
    result = summarize_budget(ledger(live_row), LIVE)
    assert result["aggregate"]["settled"]["micro_usd"] == 268
    assert result["aggregate"]["exposure"]["usd"] == "0.000268"
    assert result["phases"]["P0"]["remaining"]["usd"] == "1.999732"
    assert result["attempts"][0]["origins"] == ["campaign", "live"]
    assert result["aggregate"]["attempts_by_state"]["settled"] == 1
    assert result["live_caps"]["aggregate"] == 50000
    assert result["caps"]["aggregate"] == 20000000


def test_absent_campaign_is_not_a_zero_or_unfrozen_campaign():
    result = summarize_budget(None, LIVE)
    assert result["complete"] is False
    assert result["frozen"] is None
    assert result["phases"]["P1"]["remaining"] is None
    assert result["aggregate"]["exposure"]["micro_usd"] == 268
    assert "known" in result["scope"]


def test_uncertain_reserved_cancelled_overcharge_quota_and_stop():
    campaign = ledger(
        attempt("sent", "dispatched", 20),
        attempt("held", "reserved", 10),
        attempt("cancel", "cancelled", 30),
        attempt("paid", "settled", 40, 50),
        frozen=True,
        events=[{"kind": "stop", "detail": "mechanical_failure"}],
        quota=[{"id": "q", "provider": "codex", "units": 7}],
    )
    report = summarize_budget(campaign, LIVE)
    total = report["aggregate"]
    assert [
        total[k]["micro_usd"] for k in ["reserved", "settled", "uncertain", "exposure"]
    ] == [10, 318, 20, 348]
    assert report["frozen"] is True
    assert report["ledgers"]["campaign"]["events"][0]["kind"] == "stop"
    assert report["quota_by_provider"] == {"codex": 7}
    assert total["attempts_by_state"]["cancelled"] == 1
    assert report["phases"]["P2"]["remaining"]["micro_usd"] == 20000000 - 348


@pytest.mark.parametrize(
    "change", [{"actual": 269}, {"state": "dispatched"}, {"phase": "P1"}]
)
def test_conflicting_carry_refuses(change):
    row = {**LIVE["attempts"][0], **change}
    with pytest.raises(ValueError):
        summarize_budget(ledger(row), LIVE)


@pytest.mark.parametrize(
    "row",
    [
        attempt("x", "settled"),
        attempt("x", "reserved", 0.1),
        attempt("x", "new"),
        attempt("x", "reserved", True),
        attempt("x", "reserved", -1),
        attempt("x", "reserved", phase="P3"),
    ],
)
def test_invalid_accounting_never_silently_drops_exposure(row):
    with pytest.raises(ValueError):
        summarize_budget(ledger(row), LIVE)


@pytest.mark.parametrize("gate", SPECS)
@pytest.mark.parametrize("state", ["established", "failed", "not established"])
def test_each_gate_state_fixture(gate, state):
    checks = {
        key: {
            "outcome": True,
            "reason": "fixture criterion met",
            "sources": ["fixture.json#/value"],
        }
        for key in SPECS[gate]["requirements"]
    }
    if state == "failed":
        checks[next(iter(checks))]["outcome"] = False
    elif state == "not established":
        checks.pop(next(iter(checks)))
    report = evaluate_gate(gate, checks)
    assert report["status"] == state
    assert report["null"]
    assert report["counts"]["criteria_expected"] == len(SPECS[gate]["requirements"])
    assert report["micro"] is None and report["macro"] is None


def test_evidence_missing_or_truthy_never_establishes():
    with pytest.raises(ValueError):
        evaluate_gate("G3", {"first_pass": {"outcome": "yes", "sources": ["x"]}})
    with pytest.raises(ValueError):
        evaluate_gate("G3", {"first_pass": {"outcome": True, "sources": []}})


def test_g3_human_rubric_is_pending_not_failed():
    summary = json.loads((ROOT / "mve/lean/artifacts/g3-taskset/g3.json").read_text())
    checks = g3_checks(summary)
    report = evaluate_gate("G3", checks)
    assert report["status"] == "not established"
    assert checks["semantic_rubric"]["outcome"] is None
    assert "0/50" in checks["semantic_rubric"]["reason"]
    summary.update(human_reviews=50, semantic_rubric_passes=19)
    assert evaluate_gate("G3", g3_checks(summary))["status"] == "failed"
    summary["semantic_rubric_passes"] = 20
    assert evaluate_gate("G3", g3_checks(summary))["status"] == "established"


def test_relation_scoring_keeps_modes_and_aggregations_and_missing_denominators():
    gold = {"a": {"q": True}, "b": {"q": True, "r": False, "s": False}}
    query = relation_table(
        gold,
        {"a": {"q": True}},
        mode="query_set",
        task="appearance",
        sources=["fixture"],
    )
    full = relation_table(
        gold, {"a": ["q"]}, mode="full_record", task="appearance", sources=["fixture"]
    )
    assert query["micro"]["accuracy"] == 0.25
    assert query["macro"]["accuracy"] == 0.5
    assert query["micro"]["unanswered"] == 3
    assert query["null"]["micro"]["precision"] == 0.5
    assert full["null"]["micro"] is None
    assert full["mode"] != query["mode"]
    assert query["denominators"]["micro"]["recall"] == 2
    assert query["denominators"]["macro"]["accuracy"] == 2


def test_committed_sources_ignore_dirty_working_copy(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.json").write_text('{"x":1}\n')
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.json"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    (tmp_path / "a.json").write_text('{"x":2}')
    evidence = Evidence(tmp_path, "HEAD")
    assert evidence.json("a.json") == {"x": 1}
    assert (
        evidence.sources["a.json"]["sha256"] == hashlib.sha256(b'{"x":1}\n').hexdigest()
    )
    assert evidence.optional("absent.json") is None
    with pytest.raises(ValueError):
        evidence.json("../outside")


def test_current_report_determinism_provenance_and_honesty():
    first = build_report(ROOT, BASE)
    second = build_report(ROOT, BASE)
    assert serialize(first) == serialize(second)
    assert markdown(first) == markdown(second)
    assert first["budget"]["aggregate"]["settled"]["micro_usd"] == 268
    assert first["gates"]["G3"]["status"] == "not established"
    assert first["gates"]["G2"]["status"] == "not established"
    assert all(g["status"] == "not established" for g in first["gates"].values())
    assert all(len(s["sha256"]) == 64 for s in first["sources"].values())
    assert "/Users/" not in serialize(first)
    assert "0/50" in markdown(first)
    assert "query_set" in markdown(first) and "full_record" in markdown(first)


def test_cli_writes_identical_formats(tmp_path):
    from mve.reporting.__main__ import main

    main(["--revision", BASE, "--output", str(tmp_path)])
    data = json.loads((tmp_path / "SUMMARY.json").read_text())
    assert (tmp_path / "SUMMARY.md").read_text() == markdown(data)
    original = (tmp_path / "SUMMARY.json").read_bytes()
    main(["--revision", BASE, "--output", str(tmp_path)])
    assert (tmp_path / "SUMMARY.json").read_bytes() == original


def test_snapshot_validation_and_quota_deduplication():
    bad = ledger()
    bad["frozen"] = "false"
    with pytest.raises(ValueError):
        summarize_budget(bad, LIVE)
    bad = ledger(attempt("a", "settled", actual=1))
    bad["exposure_micro_usd"] = 9
    with pytest.raises(ValueError):
        summarize_budget(bad, LIVE)
    bad = ledger()
    bad["configuration"]["caps"]["P0"] = 3_000_000
    with pytest.raises(ValueError):
        summarize_budget(bad, LIVE)
    quota = {"id": "q", "provider": "codex", "units": 4}
    live = deepcopy(LIVE)
    live["quota"] = [quota]
    assert summarize_budget(ledger(quota=[quota]), live)["quota_by_provider"] == {
        "codex": 4
    }
    with pytest.raises(ValueError):
        summarize_budget(ledger(quota=[{**quota, "units": 5}]), live)


def test_mutation_free_and_live_freeze_is_not_hidden():
    live = deepcopy(LIVE)
    live["frozen"] = True
    wrong_phase = deepcopy(LIVE)
    wrong_phase["attempts"][0]["phase"] = "P1"
    with pytest.raises(ValueError, match="P0"):
        summarize_budget(None, wrong_phase)
    before = deepcopy(live)
    assert summarize_budget(None, live)["frozen"] is True
    assert live == before
    with pytest.raises(ValueError):
        summarize_budget(ledger(attempt("a", "reserved", actual=1)), LIVE)


def test_over_cap_headroom_is_negative_not_clamped():
    result = summarize_budget(
        ledger(attempt("p", "settled", actual=21_000_000), frozen=True), LIVE
    )
    assert result["aggregate"]["remaining"]["micro_usd"] == -1_000_268
    assert result["phases"]["P2"]["remaining"]["usd"] == "-1.000268"


def test_bad_git_revision_and_required_missing():
    with pytest.raises(ValueError):
        Evidence(ROOT, "missing-reports-fixture-revision")
    with pytest.raises(ValueError):
        Evidence(ROOT, BASE).json("not-present.json")
    with pytest.raises(ValueError):
        evaluate_gate("G3", {"bogus": {"outcome": True, "sources": ["fixture"]}})


def test_stale_g3_or_corpus_aggregate_is_refused():
    from mve.reporting.tables import (
        g3_table,
        corpus_table,
        G3,
        TASKS,
        REFERENCES,
        CORPUS,
        GENERATION,
    )

    def read(path):
        return json.loads((ROOT / path).read_text())

    summary = read(G3)
    summary["first_pass_well_typed"] = 99
    with pytest.raises(ValueError, match="summary disagrees"):
        g3_table(summary, read(TASKS), read(REFERENCES))
    summary = read(G3)
    summary["controls"]["empty"]["detected"] = 99
    with pytest.raises(ValueError, match="controls/equivalence"):
        g3_table(summary, read(TASKS), read(REFERENCES))
    generation = read(GENERATION)
    generation["counts"]["sealed"] = 499
    with pytest.raises(ValueError, match="receipts disagree"):
        corpus_table(read(CORPUS), generation)


def test_underpowered_g3_is_inconclusive_and_invalid_counts_refused():
    summary = json.loads((ROOT / "mve/lean/artifacts/g3-taskset/g3.json").read_text())
    summary.update(
        tasks=90,
        unique_canonical_statements=90,
        post_repair_well_typed=90,
        human_reviews=50,
        semantic_rubric_passes=20,
    )
    assert evaluate_gate("G3", g3_checks(summary))["status"] == "not established"
    summary.update(semantic_rubric_passes=51)
    with pytest.raises(ValueError):
        g3_checks(summary)


def test_partial_sources_and_campaign_snapshot(monkeypatch):
    import mve.reporting.current as current

    class FixtureEvidence(Evidence):
        def optional(self, path):
            if path == current.CAMPAIGN:
                return ledger(*LIVE["attempts"])
            self.missing.append(path)
            return None

    monkeypatch.setattr(current, "Evidence", FixtureEvidence)
    report = current.build_report(ROOT, BASE)
    assert report["budget"]["complete"]
    assert all(g["status"] == "not established" for g in report["gates"].values())
    assert all(not rows for rows in report["tables"].values())
    assert "not established" in markdown(report)


def test_live_receipt_disagreement_refuses(monkeypatch):
    import mve.reporting.current as current

    class FixtureEvidence(Evidence):
        def optional(self, path):
            data = super().optional(path)
            if path == current.LIVE:
                data["observation"]["derived_micro_usd"] = 999
            return data

    monkeypatch.setattr(current, "Evidence", FixtureEvidence)
    with pytest.raises(ValueError, match="charge disagree"):
        current.build_report(ROOT, BASE)


@pytest.mark.parametrize(
    "patch",
    [{"tasks": True}, {"first_pass_well_typed": 90, "post_repair_well_typed": 80}],
)
def test_bad_g3_counts_refused(patch):
    data = json.loads((ROOT / "mve/lean/artifacts/g3-taskset/g3.json").read_text())
    data.update(patch)
    with pytest.raises(ValueError):
        g3_checks(data)


def test_g3_predicate_summary_is_checked():
    from mve.reporting.tables import g3_table, G3, TASKS, REFERENCES

    data = json.loads((ROOT / G3).read_text())
    data["per_predicate_counts"]["Parallel"] = 99
    with pytest.raises(ValueError):
        g3_table(
            data,
            json.loads((ROOT / TASKS).read_text()),
            json.loads((ROOT / REFERENCES).read_text()),
        )


def test_both_live_formats_use_exact_money():
    from mve.reporting.ledger import money

    assert money(9007199254740993)["usd"] == "9007199254.740993"
    assert (
        summarize_budget(ledger(attempt("free", "settled", actual=0)), LIVE)[
            "aggregate"
        ]["settled"]["micro_usd"]
        == 268
    )


def test_money_ignores_callers_decimal_precision():
    from decimal import localcontext
    from mve.reporting.ledger import money

    with localcontext() as context:
        context.prec = 6
        assert money(9007199254740993)["usd"] == "9007199254.740993"


@pytest.mark.parametrize("patch", ["controls", "proof", "outcome"])
def test_g3_invalid_typecheck_and_control_evidence_refused(patch):
    from mve.reporting.tables import g3_table, G3, TASKS, REFERENCES

    data = json.loads((ROOT / G3).read_text())
    tasks = json.loads((ROOT / TASKS).read_text())
    if patch == "controls":
        data["controls"] = {}
    elif patch == "proof":
        tasks[0]["first_pass"]["proof_checked"] = True
    else:
        tasks[0]["first_pass"]["outcome"] = "typechecked"
    with pytest.raises(ValueError):
        g3_table(data, tasks, json.loads((ROOT / REFERENCES).read_text()))


def test_module_entrypoint(tmp_path, monkeypatch):
    import runpy
    import sys

    monkeypatch.setattr(
        sys, "argv", ["mve.reporting", "--revision", BASE, "--output", str(tmp_path)]
    )
    runpy.run_path(str(ROOT / "mve/reporting/__main__.py"), run_name="__main__")
    assert (tmp_path / "SUMMARY.md").is_file()
