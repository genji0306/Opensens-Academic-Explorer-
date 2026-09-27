"""WP-10 receipt adapter: coordinate self-consistency cannot establish G5."""

from mve.topology.scoring import ratio

TOPOLOGY = "mve/topology/artifacts/receipt.json"
GRAMMAR_DOC = "docs/mve/TOPOLOGY.md"


def topology_evidence(data):
    sources = [TOPOLOGY + "#/", GRAMMAR_DOC]
    checks = {
        key: {"outcome": None, "reason": reason, "sources": sources}
        for key, reason in {
            "synthetic": "No real perception run; coordinate self-consistency is not G5 evidence",
            "external": "No permitted external perception set or scored run",
            "scores": "Perception scores absent; fixture scores are reported separately",
        }.items()
    }
    if data is None:
        return {
            "scope": "no committed topology fixture receipt",
            "scores": None,
            "sources": [],
        }, checks
    if (
        data["schema"] != "mve-topology-fixtures-v1"
        or data["scope"] != "synthetic_coordinate_self_consistency"
        or data["g5_status"] != "not established"
        or data["perception_runs"] != 0
        or data["external_diagrams"] != 0
        or data["hosted_calls"] != 0
        or data["split_retired"] is not True
    ):
        raise ValueError(
            "WP-10 adapter accepts only public offline self-consistency receipts"
        )
    scores = data["scores"]
    rows = scores["rows"]
    for key in ("exact", "canonicalized"):
        if scores[key] != ratio(sum(r[key] for r in rows), len(rows)):
            raise ValueError("topology aggregate disagrees with row counts")
    if any(
        type(r["crossings"]) is not int or not 0 <= r["crossings"] <= 7 for r in rows
    ):
        raise ValueError("topology crossing count out of grammar")
    checks["grammar"] = {
        "outcome": True,
        "reason": "Frozen coordinate-fixture grammar and PD scorer; evaluation split retired",
        "sources": sources,
    }
    return {"scope": data["scope"], "scores": scores, "sources": sources}, checks


def topology_markdown(report):
    evidence = report.get("topology")
    if not evidence or evidence["scores"] is None:
        return [
            "## Topology",
            "",
            "No committed topology self-consistency receipt.",
            "",
        ]
    s = evidence["scores"]
    lines = [
        "## Topology coordinate self-consistency (not G5)",
        "",
        "Exact render geometry → crossings → PD. No image perception; public family split retired. No external set. Invariant agreement would not verify transcription.",
        "",
        "| Metric | Numerator / denominator | Value |",
        "| --- | --- | --- |",
    ]
    for label, value in [
        ("Exact PD lists", s["exact"]),
        ("Canonicalized PD lists", s["canonicalized"]),
        ("Crossing micro", s["micro"]),
        ("Crossing macro", s["macro"]),
        ("Orientation micro", s["orientation"]["micro"]),
        ("Orientation macro", s["orientation"]["macro"]),
        ("Component validity", s["component_validity"]),
        ("Knot type", s["knot_type"]),
        ("Invariant consistency", s["invariant_consistency"]),
    ]:
        lines.append(
            f"| {label} | {value['numerator']} / {value['denominator']} | {value['value']} |"
        )
    return lines + [
        "",
        "Nulls: exact PD N/A; conditional complete orientation 2^(-c) per diagram, mean "
        + str(s["nulls"]["orientation_complete"]["mean"])
        + "; knot-type "
        + str(s["nulls"]["knot_type"])
        + ".",
        "",
        "Intervals unavailable: finite public regression census. Full row counts and unknowns are retained in SUMMARY.json.",
        "",
    ]
