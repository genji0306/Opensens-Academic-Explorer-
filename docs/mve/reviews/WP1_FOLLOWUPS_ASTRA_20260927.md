# WP-1 follow-up implementation — 2026-09-27

Branch: `codex/mve-wp1-review-followups`, from `github/mve/integration`
`ab3b8dd3e84d338a70df471273dff047284994d4`. For Opus review; not merged.

Addresses the WP-1 items in `WP1_WP9a_WP11a_REVIEW_OPUS_20260927.md`:

1. `validation.proposition()` now calls `canonical_exact` for each non-null
   `value_exact`, rejects invalid syntax/domain with `RecordError`, and requires the
   stored string to equal the canonical result. This runs before the predicate scalar
   policy, so it is enforced already. Record-level tests reject `2/4`, `sqrt(8)`,
   `1+0`, `pi`, decimal syntax, imaginary roots and division by zero for the intended
   exact-expression reason. A canonical `1/2` still fails the scalar predicate policy:
   no scalar predicates or new mathematical semantics were activated.
2. A record transition test swaps binder-to-entity mappings on a fixture carrying
   formal artifacts. It checks touched roots, every downstream invalidated node,
   revision/stage reset, cleared formal status, retained content identity, unchanged
   independent source and the immutable original record. The edited roots retain their
   current meaning; their dependent geometries, observation, assumption, propositions,
   typecheck and proof are invalidated. No production invalidation change was needed.
3. A valid control record with a measurement and an explicit-premise derivation is
   accepted first. Replacing the derivation's support with `mea_1`, or adding `mea_1`
   alongside `prm_1`, rejects it with `measurement is not a premise`.
4. The scalar-policy diagnostic now says `active predicates` instead of `P1 predicates`.

Validation: 11 new regression cases passed; full branch suite **238 passed, 95% statement
coverage**, no warnings with `COVERAGE_CORE=pytrace python3 -m pytest tests/mve -q --cov=mve
--cov-report=term-missing`. Changed code/tests pass Ruff and 800/50-line limits. New
source hashes are appended as `WP-1-review-followups` in the aggregate dependency lock,
leaving the merged packet receipts intact. Plan, v5 schema and predicate registry unchanged.

WP-0a's separate rebased review fix is pushed at `113be79b44b` on
`codex/mve-wp0-preflight`: 18 preflight tests, 160/171 statements covered (93.6%) including
the subprocess guard; its combined suite passed 245 tests. This branch does not contain
that unreviewed packet.

All execution was offline. No WP-0b transport was added or invoked. The owner's requirement
is a hard prerequisite for that future packet: **WP-0b must refuse unverified prices before
any hosted dispatch**. The existing offline ledger's provenance flag is not authorization.
WP-9a/11a follow-ups 6–8 remain in the Opus review for their respective packets. WP-2 has
not started in this change. No integration merge or reviewer message was sent.
