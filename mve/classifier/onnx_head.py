"""Dependency-free ONNX writer for exactly MatMul + Add, float32 rank-two input.

Encodes the public ONNX protobuf wire fields; no graph conversion or model parsing.
ORT loads and executes every export in the parity check. This deliberately small
writer is needed because ONNX's Python package is not installed locally.
"""

from pathlib import Path
import numpy as np


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result) + bytes([value])


def integer(field, value):
    return varint(field << 3) + varint(value)


def blob(field, value):
    value = value.encode() if isinstance(value, str) else value
    return varint((field << 3) | 2) + varint(len(value)) + value


def tensor(name, values):
    values = np.asarray(values, dtype="<f4")
    return (
        b"".join(integer(1, n) for n in values.shape)
        + integer(2, 1)
        + blob(8, name)
        + blob(9, values.tobytes())
    )


def value_info(name, width):
    shape = blob(1, blob(2, "batch")) + blob(1, integer(1, width))
    return blob(1, name) + blob(2, blob(1, integer(1, 1) + blob(2, shape)))


def node(op, inputs, output):
    return b"".join(blob(1, x) for x in inputs) + blob(2, output) + blob(4, op)


def export_head(weights, bias, path):
    weights, bias = np.asarray(weights), np.asarray(bias)
    if weights.ndim != 2 or bias.shape != (weights.shape[1],):
        raise ValueError("linear head shape mismatch")
    graph = (
        blob(1, node("MatMul", ["logits", "weight"], "product"))
        + blob(1, node("Add", ["product", "bias"], "adapted_logits"))
        + blob(2, "mve-frozen-openjev-logit-head")
        + blob(5, tensor("weight", weights))
        + blob(5, tensor("bias", bias))
        + blob(11, value_info("logits", weights.shape[0]))
        + blob(12, value_info("adapted_logits", weights.shape[1]))
    )
    model = (
        integer(1, 8) + blob(2, "mve-wp5") + blob(7, graph) + blob(8, integer(2, 13))
    )
    Path(path).write_bytes(model)
