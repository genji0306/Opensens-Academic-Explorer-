# Opus review — WP-1, WP-9a, WP-11a (2026-09-27)

All three: **PASS, merged into `mve/integration`**. Each branch was reviewed from a clean
`git archive`; tests and coverage re-run by the reviewer; code reviewed against MVE_PLAN r5.
Combined suite after merge: **227 passed, 94% coverage**.

| Packet | Commit | Tests / coverage | Verdict |
|---|---|---|---|
| WP-1 semantics | ca516ff7970 | 180 / 94% | PASS |
| WP-9a budget | 3fbff7fa8a3 | 27 / 98% | PASS |
| WP-11a evaluation | 4c921b0649b | 20 / 91% | PASS |

Merge notes: `tests/mve/conftest.py` conflicted only on formatting (WP-9a version taken);
`mve/DEPS.lock` now keeps each packet's lock verbatim under `packets`.

## Follow-ups (non-blocking; assign to the next packets)

WP-1
1. MEDIUM — `mve/exact.py canonical_exact` is not called from `validation.proposition()`;
   unreachable today because every predicate rejects `value_exact`. Wire it in and add a
   record-level negative test **before WP-2 activates scalar predicates**.
2. MEDIUM — `mve/operations.py:121-124` (binder re-mapping invalidation) has no test.
3. MEDIUM — no negative test that a derivation citing a `mea_*` id is rejected
   (`mve/validation.py:314`), a named r1 defect.
4. LOW — `predicates.py:35` message says "P1" but applies to all registered predicates.

WP-9a
5. MEDIUM — price `verified` flag is provenance only; dispatch does not require it
   (documented as WP-0b scope). WP-0b must gate hosted calls on verified prices.
6. LOW — add boundary tests at 01:00, 06:00 and 10:00 UTC weekday instants.
7. LOW — zero-token reservations are refused; document or special-case.

WP-11a
8. MEDIUM — add a test where the sandboxed worker itself creates a symlink to a private
   root at runtime and reading through it is denied.

WP-0a remains CHANGES REQUESTED (coverage 65%), see WP0a_REVIEW_OPUS_20260927.md.

## Addendum, 2026-09-27 — fixes merged

- **WP-0a** `113be79b44b`: coverage fixed (preflight modules 95–98%; guard module exercised in a child
  process); runner and openJev checks now testable with injected fakes. **PASS, merged.**
- **WP-1 follow-ups** `6b35653e652`: `canonical_exact` wired into `validation.proposition()` with
  record-level negative tests; binder re-mapping invalidation and derivation-cites-measurement
  tests added; message wording fixed. Items 1–4 closed. **PASS, merged.**
- Combined suite after both merges is recorded in the merge commit message below.
- Still open: items 5–8 (WP-9a verified-price gate belongs in WP-0b; boundary and zero-token
  tests; WP-11a runtime-symlink test).
