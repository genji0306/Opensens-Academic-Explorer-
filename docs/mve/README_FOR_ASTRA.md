# README for Codex Astra — Math Vision Engine (MVE) plan, r4 packet

Packet date: 2026-09-27 (r4). Flat folder, six files, every SHA-256 below. Earlier rounds
(r1, r2 plans and verdicts) are under `archive/` and are **not** part of this packet; never
cite a file that is not listed here.

| File | SHA-256 | What |
|---|---|---|
| MVE_PLAN.md | 91d1cb6a445faece421ff19289e7cd25d107a33b3b05b350ba99f52c856efd82 | **r4**: applies your r3 verdict (§4a: equality-based authorisation, adoption-only human route, `sources` nodes, argument-role registry table, incidence mapping, dependency-graph edges, conflict rule, review/ingest transitions, identity projection; §7 offline exemption; §11 truth-artifact contract; §13 log) |
| ASTRA_VERDICT_MVE_PLAN_r3_20260927.md | 6c5aaa8149fa7e972937ea95bc58eadc76c7d80829c600e189d1000e74d99cec | Your r3 verdict, verbatim |
| MVE_PLAN_r3_20260927.md | 24fb78a24dad2f68a58b93d1d722046db69216883875546a13ea70a1db432d9c | The r3 plan you reviewed, for diffing |
| MVE_REVIEW_OF_SOURCES.md | c7d41a5b020a2e57ce2ce6700ffd404fee2a8bb97d263adff38ee57cb2f166db | Per-source review (unchanged; secondary assertions only) |
| mve_observation_record.json | b9ba313819ffcbb5f8db4372ab522d3173334048e54841c6b64929b5b333f142 | JSON Schema **v4** `oae-mve-observation-v4` (derived copy of the authoritative `schemas/mve_observation_record.json`) |
| README_FOR_ASTRA.md | (this file) | Manifest and task |

## Your task (r4 review)

Read MVE_PLAN.md (r4) and the v4 schema against your r3 verdict. Return one markdown file:

1. For blockers 1–7: **cleared / partly / not cleared**, citing the r4 section or schema field.
2. For each new defect you listed under r3: fixed / not fixed.
3. Anything that still blocks WP-0a, WP-1 or WP-2.
4. Any new defect r4 introduced.
5. Last line exactly: `VERDICT: PASS (ready for WP-0a)` or `VERDICT: REVISE` with blocking
   items numbered.

Scope rule for this round: a blocker is cleared when the packet states a decidable contract
that WP-1's tests can enforce; open implementation obligations that the plan names as WP
test obligations are not blockers. Do not write code. D1–D6 are constraints. Mark anything
not verifiable from the packet as UNVERIFIED.
