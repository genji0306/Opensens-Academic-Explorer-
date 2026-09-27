import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mve.classifier.catalogue import catalogue, prompt
from mve.classifier.runtime import decide, OfflineLLM
from mve.classifier.learning import label_sets, support, training_rows
from mve.classifier.audit import sample
from mve.classifier.artifacts import digest_file, resolve_path, portable
from mve.classifier.spike import fit_head, export_head, parity, SpikeConfig
from mve.verdicts.catalogue import LABELS
from tests.mve.test_verdict_labels import label, record, split_for


def test_catalogue_and_complete_input():
    questions = catalogue()
    assert set(questions) == set(LABELS)
    for qid, q in questions.items():
        assert tuple(q["labels"]) == LABELS[qid]
        assert q["abstention"] not in q["labels"]
        assert q["activation_stage"] in (2, 3, 5)
        text = prompt(qid, "fixture state")
        assert text.count("<<LABEL>>") == len(q["labels"]) + 1
        assert "<<SEP>>" in text and "fixture state" in text
    assert "Evaluate proposition:" in prompt("Q-drift-flag", "state")
    assert questions["Q-mark-type"]["track"] == "annotated_problem"


def engine(tokens=30, scores=(10.0, 0.0, -10.0)):
    return SimpleNamespace(
        tokenize=lambda text: [1] * tokens,
        forward=lambda ids: scores,
        temperature=lambda k: 1.0,
    )


def policy(active=True):
    return {
        "sha256": "a" * 64,
        "weights_sha256": "b" * 64,
        "questions": {q: {"enabled": active, "low": 0.5, "high": 0.7} for q in LABELS},
    }


def run(**kwargs):
    args = dict(
        qid="Q-track",
        state="a diagram",
        engine=engine(),
        lock=policy(),
        stage=2,
        evidence=True,
        track="appearance_only",
    )
    args.update(kwargs)
    return decide(**args)


def test_routes_and_abstention():
    assert run().route == "act"
    assert run().weights_sha256 == "b" * 64
    assert run(lock=policy(False)).reason == "disabled"
    assert run(stage=1).reason == "inactive_stage"
    assert run(evidence=False).reason == "missing_evidence"
    assert run(mechanical_failure=True).route == "stop"
    assert run(measurements=0).route == "stop"
    assert run(engine=engine(scores=(0.0, 0.0, 10.0))).abstained
    assert run(engine=engine(513)).reason == "token_limit"
    assert run(engine=engine(512)).input_tokens == 512
    assert run(qid="Q-mark-type").reason == "inactive_track"
    assert run(engine=engine(scores=(0.0, 0.0, -100.0))).route == "human"
    middle = run(engine=engine(scores=(0.4, 0.0, -100.0)))
    assert middle.route == "human" and middle.requested_route == "llm"
    assert middle.trace == ("code", "openjev", "llm_refused_offline", "human")
    with pytest.raises(RuntimeError, match="offline"):
        OfflineLLM().ask("anything")


@pytest.mark.parametrize("high,low", [(1.1, 0.5), (0.7, 0.8), (0.69, 0.5), (0.7, -1)])
def test_invalid_thresholds(high, low):
    p = policy()
    p["questions"]["Q-track"].update(high=high, low=low)
    with pytest.raises(ValueError):
        run(lock=p)


def test_malformed_outputs_fail_closed_and_boundary_belongs_lower():
    for scores in [(float("nan"), 1, 0), (1, 2), (float("inf"), 0, 0)]:
        assert run(engine=engine(scores=scores)).reason == "invalid_output"
    from mve.classifier.runtime import confidence_route

    assert confidence_route(0.5, 0.5, 0.7) == "human"
    assert confidence_route(0.7, 0.5, 0.7) == "llm"
    assert confidence_route(0.70001, 0.5, 0.7) == "act"
    invalid = engine()
    invalid.temperature = lambda k: 0
    assert run(engine=invalid).reason == "invalid_output"


def test_labels_use_wp8a_resolution_and_fit_only():
    r = label(label(record()), "human:alice", "merge")
    bundle = label_sets([r], split_for(r))
    assert bundle["training"][0]["label"] == "merge"
    assert bundle["training"][0]["weight"] == 1.0
    assert not bundle["evaluation"] and not bundle["calibration"]
    assert training_rows(bundle["training"]) == bundle["training"]
    for split in ["sealed", "evaluation", "calibration", "development", "retrieval"]:
        with pytest.raises(ValueError, match="fit"):
            training_rows([dict(bundle["training"][0], split=split)])
    with pytest.raises(ValueError):
        training_rows([dict(bundle["training"][0], weight=0.5)])
    counts = support(bundle)
    assert not any(v["enabled"] for v in counts.values())
    full = {s: [] for s in bundle}
    for s in full:
        full[s] = [
            dict(question=q, label=label_name, image_sha256=f"{q}-{label_name}-{i}")
            for q, ls in LABELS.items()
            for label_name in ls
            for i in range(10)
        ]
    assert all(v["enabled"] for v in support(full).values())
    full["training"] *= 2
    assert support(full)["Q-track"]["counts"]["training"]["appearance_only"] == 10


def test_audit_is_seeded_act_only_and_reports_uncovered_strata():
    rows = [
        dict(id=f"d{i}", wave="w", route="act", question_id=f"Q-{i%3}")
        for i in range(21)
    ]
    rows += [dict(id="human", wave="w", route="human", question_id="Q-other")]
    a = sample(rows, wave="w", seed="fixed", manager="model:opus", judge="human:alice")
    assert a == sample(
        list(reversed(rows)),
        wave="w",
        seed="fixed",
        manager="model:opus",
        judge="human:alice",
    )
    assert a["sample_size"] == 3 and a["population_size"] == 21
    assert set(a["selected_ids"]) <= {r["id"] for r in rows if r["route"] == "act"}
    assert (
        sample([], wave="w", seed="fixed", manager="a", judge="b")["sample_size"] == 0
    )
    with pytest.raises(ValueError):
        sample(rows, wave="w", seed="fixed", manager="a", judge="a")
    with pytest.raises(ValueError):
        sample(rows + [rows[0]], wave="w", seed="fixed", manager="a", judge="b")


def test_paths_hashes_and_committed_artifacts():
    root = Path(__file__).resolve().parents[2]
    assert resolve_path("$HOME/test") == Path.home() / "test"
    assert resolve_path("mve/DEPS.lock") == root / "mve/DEPS.lock"
    assert portable(str(Path.home() / "test")) == "$HOME/test"
    assert len(digest_file(root / "mve/DEPS.lock")) == 64
    import subprocess

    files = (
        subprocess.check_output(["git", "ls-files", "-z", "mve"], cwd=root)
        .decode()
        .split("\0")
    )
    forbidden = b"/" + b"Users/"
    assert not [p for p in files if p and forbidden in (root / p).read_bytes()]


def test_bounded_weighted_head_checkpoint_export_parity(tmp_path):
    x = np.array([[2, -1, 0], [0, 2, -1], [1, 0, 0]], dtype=np.float32)
    y = np.array([0, 1, 1])
    weights = np.array([1.0, 0.5, 1.0])
    w, b, report = fit_head(x, y, weights, SpikeConfig(epochs=2, max_steps=3))
    assert report["steps"] == 2 and report["changed_parameters"] > 0
    model = tmp_path / "head.onnx"
    export_head(w, b, model)
    result = parity(x, w, b, model)
    assert result["argmax_matches"] == 3 and result["max_abs_error"] < 1e-5
    for kwargs in [
        dict(epochs=0),
        dict(epochs=4),
        dict(max_steps=21),
        dict(learning_rate=0),
    ]:
        with pytest.raises(ValueError):
            SpikeConfig(**kwargs)
    with pytest.raises(ValueError):
        fit_head(x, y, np.array([1.0, -1, 1.0]), SpikeConfig())


class Tokenizer:
    @classmethod
    def from_file(cls, path):
        return cls()

    def no_truncation(self):
        pass

    def no_padding(self):
        pass

    def encode(self, text, add_special_tokens):
        assert add_special_tokens
        return SimpleNamespace(ids=[1, 2, 3])


def test_artifact_lock_verification_and_local_engine(tmp_path, monkeypatch):
    import sys
    import mve.classifier.runtime as runtime
    from mve.classifier.artifacts import load_lock, verify_files, digest_json

    cal = tmp_path / "cal.json"
    cal.write_text('{"temperature": 1, "per_k": {"3": 2}}')
    entries = [
        dict(role=role, path=str(cal), sha256=digest_file(cal))
        for role in ["model", "tokenizer", "calibrator"]
    ]
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"artifacts": entries}))
    assert load_lock(lock)["sha256"] == digest_file(lock)
    assert len(digest_json({"a": 1})) == 64
    assert portable({"paths": [str(Path.home()), 2]}) == {"paths": ["$HOME", 2]}
    with pytest.raises(ValueError, match="hash"):
        verify_files([dict(path=str(cal), sha256="bad")])

    monkeypatch.setitem(sys.modules, "tokenizers", SimpleNamespace(Tokenizer=Tokenizer))
    import onnxruntime

    monkeypatch.setattr(
        onnxruntime,
        "InferenceSession",
        lambda *a, **kw: SimpleNamespace(run=lambda *a: [np.array([[1, 2, 3]])]),
    )
    e = runtime.LocalEngine(entries)
    assert e.tokenize("x") == [1, 2, 3]
    assert e.temperature(3) == 2 and e.temperature(4) == 1
    assert list(e.forward([1])) == [1, 2, 3]
    with pytest.raises(ValueError):
        e.forward([1] * 513)
    e.calibrator["temperature"] = 0
    with pytest.raises(ValueError):
        e.temperature(2)


def test_training_refuses_duplicates_and_reports_no_gate(tmp_path, monkeypatch):
    from mve.classifier.learning import no_update

    bundle = label_sets([label(record())], split_for(record()))
    with pytest.raises(ValueError, match="duplicate"):
        training_rows(bundle["training"] * 2)
    assert no_update(bundle)["g2"] == "G2 not established"
    with pytest.raises(ValueError):
        export_head(np.zeros((2, 3)), np.zeros(2), tmp_path / "bad.onnx")
    import mve.classifier.spike as spike

    times = iter([0, 1000])
    monkeypatch.setattr(spike.time, "monotonic", lambda: next(times))
    _, _, result = fit_head([[1, 2, 3]], [0], [1.0], SpikeConfig())
    assert result["steps"] == 0


def test_spike_runner_real_exports_and_no_promotion(tmp_path, monkeypatch, capsys):
    import mve.classifier.run_spike as runner

    e = engine(scores=(2.0, 1.0, 0.0, -1.0))
    result = runner.run(e, policy(False), tmp_path)
    assert result["training_rows"] == 4 and result["training_families"] == 1
    assert result["human_rows"] == result["manager_rows"] == 2
    assert result["checkpoint_array_equal"]
    assert result["onnx_parity"]["argmax_matches"] == 3
    assert result["production_promotion"] is False
    monkeypatch.setattr(runner, "load_lock", lambda: {"artifacts": [], **policy(False)})
    monkeypatch.setattr(runner, "LocalEngine", lambda a: e)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    assert runner.main() == 0
    assert "G2 not established" in capsys.readouterr().out
    with pytest.raises(ValueError, match="token cap"):
        runner.encode(engine(513), ["too long"], "Q-track")


def test_preflight_publication_localizes_paths_and_keeps_hashes(tmp_path):
    from mve.preflight.core import write_report

    home_path = str(Path.home() / "fixture")
    write_report(
        tmp_path,
        [{"command": [home_path], "stdout": home_path}],
        [{"path": home_path, "sha256": "a" * 64}],
    )
    report = json.loads((tmp_path / "report.json").read_text())
    lock = json.loads((tmp_path / "DEPS.lock").read_text())
    assert report["checks"][0]["stdout"] == "$HOME/fixture"
    assert lock["files"][0] == {"path": "$HOME/fixture", "sha256": "a" * 64}
