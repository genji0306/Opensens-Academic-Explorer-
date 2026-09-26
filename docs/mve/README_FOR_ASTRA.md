# README for Codex Astra — Math Vision Engine (MVE) plan, r3 packet

Packet date: 2026-09-27 (r3). Flat folder, six files, every SHA-256 below. The r1 plan and
your r1 verdict are archived under `archive/` and are **not** part of this packet; never
cite a file that is not listed here.

| File | SHA-256 | What |
|---|---|---|
| MVE_PLAN.md | 24fb78a24dad2f68a58b93d1d722046db69216883875546a13ea70a1db432d9c | **r3**: the plan after your r2 verdict was applied (§4a rewritten: addressable sources, authorisation table, operations/transitions, stage invariants, identity, validation authority, frozen registry; WP-0 split; WP-2 truth contract; §13 honest closure log) |
| ASTRA_VERDICT_MVE_PLAN_r2_20260927.md | a37780b715316c3ef1d4cccd9f83f581a72e2f100430d5c11be52cefae04d791 | Your r2 verdict, verbatim (blockers 1–7) |
| MVE_PLAN_r2_20260927.md | e74aa0732a45657c90d956372568f1363d45dc947dad9da440ed9d6016b3fce8 | The r2 plan you reviewed, for diffing |
| MVE_REVIEW_OF_SOURCES.md | c7d41a5b020a2e57ce2ce6700ffd404fee2a8bb97d263adff38ee57cb2f166db | Per-source review (unchanged; secondary assertions only) |
| mve_observation_record.json | aacf18e4fdac1570ec66e0cec53f0e793dbbfef81a6701f0d43c181e7267f2ea | JSON Schema **v3** `oae-mve-observation-v3` (derived copy of the authoritative `schemas/mve_observation_record.json`; checked equal) |
| README_FOR_ASTRA.md | (this file) | Manifest and task |

## Your task (r3 review)

Read MVE_PLAN.md (r3) and the v3 schema against your r2 verdict. Return one markdown file:

1. For blockers 1–7 of your r2 verdict: **cleared / partly / not cleared**, citing the r3
   section or schema field.
2. For each "new defect introduced by r2": fixed / not fixed.
3. Anything that still blocks WP-0a, WP-1 or WP-2.
4. Any new defect r3 introduced.
5. Last line: `VERDICT: PASS (ready for WP-0a)` or `VERDICT: REVISE` with blocking items numbered.

Do not write code. D1–D6 in §0 are constraints. Mark anything not verifiable from the
packet as UNVERIFIED.
