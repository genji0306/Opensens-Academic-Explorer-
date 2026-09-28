# WO-1b capture robustness — Astra handoff, 2026-09-29

Implemented offline in `codex/mve-wo1b-robust`, based on `cb8a3fc382d`.
Opus reviews, merges and runs native captures. No browser launch, hosted call,
network access, source-repository mutation or write to another packet's generated
evidence was performed. Sole-builder review was local; no sub-agents were used.

The WO-1b manifest is unchanged:
`d286a45abc8187fd06bd63a1957d34c809ca0c82abaf9aad8485ef3b9abe7620`.
WO-6c approval remains `WO6C_APPROVAL = "2026-09-29"`; its design remains
`c2250829b79e120a735cdeaf8e7c5d667f1aafb0630130d5665ff9db6bf946cf`.
WO-6c's capture plan carries refreshed runtime hashes; no development capture
has been run here. Its response patches and experimental design are unchanged.

## Evidence corrections and compatibility

Read-only inspection of the owner root
`~/Developer/Opensens/worktrees/oae-mve-wo1b/mve/generated/wo1b-d286a45abc8187fd/`
verified 70 complete snapshots and 140 hashed pass records. **Every pass records
Chrome `153.0.8010.54`, not 152.** This handoff preserves those recorded facts;
it cannot establish the reported 152-to-153 transition from these artifacts.
A separate synthetic legacy-format regression demonstrates that 152 records
remain valid too. Runtime upgrades do not relabel historical browser versions.

All 140 pass records bind the original `snapshot_render.py` hash
`dbde0630260b7ef05f10b568ed58f0d0d0038510be05d9b0797d5722571f1aea`.
Each sealed completion hashes its pass JSON files; those contain browser and
renderer provenance. Completion validation checks those original artifact hashes,
identity, numeric digest and source audit, rather than comparing the historical
renderer hash with today's runtime. Original complete.json files are not rewritten.
The manifest contains no runtime source hashes. `DEPS.lock` pins the current
runtime separately and retains the original WO-1b runtime pins as provenance.
The complete original runtime remains recoverable from base commit `cb8a3fc382d`.
The old completion records directly attest the renderer hash, not every historical
Python dependency independently.

**The frozen batch order is not cluster order.** For example, batch 7 contains
four snapshots from `spectral-contrast-2`, four from `field-dyson-ordinary-0`, and
two from `field-dyson-ordinary-3`. Cluster `spectral-contrast-2` already has accepted
members in batch 6. Reordering batches would break the requested resume selection,
so admission also checks version consistency across every accepted member of each
cluster. Batch size is now fixed at ten; the earlier reduced-size operator option
is no longer accepted. Pilot selection remains one complete ordinary cluster.

## Bounds and load accounting

`--page-load-timeout 120` is the pinned default, in seconds; allowed values are
1–120. It is passed explicitly to Playwright `goto(..., wait_until="load")` in
the shared block renderer used by WO-1b and WO-6c. 120 seconds gives four times
the previous navigation allowance under the reported host saturation. It is an
engineering allowance, not a claim that every saturated host can finish within it.

Each snapshot's capture and save has a signal deadline of `load + 60` seconds,
including rendering, screenshots, OCR and persistence. That deadline preserves
the remaining enclosing pass deadline. The extra 60 seconds is finite headroom
for post-load work. Other Playwright operation defaults are unchanged. A timeout
fails the attempt; there is no internal retry, fallback renderer or skipped page.

| Path | Snapshots/pass | Default snapshot cap | Default pass cap | Two-pass worker ceiling |
|---|---:|---:|---:|---:|
| WO-1b and drift | up to 10 | 180 s | 1,860 s | 3,840 s (64 min) |
| WO-6c development | 4 | 180 s | 780 s | 1,680 s (28 min) |

Derivation: `pass = count × (load + 60) + 60`, reserving 60 seconds for browser
startup/close; `overall = 2 × pass + 120`, reserving 120 seconds for worker setup,
comparison and candidate receipts. `--timeout-per-pass` may explicitly select
between the derived minimum and 1,860 seconds. Every isolated worker is therefore
bounded by 3,840 seconds. The existing parent kills worker and detached browser
process groups on both success and failure. The original WO-1 CLI retains its
900-second default. Parent source audits and archive cleanup surround the bounded
worker; they remain mandatory and are not silently skipped on timeout.

Every created batch receipt records `bounds`, `load_start` and `load_end`.
Load arrays are raw `[1-minute, 5-minute, 15-minute]` averages, descriptive only.
`--max-load X` is optional, finite and nonnegative. If the first average exceeds
X, `host_load` is printed before acquiring the storage lock or creating any
directory. Equality passes. No automatic throttling or waiting is introduced.

## Version discipline and drift receipt

Admission reads Chrome's macOS `Info.plist` without launching a browser. Native
capture verifies the actual browser context version at start and end, all packet
versions across both passes, the admission version, and the installed bundle
version at batch end. Missing or inconsistent versions fail closed before any
completion is accepted. Batch-end bundle-read failure also preserves the failure
receipt and source audit. Snapshot completion, capture, batch and WO-1b acceptance
records expose `browser_version`; pass metadata retains all original provenance
and now includes the effective navigation timeout and capture-policy hash.
Prepared-only receipts have no renderer version because nothing was rendered.

Before capture, all accepted snapshots are verified and grouped by **cluster ID**.
Any new member must match its cluster's already-accepted renderer version. A
future update that conflicts with a partially accepted cluster refuses admission;
a passing drift receipt does not authorize mixing versions or rewriting evidence.
For GO2, renderer version is a **cluster-level covariate** and remains matched
within clusters, including arms and views. Treat cross-version comparisons as
conditional on that covariate; a tolerance pass does not erase renderer provenance
or create additional independent observations.

After Opus integrates this commit into the native capture worktree, run one
already-accepted complete cluster into a new directory:

```bash
cd "$HOME/Developer/Opensens/worktrees/oae-mve-wo1b"
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  python3 -m mve.observer.renderer_drift \
  --plan mve/observer/config/wo1b_manifest.json --batch 0 \
  --drift-cluster spectral-ordinary-0 \
  --drift-from mve/generated/wo1b-d286a45abc8187fd \
  --drift-output mve/generated/wo1b-renderer-drift-20260929-001 \
  --page-load-timeout 120 --max-load 20
```

`--batch 0` labels the drift attempt; `--drift-cluster` determines its exact jobs.
All blocks and both views of that cluster must already be accepted. Two fresh
passes are captured in the separate directory, whose prior existence is refused.
The isolated worker's write allowlist is the new directory. The accepted tree
is read only, and overlapping output paths are rejected. `drift.json` binds old
and new completion hashes, both browser versions, byte-exact numeric equality,
and each corresponding blind-PNG comparison. It reports
`pixels_over_threshold_fraction`, maximum channel difference and dimensions under
the unchanged WO-1 tolerance: channel threshold 8/255, fraction at most 0.001,
same dimensions required. Any failed comparison gives a nonzero exit and retains
the sealed failed drift receipt. No actual native drift result is claimed here.

## Manual quarantine and resume

Admission recognizes `quarantine/` as non-snapshot evidence. It verifies each
record's schema, attempt identity, hashed original attempt receipt, unchanged
source audit, batch selection, exact directory/file sets and every listed file
hash, including empty partial snapshot directories. Symlinks and unsafe names
are refused. Quarantine bytes remain part of generated-byte admission. Admission
receipts record the SHA-256 of each verified `QUARANTINE.json`. There is no
quarantine creation, move, deletion or automatic repair code.

The two existing records are:

| Record | Partial pass-0 captures | QUARANTINE.json SHA-256 |
|---|---:|---|
| `quarantine/batch-007-000` | 5/10 | `f7fb5c8a7a9bba144e0db1d7ca5513c86e5dd657d8f9002e7297393fbded9dfd` |
| `quarantine/batch-007-001` | 9/10 | `f462e698ef599d1e7e039aded3dcbefb03c7a6b6adbbfa122778cec7bc59c9bd` |

Both preserve the same ten snapshot IDs. Their original attempt receipt hashes
are respectively `ce5e41a4359cb3e8be1e3932309a91374c92a9c9dc0e47b6eec8fe0f0571f58d`
and `c8a676f71493aab5797d5521e042d4d71f6f2f1fcc0c4bcbdbb42416f228fc02`.
Quarantine totals 913,377 bytes. Owner evidence totals 5,232,526 bytes;
its generated parent totals 7,601,733 bytes. Admission for 210 remaining snapshots,
pathspec archives and receipt allowance projects 140,900,742 bytes, below
209,715,200. The 5 GiB free-space floor and all existing write/extraction guards
remain in force. The local worktree has no generated capture evidence.

The read-only regression verifies all 70 completion records, skips them, and
selects exactly the ten IDs in both quarantine records. The copied-evidence
integration regression captures batch 7 twice with mocked browser packets,
accepts ten fresh completions, and confirms every old snapshot and the original
owner tree are unchanged by path, bytes, hash, mode and mtime. A native capture
is still Opus's responsibility. Details and the ordered IDs are in
[WO1B_ROBUST_EVIDENCE_20260929.json](WO1B_ROBUST_EVIDENCE_20260929.json).

Use the following exact sequence after review/integration in the worktree holding
the evidence. It stops on the first refusal. `--max-load 20` is an optional
operator policy for this command, not part of the experiment or manifest. A
host-load refusal leaves no attempt directory; rerun explicitly when appropriate.
Do not delete partial evidence to force a retry.

```bash
cd "$HOME/Developer/Opensens/worktrees/oae-mve-wo1b"
set -e
for k in $(seq 7 27); do
  PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
    python3 -m mve.observer.snapshot_batch \
    --plan mve/observer/config/wo1b_manifest.json --batch "$k" \
    --page-load-timeout 120 --timeout-per-pass 1860 --max-load 20
done
for k in $(seq 0 3); do
  PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
    python3 -m mve.observer.capture_c --batch "$k" \
    --page-load-timeout 120 --timeout-per-pass 780 --max-load 20
done
```

This is native offline capture only; it does not run the hosted WO-6c pilot.
The untouched accepted 70 and manual quarantine remain in their original paths.

## Validation and review

Tests were written first: the initial new regression module failed collection
because `capture_policy` did not yet exist. Offline tests exercise explicit goto
timeout/no retry, derived limits, subprocess ceiling propagation, nested deadlines,
load refusal before mkdir, immutable output races, version changes within/between
passes and batches, legacy completions, quarantine corruption and a measured 10%
pixel-difference refusal with byte-exact data. Browser lifecycle tests use mocks.

Final focused run: **186 passed, 2 skipped in 64.72 seconds**. Changed executable
line coverage is **266/268 (99.25%)**. Combined statement/branch coverage is 100%
for `capture_policy` and `capture_evidence`, 96% for `renderer_drift`, 98% for
`snapshot_batch`, 97% for `snapshot_render`, 96% for `snapshot_capture`, and 93%
for `capture_c`; every changed runtime module exceeds 90%. The two focused skips
are existing native nested-sandbox checks. Ruff and `git diff --check` pass.

Current runtime/test pins were refreshed in WO-1b and WO-6c. WO-6b also consumes
`snapshot_render.py` and `snapshot_capture.py`: its shared-file pins were refreshed
and the new `capture_policy.py` dependency added after its tests correctly refused
stale pins. WO-6b's approval (`2026-09-28`), design and archived evidence remain
unchanged. No other packet's generated evidence was modified.

Local review checked historical hash binding, complete-record acceptance ordering,
cluster joins across batch boundaries, both parent and worker version checks,
deadline cleanup, pathspec-only archives, byte/free-space guards, exclusive writes,
separate drift output and manual-only quarantine. No visual equivalence is claimed
until Opus executes the native drift receipt command.

Reproduction:

```bash
PYTHONDONTWRITEBYTECODE=1 COVERAGE_CORE=pytrace OPENBLAS_NUM_THREADS=1 \
  python3 -m pytest \
  tests/mve/observer/test_capture_robust.py \
  tests/mve/observer/test_snapshot_batch.py \
  tests/mve/observer/test_snapshot_inventory.py \
  tests/mve/observer/test_wo1b_review.py \
  tests/mve/observer/test_snapshot_capture.py \
  tests/mve/observer/test_wo6c.py -q \
  --cov=mve.observer.capture_policy --cov=mve.observer.capture_evidence \
  --cov=mve.observer.renderer_drift --cov=mve.observer.snapshot_batch \
  --cov=mve.observer.snapshot_render --cov=mve.observer.snapshot_capture \
  --cov=mve.observer.capture_c --cov-branch

PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages" \
  python3 -m pytest tests/mve -q
```

Full `tests/mve`: **1,236 passed, 7 failed, 4 skipped in 120.64 seconds**.
All seven failures are the established nested-sandbox cases below; a fully green
native-host run is not claimed. Opus must rerun these outside this sandbox:

1. `tests/mve/test_formalizer_g3.py::test_real_lean_repairs_statement_without_proof`
2. `tests/mve/test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
3. `tests/mve/test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
4. `tests/mve/test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
5. `tests/mve/test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
6. `tests/mve/test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
7. `tests/mve/test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

The native subprocess failures report `sandbox-exec: sandbox_apply: Operation not
permitted`; the timeout fixture exits before reaching its intended timeout. The
four skips are the two native snapshot sandbox checks and the pre-existing
opt-in size-calibration and full Odlyzko reproduction checks. No functional or
source-pin failure remains. The final local commit hash is in the handoff message,
avoiding a self-referential hash inside its own commit.
