"""Immutable card specifications, revision-bound evidence and GO1 slot accounting.

Historical H0/H1 cards are archival examples, not prospective gate inputs. Their
replacement machine rule is explicitly retrospective; the invalid original is retained.
"""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from mve.errors import RecordError
from mve.graph import downstream, validate_graph
from mve.record import _unique
from mve.validation import require

SPEC_FIELDS = (
    "claim",
    "testable_form",
    "prediction",
    "primary_statistic",
    "kill_criterion",
    "check_spec",
    "sources",
    "observer",
    "resemblance_target",
)
SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[2] / "schemas/mve_hypothesis_card.json"
    ).read_text()
)
VALIDATOR = Draft202012Validator(SCHEMA)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def spec_hash(spec):
    return digest({k: v for k, v in spec.items() if k != "spec_sha256"})


def card_hash(data):
    return digest({k: data[k] for k in SPEC_FIELDS})


def binding(data):
    return {k: data[k] for k in ("card_id", "revision", "content_hash")}


def root_id(data):
    return f"{data['card_id']}@{data['revision']}:{data['content_hash']}"


def check_rule(rule):
    components = rule["components"]
    require(all(0 < c["alpha"] < 1 for c in components), "invalid component alpha")
    require(
        len({c["statistic"] for c in components}) == len(components),
        "duplicate kill component",
    )
    require(
        sum(c["alpha"] for c in components) <= rule["overall_alpha"] + 1e-15,
        "kill rule exceeds overall alpha",
    )
    require(
        (rule["method"] == "primary" and len(components) == 1)
        or (rule["method"] == "bonferroni" and len(components) == 2),
        "one declared kill rule required",
    )


def validate(data):
    try:
        json.dumps(data, allow_nan=False)
        errors = list(VALIDATOR.iter_errors(data))
        require(not errors, f"schema: {errors[0].message}" if errors else "")
        require(
            [b["revision"] for b in data["history"]]
            == list(range(1, data["revision"])),
            "noncontiguous card history",
        )
        require(
            all(b["card_id"] == data["card_id"] for b in data["history"]),
            "history lineage mismatch",
        )
        spec = data["check_spec"]
        check_rule(spec["kill_rule"])
        require(data["kill_criterion"] == spec["kill_rule"], "conflicting kill rules")
        require(spec["alpha"] == spec["kill_rule"]["overall_alpha"], "alpha mismatch")
        require(spec["spec_sha256"] == spec_hash(spec), "spec hash mismatch")
        require(data["content_hash"] == card_hash(data), "content hash mismatch")
        lo, hi = spec["fitting_interval"]
        require(lo == 0 and hi > lo, "exponent interval must be (0, cutoff]")
        require(
            {b["name"] for b in spec["baselines"] if b["role"] == "primary"}
            >= {"gaudin", "cue"},
            "accepted Gaudin and CUE baselines required",
        )
        require(
            all(
                b["role"] == "secondary"
                for b in spec["baselines"]
                if b["name"] == "wigner"
            ),
            "Wigner is secondary",
        )
        for partition in ("development", "replication"):
            require(
                all(b["role"] == partition for b in spec[partition]),
                "partition role mismatch",
            )
        require(
            all(
                len({b["source_block_id"] for b in spec[p]}) == len(spec[p])
                for p in ("development", "replication")
            ),
            "duplicate source block",
        )
        require(
            not (
                {b["source_block_id"] for b in spec["development"]}
                & {b["source_block_id"] for b in spec["replication"]}
            ),
            "overlapping source blocks",
        )
        require(
            not (
                {b["sha256"] for b in spec["development"]}
                & {b["sha256"] for b in spec["replication"]}
            ),
            "reused partition data",
        )
        observer = data["observer"]
        require(
            observer["id"].startswith(observer["kind"] + ":"),
            "observer identity kind mismatch",
        )
        model_fields = {"model_id", "prompt_sha", "call_ids"}
        require(
            model_fields <= set(observer)
            if observer["kind"] == "model"
            else not model_fields & set(observer),
            "human/model origin conflated",
        )
        if any(s["png_sha256"] is None for s in data["sources"]):
            require(
                data["context"]["retrospective"]
                and not data["context"]["original_png_available"]
                and data["context"]["limitations"],
                "missing screenshot provenance",
            )
        graph = {
            root_id(b): {"depends_on": [], "valid": False} for b in data["history"]
        }
        graph[root_id(data)] = {"depends_on": [], "valid": True}
        for node in data["artifacts"] + data["judgments"]:
            require(node["id"] not in graph, "duplicate evidence id")
            graph[node["id"]] = node
        validate_graph(graph)
        for jud in data["judgments"]:
            human = jud["actor"].startswith("human:")
            require(human or jud["actor"].startswith("model:"), "unknown judge kind")
            require(jud["weight"] == (1 if human else 0.5), "judge weight mismatch")
            require(
                jud["verdict"] not in ("adopt", "decline") or human,
                "only human may adopt",
            )
            require(
                root_id(jud) in jud["depends_on"],
                "judgment missing revision dependency",
            )
            if jud["valid"]:
                require(binding(jud) == binding(data), "stale judgment")
        if data["status"] in ("adopted", "handed_off"):
            require(_eligible(data), "current survivor and human adoption required")
        if data["status"] == "checked:baseline_exceeding_survivor":
            require(
                not data["context"]["retrospective"] and _survivor_receipt(data),
                "survival needs current inferential receipt",
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise RecordError(str(exc)) from exc
    return data


def _survivor_receipt(data):
    return any(
        a["valid"]
        and root_id(data) in a["depends_on"]
        and a.get("receipt", {}).get("status") == "baseline_exceeding_survivor"
        and a["receipt"].get("inferential") is True
        and a["receipt"].get("spec_sha256") == data["check_spec"]["spec_sha256"]
        and all(
            a["receipt"].get(k) == data[k]
            for k in ("card_id", "revision", "content_hash")
        )
        for a in data["artifacts"]
    )


def _eligible(data):
    return (
        not data["context"]["retrospective"]
        and _survivor_receipt(data)
        and any(
            j["valid"]
            and j["verdict"] == "adopt"
            and j["actor"].startswith("human:")
            and binding(j) == binding(data)
            for j in data["judgments"]
        )
    )


@dataclass(frozen=True)
class Card:
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

    def handoff_eligible(self):
        d = self.to_dict()
        return d["status"] in (
            "checked:baseline_exceeding_survivor",
            "adopted",
        ) and _eligible(d)

    def revise(self, changes, *, expected_revision):
        d = self.to_dict()
        require(d["revision"] == expected_revision, "stale revision")
        require(
            bool(changes) and set(changes) <= set(SPEC_FIELDS),
            "edit specification fields only",
        )
        old_root = root_id(d)
        d["history"].append(binding(d))
        d.update(deepcopy(changes))
        d["check_spec"]["spec_sha256"] = spec_hash(d["check_spec"])
        d["content_hash"] = card_hash(d)
        require(
            d["content_hash"] != d["history"][-1]["content_hash"],
            "empty specification edit",
        )
        graph = {n["id"]: n for n in d["artifacts"] + d["judgments"]}
        invalid = downstream(graph, [old_root])
        for ident in invalid:
            graph[ident]["valid"] = False
        d["revision"] += 1
        d["status"] = "draft"
        return Card.from_dict(d)

    def transition(self, status, *, receipt=None):
        d = self.to_dict()
        old = d["status"]
        allowed = {
            "draft": ["well_formed"],
            "well_formed": ["frozen"],
            "frozen": ["preliminary"],
            "checked:baseline_exceeding_survivor": ["adopted"],
            "adopted": ["handed_off"],
        }
        if old == "preliminary" and status.startswith("checked:"):
            require(
                receipt is not None
                and receipt.get("status") == status.split(":")[1]
                and receipt.get("spec_sha256") == d["check_spec"]["spec_sha256"]
                and all(
                    receipt.get(k) == d[k]
                    for k in ("card_id", "revision", "content_hash")
                ),
                "check receipt mismatch",
            )
            require(
                receipt["status"] in ("inconclusive", "not_checkable")
                or receipt.get("inferential") is True,
                "nominal result cannot decide a checked outcome",
            )
            d["artifacts"].append(
                dict(
                    id=f"check_{len(d['artifacts'])+1}",
                    depends_on=[root_id(d)],
                    valid=True,
                    receipt=deepcopy(receipt),
                )
            )
        elif old == "handed_off" and status.startswith("lane_verdict:"):
            require(receipt is not None, "lane receipt required")
            d["artifacts"].append(
                dict(
                    id=f"lane_{len(d['artifacts'])+1}",
                    depends_on=[root_id(d)],
                    valid=True,
                    receipt=deepcopy(receipt),
                )
            )
        elif old.startswith("lane_verdict:") and status == "reported":
            pass
        else:
            require(status in allowed.get(old, []), "invalid lifecycle transition")
        d["status"] = status
        return Card.from_dict(d)

    def judge(self, actor, verdict):
        d = self.to_dict()
        d["judgments"].append(
            dict(
                id=f"jud_{len(d['judgments'])+1}",
                **binding(d),
                actor=actor,
                verdict=verdict,
                weight=1 if actor.startswith("human:") else 0.5,
                depends_on=[root_id(d)],
                valid=True,
            )
        )
        return Card.from_dict(d)


def go1(replies, *, slots_per_view, human_checkable=()):
    """Each view lists attempted slot replies; missing/refused/invalid slots stay failures.

    Checkability is a human assessment keyed by (card_id, revision, content_hash).
    Transport retries replace a reply, never add a view or slots.
    """
    require(
        isinstance(slots_per_view, int) and slots_per_view > 0,
        "positive slot count required",
    )
    result = {}
    for observer, views in replies.items():
        good = checkable = 0
        for view in views:
            require(len(view) <= slots_per_view, "too many slot replies")
            for reply in view:
                try:
                    card = (
                        Card.from_json(reply)
                        if isinstance(reply, str)
                        else Card.from_dict(reply)
                    )
                except (RecordError, ValueError):
                    continue
                d = card.to_dict()
                if d["observer"]["id"] != observer:
                    continue
                good += 1
                checkable += tuple(binding(d).values()) in human_checkable
        n = len(views) * slots_per_view
        result[observer] = dict(
            requested=n,
            well_formed=good,
            data_checkable=checkable,
            well_formed_rate=good / n if n else None,
            checkable_rate=checkable / n if n else None,
            passed=bool(n and good / n >= 0.9 and checkable / n >= 0.5),
        )
    return result
