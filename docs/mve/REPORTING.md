# WP-9b / WP-11b offline reports

Run from the repository root, with a local evidence commit:

```bash
python3 -m mve.reporting --revision ea621a8918e --output docs/mve/reports
```

This writes `SUMMARY.md` and `SUMMARY.json`. The same revision and inputs produce
identical bytes, including after a JSON round trip. There is no clock, hostname,
model call, download, compiler invocation, corpus regeneration or database mutation.
`Evidence` reads exact Git blobs, ignoring uncommitted changes. Each consumed source
has its SHA-256 in the report; rows carry file/field pointers. The packet entry in
`mve/DEPS.lock` pins the reporting implementation and its evidence dependencies.

The checked-in report uses integration commit
`ea621a8918e5bb22c5ed53a1d3c30bfb5b09f7d7`. Reproducing it does not require a model,
Lean cache, generated private corpus, credentials or network access.

## Accounting

The campaign input is a **committed JSON snapshot** with the shape returned by
`BudgetLedger.snapshot()`. Supply its repository-relative path:

```bash
python3 -m mve.reporting --revision YOUR_LOCAL_COMMIT --campaign path/to/campaign-ledger.json
```

The default is `mve/campaign/ledger.json`. That file is absent in the current
integration commit. The report does **not** instantiate a new campaign ledger to
replace it: it reports the known subledger exposure and leaves complete campaign
state and remaining headroom unknown. The USD 20 aggregate / USD 2 P0 / USD 8 P1
limits in this case are the plan's D4 authorization, not measured campaign state.
P2 has no separate fixed cap; it shares the aggregate remainder.

The dedicated live snapshot is
`docs/mve/reviews/wp0b-live/ledger.json`. Its USD 0.05 aggregate limit belongs to the
single probe. The charge is 268 micro-USD, carried into campaign P0 accounting.
Copies in both snapshots count once only when the complete attempt rows agree.
Conflicting rows or totals fail generation. This is a report projection; it does
not import the charge into a writable campaign database or enforce future spend.
An operator must carry this charge into the real campaign ledger before more calls.

Money stays in integer micro-USD and Decimal USD strings. Unsent reservations,
settled actuals and dispatched-but-unsettled reservations are separate. Uncertain
actual costs remain unknown; their complete reservation remains in exposure.
Cancelled rows retain their attempt count but contribute no exposure. Overcharges
are not clamped, and negative remaining headroom is retained. Snapshot freeze state,
stop/resume/breach events and each pinned window string are reported without
claiming live authorization. Quota is separate from money; the source quota rows
have neither phase attribution nor quota limits, so those are not inferred.

## Gate evidence and limits

All G0–G6 rows include the plan's null/baselines and criteria counts. G4a and G4b
are distinct gates. A gate is established only if every required criterion has
explicit evidence and passes. Missing, unresolved or underpowered evidence yields
`not established`; a complete evaluated set with a failed criterion yields
`failed`. Numeric failure cannot be replaced by prose. Tests exercise all three
states for every gate. The generic criterion reducer accepts adapter-produced
checks; the CLI does not accept arbitrary pass assertions.

Current adapters read WP-0a preflight, both WP-2 corpus receipts, WP-5 spike,
WP-0b live receipt and the current `g3-taskset` aggregate/task/reference receipts.
Historical preflight failures are labeled historical and capability-specific.
WP-2 generation and artifact-audit receipts must agree. G3 headline, predicate,
control and equivalence counts are checked against its row receipts. These are
reported receipts, not an independent rerun of Lean or the private corpus.

G3 reports 80/100 first-pass, 100/100 post-repair, 100 distinct statements,
all seven controls 100/100, 50/50 machine-supported references and **0/50 human
reviews / 0/50 semantic passes**. It is pending the human rubric. These results
measure the deterministic emitter and injected-syntax repair, not model
formalization, theorem proof or semantic acceptance. G2 remains unestablished:
the new-head spike's 3/3 parity on fixture states, four training rows and one
family do not establish production refit or independent evaluation.

The absent G1 results have separate rows for query-set/full-record,
raw perception/coordinate consistency/image measurement, and synthetic/real
transfer. `relation_table()` uses the existing WP-11a scorer and preserves
relation micro counts, diagram macro scores and each metric's denominator,
including malformed/missing outputs. It cannot establish G1 without sampling and
per-predicate confidence evidence. No present receipt supplies scored predictions,
so the checked-in report leaves these scores null. Non-relation tables explicitly
mark these aggregations N/A rather than relabeling statement counts as relations.

95% intervals are null with an explicit reason where no independent sampling design
is established. Finite fixture censuses are descriptive; they do not supply
population confidence bounds. Null scores are not zero, and the report does not
claim that a missing confidence gate passes. New scored-run adapters are needed
when those run receipts exist. The current packet does not perform the P6
submission mentioned alongside reporting in plan §7 step 9.

## Offline validation

```bash
python3 -m pytest -q tests/mve/test_reporting.py --cov=mve.reporting --cov-branch --cov-report=term-missing
python3 -m pytest -q tests/mve -ra --tb=short
ruff check mve/reporting tests/mve/test_reporting.py
```

The handoff in `reviews/REPORTS_ASTRA_20260928.md` records the full-suite result and
names the nested-sandbox failures for Opus to rerun outside the builder sandbox.

## WP-10 topology evidence

When the evidence revision includes `mve/topology/artifacts/receipt.json`, the
report adds a separate coordinate self-consistency section with crossing micro,
diagram macro, exact/canonicalized PD, orientation nulls and component counts.
This public fixture census is not G5 perception evidence. Its family split is
retired; external data and real perception runs are absent. Only G5's grammar
criterion is evidenced. The details and the deliberately narrow canonicalization
convention are frozen in [TOPOLOGY.md](TOPOLOGY.md).
