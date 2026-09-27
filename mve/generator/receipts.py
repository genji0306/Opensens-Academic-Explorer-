"""Receipts computed from the stored corpus, never manually asserted collision counts."""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from mve.evaluation.splits import FrozenSplit
from mve.generator.corpus import corpus_report
from mve.generator.scene import scene_from_render
from mve.record import Record


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def verify_item(root, row, roles):
    private = root / "private" / row["id"]
    public = root / "public" / row["id"]
    blobs = {
        "truth": gzip.decompress((private / "truth.json.gz").read_bytes()),
        "record": (private / "record.json").read_bytes(),
        "render": (private / "render.json").read_bytes(),
        "image": (public / "image.png").read_bytes(),
    }
    if any(sha(blob) != row[kind + "_sha256"] for kind, blob in blobs.items()):
        raise ValueError("artifact hash mismatch")
    record = Record.from_json(blobs["record"].decode()).to_dict()
    truth = record["image"]["truth"]
    if truth["split"] != row["split"] or roles[row["id"]] != row["split"]:
        raise ValueError("split labels disagree")
    if truth["math_coordinates_sha256"] != row["math_coordinates_sha256"]:
        raise ValueError("coordinate summary disagrees with record")
    if set(p.name for p in public.iterdir()) != {"image.png"}:
        raise ValueError("unexpected public artifact")
    scene_from_render(json.loads(blobs["render"]))


def audit_corpus(output):
    root = Path(output)
    raw = (root / "private/manifest.json").read_bytes()
    saved = json.loads(raw)
    frozen = FrozenSplit.load(
        (root / "private/split.json").read_text(), expected_sha256=saved["split_sha256"]
    )
    roles = {r["id"]: r["split"] for r in frozen.manifest()["items"]}
    if set(roles) != {r["id"] for r in saved["items"]}:
        raise ValueError("manifest item set mismatch")
    for row in saved["items"]:
        verify_item(root, row, roles)
    report = corpus_report(
        saved["counts"],
        frozen,
        saved["items"],
        Counter(saved["class_counts"]),
        Counter(saved["controls"]),
        saved["code_sha"],
    )
    if report != saved:
        raise ValueError("stored corpus report does not match recomputed report")
    base = {k: v for k, v in report.items() if k != "items"}
    base.update(manifest_sha256=sha(raw), artifact_root=root.name)
    audited = {
        **base,
        "artifact_hashes_verified": 4 * len(saved["items"]),
        "records_validated": len(saved["items"]),
        "scene_contracts_validated": len(saved["items"]),
        "split_labels_verified": len(saved["items"]),
        "sealed_truth_inspected_for_tuning": False,
    }
    return {**base, "receipt_kind": "generation"}, {
        **audited,
        "receipt_kind": "artifact_audit",
    }


def write_receipts(output, generation_path, audit_path):
    receipts = audit_corpus(output)
    for path, receipt in zip((generation_path, audit_path), receipts):
        Path(path).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipts
