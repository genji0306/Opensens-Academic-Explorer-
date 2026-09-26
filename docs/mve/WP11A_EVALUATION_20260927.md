# WP-11a offline evaluation infrastructure — 2026-09-27

Branch: `codex/mve-wp11a-evaluation`, directly from r5 integration
`5645250003f129473919f4f32984c68a86e1c477`. For Opus review; not merged.
Plan and v5 schema unchanged. Hosted inference calls: **0**; API spend: **USD 0**.

## Delivered

- `mve/evaluation/splits.py`: deterministic, immutable, hashed family partitions for
  development, retrieval, fit, calibration and evaluation. Style variants sharing a family
  cannot cross partitions. Allocations count families, not images. Reload verifies the
  expected manifest hash and structure. Retirement creates a new artifact linked to its
  parent and refuses evaluation through the retired artifact.
- `scoring.py`: binary relation query-set and full-record scorers, explicitly separate.
  Three schema-v5 evaluation tasks must be selected individually. Micro relation and macro
  diagram metrics both include counts. Missing, malformed, timeout and abstaining outputs
  stay in frozen denominators; out-of-universe relations invalidate the diagram response.
  Query omission is unanswered; omission from a valid complete record is predicted false.
  Unknown gold is rejected, not relabelled false. No empty scored diagram is accepted.
- Independent binary-guess nulls and the all-positive baseline use the same micro/macro
  weights. Undefined metrics return null with their eligible macro diagram counts. A
  full-record random-set null is explicitly N/A. Negative unanswered cases are reported
  separately and included in `negative_error_or_missing_rate`; a zero raw FPR obtained by
  abstaining is not a gate pass. Full-record exact results are counts; total diagrams are
  the denominator. Positive unanswered queries reduce recall without being conflated with
  explicit false predictions in the FN count.
- `manifest.py`: split, gold, scorer-source, model revision and six control categories
  are frozen together before scoring. Every evaluation diagram must have gold. Changes to
  the gold, split or scorer refuse scoring. Controls pin fixture ids and content hashes for
  exact positives, adversarial/near-miss negatives, weakened/strengthened statements and
  unchanged-record round trips. Fixtures still need domain-specific expected outcomes.
- `confidence.py`: one-sided 95% Clopper–Pearson bounds, using pinned SciPy 1.17.1.
  Zero trials or undeclared independence cannot pass. The fixture distinguishes 0/148
  (upper bound about .020038) from 0/149 (about .019905) at the proposed .02 limit.
  This is only a component test, not G1 or any other complete scientific gate. Method:
  [SciPy binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)
  and [exact proportion interval](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).
- `isolation.py`: allowlisted public packet construction preserves stated givens and
  problem text on the annotated track, refuses hidden fields and path traversal, and
  separates the two tracks and three tasks. A macOS sandbox subprocess denies reads/writes
  under declared private roots and denies network operations. The subprocess receives a
  minimal environment, closed inherited descriptors and Python isolated mode. Public
  staging rejects symbolic and hard links. Missing sandbox support or timeout fails closed.

## Observed validation

`COVERAGE_CORE=pytrace python3 -m pytest tests/mve -q --cov=mve --cov-report=term-missing`
passed **20 tests**, **91% statement coverage**. A real isolated child read its public
fixture while both an attempted gold read and a loopback connection returned EPERM.
Tests also exercised family leakage rejection, changed hashes, retirement, malformed
outputs, weighting, exact binomial bounds, linked-file leakage and worker timeout.
`ruff check mve tests/mve` passed; files ≤800 lines and functions ≤50 lines.
`mve/DEPS.lock` records Python/platform, dependencies and source hashes.

## Limits and review obligations

No benchmark was run and no scientific gate passed. This is the binary relation slice;
variable-choice Geoperception scoring/chance, paired classifier comparison intervals,
formalization rubrics and PD scorers remain separate tasks. Candidate ids and exact gold
must come from reviewed WP-1/WP-2. Correlated relations must not be presented as independent
trials; the caller must document its sampling design before using a binomial gate.
Image-byte hashes, decoding/repair budgets, actual model revisions and control execution
receipts must be bound by the future run adapter in addition to these primitive manifests.
The stored control hashes establish identities, not successful execution or correctness.

The sandbox guarantees tested direct access denial for **declared gold roots**. It is not
an all-files allowlist, container or defense against arbitrary hostile native programs.
It cannot discover undeclared gold copies. Public data must be curated into a dedicated
staging directory before launch; the operator must inventory every private location and
prevent concurrent staging changes. Initial deny-default sandbox experiments could not
start Python on this host; no unguarded fallback was introduced. The delivered profile
uses default allowance with explicit private-root and network denial. A hosted adapter
needs a separately reviewed isolation design and must not weaken this offline barrier.

Retirement artifacts must be persisted and the operational registry must select the
latest artifact. Old signed/hashed data is not remotely revoked by an immutable object;
this packet does not implement that registry. A hash is not an authenticated signature.
The public packet contract rejects secret fields but cannot recognize a secret deliberately
placed inside legitimate free text. No proof authority or model trust is inferred.

All work occurred in the Developer worktree. Integration is unchanged. Shared wiki refresh
scripts are absent from this base, so the durable handoff is kept under docs/mve.
