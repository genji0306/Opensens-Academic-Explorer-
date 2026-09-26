# README for Codex Astra — Math Vision Engine (MVE) plan, r5 packet

Packet date: 2026-09-27 (r5). Flat folder, six files, every SHA-256 below. Earlier rounds
(r1–r3 plans and verdicts) are under `archive/` and are **not** part of this packet; never
cite a file that is not listed here.

| File | SHA-256 | What |
|---|---|---|
| MVE_PLAN.md | e74be9398e57bd5646b501093b4aa0f6711c5a3091af2357fb1cd68e39dfaa6d | **r5**: applies your r4 verdict (exact grammar over real algebraic numbers only, round-tripping canonical form; `valid` on geometries; exact-only truth with proof refinement as frozen run evidence; mathematical identity vs truth evidence; stale field names fixed) |
| ASTRA_VERDICT_MVE_PLAN_r4_20260927.md | d4c65359f20533ac7161ed07d2226f0c6b8917c4dca027538fc8492bda818ed2 | Your r4 verdict, verbatim |
| MVE_PLAN_r4_20260927.md | 91d1cb6a445faece421ff19289e7cd25d107a33b3b05b350ba99f52c856efd82 | The r4 plan you reviewed, for diffing |
| MVE_REVIEW_OF_SOURCES.md | c7d41a5b020a2e57ce2ce6700ffd404fee2a8bb97d263adff38ee57cb2f166db | Per-source review (unchanged; secondary assertions only) |
| mve_observation_record.json | 13ebcbe03ab718dd39844a65db7519cec370acdc7924555dece6d970414e46fc | JSON Schema **v5** `oae-mve-observation-v5` (derived copy of the authoritative `schemas/mve_observation_record.json`) |
| README_FOR_ASTRA.md | (this file) | Manifest and task |

## Your task (r5 review)

Read MVE_PLAN.md (r5) and the v5 schema against your r4 verdict. Return one markdown file:

1. For blockers 1–4 of your r4 verdict: **cleared / partly / not cleared**, citing the r5 section or schema field.
2. For each new defect you listed under r4: fixed / not fixed.
3. Anything that still blocks WP-0a, WP-1 or WP-2.
4. Any new defect r5 introduced.
5. Last line exactly: `VERDICT: PASS (ready for WP-0a)` or `VERDICT: REVISE` with blocking
   items numbered.

Scope rule for this round: a blocker is cleared when the packet states a decidable contract
that WP-1's tests can enforce; open implementation obligations that the plan names as WP
test obligations are not blockers. Do not write code. D1–D6 are constraints. Mark anything
not verifiable from the packet as UNVERIFIED.
