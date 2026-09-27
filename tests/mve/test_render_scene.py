import pytest
from mve.generator.pipeline import generate
from mve.generator.scene import scene_from_render, validate_scene


def test_offline_scene_contract_contains_only_visible_geometry():
    result = generate("midpoint_grid", 0)
    scene = scene_from_render(result.render)
    validate_scene(scene)
    assert len(scene["points"]) == 6 and len(scene["segments"]) == 6
    assert set(scene) == {
        "schema",
        "frame",
        "width",
        "height",
        "points",
        "segments",
        "style",
    }
    assert "math_coordinates" not in str(scene) and "premises" not in str(scene)
    assert scene["points"]["A"] == result.render["pixels"]["A"]


def test_scene_rejects_missing_endpoint_nonfinite_and_out_of_frame():
    scene = scene_from_render(generate("midpoint_grid", 0).render)
    scene["segments"][0] = ["A", "missing"]
    with pytest.raises(ValueError):
        validate_scene(scene)
    scene["segments"][0] = ["A", "B"]
    scene["points"]["A"] = [float("nan"), 1]
    with pytest.raises(ValueError):
        validate_scene(scene)
    scene["points"]["A"] = [-1, 1]
    with pytest.raises(ValueError):
        validate_scene(scene)


@pytest.mark.parametrize("point", [[-1, 0], [0, -1], [-1, -1]])
def test_negative_scene_coordinates_are_rejected_on_both_axes(point):
    scene = scene_from_render(generate("midpoint_grid", 0).render)
    scene["points"]["A"] = point
    with pytest.raises(ValueError):
        validate_scene(scene)
