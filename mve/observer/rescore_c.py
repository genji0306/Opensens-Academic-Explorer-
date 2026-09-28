"""Read-only retrospective v3 diagnostics for committed WO-6b live cards.

No prose-to-data substitution: only exact source_gaps permits new numerical
exploration. Old statistics/directions remain historical; diagnostics are not
claim confirmations and no retrospective card becomes comparative.
"""

import argparse
import json
from pathlib import Path
from mve.observer import development_c as dev, feature_power as fp, features as f
from mve.observer.card import digest

ROOT = dev.ROOT
EVIDENCE = Path("docs/mve/reviews/wo6b-live/report.json")
TAG_MAP = {
    "histogram_peak": ["modality_x"],
    "density_gradient": ["density_linear_x", "density_linear_y", "density_radial"],
    "symmetry_axis": ["reflection_x", "reflection_y"],
    "point_cluster": ["modality_x", "modality_y"],
}
EXCLUDED = {
    "curve_shape": "May name reference curves or sphere guides; no data-bound v3 equivalent.",
    "histogram_tail": "Unspecified tail boundary/baseline; no exact v3 check.",
    "void": "Unspecified region/area; no exact whole-sample mapping.",
    "spacing_gap": "Unspecified individual gap; use explicit two-sample spacing_ks.",
    "spiral_arm": "Shared coordinate map alone is not a data difference.",
    "intersection": "Guide/coordinate intersections can be invariant.",
}


def rescore():
    old = json.loads((ROOT / EVIDENCE).read_text())
    rows = []
    for row in old["slots"]:
        card = row.get("card")
        if not card:
            continue
        p = card["proposal"]
        module = row["module"]
        field = p["testable_form"]["data"]
        tags = sorted(
            {
                o["feature_tag"]
                for o in card["observations"]
                if o["id"] in p["observation_ids"]
            }
        )
        allowed = field == "source_gaps" and module in dev.ZERO
        checks = []
        if allowed:
            data = dev.original(module, "real" if row["arm"] == "real" else "null")
            checks = [fp.check(module, t, field, data) for t in f.tags(module)]
        r = dict(
            job=row["job"],
            slot=row["slot"],
            module=module,
            arm=row["arm"],
            original_data=field,
            old_tags=tags,
            v3_candidates=sorted(
                {
                    t
                    for oldtag in tags
                    for t in TAG_MAP.get(oldtag, [])
                    if t in f.tags(module)
                }
            ),
            excluded_tags={t: EXCLUDED[t] for t in tags if t in EXCLUDED},
            one_sample_diagnostics=checks,
            status="diagnostics_only" if allowed else "unavailable",
            claim_validated=False,
            comparative_status="unavailable_no_pair_or_side",
            reason="Exact exported source_gaps permits descriptive diagnostics; original prose statistic is not rewritten."
            if allowed
            else "Data field does not exactly name exported source_gaps or the pinned projected coordinates; no pixel/3D/index substitution.",
        )
        rows.append(r)
    result = dict(
        schema="mve-wo6c-wo6b-rescore-v1",
        source=EVIDENCE.as_posix(),
        source_sha256=__import__("hashlib")
        .sha256((ROOT / EVIDENCE).read_bytes())
        .hexdigest(),
        rows=rows,
        total=len(rows),
        diagnostic_rows=sum(r["status"] == "diagnostics_only" for r in rows),
        unavailable=sum(r["status"] == "unavailable" for r in rows),
        comparative_cards=0,
        hosted_calls=0,
        inferential=False,
        limitations="Retrospective feature candidates are declared vocabulary translations, not fresh perception or validation of the original claim.",
    )
    return {**result, "sha256": digest(result)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    from mve.observer.storage import encoded

    raw = encoded(rescore())
    if a.output.resolve().is_relative_to(
        (ROOT / "docs/mve/reviews/wo6b-live").resolve()
    ):
        raise ValueError("live evidence is read-only")
    with a.output.open("xb") as stream:
        stream.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
