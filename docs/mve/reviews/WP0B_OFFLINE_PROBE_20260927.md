# WP-0b offline probe refusal path — ready for Opus review

Base: github/mve/integration `d9066f6e1aa`. Branch: `codex/mve-wp0b-probe-guards`. This packet implements and tests the offline boundary before the single paid WP-0b probe. It does not complete the live probe or authorize one. Leave the branch unmerged for Opus review.

## Dispatch contract

`mve/preflight/probe.py` defaults to refusing hosted mode. No HTTP client, provider SDK, API-key reader or live transport is present. The only enabled mode is explicitly `offline_fixture`, and it accepts exactly the built-in local `FakeTransport`, not an arbitrary sender or a subclass. There is no flag that enables hosted calls. Opus must review this refusal path and the owner must say go before a later packet activates live transport.

The fake exercises the pre-dispatch path intended for that adapter:

1. Validate an immutable, bounded single-image request with positive integer input/output token limits, a bounded timeout and an explicit DeepSeek model id. V4-Pro image requests are refused. The 1024-pixel/4-MiB PNG limits are local probe constraints, not vendor capability claims.
2. Read the campaign's pinned WP-9a price entry. Missing prices or `verified != true` refuse before reservation or transport. WP-9a's estimation primitives remain usable for offline estimates; this new dispatch boundary enforces the flag.
3. Compute the conservative token ceiling with WP-9a, require a positive amount ≤ USD 0.05, and reserve it atomically in **P0**. Existing in-flight exposure counts against both P0 and aggregate caps. No fresh budget is created by the runner: the caller supplies the shared campaign ledger.
4. Persist the exact request/image, then call WP-9a `mark_dispatched`, rechecking the off-peak clock after preparation. The durable dispatch intent precedes the sender. There is one fixed attempt id, `wp0b:single-model-probe`, across threads, restarts and model changes within that ledger.

There are no retries. Even a cancelled unsent attempt consumes this runner's one-shot id; a later operational decision must resolve that state explicitly rather than silently resetting the campaign or generating a fresh attempt id.

## Failure and evidence handling

Unsent preparation/peak-boundary failures cancel the reservation. After dispatch, timeouts, transport failures, missing billing and simulated process loss retain the full reservation. Raw reply bytes are saved before parsing. Refusal, malformed content, truncation, missing usage and returned-model mismatch are separate outcomes.

A billing amount is transport metadata (`ProbeReply.billed_usd`), independent of model-generated text. Known charges are reconciled even if the model response is malformed. Missing/invalid billing is not treated as free. Charges above the reservation are recorded without clamping and freeze the campaign through WP-9a; token-bound violations, model mismatch and invalid billing also freeze it. A saved receipt hash accompanies settlement.

The receipt records requested/returned model ids, pinned price/source, the window policy, token bounds, usage, optional image-token count, latency, raw hash, reserved amount and billing metadata. Each fake run writes a `cost_model.json` with its simulated evidence separate from a **live** cost model whose model id, tokens, latency and cost are null, image support is unverified, and price verification is false. A successful fake never verifies image understanding or vendor support.

## Reproduction and evidence

Run only the offline fixture command, with a new output directory:

```bash
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  python3 -m mve.preflight.probe --offline-fixture --output mve/generated/wp0b-review-replay
```

The command computes a seven-case matrix: unverified price, peak time, crossing into peak before dispatch, an occupied P0 budget, an excessive probe ceiling, a successful fake reply and an uncertain timeout. The first five make zero transport calls; the last two each make one local fake call. Each case has an independent **fixture** ledger. The synthetic price evidence explicitly says it is not vendor verification or authorization; the fixture's true verification flag exists solely to exercise the permitted branch.

`WP0B_OFFLINE_REFUSAL_RECEIPT_20260927.json` is an exact copy of the code-generated report from `mve/generated/wp0b-refusal-final-20260927/`. The report computes source and artifact hashes; no refusal result or cost was manually inserted. These artifacts contain no live credentials or vendor evidence. The run also used an OS network-denying sandbox; that sandbox does not restrict filesystem access.

Validation: **463 full MVE tests passed, none skipped, 93% coverage**. The 39 probe tests pass separately with **98% coverage** after the source/artifact-pinning addition. Coverage includes concurrent one-shot admission, resume refusal, durable reservation before send, both clock checks, zero/oversized ceilings, phase/aggregate pressure, cancelled preparation, uncertain failure, charged malformed output, overcharge retention, invalid requests and explicit hosted-mode refusal. Ruff and file/function limits pass.

## Before a real probe

No current vendor price is verified by this packet. The inherited `WINDOW_POLICY` remains explicitly `UNVERIFIED` against the vendor; it is enforced as the pinned WP-9a UTC policy here. The live activation packet must establish the actual model id/image support contract, verified price source and applicable off-peak policy, and make the transport enforce a conservative input bound including image/hidden overhead plus its output limit and timeout. The fake values and simulated latency cannot supply that evidence.

Opus refusal-path review and owner go remain required before the single hosted probe. After that probe produces real model/token/latency/cost evidence, proceed to WP-3 / WP-4b per r5. Zero hosted calls and USD 0 actual API spend were made here. No independent Opus PASS is claimed. Shared wiki refresh files are absent from this checkout; this handoff is in the stable docs directory.
