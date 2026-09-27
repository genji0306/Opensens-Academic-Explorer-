# Offline packets — E1a review-fix handoff

Opus merged WP-4 follow-ups and WP-6a in github/mve/integration `0550144a895`. The WP-2 branch `codex/mve-wp2-generator` is rebased on that commit and remains unmerged for review. B2/M1/M2 were accepted; this revision applies binding erratum E1a from the review addendum.

The E1a six-point universe has 2,257 candidates: 1,770 EqualAngle pairs and 105 EqualLength pairs. Every angle triple requires three distinct points. Both same-angle and same-segment identities are excluded up to symmetry. EqualAngle's required_nondegeneracy now contains the endpoint pairs, so the merged WP-6a guard refuses emission without them. Exact evaluation and the coordinate kernel use the same registry policy.

The corpus is regenerated from immutable source `0e6abed36b39736043375855fff1fb131734f3eb`, under a network-denying sandbox. Current generated receipts are WP2_CORPUS_RECEIPT_20260927.json and WP2_CORPUS_RENDER_V2_RECEIPT_20260927.json; the E1 receipts are archived as superseded. Local artifacts are under `mve/generated/wp2-corpus-e1a-20260927/`. See WP2_GENERATOR_20260927.md for validation and final computed counts.

The non-blocking WP-6a location-discovery follow-up is pushed as `codex/mve-wp6-portable-discovery` at `360ef0ab4ec`, based on 0550144a895. It passes 357 tests including three real-Lean checks with none skipped, and does not alter E1a's mathematical policy. Preserve both packet entries in DEPS.lock when integrating.

Euclid discovery failed: no local checkout; no network fetch in offline packets. DDAR remains explicitly unsupported; exact-true non-premises remain incidental_unproved. LeanGeo/JSXGraph are unavailable locally; vendoring is deferred to an owner-approved packet. WP-0b must refuse unverified prices before any hosted transport. No hosted calls, downloads, merges or independent Opus PASS are claimed. All work is confined to the designated Developer worktree. Shared wiki refresh files are absent there.

WP-2 validation: 415 full MVE tests pass (88% generator/shared-policy coverage; degeneracy.py 100%). Regenerated E1a receipts validate 2,560 records/scenes/split labels and 10,240 hashes, with zero cross-split image or coordinate collisions and `generated_counts_met`. The fit/sealed sets contain 2,000/500 unique mathematical configurations and PNGs respectively.
