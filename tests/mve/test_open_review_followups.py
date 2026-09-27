"""Offline regressions for Opus follow-ups 6–8."""

from datetime import datetime, timezone, timedelta
import errno
import json
import sys
import pytest
from mve.budget import BudgetLedger, BudgetError, offpeak
from mve.evaluation.isolation import run_offline
from mve.pricing import normalize_prices, token_ceiling
from tests.mve.test_budget import OFF
from tests.mve.test_pricing import table


@pytest.mark.parametrize(
    "instant,allowed",
    [
        ("00:59:59.999999", True),
        ("01:00:00", False),
        ("03:59:59.999999", False),
        ("04:00:00", True),
        ("05:59:59.999999", True),
        ("06:00:00", False),
        ("09:59:59.999999", False),
        ("10:00:00", True),
    ],
)
def test_weekday_window_boundaries_guard_reservation_and_dispatch(
    tmp_path, instant, allowed
):
    when = datetime.fromisoformat("2026-09-28T" + instant + "+00:00")
    local = when.astimezone(timezone(timedelta(hours=7)))
    assert offpeak(when) is allowed and offpeak(local) is allowed
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.reserve("held", "P0", ".1", wave="fixture", when=OFF)
    if allowed:
        ledger.reserve("new", "P0", ".1", wave="fixture", when=local)
        ledger.mark_dispatched("held", when=local)
        assert ledger.snapshot()["attempts"][0]["state"] == "dispatched"
    else:
        with pytest.raises(BudgetError, match="peak-hour"):
            ledger.reserve("new", "P0", ".1", wave="fixture", when=local)
        with pytest.raises(BudgetError, match="peak-hour"):
            ledger.mark_dispatched("held", when=local)
        assert len(ledger.snapshot()["attempts"]) == 1
        assert ledger.snapshot()["attempts"][0]["state"] == "reserved"


def test_zero_token_bound_cannot_create_a_dispatch_permit(tmp_path):
    prices = table()
    assert (
        token_ceiling(
            normalize_prices(prices), "fixture-model", input_tokens=0, output_tokens=0
        )
        == 0
    )
    ledger = BudgetLedger(tmp_path / "budget.sqlite", price_table=prices)
    with pytest.raises(BudgetError, match="positive"):
        ledger.reserve_tokens(
            "zero",
            "P0",
            "fixture-model",
            input_tokens=0,
            output_tokens=0,
            wave="fixture",
            when=OFF,
        )
    assert ledger.snapshot()["attempts"] == []
    assert ledger.snapshot()["exposure_micro_usd"] == 0
    with pytest.raises(BudgetError, match="unknown attempt"):
        ledger.mark_dispatched("zero", when=OFF)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox evidence only")
def test_worker_created_runtime_symlink_cannot_read_private_gold(tmp_path):
    private = tmp_path / "gold"
    private.mkdir()
    (private / "truth.json").write_text("PRIVATE FIXTURE ANSWER")
    public = tmp_path / "public"
    public.mkdir()
    worker = public / "worker.py"
    worker.write_text("""import json, pathlib, sys
alias = pathlib.Path('created-after-launch')
alias.symlink_to(sys.argv[1], target_is_directory=True)
result = {'link_created': alias.is_symlink()}
try:
    result['read'] = (alias / 'truth.json').read_text()
except OSError as exc:
    result['errno'] = exc.errno
print(json.dumps(result))
""")
    assert not (public / "created-after-launch").exists()
    result = run_offline(
        worker, public_dir=public, private_roots=[private], args=[str(private)]
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"link_created": True, "errno": errno.EPERM}
    assert "PRIVATE FIXTURE ANSWER" not in result.stdout
