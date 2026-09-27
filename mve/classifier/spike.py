"""Bounded numpy logit-head training spike; the openJev encoder stays frozen."""

from dataclasses import dataclass
import math
import time
import numpy as np

from mve.classifier.onnx_head import export_head as export_head


@dataclass(frozen=True)
class SpikeConfig:
    epochs: int = 2
    max_steps: int = 4
    learning_rate: float = 0.01
    max_seconds: float = 120.0

    def __post_init__(self):
        if (
            type(self.epochs) is not int
            or not 1 <= self.epochs <= 3
            or type(self.max_steps) is not int
            or not 1 <= self.max_steps <= 20
            or not math.isfinite(self.learning_rate)
            or not 0 < self.learning_rate <= 0.1
            or not math.isfinite(self.max_seconds)
            or not 0 < self.max_seconds <= 180
        ):
            raise ValueError("spike budget exceeded or invalid configuration")


def validate_training(x, y, weights):
    if (
        x.ndim != 2
        or not 1 <= len(x) <= 64
        or x.shape[1] < 2
        or y.shape != (len(x),)
        or weights.shape != y.shape
        or not np.issubdtype(y.dtype, np.integer)
        or not np.isfinite(x).all()
        or not np.isfinite(weights).all()
        or not np.isin(weights, [1.0, 0.5]).all()
        or not ((y >= 0) & (y < x.shape[1] - 1)).all()
    ):
        raise ValueError("invalid bounded training arrays; final column is abstention")


def fit_head(x, y, weights, config):
    """Full-batch weighted cross-entropy, identity initial head, deterministic SGD."""
    x, y, weights = np.asarray(x, dtype=np.float32), np.asarray(y), np.asarray(weights)
    validate_training(x, y, weights)
    w, b = np.eye(x.shape[1], dtype=np.float32), np.zeros(x.shape[1], dtype=np.float32)
    started, losses = time.monotonic(), []
    for _ in range(min(config.epochs, config.max_steps)):
        if time.monotonic() - started >= config.max_seconds:
            break
        logits = x @ w + b
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        losses.append(
            float(
                -np.sum(
                    weights * np.log(np.maximum(probs[np.arange(len(y)), y], 1e-30))
                )
                / weights.sum()
            )
        )
        probs[np.arange(len(y)), y] -= 1
        grad = probs * (weights / weights.sum())[:, None]
        w -= config.learning_rate * (x.T @ grad)
        b -= config.learning_rate * grad.sum(axis=0)
    return (
        w,
        b,
        {
            "steps": len(losses),
            "losses": losses,
            "objective": "human=1.0, manager=0.5 weighted cross-entropy",
            "trainable_parameters": int(w.size + b.size),
            "changed_parameters": int(
                np.count_nonzero(w - np.eye(len(b))) + np.count_nonzero(b)
            ),
            "encoder_trainable": False,
            "original_openjev_head_trainable": False,
        },
    )


def parity(x, weights, bias, exported):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(
        str(exported), options, providers=["CPUExecutionProvider"]
    )
    expected = np.asarray(x, dtype=np.float32) @ weights + bias
    actual = session.run(None, {"logits": np.asarray(x, dtype=np.float32)})[0]
    error = float(np.max(np.abs(expected - actual)))
    matches = int(np.sum(expected.argmax(axis=1) == actual.argmax(axis=1)))
    return {
        "fixtures": len(x),
        "argmax_matches": matches,
        "max_abs_error": error,
        "atol": 1e-5,
        "passed": error <= 1e-5 and matches == len(x),
    }
