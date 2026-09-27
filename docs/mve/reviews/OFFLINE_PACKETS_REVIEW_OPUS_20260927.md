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
