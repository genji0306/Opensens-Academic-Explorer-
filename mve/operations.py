"""Operation permissions, append-only evidence and invalidating edits."""

from copy import deepcopy
from mve.graph import nodes, downstream
from mve.identity import content_hash, execution_hash
from mve.patch import apply_patch, tokens
from mve.validation import require, active

PERMISSIONS = {
    "propose": ("human:", "model:"),
    "perceive": ("A1",),
    "measure": ("A2",),
    "derive": ("A2c",),
    "judge": ("human:", "model:", "audit:"),
    "adopt": ("human:", "policy:"),
    "decide": ("A3",),
    "formalize": ("A4",),
    "prove": ("A5",),
    "edit": ("human:",),
    "review": ("Opus", "Sol", "human:"),
    "ingest": ("A7",),
}
KINDS = {
    "propose": "proposed",
    "perceive": "perceived",
    "measure": "measured",
    "derive": "derived",
    "judge": "judged",
    "adopt": "assumed",
    "decide": "decided",
    "formalize": "formalized",
    "prove": "proved",
    "edit": "edited",
    "review": "reviewed",
    "ingest": "ingested",
}
COLLECTION = {
    "propose": "candidates",
    "perceive": "observations",
    "measure": "measurements",
    "derive": "derivations",
    "judge": "judgments",
    "adopt": "assumptions",
    "decide": "decisions",
    "review": "judgments",
}


def permitted(operation, actor):
    return any(
        actor.startswith(p) if p.endswith(":") else actor == p
        for p in PERMISSIONS.get(operation, ())
    )


def check_operation(data, operation, actor, payload):
    require(permitted(operation, actor), "actor not authorized for operation")
    check_payload(operation, payload)
    require(
        data["stage"] != "ingested_atlas",
        "ingested atlas record is frozen; create lineage record",
    )
    if operation == "perceive":
        require(
            data["stage"] in ("ingested", "ground_truth"),
            "re-perception requires human invalidating edit",
        )
    if operation == "measure":
        require(
            data["stage"] in ("perceived", "ground_truth"),
            "measurement stage precondition",
        )
    if operation == "derive":
        require(
            data["problem"]["premises"] or data["assumptions"],
            "derivation needs premises",
        )
    if operation == "prove":
        require(
            data["formal"]["status"] in ("typechecked", "proof_attempted"),
            "prove requires typecheck",
        )
    if operation == "review":
        negative = any(
            active(d)
            and d["outcome"] in ("unknown", "unsupported", "timeout", "counterexample")
            for d in data["derivations"]
        )
        require(
            data["formal"]["status"]
            in ("typechecked", "proved", "counterexample", "unsupported")
            or negative,
            "review requires formal status or explicit negative result",
        )
    if operation == "ingest":
        require(data["stage"] == "reviewed", "ingest requires review")
    check_owner(operation, actor, payload)


def check_owner(operation, actor, payload):
    if operation in ("judge", "adopt", "review", "propose"):
        for node in payload.get(COLLECTION[operation], []):
            owner_field = {"adopt": "adopted_by", "propose": "proposed_by"}.get(
                operation, "judge"
            )
            owner = node.get(owner_field)
            expected = actor if actor not in ("Opus", "Sol") else f"audit:{actor}"
            require(owner == expected, "actor cannot impersonate evidence owner")
            if operation == "review":
                require(node["question"] == "review", "review question required")


def edit(data, payload, actor):
    patch = checked_patch(payload)
    previous = nodes(data)
    updated = apply_patch(data, patch)
    current = nodes(updated)
    require(
        previous.keys() == current.keys(),
        "edit cannot add/remove addressable nodes; use append operations",
    )

    def snapshot(node):
        return {k: v for k, v in node.items() if k != "geometries"}

    roots = {
        key for key in previous if snapshot(previous[key]) != snapshot(current[key])
    }
    if data["problem"]["binders"] != updated["problem"]["binders"]:
        roots |= {
            key for key in previous if key.startswith(("prm_", "ndg_", "goal_", "ent_"))
        }
    for key in roots:
        for owner in ("judge", "proposed_by", "adopted_by"):
            if owner in previous[key]:
                require(
                    previous[key][owner] == current[key].get(owner),
                    "edit cannot rewrite evidence owner",
                )
                if owner != "adopted_by":
                    require(
                        actor == previous[key][owner],
                        "cannot impersonate original owner; append an override",
                    )
    invalid = downstream(previous, roots) | downstream(current, roots)
    for key in invalid:
        current[key]["valid"] = False
    if roots:
        updated["formal"]["status"] = "none"
        updated["stage"] = (
            "ground_truth" if updated["image"].get("truth") else "ingested"
        )
        updated["versions"]["measurement_contract"] = None
    update_edit_identity(data, updated, payload)
    return updated, roots, invalid


def append_evidence(data, operation, payload):
    collection = COLLECTION[operation]
    require(payload.get(collection), "operation requires evidence to append")
    data.setdefault(collection, []).extend(deepcopy(payload[collection]))
    if operation == "perceive":
        data["entities"].extend(deepcopy(payload.get("entities", [])))
    for entity_id, geometries in payload.get("geometries", {}).items():
        require(
            operation in ("perceive", "measure"),
            "geometry writes belong to perception or measurement",
        )
        entity = next((e for e in data["entities"] if e["id"] == entity_id), None)
        require(entity is not None, "unknown geometry owner")
        entity["geometries"].extend(deepcopy(geometries))
    if operation == "perceive":
        require("provenance" in payload, "perception needs execution provenance")
        data["provenance"] = deepcopy(payload["provenance"])
        data["record_id"] = execution_hash(data)
        data["stage"] = "perceived"
    if operation == "measure":
        data["versions"]["measurement_contract"] = payload.get("measurement_contract")
        data["stage"] = "measured"
    if operation == "derive":
        data["stage"] = "derived"
    if operation == "review":
        data["stage"] = "reviewed"
    return {n["id"] for n in payload[collection]}


def formal_operation(data, operation, payload):
    if operation == "formalize":
        new = deepcopy(payload["formal"])
        old = data["formal"]
        require(
            old["status"] in ("none", "unsupported", "emitted"),
            "formal changes require invalidating edit",
        )
        require(
            new["status"] in ("none", "unsupported", "emitted", "typechecked"),
            "illegal formalization status",
        )
        if new["status"] == "typechecked":
            require(old["status"] == "emitted", "typecheck follows emission")
            require(
                new.get("statement_sha256") == old.get("statement_sha256")
                and new["propositions"] == old["propositions"],
                "typecheck cannot change accepted statement",
            )
        data["formal"] = new
        for key in ("lean_lock_sha", "lean_toolchain"):
            data["versions"][key] = payload.get(key, data["versions"].get(key))
        if new["status"] not in ("none", "unsupported"):
            data["stage"] = "formalized"
    elif operation == "prove":
        data["formal"]["proof"] = deepcopy(payload["proof"])
        data["formal"]["status"] = payload.get("status", "proof_attempted")
        require(
            data["formal"]["status"] in ("proof_attempted", "proved"),
            "illegal proof status",
        )
        if data["formal"]["status"] == "proved":
            data["stage"] = "proved"
    else:
        data["stage"] = "ingested_atlas"
    return (
        {p["id"] for p in data["formal"]["propositions"]}
        if operation == "formalize"
        else set()
    )


def check_payload(operation, payload):
    fields = {
        "edit": {"patch", "request_nonce"},
        "formalize": {"formal", "lean_lock_sha", "lean_toolchain"},
        "prove": {"proof", "status"},
        "ingest": set(),
    }
    allowed = fields.get(
        operation,
        {
            COLLECTION.get(operation, ""),
            "geometries",
            "provenance",
            "measurement_contract",
        },
    )
    if operation == "perceive":
        allowed = allowed | {"entities"}
    require(set(payload) <= allowed, "unknown operation payload field")


def checked_patch(payload):
    patch = payload.get("patch")
    require(isinstance(patch, list) and patch, "edit requires nonempty RFC 6902 patch")
    allowed = {
        "sources",
        "candidates",
        "problem",
        "entities",
        "observations",
        "measurements",
        "derivations",
        "assumptions",
        "judgments",
        "decisions",
    }
    for item in patch:
        for field in ("path", "from"):
            if field not in item:
                continue
            parts = tokens(item[field])
            require(
                parts[0] in allowed and "id" not in parts and "valid" not in parts,
                "edit cannot rewrite identity, validity, artifacts or history",
            )
    return patch


def update_edit_identity(data, updated, payload):
    new_content = content_hash(updated)
    if new_content != data["content_hash"]:
        require(
            payload.get("request_nonce")
            and payload["request_nonce"] != data["provenance"]["request_nonce"],
            "mathematical edit needs a new execution nonce",
        )
        updated["lineage"] = {
            "parent_record_id": data["record_id"],
            "reason": "problem_edit"
            if data["problem"] != updated["problem"]
            else "truth_identity_edit",
        }
        updated["content_hash"] = new_content
        updated["provenance"]["request_nonce"] = payload["request_nonce"]
        updated["record_id"] = execution_hash(updated)
