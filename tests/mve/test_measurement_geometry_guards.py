"""Geometry selection refuses ambiguity before the numeric kernel or transition."""

from copy import deepcopy
from types import SimpleNamespace
import pytest
from mve.measurement import measure_record
from mve.record import Record
from mve.errors import RecordError
from tests.mve.fixtures import populated

PROP = {"pred": "Collinear", "args": ["ent_1", "ent_2", "ent_3"]}


@pytest.fixture
def kernel_must_not_run(monkeypatch):
    import mve.measurement.records as records

    def never(*args, **kwargs):
        raise AssertionError("selection must fail before numeric evaluation")

    monkeypatch.setattr(records, "measure", never)


@pytest.mark.parametrize(
    "ids,message",
    [
        (["geo_1", "geo_1", "geo_3"], "duplicate geometry id"),
        (["geo_1", "geo_2", "geo_999"], "unknown geometry id"),
    ],
)
def test_duplicate_and_unknown_selection(ids, message, kernel_must_not_run):
    record = Record.from_dict(populated())
    before = record.to_json()
    with pytest.raises(ValueError, match=message):
        measure_record(record, PROP, geometry_ids=ids, tolerance=1e-8)
    assert record.to_json() == before


def extra_entity(data):
    entity = deepcopy(data["entities"][0])
    entity.update(id="ent_4", label="D", depends_on=[])
    geometry = entity["geometries"][0]
    geometry.update(id="geo_4", depends_on=["ent_4"])
    data["entities"].append(entity)
    return entity, geometry


@pytest.mark.parametrize("case", ["nonpoint", "invalid_entity", "invalid_geometry"])
def test_only_current_point_geometry_is_accepted(case, kernel_must_not_run):
    data = populated()
    entity, geometry = extra_entity(data)
    if case == "nonpoint":
        entity["kind"] = "segment"
        geometry["params"] = [10, 20, 30, 40]
    elif case == "invalid_entity":
        entity["valid"] = False
        geometry["valid"] = False
    else:
        geometry["valid"] = False
    record = Record.from_dict(data)
    prop = {"pred": "Collinear", "args": ["ent_4", "ent_2", "ent_3"]}
    with pytest.raises(ValueError, match="one current point geometry"):
        measure_record(
            record, prop, geometry_ids=["geo_4", "geo_2", "geo_3"], tolerance=1e-8
        )


def test_two_geometries_of_one_entity_are_ambiguous(kernel_must_not_run):
    data = populated()
    second = deepcopy(data["entities"][0]["geometries"][0])
    second.update(id="geo_4", params=[15, 20])
    data["entities"][0]["geometries"].append(second)
    record = Record.from_dict(data)
    with pytest.raises(ValueError, match="one current point geometry"):
        measure_record(
            record,
            PROP,
            geometry_ids=["geo_1", "geo_4", "geo_2", "geo_3"],
            tolerance=1e-8,
        )


def test_wrong_frame_defense_precedes_numeric_kernel(kernel_must_not_run):
    data = populated()
    data["entities"][0]["geometries"][0]["frame"] = "cartesian_xy"
    # v5 already rejects this frame; exercise the adapter's defensive guard directly.
    with pytest.raises(RecordError, match="frame"):
        Record.from_dict(data)
    adapter = SimpleNamespace(to_dict=lambda: deepcopy(data))
    with pytest.raises(ValueError, match="one current point geometry"):
        measure_record(
            adapter, PROP, geometry_ids=["geo_1", "geo_2", "geo_3"], tolerance=1e-8
        )


def test_measurement_preserves_content_and_execution_identity():
    original = Record.from_dict(populated())
    before = original.to_dict()
    measured = measure_record(
        original, PROP, geometry_ids=["geo_1", "geo_2", "geo_3"], tolerance=1e-8
    ).to_dict()
    assert measured["content_hash"] == before["content_hash"]
    assert measured["record_id"] == before["record_id"]
    assert measured["revision"] == before["revision"] + 1
    assert len(measured["measurements"]) == len(before["measurements"]) + 1
    assert original.to_dict() == before
