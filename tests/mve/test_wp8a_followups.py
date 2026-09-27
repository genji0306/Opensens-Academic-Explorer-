from pathlib import Path
import json
import pytest
from tests.mve.test_verdict_capture import record, verdict


def test_model_decline_is_refused_without_mutating_record():
    original = record()
    before = original.to_json()
    with pytest.raises(ValueError, match="only a human can adopt or decline"):
        verdict(original, value="decline", actor="model:manager")
    assert original.to_json() == before


def test_v5_dated_additive_changelog_and_copies():
    schema = Path("schemas/mve_observation_record.json").read_bytes()
    assert schema == Path("docs/mve/mve_observation_record.json").read_bytes()
    description = json.loads(schema)["description"]
    for word in [
        "2026-09-27",
        "can_N",
        "proposed",
        "human:",
        "development",
        "retrieval",
        "v6",
    ]:
        assert word in description
        assert word in Path("docs/mve/MVE_PLAN.md").read_text().split("## 13.")[1]
