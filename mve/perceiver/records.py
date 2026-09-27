"""Build observation-only v5 records via the schema and mve.validation semantic checks."""

import hashlib
from mve.record import Record, create, transition
from mve.predicates import canonical_proposition
from mve.perceiver.contract import MODEL, PROMPT_SHA


def ingested(image, nonce, code_sha, at):
    data = {
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
    data.update(
        schema="oae-mve-observation-v5",
        record_id="0" * 64,
        content_hash="0" * 64,
        revision=1,
        stage="ingested",
        lineage={"parent_record_id": None, "reason": None},
        domain="euclidean_plane",
        formal={"status": "none", "propositions": [], "depends_on": []},
        problem={"binders": [], "premises": [], "nondegeneracy": [], "goal": None},
    )
    data["versions"] = {
        "code_sha": code_sha,
        "predicate_registry": "v1",
        "measurement_contract": None,
        "classifier_weights": None,
        "label_set": None,
        "calibration_lock": None,
    }
    data["image"] = image_metadata(image)
    data["provenance"] = {
        "perceiver_model": None,
        "perceiver_calls": 0,
        "prompt_sha256": None,
        "request_nonce": nonce,
        "raw_response_sha256": [],
        "created_at": at,
        "cost_usd": 0,
        "wave_id": "wp3:simulated",
        "cell_id": "offline-fixture:receipt.json",
    }
    return create(data, at)


def merge_entities(calls, alignment):
    entities, maps, geometries = [], [{}, {}], [{}, {}]
    paired = {m["right"]: m["left"] for m in alignment["matches"]}
    for call, content in enumerate(calls):
        for item in content["entities"]:
            existing = maps[0].get(paired.get(item["id"])) if call else None
            if existing is None:
                existing = f"ent_{len(entities)+1}"
                entities.append(
                    {
                        "id": existing,
                        "label": item["label"],
                        "kind": item["kind"],
                        "geometries": [],
                        "depends_on": [],
                        "valid": True,
                    }
                )
            owner = next(e for e in entities if e["id"] == existing)
            gid = f'geo_{sum(len(e["geometries"]) for e in entities)+1}'
            geo = {
                "id": gid,
                "source": f"perceiver_call_{call+1}",
                "frame": "pixel_topleft_xy",
                "params": item["params"],
                "depends_on": [existing],
                "valid": True,
            }
            if "pieces" in item:
                geo["pieces"] = item["pieces"]
            owner["geometries"].append(geo)
            maps[call][item["id"]], geometries[call][item["id"]] = existing, gid
    return entities, maps, geometries


def observations(calls, maps, geometries):
    result = []
    for call, content in enumerate(calls):
        for item in content["entities"]:
            result.append(
                {
                    "id": f"obs_{len(result)+1}",
                    "call": call + 1,
                    "kind": "free_text",
                    "free_text": f"Visible {item['kind']}: {item['label'] or '(unlabelled)'}",
                    "confidence": 0,
                    "depends_on": [geometries[call][item["id"]]],
                    "valid": True,
                }
            )
        for item in content["observations"]:
            prop = item["proposition"]
            result.append(
                {
                    "id": f"obs_{len(result)+1}",
                    "call": call + 1,
                    "kind": "proposition",
                    "proposition": canonical_proposition(prop, maps[call]),
                    "confidence": item["confidence"],
                    "depends_on": sorted({geometries[call][a] for a in prop["args"]}),
                    "valid": True,
                }
            )
    return result


def build_record(base, calls, alignment, selected):
    entities, maps, geometries = merge_entities(calls, alignment)
    provenance = base.to_dict()["provenance"]
    provenance.update(
        perceiver_model=MODEL,
        perceiver_calls=2,
        prompt_sha256=PROMPT_SHA,
        raw_response_sha256=[s["raw_sha256"] for s in selected],
    )
    record = transition(
        base,
        "perceive",
        actor="A1",
        expected_revision=1,
        at=provenance["created_at"],
        payload={
            "entities": entities,
            "observations": observations(calls, maps, geometries),
            "provenance": provenance,
        },
    )
    data = record.to_dict()
    data["events"][-1]["note"] = (
        "Offline replay only. cost_usd is actual hosted spend (0). "
        "Simulated per-image costs including retries are in receipt.json; unknown billing remains unknown."
    )

    return Record.from_dict(data)


def image_metadata(image):
    width, height = image.size()
    return {
        "sha256": hashlib.sha256(image.png).hexdigest(),
        "width": width,
        "height": height,
        "source": "benchmark:wp3-replay:public-image",
        "track": image.track,
        "eval_task": image.task,
        "isolation": {
            "visible": ["labels"]
            if image.track == "appearance_only"
            else ["labels", "stated_givens", "problem_text"],
            "hidden": [
                "generator_premises",
                "truth_classes",
                "answer",
                "reference_paths",
                "consequences",
            ],
        },
    }
