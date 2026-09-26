# Kickoff prompt for the Codex Astra builder session (paste into Codex in VS Code)

Work in a fresh worktree of this repository on branch `mve/integration` (do not use the
Claude worktree `.claude/worktrees/math-vision-engine-078a13`; do not touch the Desktop
main checkout, which is iCloud-synced). Suggested:

    git worktree add ~/Developer/Opensens/worktrees/oae-mve-integration mve/integration

You are the builder for the Math Vision Engine. Read, in order:
1. docs/mve/README_FOR_ASTRA.md
2. docs/mve/MVE_PLAN.md (r2) — §0 owner decisions D1–D6 are constraints
3. docs/mve/ASTRA_VERDICT_MVE_PLAN_20260927.md — your own r1 verdict
4. schemas/mve_observation_record.json (v2)

First deliverable, before any code: a short file docs/mve/ASTRA_VERDICT_MVE_PLAN_r2_20260927.md
saying for each item of your r1 verdict applied / partly / not applied, plus anything that
still blocks WP-0..WP-2. Commit it.

Then start WP-0 (preflight) and WP-1 (semantics) per MVE_PLAN.md §11, in that order, each on
its own branch `codex/mve-wp0-preflight`, `codex/mve-wp1-semantics` off `mve/integration`.
Rules: tests first; no network in tests; the only live call permitted in WP-0 is the single
DeepSeek preflight call capped at USD 0.05; `python3`; files ≤ 800 lines; functions ≤ 50
lines; immutable records; conventional commits; never `git commit -a`; write `mve/DEPS.lock`.
Open a PR (or leave the branch pushed) for the Claude Opus session to review before merge
into `mve/integration`. Nothing merges without that review.
