# WP-9a / WP-11a follow-ups 6–8

Branch `codex/mve-review-boundary-tests`, based on `github/mve/integration` at
`e827c05717d`. Offline only, for Opus review; no merge or hosted call.

- Weekday UTC tests cover the instant before and at 01:00, 04:00, 06:00 and 10:00.
  Each tests reservation and dispatch and repeats the time comparison in UTC+07:00.
- Zero input/output tokens produce a zero computed ceiling, which is deliberately
  refused as a paid-call reservation. No attempt or dispatch permit is created and
  ledger exposure stays zero. Zero-price bounds follow the same positive-ceiling rule.
  Account-quota activity is recorded separately; this API grants no free hosted calls.
- A real sandboxed child creates a symlink to the private root after launch. Creation
  succeeds, and reading truth.json through that link is denied with EPERM. The test
  cannot pass merely because staging rejected a pre-existing link.

Validation: 10 new cases plus related budget/pricing/isolation tests: **41 passed**.
Ruff and file/function limits pass. No production behavior changed; the positive-ceiling
policy now has an API docstring. Source/test hashes appended to the aggregate DEPS.lock.

Review item 5 belongs to WP-0b: unverified prices must be rejected before any hosted call.
That packet and any hosted transport remain outside this change.
