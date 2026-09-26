from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import multiprocessing
import pytest
from mve.budget import BudgetLedger, BudgetError, microdollars, offpeak

OFF = datetime(2026, 9, 27, 2, tzinfo=timezone.utc)
PEAK = datetime(2026, 9, 28, 2, tzinfo=timezone.utc)


def worker(path, name, queue):
    try:
        BudgetLedger(path).reserve(name, "P0", "1.00", wave="wave-a", when=OFF)
        queue.put(True)
    except BudgetError:
        queue.put(False)


def test_concurrent_reservations_count_inflight(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")

    def reserve(i):
        try:
            ledger.reserve(str(i), "P0", "0.50", wave="wave-a", when=OFF)
            return True
        except BudgetError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(16))) == 4
    assert ledger.snapshot()["exposure_micro_usd"] == 2_000_000


def test_processes_share_reservations(tmp_path):
    path = tmp_path / "budget.sqlite"
    BudgetLedger(path)
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=worker, args=(path, str(i), queue)) for i in range(4)
    ]
    for p in processes:
        p.start()
    for p in processes:
        p.join(30)
        assert p.exitcode == 0
    assert sum(queue.get(timeout=5) for _ in processes) == 2


def test_aggregate_cap_across_waves_and_phases(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    for i, (phase, amount) in enumerate([("P0", "2"), ("P1", "8"), ("P2", "10")]):
        ledger.reserve(str(i), phase, amount, wave=f"wave-{i}", when=OFF)
    with pytest.raises(BudgetError):
        ledger.reserve("excess", "P2", ".000001", wave="new", when=OFF)
    with pytest.raises(BudgetError):
        ledger.reserve("p3", "P3", ".01", wave="later", when=OFF)


def test_peak_refusal_precedes_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    with pytest.raises(BudgetError):
        ledger.reserve("peak", "P0", ".01", wave="w", when=PEAK)
    assert ledger.snapshot()["attempts"] == []


def test_resume_keeps_uncertain_cost_and_send_is_single_use(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = BudgetLedger(path)
    ledger.reserve("one", "P0", "1", wave="w", when=OFF)
    ledger.mark_dispatched("one", when=OFF)
    resumed = BudgetLedger(path)
    assert resumed.snapshot()["exposure_micro_usd"] == 1_000_000
    with pytest.raises(BudgetError):
        resumed.mark_dispatched("one", when=OFF)
    with pytest.raises(BudgetError):
        resumed.cancel_unsent("one")
    resumed.reconcile("one", "0.2", receipt_sha256="a" * 64)
    assert resumed.snapshot()["exposure_micro_usd"] == 200_000
    with pytest.raises(BudgetError):
        resumed.reserve("one", "P0", "1", wave="w", when=OFF)


def test_peak_boundary_rechecked_before_dispatch(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.reserve("one", "P0", ".1", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.mark_dispatched("one", when=PEAK)
    ledger.cancel_unsent("one")
    assert ledger.snapshot()["exposure_micro_usd"] == 0


def test_retries_have_distinct_charged_attempts(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    for name in ("attempt-1", "attempt-2"):
        ledger.reserve(name, "P0", ".1", wave="w", when=OFF)
        ledger.mark_dispatched(name, when=OFF)
        ledger.reconcile(name, ".05", receipt_sha256="b" * 64)
    assert ledger.snapshot()["exposure_micro_usd"] == 100_000


def test_underestimated_charge_is_retained_and_freezes_new_calls(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.reserve("one", "P0", ".1", wave="w", when=OFF)
    ledger.mark_dispatched("one", when=OFF)
    ledger.reconcile("one", ".2", receipt_sha256="c" * 64)
    snap = ledger.snapshot()
    assert snap["frozen"] and snap["exposure_micro_usd"] == 200_000
    with pytest.raises(BudgetError):
        ledger.reserve("two", "P0", ".1", wave="w", when=OFF)


def test_quota_and_manifest_caps(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = BudgetLedger(path)
    ledger.record_quota("review-1", provider="codex", units=1)
    assert ledger.snapshot()["quota"][0]["units"] == 1
    assert ledger.snapshot()["exposure_micro_usd"] == 0
    with pytest.raises(BudgetError):
        BudgetLedger(path, aggregate="10")
    with pytest.raises(BudgetError):
        BudgetLedger(tmp_path / "bad.sqlite", aggregate="21")


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), 0.1, "NaN", "Infinity", "-1", ".0000001"]
)
def test_invalid_money(value):
    with pytest.raises(BudgetError):
        microdollars(value)


def test_clock_requires_timezone_and_uses_utc():
    assert offpeak(OFF)
    assert not offpeak(PEAK)
    assert offpeak(datetime(2026, 9, 28, 4, tzinfo=timezone.utc))
    with pytest.raises(BudgetError):
        offpeak(datetime(2026, 9, 28, 0))


def crash_after_dispatch(path):
    import os

    ledger = BudgetLedger(path)
    ledger.reserve("crashed", "P0", "1", wave="w", when=OFF)
    ledger.mark_dispatched("crashed", when=OFF)
    os._exit(23)


def test_real_process_crash_preserves_exposure(tmp_path):
    path = tmp_path / "budget.sqlite"
    BudgetLedger(path)
    process = multiprocessing.get_context("spawn").Process(
        target=crash_after_dispatch, args=(path,)
    )
    process.start()
    process.join(30)
    assert process.exitcode == 23
    assert BudgetLedger(path).snapshot()["exposure_micro_usd"] == 1_000_000


def test_old_runner_counterexample_is_refused(tmp_path):
    ledger = BudgetLedger(
        tmp_path / "budget.sqlite", aggregate=".05", p0=".05", p1=".05"
    )
    ledger.reserve("first", "P0", ".04", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.reserve("second", "P0", ".04", wave="w", when=OFF)
    assert ledger.snapshot()["exposure_micro_usd"] == 40_000


def test_stop_precedence_and_opus_restart(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.stop("zero_measurements")
    with pytest.raises(BudgetError):
        ledger.reserve("one", "P0", ".1", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.resume(actor="A3")
    ledger.resume(actor="Opus")
    ledger.reserve("one", "P0", ".1", wave="w", when=OFF)
    ledger.mark_dispatched("one", when=OFF)
    ledger.stop("mechanical_failure")
    with pytest.raises(BudgetError):
        ledger.resume(actor="Opus")
    ledger.reconcile("one", ".1", receipt_sha256="d" * 64)
    ledger.resume(actor="Opus")
    assert [e["kind"] for e in ledger.snapshot()["events"]] == [
        "stop",
        "resume",
        "stop",
        "resume",
    ]


def test_invalid_state_receipts_and_ids(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    with pytest.raises(BudgetError):
        ledger.reserve("../x", "P0", ".1", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.reserve("zero", "P0", "0", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.cancel_unsent("missing")
    ledger.reserve("x", "P0", ".1", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.reconcile("x", ".1", receipt_sha256="a" * 64)
    ledger.mark_dispatched("x", when=OFF)
    with pytest.raises(BudgetError):
        ledger.reconcile("x", ".1", receipt_sha256="invalid")
    with pytest.raises(BudgetError):
        ledger.record_quota("q", provider="codex", units=True)
    ledger.record_quota("q", provider="codex", units=1)
    with pytest.raises(BudgetError):
        ledger.record_quota("q", provider="codex", units=1)


def test_money_does_not_round_submicrodollars():
    with pytest.raises(BudgetError):
        microdollars("1.00000000000000000000000000001")


def test_overcap_charge_cannot_be_resumed(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.reserve("one", "P0", "1", wave="w", when=OFF)
    ledger.mark_dispatched("one", when=OFF)
    ledger.reconcile("one", "3", receipt_sha256="e" * 64)
    with pytest.raises(BudgetError):
        ledger.resume(actor="Opus")
    assert ledger.snapshot()["events"][0]["kind"] == "accounting_breach"


def test_stop_blocks_existing_dispatch_and_validates_resume(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.reserve("one", "P0", ".1", wave="w", when=OFF)
    with pytest.raises(BudgetError):
        ledger.stop("classifier_says_continue")
    with pytest.raises(BudgetError):
        ledger.resume(actor="Opus")
    ledger.stop("operator_stop")
    with pytest.raises(BudgetError):
        ledger.mark_dispatched("one", when=OFF)
    ledger.cancel_unsent("one")
