"""Immutable truth artifacts; DDAR outcomes are frozen evidence, never recomputed on load."""

from dataclasses import dataclass
import json
import math
import re
from mve.identity import digest
from mve.predicates import canonical_proposition
from mve.generator.exact import ExactEvaluator, VERSION
from mve.generator.universe import candidate_universe


class TruthError(ValueError):
    pass


class UnavailableDDAR:
    version = "unavailable:no-local-ddar"

    def prove(self, proposition, premises, budget_s):
        return {
            "outcome": "unsupported",
            "trace_sha256": None,
            "reason": "No local DDAR backend has passed preflight; no derivation executed.",
        }


def classify_evidence(math_class, premise, receipt):
    if not isinstance(receipt, dict):
        raise TruthError("DDAR receipt must be an object")
    outcome = receipt.get("outcome")
    if outcome not in {"proved", "unknown", "timeout", "unsupported"}:
        raise TruthError("invalid DDAR outcome")
    trace = receipt.get("trace_sha256")
    if outcome == "proved" and (
        not isinstance(trace, str) or not re.fullmatch(r"[0-9a-f]{64}", trace)
    ):
        raise TruthError("proved DDAR receipt needs a trace hash")
    if math_class == "degenerate":
        return "unknown"
    if math_class == "false":
        return "evaluator_conflict" if outcome == "proved" else "false"
    return (
        "premise"
        if premise
        else "consequence"
        if outcome == "proved"
        else "incidental_unproved"
    )


@dataclass(frozen=True)
class FrozenTruth:
    payload: str

    def data(self):
        return json.loads(self.payload)

    @property
    def sha256(self):
        return digest(self.data())

    @classmethod
    def load(cls, payload, *, expected_sha256):
        # Hash the exact stored bytes, including whitespace; producer emits canonical JSON.
        import hashlib

        if hashlib.sha256(payload.encode()).hexdigest() != expected_sha256:
            raise TruthError("truth artifact hash mismatch")
        result = cls(payload)
        if result.data().get("schema") != "mve-truth-v1":
            raise TruthError("unsupported truth artifact")
        return result

    def require_fit(self):
        if not self.data()["fit_eligible"]:
            raise TruthError("evaluator_conflict: diagram excluded from every fit set")
        return self.sha256


def _inputs(coordinates, premises, generator, backend, budget_s):
    if (
        type(budget_s) not in (int, float)
        or not math.isfinite(budget_s)
        or budget_s < 0
    ):
        raise TruthError("finite nonnegative DDAR budget required")
    required = {"id", "version", "config_sha256", "seed"}
    if set(generator) != required or type(generator["seed"]) is not int:
        raise TruthError("pinned generator identity required")
    if not re.fullmatch(r"[0-9a-f]{64}", generator["config_sha256"]):
        raise TruthError("invalid generator config hash")
    if (
        not generator["id"]
        or not generator["version"]
        or not isinstance(backend.version, str)
        or not backend.version
    ):
        raise TruthError("generator and DDAR versions required")
    evaluator = ExactEvaluator(coordinates)
    candidates = candidate_universe(coordinates)
    keys = {digest(p) for p in candidates}
    premises = [canonical_proposition(p) for p in premises]
    if any(digest(p) not in keys or evaluator.classify(p) != "true" for p in premises):
        raise TruthError("every generator premise must be an exact-true candidate")
    return evaluator, candidates, premises


def build_truth(coordinates, premises, generator, backend=None, *, budget_s=0):
    backend = UnavailableDDAR() if backend is None else backend
    evaluator, candidates, premises = _inputs(
        coordinates, premises, generator, backend, budget_s
    )
    premise_keys = {digest(p) for p in premises}
    rows, defects = [], []
    for prop in candidates:
        key = digest(prop)
        mathematical = evaluator.classify(prop)
        receipt = backend.prove(
            json.loads(json.dumps(prop)), json.loads(json.dumps(premises)), budget_s
        )
        receipt = json.loads(json.dumps(receipt, allow_nan=False))
        label = classify_evidence(mathematical, key in premise_keys, receipt)
        rows.append(
            {
                "id": key,
                "proposition": prop,
                "math_class": mathematical,
                "class": label,
                "ddar": receipt,
            }
        )
        if label == "evaluator_conflict":
            defects.append({"kind": "evaluator_conflict", "candidate_id": key})
    artifact = {
        "schema": "mve-truth-v1",
        "generator": {
            **generator,
            "coordinates_exact": True,
            "evaluator_version": VERSION,
            "ddar_version": backend.version,
            "ddar_budget_s": budget_s,
        },
        "registry_version": "v1",
        "math_coordinates": coordinates,
        "math_coordinates_sha256": digest(coordinates),
        "premises": premises,
        "candidate_universe_sha256": digest(candidates),
        "candidates": rows,
        "fit_eligible": not defects,
        "defects": defects,
    }
    return FrozenTruth(
        json.dumps(artifact, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )
