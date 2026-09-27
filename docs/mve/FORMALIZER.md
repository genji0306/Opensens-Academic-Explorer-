# WP-6b offline formalizer

`mve.formalizer.formalize(record, project, output)` builds an IR from current explicit
problem premises, nondegeneracy, adopted assumptions, and the stated goal. Observations,
measurements, and model judgments cannot become hypotheses. Each assumption retains its
`asm_N` authority in the formal payload. Invalidated assumptions are omitted.

The complete path requires explicit premises and a goal. It refuses repeated-point and
self-identity E1a predicates, a goal repeated verbatim among the hypotheses, and missing
WP-6a registry-required nondegeneracy. This is a bounded structural filter, not a general
inconsistency or tautology solver. The original WP-6a `typecheck_record` remains available
for its assumption-only spike use cases.

```bash
export MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages"
python3 -m mve.formalizer --record input.json --output /tmp/mve-statement
python3 -m mve.formalizer.g3 --output /tmp/mve-g3
```

No fetch, package update, model, hosted transport, or prover runs. The existing pinned
Lean 4.29.0 and Mathlib are verified locally. LeanGeo remains unavailable. The existing
`sandbox-exec` profile denies network; it is **not filesystem containment**. Nested
`sandbox-exec` can fail in the builder sandbox; these failures remain failures in receipts.

## Repairs

At most three repair rounds follow the first attempt. `Candidate.make(ir, source)` freezes
candidate inputs. Every round records whole-IR, proposition, binder-map, source, and candidate
payload hashes. The whole IR includes evidence identities, so even a change of source
provenance fails closed. Unknown rewrites are refused before invoking Lean and recorded in
`repair.json`. A refused proposal returns the original immutable record and replaces any
previous `record.json` at that output location with that original record.

The accepted source language is intentionally narrow: exact deterministic emission, that
emission plus a trailing newline, or the declared missing-colon fixture. The only automatic
rule restores that colon. This permits syntax repair while refusing arbitrary Lean text,
changed goals/premises, binder remapping, hidden proof commands, or semantic substitutions.
There is no heuristic normalization that might erase a meaningful token. More repair rules
require their own preservation tests. Compiler failure on canonical source stops; a syntax
fixture gets one deterministic repair. Explicit fixture proposals still obey the same cap
and invariants. `reference.ir.json`, round compiler sources/logs/receipts, `repair.json`, and
`record.json` are persisted. Typechecking never creates a proof artifact.

## Equivalence and retrieval

Strength order: `kernel_checked`, `machine_supported`, `reviewer_judged`, `unresolved`.
The kernel-equivalence producer is unavailable; passing a claimed level is rejected.
Exact IR, explicit binder mapping, and deterministic emitted-source correspondence support
only the machine level. They do not pass the independent semantic rubric. Reviewer evidence
must bind both IR hashes and the raw source SHA, and include an identity, rationale, blinded
flag, and separate binders/premises/goal/nondegeneracy booleans. Reviewer identity and blinding
are local assertions, not authentication or an independently enforced blinding procedure.
A review can be recorded alongside stronger machine evidence without relabeling its origin.
`semantic_acceptance` is separate from evidence strength. Typecheck success alone never
upgrades evidence. The CLI stores this evidence in the packet receipt, not a proof node.

`retrieval.examples(records, frozen_split)` accepts only current records whose image hashes
belong to `retrieval`. It rejects unknown/duplicate images, retired manifests, mismatching
truth family/split labels, and every other partition (including sealed/evaluation).
This reuses `mve.evaluation.splits.FrozenSplit`; callers must freeze trusted family assignments
externally, as with WP-8a label export. No caller-supplied family alias overrides the manifest.
`nearest` ranks only the resulting record-bound examples by predicate overlap, with a stable
image-hash tie break. A retrieved example cannot replace the task's frozen IR.

## Offline G3 task set (2026-09-27)

The committed authoring packet is `mve/formalizer/fixtures/g3-taskset/packet.json.gz`.
It contains **100 distinct canonical emitted statements**, **50 distinct reference
statements**, 18 development statements, two retrieval examples, and their frozen WP-2
truth artifacts. Canonical statement uniqueness means SHA-256 of deterministic Lean
source after registry argument canonicalization and fixed binder mapping; it does not
claim logical inequivalence or independence of diagrams.

The original WP-2 split is reproduced exactly (SHA-256
`63da5b93adce004b172d9c6ddd182227d6c22c9adb482fddfa8d263795dff909`). Sealed tasks use only
`right_triangle` and `convex_hexagon`; development uses `concave_polygon` and
`oblique_parallelogram`; retrieval uses `circle_radius` and `orthogonal_pairs`.
References use the calibration families `collinear_extension` and `rational_circle`,
with no family overlap with those three groups. Reference source hashes also exclude
all sealed and retrieval source hashes. The image-indexed manifest retains the full
WP-2 membership and adds image aliases without reallocating any family.

Authoring scans seeds 0..9 in each selected family, using WP-2's existing control
schedule, exact evaluator, candidate universe and construction premise list. Each goal
is an exact-true P1 candidate outside that premise list. Every construction premise is
stated explicitly; the union of registry-required Distinct/NotCollinear conditions for
premises and goal is explicit too. Exact truth does **not** establish derivability from
these premises; incidental-unproved goals remain unproved. The formalizer receives the
explicit record and never promotes a measured or incidental fact into a hypothesis.
The private truth in the authoring archive supports auditing and reproducibility; this
is an offline deterministic harness, not an isolated model inference benchmark.

| Goal predicate | Sealed count | Initial quota |
|---|---:|---:|
| Collinear | 5 | 12 |
| Concyclic | 4 | 11 |
| Parallel | 18 | 11 |
| Perpendicular | 14 | 11 |
| EqualLength | 17 | 11 |
| EqualAngle | 17 | 11 |
| Midpoint | 3 | 11 |
| SBetween | 5 | 11 |
| RightAngle | 17 | 11 |

Collinear, Concyclic, Midpoint and SBetween exhaust their distinct sources within the
declared scan before reaching quota. Duplicate seeds are not counted as new statements;
unfilled slots are redistributed round-robin. This is a bounded search result, not a
claim that every one of the 500 WP-2 sealed diagrams has been exhausted. The sealed set
uses six diagrams; it is 100 statement tasks, not 100 independent visual problems.

Regenerate only the authoring packet, without Lean or compiler receipts:

```bash
python3 -m mve.formalizer.taskset
```

`rubric-template.json` and `.csv` contain problem binders, premises, nondegeneracy and
goal, deterministic reference and candidate Lean statements, and artifact hashes.
Reviewer identity, rationale, blinded flag and the four component judgments are empty.
The reference and candidate statements are deliberately the same deterministic emission;
a human must assess its interpretation against the explicit problem, independently of
machine correspondence. The sheet omits family, coordinates, truth classes and compiler
outcomes. An operator must give the sheet alone to an independent reviewer, keep the
provenance archive and automated results hidden, and return completed JSON entries.
Only then may `blinded` be asserted. This procedure and reviewer identity remain local
assertions, not authenticated identities or an enforced blinding service.

Run real Lean outside the nested builder sandbox:

```bash
export MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages"
python3 -m mve.formalizer.g3 --output /tmp/mve-g3
# After independent human review; supply only completed JSON entries:
python3 -m mve.formalizer.g3 --output /tmp/mve-g3-reviewed --reviews /tmp/mve-g3-human-reviews.json
```

Twenty first-pass inputs retain the declared missing-colon syntax fault; eighty use
canonical emission. Counts and rates therefore characterize deterministic emission and
bounded syntax repair, not model formalization. Canonical-source uniqueness is counted
independently of compiler outcome. Failed compiles remain in the denominator.
All seven controls (empty, trivial, nearest-retrieval, weakened, strengthened, vacuous,
unrelated-but-provable) are reported per task. Refusal checks test preservation; they do
not independently establish semantic equivalence. No theorem proof is attempted.

`g3.json` reports first-pass/post-repair counts and rates, predicate counts, quota gaps,
unique statements, all controls, null `N/A`, reference evidence levels and separate human
rubric passes. Gate thresholds are 80/100 first-pass, 95/100 post-repair and 20/50 blinded
rubric passes, with complete distinct sealed/reference sets required. Without human
reviews `g3_pass` is false and its reason states the unmet semantic threshold. Reviews
with mismatching artifact hashes, unknown/duplicate task IDs, missing identities or
incomplete booleans are refused. Machine correspondence never counts as a rubric pass.

The stale `mve/lean/artifacts/wp6b-g3/` sandbox-failure receipts have been removed.
Opus must run the pinned Lean harness outside the sandbox and commit real receipts.
