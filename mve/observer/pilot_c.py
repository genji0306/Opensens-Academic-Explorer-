"""WO-6c comparative pilot. Offline fake transport; live requires a NEW approval."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from mve.budget import BudgetLedger, checked_time
from mve.observer import storage, pilot, pilot_transport as transport, grounded as g
from mve.observer import comparative as c, development_c as dev, feature_power as fp
from mve.observer import pilot_c_accounting as accounting
from mve.observer.card import digest
from mve.observer.refusals import Refusal, Parser, require, guarded, boundary
from mve.preflight.probe import verified_ceiling, usd, utc_now
from mve.preflight.probe_live import price_table

WO6C_APPROVAL = None
ROOT = Path(__file__).resolve().parents[2]
BASE = Path("mve/generated/wo6c-pilot")


def request(png, prompt):
    return transport.request(png, prompt)


def load_plan():
    register = dev.load()
    p = dict(
        schema="mve-wo6c-design-v3",
        jobs=dev.jobs(register),
        planned_calls=24,
        slots_per_job=3,
        retries=0,
        owner_approval=WO6C_APPROVAL,
        development_sha256=register["sha256"],
        power_sha256=fp.load()["sha256"],
        composite_size=[1024, 352],
        input_tokens=16384,
        output_tokens=1024,
        worst_case_micro_usd=147456,
        input_bound="1024x352: ceil(1024/16)*ceil(352/16)=1408 patches; allowance 8 tokens/patch=11264, plus 2048 UTF-8 prompt bytes at <=1 token/byte and 3072 overhead =16384. Engineering allowance; provider image tokenizer unverified, no server-enforced input ceiling.",
        protocol="two fresh perception calls then one job-local card call; one composite image per call; no retry",
        GO2="descriptive only; development reuse, no independent replication",
    )
    return {**p, "sha256": digest(p)}


@guarded("source_pin")
def verify_pins(plan):
    packet = json.loads((ROOT / "mve/DEPS.lock").read_text())["packets"]["WO-6c"]
    require(packet["design_sha256"] == plan["sha256"], "design_pin")
    for path, sha in packet["files"].items():
        require(
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, "source_pin"
        )


def image_bytes(job, *, live):
    from mve.observer import capture_c

    if live:
        return c.composite(*(capture_c.image(job, s) for s in ("A", "B")))
    # Authored plumbing proxy only. No claim of a native new-null capture.
    from mve.observer import pilot_inputs as inputs

    def proxy(side):
        kind = "none" if job["sealed"][side] == "real" else "null_twin"
        e = next(
            e
            for e in inputs.manifest()["snapshots"]
            if e["module"] == job["module"] and e["control"]["kind"] == kind
        )
        return inputs.image_bytes(e["snapshot_id"])

    return c.composite(proxy("A"), proxy("B"))


def fake_response(index, job):
    if index < 2:
        body = {
            "observations": [
                dict(
                    id=f"p{index}:1",
                    side="A",
                    feature_tag="modality_x",
                    region="whole",
                    text="Authored fixture: more peaks in A.",
                )
            ]
        }
    else:
        body = {
            "cards": [
                dict(
                    claim="A has more peaks.",
                    side="A",
                    feature_tag="modality_x",
                    data="source_gaps"
                    if job["module"] in dev.ZERO
                    else "display_coordinates",
                    observation_ids=["p0:1"],
                )
                for _ in range(3)
            ]
        }
    return json.dumps(
        dict(
            model="deepseek-flash",
            usage=dict(prompt_tokens=300, completion_tokens=200),
            choices=[
                dict(finish_reason="stop", message=dict(content=json.dumps(body)))
            ],
        )
    ).encode()


def observe(book, job, *, output, clock, live, png):
    obs = []
    values = []
    calls = []
    failures = []
    for index in range(3):
        if book.snapshot()["frozen"]:
            break
        prompt = (
            c.PERCEPTION_PROMPT.replace("PASS", str(index))
            if index < 2
            else c.card_prompt(obs)
        )
        ident = f'wo6c:{job["id"]}:{index}'
        folder = output / str(index)
        receipt = transport.dispatch(
            book,
            request(png, prompt),
            output=folder,
            attempt=ident,
            clock=clock,
            live=live,
            fake_raw=None if live else fake_response(index, job),
        )
        calls.append(ident)
        if receipt["status"] != "ok":
            failures.append(receipt["status"])
            continue
        try:
            raw = g.parse((folder / "response.raw").read_bytes())
            body = g.parse(raw["choices"][0]["message"]["content"])
            if index < 2:
                obs.extend(c.perception(body, index))
            else:
                values = g.proposals(body)
        except (g.Malformed, KeyError, TypeError, IndexError):
            failures.append("malformed")
    return dict(proposals=values, observations=obs, calls=calls, failures=failures)


def score(job, observed):
    rows = []
    for slot in range(3):
        row = dict(
            job=job["id"],
            module=job["module"],
            pair_type=job["pair_type"],
            slot=slot,
            status="non-separating",
            card=None,
            reason="empty_or_failed",
            claimed_difference=False,
        )
        if slot < len(observed["proposals"]):
            p = observed["proposals"][slot]
            row["claimed_difference"] = (
                isinstance(p, dict)
                and isinstance(p.get("claim"), str)
                and bool(p["claim"].strip())
            )
            try:
                c.validate(p)
                check = fp.check(
                    job["module"],
                    p["feature_tag"],
                    p["data"],
                    dev.data(job, "A"),
                    dev.data(job, "B"),
                )
                card = c.envelope(job, p, observed["observations"], check)
                c.validate_card(card)
                row.update(status=card["status"], card=card, reason=None)
            except g.Malformed:
                row.update(status="ungrounded", reason="malformed")
        rows.append(row)
    return rows


@guarded("internal_error")
def execute(*, live, owner_approval=None, reviewed_head=None, clock=utc_now):
    if live:
        require(
            WO6C_APPROVAL is not None and owner_approval == WO6C_APPROVAL,
            "owner_approval",
        )
        pilot.require_review(
            owner_approval, reviewed_head, expected_approval=WO6C_APPROVAL
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
            len(plan["jobs"]) * 3 == plan["planned_calls"] == transport.CALL_CAP == 24,
            "call_cap",
        )
        worst = plan["worst_case_micro_usd"]
        require(
            0 < worst <= min(250000, reconciled["remaining_micro_usd"]), "budget_cap"
        )
        # All native capture receipts must be accepted before creating a live run.
        with boundary("source_pin"):
            images = {j["id"]: image_bytes(j, live=live) for j in plan["jobs"]}
        storage.disk_guard(storage.local(storage.GENERATED), 24 * 3 * 1024**2)
        storage.write(relative / "sealed-design.json", plan)
        storage.write(
            relative / "approval.json",
            dict(
                owner_approval=owner_approval, reviewed_by_opus=reviewed_head, live=live
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
                book, request(next(iter(images.values())), c.PERCEPTION_PROMPT)
            )
            require(ceiling * 24 == worst, "budget_cap")
        rows = []
        for job in plan["jobs"]:
            observed = observe(
                book,
                job,
                output=storage.local(relative / "attempts" / job["id"]),
                clock=safe_clock,
                live=live,
                png=images[job["id"]],
            )
            storage.write(relative / "observations" / f'{job["id"]}.json', observed)
            rows.extend(score(job, observed))
        ledger = book.snapshot()
        r = dict(
            schema="mve-wo6c-report-v3",
            mode="live" if live else "dry_run",
            planned_calls=24,
            calls=len(ledger["attempts"]),
            hosted_calls=len(ledger["attempts"]) if live else 0,
            worst_case_micro_usd=worst,
            slots=rows,
            by_pair_type=c.report(rows),
            budget=dict(
                prior_micro_usd=reconciled["prior_micro_usd"],
                pilot_micro_usd=ledger["exposure_micro_usd"],
                aggregate_micro_usd=reconciled["prior_micro_usd"]
                + ledger["exposure_micro_usd"],
                actual_new_spend_micro_usd=ledger["exposure_micro_usd"] if live else 0,
            ),
            GO2="not established; descriptive only",
            survivors=0,
            limitations=[
                "Dry-run uses WO-1 image proxies for uncaptured new draws; numeric checks use registered numbers. No perception evidence."
                if not live
                else "Development-only comparative pilot. No GO gate.",
                "Null-null false-difference numerator counts every proposed textual claim, including malformed cards, whether check agrees or not; denominator all 12 allocated slots.",
            ],
        )
        storage.write(relative / "ledger.json", ledger)
        storage.write(relative / "report.json", r)
        return r


def main(argv=None):
    ap = Parser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    ap.add_argument("--owner-approval")
    ap.add_argument("--reviewed-by-opus")
    a = ap.parse_args(argv)
    try:
        r = execute(
            live=a.live,
            owner_approval=a.owner_approval,
            reviewed_head=a.reviewed_by_opus,
            clock=utc_now
            if a.live
            else lambda: datetime(2026, 9, 28, 12, tzinfo=timezone.utc),
        )
        summary = json.dumps(
            {k: r[k] for k in ("calls", "hosted_calls", "worst_case_micro_usd")}
        )
    except Exception as exc:
        ap.exit(
            2,
            "WO-6 refused: "
            + (exc.label if isinstance(exc, Refusal) else "internal_error")
            + "\n",
        )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
