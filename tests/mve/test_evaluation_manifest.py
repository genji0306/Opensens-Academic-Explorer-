import pytest
from mve.evaluation.manifest import FrozenEvaluation, ManifestError, CONTROLS
from mve.evaluation.splits import freeze
from tests.mve.test_splits import items, allocations


def packet():
    split = freeze(items(), seed="fixture", allocations=allocations())
    gold = {
        r["id"]: {"q": True}
        for r in split.manifest()["items"]
        if r["split"] == "evaluation"
    }
    controls = {tag: {"fixture_id": tag, "sha256": "a" * 64} for tag in CONTROLS}
    manifest = FrozenEvaluation.create(
        split,
        gold,
        controls=controls,
        task="appearance",
        mode="query_set",
        model_revision="offline-fixture-v1",
    )
    return manifest, split, gold, controls


def test_frozen_gold_counts_and_provenance_bound_into_report():
    manifest, split, gold, _ = packet()
    result = manifest.score(split, gold, {})
    assert result["micro"]["queries"] == 4
    assert result["manifest_sha256"] == manifest.sha256
    assert result["split_sha256"] == split.sha256
    assert result["model_revision"] == "offline-fixture-v1"


def test_changed_gold_retired_split_and_missing_controls_fail_closed():
    manifest, split, gold, controls = packet()
    first = next(iter(gold))
    gold[first]["q"] = False
    with pytest.raises(ManifestError):
        manifest.score(split, gold, {})
    with pytest.raises(ValueError):
        manifest.score(split.retire("used for development"), gold, {})
    with pytest.raises(ManifestError):
        FrozenEvaluation.create(
            split,
            gold,
            controls={},
            task="appearance",
            mode="query_set",
            model_revision="fixture",
        )
    gold.pop(first)
    with pytest.raises(ManifestError):
        FrozenEvaluation.create(
            split,
            gold,
            controls=controls,
            task="appearance",
            mode="query_set",
            model_revision="fixture",
        )


def test_manifest_load_and_scorer_change_refusal(monkeypatch):
    manifest, split, gold, _ = packet()
    assert (
        FrozenEvaluation.load(manifest.payload, expected_sha256=manifest.sha256)
        == manifest
    )
    with pytest.raises(ManifestError):
        FrozenEvaluation.load(manifest.payload + " ", expected_sha256=manifest.sha256)
    monkeypatch.setattr("mve.evaluation.manifest.scorer_sha256", lambda: "f" * 64)
    with pytest.raises(ManifestError):
        manifest.score(split, gold, {})


def test_control_provenance_rejected_when_incomplete():
    from mve.evaluation.manifest import validate_controls

    _, _, _, controls = packet()
    for value in [
        {},
        {"fixture_id": "", "sha256": "a" * 64},
        {"fixture_id": "x", "sha256": "bad"},
    ]:
        bad = {**controls, CONTROLS[0]: value}
        with pytest.raises(ManifestError):
            validate_controls(bad)


def test_direct_construction_cannot_bypass_manifest_validation():
    for payload in ["{}", "[]", "invalid json"]:
        with pytest.raises(ManifestError):
            FrozenEvaluation(payload)
