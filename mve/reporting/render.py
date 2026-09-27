"""Canonical JSON and Markdown from the same report object."""

import json


def serialize(report):
    return (
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    )


def cell(value):
    if value is None:
        return "not established"
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(cell(v) for v in row) + " |" for row in rows],
        "",
    ]


def refs(report, sources):
    names = {p: f"S{i:02d}" for i, p in enumerate(report["sources"], 1)}
    return ", ".join(
        names.get(s.split("#")[0], "absent:" + s.split("#")[0])
        + "#"
        + s.partition("#")[2]
        for s in sources
    )


def budget_table(report):
    b = report["budget"]
    rows = []
    for name, row in [*b["phases"].items(), ("aggregate", b["aggregate"])]:
        values = [
            row[k]["usd"] for k in ("reserved", "settled", "uncertain", "exposure")
        ]
        rows.append(
            [
                name,
                *values,
                row["remaining"]["usd"] if row["remaining"] is not None else "unknown",
                row["attempts"],
                json.dumps(row["attempts_by_state"], sort_keys=True),
                refs(report, b["sources"]),
            ]
        )
    return table(
        [
            "Phase",
            "Reserved USD",
            "Settled USD",
            "Uncertain USD",
            "Known exposure USD",
            "Remaining USD",
            "Attempts",
            "Attempts by state",
            "Sources",
        ],
        rows,
    )


def budget_markdown(report):
    b = report["budget"]
    lines = [
        "## SUMMARY: budget",
        "",
        b["scope"] + ".",
        "",
        "Exposure = reserved (unsent) + settled + uncertain (dispatched). Cancelled attempts contribute no exposure. All money is exact micro-USD with Decimal USD formatting.",
        "",
        f"Campaign caps ({b['caps_basis']}): {json.dumps(b['caps'], sort_keys=True)} micro-USD.",
        "",
        f"Dedicated live limits: {json.dumps(b['live_caps'], sort_keys=True)} micro-USD. These are not campaign limits.",
        "",
        f"Stop state: **{b['stop_state']}**. Frozen: {cell(b['frozen'])}. Live cost basis: {b['live_cost_basis']}.",
        "",
        "Null: N/A (accounting census). Micro over relations / macro over diagrams: N/A; these are monetary sums. Counts are attempts; no statistical denominator or interval applies.",
        "",
    ]
    lines += budget_table(report)
    lines += [
        b["carry_policy"] + ". " + b["p2_policy"] + ".",
        "",
        "Quota is separate from USD; totals below cover supplied ledgers only. "
        + b["quota_scope"]
        + ".",
        "",
        "```json",
        json.dumps(b["quota_by_provider"], indent=2, sort_keys=True),
        "```",
        "",
    ]
    for name, state in b["ledgers"].items():
        lines += [
            f"- {name}: frozen={state['frozen']}; window `{state['window_policy']}`; events `{json.dumps(state['events'], sort_keys=True)}`."
        ]
    return lines + [""]


def gate_markdown(report):
    lines = [
        "## Gates",
        "",
        "Missing evidence takes precedence over a failed component; all criteria must be evidenced and met to establish a gate. Policy: MVE_PLAN r5 §8/§11.",
        "",
    ]
    rows = []
    for name, gate in report["gates"].items():
        c = gate["counts"]
        rows.append(
            [
                name,
                gate["status"],
                f"{c['criteria_met']}/{c['criteria_evidenced']}/{c['criteria_expected']}",
                gate["null"],
                "N/A / N/A",
                "; ".join(gate["reasons"]) or "All criteria evidenced and met",
                refs(report, gate["sources"]),
            ]
        )
    lines += table(
        [
            "Gate",
            "Status",
            "Criteria met/evidenced/required",
            "Null / baseline",
            "Micro / macro",
            "Reason",
            "Policy sources",
        ],
        rows,
    )
    for name, gate in report["gates"].items():
        lines += [f"### {name} criteria", ""]
        for key, row in gate["criteria"].items():
            outcome = (
                "not established"
                if row["outcome"] is None
                else "met"
                if row["outcome"]
                else "failed"
            )
            lines.append(
                f"- {key}: **{outcome}** — {row['requirement']}. {row['reason']} ({refs(report, row['sources']) or 'no result evidence'})."
            )
        lines.append("")
    return lines


def evidence_markdown(report):
    lines = [
        "## Evidence counts",
        "",
        report["confidence_policy"],
        "",
        "Every table below is a receipt census, not a scored relation benchmark. Micro/macro entries are N/A for these units. JSON retains null interval values, reasons and field pointers.",
        "",
    ]
    for name, rows in report["tables"].items():
        lines += [f"### {name}", ""]
        lines += table(
            [
                "Measure",
                "Count",
                "Denominator",
                "Unit",
                "Null",
                "Micro / macro",
                "Evidence / limits",
                "Sources",
            ],
            [
                [
                    r["name"],
                    r["count"],
                    r["denominator"],
                    r["unit"],
                    r["null"],
                    "N/A / N/A",
                    r["note"],
                    refs(report, r["sources"]),
                ]
                for r in rows
            ],
        )
    return lines + relation_markdown(report)


def relation_markdown(report):
    lines = [
        "## Relation scoring availability",
        "",
        "Query-set and full-record scoring remain separate, as do each measurement stage and real-data transfer. Missing results are null, never zero accuracy.",
        "",
    ]
    lines += table(
        [
            "Population",
            "Stage",
            "Mode",
            "Count / denominator",
            "Micro",
            "Macro",
            "Null",
            "Reason",
        ],
        [
            [
                r["population"],
                r["stage"],
                r["mode"],
                "unknown / unknown",
                r["micro"],
                r["macro"],
                r["null"],
                r["reason"],
            ]
            for r in report["relation_scores"]
        ],
    )
    return lines


def markdown(report):
    report = json.loads(serialize(report))
    lines = [
        "# MVE SUMMARY and gate report",
        "",
        f"Evidence commit: `{report['evidence_commit']}`",
        "",
        report["scope"],
        "",
    ]
    lines += budget_markdown(report) + gate_markdown(report) + evidence_markdown(report)
    lines += [
        "## Source hashes",
        "",
        "SHA-256 covers the exact bytes in the evidence commit. JSON field pointers and policy section references accompany derived numbers. The source inventory is provenance metadata, not a statistical table.",
        "",
    ]
    for i, (path, source) in enumerate(report["sources"].items(), 1):
        lines += [f"- S{i:02d}: `{path}` — `{source['sha256']}`"]
    lines += [
        "",
        "Missing committed sources: "
        + ", ".join(f"`{p}`" for p in report["missing_sources"])
        + ".",
        "",
    ]
    return "\n".join(lines)
