import pytest
from mve.evaluation.scoring import score, ScoreError


def gold():
    return {"small": {"p": True}, "large": {"p": True, "n1": False, "n2": False}}


def test_micro_macro_differ_and_missing_predictions_remain_in_denominators():
    report = score(gold(), {"small": {"p": True}}, mode="query_set", task="appearance")
    assert report["micro"]["accuracy"] == 0.25
    assert report["macro"]["accuracy"] == 0.5
    assert report["micro"]["queries"] == 4
    assert report["micro"]["unanswered"] == 3
    assert report["micro"]["recall"] == 0.5
    assert report["macro"]["diagrams"] == 2
    assert report["null"]["micro"]["precision"] == 0.5
    assert report["null"]["macro"]["precision"] == pytest.approx(2 / 3)
    assert report["micro"]["negative_error_or_missing_rate"] == 1


def test_abstention_timeout_malformed_and_extras_are_explicit():
    for bad in [None, "timeout", ["p"], {"outside": True}, {"p": "true"}]:
        report = score(
            {"d": {"p": True}}, {"d": bad}, mode="query_set", task="appearance"
        )
        assert report["micro"]["queries"] == 1
        assert report["micro"]["accuracy"] == 0
        assert report["micro"]["unanswered"] == 1
        assert report["outcomes"]["d"] in {"malformed", "missing_or_failed"}


def test_query_mode_is_distinct_from_full_record_absence():
    query = score(
        {"d": {"p": True, "n": False}}, {"d": {}}, mode="query_set", task="appearance"
    )
    full = score(
        {"d": {"p": True, "n": False}}, {"d": []}, mode="full_record", task="appearance"
    )
    assert query["micro"]["accuracy"] == 0
    assert full["micro"]["accuracy"] == 0.5
    assert full["micro"]["unanswered"] == 0
    assert full["null"]["description"].startswith("N/A")
    assert full["full_record_exact"] == 0
    perfect = score(
        {"d": {"p": True, "n": False}},
        {"d": ["p"]},
        mode="full_record",
        task="appearance",
    )
    assert perfect["full_record_exact"] == 1


def test_degenerate_metrics_and_invalid_contracts():
    report = score(
        {"d": {"n": False}},
        {"d": {"n": False}},
        mode="query_set",
        task="annotation_reading",
    )
    assert report["micro"]["precision"] is None
    assert report["micro"]["recall"] is None
    assert report["macro"]["metric_diagrams"]["recall"] == 0
    for invalid in [{}, {"d": {}}, {"d": {"q": "true"}}]:
        with pytest.raises(ScoreError):
            score(invalid, {}, mode="query_set", task="appearance")
    for kwargs in [
        {"mode": "mixed", "task": "appearance"},
        {"mode": "query_set", "task": "mixed"},
    ]:
        with pytest.raises(ScoreError):
            score(gold(), {}, **kwargs)
    with pytest.raises(ScoreError):
        score(gold(), {"unfrozen": {}}, mode="query_set", task="appearance")


def test_all_positive_baseline_uses_same_micro_and_macro_weights():
    report = score(gold(), {}, mode="query_set", task="appearance")
    baseline = report["all_positive_baseline"]
    assert baseline["micro"]["precision"] == 0.5
    assert baseline["macro"]["precision"] == pytest.approx(2 / 3)
    assert baseline["micro"]["queries"] == 4
    assert baseline["macro"]["diagrams"] == 2
