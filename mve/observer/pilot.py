"""Offline-buildable WO-6 activation. --live is exclusively for the reviewed operator."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from mve.budget import BudgetLedger, checked_time
from mve.errors import RecordError
from mve.money import BudgetError
from mve.observer import storage, pilot_inputs as inputs, pilot_transport as transport
from mve.observer import pilot_accounting as accounting, pilot_cards as cards
from mve.observer.design import ARMS
from mve.observer.refusals import Refusal, require, boundary, guarded, Parser
from mve.observer.metrics import sign_flip, interval
from mve.preflight.probe import utc_now, usd, verified_ceiling
from mve.preflight.probe_live import price_table

ROOT = Path(__file__).resolve().parents[2]
BASE = storage.GENERATED / "wo6-pilot"


def require_review(owner_approval, commit, *, expected_approval="2026-09-28"):
    require(owner_approval == expected_approval, "owner_approval")
    require(
        isinstance(commit, str) and re.fullmatch("[0-9a-f]{40}", commit), "review_head"
    )
    try:
        head = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                timeout=10,
            )
            .stdout.decode()
            .strip()
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            timeout=10,
        ).stdout
    except Exception:
        raise Refusal("review_head") from None
    require(head == commit, "review_head")
    require(not dirty, "clean_tree")


@guarded("source_pin")
def verify_pins(plan):
    packet = json.loads((ROOT / "mve/DEPS.lock").read_text())["packets"]["WO-6"]
    require(packet["design_sha256"] == plan["sha256"], "design_pin")
    for path, sha in packet["files"].items():
        require(
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha,
            "source_pin",
        )


def fake_response(prompt, job):
    if prompt == cards.PERCEPTION_PROMPT:
        content = {"observations": ["Authored fixture pattern."]}
    else:
        proposals = []
        for slot in range(3):
            p = cards.proposal_fixture()
            p["claim"] += " Slot " + str(slot + 1) + "."
            if job["module"] == "spectral":
                p["testable_form"].update(statistic="gaudin_ks", baseline="Gaudin GUE")
            proposals.append(p)
        content = {"cards": proposals}
    return json.dumps(
        dict(
            model="deepseek-flash",
            usage={"prompt_tokens": 300, "completion_tokens": 200},
            choices=[
                {"finish_reason": "stop", "message": {"content": json.dumps(content)}}
            ],
        )
    ).encode()


def observe(ledger, job, *, output, clock, live):
    png = inputs.image_bytes(job["snapshot_id"])
    receipts, contents, calls = [], [], []
    for index, prompt in enumerate(
        [cards.PERCEPTION_PROMPT, cards.PERCEPTION_PROMPT, cards.CARD_PROMPT]
    ):
        ident = f"wo6:{job['id']}:{index}"
        folder = output / str(index)
        r = transport.dispatch(
            ledger,
            transport.request(png, prompt),
            output=folder,
            attempt=ident,
            clock=clock,
            live=live,
            fake_raw=None if live else fake_response(prompt, job),
        )
        receipts.append(r)
        calls.append(ident)
        contents.append(transport.content(folder, r))
        if ledger.snapshot()["frozen"]:
            break
    status = next((r["status"] for r in receipts if r["status"] != "ok"), "ok")
    proposals = []
    if status == "ok" and len(contents) == 3:
        if not all(
            type(c) is dict
            and set(c) == {"observations"}
            and type(c["observations"]) is list
            and all(type(o) is str for o in c["observations"])
            for c in contents[:2]
        ):
            status = "malformed"
    if status == "ok" and len(contents) == 3:
        body = contents[2]
        if (
            type(body) is dict
            and type(body.get("cards")) is list
            and len(body["cards"]) <= 3
        ):
            proposals = body["cards"]
        else:
            status = "malformed"
    return (
        proposals,
        calls,
        status,
        {
            "agreement": contents[0] == contents[1]
            if len(contents) > 1 and all(c is not None for c in contents[:2])
            else None,
            "meaning": "Two identical fresh-context calls; agreement verifies nothing.",
        },
    )


def summarize(plan, rows, ledger, *, live, agreements):
    counts = Counter(r["status"] for r in rows)
    origins = {}
    for origin, selected in [
        ("model:O-DS", [r for r in rows if r["arm"] != "image_free"]),
        ("model:astra-library", [r for r in rows if r["arm"] == "image_free"]),
    ]:
        n = len(selected)
        valid = sum(r["card"] is not None for r in selected)
        origins[origin] = dict(
            requested=n,
            well_formed=valid,
            data_checkable=sum(r["check"]["status"] == "stage1_only" for r in selected),
            well_formed_rate=valid / n,
            interval=interval(valid, n),
        )
    return dict(
        schema="mve-wo6-report-v1",
        mode="live" if live else "dry_run",
        planned_calls=plan["planned_calls"],
        calls=len(ledger["attempts"]),
        hosted_calls=sum(
            a["state"] in ("dispatched", "settled") for a in ledger["attempts"]
        )
        if live
        else 0,
        worst_case_micro_usd=plan["worst_case_micro_usd"],
        design_sha256=plan["sha256"],
        second_observer=plan["second_observer"],
        input_assumption=plan["input_assumption"],
        images=plan["images"],
        limitations=plan["limitations"],
        slots=rows,
        status_counts=dict(counts),
        GO1={
            "by_origin": origins,
            "status": "descriptive_only",
            "null": "N/A: structural",
        },
        GO2={
            "passed": False,
            "status": "descriptive_only",
            "independent_clusters": 0,
            "development_pairs": 4,
            "comparisons": {
                a: {
                    **sign_flip([0] * 4, seed=plan["seed"]),
                    "label": "descriptive all-zero slot accounting; missing donor/replication prevents a scientific comparison",
                }
                for a in ARMS[1:]
            },
            "by_stratum": {
                c["stratum"]: {
                    a: {"survivors": 0, "slots": 3, **interval(0, 3)} for a in ARMS
                }
                for c in plan["clusters"]
            },
            "null": "real survival does not exceed null twin, image-free or shuffled survival; A1/A2 unestablished",
        },
        GO3={
            "status": "not_established",
            "handed_off": 0,
            "reason": "Q3/Q4/Q5 unanswered; outbox only",
            "null": "N/A: operational",
        },
        GO4={
            "status": "not_established",
            "searched": 0,
            "null": "absence only from a searched corpus",
        },
        budget=accounting.combined_report(ledger),
        budget_basis="usage-derived live exposure"
        if live
        else "SIMULATED pilot charges; WP-0b USD 0.000268 is the only actual prior exposure",
        actual_pilot_spend_usd=None if live else "0.000000",
        agreements=agreements,
    )


def markdown(result):
    lines = [
        "# WO-6 descriptive pilot",
        "",
        f"Mode: {result['mode']}. Planned calls: {result['planned_calls']}; attempts: {result['calls']}; hosted calls: {result['hosted_calls']}.",
        "",
        f"Worst-case reservation: USD {usd(result['worst_case_micro_usd'])}. Aggregate exposure (including WP-0b once): USD {result['budget']['aggregate']['exposure']['usd']}.",
        "",
        f"Budget basis: {result['budget_basis']}.",
        "",
        "Second observer: SKIPPED — owner Q2 unanswered. GO2 cannot pass.",
        "",
        "| Gate | Result |",
        "|---|---|",
        "| GO1 | Descriptive; structural null N/A |",
        "| GO2 | Descriptive only; zero independent clusters |",
        "| GO3 | Not established; zero handoffs; Q3/Q4/Q5 unanswered |",
        "| GO4 | Not established; zero novelty searches |",
        "",
        "| Origin | Requested slots | Valid cards | Stage-1 checkable | Nominal 95% valid-card interval |",
        "|---|---:|---:|---:|---|",
    ]
    for origin, row in result["GO1"]["by_origin"].items():
        bounds = row["interval"]
        lines.append(
            f"| {origin} | {row['requested']} | {row['well_formed']} | {row['data_checkable']} | {bounds['lower95']:.4f}–{bounds['upper95']:.4f} |"
        )
    lines += [
        "",
        "| Comparison with real | Sign-flip p | Patterns | Interpretation |",
        "|---|---:|---:|---|",
    ]
    for arm, row in result["GO2"]["comparisons"].items():
        lines.append(f"| {arm} | {row['p']:.4f} | {row['draws']} | {row['label']} |")
    lines += [
        "",
        "Each of four strata has 3 slots per arm and zero survivors. Nominal slot intervals are descriptive; missing blocks do not establish binomial coverage, independence, or exchangeability.",
        "",
    ]
    lines += ["- " + text for text in result["limitations"]]
    lines += [
        "",
        result["input_assumption"],
        "",
        "Slot statuses: " + json.dumps(result["status_counts"], sort_keys=True) + ".",
        "",
    ]
    return "\n".join(lines)


@guarded("internal_error")
def execute(*, live, owner_approval=None, reviewed_head=None, clock=utc_now):
    if live:
        require_review(owner_approval, reviewed_head)
    else:
        require(owner_approval is None and reviewed_head is None, "arguments")
    with boundary("source_pin"):
        plan = inputs.load_plan()
    verify_pins(plan)
    relative = BASE / ("live" if live else "dry-run")
    with storage.lock():
        require(
            not storage.local(relative).exists(),
            "run_exists",
        )
        with boundary("peak_window"):
            checked_time(clock())
        with boundary("reconciliation"):
            reconciled = accounting.reconcile_campaign()
        worst = plan["worst_case_micro_usd"]
        require(plan["planned_calls"] <= transport.CALL_CAP, "call_cap")
        require(
            worst <= 250000 and worst <= reconciled["remaining_micro_usd"], "budget_cap"
        )
        # Admit all raw prefixes, request images and reports before the first call.
        storage.disk_guard(
            storage.local(storage.GENERATED), plan["planned_calls"] * 3 * 1024**2
        )
        storage.write(relative / "design.json", plan)
        storage.write(
            relative / "approval.json",
            {
                "owner_approval": "2026-09-28" if live else None,
                "reviewed_by_opus": reviewed_head,
                "mode": "live" if live else "dry_run",
            },
        )
        with boundary("budget_cap"):
            book = BudgetLedger(
                storage.local(relative / "pilot.sqlite"),
                aggregate=usd(reconciled["remaining_micro_usd"]),
                p1="0.25",
                price_table=price_table(),
            )
            png = inputs.image_bytes(next(iter(plan["images"])))
            _, ceiling = verified_ceiling(
                book, transport.request(png, cards.CARD_PROMPT)
            )
            require(
                ceiling * plan["planned_calls"] == worst,
                "budget_cap",
            )
        rows, agreements = [], {}
        for job in plan["jobs"]:
            calls = []
            proposals = []
            status = "ok"
            if job["arm"] == "shuffled":
                status = "unavailable_donor"
            elif job["arm"] == "image_free":
                proposals = cards.library(job)
            elif book.snapshot()["frozen"]:
                status = "ledger_frozen"
            else:
                try:
                    proposals, calls, status, agreements[job["id"]] = observe(
                        book,
                        job,
                        output=storage.local(relative / "attempts" / job["id"]),
                        clock=clock,
                        live=live,
                    )
                except Refusal:
                    raise
                except (BudgetError, ValueError, OSError):
                    # No retry or replacement slot. Exception text can contain paths: never persist it.
                    status = "dispatch_failed"
            for slot in range(3):
                card = None
                check = {"status": "unavailable", "inferential": False}
                state = status if status != "ok" else "empty"
                if slot < len(proposals):
                    try:
                        c = cards.make_card(proposals[slot], job, calls, live=live)
                        c, check = cards.check_card(c, job)
                        card = c.to_dict()
                        state = card["status"]
                    except (ValueError, RecordError, TypeError, KeyError):
                        state = "malformed"
                rows.append(
                    dict(
                        job=job["id"],
                        arm=job["arm"],
                        slot=slot,
                        card=card,
                        check=check,
                        status=state,
                    )
                )
        result = summarize(
            plan, rows, book.snapshot(), live=live, agreements=agreements
        )
        result["reviewed_by_opus"] = reviewed_head
        storage.write(relative / "ledger.json", book.snapshot())
        storage.write(relative / "report.json", result)
        storage.write(relative / "report.md", markdown(result).encode())
        # WO-5 output boundary. Preliminary cards are held as drafts, not atlas results or submissions.
        storage.write(
            storage.OUTBOX / "wo6" / ("live" if live else "dry-run") / "drafts.json",
            {
                "status": "held_preliminary",
                "relay": False,
                "cards": [r["card"] for r in rows if r["card"]],
                "reason": "No eligible adopted survivor. Q3/Q4/Q5 unanswered.",
            },
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
        if args.live:
            result = execute(
                live=True,
                owner_approval=args.owner_approval,
                reviewed_head=args.reviewed_by_opus,
            )
        else:
            require(
                not args.owner_approval and not args.reviewed_by_opus,
                "arguments",
            )
            result = execute(
                live=False, clock=lambda: datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
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
