# WP-3 offline perceiver — Astra handoff, 2026-09-27

Built on `45b3b028fdd` in `codex/mve-wp3-perceiver`, solely in the assigned worktree.
Opus reviews, merges and pushes. Nothing was pushed. No network, downloads, hosted calls,
provider SDK, HTTP client or API-key reader was introduced or used.

**Status: implementation complete for offline review; full-suite acceptance is blocked by
this session's nested-sandbox restriction.** Do not report the full suite as green.

Tests-first commit: `3e8449d0738`. Implementation commit:
`ab1e384e7a054b02f04b5b65517e86bbe765da52`.
The frozen r5 plan (§4a, A1, §7 and WP-3), kickoff, and all three Opus review addenda
were the inputs; the current packet's offline restriction supersedes the kickoff's old
live-probe allowance. No changes to the frozen plan, registry, schema or sealed corpus.

## Delivered

- `mve/perceiver/`: immutable `ImageInput`, `Replay`, `PerceptionResult` and validated
  `Record`; pinned `deepseek-flash` contract, temperature 0, thinking disabled, JSON-only
  observation grammar. DeepSeek V4.1 Flash is the intended vendor name; the alias mapping
  and image capability remain **unverified vendor claims**. Any other requested model,
  including V4-Pro, is refused before reservation.
- Two independent logical calls with the same image and prompt. Call 2 receives no call-1
  output. Each logical call permits 0–2 retries (default 2), at most six dispatched
  attempts. Every retry has a new attempt ID and a separate reservation/receipt.
- `probe.dispatch_fixture` extracts the merged WP-0b dispatch boundary for reuse. The
  single WP-0b probe still uses its original fixed ID, phase and one-shot semantics.
  The shared path checks exact `FakeTransport` type, verified ledger prices, positive
  token ceiling ≤ USD 0.05, atomic P0/P1 reservation, persisted request/image, and
  off-peak recheck before send. WP-3 defaults to P1. There is no hosted adapter mode.
- `Replay` accepts only frozen tuples of bounded `ProbeReply` values or explicit local
  fault tags. It constructs the shared boundary's exact fake transport; there is no
  arbitrary callback or transport injection point. Input PNG limits are the merged
  4 MiB / 1024-pixel-edge contract; reply bytes are bounded at 1 MiB. Token reservations
  use fixed upper bounds of 4096 input and 4096 output tokens.
- Exact response bytes are closed to `response.raw` **before either parser runs**.
  Each attempt retains request, image, raw hash, returned model, usage, latency, price,
  window policy, reservation and receipt hash. Timeout/transport errors explicitly have
  no received raw bytes. Post-dispatch persistence failures retain ledger exposure.
- Outcomes distinguish `refused`, `malformed`, `truncated`, `model_mismatch`,
  `out_of_image`, `missing_entities`, `timeout`, `transport_error`, `usage_missing`,
  `usage_bound_exceeded` and `invalid_billing`. Refusals are not retried. Model mismatch,
  usage-bound violation and invalid billing freeze through WP-0b; overcharges remain
  unclamped and freeze the ledger. Missing billing never becomes zero.
- Strict parsing rejects extra authority fields, duplicate JSON keys, non-finite values,
  invalid IDs, unknown predicates, bad geometry, unresolved arguments and reasoning
  output. The shared envelope inspector additionally handles excessive nesting and
  non-string model values as malformed instead of crashing receipt serialization.
- Geometry-only Hungarian matching uses the pinned
  `mve/measurement/perceiver_alignment_v1.json`: dimension-normalized parameter distance,
  threshold 0.03, matching cardinality then distance, segment/line endpoint symmetry.
  Row/column distance ties within 1e-12 remain ambiguous and unmerged. Unmatched entities
  survive separately. The threshold is an **uncalibrated engineering fixture setting**.
- Both successful replies become one v5 record with separate call-specific geometries
  and observation dependencies. Labels from both calls remain in their presence
  observations; matched entity labels use call 1. Relations are canonicalized after ID
  alignment. No assumptions, premises, derivations, judgments, measurements or formal
  propositions are manufactured. Geometry agreement cannot authorise a proposition.
- Records pass the authoritative schema through `Record` / `mve.semantics.validate`,
  including the checks in `mve/validation.py`. No schema extension was needed.
  `mve/DEPS.lock` now has a WP-3 packet pinning source, contracts, fixture manifest,
  local package versions and selected imported package/solver files.

## Records, failures and accounting

`perceive(ledger, ImageInput(png), replay=Replay(tuple_of_replies), output=..., nonce=...)`
returns `PerceptionResult`. `result.record` is a v5 record only when both logical calls
have a valid observation response; otherwise it is `None`, and the retained receipts
carry the incomplete outcome. `result.report()` returns an independent JSON copy.
Output directories are exclusive; a nonce cannot redispatch an existing ledger attempt,
even through another output directory. There is no automatic resume or retransmission.

Each run writes `contract.json`, per-attempt directories, `receipt.json`, and, on success,
`record.json`. Schema v5 caps `perceiver_calls` at two: this counts the two selected logical
replies, with their two raw hashes. All retry attempts and discarded replies remain in
`receipt.json` and their own files, never silently dropped from cost accounting.

`receipt.json.simulated_cost_usd` sums **replay billing metadata across every attempt**.
It is a decimal string, labelled `cost_basis: simulated_replay_metadata`. If any billing
is missing/invalid or an attempt times out, the total is null; the known subtotal and
unknown-attempt count remain explicit, and unsettled reservations remain in the ledger.
Fixture billing is independent synthetic metadata, not a vendor price calculation.
The successful two-reply fixture costs USD 0.003600 **simulated**.

`record.provenance.cost_usd` and `actual_api_cost_usd` are **actual hosted spend: zero**.
The record's event note and `wp3:simulated` provenance identify the replay and point to
its simulated receipt. Synthetic ledger prices may carry `verified: true` to exercise
that guard, but neither those prices nor the borrowed window are vendor-verified.

## Frozen development replay evidence

Five WP-2 E1a diagrams from the frozen split's **development** family
`oblique_parallelogram`, seeds 0–4, were regenerated once with the unchanged merged WP-2
code and then frozen under `tests/mve/perceiver_fixtures/`. They cover exact-positive,
near-miss, adversarial, not-to-scale and degenerate controls. PNGs, authored reply bytes
and compressed exact truth are hashed in the manifest. Reply IDs/order deliberately
change between calls. The manifest records their authored/fake origin.

The adapter receives only PNG bytes and authored replies. It imports no generator or
truth reader and accepts no truth-bearing record/path. Tests separately score against the
frozen development truth: false Parallel claims and true/false/degenerate Midpoint claims
remain observations even when both calls agree with confidence 1. Coincident points in
controls exposed ambiguous matching; the implementation now preserves that ambiguity.
No sealed-split truth was inspected or used to tune prompts, matching or fixtures.
These are protocol tests, **not perception accuracy measurements or a G1 pass**; null N/A.

## Validation

| Check | Result |
|---|---|
| Focused perceiver + existing probe tests | **135 passed**, 0 failed, 0 skipped |
| New perceiver tests within those | 96 cases |
| New modules line coverage | **302/302 statements, 100%**, each of 7 modules 100% |
| Shared `probe.py` / `probe_contract.py` coverage | 99% / 97% |
| Full `tests/mve`, Lean packages configured | **553 passed, 6 failed, 0 skipped** (559 total) |
| Full MVE line coverage | 93.71% (rounded terminal report 94%) |
| Unmodified base reproduction, six failing tests | Same **6 failures** |
| Static checks | Ruff E9/F and formatting; `git diff --check`; source/fixture pins match |
| Production size limits | Every changed/new production file ≤800 lines; functions ≤50 lines |

Commands run, using installed dependencies only:

```bash
COVERAGE_CORE=pytrace python3 -m pytest tests/mve/test_perceiver* tests/mve/test_probe* \
  -q --cov=mve.perceiver --cov=mve.preflight.probe --cov=mve.preflight.probe_contract

MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages" \
  COVERAGE_CORE=pytrace python3 -m pytest tests/mve -q --tb=short --cov=mve
```

`COVERAGE_CORE=pytrace` selects the installed Python tracer; the optional installed C
tracer has the wrong architecture. It does not alter test selection or application code.
Machine-readable counts and module coverage are in
`WP3_PERCEIVER_VALIDATION_20260927.json`.

The six failures are all existing checks:

1. `test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
2. `test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
3. `test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
4. `test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
5. `test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
6. `test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

Lean and worker logs report `sandbox-exec: sandbox_apply: Operation not permitted`
(exit 71). The timeout test also fails because sandbox launch fails immediately rather
than reaching its timeout. All six were reproduced from `git archive 45b3b028fdd`, staged
inside this worktree, with the same Lean-packages setting. The managed session forbids
escalation; no sandbox was bypassed, and no test was skipped, weakened or marked xfail.
Opus must rerun the full suite in an environment that permits nested `sandbox-exec` before
claiming the packet's required green full-suite acceptance.

## Known gaps and live activation

- No vendor interaction occurred. Model alias/revision, image support, actual token
  accounting, JSON response behavior, pricing, window, latency and cost are unverified.
  Replay latency measures local execution only. Token limits are fixture reservations;
  a live packet must establish conservative bounds including image/reasoning tokens.
- The matching threshold is unfitted; local ties conservatively remain unresolved.
  Variable-length curves/polygons must have equal parameter counts to match; their
  reparameterization and rotation are unsupported. Strand gaps are retained separately,
  but are not part of the matching distance. Presence diagnostics use unscored confidence
  0; model confidence is retained only for proposition observations.
- The adapter creates a fresh public-image execution record. It does not merge into a
  truth-bearing record, implement re-perception edits, adopt OCR/text premises, or perform
  image measurement, mark association, routing or proving. Those remain later packets.
- An exhausted replay, reservation refusal or disk failure raises rather than inventing
  a complete per-image receipt. Existing attempt artifacts and ledger state survive;
  post-dispatch exposure is never cancelled. Incomplete two-call runs have no v5 record.
- Live activation needs a separately reviewed and owner-authorized packet: verify and pin
  vendor model/vision behavior and price/window sources; obtain the owner's go for the
  single ≤USD 0.05 P0 probe; authenticate operator resume authority; implement and test
  hosted transport under the same durable boundary, conservative token bounds, deadlines,
  billing reconciliation and crash recovery. Do not toggle this replay adapter into a
  hosted mode or treat fixture `verified` flags as authorization.
- Before live evaluation, run inference in the existing WP-11 isolation boundary with all
  private gold roots denied, stage only public inputs, calibrate matching on permitted fit
  data, and keep the sealed evaluation untouched. G1 and real-data transfer remain open.
