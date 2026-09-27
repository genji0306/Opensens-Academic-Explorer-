"""Executable offline plumbing fixture; deliberately not a production refit."""

from dataclasses import asdict
import json
from pathlib import Path
import time
import numpy as np

from mve.classifier.artifacts import ROOT, digest_file, digest_json, load_lock, portable
from mve.classifier.catalogue import catalogue, prompt
from mve.classifier.learning import label_sets, training_rows, no_update
from mve.classifier.runtime import LocalEngine
from mve.classifier.spike import SpikeConfig, fit_head, export_head, parity
from mve.evaluation.splits import FrozenSplit
from mve.record import Record

FIXTURES = ROOT / "mve/classifier/fixtures"


def encode(engine, states, qid):
    inputs = [engine.tokenize(prompt(qid, text)) for text in states]
    if any(not 0 < len(ids) <= 512 for ids in inputs):
        raise ValueError("spike input over token cap; no truncation")
    k = len(catalogue()[qid]["labels"]) + 1
    return np.array([engine.forward(ids)[:k] for ids in inputs], dtype=np.float32), [
        len(i) for i in inputs
    ]


def load_fixture():
    payload = json.loads((FIXTURES / "training.json").read_text())
    split_text = (FIXTURES / "split.json").read_text()
    split = FrozenSplit.load(split_text, expected_sha256=payload["split_sha256"])
    records = [Record.from_dict(d) for d in payload["records"]]
    bundle = label_sets(records, split)
    rows = training_rows(bundle["training"])
    if rows != json.loads((FIXTURES / "labels.json").read_text()):
        raise ValueError("resolved WP-8a label export drift")
    qid = payload["question"]
    if not rows or any(r["question"] != qid for r in rows):
        raise ValueError(
            "fixture must contain resolved labels for exactly one question"
        )
    states = [payload["states"][r["image_sha256"]] for r in rows]
    return payload, bundle, rows, states


def run(engine, lock, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    payload, bundle, rows, states = load_fixture()
    config = SpikeConfig(**json.loads((FIXTURES / "config.json").read_text()))
    started = time.monotonic()
    x, counts = encode(engine, states, payload["question"])
    labels = catalogue()[payload["question"]]["labels"]
    y, weights = [labels.index(r["label"]) for r in rows], [r["weight"] for r in rows]
    w, b, fit = fit_head(x, y, weights, config)
    np.savez(output / "checkpoint.npz", weight=w, bias=b)
    export_head(w, b, output / "head.onnx")
    fixture_x, fixture_counts = encode(
        engine, payload["parity_states"], payload["question"]
    )
    result = parity(fixture_x, w, b, output / "head.onnx")
    saved = np.load(output / "checkpoint.npz", allow_pickle=False)
    checkpoint_equal = np.array_equal(saved["weight"], w) and np.array_equal(
        saved["bias"], b
    )
    report = receipt(lock, rows, config, fit, result, checkpoint_equal, output)
    report.update(
        training_tokens=counts,
        parity_tokens=fixture_counts,
        duration_s=time.monotonic() - started,
        learning=no_update(bundle),
    )
    (output / "receipt.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def receipt(lock, rows, config, fit, result, checkpoint_equal, output):
    return {
        "schema": "mve-classifier-spike-v1",
        "mode": "offline_only",
        "hosted_calls": 0,
        "question": "Q-agree-action",
        "fixture_only": True,
        "scope": "new linear head over frozen openJev logits; not original-head refit",
        "production_promotion": False,
        "production_lock_sha256": lock["sha256"],
        "model_sha256": lock["weights_sha256"],
        "label_set_sha256": digest_json(rows),
        "training_rows": len(rows),
        "training_families": len({r["family"] for r in rows}),
        "human_rows": sum(r["actor_kind"] == "human" for r in rows),
        "manager_rows": sum(r["actor_kind"] == "model" for r in rows),
        "actor_identity": "synthetic fixture assertions, not authenticated people or gold",
        "config": asdict(config),
        "fit": fit,
        "onnx_parity": result,
        "checkpoint_array_equal": bool(checkpoint_equal),
        "artifacts": [
            {"path": portable(str(output / name)), "sha256": digest_file(output / name)}
            for name in ["checkpoint.npz", "head.onnx"]
        ],
    }


def main():
    from mve.preflight.guard.sitecustomize import guard
    import sys

    sys.addaudithook(guard)
    lock = load_lock()
    engine = LocalEngine(lock["artifacts"])
    result = run(engine, lock, ROOT / "mve/generated/wp5-spike")
    print(json.dumps(result, indent=2, sort_keys=True))
    return (
        0 if result["onnx_parity"]["passed"] and result["checkpoint_array_equal"] else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
