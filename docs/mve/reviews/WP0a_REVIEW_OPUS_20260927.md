# WP-0a review (Claude Opus) — branch codex/mve-wp0-preflight @ ae2ed0ad413

**Verdict: CHANGES REQUESTED (one blocking item). Not merged.**

Reviewed from a clean `git archive` of the branch; tests run there with coverage.

## What passes
- Scope matches r5 §11 WP-0a: offline only, `live_calls = 0`, `actual_api_cost_usd = 0`.
- Network and keychain guard: `sitecustomize` audit hook blocks socket connect / DNS / `security`;
  API keys are stripped from child environments; a test proves a child's connect fails.
- Honest reporting: every capability is "ran" or "failed" with a reason; directory presence is
  not treated as a working Euclid fixture; toolchain presence is not treated as a build.
- The two runner findings reproduce with fake transport: two cells charged USD 0.08 against a
  USD 0.05 cap (no in-flight reservation), and both ran while the rate function returned peak.
  These are real WP-9a inputs.
- DEPS.lock pins file bytes and git shas; no secrets found in report.json or DEPS.lock.
- 9 tests pass.

## Blocking
1. **Coverage below the r5 §11 convention (≥ 80% of new code).** Measured total 65%:
   `core.py` 100%, `offline.py` 96%, but `vision_contract.py` 0% and `openjev_fixture.py` 0%
   because both only run as subprocesses. The builder's "98% core/dispatcher coverage" is true
   for those two files only and should be stated with that scope.
   Fix: make `vision_contract.exercise()` testable with an injected fake module (a stub `W`
   and `run_all` that writes a ledger), and move `openjev_fixture` logic into a function that
   takes a backend so a fake backend can be tested; keep the `__main__` entry thin.

## Non-blocking
- `vision_contract.py` executes `run_all` with fake transport, which goes beyond the plan's
  "import only" wording. Acceptable and more informative; note it in the WP-0 doc.
- `test_r5_schema_packet_is_unchanged_and_valid` uses cwd-relative paths; anchor on the repo
  root via `Path(__file__)`.
- Absolute home paths are hard-coded as module constants; fine for a preflight, but move them
  into one config dict so WP-9 can reuse them.
- One pytest warning in the run; check it.

## Next
Push the fix to the same branch; I re-review and fast-forward `mve/integration`. WP-1 should
rebase onto `mve/integration` after the merge.
