"""v5 schema plus canonical identity, dependency, evidence and stage validation."""

import json
import re
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from mve.errors import RecordError
from mve.graph import nodes, validate_graph
from mve.identity import (
    canonical_projection as canonical_projection,
    content_hash,
    execution_hash,
)
from mve.predicates import canonical_proposition as canonical_proposition
from mve.formal import check_formal
from mve.validation import (
    require,
    active,
    check_problem,
    check_sources,
    check_entities,
    check_observations,
    check_measurements,
    check_adoptions,
    check_judgments,
    check_derivations,
    check_decisions,
)

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[1] / "schemas/mve_observation_record.json"
    ).read_text()
)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def check_stages(data):
    stage = data["stage"]
    p = data["provenance"]
    versions = data["versions"]
    check_versions(versions)
    if p["perceiver_calls"]:
        require(
            p["perceiver_model"] and p["prompt_sha256"], "perception provenance missing"
        )
        require(
            len(p["raw_response_sha256"]) == p["perceiver_calls"],
            "raw response count mismatch",
        )
    else:
        require(not data["observations"], "observations require perceiver calls")
    if stage in ("ground_truth", "ingested"):
        require(
            versions["measurement_contract"] is None,
            "initial stage has no measurement contract",
        )
    if stage == "ground_truth":
        require(data["image"].get("truth"), "ground truth needs truth metadata")
    if stage == "perceived":
        require(
            any(active(o) for o in data["observations"]),
            "perceived requires observations",
        )
    if stage == "measured":
        require(
            versions["measurement_contract"],
            "measured stage requires measurement contract",
        )
    if stage == "derived":
        require(
            any(active(d) for d in data["derivations"]),
            "derived stage requires derivation",
        )
    if stage == "formalized":
        require(data["formal"]["status"] != "none", "formalized stage needs artifact")
    if stage == "proved":
        require(
            data["formal"]["status"] == "proved", "proved stage requires checked proof"
        )
    if stage in ("reviewed", "ingested_atlas"):
        require(
            any(active(j) and j["question"] == "review" for j in data["judgments"]),
            "reviewed stage needs review",
        )


def check_events(data, graph):
    seen = set(graph)
    revision = 0
    for event in data["events"]:
        require(
            event["id"].startswith("evt_") and event["id"] not in seen,
            "duplicate or wrong event id",
        )
        seen.add(event["id"])
        require(
            event["from_revision"] == revision and event["to_revision"] == revision + 1,
            "noncontiguous revision history",
        )
        revision = event["to_revision"]
        require(set(event["touches"]) <= set(graph), "unknown event target")
        require(
            set(event.get("invalidates", [])) <= set(graph),
            "unknown invalidation target",
        )
    require(revision == data["revision"], "history does not reach revision")


def validate(data):
    try:
        json.dumps(data, allow_nan=False)
        errors = list(VALIDATOR.iter_errors(data))
        if errors:
            raise RecordError(f"schema: {errors[0].json_path}: {errors[0].message}")
        graph = nodes(data)
        validate_graph(graph)
        check_sources(data)
        groups = check_problem(data, graph)
        check_entities(data, graph, groups)
        check_observations(data, graph)
        check_measurements(data, graph)
        check_judgments(data, graph)
        check_adoptions(data, graph)
        check_derivations(data, graph)
        check_decisions(data)
        check_formal(data, graph)
        check_stages(data)
        check_events(data, graph)
        require(data["content_hash"] == content_hash(data), "content hash mismatch")
        require(
            data["record_id"] == execution_hash(data), "execution identity mismatch"
        )
    except RecordError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise RecordError(str(exc)) from exc
    return data


def check_versions(versions):
    require(versions["predicate_registry"] == "v1", "unknown predicate registry")
    for key in ("classifier_weights", "label_set", "calibration_lock", "lean_lock_sha"):
        value = versions.get(key)
        require(
            value is None or re.fullmatch(r"[0-9a-f]{64}", value),
            "invalid version artifact hash",
        )
