"""Offline G3 fixture counts, with explicit syntax faults and structural controls."""

import json
from pathlib import Path
from mve.formalizer.tasks import build_tasks
from mve.formalizer.emitter import emit, HEADER, native
from mve.formalizer.ir import build_ir
from mve.formalizer.repairs import (
    Candidate,
    inspect_candidate,
    syntax_fixture,
    run_attempts,
    require_task,
)
from mve.formalizer.equivalence import assess, LEVELS, proposition_hash
from mve.formalizer.retrieval import examples, nearest
from mve.formalizer.runtime import compile_source, sha
from mve.identity import digest


def controls(ir, retrieval):
    canonical = emit(ir)
    mapping = {b["name"]: f"p{i}" for i, b in enumerate(ir["binders"])}
    goal = native(ir["goal"]["proposition"], mapping)
    return {
        "empty": Candidate.make(ir, ""),
        "trivial": Candidate.make(ir, HEADER + "def statement : Prop := True\n"),
        "nearest_retrieval": Candidate.make(retrieval, emit(retrieval)),
        "weakened": Candidate.make(
            ir, canonical.replace(f"({goal})\n", f"(({goal}) ∨ True)\n")
        ),
        "strengthened": Candidate.make(
            ir, canonical.replace(f"({goal})\n", f"(({goal}) ∧ False)\n")
        ),
        "vacuous": Candidate.make(
            ir, HEADER + "def statement : Prop := False → False\n"
        ),
        "unrelated_but_provable": Candidate.make(
            ir, HEADER + "def statement : Prop := 0 = (0 : Nat)\n"
        ),
    }


def checked(source, project, output, cache):
    key = sha(source.encode())
    if key not in cache:
        receipt = compile_source(source, project, output / "checks" / key)
        if receipt["statement_sha256"] != key or receipt["proof_checked"] is not False:
            raise ValueError("mismatched statement typecheck receipt")
        cache[key] = receipt
    return cache[key]


def evaluate_task(record, catalog, index, project, output, cache):
    ir = build_ir(record)
    source = syntax_fixture(ir) if index % 5 == 0 else emit(ir)
    require_task(ir)

    def compiler(source, project, directory, **kwargs):
        return checked(source, project, output, cache)

    candidate, attempts, status = run_attempts(
        ir, Candidate.make(ir, source), (), project, output, 3, 60, compiler=compiler
    )
    first, final = attempts[0]["typecheck"], attempts[-1]["typecheck"]
    evidence = assess(ir, ir, candidate.source)
    if status != "typechecked":
        evidence.update(level="unresolved", basis="typecheck failed")
    variants = controls(ir, nearest(ir, catalog).ir())
    detections = {
        name: inspect_candidate(ir, candidate) for name, candidate in variants.items()
    }
    return {
        "image_sha256": record.to_dict()["image"]["sha256"],
        "ir_sha256": digest(ir),
        "proposition_sha256": proposition_hash(ir),
        "first_pass": first,
        "post_repair": final,
        "syntax_fault_injected": index % 5 == 0,
        "equivalence": evidence,
        "controls": detections,
        "attempts": attempts,
    }


def run(output, *, count=100, project=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    project = project or Path(__file__).resolve().parents[1] / "lean"
    tasks, retrieval, split = build_tasks(count)
    catalog = examples(retrieval, split)
    (output / "split.json").write_text(split.payload)
    cache = {}
    rows = [
        evaluate_task(r, catalog, i, project, output, cache)
        for i, r in enumerate(tasks)
    ]
    for i, record in enumerate(tasks):
        (output / f"task-{i:03}.json").write_text(record.to_json())
    report = summarize(rows, cache, split)
    (output / "tasks.json").write_text(
        json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n"
    )
    (output / "g3.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def summarize(rows, cache, split):
    references = rows[:50]
    return {
        "schema": "mve-g3-offline-v1",
        "tasks": len(rows),
        "first_pass_well_typed": sum(r["first_pass"]["ok"] for r in rows),
        "post_repair_well_typed": sum(r["post_repair"]["ok"] for r in rows),
        "injected_syntax_faults": sum(r["syntax_fault_injected"] for r in rows),
        "reference_tasks": len(references),
        "semantic_rubric_passes": 0,
        "equivalence_counts": {
            level: sum(r["equivalence"]["level"] == level for r in references)
            for level in LEVELS
        },
        "controls": {
            name: {
                "total": len(rows),
                "detected": sum("refusal" in r["controls"][name] for r in rows),
            }
            for name in rows[0]["controls"]
        },
        "unique_compiler_inputs": len(cache),
        "compiler_error_inputs": sum(not r["ok"] for r in cache.values()),
        "unique_canonical_statements": len(
            {r["post_repair"]["statement_sha256"] for r in rows}
        ),
        "split_sha256": split.sha256,
        "null": "N/A",
        "hosted_calls": 0,
        "proof_checked": False,
        "g3_pass": False,
        "scope": "WP-2 exact-positive constructions; 3 authored task templates; first 50 are structural reference comparisons only",
        "gaps": [
            "no independent blinded semantic rubric",
            "no kernel equivalence evidence",
            "no model formalization or repair evaluation",
            "LeanGeo absent",
        ],
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
