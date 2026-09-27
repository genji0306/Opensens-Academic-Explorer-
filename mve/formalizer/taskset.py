"""WP-2 exact-truth authoring and frozen explicit-input statements for offline G3."""

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from mve.degeneracy import required_nondegeneracy
from mve.evaluation.splits import FrozenSplit, canonical
from mve.formalizer.emitter import emit
from mve.formalizer.ir import build_ir
from mve.formalizer.runtime import sha
from mve.generator.constructions import construct
from mve.generator.corpus import DEFAULT_COUNTS, layout
from mve.generator.records import AT, record_from
from mve.generator.render import render
from mve.generator.truth import build_truth
from mve.identity import digest
from mve.record import create, Record

PREDICATES = (
    "Collinear",
    "Concyclic",
    "Parallel",
    "Perpendicular",
    "EqualLength",
    "EqualAngle",
    "Midpoint",
    "SBetween",
    "RightAngle",
)
ROOT = Path(__file__).with_name("fixtures") / "g3-taskset"
SPLIT_SEED = "mve-family-split-v1"
# The first ten seeds are present in every WP-2 partition, including calibration.
SEEDS = range(10)
QUOTAS = {pred: 12 if i == 0 else 11 for i, pred in enumerate(PREDICATES)}


def family_roles():
    split, _ = layout(DEFAULT_COUNTS, SPLIT_SEED)
    return {r["family"]: r["split"] for r in split.manifest()["items"]}


def record(row):
    return Record.from_json(canonical(row["record"]))


def problem(binders, premises, goal):
    def node(ident, prop):
        return {"id": ident, "proposition": prop, "depends_on": ["txt_1"]}

    required = {
        canonical(n): n
        for p in [*premises, goal]
        for n in required_nondegeneracy(p)
        if n not in premises
    }
    return {
        "binders": binders,
        "premises": [node(f"prm_{i}", p) for i, p in enumerate(premises, 1)],
        "nondegeneracy": [
            node(f"ndg_{i}", required[k]) for i, k in enumerate(sorted(required), 1)
        ],
        "goal": {**node("goal_1", goal), "kind": "prove"},
    }


def task_record(base, given):
    data = json.loads(canonical(base))
    data["problem"] = given
    data["image"].update(track="annotated_problem", eval_task="none")
    data["image"]["isolation"]["visible"].append("stated_givens")
    text = canonical(given)
    data["sources"].append(
        {
            "id": "txt_1",
            "kind": "text",
            "sha256": sha(text.encode()),
            "span": [0, len(text)],
            "depends_on": [],
        }
    )
    nodes = [*given["premises"], *given["nondegeneracy"], given["goal"]]
    for entity in data["entities"]:
        entity["depends_on"] = [
            n["id"] for n in nodes if entity["label"] in n["proposition"]["args"]
        ]
    return create(data, AT)


def candidates(family, seed, role, truths):
    construction = construct(family, seed)
    truth = build_truth(
        construction["coordinates"], construction["premises"], construction["generator"]
    )
    td = truth.data()
    key = truth.sha256
    truths[key] = td
    png, metadata = render(construction)
    base = record_from(truth, png, metadata, family=family, split=role).to_dict()
    for candidate in td["candidates"]:
        goal = candidate["proposition"]
        if (
            candidate["math_class"] != "true"
            or candidate["class"] == "premise"
            or goal["pred"] not in PREDICATES
        ):
            continue
        given = problem(base["problem"]["binders"], td["premises"], goal)
        # Emit before validation to cheaply deduplicate across construction seeds.
        ir = {
            "schema": "mve-formal-ir-v1",
            "binders": given["binders"],
            "exact_constants": [],
            "premises": [*given["premises"], *given["nondegeneracy"]],
            "goal": given["goal"],
        }
        statement = emit(ir)
        yield {
            "family": family,
            "seed": seed,
            "split": role,
            "predicate": goal["pred"],
            "truth_key": key,
            "candidate_id": candidate["id"],
            "problem": given,
            "base": base,
            "canonical_statement_sha256": sha(statement.encode()),
        }


def select(pool, count):
    buckets = {
        p: sorted(
            (r for r in pool if r["predicate"] == p),
            key=lambda r: r["canonical_statement_sha256"],
        )
        for p in PREDICATES
    }
    chosen = []
    # Round-robin exhausts scarce predicates and redistributes unfilled quotas.
    while len(chosen) < count and any(buckets.values()):
        for pred in PREDICATES:
            if buckets[pred] and len(chosen) < count:
                chosen.append(buckets[pred].pop(0))
    if len(chosen) != count:
        raise ValueError(
            f"only {len(chosen)} distinct statements available; need {count}"
        )
    result = []
    for row in chosen:
        row = dict(row)
        rec = task_record(row.pop("base"), row.pop("problem"))
        result.append({**row, "record": rec.to_dict()})
    return result


def generate_packet():
    roles, truths, pools = family_roles(), {}, {}
    for role in ("sealed", "calibration", "development", "retrieval"):
        unique = {}
        for family in sorted(f for f in roles if roles[f] == role):
            for seed in SEEDS:
                for row in candidates(family, seed, role, truths):
                    unique.setdefault(row["canonical_statement_sha256"], row)
        pools[role] = list(unique.values())
    groups = {
        "sealed": select(pools["sealed"], 100),
        "development": select(pools["development"], 18),
    }
    # Retrieval's API is image-bound: keep one example per family/image.
    groups["retrieval"] = [
        select([r for r in pools["retrieval"] if r["family"] == f], 1)[0]
        for f in sorted(f for f in roles if roles[f] == "retrieval")
    ]
    excluded = {
        r["canonical_statement_sha256"]
        for group in ("sealed", "retrieval")
        for r in groups[group]
    }
    groups["references"] = select(
        [
            r
            for r in pools["calibration"]
            if r["canonical_statement_sha256"] not in excluded
        ],
        50,
    )
    used = {r["truth_key"] for rows in groups.values() for r in rows}
    split, _ = layout(DEFAULT_COUNTS, SPLIT_SEED)
    return {
        "schema": "mve-g3-taskset-v1",
        **groups,
        "wp2_split": split.manifest(),
        "wp2_split_sha256": split.sha256,
        "truth": {k: truths[k] for k in sorted(used)},
        "summary": corpus_summary(groups, pools["sealed"]),
    }


def corpus_summary(groups, available):
    counts = Counter(r["predicate"] for r in groups["sealed"])
    capacity = Counter(r["predicate"] for r in available)
    return {
        "tasks": 100,
        "reference_tasks": 50,
        "unique_canonical_statements": 100,
        "per_predicate_counts": dict(counts),
        "quotas": QUOTAS,
        "available_unique_per_predicate": dict(capacity),
        "search_seeds": list(SEEDS),
        "quota_gaps": {
            p: {
                "quota": QUOTAS[p],
                "selected": counts[p],
                "available": capacity[p],
                "reason": "Insufficient distinct statements in frozen sealed families "
                "at seeds 0..9 (all five WP-2 controls); repeated sources "
                "are deduplicated. Unfilled quota redistributed round-robin.",
            }
            for p in PREDICATES
            if counts[p] < QUOTAS[p]
        },
    }


def load_packet(root=ROOT):
    packet = json.loads(gzip.decompress((Path(root) / "packet.json.gz").read_bytes()))
    validate_packet(packet)
    return packet


def validate_packet(packet):
    frozen, _ = layout(DEFAULT_COUNTS, SPLIT_SEED)
    if (
        packet["wp2_split"] != frozen.manifest()
        or packet["wp2_split_sha256"] != frozen.sha256
    ):
        raise ValueError("WP-2 frozen split mismatch")
    roles = family_roles()
    excluded = {
        r["canonical_statement_sha256"]
        for group in ("sealed", "retrieval")
        for r in packet[group]
    }
    if any(r["canonical_statement_sha256"] in excluded for r in packet["references"]):
        raise ValueError("reference statement overlaps sealed or retrieval")
    for group, role, count in [
        ("sealed", "sealed", 100),
        ("references", "calibration", 50),
        ("development", "development", 18),
        ("retrieval", "retrieval", 2),
    ]:
        rows = packet[group]
        if (
            len(rows) != count
            or len({r["canonical_statement_sha256"] for r in rows}) != count
        ):
            raise ValueError("task count or distinct canonical statements mismatch")
        for row in rows:
            validate_row(row, role, roles, packet["truth"])


def validate_row(row, role, roles, truths):
    if (
        roles.get(row["family"]) != role
        or row["split"] != role
        or row["seed"] not in SEEDS
    ):
        raise ValueError("task family outside frozen partition or seed range")
    rec = record(row)
    data = rec.to_dict()
    origin = data["image"]["truth"]
    truth = truths[row["truth_key"]]
    goal = data["problem"]["goal"]["proposition"]
    candidate = next(
        (c for c in truth["candidates"] if c["id"] == row["candidate_id"]), None
    )
    if (
        origin["family"] != row["family"]
        or origin["split"] != role
        or truth["generator"]["seed"] != row["seed"]
        or digest(truth) != row["truth_key"]
        or data["sources"][0]["sha256"] != row["truth_key"]
        or [n["proposition"] for n in data["problem"]["premises"]] != truth["premises"]
        or not candidate
        or candidate["proposition"] != goal
        or candidate["math_class"] != "true"
        or candidate["class"] == "premise"
        or row["predicate"] != goal["pred"]
        or sha(emit(build_ir(rec)).encode()) != row["canonical_statement_sha256"]
    ):
        raise ValueError("task statement or WP-2 truth binding mismatch")


def image_split(packet):
    manifest = json.loads(canonical(packet["wp2_split"]))
    # Retain the entire frozen WP-2 membership; add record-image aliases.
    items = {r["id"]: r for r in manifest["items"]}
    for name in ("sealed", "references", "development", "retrieval"):
        for row in packet[name]:
            ident = row["record"]["image"]["sha256"]
            items[ident] = {"id": ident, "family": row["family"], "split": row["split"]}
    manifest["items"] = sorted(items.values(), key=lambda r: r["id"])
    return FrozenSplit(canonical(manifest))


def review_rows(references):
    from mve.formalizer.equivalence import assess

    rows = []
    for index, row in enumerate(references):
        ir = build_ir(record(row))
        statement = emit(ir)
        evidence = assess(ir, ir, statement)
        rows.append(
            {
                "task_id": f"reference-{index:03}",
                **{
                    k: evidence[k]
                    for k in (
                        "reference_ir_sha256",
                        "candidate_ir_sha256",
                        "statement_sha256",
                    )
                },
                "problem": row["record"]["problem"],
                "reference_statement": statement,
                "candidate_statement": statement,
                "reviewer": None,
                "rationale": None,
                "blinded": None,
                "rubric": dict.fromkeys(
                    ("binders", "premises", "goal", "nondegeneracy")
                ),
            }
        )
    return rows


def write_review_sheet(references, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = review_rows(references)
    (output / "rubric-template.json").write_text(json.dumps(rows, indent=2) + "\n")
    flat = [
        {**{k: v for k, v in r.items() if k != "rubric"}, **r["rubric"]} for r in rows
    ]
    with (output / "rubric-template.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows({**r, "problem": canonical(r["problem"])} for r in flat)


def main():
    packet = generate_packet()
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "packet.json.gz").write_bytes(
        gzip.compress(canonical(packet).encode(), mtime=0)
    )
    (ROOT / "summary.json").write_text(json.dumps(packet["summary"], indent=2) + "\n")
    write_review_sheet(packet["references"], ROOT)
    print(json.dumps(packet["summary"], indent=2))


if __name__ == "__main__":
    main()
