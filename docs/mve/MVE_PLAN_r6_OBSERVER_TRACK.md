# MVE plan addendum r6.2: the Observer track (O)

**Date:** 2026-09-28 · **Status:** r6.2, revised after Astra's r6.1 verdict (BLOCK; B1, B3, B5, B6
closed; B2, B4 partial), itself after the r6 verdict (`docs/mve/ASTRA_VERDICT_MVE_PLAN_r6_20260928.md`);
for an Astra re-verdict. It does not edit the frozen r5 text (`docs/mve/MVE_PLAN.md`). Every addition to r5, including the r5
changelog for the new evidence class, lives in this addendum.
**Direction (owner, binding):** "The atlas (the lab creates visualization/geometry/topology) is the
input → MVE observes and creates hypotheses/theories/insights as output → RH research fleets
test/verify/create attack lanes → report to the Atlas."

## Revision r6.2 (changes against r6.1 `fe3cdf175a8`)

| # | Astra r6.1 finding | Fixed in |
|---|---|---|
| r6.2 notes | Astra r6.2 PASS WITH CHANGES: power wording, A1/A2 conditionality, Monte Carlo convention, nominal CP | Applied in §5 (Opus, 2026-09-28). |
| B2 (partial) | iid refit bootstrap, unvalidated dependence and 3,333→33,000 transfer; no joint exponent test; "KS 1% OR 95% CI" has no overall α | Honest route. §3: every card-#1 v2 p-value is **nominal/exploratory**; Monte Carlo p = 1/201 with one-sided 95% upper bound 0.01487; H0 stays `inconclusive`. §7 WO-3: v2 is a **regression fixture**, not inferential certification (`C1H/lane_check_v2_status.json`, `inferential: false`). §2c rules 4, 5, 5a for future checks: dependence-preserving refit calibration at the actual n with a size check, joint bootstrap of (measured − model-implied) exponent, one kill rule with one overall α. Sanity addendum `C1H/lane_check_v2_sanity.py` (91 s) demonstrates both devices, exploratory |
| B4 (partial) | binomial/CP unit assumes iid Bernoulli trials; opportunities per cluster unfrozen; image-free arm not budget-matched | §5 rewritten as a **fixed stratified cluster design**: strata (module × family), clusters (discovery/replication block pairs), fixed V views × C card slots × 1 check per slot in every arm, image-free and shuffled arms budget-matched, seeded allocation, exact cluster-level sign-flip permutation test per control arm (one-sided 0.05, intersection–union), K ≥ 20 clusters, detectable effect stated; CP descriptive only; pilot descriptive only (§5, §6 GO2, §7 WO-4/WO-6) |

## Revision r6.1 (changes against r6 `fc27b211c5f`)

| # | Astra r6 blocker | Fixed in |
|---|---|---|
| B1 | Index/height labels, gap counts, N_eff formula without Λ; WO-3 fixture encoded wrong claims | §3 rewritten from `lane_check_v2.json`: blocks named by zero index, heights 2.6765e11 / 1.4418e20 / 1.3709e21, 9,999 gaps each, N_eff = log(H/2π)/√(12Λ), rounding and asymptotic limits disclosed. Card #1 is a **retrospective exploratory example**, not a prospective test. WO-3's golden fixture is the v2 receipt; v1 is kept as the historical record only (§7) |
| B2 | Numerical reproduction is not calibration | (partly superseded by r6.2) §2c rules 3–4 and 7: the whole unfold→fit→test procedure is calibrated by simulation with refitting; dependence is handled by thinning and surrogate sequences, or p-values are labelled nominal; actual denominators are reported; the primary statistic is compared with the accepted baseline (exact GUE/Gaudin law, CUE(N_eff)); the CDF exponent is compared with Planck's `a`; likelihood sums are called marginal composite scores; the causal "finite-height effect" claim is removed (§3) |
| B3 | Contradictory survival definitions; H1 counted in GO2; no image-free baseline | §2c rule 6 separates `replicated_observation`, `baseline_explained` and `baseline_exceeding_survivor`; only the last counts. H1 is `baseline_explained`, owner-originated and unblinded, so it is out of GO2 (§3). §5 adds an image-free fixed-card arm and a shuffled-image ablation arm |
| B4 | Sampling assumptions of the GO2 bound | (superseded by r6.2's cluster design) §5: the unit is an independent source block (cluster), with an intersection–union test over three control arms; card limits, retries, check selection and stopping rules are frozen; development and untouched replication partitions are separated; contrast sensitivity is pre-declared |
| B5 | Incomplete identity hash; no `preliminary`; GO1 denominators | §2b: `check_spec` field; hash over the full card specification; transitive invalidation; `preliminary` in the lifecycle; current-revision, survivor-only hand-off; `hyp_N` rejected on every formalisation path. §6: GO1 denominators. §7 WO-2: H0/H1 fixtures with real hashes |
| B6 | Live readiness overstated | §7 pilot cost and §8: USD 0.000268 is **known exposure only**; aggregate-ledger reconciliation, O-M2 price/quota verification and worst-case reservation are pre-dispatch conditions; fleet ownership, GO3 timing and atlas status confirmation are pre-relay dependencies (§2d, §9) |
| notes | non-blocking | WO-1 isolation tests strengthened (§7); CP numbers called rejection thresholds, not power (§5); Planck normaliser T^{a+1}Γ(a+1)ζ(a+1) (§3); GO4 = absence from a searched corpus (§6) |

**Reading rule (r5).** Every external capability is UNVERIFIED until a packet executes it. Atlas and
lab paths come from a read-only survey on 2026-09-28; the result-bundle schema, snapshot plan, inbox
adapter and handshake script were read directly.

Abbreviations: `AT` = `~/Developer/Opensens/worktrees/oae-rh-atlas-p0-20260924` (branch
`claude/rh-atlas-p0-20260924`, live v277); `ZE` = `~/Developer/Opensens/worktrees/zeta-explorer-main`;
`EA` = `AT/data/riemann/evidence_atlas`; `RHVF` = `~/Developer/Opensens/rh-visual-fields`;
`C1H` = `docs/mve/observer/card001_hawking/`.

---

## 0. Summary

MVE gains an **Observer track (O)**: it looks at atlas lab visuals, as the owner does, and writes
**hypothesis cards** (a testable claim, a frozen check specification, a kill criterion). A cheap check
runs on the lab's source data, never on pixels. Cards whose pattern exceeds the declared baseline at
replication go to the RH fleets as attack-lane proposals; lane outcomes return to the atlas as result
bundles. The **Euclidean track (E)**, everything r5 built, becomes **observer calibration** against
exact synthetic truth. Track O's central metric is a **pareidolia null**: in a fixed stratified
cluster design, baseline-exceeding survival on real source blocks must exceed survival in null-twin,
image-free and shuffled-image arms by an exact cluster-level permutation test. MVE is allowed to be wrong. Its product is testable hypotheses, not answers.

---

## 1. Purpose change and scope

| | Track E (r5, unchanged) | Track O (new) |
|---|---|---|
| Input | synthetic Euclidean diagrams with exact truth (WP-2) | atlas lab snapshots (§2a) |
| Output | typed observation records, statements, proofs | hypothesis cards, data-check receipts, lane proposals, result bundles |
| Truth | exact generator truth | none at observation time; the data check and the fleet decide |
| New role | **observer calibration**: G1-style precision/FPR per perceiver on exact truth becomes that observer's reliability record, cited by its cards | perception: seeing a pattern or a resemblance and making a prediction |

**Nothing merged under r5 is discarded.** The evidence model (§4a), the ledger and budget guards
(WP-9a/WP-0b), the two-call perceiver (WP-3), verdict capture with human-only `adopt` (WP-8a), the
openJev routing and learning scaffolding (WP-5), the evaluation machinery (WP-11a, including one-sided
Clopper–Pearson in `mve/evaluation/confidence.py`), the formalizer (WP-6) and the reports (WP-9b/11b)
are all reused. The gates G0–G6 stay as they are: all "not established" per
`docs/mve/reports/SUMMARY.md` on `mve/integration`. Track O adds gates GO1–GO4 (§6). It changes no
E-track threshold.

**Scope limits.** MVE does not edit the atlas, the lab, Lane R (`rh-lane-r`, read only) or the
Jev-harness/dream lane. It integrates only through the contracts in §2. MVE does not create fleet
lanes. It proposes them. A card never authorises a formal proposition (§2b). E is the only place
where perception is scored against exact truth, so until G1 is established every O-track card
carries `observer_reliability: not_established`.

---

## 2. The loop and its contracts

```
 ATLAS LAB (atlas owner)          MVE track O (this repo, mve/observer/)          FLEETS / ATLAS
 ┌──────────────────┐  C1   ┌────────────┐  C2  ┌──────────┐  C3  ┌─────────┐  C4  ┌──────────────┐
 │ lab module +     │──────►│ snapshot   │─────►│ observer │─────►│ data    │─────►│ lane proposal│
 │ params + data +  │ read  │ manifest + │      │ (model / │ card │ check   │ adopt│ (handshake   │
 │ control twin     │ only  │ blinded PNG│      │  human)  │      │ + repl. │ human│  exchange)   │
 └──────────────────┘       └────────────┘      └──────────┘      └─────────┘      └──────┬───────┘
          ▲                                                                              │ lane verdict
          │ C5: result bundle → EA/inbox → ingest-inbox → atlas-build (atlas owner, Lane R window)
          └──────────────────────────────────────────────────────────────────────────────┘
```

### 2a. C1: lab snapshot export (read-only)

Sources, in order: (1) committed snapshots `EA/inputs/lab_snapshots.json` (entries `id, module,
title, params, summary, informs, caveat, why.records, attack_ids, capture.params_sha256,
capture.png.{path, sha256}`; `python3 -m rh_evidence.labs_snapshots capture|restore`, headless
Chrome, ≤ 1% pixel tolerance); (2) `ZE/scripts/astra_p34_capture.py` (maxwell, dyson, andreev,
continuation, bec; control off/on); (3) the bridge `AT/rh_evidence/labs/atlas-bridge.js`, which has no
PNG script yet (the atlas owner's work; MVE may request it).

**MVE never writes into AT or ZE.** New captures run from a `git archive` export of the pinned AT/ZE
HEADs into `mve/observer/snapshots/<capture_id>/`, following the "build from a clean archive" rule.
`DEPS.lock` records both HEADs.

**Snapshot manifest** (`mve/observer/snapshots/manifest.json`, one entry per image):

| Field | Meaning |
|---|---|
| `snapshot_id` | MVE id; for committed snapshots also `atlas_snapshot_id` |
| `module`, `deep_link` | e.g. `spectral`, `#labs/field-dyson`, `#labs/space-<scene>` (keys from `AT/rh_evidence/atlas_labs.py`, `export.py:LAB_MODULES`) |
| `params`, `params_sha256` | exact lab state |
| `lab_commit` | AT and ZE HEAD shas |
| `data_ref` | `{path, sha256, generator, seed, source_block_id, stratum, role: development \| discovery \| replication \| donor}` (§5) |
| `control` | `{kind: null_twin \| donor \| contrast \| none, cluster_id, twin_snapshot_id}` (§5) |
| `png_full` | `{path, sha256, w, h}`: the page as a human sees it |
| `png_blinded` | `{path, sha256, crop_box, caption_free: true, metadata_stripped: true}`: model view |
| `withheld_text` | title, summary, caveat, legend strings. Stored, never shown to model observers |

Acceptance rules for C1:
- The data hash must be reproducible from `data_ref`. If the source data cannot be named and hashed,
  the snapshot is `not_checkable` and is excluded from GO2.
- A control twin must be a **control-only render** with the same params, palette and crop. Many lab
  toggles draw the control over the real data. That kind of overlay is not a twin, and WO-1
  establishes per module which renders qualify.
- Modules with no control toggle (heat 04, space-sphere, strip, eigen, impedance, bec) are open to
  owner observation but excluded from GO2 until the atlas owner provides a twin.

### 2b. C2: observation → hypothesis card (new evidence class `hypothesis`)

**Addition to r5 §4a (changelog kept here; frozen r5 is not edited).** A sixth class, `hypotheses`
(`hyp_N`), is added. It **never authorises** a formal proposition, an assumption or a derivation. It
may be cited only by data checks, judgments and hand-offs. The formaliser, the proposition builder,
the assumption path and the derivation checker each **reject any `hyp_N` in their support set,
directly or transitively** (a fixture per path in WO-2). A card reaches formalization only through a
human-created `txt_N` source adopted on the normal E-track path. Schema v5 is unchanged; cards use
`schemas/mve_hypothesis_card.json` (`oae-mve-hypothesis-card-v1`), validated by `mve/observer/card.py`
with `mve/graph.py` for `depends_on` and transitive invalidation.

| Field | Content and rule |
|---|---|
| `card_id`, `revision`, `content_hash` | `content_hash` = sha256 of the canonical JSON of **every specification field**: `claim, testable_form, prediction, primary_statistic, kill_criterion, check_spec, sources, observer, resemblance_target`. Any change is a new revision |
| `claim` | one sentence about the displayed object |
| `testable_form` | the statistic or construction, the data it runs on, the baseline, the direction |
| `prediction` | the value or sign expected **at the replication scale** |
| `primary_statistic` | exactly one, declared before the check runs; the others are secondary |
| `kill_criterion` | a pre-registered numeric rule; "unfalsifiable" fails validation |
| `check_spec` | the complete frozen check: check id and library version, estimator, fitting interval, baselines with versions and parameter counts, α, calibration method and replicate counts, dependence handling (thinning or blocks), replication data selection (`source_block_id`s and sha256s from the replication partition), seeds, kill rule, `spec_sha256` |
| `sources` | ≥ 1 `{snapshot_id, png_sha256, data_sha256}` |
| `observer` | `{id, kind: human \| model, model_id?, prompt_sha?, call_ids?, blinded: bool}`. **One originating observer per card.** Another observer's agreement is a judgment, not a co-author |
| `resemblance_target` | optional: what it looks like, plus the mapping claimed |
| `novelty` | `{status: unchecked \| known \| partial \| absent_from_searched_corpus, queries, index_shas, planted_control_hit}` (GO4) |
| `suggested_lane` | free text plus a Q-card-lane label once active |
| `prior_plausibility` | `{value: low \| medium \| high, by: observer_id}`. A judgment, never a gate input |
| `observer_reliability` | a reference to the observer's E-track calibration receipt, or `not_established` |
| `status` | `draft → well_formed → frozen → preliminary → checked:{killed, replicated_observation, baseline_explained, baseline_exceeding_survivor, inconclusive, not_checkable} → adopted → handed_off → lane_verdict:{…} → reported` |
| `judgments` | as r5 (`confirm/reject/unsure/adopt/decline`), each bound to one `(card_id, revision, content_hash)`. **Only a human `adopt` moves a card to `adopted`**. Model judgments carry weight 0.5 and never authorise |

**Invalidation.** A new revision, or a changed snapshot or data hash, invalidates transitively every
check receipt, judgment, adoption and hand-off bound to the old `content_hash` (`mve/graph.py`).
**Hand-off eligibility:** only the current revision, with status
`checked:baseline_exceeding_survivor` and a human `adopt` bound to that revision's hash.

### 2c. C3: the cheap data check

A data check runs on the snapshot's **source data**, never on pixels. Its code lives in
`mve/observer/checks/` and is local and free.

1. **Freeze first.** `check_spec` is written and hashed into the card (status `frozen`) before any
   replication-partition data is read. Replication data are an **untouched partition** (§5); a
   "larger sample" may not reuse stage-1 or development observations.
2. **Two stages, always.** Stage 1 uses the data behind the snapshot (development partition). Stage 2
   is the replication on the frozen replication selection. **A stage-1 result alone yields no
   verdict**; it can at most make the card `preliminary`. Stage 2 must meet the size the spec declares;
   a smaller sample makes the card `inconclusive`, not killed or surviving.
3. **Baselines are the accepted model, not a convenience.** For spacings: the exact GUE limit (Gaudin
   law via the sine-kernel Fredholm determinant) and finite-N CUE at the Bogomolny et al. effective
   size, with the rounding of N_eff and its asymptotic nature recorded; the Wigner surmise is a
   secondary reference only. The **primary statistic is compared with the accepted baseline**.
   Penalise extra parameters (AIC and BIC). Sums of marginal log densities are reported as
   **marginal composite scores**, not joint likelihoods, because gaps are dependent.
4. **Calibrate the procedure, not the formula.** A p-value enters a verdict only if it comes from
   simulating the complete procedure (unfolding, fitting with refitting per replicate, thinning,
   testing) **at the actual sample size** with a **dependence-preserving** null: simulation from a
   declared dependent null, or a moving-block bootstrap of the unfolded sequence after the fitted
   model's quantile transform (data ranks, fitted marginal: s*_i = F̂⁻¹(rank_i/(n+1))). The device is
   **validated** before use by a size check on sequences from a known dependent null (e.g. CUE spectra
   with the same thinning) at the declared α, with enough replicates to resolve that tail (≥ 20/α).
   No transfer of a null across sample sizes. Fixed-CDF KS p-values after fitting are invalid. A
   Monte Carlo p is reported as (1 + r)/(B + 1) with the one-sided 95% upper bound on the tail
   probability. Anything short of this is labelled `nominal` and cannot enter a verdict. The receipt
   states the actual denominators (fit size, test size, replicate counts).
5. **A structural statistic is required** beside any omnibus fit (e.g. the small-gap CDF exponent,
   residue-class counts for primes). Estimator and interval are declared in `check_spec`. The test
   is on the **difference** between the measured value and the fitted model's implied value under
   the same estimator and interval, by a joint dependence-preserving bootstrap that refits the model
   in every replicate; the model's asymptotic exponent is reported beside it.
5a. **One kill rule, one overall α.** `check_spec` declares a single kill rule and its overall α:
   either one primary statistic, or components with an explicit split (e.g. Bonferroni: KS at 0.005
   and a 99.5% CI for the exponent difference, overall ≤ 0.01). "KS at 1% OR exclusion by a 95% CI"
   is not an overall 1% test and fails validation.
6. **Outcomes.** `killed` (the kill rule fires at replication); `replicated_observation` (the stated
   pattern reappears at replication; specificity not run or undecided); `baseline_explained` (it reappears **and** samples from the
   declared baseline reproduce it at the declared α: a known or explained pattern); and
   `baseline_exceeding_survivor` (it reappears, the kill rule does not fire, and baseline samples fail
   to reproduce it: specificity). Only `baseline_exceeding_survivor` counts as survival in GO2 and is
   eligible for hand-off. Also `inconclusive` (underpowered, stages disagree, replication size not
   met) and `not_checkable`.
7. **Receipt.** Script sha, `spec_sha256`, data sha256s, seeds, runtime, Python/numpy/scipy/mpmath
   versions, the denominators of rule 4, and `inferential: true | false` (false unless rules 4–5a hold).

### 2d. C4: fleet hand-off (attack-lane proposal)

Only an eligible card (§2b) is handed off, as a submission record in the shape that
`~/Developer/Opensens/worktrees/oae-rh-graph-20260903/scripts/rh_lane_handshake.py` reads (exchange
root `~/Developer/Opensens/Opensens Academic Explorer/.llm-wiki/activity/review-exchange/`), with the
keys of live records: `work_id = mve-card-<card_id>, round, review_id, submitter: "mve", reviewer,
packet_type: "attack_lane_proposal", summary, caveats, evidence, report_path, report_sha256,
changed_files: [], commit, schema_version, submitted_at, supersedes, relayed_by, packet_hash`. The
report is the card plus its receipt; a revised card is a higher `round`, never a new id.

MVE writes submissions only to `mve/observer/outbox/exchange/`. **Pre-relay dependencies (all
required before the first relay, recorded in `DEPS.lock` with the owner's answer and date):** (a)
fleet ownership of lane creation is named (Q3); (b) GO3's N and its clock start are set (Q3); (c)
the atlas owner has confirmed the status mapping of §2e and the `technical_failure` defect (Q5);
(d) the exchange-write mode is decided (Q4). Until then outbox records are written and validated but
not relayed. The relayer (Opus reviewer session) copies them after review, unless the owner allows
direct writes (Q4). The fleet side decides whether to open a lane.

### 2e. C5: outcome back to the atlas

A lane outcome becomes a result bundle against `EA/schema/result.schema.json` (required fields:
`runId, taskId, statement, method, reproduce, schemaVersion "1.0", status, assumptions, sources,
artifacts, results, counterexamples, limitations, proposedBlockerChanges, resources, review{state,
reviewerId, reviewedRevision}`). Per `AT/rh_evidence/adapters/result_bundle.py`: `reproduce` is
recorded, never executed; artifact paths are relative, exist under the atlas root and match sha256;
no bundle arrives `accepted`/`rejected`; `runId` is new (bundles are immutable).

MVE writes bundles and artifacts to `mve/observer/outbox/atlas/`. The **atlas owner** copies them into
`EA/inbox/` and AT, runs `python3 -m rh_evidence.cli ingest-inbox` and `atlas-build` in a Lane R window.

Proposed status mapping (**unconfirmed; confirmation by the atlas owner is a pre-relay dependency**, Q5):

| Card / lane outcome | `status` | Notes |
|---|---|---|
| survivor handed off, no lane result yet | `proposal` | statement = the card's claim; limitations list the stage-1/2 caveats |
| lane or data check refutes the card | `refuted_candidate` | read here as "the candidate claim was refuted". Confirm this is the atlas meaning |
| lane supports the claim | `completed` | `limitations` carry the novelty status |
| baseline-explained or replicated observation | `completed` | limitation "explained by the declared baseline"; never a new-lane proposal |
| underpowered or disagreeing stages | `inconclusive` | |
| lane could not run | `technical_failure` | see the defect below |

**Contract defect (for the atlas owner; not fixed by MVE).** The schema enum is `technical_failure`, but
`AT/rh_evidence/services.py:229` sets `infrastructure_failure` only for `failed_infrastructure`,
`timeout` or `crashed`, so a `technical_failure` bundle is staged `numerical`, not `unreviewed`. MVE
holds such bundles until it is fixed.

---

## 3. Worked example: card #1 ("Hawking gaps"), retrospective and exploratory

**Classification.** Card #1 is a **retrospective exploratory example**. The v2 specification was
written after the v1 numbers were seen, the observer was the owner, unblinded, and no replication
block meets the ≥ 10,000-gap size H0 declared. Its outcome is evidence about the method, not a
prospective test and not a GO-gate input. A prospective test of any successor card needs a frozen
`check_spec` and replication data that qualify as declared.

**Observation.** On lab 05 (spectral / Hilbert–Pólya: ζ gaps vs a GUE sample vs Poisson), the owner
thought the ζ gap density looked like a Hawking/quantum-radiation spectrum. Observer: `human:owner`,
unblinded (full page).

**Card H0** (as it would be filed):
- claim: unfolded ζ-zero gaps follow a Planck-shaped law p(s) = s^a / (e^{s/T} − 1) / Z with
  Z = T^{a+1} Γ(a+1) ζ(a+1), rather than the GUE law.
- testable form: 2-parameter Planck MLE vs the GUE limit and finite-N CUE; primary statistic
  (re-declared in v2, retrospectively; r6 used Δloglik vs Wigner): fitted-Planck KS; structural
  statistic: the small-gap CDF exponent. Near 0 the Planck CDF grows as s^a, so its CDF exponent is **a** (density s^{a−1}); the
  GUE CDF grows as s³ (density s², β = 2).
- kill criterion: at replication (≥ 10,000 gaps per block), Planck KS p < 0.01, **or** the
  Planck-implied CDF exponent outside the 95% CI of the measured one. As filed this rule has no
  overall α (1% OR 95% is not a 1% test); under §2c rule 5a it would fail validation today.
- resemblance target: Hawking/Planck spectrum. Suggested lane: spacing statistics.

**Stage 1** (`C1H/hawking_check.py` → `hawking_check.json`, unchanged). Zeros 1–2000 by mpmath, first
20 gaps dropped, 1,979 gaps, mean-normalised. Planck fit a = 5.48, T = 0.155; Δ(marginal score) =
+12.5 over the Wigner surmise; nominal fixed-CDF KS p: Wigner 0.0024, Planck 0.57. These p-values are
uncalibrated (fitted parameters, dependent gaps), so stage 1 gives at most `preliminary`.

**Stage 2, corrected** (`C1H/lane_check_v2.py` → `lane_check_v2.json`; inputs pinned in
`C1H/ODLYZKO_SHA256SUMS`; seed 20260928; spec sha256 in the receipt). Blocks are named by **zero
index**; heights come from the Odlyzko headers. Unfolding uses the smooth counting function, with no
mean normalisation (unfolded means 1.0000–1.0001). Key tests use every 3rd gap. N_eff =
log(H/2π)/√(12Λ) with Λ = 1.57314 (Bogomolny, Bohigas, Leboeuf, Monastra 2006, math/0602270), taken
at the block's median height and **rounded** to the CUE size sampled. It is an asymptotic
large-height approximation; at N_eff ≈ 2 it is outside its useful range.

**Status of every v2 p-value: nominal and exploratory.** The Planck bootstrap draws iid replicates;
the dependence of the thinned gaps (|r| ≤ 0.05 at lag 1) is not shown to leave the 1% tail of the
fitted KS intact; the GUE null comes from concatenated CUE(50) spectra, which do not establish the
dependence law of zeta zeros; its 95% check does not validate a 1% threshold; and the low block's
3,333 → 33,000 transfer is unvalidated. WO-3 reproduces these numbers as a **regression fixture**, not
as inferential certification (`C1H/lane_check_v2_status.json`).

| Block (zero index) | Median height H | Gaps all / thinned | N_eff (range) → CUE N | GUE limit KS: D, p (nominal) | CUE(N) p (nominal) | Planck a, T | Planck KS: D (boot max), p_MC | CDF exponent b̂ [95% CI] | Implied b: Gaudin / Planck |
|---|---|---|---|---|---|---|---|---|---|
| #1,001–#100,000 | 4.08e4 (1.42e3–7.49e4) | 98,999 / 33,000 | 2.02 (1.25–2.16) → 2 | 0.0171, 1/201† | 1/201† | 4.84, 0.173 | 0.0232 (0.0059), 1/201 | 3.04 [2.92, 3.17] | 2.92 / 4.16 |
| #10¹²+1 – #10¹²+10⁴ | 2.6765e11 | 9,999 / 3,333 | 5.63 → 6 | 0.0182, 0.22 | 0.60 | 4.33, 0.192 | 0.0327 (0.0193), 1/201 | 2.85 [2.53, 3.20] | 2.92 / 3.75 |
| #10²¹+1 – #10²¹+10⁴ | 1.4418e20 | 9,999 / 3,333 | 10.26 → 10 | 0.0120, 0.71 | 0.67 | 4.30, 0.191 | 0.0271 (0.0207), 1/201 | 2.90 [2.56, 3.26] | 2.92 / 3.72 |
| #10²²+1 – #10²²+10⁴ | 1.3709e21 | 9,999 / 3,333 | 10.78 → 11 | 0.0150, 0.39 | 0.40 | 4.38, 0.189 | 0.0339 (0.0209), 1/201 | 3.05 [2.75, 3.43] | 2.92 / 3.78 |

1/201 = 0.00498 is a Monte Carlo p with 0 of 200 exceedances; the one-sided 95% upper bound on the
tail probability is **0.01487**, so even nominally this is not a certified p < 0.01. † √n·D null
transferred from n = 3,333 (unvalidated). Marginal composite scores, Planck − Gaudin: −166.1, −38.2,
−27.6, −30.1 (not used).

Reading the table (all nominal):
- **Planck.** Fitted-parameter KS with refitting in each of 200 iid replicates at the thinned size;
  the observed D exceeds every replicate. The fixed-CDF p-values (recorded as `INVALID`) were
  7.7e-16, 1.5e-3, 1.5e-2 and 9.3e-4: refitting matters (at 10²¹ the fixed-CDF test gives 0.015).
- **GUE baseline.** The high blocks are not rejected by the Gaudin law (0.22, 0.71, 0.39) or CUE(N_eff)
  (0.60, 0.67, 0.40): "not rejected at this size", not equality. The low block is rejected by both.
- **Structural statistic.** Conditional power-law MLE of the CDF exponent on the pre-declared
  (0, 0.30], 95% moving-block bootstrap CI (blocks of 100, 2,000 replicates). High-block CIs contain
  Gaudin 2.92 and exclude Planck's a (4.30–4.38) and its implied value (3.72–3.78). The low-block CI
  [2.92, 3.17] excludes Planck and only just the Gaudin value 2.916.

**Sanity addendum (r6.2, `C1H/lane_check_v2_sanity.py` → `.json`, 91 s, seed 20260929; exploratory,
devices not validated).** It demonstrates the two devices §2c now requires. (1) Copula-preserving
refit null (data ranks, fitted Planck marginal, moving blocks of 100, 400 refits, actual thinned
size): 0 exceedances in every block, p_MC = 1/401, 95% upper bound 0.0075. The null maxima (0.0069,
0.0196, 0.0255, 0.0219) sit closer to the observed D than the iid maxima did, most at 10²¹ (0.0271),
which is why dependence must be calibrated. (2) Joint block bootstrap of measured − Planck-implied
exponent with refitting (1,000 replicates, 99.5% CI): −1.12 [−1.34, −0.94], −0.90 [−1.45, −0.36],
−0.83 [−1.34, −0.28], −0.74 [−1.26, −0.21]; all exclude 0.

**Exploratory outcome.** On the three high blocks the Planck shape is rejected nominally by both the
KS and the exponent difference, and the GUE descriptions are not. Read as exploration, the
resemblance does not survive. Formally the blocks have 9,999 gaps, below H0's declared 10,000 (not
lowered retrospectively), the spec is retrospective, the kill rule has no overall α and the p-values
are nominal, so H0 is `inconclusive`, recorded as an informative negative, not `killed`. The low
block rejects every model tested; whether that is the finite-height correction of Bogomolny et al.
is **not tested here**.

**Card H1:** "ζ gap statistics sit in the β = 2 universality class shared by quantum-chaotic and
horizon models." Status (exploratory) `baseline_explained`: the GUE baseline reproduces it by
construction, and its novelty is **known** (Montgomery; Odlyzko; Berry–Keating; SYK/black-hole
random-matrix literature). It is owner-originated and unblinded, and its data are the same exploratory blocks. It
is **excluded from GO2**, is not a survivor, and is not handed off. Proposed atlas outcome (pending
Q5): H0 `inconclusive` with the limitation "exploratory, nominal p-values; fitted Planck law
rejected on three 9,999-gap blocks, below the declared size"; H1 `completed` with "explained by the GUE baseline;
known in literature".

**Lessons → rules.** Stage 1 alone misled (small sample, low height, flexible family): §2c rule 2.
The Wigner surmise is not the accepted baseline: rule 3. Fixed-CDF p-values after fitting and
dependent gaps are not calibrated: rule 4. A kill rule needs one overall α: rule 5a. An omnibus fit hid a
structural contradiction, and the right comparison is Planck's CDF exponent `a` with the measured
CDF exponent: rule 5. KS and likelihood can rank models differently: one primary statistic, declared
first (§2b). v1 called zero indices "heights": labels are checked against source headers. The
resemblance mixed two objects (a Hawking spectrum is Planck in emitted energy, not in level
spacing): `resemblance_target` must state its mapping.

---

## 4. Observers

| Observer | What it sees | Protocol | Counts toward |
|---|---|---|---|
| **O-DS**: DeepSeek V4.1 Flash vision | `png_blinded` only | WP-3 two-call protocol through the P1 ledger: identical requests, temperature 0, no chain of thought, JSON cards only, raw bytes retained, retries ≤ 2 (frozen, §5). Two calls that disagree is an instability signal. Agreement verifies nothing | GO1, GO2 |
| **O-M2**: second model observer | `png_blinded` only, fresh context with no atlas/lab text | same card prompt. A different model family (V4-Pro is refused for images per WP-3), chosen by the owner (Q2). An in-session Claude agent that has read the atlas is **not** eligible | GO1, GO2 |
| **O-H**: owner (human co-observer) | full pages, captions, deep links | cards entered with `python3 -m mve.observer card new` (WO-2). First-class input | GO1, GO3, GO4; GO2 only in a separately blinded session (Q6) |

**Routing (Jev).** `Q-card-lane` (lane list plus `none`) and `Q-card-ask` (`ai_check`, `human`,
`discard`) join the openJev catalogue (r5 §5), `disabled` until the r5 label floors are met; a human
routes every card until then. Labels: human routing decisions 1.0, manager judgments 0.5. Routing is
advice only. The Jev-harness/dream router is not called or edited; MVE runs its own `mve/classifier/`.

**Calibration link to track E.** Each model observer's E-track receipts (G1 precision, per-predicate
FPR upper bound) are cited from its cards as `observer_reliability`. GO2 is computed per observer.

---

## 5. The pareidolia null (core metric)

**Question:** do observers produce baseline-exceeding survivors more often from real arithmetic
visuals than from baseline-model visuals and from no visual at all?

**Arms** (all frozen before any result is opened; order shuffled with a recorded seed, opaque ids,
PNG metadata stripped and re-encoded, since HMAC names alone do not blind, r5 §9):

| Arm | What the observer gets | Role |
|---|---|---|
| **Real** | V blinded views of the cluster's discovery block D_c | numerator |
| **Null twin** | same module, params and crop, rendered from a baseline sample seeded per cluster; checks run on baseline data | false survival of observer + check together |
| **Image-free** | no image. A frozen library of S generic cards per family (e.g. "the gaps deviate from the declared baseline"), one per slot, checked on D_c → R_c | how often checks alone "find" something in real data; same slot budget |
| **Shuffled image** | V views of a **donor block** (same stratum, used by no cluster); the cards are checked on D_c → R_c | ablates matching visual content, same slot budget |
| **Contrast** | contrast clusters: Poisson/GOE spacings, Davenport–Heilbronn, off-line pair injection | sensitivity |

| Family (modules) | Null twin | Contrast twin |
|---|---|---|
| zero spacings (05 spectral; field `dyson`, seed 20260926) | GUE / finite-N CUE sample | Poisson, GOE; off-line pairs |
| primes (03; 11 spirals/Ulam, seed 20260925; space-08 prime sphere) | Cramér random primes; coprime random control | declared per module |
| L-functions / fields (`andreev`, RHVF p1–p5) | random Dirichlet series | Davenport–Heilbronn |
| xi, heat, others with off-line toggles | — | off-line pair injection |

**Design: a fixed stratified cluster design** (r6.2; replaces the binomial unit of r6.1, since
disjoint blocks do not make iid Bernoulli trials and pooled families share no common distribution).
- **Strata** = lab module × data family (e.g. `spectral × zero spacings`, `ulam × primes`), frozen
  in `DEPS.lock` before any run.
- **Clusters** = source blocks. Cluster c is a pair (discovery block D_c, replication block R_c) of
  disjoint data from one stratum, drawn by a seeded rule from the stratum's frozen block list (e.g.
  consecutive non-overlapping zero-index ranges, alternately D and R). Donor blocks for the shuffled
  arm come from the same list. No block serves twice. Development blocks (prompt and check design)
  are a separate list and never become clusters.
- **Fixed opportunities.** Per (cluster, arm, observer): V views, C card slots per view, exactly one
  check opportunity per slot (frozen family→check mapping; stage 1 on D_c, stage 2 on R_c), so
  S = V·C slots in **every** arm. Frozen: V = 2, C = 3, S = 6 (pilot: V = 1, S = 3). ≤ 2 transport
  retries, which never add slots. No optional stopping, topping-up or re-drawing.
- **Allocation.** Every cluster receives all four arms (paired design). One recorded seed fixes the
  D/R assignment, the donor map, the baseline seeds and the call order; each call is a fresh context.
- **Outcome.** y_{c,a} = baseline-exceeding survivors / S. Empty, malformed, refused, `not_checkable`
  and `inconclusive` slots count 0. d_{c,k} = y_{c,real} − y_{c,k} for control arm k.
- **Test.** For each k ∈ {null twin, image-free, shuffled}, a one-sided **exact sign-flip permutation
  test** of T_k = Σ_c d_{c,k} (all 2^K patterns for K ≤ 20, else 10⁵ random flips with the Monte
  Carlo interval reported), α = 0.05 per comparison. **GO2 needs all three** (intersection–union:
  the global null is controlled at 5% despite the shared real arm) **plus the contrast floor**:
  contrast clusters detected in ≥ 8 of 10 at scale. One detection is weak protection.
- **Assumptions, stated, not proven.** A1: clusters are independent (disjoint blocks and donors,
  independent seeds, fresh-context calls). A2: under H0_k the within-cluster pair (y_real, y_k) is
  exchangeable, so d_{c,k} is symmetric about 0. The seed randomises order and donors, not content,
  so A2 is an assumption for the null-twin and image-free arms. Clusters may differ in distribution
  across strata and heights; the sign-flip test needs only per-cluster symmetry. Results are also
  reported per stratum.
- **Minimum size and detectable effect.** A GO2 decision needs K ≥ 20 clusters over ≥ 2 strata. The
  smallest attainable p is 2^−K′ (K′ = clusters with d ≠ 0), so K′ ≥ 5 is needed to reject at all.
  With equal-size differences the test is the sign test: it rejects only if ≥ 9 of 10, ≥ 15 of 20
  or ≥ 26 of 40 non-zero clusters favour the real arm. If each cluster (no ties) favours real with
  probability q, power is 0.38 (K = 10) and 0.80 (K = 20) at q = 0.8; at q = 0.7 it is 0.42 (K = 20)
  and 0.81 (K = 40). These are single-comparison, equal-magnitude, independent, no-tie illustrations:
  twenty clusters do not guarantee 80% overall GO2 power (all three comparisons must reject), and
  weaker effects have lower power. For unequal magnitudes or K > 20 the sign-flip p-value is computed
  by Monte Carlo over 2^K sign vectors as (1 + r)/(B + 1), B ≥ 10,000, with its one-sided 95% upper
  bound reported. A GO2 superiority conclusion is conditional on A1/A2: rejecting the symmetry null
  is not an assumption-free test of a non-positive mean lift.
- **Descriptive only.** Clopper–Pearson intervals on pooled slot proportions per arm and stratum are
  reported for description and labelled nominal: clustering prevents guaranteed binomial coverage. They do not decide GO2 (r6.1's 7/10, 8/20, 8/40, 9/100 were binomial
  rejection thresholds and are retired as decision rules).

**Pilot (WO-6): descriptive only.** K = 10 clusters (2 strata × 5), V = 1, S = 3, plus 4 contrast
clusters. The sign-flip p-values are computed and reported, but the pilot cannot pass GO2 (K < 20).

A correct observer can legitimately fail GO2. If real data match the baseline (as spacings match
GUE), real cards are `baseline_explained` or killed, as control cards are. GO2 is not impossible to
pass under a correctly matched null; it passes only when observation adds survivors beyond the
baseline, the checks alone and pictures without matching content.

---

## 6. Gates GO1–GO4

Common rules as r5 §8: freeze prompts, crops, check library version, baselines, replication
partitions, strata, clusters, V/C/S, retries, check mapping, donor map, seeds and α before opening results; report
counts and 95% intervals; keep abstentions and malformed output in denominators. An underpowered run
is **inconclusive, not a pass**.

| Gate | Test and pass rule | Null / baseline |
|---|---|---|
| **GO1 Card well-formedness and checkability** | Per observer. **Denominator** = every card slot requested: (visual, observer) pairs × the frozen card limit actually requested, with each refusal, empty reply, malformed JSON or transport failure after retries counting as one failed slot. (1) ≥ 90% of slots hold a card that validates against `oae-mve-hypothesis-card-v1` (all fields of §2b, single observer, hashes match). (2) ≥ 50% of the same denominator are `data_checkable`: an existing check runs them, or a check can be written without changing the claim, as judged by a human. Every validator negative fixture is rejected: unfalsifiable claim, missing kill rule, missing `check_spec`, human/model conflated, hash mismatch, model `adopt`, `hyp_N` as formal support | N/A (structural). Control: a fixed set of vague cards ("looks structured") must all fail validation |
| **GO2 Real-vs-control survival lift** | §5 cluster design: per observer, the exact sign-flip test rejects at one-sided 0.05 for **every** control arm, with K ≥ 20 clusters over ≥ 2 strata and the contrast floor met; owner unblinded cards and baseline-explained cards (e.g. H1) excluded; CP intervals descriptive only | declared: null-twin, image-free and shuffled arms; H0_k: d_{c,k} symmetric about 0 for some k |
| **GO3 Fleet uptake** | Among handed-off survivors: the fraction receiving a lane verdict other than `technical_failure` within N days of relay (N set by the owner before the first relay, Q3) is ≥ 0.5, with n ≥ 5 hand-offs, else inconclusive; median latency reported | N/A (operational); it measures the contract, not truth |
| **GO4 Absence from a searched corpus** | Survivors are searched against the atlas graph (`EA` export), lab snapshot summaries, `tao_ideas.json`, `atlas_literature` and the literature index. **The search counts only if it retrieves every planted known claim** (≥ 5 planted cards, e.g. "ζ gaps are GUE-distributed" must hit Montgomery/Odlyzko). Pass: ≥ 1 survivor `absent_from_searched_corpus`, confirmed by a human reviewer. This establishes absence from the searched corpus, **not global novelty** | planted-known recall must be 100%, else `not established` |

GO1–GO4 do not replace G0–G6. SUMMARY gains a track-O table with the same columns.

---

## 7. Work packets WO-1 … WO-6

Conventions as r5 §11: tests first, ≥ 80% coverage, no network in tests, `python3`, ≤ 800-line files,
immutable records, one branch per packet from `mve/integration`, and Opus review before merge.
Offline-first order: **WO-2 → WO-3 → WO-1 → WO-5 → WO-4 (offline) → [pre-dispatch conditions + owner
go] → WO-4 live → WO-6.**

| WP | Deliverable | Acceptance | Owner go? |
|---|---|---|---|
| **WO-1 Snapshot adapter** | `mve/observer/snapshots.py`: reads `EA/inputs/lab_snapshots.json` and committed PNGs by path; captures only from a `git archive` of pinned AT/ZE HEADs into `mve/observer/snapshots/`; blinded crops (caption- and title-free, metadata stripped, re-encoded); manifest per §2a with source blocks and partitions; per-module table of control-only twins | Manifest validates; hashes reproduce. **Isolation:** capture runs against the archive copy with AT/ZE paths not writable by the process (a test asserts a write attempt fails), and a before/after sha256 tree of AT/ZE **including ignored files** (`git status --ignored` plus a full file hash list) is unchanged. **Leakage:** OCR every blinded PNG for withheld strings, plus a PNG chunk/EXIF dump that must be empty of text, plus a test that planted caption text in a fixture is caught; OCR alone is not accepted as proof. ≥ 10 real + 10 null-twin blocks identified, or the shortfall stated | no (local only) |
| **WO-2 Card schema + validator** | `schemas/mve_hypothesis_card.json` (v1), `mve/observer/card.py` (validation, content hash over all spec fields incl. `check_spec`, lifecycle with `frozen` and `preliminary`, transitive invalidation via `mve/graph.py`, hand-off eligibility), `mve/observer/__main__.py card new`; the class-`hypothesis` changelog stays in this addendum | GO1 negative fixtures rejected; model `adopt` refused; an edit to `prediction` or `primary_statistic` or `check_spec` changes the hash and invalidates checks, judgments and adoption; a `hyp_N` rejected as support on each formalisation path; H0 and H1 fixtures carry the real Odlyzko sha256s, script and receipt sha256s and machine-testable kill rules | no |
| **WO-3 Data-check library** | `mve/observer/checks/spacing.py`: Gaudin GUE law, finite-N CUE with N_eff (Λ), Wigner (secondary), Planck family with analytic normaliser, dependence-preserving refit calibration at actual n (§2c rule 4) with its size check, joint bootstrap of the exponent difference, one kill rule with overall α; the two-stage runner enforcing §2c; receipts | **Regression fixture: `C1H/lane_check_v2.json`** (not v1). It certifies reproduction of code, **not inference**: its p-values stay `nominal` and the receipt `inferential: false`. Recomputed with the same spec and seed: exponents and CIs ±0.02, fitted a, T ±0.01, Monte Carlo exceedance counts equal, block labels, heights and N_eff exact to 4 digits; v1 is history only. Inferential use needs the §2c rule 4 devices, validated by a size check on a known dependent null at the declared α. Stage 1 alone returns `preliminary`; tests use small committed extracts; Odlyzko files read by sha256 pinned in `DEPS.lock`; prime checks follow as a second fixture | no |
| **WO-4 Observer runner** | `mve/observer/run.py`: the §5 cluster design (strata, D/R pairs, donors, fixed slots), allocation seed, blinded delivery, card prompt, O-DS through the WP-3 adapter and P1 ledger, O-M2 adapter, O-H intake; offline `FakeTransport` mode first | Offline: replay fixtures produce cards; the ledger reserves per call at worst-case output × (1 + retries); malformed/refusal recorded as GO1 slots; no hosted call possible without `--live` plus an owner-go stamp and the pre-dispatch conditions of §8, mirroring the WP-0b CLI gate | **yes, for any hosted call** |
| **WO-5 Fleet/atlas contracts + outbox writers** | `mve/observer/outbox.py`: exchange submission writer (§2d) and result-bundle writer (§2e); validation against `EA/schema/result.schema.json` read by path (sha pinned) and against the adapter's rules | Writers only under `mve/observer/outbox/`; H0/H1 bundles validate; `technical_failure` held; round 2 supersedes round 1 by `work_id`; relay refused while any pre-relay dependency of §2d is unrecorded | no; relay per Q4 after §2d |
| **WO-6 Pilot report** | 10 clusters (2 strata × 5) × 4 arms, V = 1, S = 3, plus 4 contrast clusters, × O-DS and O-M2; descriptive only; owner cards in their own stratum; GO1–GO4 table in SUMMARY with nulls and counts | Report deterministic given HEAD; spend reconciled in the aggregate ledger; GO2 reported as not decidable (K < 20) | **yes** (hosted calls) |

**Pilot cost.** WP-0b measured 236 input tokens and USD 0.000268 for one call on a 288×288 PNG. That
is the only **known exposure** on record, not a reconciled campaign total: SUMMARY reports the
campaign snapshot absent and the remaining budget unknown. The pilot needs 34 images (10 real, 10
null twin, 10 donor, 4 contrast) × 3 calls = 102 calls plus retries (the image-free arm makes none). WO-4 re-estimates tokens per image
offline and reserves **worst-case** output × (1 + 2 retries) per call. The hard P1 reservation ceiling
is **USD 0.25**; if the worst case does not fit, arm sizes shrink before the run, never during it.
The P1 cap (USD 8) and the aggregate cap (USD 20) are unchanged.

---

## 8. Budget and safety

- **Pre-dispatch conditions (all required before any live call, checked by the WO-4 gate):**
  (1) the WP-9a aggregate ledger is reconciled: a campaign snapshot exists, known spend is
  reconciled against the provider's usage records, and the remaining budget is a stated number;
  (2) O-DS and O-M2 prices, or O-M2's quota terms, are verified from the provider at dispatch date
  (the r5 verified-price refusal applies to both); (3) the worst-case reservation of §7 fits the
  pilot cap; (4) the owner's go names the packet and the Opus-reviewed HEAD.
- **Ledger.** WP-9a and the WP-0b/WP-3 guards are reused as they are (verified-price refusal,
  off-peak window, reservation before dispatch, one-shot ids, no zero-billing). All O-track hosted
  calls are **phase P1**; O-M2 is accounted in USD or quota (r5 A7).
- **No edits to other lanes' repositories.** MVE does not edit AT, ZE, RHVF, `rh-lane-r`, the Jev
  harness, or the shared exchange (pending Q4). Outputs are files under `mve/observer/outbox/`.
  By-path reads are recorded in `DEPS.lock`.
- **Data checks** are local and unmetered, and download nothing. The Odlyzko cache is already on
  disk. A missing dataset makes the card `not_checkable`; nothing is fetched automatically.
- **Separate sessions.** Before WO-4 or WO-6 run, check for live peer sessions on the atlas and fleet
  lanes. One runner per ledger.

---

## 9. Open questions for the owner

Questions 3–5 are **pre-relay dependencies** (§2d): no submission leaves the outbox until they are
answered and recorded.

1. **First modules.** Proposal: 05 spectral and field `dyson` (spacings), 11 Ulam and space-08
   prime sphere (primes). All have seeded controls. Heat 04 and the other control-less modules wait.
2. **Second model observer.** Which vision model, billed in USD or quota? It must be a different
   family from DeepSeek and run in a fresh context. Its price or quota is verified before dispatch.
3. **Fleet ownership and GO3 timing.** Who turns an adopted card into a lane (the fleet operator,
   Lane R, or the owner)? What is N for GO3, and does the clock start at relay?
4. **Exchange writes.** May MVE write submissions directly into the review-exchange, or does the
   Opus relayer copy them from the outbox?
5. **Atlas contract.** Does the atlas owner confirm the status mapping (especially
   `refuted_candidate` and the baseline-explained row) and the `technical_failure` defect in
   `services.py:229`?
6. **RHVF blinded panels and owner blinding.** May Lane R's p1–p5 panels be used as O-track inputs?
   Will the owner also do a short blinded session so that human cards can enter GO2?

---

## What stays from r5

Frozen r5 text, schema v5, predicate registry v1, errata E1/E1a; evidence classes and authorisation
by proposition equality (only a human `adopt` creates an assumption; `hypothesis` joins as
non-authorising); G0–G6 with their nulls and "not established" status; WP-0b/WP-9a/WP-3 guards,
P0/P1/P2 caps, D1–D6; openJev scope, label weights, family splits and audit sample; the r5 §9
honesty protocol (declared null or N/A, isolation, controls every wave, naming the check performed).

## Risks

| Risk | Mitigation |
|---|---|
| **Pareidolia**: observers see patterns in noise | null-twin, image-free and shuffled-image arms; contrast sensitivity floor; two-stage checks; stage 1 never gives a verdict |
| **Generic "reject the null" cards** produce lift whenever real data differ from a mis-chosen null | image-free fixed-card arm; baseline = accepted model at the right scale; `baseline_explained` is not survival |
| **Novelty illusion**: a "discovery" is textbook (as H1 was) | GO4 planted-known recall must be 100%; a human confirms each `absent_from_searched_corpus` |
| **Answer leakage** through captions, titles, legends, deep links, file names, PNG metadata or control colours | caption-free, title-cropped, metadata-stripped, re-encoded PNGs with opaque ids; WO-1 OCR + chunk dump + planted-text test; control-only twins with the real palette; owner cards are an unblinded stratum |
| **Miscalibrated statistics** (fitted-parameter KS, dependent gaps, wrong labels) | §2c rules 4, 5, 5a and 7; v2 receipt is a regression fixture only (`inferential: false`); labels checked against source headers |
| **Reuse of discovery data** as "replication" | development/replication partitions fixed in `DEPS.lock` before any run; stage 2 reads only replication blocks |
| **Multiple testing; non-iid units** across cards, views and arms | cluster = source block with fixed S slots in every arm; exact sign-flip test over clusters; frozen retries, check mapping, donors and seeds; intersection–union over the three control arms; CP descriptive only |
| **Ownership collisions; contract drift** | outbox-only writes; isolation tests; pre-relay dependencies; relay by a named session; schema and script sha256 pinned in `DEPS.lock`, WO-5 fails on change |
| **Budget overstatement** | known exposure only until the aggregate ledger is reconciled; worst-case reservation; pre-dispatch conditions |
| **Owner intuition dismissed** because GO2 fails | GO2 measures model observers; owner cards are tracked in their own stratum; a negative owner card is recorded as informative (as H0) |
