# README for Codex Astra — Math Vision Engine (MVE) plan review

Packet date: 2026-09-27. Flat folder, four files, every SHA-256 below. Never cite a file
that is not listed here.

| File | SHA-256 | What |
|---|---|---|
| MVE_PLAN.md | 2afdf15e56cf563a692f41bf4fdd823cb80b6ad79cab87d8cdd7b598983900aa | The review-and-plan document: vision, findings, architecture A0–A7, Jev decision layer, roles, phases P0–P6 with gates, work packets WP-1..WP-12, risks |
| MVE_REVIEW_OF_SOURCES.md | c7d41a5b020a2e57ce2ce6700ffd404fee2a8bb97d263adff38ee57cb2f166db | Per-source review of the six requested papers/repos plus Jev and the wider landscape, with verified/unverified marks |
| mve_observation_record.json | 47a45b9378cfd9c87fde5b36cdd03fdb3e268e71b16a217a7e2df98c998e8112 | JSON Schema `oae-mve-observation-v1` (copy of `schemas/mve_observation_record.json` in the repo) |
| README_FOR_ASTRA.md | (this file) | Manifest and task |

## Your task

You are the builder who will implement WP-1..WP-11 in `MVE_PLAN.md` §10. Read the plan
and the review, then return one markdown file with:

1. Every ambiguity that would block a work packet (name the WP and the sentence).
2. Every claim you believe is wrong or unverified in a way that matters (cite section).
3. The build order you would actually use, with the reason for any change from §7.
4. A revised gate table if any gate in §7 is untestable as written, with the test you would
   run instead and its chance rate.
5. Your answer to the open questions in §11 (GeoIR vs Lean-typed record; LeanGeo vs native
   Mathlib target; honest equivalence scoring; the first topology statement).

Do not write code. Do not propose spending beyond the owner's caps in §0 D4. Mark every
statement you cannot verify from the packet as UNVERIFIED.

## Context you may assume

- Repo worktree branch `claude/math-vision-engine-078a13`, crystal-platform history only;
  RH tools are reached by path (plan §3).
- Roles: Astra builds; Claude Opus reviews and operates the fleet; DeepSeek V4.1 Flash is the
  vision worker; Sol does structured reviews; Astra + Fable cross-review strategy.
- Lean 4.34.1 and a Mathlib v4.29.0 project exist locally; the AXLE MCP is down.
- Jev is text-only; the decision layer is the local openJev 151M (512-token cap) with the
  recursive self-learning loop in plan §5a (human verdicts override manager labels).
- Owner decisions D1–D6 are recorded in plan §0: openJev local; JSXGraph UI + GeoGebra in
  Newclid only; DeepSeek-Prover-V2-7B first with Goedel-Prover-V2-8B compared on the same
  50 statements; USD 20 cap for P0–P2; package `mve/` in this repo; GeoX/MultiMath data excluded.
