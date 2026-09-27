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

## Offline G3 interpretation

The harness preserves WP-2's `mve-family-split-v1` family allocation, replacing item IDs with
image hashes. It builds 100 exact-positive construction instances in the two reserved sealed
families, with explicit midpoint and distinctness premises and three authored goal templates:
collinearity, strict betweenness, equal subsegment length. The record's three named points use
WP-2 exact truth generation; images retain the full six-point WP-2 rendering. There is no
perception measurement or inference from hidden coordinates in the formalizer.

Twenty first-pass inputs have a deterministic missing-colon fixture fault. The other eighty
are canonical. Byte-identical Lean sources share a compiler receipt within this run only:
there are three canonical templates and six unique compiler inputs, not 100 independent
language-formalization problems. Fifty task instances are designated structural references;
none has an independent blinded semantic judgment. No G3 pass is claimed.

Each task receives empty, trivial, nearest-retrieval, weakened (`goal ∨ True`), strengthened
(`goal ∧ False`), vacuous, and unrelated-but-provable statement controls. Unknown source
rewrites are refused by the preservation boundary. Nearest-retrieval substitution is refused
by IR/evidence identity even when the emitted statement happens to match a template; this is
a provenance refusal, not a plagiarism detector or an independent semantic equivalence test.
Controls contain proposition definitions only, no theorem proofs.

`g3.json` reports counts and null `N/A`; `tasks.json` binds those counts to per-task source
receipts, repair attempts, control refusals, and equivalence evidence. `split.json` and the
100 input records are persisted. Successful fixture-compiler unit tests are never substituted
for real-Lean counts. Failed local compiler invocations stay unresolved and in denominators.
