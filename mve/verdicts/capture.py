"""Immutable offline verdict API over the existing operation boundary."""

import re
from mve.graph import nodes
from mve.record import Record, transition
from mve.validation import active, require
from mve.predicates import canonical_proposition
from mve.verdicts.catalogue import check_label

TARGETS = ("obs_", "mea_", "der_", "jud_", "can_", "prop_")


def actor_kind(actor):
    require(
        isinstance(actor, str) and re.fullmatch(r"(human|model):[A-Za-z0-9._-]+", actor),
        "explicit human/model actor identity required",
    )
    return actor.split(":", 1)[0]


def next_id(data, prefix):
    return f'{prefix}_{1 + max((int(k.split("_")[1]) for k in nodes(data) if k.startswith(prefix + "_")), default=0)}'


def propose(record, *, proposition, actor, from_revision, at, text=None):
    """Append a non-authorizing candidate; entity edits invalidate it transitively."""
    actor_kind(actor)
    data = record.to_dict()
    prop = canonical_proposition(proposition)
    candidate = {
        "id": next_id(data, "can"),
        "proposition": prop,
        "proposed_by": actor,
        "at": at,
        "text": text,
        "depends_on": sorted(set(prop["args"])),
        "valid": True,
    }
    return transition(
        record,
        "propose",
        actor=actor,
        expected_revision=from_revision,
        at=at,
        payload={"candidates": [candidate]},
    )


def capture(
    record,
    *,
    target,
    verdict,
    actor,
    from_revision,
    at,
    question="visibility",
    label=None,
    rationale=None,
):
    """Capture evidence; human adopt returns both judge and assumption transitions."""
    kind = actor_kind(actor)
    data = record.to_dict()
    graph = nodes(data)
    require(target in graph and target.startswith(TARGETS), "unsupported verdict target")
    require(active(graph[target]), "cannot judge invalidated target")
    judgment = {
        "id": next_id(data, "jud"),
        "judge": actor,
        "target": target,
        "question": question,
        "verdict": verdict,
        "label": label,
        "weight": 1.0 if kind == "human" else 0.5,
        "at": at,
        "rationale": rationale,
        "depends_on": [target],
        "valid": True,
    }
    check_label(judgment, graph)
    result = transition(
        record,
        "judge",
        actor=actor,
        expected_revision=from_revision,
        at=at,
        payload={"judgments": [judgment]},
    )
    return finish(result, judgment)


def finish(record, judgment):
    data = record.to_dict()
    conflicts = [
        j
        for j in data["judgments"]
        if active(j)
        and j["id"] != judgment["id"]
        and j["target"] == judgment["target"]
        and j["question"] == judgment["question"]
        and (j["verdict"], j.get("label")) != (judgment["verdict"], judgment.get("label"))
    ]
    if conflicts:
        data["events"][-1]["note"] = (
            f'label_conflict: {judgment["id"]}; {len(conflicts)} conflicting judgments; '
            'human overrides model; latest revision within actor kind wins'
        )
        record = Record.from_dict(data)
    if judgment["verdict"] != "adopt":
        return record
    target = nodes(data)[judgment["target"]]
    prop = target.get("proposition", target.get("target"))
    require(isinstance(prop, dict), "adoption requires a proposition-bearing target")
    assumption = {
        "id": next_id(data, "asm"),
        "proposition": prop,
        "adopted_by": judgment["judge"],
        "depends_on": [judgment["id"]],
        "valid": True,
    }
    return transition(
        record,
        "adopt",
        actor=judgment["judge"],
        expected_revision=data["revision"],
        at=judgment["at"],
        payload={"assumptions": [assumption]},
    )


def revise(record, *, judgment, verdict, actor, from_revision, at, label=None, rationale=None):
    """Correct one's own human verdict using RFC 6902 and graph invalidation."""
    require(actor_kind(actor) == "human", "only humans edit verdicts")
    data = record.to_dict()
    index = next((i for i, j in enumerate(data["judgments"]) if j["id"] == judgment), None)
    require(index is not None, "unknown judgment")
    previous = data["judgments"][index]
    require(previous["judge"] == actor, "cannot impersonate original judge; append an override")
    require(active(previous), "cannot revise invalidated judgment; judge current evidence")
    changes = dict(verdict=verdict, label=label, rationale=rationale, at=at)
    updated = {**previous, **changes}
    check_label(updated, nodes(data))
    patch = [
        {"op": "add", "path": f"/judgments/{index}/{key}", "value": value}
        for key, value in changes.items()
    ]
    result = transition(
        record,
        "edit",
        actor=actor,
        expected_revision=from_revision,
        at=at,
        payload={"patch": patch},
    )
    return finish(result, updated)
