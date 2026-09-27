from collections import Counter
from types import SimpleNamespace
from mve.generator.corpus import corpus_report, CONTROLS


def rows_for_acceptance():
    rows = [
        {
            "split": split,
            "math_coordinates_sha256": f"{split}:{i}",
            "image_sha256": f"{split}:image:{i}",
        }
        for split, count in [("fit", 2000), ("sealed", 500)]
        for i in range(count)
    ]
    return rows


def test_coordinate_collision_alone_blocks_corpus_acceptance():
    rows = rows_for_acceptance()
    counts = {"fit": 2000, "sealed": 500}
    controls = Counter({f"{role}:{tag}": 1 for role in counts for tag in CONTROLS})
    frozen = SimpleNamespace(sha256="f" * 64)
    clean = corpus_report(counts, frozen, rows, Counter(), controls, "a" * 40)
    assert clean["acceptance"] == "generated_counts_met"
    assert clean["cross_split_coordinate_collisions"] == 0
    rows[-1]["math_coordinates_sha256"] = rows[0]["math_coordinates_sha256"]
    contaminated = corpus_report(counts, frozen, rows, Counter(), controls, "a" * 40)
    assert contaminated["unique_mathematical_diagrams"] == counts
    assert contaminated["cross_split_image_collisions"] == 0
    assert contaminated["cross_split_coordinate_collisions"] == 1
    assert contaminated["acceptance"] != "generated_counts_met"


def test_local_parallel_generation_matches_serial():
    from mve.generator.corpus import generated_jobs

    jobs = [
        {"id": str(i), "family": "midpoint_grid", "seed": i, "split": "fit"}
        for i in range(2)
    ]
    serial = list(generated_jobs(jobs, "a" * 40, 1))
    parallel = list(generated_jobs(jobs, "a" * 40, 2))
    assert serial == parallel
