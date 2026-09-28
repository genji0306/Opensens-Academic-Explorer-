"""Closed refusal vocabulary: no exception text crosses the CLI boundary."""

import argparse
from contextlib import contextmanager
from functools import wraps

LABELS = frozenset(
    {
        "review_head",
        "clean_tree",
        "owner_approval",
        "design_pin",
        "source_pin",
        "peak_window",
        "budget_cap",
        "call_cap",
        "reconciliation",
        "disk_free",
        "generated_cap",
        "run_exists",
        "lock_held",
        "arguments",
        "input_contract",
        "storage",
        "internal_error",
    }
)


class Refusal(ValueError):
    def __init__(self, label):
        if label not in LABELS:
            raise ValueError("invalid refusal label")
        self.label = label
        super().__init__(label)


def require(ok, label):
    if not ok:
        raise Refusal(label)


@contextmanager
def boundary(label):
    try:
        yield
    except Refusal:
        raise
    except Exception:
        raise Refusal(label) from None


def guarded(label):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with boundary(label):
                return fn(*args, **kwargs)

        return wrapped

    return decorate


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "WO-6 refused: arguments\n")
