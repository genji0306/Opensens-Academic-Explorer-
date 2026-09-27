# WP-10 topology — Astra handoff, 2026-09-28

Built solely in `codex/mve-wp10-topology`, based on integration `1e6db728bd0`.
Offline only: zero hosted calls, network operations, downloads or package installs.
Local commits only; Opus reviews, pushes and merges. No subagents were used.
Read plan r5 §11/WP-10, §8/G5, §5/Q-topo-workflow, §7/step 10, REPORTING.md,
and every addendum in OFFLINE_PACKETS_REVIEW_OPUS_20260927.md before implementation.

## Delivered

- Separate immutable oriented PD records and exact rational polygon skeletons.
  [TOPOLOGY.md](../TOPOLOGY.md) freezes traversal, arc numbering, CCW local slots,
  determinant/right-handed signs, mirror flags, circle metadata and rejection rules.
- Five closed-braid families × six controls = **30 PNG diagrams**: unknot, both
  trefoil chiralities, figure-eight, Hopf link and unlink; mirror, R1 ±, R2 and
  near-miss variants. **76 crossings total**, maximum **6**, all below G5's limit 7.
- Independent symbolic braid crossing truth versus rational segment-intersection
  decoding, with every exact underpass gap preserved. The PD assembler is shared;
  these results are explicitly self-consistency, not independent transcription.
- `mve.evaluation.splits` freezes five family-disjoint partitions. Chiralities and
  move variants remain with their family. All fixtures were used in development,
  so the split is **retired** and carries its pre-retirement parent hash.
- Exact PD-list and narrowly canonicalized scorers, component/count/orientation
  diagnostics, unknowns, complete-record score and the exact plan error taxonomy.
- A kernel-checked core Lean successor-orbit certificate for the decoded trefoil,
  **no axioms**. A deliberately false orbit endpoint fails. It does not certify the
  picture or its knot type. Source and compiler receipt are committed.
- Named SnapPy operation receipts, all **unavailable**, because SnapPy/Spherogram
  are absent. No dependency was downloaded. These are placeholders, not a working
  optional adapter.
- Committed-evidence reporting consumes the fixture receipt in a separate table.
  **G5 remains not established**, with 1/1/4 criteria met/evidenced/required: grammar
  only. Synthetic perception, permitted-external perception and their score evidence
  are missing. Existing reports' budget and other gate evidence are unchanged in meaning.

## Numbers, denominators and nulls

| Descriptive fixture measure | Result |
| --- | --- |
| Exact PD lists | 30/30 = 1 |
| Canonicalized PD lists | 30/30 = 1 |
| Complete transcript including component count | 30/30 = 1 |
| Crossing micro accuracy | 76/76 = 1 |
| Crossing macro accuracy | sum of fractions 25/25 = 1; 5 crossing-free diagrams excluded |
| Orientation micro | 76/76 = 1 |
| Orientation macro | 25/25 = 1; same 5 exclusions |
| Complete orientation | 30/30; includes vacuous c=0 cases |
| Component-count correctness / crossing-count correctness | 30/30 each |
| Crossing-count errors / unknown PD outputs | 0 / 0 |
| Knot-type predictions | 0 supplied, 30 unknown; scored 0/30, micro = macro |
| Invariant consistency | 0/0, value null; not executed |

General PD null is N/A. Conditional complete-orientation null is `2^(-c)` for
each fixed crossing/arc-correspondence instance, mean **0.32447916666666665**.
Knot-type vocabulary is **k=6**, uniform null **1/6**, majority **6/30 = 0.2**.
Class counts: unknot 6, figure-eight 6, Hopf 6, unlink 6, negative trefoil 5,
positive trefoil 1. These labels are construction truth; no type classifier ran.
The finite public census has no population confidence interval.

Exact literally means identical ordered PD lists. Thus an unknot and unlink both
score exact on empty lists; the separate complete/component scores reject that
confusion. Canonicalization permits only per-component cyclic label shifts and
component reordering. Crossing-row permutation, reflection, orientation reversal
and Reidemeister moves are not added equivalences. Mirror and R1/R2 controls pin
that distinction. Orientation signs only score where opposite arc pairs establish
correspondence; matching signs on mismatched crossings earn no credit.

## Validation

Tests were written first: the initial focused run failed collection on the absent
`mve.topology.model`; the reporting and certificate additions likewise had failing
contract tests before their implementations.

Final focused suite: **130 passed** (71 topology + 59 existing reporting tests).
Coverage over all new topology modules plus the new reporting adapter:
**471/473 statements = 99.58%**, **168/170 branches = 98.82%**, combined
**639/643 = 99.38%**. Every module is ≥ 90%: geometry 99%, scoring 97%, all others
100% (rounded combined values). The unvisited branches are reused-gap rejection
and the labels-only diagnostic. No lines were excluded from coverage.
`ruff check` and `git diff --check` pass. Production functions ≤ 50 lines;
modules ≤ 800 lines. Two rendered base images were inspected visually for gaps.
Re-running corpus generation produces identical PNG/JSON/split/receipt bytes.

Full suite with the existing portable Lean package cache set:
**849 passed, 6 failed, 0 skipped**, 76.52 seconds. The six failures are the known
nested `sandbox-exec` cases, not topology failures:

1. `tests/mve/test_formalizer_g3.py::test_real_lean_repairs_statement_without_proof`
2. `tests/mve/test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
3. `tests/mve/test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
4. `tests/mve/test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
5. `tests/mve/test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
6. `tests/mve/test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

The isolation stderr and retained Lean logs say
`sandbox-exec: sandbox_apply: Operation not permitted`. Opus must rerun these
outside the builder sandbox. An initial run without the cache had 846 passed,
2 sandbox failures and 4 Lean skips (before the final three topology tests).
Coverage used the Python tracer: the installed C tracer has the wrong architecture.
The new core Lean certificate uses the already pinned binary directly, no Lake or
external packages, and passes within the existing builder sandbox.

## Reproduction and remaining gaps

```bash
python3 -m mve.topology --output /tmp/mve-wp10
python3 -m pytest -q tests/mve/test_topology.py tests/mve/test_reporting.py \
  --cov=mve.topology --cov=mve.reporting.topology --cov-branch --cov-report=term-missing
export MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages"
python3 -m pytest -q tests/mve -ra --tb=short
ruff check mve/topology mve/reporting tests/mve/test_topology.py
python3 -m mve.reporting --revision HEAD --output /tmp/mve-wp10-report
```

The sole runtime third-party dependency is existing Pillow 12.2.0; Python 3.13.2,
zlib 1.2.12, test tools and reused MVE/Lean pins are recorded under `packets.WP-10`
in DEPS.lock, preserving every pre-existing packet entry.

Still missing for G5: image-to-skeleton perception, independent sealed synthetic
transcription, a permitted external ≤7-crossing set, and real prediction receipts.
The strict polygon/signed-area grammar is narrower than arbitrary knot drawings.
Near-miss strokes may visually merge at the PNG resolution, intentionally; the
coordinate decoder is not evidence that image perception can resolve them. The
coordinate fixtures openly access geometry and symbolic truth; no inference gold
isolation is claimed. SnapPy construction/identification/Jones checks, additional
styles and a working pinned optional adapter remain future work. Candidate identity
or invariant agreement must never be promoted to transcript verification.

No Q-topo-workflow classifier activation, knot-type classifier, Euclidean record
changes, automatic gate promotion or live transport is introduced. Opus review
and an outside-sandbox full-suite rerun remain pending.

## Committed report snapshot

`docs/mve/reports/SUMMARY.md` and `SUMMARY.json` are regenerated from evidence
commit `413a5daf49b9cf4f5d8d6f37372cf962b219a44b`. A second generation and JSON round trip
produce identical bytes. G5 is 1/1/4 and not established; the budget object is
byte-equivalent after canonical serialization to the prior report. The follow-up
commit contains only this snapshot, its documentation and refreshed WP-10 hashes.
