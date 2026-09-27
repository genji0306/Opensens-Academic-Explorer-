"""Offline C4/C5 staging. No exchange/atlas destination or relay implementation."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from jsonschema import Draft202012Validator, ValidationError
from mve.observer.card import Card, binding
from mve.observer import storage
from mve.observer.snapshots import inside, sha256

SCHEMA_SHA = "ca53b079ce0323b628b292ace76fd822ec804da3c138290bfd449c3ecec7c041"
SCHEMA_PATH = Path(__file__).with_name("vendor") / "atlas-result.schema.json"
MAPPING = {
    "baseline_exceeding_survivor": "proposal",
    "killed": "refuted_candidate",
    "refuted": "refuted_candidate",
    "supported": "completed",
    "baseline_explained": "completed",
    "replicated_observation": "completed",
    "inconclusive": "inconclusive",
    "not_checkable": "inconclusive",
}


def proposal_status():
    return "proposal pending atlas-owner confirmation (Q5)"


def packet_hash(payload):
    # Byte-for-byte canonicalization used by agent_review_protocol.py.
    body = {k: v for k, v in payload.items() if k != "packet_hash"}
    return hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def validate_bundle(bundle, root):
    if sha256(SCHEMA_PATH) != SCHEMA_SHA:
        raise ValueError("vendored atlas schema hash changed")
    try:
        Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(bundle)
    except ValidationError as exc:
        raise ValueError("atlas result schema mismatch") from exc
    storage.encoded(bundle)
    if bundle["status"] == "technical_failure":
        raise ValueError(
            "technical_failure held: services.py:229 defect; Q5 unanswered"
        )
    if bundle["review"] != {
        "state": "unreviewed",
        "reviewerId": None,
        "reviewedRevision": None,
    }:
        raise ValueError("bundle must arrive unreviewed")
    for ref in bundle["sources"] + bundle["artifacts"]:
        if ref["path"].startswith("~"):
            raise ValueError("unsafe relative path")
        path = inside(root, ref["path"])
        if not path.is_file() or sha256(path) != ref["sha256"]:
            raise ValueError("artifact/source missing or hash mismatch")
    return bundle


def relay(owner_questions):
    missing = [q for q in ("Q3", "Q4", "Q5") if not owner_questions.get(q)]
    raise ValueError(
        "relay disabled in offline packet; "
        + (
            "owner " + ",".join(missing) + " unanswered"
            if missing
            else "Opus relays after review"
        )
    )


class Outbox:
    @property
    def root(self):
        return storage.local(storage.OUTBOX)

    def result(self, card, *, run_id, reproduce, outcome=None, lane_receipt=None):
        storage.token(run_id)
        d = Card.from_dict(card.to_dict()).to_dict()
        current = d["status"].split(":")[-1]
        if current in ("adopted", "handed_off"):
            current = "baseline_exceeding_survivor"
        outcome = outcome or current
        if outcome == "technical_failure":
            raise ValueError(
                "technical_failure held: services.py:229 defect; Q5 unanswered"
            )
        if outcome not in MAPPING:
            raise ValueError("no proposed status mapping for outcome")
        if outcome != current and (
            not isinstance(lane_receipt, dict)
            or lane_receipt.get("status") != outcome
            or any(lane_receipt.get(k) != v for k, v in binding(d).items())
        ):
            raise ValueError(
                "changed outcome needs a current revision-bound lane receipt"
            )
        if outcome == "baseline_exceeding_survivor" and not (
            card.handoff_eligible() or d["status"] == "handed_off"
        ):
            raise ValueError("proposal requires adopted current survivor")
        limitations = list(d["context"]["limitations"]) + [
            proposal_status(),
            "Novelty: " + d["novelty"]["status"],
            "Outbox draft; atlas owner must copy artifacts preserving relative paths.",
        ]
        if outcome == "baseline_explained":
            limitations.append(
                "explained by the declared baseline; known or explained pattern, never a new-lane proposal"
            )
        if outcome == "replicated_observation":
            limitations.append(
                "replication observed; baseline specificity undecided; never a new-lane proposal"
            )
        artifact = f"artifacts/{run_id}/card.json"
        data = storage.encoded(d)
        ref = {"path": artifact, "sha256": hashlib.sha256(data).hexdigest()}
        bundle = dict(
            runId=run_id,
            taskId="mve-card-" + d["card_id"],
            statement=d["claim"],
            method="MVE frozen two-stage source-data check; lane outcome: " + outcome,
            reproduce=reproduce,
            schemaVersion="1.0",
            status=MAPPING[outcome],
            assumptions=[],
            sources=[
                {
                    **ref,
                    "locator": f"{d['card_id']}@{d['revision']}:{d['content_hash']}",
                }
            ],
            artifacts=[ref],
            results=[
                {
                    "card_status": d["status"],
                    "outcome": outcome,
                    "novelty": d["novelty"],
                    "lane_receipt": lane_receipt,
                }
            ],
            counterexamples=[],
            limitations=limitations,
            proposedBlockerChanges=[],
            resources={"hosted_calls": 0},
            review={
                "state": "unreviewed",
                "reviewerId": None,
                "reviewedRevision": None,
            },
        )
        with storage.lock():
            root = self.root / "atlas"
            target = storage.OUTBOX / "atlas" / "inbox" / (run_id + ".json")
            if storage.local(target).exists():
                raise FileExistsError("immutable runId already in outbox")
            # Validate shape before any artifact write. Full adapter checks after bytes exist.
            if sha256(SCHEMA_PATH) != SCHEMA_SHA:
                raise ValueError("vendored atlas schema hash changed")
            try:
                Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(
                    bundle
                )
            except ValidationError as exc:
                raise ValueError("atlas result schema mismatch") from exc
            storage.disk_guard(
                storage.local(storage.GENERATED),
                len(data) + len(storage.encoded(bundle)),
            )
            storage.write(storage.OUTBOX / "atlas" / artifact, data)
            validate_bundle(bundle, root)
            return storage.write(target, bundle)

    def submission(self, card, *, reviewer, commit, submitted_at):
        card = Card.from_dict(card.to_dict())
        if not card.handoff_eligible():
            raise ValueError("current survivor and human adoption required")
        storage.token(reviewer)
        if not re.fullmatch("[0-9a-f]{40}", commit):
            raise ValueError("full commit sha required")
        if datetime.fromisoformat(submitted_at).tzinfo is None:
            raise ValueError("submission timestamp needs timezone")
        d = card.to_dict()
        work = "mve-card-" + d["card_id"]
        with storage.lock():
            existing = []
            for p in (self.root / "exchange" / "submissions").glob(work + "-r*.json"):
                previous = json.loads(
                    storage.local(p.relative_to(storage.WORKTREE)).read_text()
                )
                if previous["packet_hash"] != packet_hash(previous):
                    raise ValueError("previous packet hash mismatch")
                existing.append(previous)
            existing.sort(key=lambda p: p["round"])
            prior = existing[-1] if existing else None
            if (
                prior
                and (prior["round"] >= d["revision"] or prior["reviewer"] != reviewer)
            ) or (not prior and d["revision"] != 1):
                raise ValueError("stale revision or missing round lineage")
            if prior and d["revision"] != prior["round"] + 1:
                raise ValueError("noncontiguous submission round")
            if prior:
                prior_card = json.loads(
                    storage.local(prior["report_path"]).read_text()
                )["card"]
                if d["history"][-1] != binding(prior_card):
                    raise ValueError("superseding card does not match prior revision")
            rid = f"{work}-r{d['revision']}-{commit[:12]}"
            report_path = storage.OUTBOX / "exchange" / "reports" / (rid + ".json")
            data = storage.encoded(
                {
                    "card": d,
                    "receipts": [
                        a["receipt"]
                        for a in d["artifacts"]
                        if a.get("valid") and "receipt" in a
                    ],
                }
            )
            packet = dict(
                schema_version="oae-agent-review-v1",
                packet_type="attack_lane_proposal",
                review_id=rid,
                work_id=work,
                round=d["revision"],
                submitter="mve",
                reviewer=reviewer,
                commit=commit,
                report_path=report_path.as_posix(),
                report_sha256=hashlib.sha256(data).hexdigest(),
                changed_files=[],
                summary=d["claim"],
                evidence=[f"{d['card_id']}@{d['revision']}:{d['content_hash']}"],
                caveats=[
                    proposal_status(),
                    "Offline outbox draft; report is not yet published at commit; relay requires Q3/Q4/Q5 and Opus review.",
                ],
                supersedes=prior["review_id"] if prior else None,
                relayed_by=None,
                submitted_at=submitted_at,
            )
            packet["packet_hash"] = packet_hash(packet)
            storage.disk_guard(
                storage.local(storage.GENERATED),
                len(data) + len(storage.encoded(packet)),
            )
            storage.write(report_path, data)
            return storage.write(
                storage.OUTBOX / "exchange" / "submissions" / (rid + ".json"), packet
            )
