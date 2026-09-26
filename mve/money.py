"""Exact micro-USD conversion for offline accounting."""

from decimal import Decimal, InvalidOperation


class BudgetError(ValueError):
    """Refused accounting operation; no transport should be launched."""


def microdollars(value):
    if isinstance(value, (float, bool)):
        raise BudgetError("money must be a decimal string, Decimal or integer")
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or number > 9_000_000_000:
            raise BudgetError("money must be finite, nonnegative and within range")
        sign, digits, exponent = number.as_tuple()
        # Remove insignificant zeros before checking scale, without Decimal arithmetic.
        digits = list(digits)
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        if not digits:
            return 0
        if exponent < -6:
            raise BudgetError("money must be exact to micro-USD")
        return int("".join(map(str, digits))) * 10 ** (exponent + 6)
    except (InvalidOperation, TypeError, OverflowError) as exc:
        raise BudgetError("invalid money") from exc
