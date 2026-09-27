# G3 task-set packet — Astra, 2026-09-27

Base: `mve/integration` at `c3075d8bed30446b9a53fd5e07e10d1006c02094`.
Branch: `codex/mve-g3-taskset`. Built entirely offline in the assigned worktree;
no network, downloads, hosted calls, pushes, or fabricated reviewer judgments.

The replacement packet has **100 sealed tasks / 100 unique canonical statements**
covering all nine P1 predicates, **50 independent-family reference tasks / 50 unique
reference statements**, 18 development tasks and two retrieval examples. Files are
under `mve/formalizer/fixtures/g3-taskset/`: deterministic compressed authoring packet,
readable summary, and blank JSON/CSV rubric sheets. The archive includes the twenty
selected WP-2 truth artifacts, construction provenance and complete validated records.
Canonical uniqueness is deterministic emitted-source SHA-256 after registry argument
canonicalization and fixed binder mapping; it is not logical-inequivalence testing.

| Predicate | Sealed | Initial quota | Available unique in scan |
|---|---:|---:|---:|
| Collinear | 5 | 12 | 5 |
| Concyclic | 4 | 11 | 4 |
| Parallel | 18 | 11 | 25 |
| Perpendicular | 14 | 11 | 14 |
| EqualLength | 17 | 11 | 40 |
| EqualAngle | 17 | 11 | 411 |
| Midpoint | 3 | 11 | 3 |
| SBetween | 5 | 11 | 5 |
| RightAngle | 17 | 11 | 27 |

Collinear, Concyclic, Midpoint and SBetween cannot reach their quotas in the declared
scan: their exact-positive, non-premise candidates produce only 5, 4, 3 and 5 distinct
sources respectively. Repeated construction seeds are deduplicated. Remaining slots
are redistributed round-robin. Scope is seeds 0..9, with all five existing WP-2 control
recipes, per participating family; this is not an exhaustive search of 500 sealed
WP-2 diagrams. No family has been reassigned to improve a quota.

Every task states exactly the construction's premise list, plus the deduplicated union
of registry-required Distinct/NotCollinear conditions for premises and goal. The goal
is a WP-2 exact-true candidate that is not a construction premise. Tests independently
recheck all selected goals, premises and nondegeneracy in exact arithmetic. Exact truth
on construction coordinates does not prove entailment from the stated premises;
incidental-unproved candidates remain unproved. No proof artifacts are created.

## Isolation and references

The full WP-2 frozen split matches SHA-256
`63da5b93adce004b172d9c6ddd182227d6c22c9adb482fddfa8d263795dff909`.

| Group | Families and task counts | Distinct diagrams |
|---|---|---:|
| Sealed | right_triangle 77; convex_hexagon 23 | 6 |
| Development | concave_polygon 11; oblique_parallelogram 7 | 6 |
| Retrieval | circle_radius 1; orthogonal_pairs 1 | 2 |
| References | collinear_extension 42; rational_circle 8 (WP-2 calibration) | 6 |

Family sets are pairwise disjoint. References also have zero canonical-source overlap
with sealed tasks or retrieval examples. Tests enforce both separations. The loader
checks the original frozen manifest, role/count integrity, truth bindings, and source
hashes. The derived image lookup adds image aliases to the full WP-2 membership and
preserves its allocation counts.

Reference predicate counts: Collinear 8, Concyclic 8, Parallel 8, EqualLength 8,
EqualAngle 7, Midpoint 4, SBetween 7; Perpendicular and RightAngle 0. The nine-predicate
coverage requirement is met by the sealed set. Reference family allocation stays fixed.

The rubric sheets expose explicit binders/premises/goal/nondegeneracy and deterministic
reference/candidate source, with hashes binding both IRs and the candidate source.
Both sources are the deterministic emitter output; the human checks that emission's
meaning against the problem. All reviewer identities, rationales, blinded flags and
component judgments are blank. The sheets omit family, coordinates, exact classifications
and compiler outcomes. Give only the sheet to an independent human reviewer; withhold
this handoff, packet provenance and machine results until completion. Identity/blinding
remain local operator assertions; no authentication or enforced blinding is claimed.

## Harness and gate

`python3 -m mve.formalizer.g3` loads the committed packet. It reports first-pass and
post-repair counts/rates, unique canonical sources, nine predicate counts, quota gaps,
all seven controls, evidence-strength counts and human rubric passes separately.
Twenty of the 100 first-pass inputs deliberately retain the existing missing-colon
fault. These results characterize deterministic emission and bounded syntax repair;
they do not measure model formalization quality. This packet has no hosted component.

Thresholds: 80/100 first pass, 95/100 post repair, 20/50 human blinded semantic-rubric
passes. Incomplete task/reference sets cannot pass. Without human reviews, `g3_pass`
remains false with an explicit missing-rubric reason. Typechecking and machine
correspondence never substitute for human rubric acceptance. Unknown/duplicate reviews,
unbound hashes and incomplete judgments are rejected. Null remains `N/A`.

The seven controls are empty, trivial, nearest retrieval, weakened, strengthened,
vacuous and unrelated-but-provable statements. All seven are tested as per-task
preservation refusals, not independent proofs of semantic equivalence.

## Validation and remaining work

Tests were written first and observed failing before the new task-set module existed.
The reproducibility test regenerates the entire packet and compares it to the committed
archive. Gate boundary tests exercise 79/80 first pass, 94/95 post repair, and 19/20
rubric passes, with explicitly synthetic compiler/reviewer fixtures kept only in tests.

Full suite with `MVE_LEAN_PACKAGES` set: **718 passed, 7 failed**, no skips.
Every failure is the known nested `sandbox-exec` restriction (`sandbox_apply: Operation
not permitted`), including the worker-timeout expectation that cannot run its child:

- `tests/mve/test_formalizer_g3.py::test_real_lean_repairs_statement_without_proof`
- `tests/mve/test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
- `tests/mve/test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
- `tests/mve/test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
- `tests/mve/test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
- `tests/mve/test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
- `tests/mve/test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

Final focused validation: **23 passed, 1 deselected** (the named real-Lean repair test),
with **99%** coverage in `g3.py`, **99%** in `taskset.py`, **100%** in `tasks.py`
(293/295 statements covered overall). The two uncovered lines are module-entry calls;
the CLI functions are tested. Coverage used its working Python tracer fallback after
an installed C-tracer architecture warning. Command:

```bash
MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages" python3 -m pytest tests/mve/test_g3_taskset.py tests/mve/test_formalizer_g3.py tests/mve/test_formalizer_retrieval.py -k 'not real_lean' -q --cov=mve.formalizer.g3 --cov=mve.formalizer.taskset --cov=mve.formalizer.tasks --cov-report=term-missing
```

The final CSV line-ending normalization was followed by a passing CSV/JSON sheet test
(50 parseable rows, blank judgments). Ruff and `git diff --check` pass. New Python files obey the plan's 800-line file / 50-line function limits.
The archive, source files, handoff and dependency lock contain no absolute user paths.

All 122 stale files under `mve/lean/artifacts/wp6b-g3/` are removed, including the old
three-template task records and sandbox-failure receipts. Historical WP-6b lock entries
are retained; the new `G3-taskset` entry records the replacement sources and packet.
No new sandbox-failure receipts are committed. Real Lean rates remain for Opus to
establish outside the nested builder sandbox. Semantic review, kernel equivalence,
model formalization evaluation and LeanGeo remain unestablished.

## Exact commands for Opus

From this worktree, outside the builder sandbox:

```bash
export MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages"
python3 -m mve.formalizer.g3 --output mve/lean/artifacts/g3-taskset
python3 -m pytest tests/mve -q --cov=mve.formalizer.g3 --cov=mve.formalizer.taskset --cov=mve.formalizer.tasks --cov-report=term-missing
```

Inspect and commit real receipts with explicit paths after the run. To regenerate
only authoring inputs (no Lean): `python3 -m mve.formalizer.taskset`.

After an independent human has completed rubric judgments, export only completed JSON
entries and run:

```bash
python3 -m mve.formalizer.g3 --output mve/lean/artifacts/g3-taskset-reviewed --reviews /tmp/mve-g3-human-reviews.json
```

A completed entry needs its unchanged `task_id`, `reference_ir_sha256`,
`candidate_ir_sha256`, `statement_sha256`, a human reviewer identity, rationale,
`blinded: true`, and four boolean rubric components. This packet supplies none of those
human judgments. Opus reviews, merges and pushes; Astra commits locally only.
