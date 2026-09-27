"""WP-0b exercises the dispatch boundary with local fake replies only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import pytest
from mve.budget import BudgetLedger, BudgetError
from mve.preflight.probe import ProbeRefused, run_probe, PROBE_ID
from mve.preflight.probe_fixtures import FakeTransport, fixture_request, fixture_reply

OFF = datetime(2026, 9, 28, 0, 59, tzinfo=timezone.utc)
PEAK = datetime(2026, 9, 28, 1, tzinfo=timezone.utc)
MODEL = "deepseek-fixture"


def prices(verified=True):
    return {
        MODEL: {
            "input_per_million": "10",
            "output_per_million": "10",
            "source_sha256": "a" * 64,
            "verified": verified,
        }
    }


def ledger(tmp_path, **kwargs):
    return BudgetLedger(tmp_path / "campaign.sqlite", price_table=prices(), **kwargs)


def invoke(book, tmp_path, transport=None, request=None, clock=lambda: OFF):
    return run_probe(
        book,
        request or fixture_request(),
        output=tmp_path / "probe",
        transport=transport or FakeTransport(fixture_reply()),
        mode="offline_fixture",
        clock=clock,
    )


@pytest.mark.parametrize("table", [prices(False), {}])
def test_unverified_or_missing_price_refuses_before_fake_send(tmp_path, table):
    book = BudgetLedger(tmp_path / "campaign.sqlite", price_table=table)
    fake = FakeTransport(fixture_reply())
    with pytest.raises(BudgetError, match="price"):
        invoke(book, tmp_path, fake)
    assert fake.calls == 0
    assert book.snapshot()["attempts"] == []


def test_hosted_mode_is_hard_disabled_pending_review_and_owner_go(tmp_path):
    fake = FakeTransport(fixture_reply())
    with pytest.raises(ProbeRefused, match="hosted.*disabled"):
        run_probe(
            ledger(tmp_path),
            fixture_request(),
            output=tmp_path / "probe",
            transport=fake,
        )
    assert fake.calls == 0


def test_offline_mode_cannot_accept_an_arbitrary_sender(tmp_path):
    with pytest.raises(ProbeRefused, match="FakeTransport"):
        run_probe(
            ledger(tmp_path),
            fixture_request(),
            output=tmp_path / "probe",
            transport=lambda _: pytest.fail("must not send"),
            mode="offline_fixture",
        )


@pytest.mark.parametrize(
    "times,expected_state", [([PEAK], None), ([OFF, PEAK], "cancelled")]
)
def test_peak_refused_at_reservation_and_again_at_dispatch(
    tmp_path, times, expected_state
):
    book, fake = ledger(tmp_path), FakeTransport(fixture_reply())
    clock = iter(times)
    with pytest.raises(BudgetError, match="peak"):
        invoke(book, tmp_path, fake, clock=lambda: next(clock))
    assert fake.calls == 0
    rows = book.snapshot()["attempts"]
    assert (rows[0]["state"] if rows else None) == expected_state
    assert book.snapshot()["exposure_micro_usd"] == 0


def test_frozen_campaign_refuses_transport(tmp_path):
    book, fake = ledger(tmp_path), FakeTransport(fixture_reply())
    book.stop("operator_stop")
    with pytest.raises(BudgetError, match="frozen"):
        invoke(book, tmp_path, fake)
    assert fake.calls == 0


@pytest.mark.parametrize(
    "caps,phase,amount", [({}, "P0", "1.99"), ({"aggregate": ".03"}, "P2", ".02")]
)
def test_existing_inflight_exposure_blocks_probe(tmp_path, caps, phase, amount):
    book, fake = ledger(tmp_path, **caps), FakeTransport(fixture_reply())
    book.reserve("occupied", phase, amount, wave="prior", when=OFF)
    with pytest.raises(BudgetError, match="cap"):
        invoke(book, tmp_path, fake)
    assert fake.calls == 0
    assert len(book.snapshot()["attempts"]) == 1


def test_probe_ceiling_and_positive_token_bound(tmp_path):
    from dataclasses import replace

    book, fake = ledger(tmp_path), FakeTransport(fixture_reply())
    for request in [
        replace(fixture_request(), max_input_tokens=5001),
        replace(fixture_request(), max_input_tokens=0, max_output_tokens=0),
    ]:
        with pytest.raises(BudgetError):
            invoke(book, tmp_path, fake, request)
    assert fake.calls == 0
    assert book.snapshot()["attempts"] == []


def test_five_cent_boundary_is_allowed_and_accounted_in_p0(tmp_path):
    from dataclasses import replace

    book = ledger(tmp_path)
    invoke(
        book,
        tmp_path,
        request=replace(
            fixture_request(), max_input_tokens=2500, max_output_tokens=2500
        ),
    )
    row = book.snapshot()["attempts"][0]
    assert row["reserved"] == 50_000 and row["phase"] == "P0"
    assert row["state"] == "settled" and row["actual"] == 1500


def test_reservation_is_durable_before_transport_and_receipts_are_explicitly_fake(
    tmp_path, monkeypatch
):
    book, fake = ledger(tmp_path), FakeTransport(fixture_reply())
    original = FakeTransport.send

    def inspect_before_send(self, request):
        snap = BudgetLedger(book.path, price_table=prices()).snapshot()
        assert snap["attempts"][0]["id"] == PROBE_ID
        assert snap["attempts"][0]["state"] == "dispatched"
        assert snap["exposure_micro_usd"] == 20_000
        assert request.max_output_tokens == 1000
        return original(self, request)

    monkeypatch.setattr(FakeTransport, "send", inspect_before_send)
    result = invoke(book, tmp_path, fake)
    assert fake.calls == 1
    assert result["mode"] == "offline_fixture" and result["hosted_calls"] == 0
    assert result["actual_api_cost_usd"] == "0"
    assert result["live_cost_model"]["tokens_per_image"] is None
    assert result["live_cost_model"]["image_support"] == "unverified"
    assert (tmp_path / "probe/response.raw").read_bytes() == fixture_reply().raw
    assert json.loads((tmp_path / "probe/cost_model.json").read_text()) == result


def test_one_probe_only_across_concurrent_calls_and_restart(tmp_path):
    book = ledger(tmp_path)
    fakes = [FakeTransport(fixture_reply()) for _ in range(2)]

    def run(i):
        try:
            run_probe(
                book,
                fixture_request(),
                output=tmp_path / str(i),
                transport=fakes[i],
                mode="offline_fixture",
                clock=lambda: OFF,
            )
            return True
        except BudgetError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(run, range(2))) == 1
    assert sum(f.calls for f in fakes) == 1
    with pytest.raises(BudgetError, match="already exists"):
        invoke(BudgetLedger(book.path, price_table=prices()), tmp_path)
    assert len(book.snapshot()["attempts"]) == 1
