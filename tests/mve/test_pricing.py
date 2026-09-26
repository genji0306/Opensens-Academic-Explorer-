import pytest
from mve.pricing import PriceError, normalize_prices, token_ceiling
from mve.budget import BudgetLedger, BudgetError
from tests.mve.test_budget import OFF


def table():
    return {
        "fixture-model": {
            "input_per_million": ".15",
            "output_per_million": ".60",
            "source_sha256": "a" * 64,
            "verified": False,
        }
    }


def test_token_ceiling_rounds_up_and_counts_both_directions():
    prices = normalize_prices(table())
    assert token_ceiling(prices, "fixture-model", input_tokens=1, output_tokens=1) == 1
    assert (
        token_ceiling(
            prices, "fixture-model", input_tokens=1_000_000, output_tokens=1_000_000
        )
        == 750_000
    )


def test_price_table_is_pinned_on_resume(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = BudgetLedger(path, price_table=table())
    ledger.reserve_tokens(
        "call",
        "P0",
        "fixture-model",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        wave="w",
        when=OFF,
    )
    assert ledger.snapshot()["exposure_micro_usd"] == 750_000
    changed = table()
    changed["fixture-model"]["output_per_million"] = ".70"
    with pytest.raises(BudgetError):
        BudgetLedger(path, price_table=changed)
    assert BudgetLedger(path, price_table=table()).snapshot()["configuration"]["prices"]


def test_price_and_token_input_rejections():
    prices = normalize_prices(table())
    for value in [-1, True, 1.1, "1"]:
        with pytest.raises(PriceError):
            token_ceiling(prices, "fixture-model", input_tokens=value, output_tokens=1)
    with pytest.raises(PriceError):
        token_ceiling(prices, "missing", input_tokens=1, output_tokens=1)
    for key, value in [
        ("source_sha256", "bad"),
        ("verified", "yes"),
        ("input_per_million", "-.1"),
        ("output_per_million", ".0000001"),
    ]:
        invalid = table()
        invalid["fixture-model"][key] = value
        with pytest.raises(PriceError):
            normalize_prices(invalid)
