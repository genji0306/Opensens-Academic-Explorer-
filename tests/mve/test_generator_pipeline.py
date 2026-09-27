import pytest
from mve.generator.constructions import construct, FAMILIES
from mve.generator.pipeline import generate
from mve.generator.exact import ExactEvaluator
from mve.identity import digest
from mve.record import Record


@pytest.mark.parametrize(
    "control",
    [
        "exact_positive",
        "near_miss_negative",
        "adversarial_negative",
        "not_to_scale",
        "degenerate",
    ],
)
def test_construction_controls_have_independent_exact_expectations(control):
    construction = construct(FAMILIES[0], 17, control=control)
    target = construction["control_target"]
    result = ExactEvaluator(construction["coordinates"]).classify(target)
    expected = (
        "degenerate"
        if control == "degenerate"
        else "false"
        if "negative" in control
        else "true"
    )
    assert result == expected


def test_generator_record_validates_and_render_style_is_not_math_identity():
    first = generate(FAMILIES[0], 7, style="thin")
    second = generate(FAMILIES[0], 7, style="bold")
    assert (
        first.record.to_dict()["content_hash"]
        == second.record.to_dict()["content_hash"]
    )
    assert first.truth.sha256 == second.truth.sha256
    assert first.png != second.png
    assert generate(FAMILIES[0], 7, style="thin").png == first.png
    assert Record.from_json(first.record.to_json()) == first.record
    assert first.record.to_dict()["image"]["truth"][
        "math_coordinates_sha256"
    ] == digest(first.truth.data()["math_coordinates"])
    assert first.record.to_dict()["sources"][0]["sha256"] == first.truth.sha256
    assert first.record.to_dict()["provenance"]["perceiver_calls"] == 0


def test_notscale_pixels_do_not_change_truth_coordinates():
    result = generate(FAMILIES[0], 3, control="not_to_scale")
    a, b, c = (result.render["pixels"][name] for name in "ABC")
    assert c != [(a[i] + b[i]) / 2 for i in (0, 1)]
    assert (
        ExactEvaluator(result.truth.data()["math_coordinates"]).classify(
            {"pred": "Midpoint", "args": ["C", "A", "B"]}
        )
        == "true"
    )


def test_frozen_proof_revision_changes_evidence_not_content_identity():
    original = generate(FAMILIES[0], 0, control="exact_positive")

    class FixtureDDAR:
        version = "fixture-v2"

        def prove(self, prop, premises, budget_s):
            return {"outcome": "timeout", "trace_sha256": None}

    changed = generate(FAMILIES[0], 0, control="exact_positive", backend=FixtureDDAR())
    assert original.truth.sha256 != changed.truth.sha256
    assert (
        original.record.to_dict()["content_hash"]
        == changed.record.to_dict()["content_hash"]
    )


def test_all_families_are_deterministic_and_unsupported_inputs_fail():
    assert len(set(FAMILIES)) == 15
    for family in FAMILIES:
        assert construct(family, 1) == construct(family, 1)
    for args in [("not-a-family", 0), (FAMILIES[0], True), (FAMILIES[0], -1)]:
        with pytest.raises(ValueError):
            construct(*args)


def test_evidence_rerun_is_explicit_record_revision():
    from mve.generator.pipeline import revise_evidence

    class Timeout:
        version = "fixture-timeout-v1"

        def prove(self, prop, premises, budget_s):
            return {"outcome": "timeout", "trace_sha256": None}

    original = generate(FAMILIES[0], 0)
    revised = revise_evidence(original, Timeout(), budget_s=2)
    before, after = original.record.to_dict(), revised.record.to_dict()
    assert after["revision"] == before["revision"] + 1
    assert after["record_id"] == before["record_id"]
    assert after["content_hash"] == before["content_hash"]
    assert after["sources"][0]["sha256"] == revised.truth.sha256
    assert original.truth.sha256 != revised.truth.sha256
    assert after["events"][-1]["kind"] == "edited"
    assert revised.png == original.png
