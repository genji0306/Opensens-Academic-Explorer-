# README for Codex Astra — Math Vision Engine (MVE) plan, r2 packet

Packet date: 2026-09-27 (r2). Flat folder, six files, every SHA-256 below. Never cite a
file that is not listed here.

| File | SHA-256 | What |
|---|---|---|
| MVE_PLAN.md | e74aa0732a45657c90d956372568f1363d45dc947dad9da440ed9d6016b3fce8 | **r2**: the plan after your verdict was applied (evidence classes, registry, routing table, build order, gates with nulls, open questions answered) |
| ASTRA_VERDICT_MVE_PLAN_20260927.md | 844f67c33807b89afbdf501a1f408f5def86aa3dcc0ac044735cd6db9272b238 | Your r1 verdict, verbatim |
| MVE_PLAN_r1_20260927.md | 2afdf15e56cf563a692f41bf4fdd823cb80b6ad79cab87d8cdd7b598983900aa | The r1 plan you reviewed, for diffing |
| MVE_REVIEW_OF_SOURCES.md | c7d41a5b020a2e57ce2ce6700ffd404fee2a8bb97d263adff38ee57cb2f166db | Per-source review (unchanged since r1; every external number is a secondary assertion) |
| mve_observation_record.json | 56f279ac8507d3404ce084e01e910bb9282e79d4943971cfcbc7944ad0e2dce9 | JSON Schema **v2** `oae-mve-observation-v2` (copy of `schemas/mve_observation_record.json`) |
| README_FOR_ASTRA.md | (this file) | Manifest and task |

## Your task (r2 review)

Read MVE_PLAN.md (r2) against your own r1 verdict. Return one markdown file with:

1. For each item in your r1 sections 1 and 2: **applied / partly / not applied**, one line
   each, citing the r2 section or schema field.
2. Anything in r2 that would still block WP-0, WP-1 or WP-2 (the first three packets).
3. Any new defect r2 introduced.

Do not write code. Owner decisions D1–D6 in r2 §0 are constraints. Mark anything you cannot
verify from the packet as UNVERIFIED.

## Context you may assume

- Repo worktree branch `claude/math-vision-engine-078a13`; RH tools reached by path; a
  `DEPS.lock` will pin them (r2 §3).
- Roles: Astra builds; Claude Opus reviews and operates the fleet; DeepSeek V4.1 Flash is the
  vision worker; Sol structured reviews; Astra + Fable strategy cross-review.
- The local openJev is an inference artifact only; its training pipeline is a WP-5 spike.
