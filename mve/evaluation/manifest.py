"""Bind frozen splits, scorer code, gold keys and controls before opening results."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from mve.evaluation import scoring
from mve.evaluation.splits import canonical, digest

CONTROLS = (
    "exact_positive",
    "adversarial_negative",
    "near_miss_negative",
    "weakened_statement",
    "strengthened_statement",
    "unchanged_round_trip",
)


class ManifestError(ValueError):
    pass


def scorer_sha256():
    return hashlib.sha256(Path(scoring.__file__).read_bytes()).hexdigest()


def validate_controls(controls):
    if not isinstance(controls, dict) or set(controls) != set(CONTROLS):
        raise ManifestError("all six control categories must be frozen")
    for item in controls.values():
        if not isinstance(item, dict) or set(item) != {"fixture_id", "sha256"}:
            raise ManifestError("control id and content hash required")
        if not isinstance(item["fixture_id"], str) or not item["fixture_id"]:
            raise ManifestError("nonempty control fixture id required")
        if not isinstance(item["sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", item["sha256"]
        ):
            raise ManifestError("invalid control hash")


def validate_manifest(data):
    required = {
        "schema",
        "split_sha256",
        "gold_sha256",
        "scorer_sha256",
        "task",
        "mode",
        "model_revision",
        "controls",
    }
    if (
        not isinstance(data, dict)
        or set(data) != required
        or data["schema"] != "mve-evaluation-v1"
    ):
        raise ManifestError("invalid evaluation manifest")
    validate_controls(data["controls"])
    for name in ("split_sha256", "gold_sha256", "scorer_sha256"):
        if not isinstance(data[name], str) or not re.fullmatch(
            r"[0-9a-f]{64}", data[name]
        ):
            raise ManifestError("invalid provenance hash")
    if data["task"] not in scoring.TASKS or data["mode"] not in {
        "query_set",
        "full_record",
    }:
        raise ManifestError("invalid task or scorer mode")
    if not isinstance(data["model_revision"], str) or not data["model_revision"]:
        raise ManifestError("model revision required")


@dataclass(frozen=True)
class FrozenEvaluation:
    payload: str

    def __post_init__(self):
        try:
            validate_manifest(json.loads(self.payload))
        except (TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ManifestError("invalid evaluation payload") from exc

    @property
    def sha256(self):
        return digest(self.payload)

    @classmethod
    def create(cls, split, gold, *, controls, task, mode, model_revision):
        split.require_evaluation()
        validate_controls(controls)
        scoring.validate(gold, {}, mode, task)
        expected = {
            r["id"] for r in split.manifest()["items"] if r["split"] == "evaluation"
        }
        if set(gold) != expected:
            raise ManifestError(
                "gold must cover exactly the frozen evaluation diagrams"
            )
        if not isinstance(model_revision, str) or not model_revision:
            raise ManifestError("pinned model or fixture revision required")
        data = {
            "schema": "mve-evaluation-v1",
            "split_sha256": split.sha256,
            "gold_sha256": digest(canonical(gold)),
            "scorer_sha256": scorer_sha256(),
            "task": task,
            "mode": mode,
            "model_revision": model_revision,
            "controls": controls,
        }
        return cls(canonical(data))

    @classmethod
    def load(cls, payload, *, expected_sha256):
        if digest(payload) != expected_sha256:
            raise ManifestError("evaluation manifest hash mismatch")
        return cls(payload)

    def score(self, split, gold, predictions):
        split.require_evaluation()
        data = json.loads(self.payload)
        if data["split_sha256"] != split.sha256 or data["gold_sha256"] != digest(
            canonical(gold)
        ):
            raise ManifestError("frozen split or gold changed")
        if data["scorer_sha256"] != scorer_sha256():
            raise ManifestError("scorer code changed after freeze")
        report = scoring.score(gold, predictions, mode=data["mode"], task=data["task"])
        return {**report, **data, "manifest_sha256": self.sha256}
