# MVE plan addendum r6: the Observer track (O)

**Date:** 2026-09-28 · **Status:** proposal for Opus review and an Astra verdict; it does not edit
the frozen r5 text (`docs/mve/MVE_PLAN.md`). Where it adds to r5, the addition is named as such.
**Direction (owner, binding):** "The atlas (the lab creates visualization/geometry/topology) is the
input → MVE observes and creates hypotheses/theories/insights as output → RH research fleets
test/verify/create attack lanes → report to the Atlas."

**Reading rule (inherited from r5).** Every capability of an external repository, model or script
is UNVERIFIED until a packet executes it. The atlas and lab paths below come from a read-only survey
on 2026-09-28. Four points were read directly: the result-bundle schema, the snapshot plan, the
inbox adapter and the handshake script.

Abbreviations: `AT` = `~/Developer/Opensens/worktrees/oae-rh-atlas-p0-20260924` (branch
`claude/rh-atlas-p0-20260924`, live v277); `ZE` = `~/Developer/Opensens/worktrees/zeta-explorer-main`;
`EA` = `AT/data/riemann/evidence_atlas`; `RHVF` = `~/Developer/Opensens/rh-visual-fields`.

---

## 0. Summary

MVE gains a second track. The **Observer track (O)** looks at atlas lab visuals, as the owner does,
and writes **hypothesis cards**. Each card is a testable claim with a kill criterion. A cheap data
check runs on the lab's source data, never on the pixels. Cards that survive go to the RH fleets as
attack-lane proposals, and lane outcomes go back to the atlas as result bundles. The **Euclidean
track (E)** is everything r5 built. It becomes the **observer-calibration track**: exact synthetic
truth measures how reliable each observer is. The central metric of track O is a **pareidolia
null**: blinded observers see real visuals mixed with control twins, and the gate is the surviving-card
rate on real visuals minus the rate on controls, with a declared one-sided bound. MVE is allowed to
be wrong. Its product is testable hypotheses, not answers.

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
`docs/mve/reports/SUMMARY.md` on `mve/integration`. Track O adds gates GO1–GO4 (§5). It changes no
E-track threshold.

**Scope limits.** MVE does not edit the atlas, the lab, Lane R (`rh-lane-r`, read only) or the
Jev-harness/dream lane. It integrates only through the contracts in §2. MVE does not create fleet
lanes. It proposes them. A card never authorises a formal proposition (§2b).

**Why E stays useful.** A model observer's cards are worth only as much as its perception. E is the
only place where perception is scored against exact truth. Until G1 is established, every O-track
card carries `observer_reliability: not_established` and is reported that way.

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

Sources, in the order to try them:
1. Committed snapshots: `EA/inputs/lab_snapshots.json` (`{schema, note, snapshots[]}`; each entry
   has `id, module, title, params, summary, informs, caveat, why.records, attack_ids,
   capture.params_sha256, capture.png.{path, sha256}`), captured by
   `python3 -m rh_evidence.labs_snapshots capture|restore [--only ID]` (headless Chrome, PNG sha256
   pinned, ≤ 1% pixel tolerance).
2. `ZE/scripts/astra_p34_capture.py` (maxwell, dyson, andreev, continuation, bec; control off and on).
3. The bridge `AT/rh_evidence/labs/atlas-bridge.js` (`set_state` / `snapshot`). It has no PNG script
   yet. Writing one is the atlas owner's work. MVE may request it.

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
| `data_ref` | `{path, sha256, generator, seed}` for the data drawn (e.g. zeros file, prime range, control seed 20260925 / 20260926) |
| `control` | `{kind: null_twin \| contrast_twin \| none, twin_snapshot_id}` (§4) |
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

**Addition to r5 §4a.** A sixth class, `hypotheses` (`hyp_N`), is added. It **never authorises** a
formal proposition, an assumption or a derivation. It may be cited only by data checks, judgments and
hand-offs. A card enters formalization only if a human creates a `txt_N` problem source from it and
adopts it through the normal E-track path. The E-track observation schema v5 is unchanged. Cards
get their own schema, `schemas/mve_hypothesis_card.json` (`oae-mve-hypothesis-card-v1`), validated
by `mve/observer/card.py`. It reuses `mve/graph.py` for `depends_on` and transitive invalidation: if
a snapshot hash changes, every card citing it is invalidated.

| Field | Content and rule |
|---|---|
| `card_id`, `revision`, `content_hash` | identity over {claim, testable_form, kill_criterion, source snapshots}; an edit to any of them is a new revision |
| `claim` | one sentence about the displayed object |
| `testable_form` | the statistic or construction, the data it runs on, the baseline it is compared with, the direction of the prediction |
| `prediction` | the value or sign expected **at the replication scale** |
| `kill_criterion` | a pre-registered numeric rule; "unfalsifiable" fails validation |
| `primary_statistic` | exactly one, declared before the check runs; the others are secondary |
| `sources` | ≥ 1 `{snapshot_id, png_sha256, data_sha256}` |
| `observer` | `{id, kind: human \| model, model_id?, prompt_sha?, call_ids?, blinded: bool}`. **One originating observer per card.** Human and model are never merged. Another observer's agreement is a judgment, not a co-author |
| `resemblance_target` | optional: what it looks like (e.g. "Hawking/Planck spectrum"), plus the mapping claimed |
| `novelty` | `{status: unchecked \| known \| partial \| absent, queries, index_shas, planted_control_hit}` (GO4) |
| `suggested_lane` | free text plus a Q-card-lane label once active |
| `prior_plausibility` | `{value: low \| medium \| high, by: observer_id}`. It is a judgment and never a gate input |
| `observer_reliability` | a reference to the observer's E-track calibration receipt, or `not_established` |
| `status` | `draft → well_formed → checked:{killed, survived, inconclusive, not_checkable} → adopted → handed_off → lane_verdict:{…} → reported` |
| `judgments` | as r5 (`confirm/reject/unsure/adopt/decline`). **Only a human `adopt` moves a card to `adopted`**. Model judgments are recorded with weight 0.5 and never authorise |

### 2c. C3: the cheap data check

A data check runs on the snapshot's **source data**, never on pixels. Its code lives in
`mve/observer/checks/` and is local and free.

1. **Freeze first.** The check spec (statistic, baseline models, parameter counts, α, replication
   scale, kill rule) is hashed into the card before any data is read at the replication scale.
2. **Two stages, always.** Stage 1 uses the data behind the snapshot. Stage 2 is a **replication**:
   a larger sample, a greater height, or new seeds, chosen in the spec. **A stage-1 result alone
   yields no verdict.** It can at most make the card `preliminary`.
3. **Baselines are explicit and fair.** Compare against the accepted model at the right scale (for
   spacings: the exact limit or finite-N CUE with Bogomolny–Keating effective N, not only the
   2×2 Wigner surmise), and penalise extra parameters (report AIC and BIC).
4. **A structural statistic is required** beside any omnibus fit (e.g. the small-gap exponent for
   spacings, residue-class counts for primes). An omnibus p-value alone can hide a structural
   contradiction (§3).
5. **Specificity.** The claimed pattern must fail to appear in samples from the baseline model. A
   pattern that the baseline reproduces is `known` or `explained_by_baseline`, not a survivor.
6. **Outcomes:** `survived` (the prediction holds at replication, the kill rule does not fire, and
   specificity passes), `killed`, `inconclusive` (underpowered or the stages disagree), or
   `not_checkable`. The receipt records script sha, data sha, seeds and runtime.

### 2d. C4: fleet hand-off (attack-lane proposal)

Only an `adopted` card is handed off. The hand-off is a submission record in the shape that
`rh_lane_handshake.py` already reads (found at
`~/Developer/Opensens/worktrees/oae-rh-graph-20260903/scripts/rh_lane_handshake.py`; exchange root
`~/Developer/Opensens/Opensens Academic Explorer/.llm-wiki/activity/review-exchange/{submissions,verdicts}/`).
The record keys are the ones present on live records: `work_id, round, review_id, submitter: "mve",
reviewer: <fleet lane>, packet_type: "attack_lane_proposal", summary, caveats, evidence,
report_path, report_sha256, changed_files: [], commit, schema_version, submitted_at, supersedes,
relayed_by, packet_hash`. The report is the card plus its check receipt. `work_id =
mve-card-<card_id>`, and a revised card is a higher `round`, never a new id.

MVE writes submissions only to `mve/observer/outbox/exchange/`. Copying a submission into the
shared exchange is done by the relayer (Opus reviewer session) after review, unless the owner allows
MVE to write there directly (Q4). The fleet side decides whether to open a lane. Lane creation
belongs to the fleet owner (Q3).

### 2e. C5: outcome back to the atlas

A lane outcome becomes a result bundle against `EA/schema/result.schema.json` (required fields:
`runId, taskId, statement, method, reproduce, schemaVersion "1.0", status, assumptions, sources,
artifacts, results, counterexamples, limitations, proposedBlockerChanges, resources, review{state,
reviewerId, reviewedRevision}`). Facts from `AT/rh_evidence/adapters/result_bundle.py`:
- `reproduce` is recorded and never executed.
- Artifact paths must be relative and exist under the atlas project root, with matching sha256.
- A bundle may not arrive with review state `accepted`/`rejected`.
- `runId` must be new, because bundles are immutable.

MVE therefore writes bundle plus artifacts to `mve/observer/outbox/atlas/`. The **atlas owner**
copies them to `EA/inbox/` and a path under AT, runs `python3 -m rh_evidence.cli ingest-inbox`,
and builds with `atlas-build` in a window granted by Lane R. Visualising outcomes in the lab (for
example a snapshot whose `why.records` cite the `run::` node) is the atlas owner's work.

Proposed status mapping (to be confirmed with the atlas owner, Q5):

| Card / lane outcome | `status` | Notes |
|---|---|---|
| card survived, handed off, no lane result yet | `proposal` | statement = the card's claim; limitations list the stage-1/2 caveats |
| lane or data check refutes the card | `refuted_candidate` | read here as "the candidate claim was refuted". Confirm this is the atlas meaning |
| lane supports the claim | `completed` | `limitations` must carry the novelty status (e.g. "known in literature") |
| underpowered or disagreeing stages | `inconclusive` | |
| lane could not run | `technical_failure` | see the defect below |

**Contract defect found while reading (for the atlas owner, not fixed by MVE).** The schema's enum
is `technical_failure`, but `AT/rh_evidence/services.py:229` sets `infrastructure_failure` only for
`failed_infrastructure`, `timeout` or `crashed`. A `technical_failure` bundle is therefore staged
with `epistemic = "numerical"` claims instead of `unreviewed`. Until this is fixed, MVE puts
`technical_failure` bundles on hold instead of emitting them.

---

## 3. Worked example: hypothesis card #1 ("Hawking gaps"), owner-observed

**Observation.** On lab 05 (spectral / Hilbert–Pólya: ζ gaps vs a GUE sample vs Poisson), the owner
thought the ζ gap density looked like a Hawking/quantum-radiation spectrum. Observer: `human:owner`,
unblinded (full page).

**Card H0** (as it would be filed):
- claim: normalised ζ-zero gaps follow a Planck-shaped law p(s) ∝ s^a / (e^{s/T} − 1) rather than
  the GUE law.
- testable form: 2-parameter Planck MLE vs Wigner surmise and finite-N CUE; primary statistic
  Δloglik (Planck − Wigner, BIC-penalised); structural statistic: the small-gap CDF exponent
  (GUE ≈ 3, i.e. density ∝ s², β = 2; Planck predicts density ∝ s^{a−1}).
- kill criterion: at replication (≥ 10⁴ gaps at height ≥ 10¹²), Planck KS p < 0.01, **or**
  penalised Δloglik < 0, **or** a measured exponent inconsistent with a − 1.
- resemblance target: Hawking/Planck spectrum. Suggested lane: spacing statistics (Lane R-style).

**Stage 1** (`r6/hawking_check.py`, output `r6/hawking_check.json`). Zeros 1–2000 computed with
mpmath, first 20 gaps dropped, 1,979 gaps. Planck fit a = 5.48, T = 0.155. Δloglik = +12.5 over the
Wigner surmise, which exceeds the BIC penalty for two parameters (ln 1979 ≈ 7.6). KS p: Wigner
0.0024, Planck 0.57. Read alone, this looked like support.

**Stage 2, the decisive lane** (`r6/lane_check.py`, output `r6/lane_check.json`; Odlyzko tables in
`~/Developer/Opensens/cache/odlyzko_zeros`, rng seed 2026):

| Set | Gaps | BK N_eff | CDF small-gap exp. | KS p Wigner | KS p CUE N=200 | KS p CUE N_eff | KS p Planck | Planck a−1 | Δloglik Planck−Wigner |
|---|---|---|---|---|---|---|---|---|---|
| zeros 1,001–100,000 | 98,999 | 2.53 | 2.995 | 7.7e-6 | 1.6e-25 | 2.4e-15 | 7.9e-4 | 3.99 | −18.5 |
| height 10¹² | 9,999 | 7.07 | 3.207 | 0.90 | 0.70 | 0.82 | 3.1e-7 | 3.38 | −92.4 |
| height 10²¹ | 9,999 | 12.87 | 2.948 | 0.59 | 0.65 | 0.64 | 7.0e-7 | 3.32 | −88.2 |
| height 10²² | 9,999 | 13.52 | 3.129 | 0.65 | 0.60 | 0.60 | 2.6e-8 | 3.42 | −85.1 |

**Verdict.** H0 is **killed**. At every large height the GUE descriptions are not rejected and the
fitted Planck law is. The small-gap exponent is ≈ 3 (β = 2) at every height, but Planck needs a
density ∝ s^{3.3–4}. The low-zero set rejects every model, including finite-N_eff CUE. This is a
finite-height effect on 99k gaps, and there the Wigner surmise still leads Planck by 18.5.

**Refined card H1:** "ζ gap statistics sit in the β = 2 universality class shared by quantum-chaotic
and horizon models (Berry–Keating xp; random-matrix statistics of black holes and SYK)." It is
supported, and its novelty status is **known**: Montgomery's pair correlation, Odlyzko's numerics,
Berry–Keating, and the SYK/black-hole random-matrix literature. It counts as a survivor in GO2 and
as not novel in GO4. It is not handed off as a new lane. Atlas outcome: H0 `refuted_candidate`, H1
`completed` with the limitation "known in literature" (pending Q5).

**Why stage 1 misled, and what the contract now requires.**
1. *Small sample at low height.* Near height 10³ the effective matrix size is small. Finite-height
   corrections move the gap law away from its limit, and a flexible two-parameter family absorbs
   them. Hence §2c rule 2: no verdict without the higher-height or larger-sample replication.
2. *Unfair baseline.* The Wigner surmise is a 2×2 approximation, not the exact limit or finite-N CUE.
   Hence rule 3.
3. *An omnibus test hid a structural contradiction.* The stage-1 fit had density exponent a − 1 ≈ 4.5,
   which contradicts the measured s² repulsion. Hence rule 4.
4. *KS and likelihood can rank models differently* (low zeros: KS favours Planck and likelihood
   favours Wigner). Hence one primary statistic, declared first.
5. *The resemblance mixed two objects.* A Hawking spectrum is Planck in emitted energy, not in level
   spacing. The shape resemblance (zero at 0, one hump, fast tail) holds at histogram resolution
   only. `resemblance_target` must state the mapping it claims.

Honesty notes: KS p 0.59–0.90 at 10⁴ gaps means "not rejected at this size", not equality. The
surmise and the exact GUE law differ slightly. This example is also the first fixture of WO-3.

---

## 4. Observers

| Observer | What it sees | Protocol | Counts toward |
|---|---|---|---|
| **O-DS**: DeepSeek V4.1 Flash vision | `png_blinded` only | WP-3 two-call protocol through the P1 ledger: identical requests, temperature 0, no chain of thought, JSON cards only, raw bytes retained, retries ≤ 2. Two calls that disagree is an instability signal. Agreement verifies nothing | GO1, GO2 |
| **O-M2**: second model observer | `png_blinded` only, fresh context with no atlas/lab text | same card prompt. Must be a different model family (V4-Pro is refused for images per WP-3). The candidate is chosen by the owner (Q2). An in-session Claude agent that has read the atlas is **not** eligible | GO1, GO2 |
| **O-H**: owner (human co-observer) | full pages, captions, deep links | cards entered with `python3 -m mve.observer.card new` (WO-2). First-class input | GO1, GO3, GO4; GO2 only in a separately blinded session (Q6) |

**Routing (Jev).** Two workflow questions are added to the openJev catalogue (r5 §5):
- `Q-card-lane` (Choice over the fleet's lane list plus `none`)
- `Q-card-ask` (Choice: `ai_check`, `human`, `discard`)

Both stay `disabled` until the r5 label floors are met, and a human routes every card until then.
Labels come from human routing decisions (weight 1.0) and manager judgments (weight 0.5), as §5a
already specifies. Routing is advice only. **Model judgments never authorise. Only a human `adopt`
hands a card off.** The Jev-harness/dream session's router is not called or edited. MVE runs its
own local openJev inference (`mve/classifier/`).

**Calibration link to track E.** Each model observer's E-track receipts (G1 precision, per-predicate
FPR upper bound) are cited from its cards as `observer_reliability`. GO2 stratifies by observer.

---

## 5. The pareidolia null (core metric)

**Question:** do observers produce surviving hypotheses more often from real arithmetic visuals than
from visuals of the declared baseline model?

**Arms.** Each real snapshot is paired 1:1 with a **null twin**: the same module, params and crop,
rendered from a sample of the baseline model. The order is shuffled with a recorded seed, and ids
are opaque. HMAC names alone do not blind (r5 §9), so PNG metadata is stripped and images are
re-encoded.

| Family (modules) | Null twin (baseline sample; GO2) | Contrast twin (positive control; sensitivity) |
|---|---|---|
| zero spacings (05 spectral; field `dyson`, seed 20260926) | GUE / finite-N CUE sample | Poisson, GOE samples; off-line pairs |
| primes (03; 11 spirals/Ulam, seed 20260925; space-08 prime sphere) | Cramér random primes; coprime random control | — (declare per module) |
| L-functions / fields (`andreev`, RHVF p1–p5) | random Dirichlet series | Davenport–Heilbronn (off-line zeros) |
| xi, heat, others with off-line toggles | — | off-line pair injection |

**Survival on a null twin** measures the false-survival rate of observer and check together. Its
source data are baseline draws, so specificity (§2c rule 5) should fail except at rate α.
**Contrast twins** measure sensitivity: an observer that never flags Davenport–Heilbronn's off-line
zeros or Poisson's missing repulsion is blind, and its GO2 result is `uninterpretable` whatever the
lift.

**Unit and statistic.** The unit is (visual, observer). The value is 1 if the visual yields at least
one `survived` card, else 0. Malformed output, refusals, `not_checkable` and `inconclusive` stay in
the denominator as 0. Cards from one module share data, so results are stratified by module and
module-level counts are reported. The rates are p_real and p_ctrl per observer.

**Declared bound (as WP-11a):** L = CP_lower(p_real, one-sided 97.5%) − CP_upper(p_ctrl, one-sided
97.5%), a Bonferroni split that gives a one-sided 95% bound on the lift. **GO2 passes iff L > 0 for
that observer**, and sensitivity on contrast twins is ≥ 1 detection.

Power, stated now so that nobody calls a failure "encouraging". With 20 units per arm and 0 control
survivors, the control upper bound is 0.168, and L > 0 needs ≥ 8/20 real survivors. At 40 per arm it
needs ≥ 8/40, and at 100 per arm ≥ 9/100. The 10 + 10 pilot (WO-6) is **expected to be
inconclusive** unless the effect is very large. That is an acceptable pilot outcome.

A correct observer can legitimately fail GO2. If the real data match the baseline (as spacings match
GUE), real cards die as often as control cards. GO2 measures whether observation adds signal beyond
pareidolia. It does not measure whether the owner's intuition is sound.

---

## 6. Gates GO1–GO4

Common rules as r5 §8: freeze prompts, crops, check library version, baselines, replication scales
and α before opening results; report counts and 95% intervals; keep abstentions and malformed output
in denominators. An underpowered run is **inconclusive, not a pass**.

| Gate | Test and pass rule | Null / baseline |
|---|---|---|
| **GO1 Card well-formedness and checkability** | Two parts, per observer. (1) ≥ 90% of model cards validate against `oae-mve-hypothesis-card-v1` (claim, testable form, prediction, kill criterion, primary statistic, sources with hashes, single observer). (2) ≥ 50% are `data_checkable`: an existing check in `mve/observer/checks/` runs them, or a check can be written without changing the claim, as judged by a human. Every validator negative fixture is rejected: unfalsifiable claim, missing kill rule, human/model conflated, hash mismatch, model `adopt` | N/A (structural). Control: a fixed set of vague cards ("looks structured") must all fail validation |
| **GO2 Real-vs-control survival lift** | §5: L > 0 per observer, with contrast-twin sensitivity ≥ 1; the owner's unblinded cards are excluded | declared: the null-twin arm; H0: p_real ≤ p_ctrl |
| **GO3 Fleet uptake** | Among adopted, handed-off, surviving cards: the fraction receiving a lane verdict other than `technical_failure` within N days (N = 14 proposed, owner sets it) is ≥ 0.5, with n ≥ 5 hand-offs, else inconclusive; median latency reported | N/A (operational); it measures the contract, not truth |
| **GO4 Novelty** | Surviving cards are searched against the atlas graph (`EA` graph export), lab snapshot summaries, `tao_ideas.json`, `atlas_literature` and the literature index. **The search is valid only if it retrieves every planted known claim** (≥ 5 planted cards, e.g. "ζ gaps are GUE-distributed" must hit Montgomery/Odlyzko). This is the rule "absence from the corpus is a cheap novelty test", with a search that could have succeeded. Pass: ≥ 1 surviving card with novelty `absent`, confirmed by a human reviewer; the fraction absent/known/partial is reported | planted-known recall must be 100%, else GO4 is `not established` (search invalid) |

GO1–GO4 do not replace G0–G6. SUMMARY gains a track-O table with the same columns.

---

## 7. Work packets WO-1 … WO-6

Conventions as r5 §11: tests first, ≥ 80% coverage, no network in tests, `python3`, ≤ 800-line files,
immutable records, one branch per packet from `mve/integration`, and Opus review before merge.
Offline-first order: **WO-2 → WO-3 → WO-1 → WO-5 → WO-4 (offline) → [owner go] → WO-4 live → WO-6.**

| WP | Deliverable | Acceptance | Owner go? |
|---|---|---|---|
| **WO-1 Snapshot adapter** | `mve/observer/snapshots.py`: reads `EA/inputs/lab_snapshots.json` and committed PNGs by path; captures new states only from a `git archive` of pinned AT/ZE HEADs into `mve/observer/snapshots/`; produces blinded crops (caption- and title-free, metadata stripped, re-encoded); manifest per §2a; per-module table of which control toggles yield a control-only twin | Manifest validates; hashes reproduce; zero writes under AT/ZE (a test snapshots their `git status` before and after); ≥ 10 real + 10 null-twin pairs identified, or the shortfall stated; a leakage check OCRs every blinded PNG and fails on any withheld string | no (local only) |
| **WO-2 Card schema + validator** | `schemas/mve_hypothesis_card.json` (v1), `mve/observer/card.py` (validation, content hash, lifecycle transitions, dependency invalidation via `mve/graph.py`), `mve/observer/__main__.py card new` for owner entry; an r5 §4a changelog note adding class `hypothesis` (never authorises) | Negative fixtures from GO1 rejected; a model `adopt` refused at the transition; H0 and H1 from §3 validate as fixtures | no |
| **WO-3 Data-check library** | `mve/observer/checks/spacing.py` (Wigner surmise, finite-N CUE, Bogomolny–Keating N_eff, Planck family, penalised likelihood, KS, small-gap exponent, baseline-sample specificity); the two-stage runner enforcing §2c; receipts | **First fixture: the Hawking lane.** Stage 2 reproduces `r6/lane_check.json` (KS p within ±0.05 absolute where > 0.01; exponents ±0.02; Δloglik ±1), reading Odlyzko files by sha256 pinned in `DEPS.lock`; stage 1 alone returns `preliminary`; tests use small committed extracts; prime-family checks follow as a second fixture | no |
| **WO-4 Observer runner** | `mve/observer/run.py`: pairing, shuffle seed, blinded delivery, card prompt, O-DS through the WP-3 adapter and P1 ledger, O-M2 adapter, O-H intake; offline `FakeTransport` mode first | Offline: replay fixtures produce cards, and the ledger reserves per call; malformed/refusal are recorded; no hosted call possible without `--live` plus an owner-go stamp, mirroring the WP-0b CLI gate (owner date, Opus-reviewed HEAD, clean tree) | **yes, for any hosted call** |
| **WO-5 Fleet/atlas contracts + outbox writers** | `mve/observer/outbox.py`: exchange submission writer (§2d) and result-bundle writer (§2e); validation against `EA/schema/result.schema.json` read by path (sha pinned) and against the adapter's rules (relative paths, hashes, no pre-review) | Writers only under `mve/observer/outbox/`; H0/H1 bundles validate; `technical_failure` held until the services defect is resolved; a round-2 card supersedes round 1 by `work_id` | no; relay into the shared exchange per Q4 |
| **WO-6 Pilot report** | 10 real + 10 null-twin visuals, plus ≥ 2 contrast twins, × O-DS and O-M2; owner cards in their own stratum; GO1–GO4 table in SUMMARY with nulls and counts | Report is deterministic given HEAD; spend reconciled in the ledger; GO2 labelled inconclusive if underpowered | **yes** (hosted calls) |

**Pilot cost.** WP-0b measured 236 input tokens and USD 0.000268 per call for a 288×288 PNG. The
pilot is 20 visuals + 2 contrast twins, with two O-DS calls each plus one O-M2 call each, which is
≈ 66 calls. At the measured rate that is about USD 0.02. Lab snapshots are larger than 288×288 and
cards are longer than the probe reply, so WO-4 re-estimates tokens per image offline. The pilot runs
under a hard P1 reservation ceiling of **USD 0.25**, and the actual spend is reported. The P1 cap
(USD 8) and the aggregate cap (USD 20, spent so far USD 0.000268) are unchanged.

---

## 8. Budget and safety

- **Budget and ledger.** The WP-9a aggregate ledger and the WP-0b/WP-3 guards are reused as they
  are: verified-price refusal, off-peak window, reservation before dispatch, one-shot ids, no
  zero-billing. All O-track hosted calls are **phase P1**. O-M2's cost is accounted in USD or quota,
  per r5 A7.
- **Owner go.** No hosted call runs without the owner's go for that packet. The owner-run pattern of
  the WP-0b live probe is the default.
- **No edits to other lanes' repositories.** MVE does not edit AT, ZE, RHVF, `rh-lane-r`, the Jev
  harness, or the shared exchange (the last one pending Q4). Its outputs are files under
  `mve/observer/outbox/`. By-path reads are recorded in `DEPS.lock`.
- **Data checks** are local and unmetered, and download nothing. The Odlyzko cache is already on
  disk. A missing dataset makes the card `not_checkable`; nothing is fetched automatically.
- **Separate sessions.** Before WO-4 or WO-6 run, check for live peer sessions on the atlas and
  fleet lanes. One runner per ledger.

---

## 9. Open questions for the owner

1. **First modules.** Proposal: 05 spectral and field `dyson` (spacings), 11 Ulam and space-08
   prime sphere (primes). All have seeded controls. Heat 04 and the other control-less modules wait.
2. **Second model observer.** Which vision model, billed in USD or quota? It must be a different
   family from DeepSeek and run in a fresh context.
3. **Fleet-side lane creation.** Who turns an adopted card into a lane? (The fleet operator, Lane R,
   or the owner.) What is N for GO3?
4. **Exchange writes.** May MVE write submissions directly into the review-exchange, or does the
   Opus relayer copy them from the outbox?
5. **Atlas contract.** Does the atlas owner confirm the status mapping (especially the meaning of
   `refuted_candidate`) and the `technical_failure` defect in `services.py:229`?
6. **RHVF blinded panels and owner blinding.** May Lane R's p1–p5 panels (with Davenport–Heilbronn
   and random-Dirichlet controls) be used as O-track inputs? Will the owner also do a short blinded
   session so that human cards can enter GO2?

---

## What stays from r5

- Frozen r5 plan text, schema v5, predicate registry v1 and errata E1/E1a.
- Evidence classes and authorisation by proposition equality. Only a human `adopt` creates an
  assumption. Model judges never authorise. `hypothesis` joins the classes as non-authorising.
- Gates G0–G6, their nulls and their "not established" status. Track E continues as calibration.
- WP-0b/WP-9a/WP-3 budget and transport guards, P0/P1/P2 caps, D1–D6 owner decisions.
- openJev routing scope (workflow questions only), label weights, three-way family splits and the
  audit sample.
- The r5 §9 honesty protocol: a declared null or N/A, isolation, controls every wave, and naming the
  check performed.

## Risks

| Risk | Mitigation |
|---|---|
| **Pareidolia**: observers see patterns in noise | GO2 null-twin arm; contrast-twin sensitivity; two-stage checks; stage 1 never gives a verdict |
| **Novelty illusion**: a "discovery" is textbook (as H1 was) | GO4 planted-known recall must be 100% before any `absent` counts; a human confirms each novel card |
| **Answer leakage** through captions, titles, legends, deep links, file names, PNG metadata or control colours | Model observers get only caption-free, title-cropped, metadata-stripped, re-encoded PNGs with opaque ids; the OCR leakage test in WO-1; a control twin must be a control-only render with the real palette. The owner sees full pages, and those cards are an unblinded stratum |
| **Small-sample artefacts** (the Hawking lesson) | §2c: replication scale, fair finite-N baselines, a structural statistic, one primary statistic declared first |
| **Checks on pixels** instead of data | C1 refuses snapshots without hashable source data; checks read `data_ref` only |
| **Multiple testing** across many cards | one primary statistic per card; GO2 counts visuals, not cards; the per-module stratum is reported |
| **Ownership collisions** with the atlas, Lane R and Jev sessions | outbox-only writes; `git status` guard tests; relay by a named session; ask the owner when two lanes claim one step |
| **Contract drift** in the atlas schema or handshake | pin schema and script sha256 in `DEPS.lock`; WO-5 tests fail on hash change |
| **Fleet cost** from too many hand-offs | human `adopt` is the only path; GO3 reports uptake and latency |
| **Owner intuition dismissed** because GO2 fails | GO2 measures model observers; owner cards are tracked in their own stratum, and a killed owner card is recorded as an informative negative (as H0) |
