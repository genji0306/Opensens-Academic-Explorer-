# Opus review: offline packets (WP-2, WP-4a, WP-6a, follow-ups), 2026-09-27

Method: each branch rebuilt from `git archive` of its head; full `tests/mve` suite with coverage
re-run per branch; one independent python reviewer per substantive packet against plan r5.
Every finding cited below was reproduced by executing the shipped code.

| Branch | Head | Re-run | Verdict |
|---|---|---|---|
| codex/mve-review-boundary-tests | 58c4bef8496 | 266 passed, budget 100% | **PASS, merged** |
| codex/mve-wp4a-fixtures | efa459a3847 | 299 passed, measurement 95% | **PASS with follow-ups, merged** |
| codex/mve-wp2-generator | c7661da4c11 | 303 passed, generator 89–100% | **CHANGES REQUESTED** |
| codex/mve-wp6a-lean-spike | 6fed848186e | 266 passed, formalizer 76–100% | **CHANGES REQUESTED** |

Combined mve/integration after the two merges: 309 passed, 95% coverage.

## Follow-ups branch: PASS
Weekday boundaries at 00:59:59.999999 / 01:00 / 03:59:59.999999 / 04:00 / 05:59:59.999999 /
06:00 / 09:59:59.999999 / 10:00 UTC on Monday 2026-09-28, UTC and +07:00, for reserve and
dispatch; zero-token reservation refused with no attempt row; a symlink created by the sandboxed
worker at runtime gets EPERM on the private root. Closes open follow-ups 6–8.

## WP-4a: PASS with follow-ups
Verified: measurements never authorise (no support path; derivations cannot cite `mea_`);
tolerances explicit, zero forced for Distinct/NotCollinear; `consistent == residual <= tolerance`
re-derived in semantics; an edit of a cited geometry transitively invalidates the measurement and
its observation; `content_hash` and `record_id` are unchanged by `measure_record` (measurement
floats never enter identity); `atan2` angles; non-finite input refused.
Follow-ups (next WP-4 branch):
1. Tests for the three `records.py` geometry-selection guards (duplicate ids, unknown id, one
   current point geometry per argument: wrong kind / invalid / wrong frame / two ids for one entity).
2. Assert `content_hash` and `record_id` unchanged after `measure_record`.

## WP-2: CHANGES REQUESTED
**B1 (blocking): repeated-point policy over-applied; the candidate universe is incomplete.**
Plan r5 §4a: "any repeated point makes the candidate degenerate … *unless stated*", and the
Degeneracy column states narrower rules. The code applies full-tuple distinctness to every row
with a degeneracy string (`universe.py:22-27`, `exact.py:137-142`, and the registry strings), so
on A=(0,0), B=(1,0), C=(0,1): `EqualLength(A,B,A,C)` → `degenerate` (true isosceles fact) and it is
absent from the universe; likewise every EqualAngle sharing a point across triples (angle
bisector, inscribed angle). The test at `test_generator_exact.py:89-93` pins the defect.

**Reviewer ruling (plan r5 erratum E1; the plan's wording was ambiguous, this is the binding
reading):** the Degeneracy column overrides the default where it states a rule.
- EqualLength: degenerate iff A=B or C=D; cross-pair sharing allowed (isosceles, circumcentre).
- EqualAngle: degenerate iff A=B, B=C, D=E or E=F; cross-triple sharing allowed, except the two
  triples being the same angle up to symmetry (trivial identity; exclude from the universe).
- Parallel / Perpendicular: keep full distinctness. A shared point makes them the same fact as
  Collinear / RightAngle, which are already in the universe; excluding them avoids duplicate facts.
- Collinear, Concyclic, Midpoint, SBetween, RightAngle: unchanged.
Registry v1 degeneracy strings updated to match; universe count, `candidate_universe_sha256`,
truth and the corpus regenerated (no downstream consumer exists yet, so no versioned migration).
Replace the pinning test with tests for the cases above (a true isosceles EqualLength, a true
bisector EqualAngle, a trivial self-EqualAngle excluded, Perpendicular(A,B,A,C) excluded).

**B2 (blocking): receipt claims a check the code does not run.** Both receipts report
`cross_split_coordinate_collisions: 0`; `corpus_report` computes only image collisions and no
code emits that field. Compute it from `math_coordinates_sha256`, fold it into `accepted`, and
regenerate the receipts from the merged code.

**M1:** `corpus.py:97-104` writes `split: "sealed"` into `record.json` for development / retrieval
items while the manifest says `development` / `retrieval`. Use one label in both, and never
"sealed" for anything but the 500-item evaluation set.
**M2:** `scene.py:17-21` rejects only x > width or y > height; also reject negatives.

## WP-6a: CHANGES REQUESTED
Verified: no `sorry`, `axiom` or `theorem` anywhere; LeanGeo interface reports unsupported,
never success; binder names restricted to `p[0-9]+`; all 11 targets independently re-typechecked
against the pinned Lean 4.29.0 + Mathlib; statement hash frozen from emitted to typechecked.

**B1 (blocking): nondegeneracy not enforced.** `ir.py` copies whatever `problem.nondegeneracy`
holds; nothing requires the registry's nondegeneracy for Parallel, Perpendicular, Concyclic,
EqualAngle, RightAngle, SBetween. `Parallel` over two single-point spans is vacuously true in
Mathlib, so a record without `Distinct` premises typechecks as a vacuous statement. Add a guard
before `emit` (refuse, naming the missing `Distinct`/`NotCollinear`) with tests.
**B2 (blocking): the only real-Lean tests skip off one machine.** `test_formalizer_runtime.py:14-17`
hard-codes `/Users/applefamily/.elan/...`. Gate on `lock.json`'s `lean_binary` (or an env var).
**M1:** committed receipts and `lock.json` carry absolute `/Users/...` paths; store paths relative
to the project / output root (hashes carry the integrity).
**M2:** `compile_source` copies the whole host environment; pass an explicit minimal env
(PATH, HOME, LEAN_PATH).
**M3:** the sandbox profile denies network only; say so in the WP-6a doc (not filesystem-contained).
**L1:** `Spike.lean` opens `RealInnerProductSpace` unnecessarily; align with `HEADER`.

## Standing
WP-0b must refuse unverified prices before any hosted transport. Euclid, LeanGeo and JSXGraph
remain "failed: not present locally"; vendoring needs an owner-approved packet.

## Addendum: re-review after fixes (base 8da83b3c2a2)

| Branch | Head | Re-run | Verdict |
|---|---|---|---|
| codex/mve-wp4-geometry-guards | a9ac0502255 | 317 passed, measurement/records.py 100% | **PASS, merged** |
| codex/mve-wp6a-lean-spike | 0c94e493fe5 | 338 passed + 2 skipped in scratch; the 29 formalizer tests incl. both real-Lean checks pass from a Developer worktree at the lock's depth | **PASS, merged** |
| codex/mve-wp2-generator | cfd40f80bb2 | 364 passed | **CHANGES REQUESTED (E1a, from my own incomplete ruling)** |

Combined mve/integration: 346 passed, 2 skipped (real-Lean, path-dependent), 93% coverage.

WP-6a: `guards.require_nondegeneracy` refuses emission naming each missing Distinct/NotCollinear;
env is built explicitly; no `/Users/` in committed artifacts. Follow-up (non-blocking): `lock.json`
paths are relative to the worktree location, so the real-Lean tests still skip unless the checkout
sits at `~/Developer/Opensens/worktrees/<name>`. Resolve the toolchain from `ELAN_HOME` (default
`~/.elan`) plus the toolchain name, and the packages from an `MVE_LEAN_PACKAGES` root, verified
by the existing hashes; print one line when they are skipped.

WP-2 fixed B2 (coordinate collisions computed and in `accepted`; receipts regenerated), M1 (one
label; "sealed" is the 500-item set; record matches manifest, tested), M2. B1 follows E1 exactly,
but E1 was incomplete and now admits trivially true candidates (probe, four points A–D):
- 6 self-EqualLength candidates such as `EqualLength(A,B,A,B)`.
- 210 of 276 EqualAngle candidates contain a zero angle such as `∠ABA`; `EqualAngle(A,B,A,C,D,C)`
  is `true` for any configuration.

**Erratum E1a (binding):** EqualAngle is also degenerate iff A=C or D=F (a zero "angle" is not an
angle). EqualLength is excluded when both sides are the same segment up to symmetry (as for the
self-EqualAngle). Update `mve/degeneracy.py`, the registry strings, `required_nondegeneracy`
(EqualAngle now requires `Distinct(A,C)` and `Distinct(D,F)`), and the universe, truth and corpus;
add tests for both exclusions. WP-6a's guard picks up the change through `mve/degeneracy.py`.

## Addendum 2: WP-2 E1a and portable Lean (base 0550144a895)

| Branch | Head | Re-run | Verdict |
|---|---|---|---|
| codex/mve-wp2-generator | 998ffdcb2f0 | 413 passed, 2 skipped (real-Lean, pre-portable) | **PASS, merged** |
| codex/mve-wp6-portable-discovery | 360ef0ab4ec | 354 passed, 3 skipped without `MVE_LEAN_PACKAGES`; 22/22 runtime+discovery with it, from a scratch path | **PASS, merged** |

Combined mve/integration, with `MVE_LEAN_PACKAGES` set: 424 passed, 0 skipped, 92% coverage.

E1a probe on four points A–D: 158 candidates; EqualAngle 66 = C(12,2) (12 proper angles, distinct
unordered pairs), EqualLength 15 = C(6,2); zero self-EqualLength, zero zero-angle candidates;
`EqualAngle(A,B,A,C,D,C)` → degenerate; bisector `EqualAngle(B,A,D,D,A,C)` and isosceles
`EqualLength(A,B,A,C)` → true. Schema v5 gains `development` / `retrieval` in the truth split enum
(additive; docs copy byte-equal). Lean discovery: toolchain from `ELAN_HOME`, packages from
`MVE_LEAN_PACKAGES`, pins verified, explicit missing roots never replaced, skips print a reason,
compiler env is PATH/HOME/LEAN_PATH only, no `/Users/` in the lock.

Build order next (r5 §7): WP-0b probe (verified-price refusal before any hosted transport), then
WP-3 / WP-4b, WP-8a / WP-5.

## Addendum 3: WP-0b offline refusal path (ee727aa1f39): PASS, merged

Re-run from archive: 463 passed, 0 skipped, 93%; probe modules 96–100%. No network, SDK or key
reader. Hosted mode refused unless the mode is literally `offline_fixture` with an exact
`FakeTransport` (not isinstance). Verified price is read from the ledger's pinned configuration,
with a strict bool; checked before reservation. Order: validate → verified ceiling (0 < c ≤ USD 0.05)
→ atomic P0 reserve → persist → `mark_dispatched` (off-peak rechecked) → send. After dispatch,
cancellation is structurally impossible. One-shot id enforced by primary key + `BEGIN IMMEDIATE`
under real threads. Missing billing is never zero; overcharge unclamped and freezes; Decimal money.
Receipt hashes computed by code; nothing claims vendor verification.
Follow-ups for the live-activation packet: (1) `resume(actor)` is a role string, never an auth
path; (2) the window policy is `UNVERIFIED` and a new ledger could pin another string, so the
live packet must verify the vendor window and price source. **The single hosted probe still needs
the owner's go.**

## Addendum 4: WP-3 offline perceiver (5fa1724555d): PASS with follow-ups, merged

Built by a headless Astra session launched by Opus (network-off Codex sandbox). The 6 failures
it reported were nested `sandbox-exec` inside that sandbox. From a clean archive outside it:
559 passed, 0 skipped, 94%; `mve/perceiver/*` 100%. The WP-0b refactor (parametrised attempt /
phase / wave, `dispatch_fixture`, `settle`) keeps every refusal-path guarantee. Phases limited to
P0/P1 with caps enforced by the ledger. Retries 0..2, each a distinct reserved attempt (≤ 6 per
image). Nonce reuse refused by the ledger. The two calls get identical requests. Raw bytes are
saved before parsing. Output goes only to observations.
Follow-ups (next perceiver branch): (a) WP-3 dispatch fixed to P1, since P0 is the WP-0b
probe's pool; (b) remove the dead `model=` kwarg on `perceive()`, or assert it equals
`deepseek-flash`.

## Addendum 5: WP-8a verdict capture (e0f679d23cc): PASS with follow-ups, merged

Headless Astra build; from a clean archive outside the Codex sandbox: 612 passed, 0 skipped,
94%; `mve/verdicts/*` 100%. `adopt` remains human/policy only; a model judgment that says adopt
fails at the transition before any assumption is written; model judgments keep weight 0.5 under
full revalidation. Stale revisions rejected; edits invalidate dependent judgments transitively.
Training export draws from `fit` only; human 1.0 beats model 0.5 deterministically; model labels
exported as `actor_kind: model`. WP-3 follow-ups closed (P1 only; `model` asserted).
Follow-ups: (1) the schema gained `can_N` nodes, a `proposed` event and a wider `human:` id pattern
under the unchanged `oae-mve-observation-v5` id. They are additive and old records validate, but add a
dated changelog block to the schema description and to MVE_PLAN §13 naming each extension; any
future non-additive change bumps to v6. (2) VERDICTS.md says a model may not decline, but only
adopt is blocked. Fix the doc, or refuse model `decline` as well. (3) "human:" is a local
operator assertion, not authentication; keep that stated wherever labels are exported.

## Addendum 6: WP-6b formalizer (7b9c53e3021): PASS with follow-ups, merged; G3 NOT established

From a clean archive outside the Codex sandbox: 640 passed, 0 skipped, 95%; new formalizer
modules 98–100%; schema copies byte-equal; WP-8a follow-ups closed (dated v5 changelog; model
decline refused and pinned). The committed `mve/lean/artifacts/wp6b-g3/` receipts were produced
inside the Codex sandbox and record `sandbox_apply: Operation not permitted` for every compile.
Opus re-ran `python3 -m mve.formalizer.g3` outside it (real pinned Lean):
`WP6B_G3_OUTSIDE_SANDBOX_RUN_OPUS_20260927.json`: first-pass 80/100 (exactly the 20 injected
syntax faults), post-repair 100/100, all 7 control kinds 100/100 detected, `g3_pass: false`,
semantic rubric 0. Only 3 unique canonical statements across 100 tasks, so these rates measure
the repair rules, not formalization. **G3 is not established**, and the harness says so.
Follow-ups (next formalizer branch): (1) a G3 task corpus of ≥ 100 distinct statements from WP-2
exact-true candidates across all P1 predicates, with explicit premises and goals, family-split,
and a 50-task retrieval-disjoint blinded reference set; (2) regenerate the committed G3 receipts
outside the Codex sandbox (Opus can run it) or drop them; (3) localise the pre-existing absolute
`/Users/` paths in `mve/DEPS.lock` (184) and `mve/preflight/results/report.json` (19), which come
from WP-0a.

## Addendum 7: WP-5 classifier (9ef15969f01): PASS with follow-ups, merged; G2 NOT established

Outside the Codex sandbox: 654 passed plus `test_paths_hashes_and_committed_artifacts`, which needs
a git checkout (it passes in one; it fails in a `git archive` copy only). Classifier modules 95–100%.
The 512-token cap uses the real openJev tokenizer with no truncation; over-cap abstains to a human.
The LLM tier refuses offline and falls back to a human. Training reads only `fit`; human beats
manager; the actor kind is checked. The spike is capped (≤ 3 epochs, 20 steps, 180 s, 64 rows) and
trains only a separate 20-parameter head; base openJev is untouched. ONNX parity is computed (3/3,
max diff 0.0). Weights are ignored and only hashes committed. All 487 prior DEPS.lock hashes are
preserved; no `/Users/` remains in tracked `mve/` files.
Follow-ups: (1) the parity and fit set (3 states, 4 rows, 1 family) is plumbing only, so G2 needs
real WP-8a human labels; (2) rename or comment `epochs` vs `min(epochs, max_steps)` in spike.py;
(3) make the no-`/Users/` test skip with a reason outside a git checkout.

## Addendum 8: WP-0b live probe: EXECUTED ONCE (owner-run), merged

Code `16cf4788cce` reviewed by Opus (stdlib urllib; fixed host; no proxy, redirect or retry;
1 MiB reply cap; Keychain key read at call time only and scrubbed from raw bytes; CLI gated on
owner date + Opus-reviewed HEAD + clean tree). 695 passed outside the sandbox before the call;
710 passed on integration after merge. Opus's own invocation was blocked by the Claude Code
permission classifier; **the owner ran the single call** at 2026-09-27T12:28:42Z (Sunday, off-peak).

Result (receipt, request, raw response and ledger rows in `docs/mve/reviews/wp0b-live/`):
HTTP 200, returned model `deepseek-flash`, image accepted with the OpenAI-compatible `image_url`
data URL, `thinking: disabled` accepted, JSON reply. Usage 236 prompt tokens (all cache miss; image
included), 164 completion tokens, latency 1.45 s. Cost derived from usage at peak prices:
**USD 0.000268** (reserved 0.039936), settled in the one-shot ledger with no freeze. The key was
not found in any artifact (checked byte-for-byte against the Keychain value). Campaign P0 spend
is now USD 0.000268 of 2.00.
Measured cost model for WP-3 planning: ≈ 236 input tokens for a 288×288 PNG plus a short prompt.
At P1 peak prices one two-call perception costs ≈ USD 0.0005, so USD 8 covers ~15,000 images
before retries. The reply named 6 points, collinearities and segments; accuracy is not scored
here (one image, no truth in the prompt).
Next: WP-3 live transport reuses this adapter behind the P1 ledger; the first scored run on the
fit split still needs an owner go.

## Addendum 9: G3 task set (83ceda94dda + Opus receipts 623026be358): PASS, merged; G3 pending human rubric

725 passed in a git worktree outside the builder sandbox. Opus ran
`python3 -m mve.formalizer.g3 --output mve/lean/artifacts/g3-taskset` with real pinned Lean:
100 tasks with **100 unique canonical statements**, 170 unique compiler inputs; first-pass 80/100
(exactly the 20 injected syntax faults), post-repair 100/100; all 7 control kinds 100/100;
`g3_pass: false`, because the 50-task blinded rubric has 0 human reviews (needs ≥ 20 passes).
Per predicate: Parallel 18, EqualLength 17, EqualAngle 17, RightAngle 17, Perpendicular 14,
Collinear 5, SBetween 5, Concyclic 4, Midpoint 3. The shortfalls are disclosed: the frozen sealed
families at seeds 0–9 hold only that many distinct statements, and the unfilled quota is spread round-robin.
Caveat: first-pass/post-repair measure the deterministic emitter and syntax repair, not model
formalization; G3's model-facing meaning needs the formalizer to be driven by perceived records.
**Owner action to finish G3:** a human fills
`mve/lean/artifacts/g3-taskset/rubric-template.csv` (50 rows, blinded), then Opus runs the
`--reviews` command in docs/mve/reviews/G3_TASKSET_ASTRA_20260927.md.
Follow-up: widen Collinear/Concyclic/Midpoint/SBetween coverage by adding sealed-family seeds or
constructions (a WP-2 generator extension), without touching the frozen split.

## Addendum 10: WP-9b/WP-11b reports (47e7e8d01d7): PASS, merged

784 passed in a git worktree outside the builder sandbox. Regenerating the report changes only
the recorded evidence-commit line, so it is deterministic given HEAD. Ledger: the live WP-0b charge
is counted once (P0 settled USD 0.000268; aggregate 0.000268 of 20.00). The campaign-snapshot
absence is stated, not zero-filled. Gates G0–G6 are all "not established", each with its null
and the specific missing evidence. G3 is 4/4/5 criteria, pending the 0/50 human rubric. This
matches the individual reviews.
Opus spot-check follow-up: G0 reports 1/1/4 because the validation-negatives evidence is not
wired into the report, although WP-1 tests cover it. Wire the WP-1 negative-fixture receipts as
G0 evidence in a later reporting pass.

## Addendum 11: WP-10 topology (f518aba116e): PASS, merged; G5 not established

855 passed in a git worktree outside the builder sandbox; 71 topology tests. All 30 fixture PD
codes are valid (each arc label exactly twice). The trefoil has writhe −3 and its mirror +3; the
figure-eight has writhe 0. Geometry decoding reproduces the symbolic truth for all 30. Linking
numbers are invariant across R1/R2/near-miss variants and flip only under mirror. R1/R2 are
literal Markov stabilisation and σσ⁻¹ insertion. Canonicalisation does not equate a knot with
its mirror or its R-variants. Non-transverse and triple crossings are rejected. G5 is forced
"not established" while any criterion is unevidenced.
Follow-ups: (1) `mve-oriented-pd-v1` breaks arcs at every crossing visit, unlike classical PD;
any SnapPy/KnotTheory adapter must convert, never pass it straight to `snappy.Link()`;
(2) document or align the `arc_labels` anchor (the first visit vs the underpass tie-break).

## Addendum 12: WO-2 hypothesis cards + WO-3 spacing checks (cbe161e4248): PASS, merged

909 passed plus 2 opt-in skips in a git worktree outside the sandbox. With `MVE_RUN_SLOW=1` the
full v2 regression reproduces card #1's receipts (2 passed, 152 s). Hypotheses never authorise:
`graph.reject_hypothesis_support` walks the `depends_on` closure and is called at every
formalisation entry (formal, validation, IR, guards, emitter, runtime), with direct and transitive
tests. Card hash covers `check_spec`, `prediction` and `primary_statistic`; revisions invalidate
downstream; `preliminary` is in the lifecycle; human and model origin are structurally distinct;
GO1 denominators count requested slots. Gaudin law via the Bornemann Fredholm quadrature;
N_eff includes Λ; the Planck normaliser is analytic; a single frozen kill rule. Everything
defaults to `nominal` / `inferential: false`. Odlyzko tables are sha256-verified from the cache
and never copied.
Note: `check_candidates` has no hypothesis guard because candidates are non-authorising; re-check
if candidates ever gain a consumer.
Next (need owner answers, plan r6 §9): WO-1 snapshot adapter (first modules), WO-4 observer
runner (second model observer), WO-5 fleet/atlas contracts (ownership, exchange writes, status
mapping), then the WO-6 pilot (owner go; ≈ 102 calls).

## Addendum 13: WO-1 lab snapshot adapter (a8183e43716): PASS, merged

975 passed outside the sandbox. The first attempt archived the whole OAE repo (6.1 GB) and filled
the disk. Opus deleted the generated tar; the relaunch uses pathspec-only archives (atlas 97b1e48cb10:
vendor/zeta-explorer/dist, rh_evidence/labs, lab_snapshots.json; lab c81510cd29b) with a disk cap.
Native capture was run by Opus outside the builder sandbox after four fixes found by running it:
(1) short private HOME/TMPDIR with Chrome writes kept out of ~/Library; (2) PYTHONUSERBASE
preserved, since a private HOME hid the arm64 Pillow; (3) the OS profile allows Unix-socket IPC
and /private/var/folders, and uses Chrome `--no-sandbox` inside the OS sandbox. Opus verified
that profile still refuses inet (curl to example.com fails). (4) A per-pass timeout and a PNG repeat
tolerance: data.json stays byte-exact, while PNGs allow ≤ 0.1% of pixels over 8/255. The measured
drift was one anti-aliased WebGL pixel. Final run: 8 snapshots (05 spectral, field-dyson, Ulam,
space-08 prime sphere, each with its control twin), `capture: captured`, repeat verified,
source repos unchanged, outside-write probe denied, 0 hosted calls, 7.6 MB generated (ignored).
Blinded crops inspected by Opus: plot-only, no titles, captions or axis labels.
The atlas-file drift during the first session was the atlas manager's v280 commit (02:46), not WO-1.

## Addendum 14: WO-4 observer runner + WO-5 outbox contracts (5cd566250b1 + Opus 567bfc0050b): PASS, merged

1014 passed outside the sandbox, after one Opus one-line fix: storage.py's own `/Users/` guard
literal tripped the repo-wide committed-path lint, so the literal was split. Dispatch uses only the
WP-0b FakeTransport in P1 behind the ledger; no live mode exists, and the second observer refuses
('owner Q2 unanswered'). All writes go through `storage.local`: inside `mve/generated` only, no
absolute paths or `..`, symlinks refused, with a 200 MiB cap and a free-disk guard. The outbox holds
handshake submissions and atlas result bundles (validated against a pinned, vendored copy of the
atlas result schema); nothing is written to the review-exchange or the atlas. The status mapping
is a proposal pending the atlas owner (Q5); technical_failure bundles are held back.
**All offline packets of plan r6 are now merged.** Remaining work needs the owner: §9 Q1–Q6,
the second-observer choice, and the go for the WO-6 pilot (hosted calls).
