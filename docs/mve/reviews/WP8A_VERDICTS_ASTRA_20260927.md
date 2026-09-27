# WP-8a verdict capture — Astra handoff, 2026-09-27

Branch: `codex/mve-wp8a-verdicts`; base: `0be52713584ac62338e877b3197dfbef7d466b82`.
Sole builder: Astra. Local commit only; Opus reviews, reruns the six sandbox-blocked tests,
and pushes/merges. No downloads, network, hosted calls, UI framework, or JSXGraph.

## Built

- `mve.verdicts`: immutable `capture`, `propose`, `revise`, `export_labels`, and
  `export_verdicts` APIs; `python3 -m mve.verdicts` provides local JSON apply/export commands.
  Usage and split conversion are documented in [VERDICTS.md](../VERDICTS.md).
- Verdict targets: observations, measurements, derivations, judgments, optional candidate
  propositions, and existing formal propositions. Human/model identity is explicit and
  preserved, including case and punctuation. Timestamps are checked without relying on
  optional JSON Schema date-time packages absent in this environment.
- Capture is evidence only. Only human `adopt` in this API creates an assumption, through
  the existing `judge` then `adopt` transitions. Models cannot adopt/decline. There is no
  `human_confirmed` support and no new formal authorization route. Proposition equality and
  authority continue through the existing semantic validator. Adoption of a judgment itself
  is refused; select its underlying proposition-bearing target instead.
- Every write uses optimistic concurrency. Stale `from_revision` is refused. Human revisions
  use RFC 6902 and `mve/graph.py` invalidation, tested through `jud → asm → prop → tc → prf/rnd`.
  Edits cannot rewrite evidence owners or change another actor's judgment/candidate.
  New opinions append; correcting/withdrawing one's prior adoption uses `revise`.
- The local store locks, rereads, validates, then atomically replaces the record. Concurrent
  writers with the same starting revision yield one success and one stale rejection.
  Both adoption transitions persist together. Validation, temporary-file creation, and
  replacement failures preserve the previous record.
- Explicit catalogue labels use the frozen §5 vocabulary. Human labels (weight 1.0) override
  model manager labels (0.5), in either arrival order. Latest revision wins within actor
  kind; caller timestamps cannot reorder precedence. Conflicts are event notes and export
  provenance. Human abstention suppresses a model label; invalidated labels are excluded.
  Visibility/adoption/abstention verdict rows can be exported separately, without inventing
  classifier targets. Q-claim-workflow needs its own label and a free-text claim.
- Both exports are family-keyed and use the existing `FrozenSplit`, with image SHA256 item
  IDs to prevent caller-supplied item aliases. Training includes only `fit`; calibration
  and evaluation/sealed require separate explicit purposes. Metadata contradictions,
  unknown images, retired splits, duplicate record images, and observed mathematical
  identity collisions across splits fail closed. Alternate family renderings cannot cross
  partitions under the existing split validator. Rows carry split hash and record/judgment
  revisions, actor kind/identity, weight, timestamp, target, and conflict IDs.
- WP-3 follow-ups: dispatch and attempt receipts are hard-coded P1; a public P0 request is
  rejected before reservation/output. `perceive(model=...)` explicitly requires
  `deepseek-flash`. Regression tests cover P0 refusal, explicit Flash acceptance, wrong-model
  refusal, and P1 dispatch. WP-0b's P0 probe remains unchanged.
- `mve/DEPS.lock` contains `packets.WP-8a`, pinning new/reused files and installed package
  versions. No new third-party dependency.

## Schema extension and justification

The existing schema can address only observations produced by perceiver calls, derived
results on premises, assumptions, judgments targeting existing nodes, and already-authorized
formal propositions. It cannot hold a new human/model candidate awaiting adoption without
misstating its evidence class or prematurely granting authority. Therefore v5 gains the
optional `candidates` array (`can_N`) and `proposed` event kind. Each candidate stores its
proposition, proposer, timestamp, optional free text, validity, and entity dependencies.
It is a non-authorizing proposal, not a sixth evidence class. Existing records remain valid
without the array. Candidate validation, edit permission, and graph enumeration are wired
into existing operations/semantics rather than a parallel record implementation.

The human identity grammar in `assumptions.adopted_by` is aligned with the existing judgment
identity grammar: otherwise an accepted `human:Alice.Smith` verdict could not be adopted by
the same identity without lossy renaming. Policy identity syntax is unchanged.

`schemas/mve_observation_record.json` and `docs/mve/mve_observation_record.json` are byte-equal
(`cmp` passed). No change to the frozen plan, authorization table, or identity projection.

## Validation

Tests were written first. Initial verdict tests failed collection because the APIs did not
exist; the new WP-3 P0 regression independently failed because P0 was still accepted.
Additional persistence tests first failed on the missing store module. No network in tests.

Final command:

```bash
MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages" \
  python3 -m pytest tests/mve -q --cov=mve --cov-branch \
  --cov-report=term-missing --cov-report=json:/tmp/wp8a-final-coverage.json
```

**606 passed, 6 failed, 0 skipped; 612 collected, 34.13 seconds.** The six failures are only
nested `sandbox-exec` denial inside the Codex sandbox, listed below. No WP-8a/WP-3 failures.
Full-suite statement coverage **94.14%** (2,908/3,089); branch-aware total **92.59%**.
Coverage used its Python tracer because the installed optional C tracer has the wrong
architecture; this produces one warning, not skipped tests.

| New module | Statements | Statement coverage | Branch-aware coverage |
|---|---:|---:|---:|
| `mve/verdicts/__init__.py` | 3 | 100% | 100% |
| `mve/verdicts/__main__.py` | 38 | 100% | 100% |
| `mve/verdicts/capture.py` | 55 | 100% | 100% |
| `mve/verdicts/catalogue.py` | 15 | 100% | 100% |
| `mve/verdicts/labels.py` | 48 | 100% | 100% |
| `mve/verdicts/store.py` | 37 | 100% | 97.56% |

New modules: **196/196 statements covered**, 41/42 branches, **99.58% branch-aware total**.
The sole reported missing branch is the exceptional temporary-cleanup path in `store.py`;
temporary-file creation and replacement failure tests both pass. All new modules exceed 90%.
Ruff checks on changed Python files, `git diff --check`, and schema byte-equality passed.
New production modules are below 800 lines; new functions are at most 50 lines.

### Opus rerun outside the nested sandbox

1. `tests/mve/test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
2. `tests/mve/test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
3. `tests/mve/test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
4. `tests/mve/test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
5. `tests/mve/test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
6. `tests/mve/test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

All three Lean compiler logs contain exactly `sandbox-exec: sandbox_apply: Operation not
permitted`. The two worker isolation assertions report the same denial and exit 71. The
worker-timeout test fails because sandbox-exec exits before the worker can sleep/time out;
its earlier hard-link and symbolic-link refusals pass. No sandbox guards were weakened or
removed. Opus should rerun the full suite with the same package root outside this sandbox.

## Gaps and boundaries

- Actor roles are local operator assertions, not authentication. A future host must supply
  trusted human/model identities. Audit-role review judgments are not reclassified as
  manager labels; explicit model identities are required for this export path.
- File concurrency covers cooperating writers on the same canonical path, not external
  direct writes or hard-link aliases. The immutable API itself has no persistent store.
- Family assignments remain externally frozen. WP-2 opaque corpus IDs need a metadata-only
  conversion to image SHA256 IDs preserving every original family/split, as documented.
  No family inference from pixels, family reallocation, or gold access was added.
- No trained model, classifier activation/refit, state-feature packaging, audit sampling,
  routing replay, 20-diagram session, render-back UI, or atlas integration was attempted.
  This supplies WP-8a's label capture/export path; it does not claim G2 or G4b acceptance.
