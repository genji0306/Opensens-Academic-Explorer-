"""Immutable v5 records and optimistic-concurrency operation boundary."""

from dataclasses import dataclass
import json
from mve.errors import RecordError
from mve.identity import content_hash, execution_hash
from mve.operations import (
    check_operation,
    edit,
    append_evidence,
    formal_operation,
    COLLECTION,
    KINDS,
)
from mve.semantics import validate
from mve.validation import require


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RecordError("duplicate JSON object key")
        result[key] = value
    return result


@dataclass(frozen=True)
class Record:
    _json: str

    def __post_init__(self):
        validate(json.loads(self._json, object_pairs_hook=_unique))

    @classmethod
    def from_dict(cls, data):
        try:
            return cls(
                json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
            )
        except (ValueError, TypeError) as exc:
            raise RecordError(str(exc)) from exc

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique))

    def to_dict(self):
        return json.loads(self._json)

    def to_json(self):
        return self._json


def create(data, at):
    data = json.loads(json.dumps(data))
    require(
        data["stage"] in ("ingested", "ground_truth"),
        "create stage must be ingested or ground_truth",
    )
    data["revision"] = 1
    data["content_hash"] = content_hash(data)
    data["record_id"] = execution_hash(data)
    data["events"] = [
        {
            "id": "evt_1",
            "at": at,
            "actor": "ingest",
            "kind": "created",
            "from_revision": 0,
            "to_revision": 1,
            "touches": [],
        }
    ]
    return Record.from_dict(data)


def transition(record, operation, *, actor, expected_revision, at, payload):
    data = record.to_dict()
    require(expected_revision == data["revision"], "stale revision; rebase required")
    check_operation(data, operation, actor, payload)
    try:
        invalid = set()
        if operation == "edit":
            data, touched, invalid = edit(data, payload, actor)
        elif operation in COLLECTION:
            touched = append_evidence(data, operation, payload)
        else:
            touched = formal_operation(data, operation, payload)
        event = {
            "id": f'evt_{max(int(e["id"].split("_")[1]) for e in data["events"])+1}',
            "at": at,
            "actor": actor,
            "kind": KINDS[operation],
            "from_revision": expected_revision,
            "to_revision": expected_revision + 1,
            "touches": sorted(touched),
        }
        if operation == "edit":
            event.update(patch=payload["patch"], invalidates=sorted(invalid))
        data["events"].append(event)
        data["revision"] += 1
        return Record.from_dict(data)
    except RecordError:
        raise
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        raise RecordError(str(exc)) from exc
