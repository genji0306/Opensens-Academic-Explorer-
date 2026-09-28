"""WO-4 replay runner; reviewed WO-6 live activation delegates to pilot.py."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from mve.errors import RecordError
from mve.money import BudgetError
from mve.observer.card import Card, card_hash, spec_hash, digest, go1
from mve.observer.design import allocate, require
from mve.observer.snapshots import inside, sha256, card_source
from mve.observer.checks.runner import run_stage, combine_stages
from mve.observer.metrics import report
from mve.observer import storage
from mve.observer.dispatch import (
    observe,
    card_request,
    card_prompt,
    reconciliation as reconciliation,
    check_reconciled,
    reserved,
)
from mve.perceiver import Replay
from mve.perceiver.contract import MODEL
from mve.preflight.probe import utc_now, verified_ceiling


def second_model():
    raise ValueError("owner Q2 unanswered")


def human_cards(cards):
    validated = [Card.from_dict(c).to_dict() for c in cards]
    require(
        all(c["observer"]["kind"] == "human" for c in validated),
        "human card API requires human origin",
    )
    origins = {c["observer"]["id"] for c in validated}
    require(len(origins) <= 1, "one human observer per intake")
    observer = next(iter(origins), "human:owner")
    views = [validated[i : i + 3] for i in range(0, len(validated), 3)]
    return {
        "cards": validated,
        "GO1": go1({observer: views}, slots_per_view=3)[observer],
        "GO2": "excluded: owner Q6 unanswered",
    }


def make_card(proposal, *, job, plan, observer, call_ids, slot):
    """Model authors only claim fields; host binds frozen check and provenance."""
    require(
        type(proposal) is dict
        and set(proposal)
        == {"claim", "testable_form", "prediction", "resemblance_target"},
        "malformed card proposal",
    )
    p = plan.to_dict()
    template = deepcopy(p["config"]["checks"][job["family"]])
    entries = {e["snapshot_id"]: e for e in p["manifest"]["snapshots"]}
    blocks = {e["data_ref"]["source_block_id"]: e for e in entries.values()}
    require(
        proposal["testable_form"] == template["testable_form"],
        "proposal changes frozen check mapping",
    )
    template.update(deepcopy(proposal))
    template.update(
        card_id="hyp_" + str(int(digest({"job": job["id"], "slot": slot})[:15], 16)),
        revision=1,
        history=[],
        artifacts=[],
        judgments=[],
        status="draft",
    )
    spec = template["check_spec"]
    for partition, key in (
        ("development", "discovery"),
        ("replication", "replication"),
    ):
        ref = blocks[job[key]]["data_ref"]
        minimum = spec[partition][0]["min_gaps"]
        spec[partition] = [
            dict(
                source_block_id=ref["source_block_id"],
                sha256=ref["sha256"],
                role=partition,
                min_gaps=minimum,
            )
        ]
    spec["seed"] = int(job["id"][:8], 16)
    spec["spec_sha256"] = spec_hash(spec)
    source = (
        entries[job["snapshot_id"]] if job["snapshot_id"] else blocks[job["discovery"]]
    )
    template["sources"] = [card_source(source)]
    template["observer"] = (
        deepcopy(p["config"]["checks"][job["family"]]["observer"])
        if job["arm"] == "image_free"
        else {
            "id": observer,
            "kind": "model",
            "model_id": MODEL,
            "prompt_sha": hashlib.sha256(
                card_prompt(
                    job["family"], p["config"]["checks"][job["family"]]
                ).encode()
            ).hexdigest(),
            "call_ids": call_ids,
            "blinded": True,
        }
    )
    template["observer_reliability"] = "not_established"
    template["novelty"] = {
        "status": "unchecked",
        "queries": [],
        "index_shas": [],
        "planted_control_hit": False,
    }
    template["prior_plausibility"] = {"value": "low", "by": template["observer"]["id"]}
    template["context"] = {
        "retrospective": False,
        "original_png_available": True,
        "limitations": [
            "Offline authored replay; no scientific gate claim.",
            "WO-2 development check field binds cluster discovery, not prompt-development data.",
            "Image-free source PNG is provenance only and is never delivered.",
        ]
        if job["arm"] == "image_free"
        else ["Offline authored replay; no scientific gate claim."],
        "original_kill_rule": None,
        "evidence": [],
    }
    template["content_hash"] = card_hash(template)
    return Card.from_dict(template)


def check_card(card, *, root, blocks):
    frozen = card.transition("well_formed").transition("frozen")

    def loader(block):
        ref = blocks[block["source_block_id"]]["data_ref"]
        path = inside(root, ref["path"])
        require(sha256(path) == block["sha256"], "source bytes changed after freeze")
        raw = json.loads(path.read_text())
        return {**raw, "sha256": ref["sha256"]}

    try:
        first = run_stage(frozen, 1, loader)
        preliminary = frozen.transition("preliminary")
        second = run_stage(preliminary, 2, loader)
        receipt = combine_stages(preliminary, first, second)
        return preliminary.transition(
            "checked:" + receipt["status"], receipt=receipt
        ), True
    except (ValueError, KeyError, OSError, RecordError):
        # No topping up or second check; retain a valid card with failed check slot.
        return frozen, False


def run(
    plan,
    *,
    root,
    ledger,
    reconciled,
    replays,
    run_id,
    observer="model:O-DS",
    clock=utc_now,
):
    if observer == "model:O-M2":
        second_model()
    require(observer == "model:O-DS", "use human_cards for WO-2 human intake")
    storage.token(run_id)
    p = plan.to_dict()
    lock_path = storage.WORKTREE / "mve/DEPS.lock"
    locked = json.loads(lock_path.read_text())["packets"]["WO-4"]
    require(
        p["sha256"] in locked["frozen_design_sha256s"],
        "design must be frozen in DEPS.lock before run",
    )
    try:
        ledger_relative = ledger.path.relative_to(storage.WORKTREE)
    except ValueError:
        raise ValueError(
            "ledger must be inside this worktree generated directory"
        ) from None
    require(storage.local(ledger_relative) == ledger.path, "ledger path mismatch")
    # Recheck frozen allocation and artifact bytes before any dispatch.
    require(allocate(p["manifest"], root, p["config"]).to_dict() == p, "design changed")
    entries = {e["snapshot_id"]: e for e in p["manifest"]["snapshots"]}
    blocks = {e["data_ref"]["source_block_id"]: e for e in entries.values()}
    visual = [j for j in p["jobs"] if j["arm"] != "image_free"]
    require(
        set(replays) == {j["id"] for j in visual},
        "replay must exactly cover fixed visual jobs",
    )
    for value in replays.values():
        require(
            type(value) is tuple
            and len(value) == 2
            and all(type(r) is Replay for r in value),
            "exact local Replay pair required",
        )
    with storage.lock():
        check_reconciled(ledger, reconciled)
        pngs = {
            j["id"]: inside(
                root, entries[j["snapshot_id"]]["png_blinded"]["path"]
            ).read_bytes()
            for j in visual
        }
        for j in visual:
            card_request(
                pngs[j["id"]], j["family"], p["config"]["checks"][j["family"]]
            ).validate()
        _, ceiling = verified_ceiling(
            ledger,
            card_request(
                pngs[visual[0]["id"]],
                visual[0]["family"],
                p["config"]["checks"][visual[0]["family"]],
            ),
        )
        count = len(visual) * 3 * (1 + p["config"]["retries"])
        worst = count * ceiling
        require(
            worst <= 250000,
            "worst-case P1 reservation exceeds USD 0.25; refreeze smaller design before run",
        )
        snap = ledger.snapshot()
        phase = sum(
            (a["actual"] if a["state"] == "settled" else a["reserved"])
            for a in snap["attempts"]
            if a["phase"] == "P1" and a["state"] != "cancelled"
        )
        require(
            worst <= reconciled["remaining_micro_usd"]
            and phase + worst <= snap["configuration"]["caps"]["P1"],
            "worst-case exceeds remaining campaign/P1 budget",
        )
        # WP-3 writes bounded request/raw/PNG receipts. Admit their entire upper bound.
        incoming = sum(
            6 * (1 + p["config"]["retries"]) * len(pngs[j["id"]])
            + 12
            * sum(
                len(e.raw)
                for replay in replays[j["id"]]
                for e in replay.entries
                if hasattr(e, "raw")
            )
            + 512 * 1024
            for j in visual
        )
        storage.disk_guard(storage.local(storage.GENERATED), incoming)
        relative = storage.GENERATED / "observer-runs" / run_id
        output = storage.local(relative)
        require(not output.exists(), "immutable run directory already exists")
        storage.write(relative / "design.json", p)
        storage.write(relative / "reconciliation.json", reconciled)
        rows = []
        with reserved(
            ledger, count=count, ceiling=ceiling, run_id=run_id, clock=clock
        ) as guarded:
            for job in p["jobs"]:
                calls = []
                status = "ok"
                if job["arm"] == "image_free":
                    start = job["view"] * 3
                    proposals = p["config"]["image_free"][job["family"]][
                        start : start + 3
                    ]
                elif ledger.snapshot()["frozen"]:
                    proposals, status = [], "ledger_frozen"
                else:
                    nonce = digest({"run": run_id, "job": job["id"]})[:16]
                    try:
                        proposals, calls, status = observe(
                            guarded,
                            png=pngs[job["id"]],
                            family=job["family"],
                            template=p["config"]["checks"][job["family"]],
                            replay=replays[job["id"]],
                            output=output / job["id"],
                            nonce=nonce,
                            retries=p["config"]["retries"],
                            clock=clock,
                        )
                    except storage.DiskLimitError:
                        raise
                    except (BudgetError, ValueError, OSError):
                        proposals, status = [], "dispatch_failed"
                for slot in range(3):
                    card, checkable = None, False
                    slot_status = status if status != "ok" else "empty"
                    if slot < len(proposals):
                        try:
                            card = make_card(
                                proposals[slot],
                                job=job,
                                plan=plan,
                                observer=observer,
                                call_ids=calls,
                                slot=slot,
                            )
                            card, checkable = check_card(card, root=root, blocks=blocks)
                            card = card.to_dict()
                            slot_status = card["status"]
                        except (ValueError, RecordError):
                            card = None
                            slot_status = "malformed"
                    rows.append(
                        dict(
                            job=job["id"],
                            slot=slot,
                            card=card,
                            checkable=checkable,
                            status=slot_status,
                        )
                    )
        result = dict(
            report=report(plan, rows, observer),
            slots=rows,
            cards=[r["card"] for r in rows if r["card"]],
            worst_case_micro_usd=worst,
            ledger=ledger.snapshot(),
        )
        storage.write(relative / "result.json", result)
        storage.disk_guard(storage.local(storage.GENERATED))
        return result


def main(argv=None):
    """Run authored replays or delegate the separately gated WO-6 pilot."""
    import sys

    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--live" in arguments or "--dry-run" in arguments:
        from mve.observer.pilot import main as pilot_main

        return pilot_main(arguments)
    import argparse
    from datetime import datetime
    from mve.budget import BudgetLedger
    from mve.observer.design import Design
    from mve.perceiver.contract import strict_json
    from mve.preflight.probe_contract import ProbeReply

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--request", type=Path, required=True, help="offline replay request JSON"
    )
    args = parser.parse_args(argv)
    require(
        args.request.stat().st_size <= 10 * 1024**2, "offline request exceeds 10 MiB"
    )
    request = strict_json(args.request.read_text())
    root = inside(args.request.parent, request["input_root"])
    ledger_path = storage.local(storage.GENERATED / storage.token(request["ledger"]))
    storage.disk_guard(storage.local(storage.GENERATED), 1024 * 1024)
    ledger = BudgetLedger(ledger_path, price_table=request["prices"])
    replay = {
        key: tuple(
            Replay(
                tuple(
                    ProbeReply(e["raw"].encode(), e["billed_usd"])
                    if isinstance(e, dict)
                    else e
                    for e in entries
                )
            )
            for entries in pair
        )
        for key, pair in request["replays"].items()
    }
    when = datetime.fromisoformat(request["fixture_time"])
    result = run(
        Design.from_dict(request["design"]),
        root=root,
        ledger=ledger,
        reconciled=request["reconciliation"],
        replays=replay,
        run_id=request["run_id"],
        clock=lambda: when,
    )
    print(
        json.dumps(
            {
                "hosted_calls": 0,
                "GO1": result["report"]["GO1"],
                "GO2": result["report"]["GO2"]["status"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
