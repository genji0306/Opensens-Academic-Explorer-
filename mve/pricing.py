"""Pinned rate manifests and conservative token ceilings; no vendor lookup or transport."""

import re
from mve.money import BudgetError, microdollars


class PriceError(BudgetError):
    """Price manifest or token upper bound is invalid."""


def normalize_prices(table):
    if not isinstance(table, dict):
        raise PriceError("price table must be a mapping")
    normalized = {}
    required = {"input_per_million", "output_per_million", "source_sha256", "verified"}
    for model, entry in table.items():
        if not isinstance(model, str) or not re.fullmatch(
            r"[A-Za-z0-9_.:/-]{1,200}", model
        ):
            raise PriceError("invalid model id")
        if not isinstance(entry, dict) or set(entry) != required:
            raise PriceError("price fields must match the manifest contract")
        if type(entry["verified"]) is not bool:
            raise PriceError("verification must be boolean")
        if not isinstance(entry["source_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", entry["source_sha256"]
        ):
            raise PriceError("price source hash required")
        try:
            rates = {
                key.replace("_per_", "_micro_usd_per_"): microdollars(entry[key])
                for key in ("input_per_million", "output_per_million")
            }
        except BudgetError as exc:
            raise PriceError(str(exc)) from exc
        normalized[model] = {
            **rates,
            "source_sha256": entry["source_sha256"],
            "verified": entry["verified"],
        }
    return normalized


def token_ceiling(prices, model, *, input_tokens, output_tokens):
    if model not in prices:
        raise PriceError("model absent from pinned price manifest")
    if any(
        type(n) is not int or n < 0 or n > 1_000_000_000
        for n in (input_tokens, output_tokens)
    ):
        raise PriceError(
            "token bounds must be nonnegative integers no larger than one billion"
        )
    rates = prices[model]
    # Input uses the uncached rate; callers must include image and hidden token costs.
    numerator = (
        input_tokens * rates["input_micro_usd_per_million"]
        + output_tokens * rates["output_micro_usd_per_million"]
    )
    return (numerator + 999_999) // 1_000_000
