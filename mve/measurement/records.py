"""Append coordinate evidence from explicitly selected geometry IDs; never read truth files."""

from mve.record import transition
from mve.measurement.numpy_kernel import measure, VERSION


def measure_record(
    record, proposition, *, geometry_ids, tolerance, at="2026-09-27T00:00:00Z"
):
    data = record.to_dict()
    geometry = {g["id"]: (e, g) for e in data["entities"] for g in e["geometries"]}
    if len(set(geometry_ids)) != len(geometry_ids):
        raise ValueError("duplicate geometry id")
    coordinates = {}
    for ident in geometry_ids:
        if ident not in geometry:
            raise ValueError("unknown geometry id")
        entity, g = geometry[ident]
        if (
            entity["kind"] != "point"
            or not entity.get("valid", True)
            or not g.get("valid", True)
            or g["frame"] != "pixel_topleft_xy"
            or entity["id"] in coordinates
        ):
            raise ValueError("one current point geometry per argument required")
        coordinates[entity["id"]] = g["params"]
    if set(coordinates) != set(proposition["args"]):
        raise ValueError("geometry arguments mismatch")
    result = measure(
        proposition,
        coordinates,
        width=data["image"]["width"],
        height=data["image"]["height"],
        tolerance=tolerance,
    )
    number = max([int(m["id"].split("_")[1]) for m in data["measurements"]] + [0]) + 1
    result.update(id=f"mea_{number}", depends_on=list(geometry_ids))
    return transition(
        record,
        "measure",
        actor="A2",
        expected_revision=data["revision"],
        at=at,
        payload={"measurements": [result], "measurement_contract": VERSION},
    )
