# WP-1 semantics review packet — 2026-09-27

Base: `5645250003f`, reviewed plan r5 and schema v5, unchanged. Branch:
`codex/mve-wp1-semantics`. No merge and no hosted calls. The r2 tests remain in the
separate local stash; this implementation uses newly authored v5 fixtures.

Implemented:

- Frozen registry: nine P1 predicates plus Distinct and NotCollinear, symmetry groups,
  degeneracy descriptions, incidence mapping and uncompiled Mathlib target expressions.
  Remaining registered predicates reject typed use until semantics are frozen.
- Immutable `Record` snapshots, independent mathematical and execution identities,
  canonical binder/argument projections, synthetic render/proof-evidence exclusions,
  addressable sources and exact algebraic expression parsing without Python evaluation.
- Schema validation plus typed references, ID uniqueness, dependency-cycle detection,
  source/call-specific geometry, evidence equality, human adoption, per-proposition
  authorization, explicit goals, artifact dependencies and stage checks.
- Optimistic-concurrency operations, RFC 6902 edits, retained invalidated evidence,
  transitive invalidation through typecheck/proof/render, and lineage on mathematical
  identity changes. Atlas-ingested records reject further mutation.
- Separate typecheck and proof states, standard-axiom policy, receipt flag checks,
  missing-evidence routing and lower-route threshold boundaries.

Run `python3 -m pytest tests/mve --cov=mve`. Latest full run: **180 passed, 94% statement
coverage**. This includes 100 independently authored initial records and negative cases
for references, types, authorization, revisions, identity, artifacts and transitions.
Production code passes `ruff check mve`; files/functions meet the 800/50-line limits.
This satisfies the exercised G0 validation slice, not the hosted benchmark half of G0.
The final refactor only extracted version checks; the targeted suite was rerun afterward.

Review details and limits:

1. Geometry `depends_on` includes its owner entity in addition to its source. This fills
   a dependency-completeness obligation in r5: otherwise a problem edit invalidates an
   entity but leaves its geometry and downstream observations usable. No schema change.
2. Invalid historical nodes retain their original propositions and skip current semantic
   equality checks. They still obey schema and graph integrity and cannot authorize any
   valid node. Callers should persist every immutable snapshot, not just the latest one.
3. Exact parsing has explicit resource bounds (120 characters, 80 AST nodes, bounded
   integer size/exponents and intermediate arithmetic). Unsupported expressions raise an
   error; they do not become approximate authoritative truth. WP-2 must exclude them.
4. Actor strings describe the trusted caller; they are not authentication. Likewise,
   validation checks receipt structure and policy, not a Lean kernel execution. WP-6/7
   must supply independent receipts and verify artifact bytes. No proof was established.
5. Source hashes identify out-of-band truth artifacts; checking the actual exact-coordinate
   evaluator and candidate universe belongs to WP-2. Inference-process isolation belongs
   to WP-11a, and active-question/calibration-lock loading to WP-5.
6. The operation API intentionally rejects deletion of addressable evidence, direct edits
   to IDs/validity/history, and re-formalization of checked statements without an edit.
   Source/image replacement and post-ingest changes should start an explicit new record.
7. `mve/DEPS.lock` pins this branch's source bytes and Python packages. It will need union
   with WP-0a's external dependency pins at the reviewed integration step.

Manual review found and repaired missing argument-geometry checks, unrestricted review
actors, checked-statement replacement, invalidated-adoption equality, and missing-evidence
routing. The shared wiki refresh tooling is absent from this branch; no Desktop refresh
or modification was attempted. Ready for Opus review; nothing merged.
