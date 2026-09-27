"""Pinned local ONNX inference and fail-closed workflow routing."""

from dataclasses import dataclass
from hashlib import sha256
import json
import math

from mve.classifier.artifacts import resolve_path, verify_files
from mve.classifier.catalogue import catalogue, prompt


class OfflineLLM:
    def ask(self, _request):
        raise RuntimeError("LLM tier refused: offline packet prohibits hosted calls")


class LocalEngine:
    def __init__(self, artifacts):
        verify_files(artifacts)
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        paths = {a["role"]: resolve_path(a["path"]) for a in artifacts}
        self.tokenizer = Tokenizer.from_file(str(paths["tokenizer"]))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.calibrator = json.loads(paths["calibrator"].read_text())
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(paths["model"]), options, providers=["CPUExecutionProvider"]
        )
        self.np = np

    def tokenize(self, text):
        return self.tokenizer.encode(text, add_special_tokens=True).ids

    def temperature(self, k):
        value = float(
            self.calibrator.get("per_k", {}).get(str(k), self.calibrator["temperature"])
        )
        if not math.isfinite(value) or value <= 0:
            raise ValueError("invalid pinned temperature")
        return value

    def forward(self, ids):
        if not 0 < len(ids) <= 512:
            raise ValueError("input must contain 1..512 tokens; no truncation")
        x = self.np.array([ids], dtype=self.np.int64)
        return self.session.run(
            ["logits"], {"input_ids": x, "attention_mask": self.np.ones_like(x)}
        )[0][0]


@dataclass(frozen=True)
class Decision:
    question_id: str
    state_sha256: str
    input_tokens: int
    answer: str | None
    abstained: bool
    confidence: float
    route: str
    requested_route: str
    reason: str
    trace: tuple[str, ...]
    lock_sha256: str
    weights_sha256: str
    threshold_low: float
    threshold_high: float


def confidence_route(confidence, low, high):
    return "act" if confidence > high else "llm" if confidence > low else "human"


def probabilities(scores, size, temperature):
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("invalid temperature")
    scores = list(scores)[:size]
    if len(scores) != size or not all(math.isfinite(v) for v in scores):
        raise ValueError("invalid model logits")
    scaled = [float(v) / temperature for v in scores]
    values = [math.exp(v - max(scaled)) for v in scaled]
    return [v / sum(values) for v in values]


def eligibility(q, config, *, stage, evidence, track, mechanical_failure, measurements):
    if mechanical_failure or measurements == 0:
        return "mechanical_stop"
    if not config["enabled"]:
        return "disabled"
    if stage < q["activation_stage"]:
        return "inactive_stage"
    if q["track"] != "any" and track != q["track"]:
        return "inactive_track"
    if not evidence:
        return "missing_evidence"
    return None


def decide(
    *,
    qid,
    state,
    engine,
    lock,
    stage,
    evidence,
    track,
    mechanical_failure=False,
    measurements=None,
):
    q, config = catalogue()[qid], lock["questions"][qid]
    low, high = config["low"], config["high"]
    floor = 0.9 if q["risk"] == "formal" else 0.7
    if not (0 <= low < high <= 1 and high >= floor):
        raise ValueError("invalid risk thresholds")
    text = prompt(qid, state)
    common = dict(
        question_id=qid,
        state_sha256=sha256(text.encode()).hexdigest(),
        lock_sha256=lock["sha256"],
        weights_sha256=lock["weights_sha256"],
        threshold_low=low,
        threshold_high=high,
    )
    reason = eligibility(
        q,
        config,
        stage=stage,
        evidence=evidence,
        track=track,
        mechanical_failure=mechanical_failure,
        measurements=measurements,
    )
    if reason:
        route = "stop" if reason == "mechanical_stop" else "human"
        return Decision(
            **common,
            input_tokens=0,
            answer=None,
            abstained=True,
            confidence=0.0,
            route=route,
            requested_route=route,
            reason=reason,
            trace=("code", route),
        )
    return infer(q, text, common, engine, low, high)


def infer(q, text, common, engine, low, high):
    count = 0
    try:
        ids = engine.tokenize(text)
        count = len(ids)
        if not 0 < count <= 512:
            raise OverflowError("token_limit")
        probs = probabilities(
            engine.forward(ids),
            len(q["labels"]) + 1,
            engine.temperature(len(q["labels"]) + 1),
        )
    except (ValueError, RuntimeError, OverflowError) as exc:
        reason = "token_limit" if isinstance(exc, OverflowError) else "invalid_output"
        return Decision(
            **common,
            input_tokens=count,
            answer=None,
            abstained=True,
            confidence=0.0,
            route="human",
            requested_route="human",
            reason=reason,
            trace=("code", "openjev", "human"),
        )
    index = max(range(len(probs)), key=probs.__getitem__)
    abstained = index == len(q["labels"])
    answer, confidence = (
        (None, 0.0) if abstained else (q["labels"][index], probs[index])
    )
    requested = "human" if abstained else confidence_route(confidence, low, high)
    route, trace = requested, ("code", "openjev", requested)
    reason = "abstained" if abstained else "confidence"
    if requested == "llm":
        try:
            OfflineLLM().ask(text)
        except RuntimeError:
            route, reason = "human", "llm_refused_offline"
            trace = ("code", "openjev", "llm_refused_offline", "human")
    return Decision(
        **common,
        input_tokens=count,
        answer=answer,
        abstained=abstained,
        confidence=confidence,
        route=route,
        requested_route=requested,
        reason=reason,
        trace=trace,
    )
