"""WO-6b grounded descriptive pilot. Builder runs --dry-run only."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from mve.budget import BudgetLedger, checked_time
from mve.observer import (
    storage,
    pilot,
    pilot_inputs as inputs,
    pilot_transport as transport,
)
from mve.observer import (
    pilot_cards,
    pilot_b_accounting as accounting,
    grounded as g,
    power,
)
from mve.observer.card import Card, card_hash, digest
from mve.observer.refusals import Refusal, Parser, require, boundary, guarded
from mve.preflight.probe import verified_ceiling, usd, utc_now
from mve.preflight.probe_live import price_table

WO6B_APPROVAL = None
ROOT = Path(__file__).resolve().parents[2]
BASE = storage.GENERATED / "wo6b-pilot"


def load_plan():
    p = inputs.load_plan()
    p.pop("sha256")
    p.update(
        schema="mve-wo6b-descriptive-design-v2",
        jobs=[j for j in p["jobs"] if j["arm"] in ("real", "null_twin")],
        contract_sha256=digest(g.CONTRACT),
        power_sha256=power.load()["sha256"],
        protocol="two bounded perception passes, then one card call with this job observations; no retries",
        owner_approval=WO6B_APPROVAL,
    )
    return {**p, "sha256": digest(p)}


@guarded("source_pin")
def verify_pins(plan):
    packet = json.loads((ROOT / "mve/DEPS.lock").read_text())["packets"]["WO-6b"]
    require(packet["design_sha256"] == plan["sha256"], "design_pin")
    for path, sha in packet["files"].items():
        require(
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, "source_pin"
        )


def fake_response(prompt, job):
    if prompt.startswith("Pixels only."):
        pass_index = 0 if "p0:1" in prompt else 1
        content = {
            "observations": [
                dict(
                    id=f"p{pass_index}:1",
                    feature_tag="histogram_peak",
                    region="whole",
                    text="Authored fixture peak.",
                )
            ]
        }
    else:
        content = {"cards": []}
        for i in range(3):
            p = pilot_cards.proposal_fixture()
            p["claim"] += f" Slot {i+1}."
            p["observation_ids"] = ["p0:1"]
            p["testable_form"].update(
                statistic="gaudin_ks",
                baseline="Gaudin GUE",
                data="source_gaps"
                if job["module"] in ("spectral", "field-dyson")
                else "source_index_gaps",
            )
            content["cards"].append(p)
    return json.dumps(
        dict(
            model="deepseek-flash",
            usage=dict(prompt_tokens=300, completion_tokens=200),
            choices=[
                dict(finish_reason="stop", message=dict(content=json.dumps(content)))
            ],
        )
    ).encode()


def observe(book, job, *, output, clock, live):
    observations, passes, calls = [], [], []
    reason, state, values, prompt = None, "ok", [], ""
    for index in range(3):
        # Failed perception still consumes the scheduled card opportunity; no
        # repair call, invented observation, or replacement slot is allowed.
        prompt = (
            g.PERCEPTION_PROMPT.replace("PASS", str(index))
            if index < 2
            else g.card_prompt(observations)
        )
        ident = f"wo6b:{job['id']}:{index}"
        folder = output / str(index)
        r = transport.dispatch(
            book,
            transport.request(inputs.image_bytes(job["snapshot_id"]), prompt),
            output=folder,
            attempt=ident,
            clock=clock,
            live=live,
            fake_raw=None if live else fake_response(prompt, job),
        )
        calls.append(ident)
        try:
            if r["status"] not in ("ok", "malformed"):
                state = r["status"]
                if index < 2:
                    passes.append(None)
                if book.snapshot()["frozen"]:
                    break
                continue
            else:
                raw = g.parse((folder / "response.raw").read_bytes())
                body = g.parse(raw["choices"][0]["message"]["content"])
            if index < 2:
                parsed = g.perception(body, index)
                passes.append(parsed)
                observations.extend(parsed)
            else:
                values = g.proposals(body)
        except (g.Malformed, KeyError, TypeError, IndexError) as exc:
            reason = exc.reason if isinstance(exc, g.Malformed) else "bad_type"
            state = "malformed"
            if index < 2:
                passes.append(None)
        if book.snapshot()["frozen"]:
            state = "ledger_frozen"
            break
    rep = (
        g.repeatability(*passes)
        if len(passes) == 2 and all(p is not None for p in passes)
        else None
    )
    return dict(
        proposals=values,
        observations=observations,
        calls=calls,
        status=state,
        reason=reason,
        tag_jaccard=rep,
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
    )


def score(job, observed, *, live):
    values = observed["proposals"] if observed["status"] == "ok" else []
    assessed = g.assess(values, observed["observations"], job_id=job["id"])
    rows = []
    for slot in range(3):
        row = dict(
            job=job["id"],
            arm=job["arm"],
            module=job["module"],
            slot=slot,
            status="empty" if observed["status"] == "ok" else observed["status"],
            reason=observed["reason"],
            grounded=False,
            contradictory=False,
            card=None,
            check=dict(status="unavailable", inferential=False),
        )
        if slot < len(values):
            row.update(assessed[slot])
            if row["reason"] is None:
                p = values[slot]
                # Preserve the WO-2 lifecycle, with v2 diagnostic status outside it.
                c = pilot_cards.make_card(
                    {k: v for k, v in p.items() if k != "observation_ids"},
                    job,
                    observed["calls"],
                    live=live,
                )
                d = c.to_dict()
                d["observer"]["prompt_sha"] = observed["prompt_sha256"]
                d["context"]["limitations"] = [
                    "WO-6b descriptive; citation is not truth; no replication or survivor.",
                    "Hosted observation."
                    if live
                    else "Authored fake transport; no scientific evidence.",
                ]
                d["content_hash"] = card_hash(d)
                d = (
                    Card.from_dict(d)
                    .transition("well_formed")
                    .transition("frozen")
                    .transition("preliminary")
                    .to_dict()
                )
                check = power.check(p, job)
                status = row["status"]
                if status == "grounded" and check["status"] == "underpowered":
                    status = "underpowered"
                card = dict(
                    schema="oae-mve-grounded-card-v2",
                    job=job["id"],
                    hypothesis=d,
                    status=status,
                    lifecycle="preliminary",
                    proposal=p,
                    observations=observed["observations"],
                    assessment=assessed[slot],
                    check=check,
                )
                card["sha256"] = digest(card)
                g.validate_card(card)
                row.update(card=card, check=check, status=status)
        rows.append(row)
    return rows


def markdown(r):
    lines = [
        "# WO-6b descriptive pilot",
        "",
        f"Mode: {r['mode']}; calls {r['calls']}/24; hosted {r['hosted_calls']}; survivors 0.",
        "",
        "| Arm | Slots | Grounded | Ungrounded | Contradictory | Underpowered | Malformed | Tag Jaccard |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, counts in r["by_arm"].items():
        vals = [
            counts[k]
            for k in (
                "slots",
                "grounded",
                "ungrounded",
                "contradictory",
                "underpowered",
                "malformed",
            )
        ]
        lines.append(
            "| "
            + arm
            + " | "
            + " | ".join(map(str, vals))
            + " | "
            + str(r["repeatability"]["by_arm"][arm]["mean_tag_jaccard"])
            + " |"
        )
    lines += [
        "",
        "Counts overlap: grounding, contradiction and power are separate diagnostics. All cards remain preliminary.",
        "Tag Jaccard is descriptive; agreement verifies nothing. GO1–GO4 not established.",
        "No second observer, donors, contrasts or independent replication. No relay.",
    ]
    return "\n".join(lines) + "\n"


@guarded("internal_error")
def execute(*, live, owner_approval=None, reviewed_head=None, clock=utc_now):
    if live:
        require(
            WO6B_APPROVAL is not None and owner_approval == WO6B_APPROVAL,
            "owner_approval",
        )
        pilot.require_review(
            owner_approval, reviewed_head, expected_approval=WO6B_APPROVAL
        )
    else:
        require(owner_approval is None and reviewed_head is None, "arguments")
    with boundary("source_pin"):
        plan = load_plan()
    verify_pins(plan)
    relative = BASE / ("live" if live else "dry-run")
    with storage.lock():
        require(not storage.local(relative).exists(), "run_exists")

        def safe_clock():
            with boundary("peak_window"):
                now = clock()
                checked_time(now)
                return now

        safe_clock()
        reconciled = accounting.reconcile()
        require(
            plan["planned_calls"] == len(plan["jobs"]) * 3 == transport.CALL_CAP == 24,
            "call_cap",
        )
        worst = plan["worst_case_micro_usd"]
        require(
            0 < worst <= min(250000, reconciled["remaining_micro_usd"]), "budget_cap"
        )
        storage.disk_guard(storage.local(storage.GENERATED), 24 * 3 * 1024**2)
        storage.write(relative / "design.json", plan)
        storage.write(
            relative / "approval.json",
            dict(
                owner_approval=owner_approval,
                reviewed_by_opus=reviewed_head,
                mode="live" if live else "dry_run",
            ),
        )
        storage.write(relative / "reconciliation.json", reconciled)
        with boundary("budget_cap"):
            book = BudgetLedger(
                storage.local(relative / "pilot.sqlite"),
                aggregate=usd(reconciled["remaining_micro_usd"]),
                p1="0.25",
                price_table=price_table(),
            )
            _, ceiling = verified_ceiling(
                book,
                transport.request(
                    inputs.image_bytes(plan["jobs"][0]["snapshot_id"]), g.CARD_PROMPT
                ),
            )
            require(ceiling * 24 == worst, "budget_cap")
        rows, repetitions = [], {}
        for job in plan["jobs"]:
            observed = dict(
                proposals=[],
                observations=[],
                calls=[],
                status="ledger_frozen",
                reason=None,
                tag_jaccard=None,
                prompt_sha256="",
            )
            if not book.snapshot()["frozen"]:
                observed = observe(
                    book,
                    job,
                    output=storage.local(relative / "attempts" / job["id"]),
                    clock=safe_clock,
                    live=live,
                )
            rows.extend(score(job, observed, live=live))
            repetitions[job["id"]] = dict(
                module=job["module"],
                arm=job["arm"],
                tag_jaccard=observed["tag_jaccard"],
            )
        ledger = book.snapshot()
        result = dict(
            schema="mve-wo6b-report-v2",
            mode="live" if live else "dry_run",
            planned_calls=24,
            calls=len(ledger["attempts"]),
            hosted_calls=len(ledger["attempts"]) if live else 0,
            worst_case_micro_usd=worst,
            design_sha256=plan["sha256"],
            slots=rows,
            by_arm=g.arm_counts(rows),
            repeatability=g.repetition_report(repetitions),
            budget=dict(
                prior_micro_usd=reconciled["prior_micro_usd"],
                pilot_micro_usd=ledger["exposure_micro_usd"],
                aggregate_micro_usd=reconciled["prior_micro_usd"]
                + ledger["exposure_micro_usd"],
                basis="usage-derived"
                if live
                else "SIMULATED pilot; prior usage actual; actual new spend zero",
            ),
            GO1="descriptive_only",
            GO2=dict(
                passed=False,
                status="descriptive_only",
                independent_clusters=0,
                survivors=0,
            ),
            GO3="not_established",
            GO4="not_established",
            reviewed_by_opus=reviewed_head,
        )
        storage.write(relative / "ledger.json", ledger)
        storage.write(relative / "report.json", result)
        storage.write(relative / "report.md", markdown(result).encode())
        storage.write(
            storage.OUTBOX / "wo6b" / ("live" if live else "dry-run") / "drafts.json",
            dict(
                status="held_preliminary",
                relay=False,
                cards=[r["card"] for r in rows if r["card"]],
            ),
        )
        return result


def main(argv=None):
    ap = Parser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    ap.add_argument("--owner-approval")
    ap.add_argument("--reviewed-by-opus")
    args = ap.parse_args(argv)
    try:
        result = execute(
            live=args.live,
            owner_approval=args.owner_approval,
            reviewed_head=args.reviewed_by_opus,
            clock=utc_now
            if args.live
            else lambda: datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
        )
    except Exception as exc:
        label = exc.label if isinstance(exc, Refusal) else "internal_error"
        ap.exit(2, "WO-6 refused: " + label + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "planned_calls",
                    "calls",
                    "hosted_calls",
                    "worst_case_micro_usd",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
