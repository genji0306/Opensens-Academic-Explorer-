"""Mathematical identity excludes render bytes and proof-refinement evidence."""

import hashlib
import json
from mve.errors import RecordError
from mve.predicates import canonical_proposition


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def canonical_problem(data):
    problem = data["problem"]
    mapping = {b["entity"]: b["name"] for b in problem["binders"] if b.get("entity")}
    result = {
        "binders": sorted(
            [{"name": b["name"], "type": b["type"]} for b in problem["binders"]],
            key=lambda b: b["name"],
        )
    }
    for name in ("premises", "nondegeneracy"):
        props = [
            canonical_proposition(p["proposition"], mapping) for p in problem[name]
        ]
        result[name] = sorted(props, key=lambda p: json.dumps(p, sort_keys=True))
    goal = problem["goal"]
    result["goal"] = (
        None
        if goal is None
        else {
            "kind": goal["kind"],
            "proposition": canonical_proposition(goal["proposition"], mapping),
        }
    )
    return result


def canonical_projection(data):
    base = {
        "predicate_registry": data["versions"]["predicate_registry"],
        "problem": canonical_problem(data),
    }
    if not data["image"]["source"].startswith("synthetic:"):
        return dict(base, image_sha256=data["image"]["sha256"])
    truth = data["image"].get("truth")
    if not truth:
        raise RecordError("synthetic mathematical identity needs truth inputs")
    sources = {s["id"]: s for s in data["sources"]}
    source = sources.get(truth["source"], {})
    generator = source.get("generator") or {}
    required = ("id", "version", "config_sha256", "seed", "evaluator_version")
    if source.get("kind") != "truth_artifact" or any(
        k not in generator for k in required
    ):
        raise RecordError("missing synthetic identity inputs")
    return dict(
        base,
        generator={k: generator[k] for k in required},
        candidate_universe_sha256=truth["candidate_universe_sha256"],
        math_coordinates_sha256=truth["math_coordinates_sha256"],
    )


def content_hash(data):
    return digest(canonical_projection(data))


def execution_hash(data):
    p = data["provenance"]
    return digest(
        [
            data["content_hash"],
            p["perceiver_model"],
            p["prompt_sha256"],
            p["request_nonce"],
        ]
    )
