"""Validation failures at the record boundary."""


class RecordError(ValueError):
    """The supplied record or operation violates the v5 semantic contract."""
