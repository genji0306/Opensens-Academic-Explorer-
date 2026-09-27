# WP-0a offline preflight — r5, 2026-09-27

Original probe base: `5645250003f` (r5 PASS), authoritative observation schema v5.
Review-fix branch rebased onto `github/mve/integration` at `ab3b8dd3e84`. The packet was
re-read after the owner's correction. The superseded builder r2 self-check commit
`0a338dc305e` is absent from this branch's ancestry; the reviewed r5 packet is unchanged.

Run `python3 -m mve.preflight.offline`. Capability receipts are in
`mve/preflight/results/report.json`; actual file bytes and git revisions are pinned in
`mve/DEPS.lock`. Nonzero exit records failed required capabilities; it is not a claim
that the report failed to write. **No hosted model calls; API spend USD 0.**

| Capability | Result |
|---|---|
| Vision callable / raw retention | Executed with injected fake transport; signature and two retained raw responses recorded |
| Runner in-flight reservation | **Failed**: two fake cells charged USD 0.08 against a USD 0.05 simulated cap |
| Runner peak refusal | **Failed**: both fake cells invoked while the rate function returned peak; UTC boundary outputs recorded separately |
| RH Jev tests | **308 passed**, 3.48 s, Python network/keychain guard active |
| Local openJev fixture | Ran with 38 input tokens; response, load/forward latency and runtime package versions retained |
| Newclid import | Failed: module absent in selected Python |
| Newclid JGEX round trip | Failed prerequisite: import unavailable; no round-trip claim |
| Actual GeoGebra dependency terms | Unavailable; no licence conclusion |
| Lean toolchain presence | Ran `lean --version`: 4.29.0, arm64, pinned commit in receipt |
| Atlas ingest contract | Executed exact `validate_bundle` signature and empty-bundle rejection; positive MVE ingest unverified |
| Codex CLI | Reports 0.154.0 |
| Euclid discovery | No local checkout in bounded vendor/references/Developer/worktrees/runtimes roots; fixture unavailable offline |
| rhvf / Explorer / local prover host | Sources pinned; isolation, scene integration and prover hosting unverified |

The openJev fixture selected topology for a triangle workflow with low confidence. It
establishes inference availability, not accuracy. Its probabilities renormalize away
abstention while confidence does not; WP-5 must adapt this explicitly.

The two runner findings belong to WP-0a and require WP-9a enforcement repairs before
WP-0b. Pricing, hosted image support and live latency are **deferred to WP-0b**, not WP-0a
failures. The report leaves vision/human timing fields null. The earlier r2 attempt at an
isolated Lean build failed on unavailable isolated dependencies with network denied; r5
correctly scopes that build to WP-6a, and the current runner only checks toolchain presence.

Euclid's two-engineer-hour stop criterion is recorded but has **not** been exhausted.
No in-house fallback has been selected. An available checkout and executable fixture
remain discovery work; directory absence does not establish generator incompatibility.

Review-fix validation: **18 offline preflight tests**, **160/171 covered statements
(93.6%) across all preflight code, including the child-only audit guard**.
Combined with the merged packets: **245 passed, 94% coverage**, no pytest warnings with
`COVERAGE_CORE=pytrace python3 -m pytest tests/mve -q --cov=mve --cov-report=term-missing`.
The earlier 98% number covered only core/dispatcher; Opus correctly measured 65% for
that original packet as a whole. This revision tests `vision_contract.exercise()` with
an injected runner stub and openJev's extracted `exercise(backend, request)` with fake
backends. The CLI entry points are thin and tested with injected modules. Real dependency
capability receipts above remain the original offline run, not newly claimed executions.

The fake runner test exercises execution beyond the plan's import-only wording, as accepted
in Opus's review; it performs no HTTP. Both findings remain reproduced with fake responses.
The temporary peak-rate override is restored after execution. Dependency paths now share
`mve/preflight/config.py`; schema checks work after changing cwd away from the repository.
Default preflight publication preserves other reviewed packets in the aggregate DEPS.lock.
The warning came from an incompatible native coverage tracer in this Python installation;
using its supported Python tracer produced the warning-free validation above.
Ruff and the 800/50-line checks pass.

Manual review covered fake-only transport, guard propagation, explicit failure labels,
actual-byte pins and separation of executable inference from measured accuracy. No
credentials are resolved. Dependency execution disables Python bytecode and pytest cache
writes; no Desktop working-tree files were changed. The integration branch has no wiki
manifest/refresh script; no main-checkout refresh was attempted.

Handoff: the unfinished r2 WP-1 tests are preserved in the local stash named
`mve: preserve unfinished r2 semantics tests before r5 rebase`; they are not implementation
of the v5 contract. The owner subsequently authorized continued development. WP-0a corrections are
committed on the r5-based preflight branch for Opus review; the earlier r2-based remote
head is superseded using a lease-protected update. WP-0a remains unmerged for re-review; Opus has merged WP-1, WP-9a and WP-11a separately.
