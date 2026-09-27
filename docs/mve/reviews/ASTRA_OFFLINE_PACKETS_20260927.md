# Offline packet review-fix handoff for Opus

WP-2 and WP-6a are rebased on github/mve/integration 8da83b3c2a2 and remain unmerged. Boundary/symlink follow-ups and WP-4a are already merged by Opus. Work was confined to ~/Developer/Opensens/worktrees/oae-mve-integration. Hosted calls and API cost: zero.

| Branch | Validation | Review fixes |
|---|---|---|
| codex/mve-wp2-generator (`cfd40f80bb2`) | 364 full MVE tests; 88% generator coverage | E1 registry/universe/exact truth, computed coordinate collisions in acceptance, consistent split labels, negative scene-coordinate refusal |
| codex/mve-wp6a-lean-spike (implementation `edaa4a26db4`) | 338 full MVE tests; 84% formalizer/shared-policy coverage, plus two added consistency tests; real Lean checks and Lake build pass | Explicit required nondegeneracy, lock-based compiler gate, relative pins/receipts, minimal environment, accurate network-only sandbox documentation, matching Spike HEADER |

| codex/mve-wp4-geometry-guards (`a9ac0502255`) | 317 full MVE tests; 98% measurement coverage and 100% records.py coverage | All geometry-selection guards and unchanged content_hash/record_id |

Counts are per branch and share baseline tests. Local validation is not an independent Opus PASS.

Both branches contain an identical shared E1 policy change (WP-2 a27e1eb04c7; WP-6a a4ff9b68eb3). Preserve that policy and both aggregate DEPS.lock packet entries when integrating.

The E1 corpus was generated from immutable WP-2 source 110df922429418b34a0812007351ac30f85092ce. Use the regenerated WP2_CORPUS_RECEIPT_20260927.json and WP2_CORPUS_RENDER_V2_RECEIPT_20260927.json on the WP-2 branch. The old pre-E1 receipts are archived there. Local artifacts are under mve/generated/wp2-corpus-e1-20260927/. There are 2,560 diagrams, including 2,000 fit and 500 sealed; all records/scenes validate, all 10,240 hashes match, and computed cross-split image and coordinate collisions are zero. Every record label matches its manifest and frozen split. The six-point universe has 4,507 candidates, including shared-point isosceles/bisector instances. No sealed truth was inspected for tuning.

Euclid discovery failed: no local checkout; no network fetch in offline packets. Newclid still does not import; exact-true non-premise candidates remain incidental_unproved with DDAR unsupported. LeanGeo and JSXGraph are failed: not present locally; vendoring deferred to an owner-approved packet. LeanGeo integration stays open, JSXGraph stays deferred to A6/WP-7. Native Mathlib statement typechecks are not theorem proofs.

WP-4's geometry-selection guard and unchanged-identity tests are pushed on the separate branch above, also based on 8da83b3c2a2 and unmerged. WP-0b's verified-price refusal must precede any hosted transport. No hosted adapter was added. Shared wiki refresh tooling is absent from this checkout; durable handoffs are under docs/mve/.
