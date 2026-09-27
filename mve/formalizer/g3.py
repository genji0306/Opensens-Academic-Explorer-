"""Offline G3 sealed statements, disjoint references and explicit gate thresholds."""

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
from mve.formalizer.taskset import load_packet, record, write_review_sheet, PREDICATES


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
        "predicate": ir["goal"]["proposition"]["pred"],
        "canonical_statement_sha256": sha(emit(ir).encode()),
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


def evaluate_references(references, reviews, project, output, cache):
    templates = {f"reference-{i:03}": row for i, row in enumerate(references)}
    if not isinstance(reviews, list):
        raise ValueError("reviews must be a list")
    by_id = {}
    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("each reference review must be an object")
        ident = review.get("task_id")
        if ident not in templates or ident in by_id:
            raise ValueError("unknown or duplicate reference review")
        by_id[ident] = review
    rows = []
    for ident, row in templates.items():
        ir = build_ir(record(row))
        source = emit(ir)
        receipt = checked(source, project, output, cache)
        evidence = assess(ir, ir, source, review=by_id.get(ident))
        if not receipt["ok"]:
            evidence.update(level="unresolved", basis="typecheck failed")
        rows.append({"task_id": ident, "equivalence": evidence, "typecheck": receipt})
    return rows


def run(output, *, count=100, project=None, reviews=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    project = project or Path(__file__).resolve().parents[1] / "lean"
    packet = load_packet()
    tasks, retrieval, split = build_tasks(count)
    catalog = examples(retrieval, split)
    (output / "split.json").write_text(split.payload)
    cache = {}
    rows = [
        evaluate_task(r, catalog, i, project, output, cache)
        for i, r in enumerate(tasks)
    ]
    references = evaluate_references(
        packet["references"], [] if reviews is None else reviews, project, output, cache
    )
    for i, rec in enumerate(tasks):
        (output / f"task-{i:03}.json").write_text(rec.to_json())
    write_review_sheet(packet["references"], output)
    report = summarize(rows, references, cache, split, packet)
    for name, data in [("tasks", rows), ("references", references), ("g3", report)]:
        (output / f"{name}.json").write_text(
            json.dumps(data, sort_keys=True, indent=2) + "\n"
        )
    return report


def gate(*, tasks, unique, first, post, references, semantic):
    checks = [
        (tasks == 100 and unique == 100, "need 100 distinct sealed statements"),
        (first >= 80, "need at least 80/100 first-pass well-typed statements"),
        (post >= 95, "need at least 95/100 post-repair well-typed statements"),
        (references == 50, "need 50 retrieval-disjoint references"),
        (
            semantic >= 20,
            "need at least 20/50 blinded semantic rubric passes; "
            "without human reviews G3 is not established",
        ),
    ]
    reasons = [reason for ok, reason in checks if not ok]
    return {"g3_pass": not reasons, "g3_reasons": reasons}


def evidence_summary(rows, references):
    return {
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
    }


def summarize(rows, references, cache, split, packet):
    first = sum(r["first_pass"]["ok"] for r in rows)
    post = sum(r["post_repair"]["ok"] for r in rows)
    unique = len({r["canonical_statement_sha256"] for r in rows})
    semantic = sum(r["equivalence"]["semantic_acceptance"] for r in references)
    return {
        "schema": "mve-g3-offline-v2",
        "tasks": len(rows),
        "first_pass_well_typed": first,
        "post_repair_well_typed": post,
        "first_pass_rate": first / len(rows),
        "post_repair_rate": post / len(rows),
        "injected_syntax_faults": sum(r["syntax_fault_injected"] for r in rows),
        "reference_tasks": len(references),
        "semantic_rubric_passes": semantic,
        "human_reviews": sum("review" in r["equivalence"] for r in references),
        **evidence_summary(rows, references),
        "unique_compiler_inputs": len(cache),
        "compiler_error_inputs": sum(not r["ok"] for r in cache.values()),
        "unique_canonical_statements": unique,
        "per_predicate_counts": {
            p: sum(r["predicate"] == p for r in rows) for p in PREDICATES
        },
        "quota_gaps": packet["summary"]["quota_gaps"],
        "split_sha256": split.sha256,
        "wp2_split_sha256": packet["wp2_split_sha256"],
        "null": "N/A",
        "hosted_calls": 0,
        "proof_checked": False,
        **gate(
            tasks=len(rows),
            unique=unique,
            first=first,
            post=post,
            references=len(references),
            semantic=semantic,
        ),
        "scope": "WP-2 exact-true non-premise goals; deterministic emitter and syntax repair, "
        "not a model formalization benchmark; exact truth is not a derivability claim",
        "gaps": [
            "no kernel equivalence evidence",
            "no model formalization or repair evaluation",
            "LeanGeo absent",
        ],
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/mve-g3"))
    parser.add_argument(
        "--reviews", type=Path, help="completed, blinded human rubric JSON"
    )
    args = parser.parse_args(argv)
    kwargs = {"reviews": json.loads(args.reviews.read_text())} if args.reviews else {}
    print(json.dumps(run(args.output, **kwargs), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
