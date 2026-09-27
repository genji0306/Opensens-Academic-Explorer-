"""Backend-neutral visible scene contract; no JSXGraph dependency or hidden truth."""

import json
from pathlib import Path
from jsonschema import Draft202012Validator, ValidationError
from mve.generator.render import EDGES

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "schemas/mve_render_scene.json").read_text()
)


def validate_scene(scene):
    try:
        json.dumps(scene, allow_nan=False)
        Draft202012Validator(SCHEMA).validate(scene)
        if any(
            x > scene["width"] or y > scene["height"]
            for x, y in scene["points"].values()
        ):
            raise ValueError("point outside scene frame")
        if any(
            a not in scene["points"] or b not in scene["points"]
            for a, b in scene["segments"]
        ):
            raise ValueError("unknown scene segment endpoint")
    except (ValidationError, TypeError) as exc:
        raise ValueError("invalid visible scene") from exc


def scene_from_render(metadata):
    scene = {
        "schema": "mve-scene-v1",
        "frame": "pixel_topleft_xy",
        "width": metadata["width"],
        "height": metadata["height"],
        "points": json.loads(json.dumps(metadata["pixels"])),
        "segments": [list(pair) for pair in EDGES],
        "style": metadata["style"],
    }
    validate_scene(scene)
    return scene
