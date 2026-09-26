# WP-0 preflight — 2026-09-27

Execution receipt: `mve/preflight/results/report.json`; actual by-path bytes and git
revisions: `mve/DEPS.lock`. Run with `python3 -m mve.preflight.run` (offline only).
Nonzero exit is intentional when a required capability fails. No API calls were made;
actual API spend is USD 0. There is no live-call transport in this packet.

- RH Jev: **308 tests passed** in 3.80 seconds, with network/keychain blocked.
- openJev: fixture inference ran (38 input tokens; 59.323 ms forward; 1.325 s including
  load). It selected topology for the triangle workflow fixture with confidence 0.411.
  This establishes executable inference, **not classification accuracy**. Its returned
  probabilities renormalize away abstention while confidence does not; WP-5 must adapt
  this explicitly rather than equating the two.
- Vision/runner: callable and raw-response retention ran with fake transport. Two
  concurrent cells charged USD 0.08 against a USD 0.05 simulated cap. Both invoked the
  fake transport while the rate function returned peak. Thus in-flight reservations and
  peak refusal **fail**. Window boundary outputs are in the receipt; current vendor
  pricing/window agreement remains UNVERIFIED. Image limits use an estimate, not a guard.
- DeepSeek live probe: **failed prerequisite**, withheld because the borrowed runner
  failed enforcement and no current verified pricing lock exists. The single permitted
  live-call allowance remains unused. WP-9a must provide enforcement before paid work.
- Newclid: import failed in the selected Python environment. Actual GeoGebra dependency
  and licence terms unavailable; no licence conclusion or silent alternative adopted.
- Lean: isolated pinned source-config smoke build attempted, substituting `import Mathlib`
  for RH programme sources. OS sandbox denied network; absent isolated dependency cache
  caused Mathlib acquisition to fail. This is not a successful RH or MVE/LeanGeo build.
- Atlas: exact `validate_bundle` signature executed; malformed empty bundle rejected.
  Positive MVE ingest is not established and belongs to WP-9 integration work.
- Codex: local CLI reports 0.154.0. rhvf, Explorer and local worker files are pinned;
  their end-to-end contracts remain explicitly failed/unverified in the report.

The latency/token/cost model retains nulls for vision and human measurements. It records
2 calls/image and the cost formula, with aggregate USD 20, P0 USD 2 and P1 USD 8 limits;
these are requirements, not enforcement supplied by this packet.

Validation: tests written first and observed failing before implementation; 6 tests pass,
87% coverage of preflight core/dispatcher. External probe scripts are exercised through
recorded subprocess runs, outside that unit coverage denominator. Manual review checked
network denial, explicit failures, actual-byte pins, bounded subprocesses and no secret
output. The scripts never resolve credentials. No external files were edited.

The main checkout's wiki overview/index were read first. This integration branch has no
wiki manifest or refresh script, so refresh is unavailable here; main checkout unchanged.
Awaiting Claude Opus review; no implementation merge authorized without it.
