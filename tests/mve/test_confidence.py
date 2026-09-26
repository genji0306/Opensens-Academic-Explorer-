import pytest
from mve.evaluation.confidence import error_gate


def test_underpowered_zero_errors_does_not_pass_two_percent_gate():
    assert (
        error_gate(0, 148, independent=True, unit="independent diagram")["status"]
        == "insufficient_evidence"
    )
    result = error_gate(0, 149, independent=True, unit="independent diagram")
    assert result["upper95"] == pytest.approx(1 - 0.05 ** (1 / 149))
    assert result["status"] == "component_pass"


def test_missing_independence_or_measurements_is_inconclusive():
    assert error_gate(0, 0, independent=True, unit="diagram")["upper95"] is None
    assert (
        error_gate(0, 500, independent=False, unit="correlated relations")["status"]
        == "insufficient_evidence"
    )
    assert error_gate(1, 100, independent=True, unit="diagram")[
        "upper95"
    ] == pytest.approx(0.04655981145304509)
    for args in [(True, 2), (-1, 2), (3, 2), (0, -1)]:
        with pytest.raises(ValueError):
            error_gate(*args, independent=True, unit="diagram")
