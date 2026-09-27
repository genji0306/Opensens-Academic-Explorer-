"""Family-keyed label exports; sealed/evaluation data never enter training output."""

from mve.validation import active, require
from mve.verdicts.catalogue import LABELS, ABSTENTIONS

PURPOSES = {
    "training": {"fit"},
    "calibration": {"calibration"},
    "evaluation": {"evaluation", "sealed"},
}


def selected_labels(data, *, verdicts=False):
    revisions = {}
    for event in data["events"]:
        for key in event["touches"]:
            revisions[key] = event["to_revision"]
    groups = {}
    for j in data["judgments"]:
        if (
            active(j)
            and (verdicts or (j["question"] in LABELS and j["verdict"] in {"label", *ABSTENTIONS}))
            and j["judge"].startswith(("human:", "model:"))
        ):
            require(j["id"] in revisions, "label lacks revision event provenance")
            groups.setdefault((j["target"], j["question"]), []).append(j)
    for key, judgments in sorted(groups.items()):
        winner = max(
            judgments,
            key=lambda j: (
                j["judge"].startswith("human:"),
                revisions[j["id"]],
                int(j["id"].split("_")[1]),
            ),
        )
        if verdicts or winner["verdict"] == "label":
            conflicts = sorted(
                j["id"]
                for j in judgments
                if (j["verdict"], j.get("label")) != (winner["verdict"], winner.get("label"))
            )
            yield winner, revisions[winner["id"]], conflicts


def export_labels(records, split, *, purpose="training"):
    """Split item IDs must be image SHA256s, including each alternative rendering."""
    return export_rows(records, split, purpose=purpose, verdicts=False)


def export_verdicts(records, split, *, purpose="training"):
    """Export resolved visibility/adoption/abstention evidence without inventing labels."""
    return export_rows(records, split, purpose=purpose, verdicts=True)


def export_rows(records, split, *, purpose, verdicts):
    require(purpose in PURPOSES, "unknown export purpose")
    manifest = split.manifest()
    require(not manifest["retired"], "retired split cannot be used for label exports")
    items = {row["id"]: row for row in manifest["items"]}
    rows, seen, contents = [], set(), {}
    for record in records:
        data = record.to_dict()
        image = data["image"]["sha256"]
        require(image in items, "record image missing from frozen family split")
        item = items[image]
        require(image not in seen, "duplicate record image; supply only current revision")
        seen.add(image)
        content = data["content_hash"]
        require(
            contents.setdefault(content, item["split"]) == item["split"],
            "same mathematical content crosses splits",
        )
        truth = data["image"].get("truth")
        if truth:
            require(
                (truth["family"], truth["split"]) == (item["family"], item["split"]),
                "record truth family/split conflicts with frozen split",
            )
        if item["split"] not in PURPOSES[purpose]:
            continue
        for judgment, revision, conflicts in selected_labels(data, verdicts=verdicts):
            rows.append(label_row(data, item, judgment, revision, conflicts, split.sha256))
    return sorted(rows, key=lambda r: (r["family"], r["image_sha256"], r["target"], r["question"]))


def label_row(data, item, judgment, revision, conflicts, split_sha):
    human = judgment["judge"].startswith("human:")
    return {
        "schema": "mve-label-row-v1",
        "family": item["family"],
        "split": item["split"],
        "split_sha256": split_sha,
        "image_sha256": data["image"]["sha256"],
        "content_hash": data["content_hash"],
        "record_id": data["record_id"],
        "record_revision": data["revision"],
        "judgment_revision": revision,
        "judgment_id": judgment["id"],
        "target": judgment["target"],
        "question": judgment["question"],
        "label": judgment.get("label"),
        "verdict": judgment["verdict"],
        "abstained": judgment["verdict"] in ABSTENTIONS,
        "label_scope": "catalogue" if judgment["question"] in LABELS else judgment["question"],
        "actor": judgment["judge"],
        "actor_kind": "human" if human else "model",
        "weight": 1.0 if human else 0.5,
        "at": judgment["at"],
        "conflicting_judgments": conflicts,
    }
