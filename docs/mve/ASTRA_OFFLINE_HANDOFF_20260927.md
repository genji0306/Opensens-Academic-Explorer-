# Astra offline development handoff — 2026-09-27

Worktree: `~/Developer/Opensens/worktrees/oae-mve-integration`.
Integration remains reviewed r5 `5645250003f129473919f4f32984c68a86e1c477`.
The v5 schema and plan were not edited. No implementation branch was merged.
No hosted model calls were made. No messages were sent to reviewers.

| Review branch | Head before this handoff | Evidence |
|---|---|---|
| `codex/mve-wp0-preflight` | `ae2ed0ad413` | `docs/mve/WP0_PREFLIGHT_20260927.md` |
| `codex/mve-wp1-semantics` | `ca516ff7970` | `docs/mve/WP1_SEMANTICS_20260927.md` |
| `codex/mve-wp9a-budget` | `3fbff7fa8a3` | `docs/mve/WP9A_BUDGET_20260927.md` |
| `codex/mve-wp11a-evaluation` | this branch | `docs/mve/WP11A_EVALUATION_20260927.md` |

Read each report on its branch. Every packet branches directly from r5, so integration
requires Opus review, combining the DEPS.lock receipts and retaining each packet's tests.
Common test scaffolding may need a small formatting-only conflict resolution. The r2
self-check commit was removed from the preflight branch; r5 PASS remains authoritative.
Old unfinished r2 tests and the WP-1 coverage receipt remain in named local stashes.

WP-0a retains both fake-only runner findings: absent in-flight reservation and peak hours
labelled but not refused. The new budget primitive addresses those patterns in isolation;
it does not modify or endorse the old runner. Newclid/JGEX and Euclid discovery gaps remain
as described in the WP-0a report. No unsupported Euclid fallback decision was made.

Next reviewed integration work: combine the foundations, run their combined tests, finish
artifact/run-adapter binding and isolation, then proceed to the generator and deterministic
fixtures. User direction remains offline: WP-0b hosted probes must not run during this
session merely because some prerequisites now have code. Vendor pricing/window agreement,
transport integration and the full evaluation protocol are not established by these tests.
