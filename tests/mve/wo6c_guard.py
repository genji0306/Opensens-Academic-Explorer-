"""Opt-in WO-6c validation boundary, loaded only with -p tests.mve.wo6c_guard.

Existing WO-1b tests open/materialize D/R/donor/null/contrast blocks. The owner's
WO-6c instruction forbids that even during development tests. Opus runs those
three modules separately after this packet's review; their source is unchanged.
"""

import pytest

PROSPECTIVE_TESTS = {
    "test_snapshot_inventory.py",
    "test_snapshot_batch.py",
    "test_wo1b_review.py",
}


def pytest_runtest_setup(item):
    if item.path.name in PROSPECTIVE_TESTS:
        pytest.skip("WO-6c data discipline: prospective WO-1b tests deferred to Opus")
