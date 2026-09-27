"""Frozen family corpus; public PNGs and private truth/records live in separate roots."""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from mve.evaluation.splits import freeze
from mve.generator.constructions import FAMILIES, CONTROLS
from mve.generator.pipeline import generate
from mve.identity import digest

ALLOCATIONS = {
    "development": 2,
    "retrieval": 2,
    "fit": 7,
    "calibration": 2,
    "evaluation": 2,
}
DEFAULT_COUNTS = {
    "development": 20,
    "retrieval": 20,
    "fit": 2000,
    "calibration": 20,
    "evaluation": 500,
}


def layout(counts, seed):
    if set(counts) != set(ALLOCATIONS) or any(
        type(counts[k]) is not int or counts[k] < n for k, n in ALLOCATIONS.items()
    ):
        raise ValueError("counts must include each reserved construction family")
    base = freeze(
        [{"id": f, "family": f} for f in FAMILIES], seed=seed, allocations=ALLOCATIONS
    )
    family_roles = {r["family"]: r["split"] for r in base.manifest()["items"]}
    items, jobs = [], []
    for split, count in counts.items():
        families = sorted(f for f, role in family_roles.items() if role == split)
        for index in range(count):
            family, construction_seed = (
                families[index % len(families)],
                index // len(families),
            )
            ident = digest([family, construction_seed, "pillow-lines-v2"])[:32]
            items.append({"id": ident, "family": family})
            jobs.append(
                {
                    "id": ident,
                    "family": family,
                    "seed": construction_seed,
                    "split": split,
                }
            )
    frozen = freeze(items, seed=seed, allocations=ALLOCATIONS)
    return frozen, jobs


def write_diagram(root, job, result):
    private = root / "private" / job["id"]
    private.mkdir()
    public = root / "public" / job["id"]
    public.mkdir()
    (private / "truth.json.gz").write_bytes(
        gzip.compress(result.truth.payload.encode(), mtime=0)
    )
    (private / "record.json").write_text(result.record.to_json())
    (private / "render.json").write_text(
        json.dumps(result.render, sort_keys=True, separators=(",", ":"))
    )
    (public / "image.png").write_bytes(result.png)
    data = result.record.to_dict()
    return {
        **job,
        "control": result.render["control"],
        "truth_sha256": result.truth.sha256,
        "image_sha256": hashlib.sha256(result.png).hexdigest(),
        "record_sha256": hashlib.sha256(result.record.to_json().encode()).hexdigest(),
        "render_sha256": digest(result.render),
        "content_hash": data["content_hash"],
        "math_coordinates_sha256": result.truth.data()["math_coordinates_sha256"],
    }


def build_corpus(
    output, *, counts=None, seed="mve-family-split-v1", code_sha, progress=None
):
    counts = dict(DEFAULT_COUNTS if counts is None else counts)
    frozen, jobs = layout(counts, seed)
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    (root / "private").mkdir()
    (root / "public").mkdir()
    (root / "private/split.json").write_text(frozen.payload)
    classes, controls, items = Counter(), Counter(), []
    for index, job in enumerate(jobs):
        split = (
            job["split"]
            if job["split"] in {"fit", "calibration", "evaluation"}
            else "sealed"
        )
        result = generate(job["family"], job["seed"], split=split, code_sha=code_sha)
        items.append(write_diagram(root, job, result))
        classes.update(row["class"] for row in result.truth.data()["candidates"])
        controls.update([job["split"] + ":" + result.render["control"]])
        if progress is not None:
            progress(index + 1, len(jobs))
    report = corpus_report(counts, frozen, items, classes, controls, code_sha)
    (root / "private/manifest.json").write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":"))
    )
    return report


def corpus_report(counts, frozen, items, classes, controls, code_sha):
    unique_math = {
        role: len({r["math_coordinates_sha256"] for r in items if r["split"] == role})
        for role in counts
    }
    unique_images = {
        role: len({r["image_sha256"] for r in items if r["split"] == role})
        for role in counts
    }
    image_roles = {}
    for row in items:
        image_roles.setdefault(row["image_sha256"], set()).add(row["split"])
    cross_split_images = sum(len(roles) > 1 for roles in image_roles.values())
    controls_complete = all(
        controls[role + ":" + tag] for role in ("fit", "evaluation") for tag in CONTROLS
    )
    accepted = (
        unique_math["fit"] >= 2000
        and unique_math["evaluation"] >= 500
        and unique_images["fit"] >= 2000
        and unique_images["evaluation"] >= 500
        and cross_split_images == 0
        and controls_complete
    )
    return {
        "schema": "mve-corpus-v1",
        "counts": counts,
        "unique_mathematical_diagrams": unique_math,
        "unique_rendered_images": unique_images,
        "cross_split_image_collisions": cross_split_images,
        "split_sha256": frozen.sha256,
        "code_sha": code_sha,
        "controls": dict(controls),
        "class_counts": dict(classes),
        "items": items,
        "styles": ["thin"],
        "render_pinned": False,
        "hosted_calls": 0,
        "api_cost_usd": 0,
        "acceptance": "generated_counts_met" if accepted else "fixture_only",
        "ddar_note": "All DDAR receipts unsupported until a local backend passes preflight; no consequence claims.",
    }
