"""Build v5 truth records; mathematical coordinates stay in out-of-band artifacts."""

import hashlib
from mve.identity import digest
from mve.record import create

AT = "2026-09-27T00:00:00Z"


def source(truth):
    return {
        "id": "geo_999999",
        "kind": "truth_artifact",
        "sha256": truth.sha256,
        "path_hint": None,
        "generator": truth.data()["generator"],
        "depends_on": [],
    }


def empty_record(code_sha, nonce):
    record = {
        key: []
        for key in (
            "sources",
            "entities",
            "observations",
            "measurements",
            "derivations",
            "assumptions",
            "judgments",
            "decisions",
            "events",
        )
    }
    record.update(
        schema="oae-mve-observation-v5",
        record_id="0" * 64,
        content_hash="0" * 64,
        revision=1,
        lineage={"parent_record_id": None, "reason": None},
        stage="ground_truth",
        domain="euclidean_plane",
        formal={"status": "none", "propositions": [], "depends_on": []},
    )
    record["versions"] = {
        "code_sha": code_sha,
        "predicate_registry": "v1",
        "measurement_contract": None,
        "classifier_weights": None,
        "label_set": None,
        "calibration_lock": None,
    }
    record["provenance"] = {
        "perceiver_model": None,
        "perceiver_calls": 0,
        "prompt_sha256": None,
        "request_nonce": nonce,
        "raw_response_sha256": [],
        "created_at": AT,
        "cost_usd": 0,
    }
    return record


def image_record(data, image_hash, family, split):
    return {
        "sha256": image_hash,
        "width": 288,
        "height": 288,
        "source": f'synthetic:mve-inhouse:seed{data["generator"]["seed"]}',
        "track": "appearance_only",
        "eval_task": "appearance",
        "ground_truth_ref": "geo_999999",
        "isolation": {
            "visible": ["labels"],
            "hidden": [
                "generator_premises",
                "truth_classes",
                "answer",
                "reference_paths",
                "consequences",
            ],
        },
        "truth": {
            "source": "geo_999999",
            "split": split,
            "family": family,
            "render_pinned": False,
            "candidate_universe_sha256": data["candidate_universe_sha256"],
            "math_coordinates_sha256": data["math_coordinates_sha256"],
        },
    }


def point_entity(index, name, pixels):
    entity = f"ent_{index}"
    return {
        "id": entity,
        "label": name,
        "kind": "point",
        "depends_on": [],
        "geometries": [
            {
                "id": f"geo_{index}",
                "source": "ground_truth",
                "frame": "pixel_topleft_xy",
                "params": pixels,
                "depends_on": [entity, "geo_999999"],
            }
        ],
    }


def record_from(truth, png, render_metadata, *, family, split="fit", code_sha="0" * 40):
    data = truth.data()
    names = sorted(data["math_coordinates"])
    image_hash = hashlib.sha256(png).hexdigest()
    nonce = digest([data["generator"], image_hash])[:16]
    record = empty_record(code_sha, nonce)
    record["sources"] = [source(truth)]
    record["problem"] = {
        "binders": [
            {"name": name, "type": "Point", "entity": f"ent_{i}"}
            for i, name in enumerate(names, 1)
        ],
        "premises": [],
        "nondegeneracy": [],
        "goal": None,
    }
    record["entities"] = [
        point_entity(i, name, render_metadata["pixels"][name])
        for i, name in enumerate(names, 1)
    ]
    record["image"] = image_record(data, image_hash, family, split)
    return create(record, AT)
