# WP-9b + WP-11b reporting — Astra handoff, 2026-09-28

Builder: Codex Astra, sole builder. Reviewer/merger: Opus.
Branch: `codex/mve-wp9b-wp11b-reports`.
Evidence/base: `ea621a8918e5bb22c5ed53a1d3c30bfb5b09f7d7`.
Local commit only; no push. No hosted calls, network access or downloads.

## Delivered

- `mve/reporting/`: committed-Git-blob reader, exact ledger projection, explicit
  gate criteria and three-state reducer, receipt adapters, relation-score adapter,
  deterministic Markdown/JSON renderer and offline CLI.
- `docs/mve/reports/SUMMARY.md` and `SUMMARY.json`: current report from the pinned
  integration evidence, with 11 source-file SHA-256s and field/section references.
- `docs/mve/REPORTING.md`: invocation, snapshot contract, accounting semantics,
  reproducibility and evidence limits.
- `tests/mve/test_reporting.py`: 59 offline tests, written before implementation;
  missing-module RED, followed by focused RED cases for discovered boundary issues.
- `mve/DEPS.lock`: additive `packets.WP-9b-WP-11b` entry; previous packets preserved.

Reproduce the checked-in outputs:

```bash
python3 -m mve.reporting --revision ea621a8918e --output docs/mve/reports
```

The reader uses Git objects, not mutable worktree contents; Git protocol access
and lazy fetch are disabled. Regeneration was byte-identical for both formats,
including rendering after a JSON round trip. All 11 hashes were independently
compared with the pinned Git blobs. There are no new external dependencies.

## Accounting result and gap

The dedicated WP-0b ledger has **one settled P0 attempt**, originally reserved at
39,936 micro-USD (USD 0.039936), now settled at **268 micro-USD (USD 0.000268)**.
Known current reserved exposure is 0; known uncertain exposure is 0. The live
subledger is not frozen and has no events or quota entries. Its window string is
reported verbatim. This charge is a usage-derived peak-price upper estimate,
not a vendor-billed amount.

The campaign ledger snapshot is **not committed** at this integration head.
The default expected path is `mve/campaign/ledger.json`; a different committed
snapshot can be supplied with `--campaign`. Therefore the report shows known
exposure and leaves full campaign freeze/stop state and remaining headroom unknown.
The plan's authorization is USD 20 aggregate, USD 2 P0, USD 8 P1; P2 shares the
aggregate remainder. The probe's USD 0.05 limit is never substituted for those caps.
Known P1/P2 exposure is zero in the supplied snapshot, not a claim that an unseen
campaign contains no attempts.

The live charge is carried into P0 in the report projection. A matching attempt
in both snapshots is counted once, with both origins retained. Conflicting rows,
wrong live phase, inconsistent exposure totals and invalid money fail generation.
This code does not write the campaign database: Opus/operator must preserve the
live charge in real campaign accounting before further chargeable work.

All money is integer micro-USD with Decimal USD strings, independent of the caller's
Decimal precision. Dispatched unsettled attempts retain their reservation as
uncertain exposure. Cancellation, overcharge, negative headroom, freeze, stop
history and quota separation have dedicated tests. Quota rows have no phase field
or quota limit, so per-phase quota and remaining allowance are not established.

## Gate results and gaps

**No complete gate is established by the selected committed evidence.**

- **G0:** the WP-2 audit records 2,560 validated records, including 2,000 fit and
  500 sealed diagrams, with 20 each calibration/development/retrieval. Both corpus
  receipts agree. Reported cross-split image and coordinate collisions are zero.
  The 300-item / three-model Geoperception comparison is absent. This adapter
  does not turn general suite pass counts into a dedicated negative-fixture gate
  receipt. Historical WP-0a capability results remain historical, not new runs.
- **G1:** no committed scored sealed predictions or per-predicate confidence
  evidence. Query-set/full-record, raw/coordinate/image stages and real transfer
  each have separate unavailable rows. Corpus availability is not perception
  performance.
- **G2:** not established. The spike has 4 fixture training rows, 1 family,
  **3/3 ONNX argmax parity** and a separate 20-parameter head. It does not supply
  independent gold, paired Opus evaluation, production weight refit, or
  calibration promotion/rollback evidence. Fixture label counts stay separate
  from independent evaluation.
- **G3:** **pending human rubric: 0/50 reviews, 0/50 semantic passes**. Real-Lean
  receipts report **80/100 first-pass**, **100/100 post-repair**, **100 unique
  canonical statements** and all **seven control kinds 100/100 detected**.
  Reference equivalence is 50 machine-supported, 0 reviewer-judged, 0
  kernel-checked, 0 unresolved. These are deterministic emission/syntax-repair
  results, not model formalization or theorem proof. The report cross-checks
  headline, predicate, control and equivalence counts against task/reference
  receipts; it does not rerun the compiler. Per-predicate counts are Parallel 18,
  EqualLength 17, EqualAngle 17, RightAngle 17, Perpendicular 14, Collinear 5,
  SBetween 5, Concyclic 4, Midpoint 3. The existing low-coverage quota gaps remain.
- **G4a:** no two-prover comparison over 50 semantically accepted statements.
- **G4b:** no completed 20-diagram co-observer session and archived atlas test.
- **G5:** no frozen synthetic/external PD evaluation receipts.
- **G6:** no reproducible real-ingest record with Sol review; no P6 submission
  performed in this offline reporting packet.

Every report table includes a null/baseline and counts/denominators; non-relation
units explicitly mark micro/macro N/A. The relation adapter preserves both
micro-over-relations and macro-over-diagrams, each metric's denominator, and
missing/malformed responses. Absent scores and 95% confidence intervals are null
with reasons; fixture censuses do not establish independent sampling or population
confidence. Future scored-run receipts need corresponding adapters; arbitrary
pass assertions are not accepted by the CLI.

## Validation

Focused reporting suite: **59 passed**; **100% statement coverage (356/356)** and
**99% combined statement/branch coverage** (one unvisited optional-generation
branch). `ruff check` passes. All new functions are at most 50 lines and modules
at most 800 lines. Existing code outside the additive lock entry was unchanged.

Full `tests/mve` with the existing local Lean package cache configured:
**778 passed, 6 failed, no skips**, in 301.54 seconds. The six failures are the
nested-sandbox cases; Opus must rerun outside the builder sandbox:

1. `tests/mve/test_formalizer_g3.py::test_real_lean_repairs_statement_without_proof`
2. `tests/mve/test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
3. `tests/mve/test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
4. `tests/mve/test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
5. `tests/mve/test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
6. `tests/mve/test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

The isolation failures directly report `sandbox_apply: Operation not permitted`.
A focused diagnostic rerun of the four Lean cases confirmed the same exact
`sandbox-exec: sandbox_apply: Operation not permitted` text in every retained
compiler log; their wrappers consequently report failed typechecking.
An earlier uninstrumented run, before setting the Lean cache, had 759 passed,
3 failed and 4 skipped. Its additional timing-dependent sandbox failure was
`tests/mve/test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`:
the denied sandbox exits before the expected worker timeout. It passed under
coverage in the final full run; Opus should include it in the outside-sandbox rerun.
Coverage used the Python tracer because the installed C tracer has the wrong
architecture; collection completed successfully.

Commands for Opus:

```bash
export MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages"
python3 -m pytest -q tests/mve -ra --tb=short
python3 -m pytest -q tests/mve/test_reporting.py --cov=mve.reporting --cov-branch --cov-report=term-missing
ruff check mve/reporting tests/mve/test_reporting.py
python3 -m mve.reporting --revision ea621a8918e
```

The live charge remains accounted for; no gate, corpus, review or learning evidence
was manufactured to close the outstanding work.
