# WO-1 lab snapshot adapter — Astra handoff

Built on `codex/mve-wo1-snapshots`, base `d6a6a6efea4ab394d5c378e06a2a112ba0a064fe`.
Offline only; sole builder; Opus reviews, runs native capture outside the nested sandbox, and pushes.
No atlas/lab build, publish, download, hosted call, or source-worktree edit was performed.

## Delivery and validation boundary

Per-pass timeout follow-up to `ebf704002c1` (2026-09-28): Opus reports a
**successful first native pass** outside the builder sandbox. All eight snapshots
(four modules plus control twins) produced `full.png`, `blind.png` and `data.json`;
Opus inspected the blinded crops and found them clean. The repeat pass then hit
the old 300-second deadline shared by both passes. Byte-identical native repeat
verification remains pending. This report supersedes the older native-capture
status below; the historical evidence JSON is unchanged.

Each pass now receives a fresh wall-clock timer, default **300 seconds**,
configurable with `--timeout-per-pass` (integer seconds, 1–900). The worker arms
the timer around each browser pass and cancels it on exit. The parent independently
enforces a **900-second overall worker cap**, even if configured pass budgets sum
to more than 900 seconds. Existing worker/Chrome process-group cleanup and the
five-second reap bound are unchanged. Rendering, blinding and hash comparison are
unchanged.

Focused validation: **55 passed, 2 skipped** across `test_snapshot_capture.py`
and `test_snapshots.py`; Ruff lint/format checks and `git diff --check` pass.
Regression tests cover two passes whose combined duration exceeds one pass's
budget, default/custom budgets, first/second-pass expiry, a real wall-clock timer,
argument validation, worker argument forwarding and the overall cap with group
cleanup. The two native OS sandbox tests remain skipped in this nested sandbox.
No native capture was rerun here. Opus should retry with a new output directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m mve.observer.snapshot_capture \
  --output mve/generated/wo1-opus-per-pass-timeout --repeat --timeout-per-pass 300 \
  --chrome '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

Chrome OS-sandbox follow-up to `8b5c09a9238` (2026-09-28): the Pillow fix works,
but Chrome ignores TMPDIR for its SingletonSocket and uses the Darwin user temp
directory. Its own sandbox also cannot initialize inside `sandbox-exec`. Opus
reports an outside-builder-sandbox headless screenshot with the supplied OS
profile and `--no-sandbox`, while curl to `https://example.com` remained refused.
That reported smoke result is not a completed WO-1 capture or repeat receipt.

The profile now denies `network*` with only local/remote **Unix socket** exceptions;
there is no inet allowance. It retains this run's worktree output, fresh private
runtime and `/dev/null` write exceptions, and adds the canonical paths returned by
`getconf DARWIN_USER_TEMP_DIR` and `DARWIN_USER_CACHE_DIR`. If either lookup fails
or returns a path outside `/private/var/folders`, it uses the authorized
`/private/var/folders` fallback. Here the temp lookup succeeds but the cache lookup
reports `Input/output error`, so the fallback applies. The narrow pair still needs
native verification on a host where both lookups succeed; it does not silently
broaden on a Chrome failure. These allowances supersede the earlier profile below.

Chrome explicitly receives `--headless=new`, `--no-sandbox`, crash-reporter and
Breakpad disable flags, and a private user-data directory. **`--no-sandbox` is safe
only because the enclosing OS sandbox continues to deny internet access and
writes outside its explicit output/runtime allowlist.** Do not run this capture
without that OS sandbox. Private HOME/TMPDIR and the parent Python user base remain.

At that revision, the worker had a 300-second wall-clock deadline covering both
captures with `--repeat`, superseded by the per-pass fix above. A
short launcher records Chrome's group ID before exec: Playwright launches POSIX
browsers in separate process groups, so killing just the worker is insufficient.
The parent always SIGKILLs the worker group and every recorded Chrome group on
success, nonzero exit, timeout or wait exception, including when Chrome's leader
has exited but an updater remains. Cleanup precedes deletion of the private runtime
and the existing source-tree audit. Runtime lookups and the write probe are also
bounded. The 500 MiB generated-output cap, 5 GiB free-disk floor and bounded pinned
archives are unchanged.

Focused validation: **44 passed, 2 skipped**. The complete observer suite has
**98 passed, 4 skipped**, with **98%** combined coverage of the three snapshot
modules. Ruff and `git diff --check` pass. Tests assert the complete profile,
canonical narrow paths and fallback, explicit browser flags, deadline and group
kills on normal completion/timeout. A real subprocess fixture leaves a child
holding a pipe after its leader exits; group cleanup kills that child and releases
the pipe. Real OS tests for Unix IPC, IPv4/IPv6 denial and outside-write denial are
skipped here with the explicit nested `sandbox_apply` restriction. The write-denial
fixture now lives outside Darwin's allowed temp tree. No native Chrome capture was
attempted here; Opus must rerun native capture and byte-identical repeats outside
the builder sandbox using a new output directory. Earlier counts and the evidence
JSON remain historical receipts.

Python user-site follow-up to `f3992721a338d75578a477b96470ef4ab9ecd099`
(2026-09-28): Opus reports that the short private Chrome runtime now works,
but the sandboxed Python worker fails importing Pillow: the framework `_imaging`
extension is x86_64 while the process needs arm64. Opus verified that working
arm64 Pillow and Playwright are installed in the parent's user site; changing
HOME hid that site and exposed the stale framework installation.

The worker environment now explicitly sets `PYTHONUSERBASE` to the parent's
`site.USER_BASE`, preserving access to those installed packages. HOME and TMPDIR
remain the private `h` and `t` directories, and `PYTHONDONTWRITEBYTECODE=1` remains
set. The sandbox grants no writes to the real user base. The write allowlist,
network denial, runtime cleanup, socket length guard, pinned pathspec archives,
500 MiB generated-output limit and 5 GiB free-disk floor are unchanged.

Validation for this follow-up: **36 passed, 1 skipped** in the focused fixture
suite; combined Python coverage **98%** (rounded); Ruff and `git diff --check`
pass. The new parameterized regression test failed before the fix for both an
absent and a stale inherited PYTHONUSERBASE; it now verifies the parent's resolved
user base together with private HOME/TMPDIR and disabled bytecode writes. The
OS denial test remains skipped because nested `sandbox-exec` is unavailable.
No native capture was attempted here; Opus must retry outside the builder sandbox
to verify worker imports, completed capture and byte-identical repeat hashes.
Earlier validation counts and the evidence JSON remain historical receipts.

Isolation follow-up to `7233da17d5f` (2026-09-28): Opus reported **940 passed**
outside the builder sandbox, but native capture failed inside the adapter's own
profile: Chrome could not create its ProcessSingleton socket directory and tried
to write Crashpad settings in the real `~/Library`. This was an adapter isolation
configuration defect, not evidence of an already-running capture profile.

The wrapper now allocates a fresh mode-0700 directory using `mkdtemp` via
`TemporaryDirectory(prefix="mvewo1-", dir="/private/tmp")`. Its short `h` and `t`
children supply HOME and TMPDIR to both the worker and Chrome. Separate `capture`
and `repeat` profiles live inside it; Playwright's persistent-context
`user_data_dir` argument emits `--user-data-dir` for Chrome. Crash reporter,
Breakpad, first-run and default-browser checks are disabled. The sandbox permits
writes only to this run's output directory and this exact private runtime subpath
(plus the existing `/dev/null` exception); network remains denied. A runtime guard
reserves 64 suffix bytes and requires the encoded socket path to stay below 100
bytes. The private runtime is removed on success, probe failure, launch exception,
and nonzero worker exit, before the source-tree audit runs.

Follow-up validation: **34 passed, 1 skipped** in the focused fixture suite;
combined Python coverage **98%** (rounded); Ruff and `git diff --check` pass.
Tests assert the complete sandbox profile, private directory permissions, socket
length bound, browser flags/environment/profile placement, fresh allocation and
cleanup on each exit. The pre-existing disk budget and pathspec archive tests still
pass. **No Chrome launch or native capture was attempted during this follow-up.**
The full suite was not rerun here; 940 passed is Opus's reported prior result.
The evidence JSON and older verification counts below describe the original packet,
not this follow-up. Native capture and byte-identical repeat results still require
Opus's retry with the command below.

Implemented the C1 adapter, bounded archive preparation, native render adaptations,
blinding, manifest validation, WO-2 source bindings, and isolation receipts. **Native
browser capture remains unverified here.** During the original build, installed Chrome exited with
`TargetClosedError`; nested `sandbox-exec` also fails with
`sandbox_apply: Operation not permitted`. The authorized fallback is exercised:
fixture HTML tests, actual Node execution of its planted canvas text and suppression
hook, synthetic PNG tests, and mocked browser orchestration. These are not lab captures.

There are **zero captured lab PNGs**, four planned development pairs, and zero
allocated independent discovery/replication/donor blocks. The requirement for at
least ten real and ten null blocks is short by ten each. Repeated views/seeds must
not be called independent blocks. Every initial manifest record is development-only
and `go2_eligible: false`; no GO gate is established.

Code:
- `mve/observer/snapshots.py`: C1 validation, atlas index reader, hash/PNG utilities,
  bounded archive extraction, source-tree audit, and `card_source()` for WO-2.
- `mve/observer/snapshot_render.py`: native page capture from a virtual origin;
  source changes are applied to response bytes in memory, never to archive files.
- `mve/observer/snapshot_capture.py`: prepare/capture command and OS isolation wrapper.
- `tests/mve/observer/test_snapshot*.py` and `snapshot_fixtures/`: offline tests.
- `WO1_SNAPSHOTS_EVIDENCE_20260928.json`: numerical, source-patch, coverage and isolation evidence.

## Pinned input and control table

Atlas: `97b1e48cb1075aea431cf754cc84f2eeabb3dfb9`.
Lab: `c81510cd29b0fc666b1f171a9604a51be9661576`.
The atlas distribution supplies the rendered modules. The lab export supplies the
reference SwiftShader capture script. Only the two authorized pathspec archives
are used. No whole-repository archive is possible through the adapter.

| Module | Selected canvas and real data | Seeded, control-only twin | Qualification |
|---|---|---|---|
| 05 spectral | `spectralPlot`; zeros 11–100, 89 unfolded gaps | Seed 20260926; matrix dimension 64; first 89 gaps from native `gueSample` | Native comparison overlay is adapted to one histogram, fixed density range 0–2 and the same mint palette; comparison curves removed from this canvas. Owner heading/legend identify the single sample. |
| field-dyson | `fieldSide`; native pair/spacing plots, first 1000 zeros when local data load | Native GUE selector, seed 20260926; 8 matrices × 200, 960 retained levels | Off-line-pair checkbox is **not** a null twin. It stays off; animation starts paused. Both bar palettes are white; identical analytic reference curves remain. Native sample sizes differ (1000 vs 960), so this is not a calibrated matched-block experiment. A local-file fallback to 100 zeros would be explicit in exported ordinates. |
| 11 Ulam (`polar-ulam`) | `polarPlot`, N=30000, polynomial overlay off | Native Cramér-only source, seed 20260925 | Same mint palette; control stamp suppressed; fixed header/footer masks. No real points are overlaid. |
| space-08 prime sphere | Geometry `primesphere` canvas; N=100000, Viviani, α=β=1, q=44 | Native replacement Cramér set, seed 2026 | Native class-based palette is shared; no real cloud remains in the twin. Geometry route is `#primesphere`; atlas link is `#labs/space-primesphere`. The current lab comments number this scene 07; the requested packet key stays `space-08`. |

The four native numerical generators were run twice under installed Node v22.22.2;
all arrays reproduced exactly. Counts: spectral 89/89; Dyson 1000/960 levels;
Ulam 3245/3284 points; sphere 9592/9594 points. These numerical array hashes are
separate from future browser-exported JSON hashes. Seven transformed native JS
files passed `node --check` against the pinned archive. This does not establish
WebGL/browser runtime correctness.

The five committed atlas snapshot metadata entries are read. Their PNGs are outside
the permitted archive pathspec, so all are recorded `not_in_allowed_archive`.
The legacy atlas params-hash algorithm is also outside the permitted export; its
claimed hash is preserved as unverified, alongside an independent canonical params
hash. New MVE manifests use the WO-2 canonical JSON digest, not that legacy claim.

## Capture and blinding contract

Each successful manifest records module/deep link, shared requested params and hash,
both commits, exact exported numerical JSON and hash, generator/seed/block/stratum/role,
reciprocal twin identity, full-page owner PNG, blinded PNG, dimensions/crop/masks,
withheld owner text, native input state and its hash, and renderer versions.
The full-page owner view retains the surrounding native lab context; selected
canvases have the documented in-memory adaptations. Blinding re-renders the same
native canvas with text calls suppressed, then crops and re-encodes it. It is not
claimed to be merely a byte crop of the owner PNG.

Chrome uses the archived script's SwiftShader flags, 1440×1100 viewport, scale 1,
fixed seeds, en-US locale, UTC, static selected views and fresh profiles. PNG/data
SHA256s are computed from actual output bytes. `--repeat` requires byte-identical
full PNG, blinded PNG and data hashes across two independent contexts; a mismatch
fails. That native determinism check is pending, including MathBox readiness and
full-page layout stability.

Blinded paths use opaque IDs. Deliver **only** `png_blinded` bytes to a model; owner
manifest, labels, deep links, native states, twin map and source JSON are withheld.
No observer runner or randomized presentation order is introduced in WO-1.

Text defenses: canvas-only crop; suppress both Canvas2D text APIs on redraw; fixed
spectral and Dyson label-band masks; fixed Ulam header/footer masks; hidden geometry
DOM pole labels; same arm palettes. New RGB encoding permits only IHDR/IDAT/IEND
chunks. Pixel-region tests reject planted unmasked caption pixels; Node tests show
planted HTML canvas text before blinding and its suppression afterward. Tesseract,
if installed, scans every blinded PNG for owner strings and a vocabulary of answer
terms. It was absent from PATH and the usual Homebrew locations here. The fallback
is explicitly recorded in each PNG receipt: these rules cannot prove absence of
rasterized/WebGL text, and OCR itself would not suffice as proof. Opus must inspect
the actual blind crops. The committed 611-byte PNG is a **synthetic pixel fixture**,
not a lab capture or an HTML rasterization; its hash and chunk list are committed.

## Isolation and disk evidence

Every command archives into its newly created `mve/generated/.../stage`, then deletes
that stage, including on failure. Only allowlisted regular files/directories extract;
links/traversal and archives over 64 MiB fail. Before writes, free disk must be at
least 5 GiB and projected generated usage below 500 MiB. Browser capture additionally
runs under `sandbox-exec`: inet denied, Unix IPC allowed, writes denied outside this
run's output, fresh `/private/tmp/mvewo1-*` subpath, Darwin temp/cache paths (or the
documented `/private/var/folders` fallback) and `/dev/null`. The worker and Chrome
use the short private HOME/TMPDIR and private browser profiles described above. All page
requests are fulfilled from the archive by Playwright; remote/missing paths abort.
No local HTTP listener or download is needed.

The OS probe opens existing atlas/lab files with O_WRONLY but **without** O_TRUNC,
O_CREAT or any write: it must receive PermissionError, and cannot change file bytes
even if protection is defective. It cannot run inside this nested sandbox; the
fixture denial test is explicitly skipped, not counted as an isolation pass.

Two narrow audits passed: preparation and the failed isolated-capture attempt each
had unchanged source trees, unchanged full `git status --ignored` results, and
unchanged archive trees. The **whole-session audit did not match**: four atlas
files changed during the session, while the lab tree and both status outputs stayed
identical. Observed changed atlas files:
- `vendor/zeta-explorer/dist/obligations-euler.js`
- `vendor/zeta-explorer/dist/obligations-heat.js`
- `vendor/zeta-explorer/dist/obligations-li-math.js`
- `vendor/zeta-explorer/dist/obligations-li.js`

This drift is recorded without attributing it or claiming a whole-session isolation
pass. No working-tree source was used for rendering; the adapter uses pinned git
objects. Its own before/after mismatch raises an error, even if rendering succeeded.
Audit scope is every file, directory, symlink, content hash and metadata under the
allowed source pathspecs (including ignored entries: 372 atlas, 383 lab), plus full
repository ignored-file status. It is **not** a content hash of unrelated directories
in the multi-GB repositories. Raw receipts remain in ignored `mve/generated/`;
portable summary hashes are in the committed evidence JSON.

Staging copies were removed. Final `du -sh mve/generated`: **2.2M**. Final checked
`df -k /` available: **10120000 KiB**, above the 5 GiB floor. No PNG over 300 KB is
staged or committed; full-page images and future large artifacts remain ignored.

## Verification and exact commands for Opus

Original packet (before this isolation follow-up): **30 passed, 1 skipped**; Python statement coverage **98.98%**, branch
coverage **94.77%**, combined **97.89%** (every new Python file >90% combined).
Inline browser JS is not claimed covered by the Python percentage; the text hook
is executed with the offline HTML fixture in Node. Ruff passes.
Full `tests/mve`: **932 passed, 7 skipped, 3 failures**; all three are pre-existing
nested-sandbox-only failures, with `sandbox_apply: Operation not permitted`:
- `tests/mve/test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
- `tests/mve/test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
- `tests/mve/test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

Run from this worktree outside the nested sandbox, with other atlas/lab sessions
quiescent for the source-tree comparison. This command does not build or publish:

```bash
cd "$HOME/Developer/Opensens/worktrees/oae-mve-wo1"
df -k /
PYTHONDONTWRITEBYTECODE=1 python3 -m mve.observer.snapshot_capture \
  --output mve/generated/wo1-opus-private-runtime --repeat \
  --chrome '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The output directory must be new; choose another `mve/generated/...` name on retry.
Keep the hard disk limits: only pinned pathspec archives, `mve/generated` below
500 MiB, and abort if free disk is below 5 GiB. The existing guards remain enabled;
do not make a whole-repository archive for this retry. Browser runtime directories
are short, temporary and removed after the worker exits.
Do not bypass OS isolation if Chrome fails. Inspect private `browser.log` and the
failure receipt. A successful run emits `capture/manifest.json`, owner/full PNGs,
blind PNGs, data JSON, `repeat-verification.json`, source and isolation receipts,
then removes staging and profiles. Review each blind crop before using it. Native
capture success and matched-block allocation remain separate obligations.

```bash
PYTHONDONTWRITEBYTECODE=1 COVERAGE_CORE=pytrace python3 -m pytest \
  tests/mve/observer/test_snapshots.py tests/mve/observer/test_snapshot_capture.py \
  --cov=mve.observer.snapshots --cov=mve.observer.snapshot_capture \
  --cov=mve.observer.snapshot_render --cov-branch
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python3 -m pytest tests/mve
```

Opus should retain the manifests/hashes and explicitly stage only inspected blind
PNGs ≤300 KB if native capture succeeds. Large/full PNGs stay ignored. No push,
merge, publication, or live observer call is part of this packet.
