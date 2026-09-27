"""Strict JSON observation grammar, followed by the WP-1 semantic geometry checks."""

import re
from mve.errors import RecordError
from mve.predicates import canonical_proposition, REGISTRY
from mve.validation import GEOMETRY_LENGTHS, check_geometry
from mve.perceiver.contract import strict_json

KINDS = set(GEOMETRY_LENGTHS) | {"polygon", "curve", "strand", "region"}


class ContentError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


def require(condition, status="malformed"):
    if not condition:
        raise ContentError(status)


def entity(value, width, height):
    require(isinstance(value, dict) and {"id", "label", "kind", "params"} <= set(value))
    require(not set(value) - {"id", "label", "kind", "params", "pieces"})
    require(
        isinstance(value["id"], str)
        and re.fullmatch(r"[A-Za-z0-9_]{1,64}", value["id"])
    )
    require(
        value["label"] is None
        or isinstance(value["label"], str)
        and len(value["label"]) <= 100
    )
    require(value["kind"] in KINDS)
    params = value["params"]
    require(isinstance(params, list) and len(params) <= 256)
    require(all(type(x) in {int, float} for x in params))
    geo = {"params": params, "source": "perceiver_call_1", "depends_on": [value["id"]]}
    if "pieces" in value:
        pieces = value["pieces"]
        require(isinstance(pieces, list) and len(pieces) <= 128)
        require(
            all(
                isinstance(p, list)
                and len(p) <= 256
                and all(type(x) in {int, float} for x in p)
                for p in pieces
            )
        )
        geo["pieces"] = pieces
        require(
            all(
                0 <= x <= (width if i % 2 == 0 else height)
                for p in pieces
                for i, x in enumerate(p)
            ),
            "out_of_image",
        )
    try:
        check_geometry(value, geo, {"image": {"width": width, "height": height}}, {})
    except RecordError as exc:
        raise ContentError(
            "out_of_image" if "out of frame" in str(exc) else "malformed"
        ) from exc
    if value["kind"] in {"tick", "arrow", "angle_mark", "right_angle_mark"}:
        require(
            params[0] + params[2] <= width and params[1] + params[3] <= height,
            "out_of_image",
        )
    return value


def observation(value, entities):
    require(isinstance(value, dict) and set(value) == {"proposition", "confidence"})
    confidence = value["confidence"]
    require(type(confidence) in {int, float} and 0 <= confidence <= 1)
    prop = value["proposition"]
    require(isinstance(prop, dict) and set(prop) == {"pred", "args"})
    require(isinstance(prop["pred"], str) and isinstance(prop["args"], list))
    require(all(isinstance(a, str) for a in prop["args"]))
    require(set(prop["args"]) <= set(entities), "missing_entities")
    try:
        prop = canonical_proposition(prop)
    except RecordError as exc:
        raise ContentError("malformed") from exc
    require(
        all(
            entities[a]["kind"] == kind
            for a, kind in zip(prop["args"], REGISTRY[prop["pred"]]["argument_kinds"])
        )
    )
    return {"proposition": prop, "confidence": confidence}


def parse(raw, width, height):
    try:
        body = strict_json(raw)
        message = body["choices"][0]["message"]
        require(not message.get("reasoning_content") and not message.get("reasoning"))
        content = strict_json(message["content"])
        require(
            isinstance(content, dict) and set(content) == {"entities", "observations"}
        )
        require(
            isinstance(content["entities"], list) and len(content["entities"]) <= 256
        )
        require(bool(content["entities"]), "missing_entities")
        entities = [entity(e, width, height) for e in content["entities"]]
        by_id = {e["id"]: e for e in entities}
        require(len(by_id) == len(entities))
        require(
            isinstance(content["observations"], list)
            and len(content["observations"]) <= 512
        )
        observations = [observation(o, by_id) for o in content["observations"]]
        return {"status": "ok", "entities": entities, "observations": observations}
    except ContentError as exc:
        return {"status": exc.status}
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
        OverflowError,
    ):
        return {"status": "malformed"}
