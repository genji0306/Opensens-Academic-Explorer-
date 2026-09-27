"""Assemble the present committed evidence; never run a model, compiler or corpus."""

from mve.reporting.sources import Evidence
from mve.reporting.ledger import summarize_budget
from mve.reporting.gates import PLAN, G3, SPECS, evaluate_gate, g3_checks
from mve.reporting.tables import (
    PREFLIGHT,
    CORPUS,
    GENERATION,
    SPIKE,
    LIVE,
    TASKS,
    REFERENCES,
    preflight_table,
    corpus_table,
    g3_table,
    spike_table,
    live_table,
    missing_scores,
)

CAMPAIGN = "mve/campaign/ledger.json"
LIVE_LEDGER = "docs/mve/reviews/wp0b-live/ledger.json"
REVIEW = "docs/mve/reviews/OFFLINE_PACKETS_REVIEW_OPUS_20260927.md"


def collect_tables(evidence):
    data = {
        p: evidence.optional(p)
        for p in (PREFLIGHT, CORPUS, GENERATION, SPIKE, LIVE, G3, TASKS, REFERENCES)
    }
    tables = {}
    for name, path, builder in [
        ("preflight", PREFLIGHT, preflight_table),
        ("classifier_spike", SPIKE, spike_table),
        ("live_probe", LIVE, live_table),
    ]:
        tables[name] = builder(data[path]) if data[path] is not None else []
    tables["corpus"] = (
        corpus_table(data[CORPUS], data[GENERATION]) if data[CORPUS] else []
    )
    tables["formalization"] = (
        g3_table(data[G3], data[TASKS], data[REFERENCES])
        if all(data[p] is not None for p in (G3, TASKS, REFERENCES))
        else []
    )
    return data, tables


def build_gates(data, tables):
    checks = {gate: {} for gate in SPECS}
    if tables["corpus"]:
        checks["G0"]["records"] = {
            "outcome": data[CORPUS]["records_validated"] >= 100,
            "reason": "WP-2 artifact audit records validated; does not replace negative fixtures or model comparison",
            "sources": [CORPUS + "#/records_validated"],
        }
    if tables["formalization"]:
        checks["G3"] = g3_checks(data[G3])
        for row in checks["G3"].values():
            row["sources"] += [TASKS + "#/", REFERENCES + "#/"]
    if data[SPIKE] is not None:
        for key in ("floors", "weight_refit", "promotion"):
            checks["G2"][key] = {
                "outcome": None,
                "reason": data[SPIKE]["learning"]["reason"]
                + "; "
                + "; ".join(data[SPIKE]["learning"]["gaps"]),
                "sources": [SPIKE + "#/learning"],
            }
    return {gate: evaluate_gate(gate, checks[gate]) for gate in SPECS}


def build_report(root, revision="HEAD", *, campaign_path=CAMPAIGN):
    evidence = Evidence(root, revision)
    evidence.read(PLAN)
    evidence.read(REVIEW)
    data, tables = collect_tables(evidence)
    campaign = evidence.optional(campaign_path)
    live = evidence.json(LIVE_LEDGER)
    budget = summarize_budget(campaign, live)
    receipt = data[LIVE]
    if receipt is not None:
        matches = [r for r in live["attempts"] if r["id"] == receipt["attempt"]]
        if (
            len(matches) != 1
            or matches[0]["actual"] != receipt["observation"]["derived_micro_usd"]
            or matches[0]["phase"] != receipt["phase"]
            or matches[0]["reserved"] != receipt["reserved_micro_usd"]
        ):
            raise ValueError("live receipt and ledger charge disagree")
    budget["sources"] = [LIVE_LEDGER + "#/", PLAN + "#0"]
    if receipt is not None:
        budget["sources"].append(LIVE + "#/observation/derived_micro_usd")
    if campaign is not None:
        budget["sources"].append(campaign_path + "#/")
    budget["live_cost_basis"] = (
        receipt["cost_policy"] if receipt else "receipt absent; ledger settlement only"
    )
    return {
        "schema": "mve-offline-report-v1",
        "evidence_commit": evidence.revision,
        "budget": budget,
        "gates": build_gates(data, tables),
        "tables": tables,
        "relation_scores": missing_scores(),
        "sources": dict(sorted(evidence.sources.items())),
        "missing_sources": sorted(evidence.missing),
        "scope": "Committed receipts only. No new model, Lean, corpus, benchmark or ingest run. No P6 submission.",
        "confidence_policy": "95% intervals are null where no independent sampling design is committed; fixture counts are descriptive, not population confidence claims.",
    }
