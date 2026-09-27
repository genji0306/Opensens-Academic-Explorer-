"""Bounded offline repairs; unknown source rewrites fail closed before Lean execution."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from mve.formalizer.emitter import emit
from mve.formalizer.ir import build_ir
from mve.formalizer.equivalence import assess, binder_mapping, proposition_hash
from mve.formalizer.runtime import compile_source, formal_payload, sha, verify_project
from mve.identity import digest
from mve.record import transition
from mve.degeneracy import repeated_degenerate, excluded_identity
from mve.predicates import canonical_proposition


@dataclass(frozen=True)
class Candidate:
    payload: str
    source: str

    @classmethod
    def make(cls, ir, source):
        return cls(json.dumps(ir, sort_keys=True, allow_nan=False), source)

    def ir(self):
        return json.loads(self.payload)


def syntax_fixture(ir):
    """Single deterministic missing-colon fault, used only for repair measurements."""
    return emit(ir).replace("def statement : Prop", "def statement Prop", 1)


def inspect_candidate(reference, candidate):
    row = {
        "statement_sha256": sha(candidate.source.encode()),
        "candidate_payload_sha256": sha(candidate.payload.encode()),
    }
    try:
        ir = candidate.ir()
        row.update(
            ir_sha256=digest(ir),
            proposition_sha256=proposition_hash(ir),
            binder_sha256=digest(binder_mapping(ir)),
        )
    except (ValueError, KeyError, TypeError):
        row["refusal"] = "malformed candidate IR refused"
        return row
    if digest(reference) != digest(ir):
        row["refusal"] = "IR/evidence or binder mapping drift refused"
    elif candidate.source not in (
        emit(reference),
        emit(reference) + "\n",
        syntax_fixture(reference),
    ):
        row["refusal"] = "unrecognized source: semantic preservation not established"
    return row


def run_attempts(
    ir, initial, repairs, project, output, max_repairs, timeout, *, compiler=None
):
    compiler = compiler or compile_source
    candidate = initial or Candidate.make(ir, emit(ir))
    attempts, planned = [], iter(repairs)
    for index in range(max_repairs + 1):
        row = inspect_candidate(ir, candidate)
        row["round"] = index
        attempts.append(row)
        if "refusal" in row:
            return candidate, attempts, "refused"
        receipt = compiler(
            candidate.source, project, output / str(index), timeout=timeout
        )
        row["typecheck"] = receipt
        if (
            receipt["statement_sha256"] != row["statement_sha256"]
            or receipt["proof_checked"] is not False
        ):
            row["refusal"] = "compiler receipt does not attest this statement type"
            return candidate, attempts, "refused"
        if receipt["ok"]:
            return candidate, attempts, "typechecked"
        if index == max_repairs:
            break
        next_candidate = next(planned, None)
        if next_candidate is None:
            if candidate.source != syntax_fixture(ir):
                break
            next_candidate = Candidate.make(ir, emit(ir))
        candidate = next_candidate
    return candidate, attempts, "error"


def formalize(
    record,
    project,
    output,
    *,
    initial=None,
    repairs=(),
    max_repairs=3,
    timeout=60,
    at=None,
):
    if type(max_repairs) is not int or not 0 <= max_repairs <= 3:
        raise ValueError("repair rounds must be 0..3")
    ir = build_ir(record)
    require_task(ir)
    lock = verify_project(project)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    candidate, attempts, status = run_attempts(
        ir, initial, repairs, project, output, max_repairs, timeout
    )
    report = repair_report(ir, candidate, attempts, status)
    (output / "repair.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n"
    )
    (output / "reference.ir.json").write_text(json.dumps(ir, sort_keys=True) + "\n")
    if status == "refused":
        (output / "record.json").write_text(record.to_json())
        return record, report
    at = at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = attach(
        record, ir, candidate.source, attempts[-1]["typecheck"], project, lock, at
    )
    (output / "record.json").write_text(result.to_json())
    return result, report


def attach(record, ir, source, receipt, project, lock, at):
    formal = formal_payload(ir, source)
    payload = {
        "formal": formal,
        "lean_lock_sha": sha((Path(project) / "lock.json").read_bytes()),
        "lean_toolchain": lock["lean_toolchain"],
    }
    emitted = transition(
        record,
        "formalize",
        actor="A4",
        at=at,
        expected_revision=record.to_dict()["revision"],
        payload=payload,
    )
    if not receipt["ok"]:
        return emitted
    formal.update(
        status="typechecked",
        typecheck={
            "id": "tc_1",
            "ok": True,
            "toolchain": receipt["toolchain"],
            "log_sha256": receipt["log_sha256"],
            "depends_on": [p["id"] for p in formal["propositions"]],
        },
    )
    return transition(
        emitted,
        "formalize",
        actor="A4",
        at=at,
        expected_revision=emitted.to_dict()["revision"],
        payload=payload,
    )


def require_task(ir):
    if ir["goal"] is None or not ir["premises"]:
        raise ValueError("explicit premises and goal required")
    mapping = {b["name"]: b["entity"] or b["name"] for b in ir["binders"]}
    props = [
        canonical_proposition(n["proposition"], mapping)
        for n in [*ir["premises"], ir["goal"]]
    ]
    if props[-1] in props[:-1]:
        raise ValueError("trivial task: goal repeats an explicit premise")
    for prop in props:
        if repeated_degenerate(prop["pred"], prop["args"]) or excluded_identity(
            prop["pred"], prop["args"]
        ):
            raise ValueError("degenerate or self-identity statement refused (E1a)")
    emit(ir)  # Includes the WP-6a registry nondegeneracy guard.


def repair_report(ir, candidate, attempts, status):
    evidence = (
        assess(ir, ir, candidate.source)
        if status == "typechecked"
        else {
            "level": "unresolved",
            "semantic_acceptance": False,
            "proof_checked": False,
        }
    )
    return {
        "schema": "mve-repair-v1",
        "status": status,
        "attempts": attempts,
        "ir_sha256": digest(ir),
        "proposition_sha256": proposition_hash(ir),
        "binder_mapping": binder_mapping(ir),
        "equivalence": evidence,
        "hosted_calls": 0,
        "proof_checked": False,
    }
