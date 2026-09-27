"""Exact snapshot accounting; source subledger limits never replace campaign caps."""

from collections import Counter
from decimal import Decimal, localcontext

STATES = ("reserved", "dispatched", "settled", "cancelled")
D4 = {"P0": 2_000_000, "P1": 8_000_000, "aggregate": 20_000_000}


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer micro-USD or count required")
    return value


def money(value):
    with localcontext() as context:
        context.prec = max(28, len(str(abs(value))) + 8)
        usd = format(Decimal(value) / Decimal(1_000_000), ".6f")
    return {"micro_usd": value, "usd": usd}


def checked_rows(snapshot):
    if type(snapshot["frozen"]) is not bool:
        raise ValueError("ledger frozen state must be boolean")
    seen = set()
    for row in snapshot["attempts"]:
        if (
            not row["id"]
            or row["id"] in seen
            or row["state"] not in STATES
            or row["phase"] not in ("P0", "P1", "P2")
        ):
            raise ValueError("duplicate attempt, invalid state or phase")
        seen.add(row["id"])
        integer(row["reserved"])
        if row["state"] == "settled":
            integer(row["actual"])
        elif row.get("actual") is not None:
            raise ValueError("unsettled attempt cannot have an actual charge")
        yield row


def totals(rows):
    by_state = Counter(row["state"] for row in rows)
    reserved = sum(r["reserved"] for r in rows if r["state"] == "reserved")
    uncertain = sum(r["reserved"] for r in rows if r["state"] == "dispatched")
    settled = sum(r["actual"] for r in rows if r["state"] == "settled")
    return {
        "reserved": money(reserved),
        "uncertain": money(uncertain),
        "settled": money(settled),
        "exposure": money(reserved + uncertain + settled),
        "attempts_by_state": {s: by_state[s] for s in STATES},
        "attempts": len(rows),
    }


def merge_attempts(ledgers):
    merged = {}
    for origin, snapshot in ledgers.items():
        rows = list(checked_rows(snapshot))
        if "exposure_micro_usd" in snapshot:
            if (
                integer(snapshot["exposure_micro_usd"])
                != totals(rows)["exposure"]["micro_usd"]
            ):
                raise ValueError("snapshot exposure disagrees with attempts")
        for row in rows:
            ident = row["id"]
            if ident in merged and merged[ident]["row"] != row:
                raise ValueError(
                    "conflicting copies of an attempt; reconcile before reporting"
                )
            saved = merged.setdefault(ident, {"row": row, "origins": []})
            saved["origins"].append(origin)
    return [{**v["row"], "origins": v["origins"]} for _, v in sorted(merged.items())]


def quota_totals(ledgers):
    entries, amounts = {}, Counter()
    for snapshot in ledgers.values():
        for row in snapshot["quota"]:
            if row["id"] in entries:
                if entries[row["id"]] != row:
                    raise ValueError("conflicting quota entry")
                continue
            entries[row["id"]] = row
            amounts[row["provider"]] += integer(row["units"])
    return dict(sorted(amounts.items()))


def phase_totals(rows, caps, complete):
    aggregate = totals(rows)
    exposure = aggregate["exposure"]["micro_usd"]
    phases = {
        p: totals([r for r in rows if r["phase"] == p]) for p in ("P0", "P1", "P2")
    }
    for phase, summary in phases.items():
        remaining = (
            caps.get(phase, caps["aggregate"]) - summary["exposure"]["micro_usd"]
        )
        summary["remaining"] = (
            money(min(remaining, caps["aggregate"] - exposure)) if complete else None
        )
    aggregate["remaining"] = money(caps["aggregate"] - exposure) if complete else None
    return aggregate, phases


def summarize_budget(campaign, live):
    if any(row["phase"] != "P0" for row in live["attempts"]):
        raise ValueError("dedicated WP-0b live subledger must belong to P0")
    ledgers = (
        {"campaign": campaign, "live": live} if campaign is not None else {"live": live}
    )
    caps = campaign["configuration"]["caps"] if campaign is not None else D4.copy()
    if set(caps) != set(D4) or any(not 0 < integer(caps[k]) <= D4[k] for k in D4):
        raise ValueError("invalid campaign caps")
    rows = merge_attempts(ledgers)
    aggregate, phases = phase_totals(rows, caps, campaign is not None)
    frozen = any(s["frozen"] for s in ledgers.values())
    return {
        "complete": campaign is not None,
        "scope": "complete supplied snapshots"
        if campaign is not None
        else "known exposure only; campaign snapshot absent",
        "caps": caps,
        "caps_basis": "campaign configuration"
        if campaign is not None
        else "plan D4 authorization, not a ledger",
        "live_caps": live["configuration"]["caps"],
        "aggregate": aggregate,
        "phases": phases,
        "frozen": frozen if frozen or campaign is not None else None,
        "stop_state": "frozen"
        if frozen
        else "not frozen"
        if campaign is not None
        else "unknown: campaign snapshot absent",
        "ledgers": {
            k: {
                "frozen": v["frozen"],
                "events": v["events"],
                "window_policy": v["configuration"]["window"],
                "quota": v["quota"],
            }
            for k, v in ledgers.items()
        },
        "quota_by_provider": quota_totals(ledgers),
        "quota_scope": "ledger quota rows have no phase field; per-phase attribution and quota limits are not established",
        "attempts": rows,
        "null": "N/A: accounting census",
        "micro": None,
        "macro": None,
        "aggregation_reason": "monetary sums and attempt counts, not relation scoring",
        "uncertain_policy": "dispatched without settlement retains full reservation; actual cost unknown",
        "p2_policy": "P2 shares the remaining aggregate, not a separate fixed cap",
        "carry_policy": "same attempt ID with byte-equivalent parsed row counted once; conflicting copies refused",
    }
