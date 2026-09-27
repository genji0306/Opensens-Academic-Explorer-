# MVE SUMMARY and gate report

Evidence commit: `ea621a8918e5bb22c5ed53a1d3c30bfb5b09f7d7`

Committed receipts only. No new model, Lean, corpus, benchmark or ingest run. No P6 submission.

## SUMMARY: budget

known exposure only; campaign snapshot absent.

Exposure = reserved (unsent) + settled + uncertain (dispatched). Cancelled attempts contribute no exposure. All money is exact micro-USD with Decimal USD formatting.

Campaign caps (plan D4 authorization, not a ledger): {"P0": 2000000, "P1": 8000000, "aggregate": 20000000} micro-USD.

Dedicated live limits: {"P0": 50000, "P1": 8000000, "aggregate": 50000} micro-USD. These are not campaign limits.

Stop state: **unknown: campaign snapshot absent**. Frozen: not established. Live cost basis: peak cache-miss input and peak output; cache discounts not assumed; derived upper estimate, not vendor-billed.

Null: N/A (accounting census). Micro over relations / macro over diagrams: N/A; these are monetary sums. Counts are attempts; no statistical denominator or interval applies.

| Phase | Reserved USD | Settled USD | Uncertain USD | Known exposure USD | Remaining USD | Attempts | Attempts by state | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | 0.000000 | 0.000268 | 0.000000 | 0.000268 | unknown | 1 | {"cancelled": 0, "dispatched": 0, "reserved": 0, "settled": 1} | S05#/, S01#0, S06#/observation/derived_micro_usd |
| P1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | unknown | 0 | {"cancelled": 0, "dispatched": 0, "reserved": 0, "settled": 0} | S05#/, S01#0, S06#/observation/derived_micro_usd |
| P2 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | unknown | 0 | {"cancelled": 0, "dispatched": 0, "reserved": 0, "settled": 0} | S05#/, S01#0, S06#/observation/derived_micro_usd |
| aggregate | 0.000000 | 0.000268 | 0.000000 | 0.000268 | unknown | 1 | {"cancelled": 0, "dispatched": 0, "reserved": 0, "settled": 1} | S05#/, S01#0, S06#/observation/derived_micro_usd |

same attempt ID with byte-equivalent parsed row counted once; conflicting copies refused. P2 shares the remaining aggregate, not a separate fixed cap.

Quota is separate from USD; totals below cover supplied ledgers only. ledger quota rows have no phase field; per-phase attribution and quota limits are not established.

```json
{}
```

- live: frozen=False; window `deepseek-pricing-20260927:UTC:Mon-Fri:01-04,06-10:VERIFIED:holidays-conservative`; events `[]`.

## Gates

Missing evidence takes precedence over a failed component; all criteria must be evidenced and met to establish a gate. Policy: MVE_PLAN r5 §8/§11.

| Gate | Status | Criteria met/evidenced/required | Null / baseline | Micro / macro | Reason | Policy sources |
| --- | --- | --- | --- | --- | --- | --- |
| G0 | not established | 1/1/4 | Validation N/A; Geoperception weighted per-item 1/k_i and majority baseline (sample absent) | N/A / N/A | Missing evidence: bad references, arities, unauthorized support and invalid transitions rejected; Missing evidence: coverage target met; Missing evidence: 300 frozen Geoperception items, three pinned models and pinned scorer within USD 2; comparison incomplete without results | S01#8, S01#11 |
| G1 | not established | 0/0/5 | Query-set independent guessing: recall=FPR=1/2, precision=prevalence; all-positive precision=prevalence, recall=1. Full-record random-set null N/A. | N/A / N/A | Missing evidence: 500 sealed incidence diagrams; fixed queries, family split, no tolerance fitting on evaluation; Missing evidence: precision >= 0.90; Missing evidence: recall >= 0.70; Missing evidence: per-predicate suitable negatives: one-sided 95% FPR upper bound <= 0.02; otherwise insufficient evidence; Missing evidence: raw, coordinate-consistency, image-measurement; micro/macro; query/full-record; separate real-data transfer | S01#8, S01#11 |
| G2 | not established | 0/0/6 | Balanced binary 1/2; uniform k-class 1/k; majority, code-only and previous-lock baselines | N/A / N/A | spike fixture is not an activation dataset; no production promotion; independent evaluation gold and paired Opus predictions absent; calibration promotion/rollback evidence absent; original openJev head refit with ONNX parity absent; Missing evidence: independent gold: paired 95% lower bound cascade minus Opus >= -0.03; Missing evidence: human queue <= 25%; Missing evidence: per active question one-sided 95% automatic-route error upper bound <= 5%; spike fixture is not an activation dataset; no production promotion; independent evaluation gold and paired Opus predictions absent; calibration promotion/rollback evidence absent; original openJev head refit with ONNX parity absent; spike fixture is not an activation dataset; no production promotion; independent evaluation gold and paired Opus predictions absent; calibration promotion/rollback evidence absent; original openJev head refit with ONNX parity absent | S01#8, S01#11 |
| G3 | not established | 4/4/5 | N/A; empty/trivial, nearest-retrieval, weakened/strengthened/vacuous/unrelated-but-provable controls | N/A / N/A | 0/50 human reviews; 0/50 rubric passes; pending human rubric | S01#8, S01#11 |
| G4a | not established | 0/0/5 | N/A; fixed trivial-tactic baseline | N/A / N/A | Missing evidence: 50 semantically accepted statements frozen before tuning; Missing evidence: both provers, 120 s, declared resources; proved/timeout/error, latency, memory; Missing evidence: default >= 15/50 proved with checked dependency closures; Missing evidence: proved count then latency; DeepSeek on exact tie; Missing evidence: end-to-end success and trivial-tactic baseline reported | S01#8, S01#11 |
| G4b | not established | 0/0/5 | N/A; previous lock and unchanged-record round trip | N/A / N/A | Missing evidence: 30-minute, 20-diagram session; Missing evidence: persisted verdicts, not_visible abstention, revision invalidation, label provenance; Missing evidence: routing effects replayable; Missing evidence: floor-conditional refit or documented no-update; Missing evidence: pinned atlas integration test passes from archived build | S01#8, S01#11 |
| G5 | not established | 0/0/4 | N/A general PD; conditional orientation-only 2^(-c); knot-type 1/k plus majority | N/A / N/A | Missing evidence: frozen diagram grammar and PD scorer; Missing evidence: >= 30% complete PD on separate synthetic <= 7-crossing set; Missing evidence: >= 30% complete PD on permitted external <= 7-crossing set; missing external incomplete; Missing evidence: exact/canonicalized apart; component validity, crossing/orientation errors, unknowns, invariant consistency | S01#8, S01#11 |
| G6 | not established | 0/0/3 | N/A integration; each scientific claim declares its own null and unit | N/A / N/A | Missing evidence: one reproducible record: image, revisions, evidence, assumptions, statement hash, actual statuses and baselines; Missing evidence: Sol review; Missing evidence: real ingest/validation contract passes; negative or inconclusive science is acceptable | S01#8, S01#11 |

### G0 criteria

- comparison: **not established** — 300 frozen Geoperception items, three pinned models and pinned scorer within USD 2; comparison incomplete without results. Missing evidence: 300 frozen Geoperception items, three pinned models and pinned scorer within USD 2; comparison incomplete without results (no result evidence).
- coverage: **not established** — coverage target met. Missing evidence: coverage target met (no result evidence).
- negative_fixtures: **not established** — bad references, arities, unauthorized support and invalid transitions rejected. Missing evidence: bad references, arities, unauthorized support and invalid transitions rejected (no result evidence).
- records: **met** — 100 independently generated records validate. WP-2 artifact audit records validated; does not replace negative fixtures or model comparison (S04#/records_validated).

### G1 criteria

- fpr: **not established** — per-predicate suitable negatives: one-sided 95% FPR upper bound <= 0.02; otherwise insufficient evidence. Missing evidence: per-predicate suitable negatives: one-sided 95% FPR upper bound <= 0.02; otherwise insufficient evidence (no result evidence).
- precision: **not established** — precision >= 0.90. Missing evidence: precision >= 0.90 (no result evidence).
- recall: **not established** — recall >= 0.70. Missing evidence: recall >= 0.70 (no result evidence).
- sealed: **not established** — 500 sealed incidence diagrams; fixed queries, family split, no tolerance fitting on evaluation. Missing evidence: 500 sealed incidence diagrams; fixed queries, family split, no tolerance fitting on evaluation (no result evidence).
- separate_scores: **not established** — raw, coordinate-consistency, image-measurement; micro/macro; query/full-record; separate real-data transfer. Missing evidence: raw, coordinate-consistency, image-measurement; micro/macro; query/full-record; separate real-data transfer (no result evidence).

### G2 criteria

- floors: **not established** — only floor-met questions active with three family-disjoint splits. spike fixture is not an activation dataset; no production promotion; independent evaluation gold and paired Opus predictions absent; calibration promotion/rollback evidence absent; original openJev head refit with ONNX parity absent (S07#/learning).
- paired_accuracy: **not established** — independent gold: paired 95% lower bound cascade minus Opus >= -0.03. Missing evidence: independent gold: paired 95% lower bound cascade minus Opus >= -0.03 (no result evidence).
- promotion: **not established** — promote/rollback decision on calibration evidence. spike fixture is not an activation dataset; no production promotion; independent evaluation gold and paired Opus predictions absent; calibration promotion/rollback evidence absent; original openJev head refit with ONNX parity absent (S07#/learning).
- queue: **not established** — human queue <= 25%. Missing evidence: human queue <= 25% (no result evidence).
- route_error: **not established** — per active question one-sided 95% automatic-route error upper bound <= 5%. Missing evidence: per active question one-sided 95% automatic-route error upper bound <= 5% (no result evidence).
- weight_refit: **not established** — real production weight refit, ONNX export and inference parity. spike fixture is not an activation dataset; no production promotion; independent evaluation gold and paired Opus predictions absent; calibration promotion/rollback evidence absent; original openJev head refit with ONNX parity absent (S07#/learning).

### G3 criteria

- first_pass: **met** — at least 80/100 first-pass well-typed artifacts. 80/100 first-pass (S08#/, S02#addendum-9, S10#/, S09#/).
- post_repair: **met** — at least 95/100 post-repair well-typed artifacts. 100/100 post-repair (S08#/, S02#addendum-9, S10#/, S09#/).
- references: **met** — 50 retrieval-disjoint blinded reference tasks. 50/50 retrieval-disjoint references (S08#/, S02#addendum-9, S10#/, S09#/).
- semantic_rubric: **not established** — at least 20/50 human rubric passes: binders, premises, goal, nondegeneracy. 0/50 human reviews; 0/50 rubric passes; pending human rubric (S08#/, S02#addendum-9, S10#/, S09#/).
- tasks: **met** — 100 distinct sealed statements with explicit premises and goals. 100/100 unique sealed statements (S08#/, S02#addendum-9, S10#/, S09#/).

### G4a criteria

- comparison: **not established** — both provers, 120 s, declared resources; proved/timeout/error, latency, memory. Missing evidence: both provers, 120 s, declared resources; proved/timeout/error, latency, memory (no result evidence).
- eligible: **not established** — 50 semantically accepted statements frozen before tuning. Missing evidence: 50 semantically accepted statements frozen before tuning (no result evidence).
- end_to_end: **not established** — end-to-end success and trivial-tactic baseline reported. Missing evidence: end-to-end success and trivial-tactic baseline reported (no result evidence).
- proofs: **not established** — default >= 15/50 proved with checked dependency closures. Missing evidence: default >= 15/50 proved with checked dependency closures (no result evidence).
- selection: **not established** — proved count then latency; DeepSeek on exact tie. Missing evidence: proved count then latency; DeepSeek on exact tie (no result evidence).

### G4b criteria

- atlas: **not established** — pinned atlas integration test passes from archived build. Missing evidence: pinned atlas integration test passes from archived build (no result evidence).
- refit: **not established** — floor-conditional refit or documented no-update. Missing evidence: floor-conditional refit or documented no-update (no result evidence).
- routing: **not established** — routing effects replayable. Missing evidence: routing effects replayable (no result evidence).
- session: **not established** — 30-minute, 20-diagram session. Missing evidence: 30-minute, 20-diagram session (no result evidence).
- verdicts: **not established** — persisted verdicts, not_visible abstention, revision invalidation, label provenance. Missing evidence: persisted verdicts, not_visible abstention, revision invalidation, label provenance (no result evidence).

### G5 criteria

- external: **not established** — >= 30% complete PD on permitted external <= 7-crossing set; missing external incomplete. Missing evidence: >= 30% complete PD on permitted external <= 7-crossing set; missing external incomplete (no result evidence).
- grammar: **not established** — frozen diagram grammar and PD scorer. Missing evidence: frozen diagram grammar and PD scorer (no result evidence).
- scores: **not established** — exact/canonicalized apart; component validity, crossing/orientation errors, unknowns, invariant consistency. Missing evidence: exact/canonicalized apart; component validity, crossing/orientation errors, unknowns, invariant consistency (no result evidence).
- synthetic: **not established** — >= 30% complete PD on separate synthetic <= 7-crossing set. Missing evidence: >= 30% complete PD on separate synthetic <= 7-crossing set (no result evidence).

### G6 criteria

- ingest: **not established** — real ingest/validation contract passes; negative or inconclusive science is acceptable. Missing evidence: real ingest/validation contract passes; negative or inconclusive science is acceptable (no result evidence).
- record: **not established** — one reproducible record: image, revisions, evidence, assumptions, statement hash, actual statuses and baselines. Missing evidence: one reproducible record: image, revisions, evidence, assumptions, statement hash, actual statuses and baselines (no result evidence).
- review: **not established** — Sol review. Missing evidence: Sol review (no result evidence).

## Evidence counts

95% intervals are null where no independent sampling design is committed; fixture counts are descriptive, not population confidence claims.

Every table below is a receipt census, not a scored relation benchmark. Micro/macro entries are N/A for these units. JSON retains null interval values, reasons and field pointers.

### classifier_spike

| Measure | Count | Denominator | Unit | Null | Micro / macro | Evidence / limits | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ONNX argmax parity | 3 | 3 | fixture states | N/A: structural or operational census | N/A / N/A | new linear head over frozen openJev logits; not original-head refit; fixture only, not G2 | S07#/onnx_parity |
| training rows | 4 | 4 | fixture rows | N/A: structural or operational census | N/A / N/A |  | S07#/training_rows |
| training families | 1 | not established | families | N/A: structural or operational census | N/A / N/A |  | S07#/training_families |
| Q-agree-action/calibration | 0 | not established | label rows | uniform 1/k = 0.3333333333333333 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-agree-action/counts/calibration |
| Q-agree-action/evaluation | 0 | not established | label rows | uniform 1/k = 0.3333333333333333 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-agree-action/counts/evaluation |
| Q-agree-action/training | 4 | not established | label rows | uniform 1/k = 0.3333333333333333 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-agree-action/counts/training |
| Q-claim-workflow/calibration | 0 | not established | label rows | uniform 1/k = 0.25 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-claim-workflow/counts/calibration |
| Q-claim-workflow/evaluation | 0 | not established | label rows | uniform 1/k = 0.25 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-claim-workflow/counts/evaluation |
| Q-claim-workflow/training | 0 | not established | label rows | uniform 1/k = 0.25 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-claim-workflow/counts/training |
| Q-domain/calibration | 0 | not established | label rows | uniform 1/k = 0.1111111111111111 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-domain/counts/calibration |
| Q-domain/evaluation | 0 | not established | label rows | uniform 1/k = 0.1111111111111111 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-domain/counts/evaluation |
| Q-domain/training | 0 | not established | label rows | uniform 1/k = 0.1111111111111111 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-domain/counts/training |
| Q-drift-flag/calibration | 0 | not established | label rows | uniform 1/k = 0.5 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-drift-flag/counts/calibration |
| Q-drift-flag/evaluation | 0 | not established | label rows | uniform 1/k = 0.5 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-drift-flag/counts/evaluation |
| Q-drift-flag/training | 0 | not established | label rows | uniform 1/k = 0.5 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-drift-flag/counts/training |
| Q-mark-type/calibration | 0 | not established | label rows | uniform 1/k = 0.2 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-mark-type/counts/calibration |
| Q-mark-type/evaluation | 0 | not established | label rows | uniform 1/k = 0.2 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-mark-type/counts/evaluation |
| Q-mark-type/training | 0 | not established | label rows | uniform 1/k = 0.2 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-mark-type/counts/training |
| Q-shape/calibration | 0 | not established | label rows | uniform 1/k = 0.16666666666666666 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-shape/counts/calibration |
| Q-shape/evaluation | 0 | not established | label rows | uniform 1/k = 0.16666666666666666 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-shape/counts/evaluation |
| Q-shape/training | 0 | not established | label rows | uniform 1/k = 0.16666666666666666 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-shape/counts/training |
| Q-solver/calibration | 0 | not established | label rows | uniform 1/k = 0.2 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-solver/counts/calibration |
| Q-solver/evaluation | 0 | not established | label rows | uniform 1/k = 0.2 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-solver/counts/evaluation |
| Q-solver/training | 0 | not established | label rows | uniform 1/k = 0.2 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-solver/counts/training |
| Q-topo-workflow/calibration | 0 | not established | label rows | uniform 1/k = 0.25 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-topo-workflow/counts/calibration |
| Q-topo-workflow/evaluation | 0 | not established | label rows | uniform 1/k = 0.25 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-topo-workflow/counts/evaluation |
| Q-topo-workflow/training | 0 | not established | label rows | uniform 1/k = 0.25 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-topo-workflow/counts/training |
| Q-track/calibration | 0 | not established | label rows | uniform 1/k = 0.5 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-track/counts/calibration |
| Q-track/evaluation | 0 | not established | label rows | uniform 1/k = 0.5 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-track/counts/evaluation |
| Q-track/training | 0 | not established | label rows | uniform 1/k = 0.5 | N/A / N/A | No independent gold accuracy; majority/code-only/previous-lock unavailable | S07#/learning/support/Q-track/counts/training |

### corpus

| Measure | Count | Denominator | Unit | Null | Micro / macro | Evidence / limits | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| corpus/calibration | 20 | 2560 | diagrams | N/A: structural or operational census | N/A / N/A |  | S04#/counts/calibration |
| corpus/development | 20 | 2560 | diagrams | N/A: structural or operational census | N/A / N/A |  | S04#/counts/development |
| corpus/fit | 2000 | 2560 | diagrams | N/A: structural or operational census | N/A / N/A |  | S04#/counts/fit |
| corpus/retrieval | 20 | 2560 | diagrams | N/A: structural or operational census | N/A / N/A |  | S04#/counts/retrieval |
| corpus/sealed | 500 | 2560 | diagrams | N/A: structural or operational census | N/A / N/A |  | S04#/counts/sealed |
| records validated | 2560 | 2560 | records | N/A: structural or operational census | N/A / N/A | Receipt evidence; generated private corpus not re-audited by this report | S04#/records_validated |
| truth class/false | 4881465 | 5777920 | candidate relations | N/A: structural or operational census | N/A / N/A | Truth census, not perception scores; per-diagram truth counts unavailable in receipt | S04#/class_counts/false |
| truth class/incidental_unproved | 341223 | 5777920 | candidate relations | N/A: structural or operational census | N/A / N/A | Truth census, not perception scores; per-diagram truth counts unavailable in receipt | S04#/class_counts/incidental_unproved |
| truth class/premise | 3587 | 5777920 | candidate relations | N/A: structural or operational census | N/A / N/A | Truth census, not perception scores; per-diagram truth counts unavailable in receipt | S04#/class_counts/premise |
| truth class/unknown | 551645 | 5777920 | candidate relations | N/A: structural or operational census | N/A / N/A | Truth census, not perception scores; per-diagram truth counts unavailable in receipt | S04#/class_counts/unknown |
| cross_split_coordinate_collisions | 0 | not established | cross-split collisions | N/A: structural or operational census | N/A / N/A | Pair denominator not retained by receipt | S04#/cross_split_coordinate_collisions |
| cross_split_image_collisions | 0 | not established | cross-split collisions | N/A: structural or operational census | N/A / N/A | Pair denominator not retained by receipt | S04#/cross_split_image_collisions |

### formalization

| Measure | Count | Denominator | Unit | Null | Micro / macro | Evidence / limits | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| first_pass_well_typed | 80 | 100 | statements | N/A: structural or operational census | N/A / N/A | WP-2 exact-true non-premise goals; deterministic emitter and syntax repair, not a model formalization benchmark; exact truth is not a derivability claim; typechecking is not proof or semantic acceptance | S08#/first_pass_well_typed, S10#/, S09#/ |
| post_repair_well_typed | 100 | 100 | statements | N/A: structural or operational census | N/A / N/A | WP-2 exact-true non-premise goals; deterministic emitter and syntax repair, not a model formalization benchmark; exact truth is not a derivability claim; typechecking is not proof or semantic acceptance | S08#/post_repair_well_typed, S10#/, S09#/ |
| unique_canonical_statements | 100 | 100 | statements | N/A: structural or operational census | N/A / N/A | WP-2 exact-true non-premise goals; deterministic emitter and syntax repair, not a model formalization benchmark; exact truth is not a derivability claim; typechecking is not proof or semantic acceptance | S08#/unique_canonical_statements, S10#/, S09#/ |
| human_reviews | 0 | 50 | reference tasks | N/A: structural or operational census | N/A / N/A | WP-2 exact-true non-premise goals; deterministic emitter and syntax repair, not a model formalization benchmark; exact truth is not a derivability claim; typechecking is not proof or semantic acceptance | S08#/human_reviews, S10#/, S09#/ |
| semantic_rubric_passes | 0 | 50 | reference tasks | N/A: structural or operational census | N/A / N/A | WP-2 exact-true non-premise goals; deterministic emitter and syntax repair, not a model formalization benchmark; exact truth is not a derivability claim; typechecking is not proof or semantic acceptance | S08#/semantic_rubric_passes, S10#/, S09#/ |
| control/empty | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/empty, S10#/, S09#/ |
| control/nearest_retrieval | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/nearest_retrieval, S10#/, S09#/ |
| control/strengthened | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/strengthened, S10#/, S09#/ |
| control/trivial | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/trivial, S10#/, S09#/ |
| control/unrelated_but_provable | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/unrelated_but_provable, S10#/, S09#/ |
| control/vacuous | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/vacuous, S10#/, S09#/ |
| control/weakened | 100 | 100 | control statements | N/A: structural or operational census | N/A / N/A |  | S08#/controls/weakened, S10#/, S09#/ |
| equivalence/kernel_checked | 0 | 50 | reference tasks | N/A: structural or operational census | N/A / N/A |  | S08#/equivalence_counts/kernel_checked, S10#/, S09#/ |
| equivalence/machine_supported | 50 | 50 | reference tasks | N/A: structural or operational census | N/A / N/A |  | S08#/equivalence_counts/machine_supported, S10#/, S09#/ |
| equivalence/reviewer_judged | 0 | 50 | reference tasks | N/A: structural or operational census | N/A / N/A |  | S08#/equivalence_counts/reviewer_judged, S10#/, S09#/ |
| equivalence/unresolved | 0 | 50 | reference tasks | N/A: structural or operational census | N/A / N/A |  | S08#/equivalence_counts/unresolved, S10#/, S09#/ |
| predicate/Collinear | 5 | 100 | statements | N/A: structural or operational census | N/A / N/A | {'available': 5, 'quota': 12, 'reason': 'Insufficient distinct statements in frozen sealed families at seeds 0..9 (all five WP-2 controls); repeated sources are deduplicated. Unfilled quota redistributed round-robin.', 'selected': 5} | S08#/per_predicate_counts/Collinear, S10#/, S09#/ |
| predicate/Concyclic | 4 | 100 | statements | N/A: structural or operational census | N/A / N/A | {'available': 4, 'quota': 11, 'reason': 'Insufficient distinct statements in frozen sealed families at seeds 0..9 (all five WP-2 controls); repeated sources are deduplicated. Unfilled quota redistributed round-robin.', 'selected': 4} | S08#/per_predicate_counts/Concyclic, S10#/, S09#/ |
| predicate/EqualAngle | 17 | 100 | statements | N/A: structural or operational census | N/A / N/A |  | S08#/per_predicate_counts/EqualAngle, S10#/, S09#/ |
| predicate/EqualLength | 17 | 100 | statements | N/A: structural or operational census | N/A / N/A |  | S08#/per_predicate_counts/EqualLength, S10#/, S09#/ |
| predicate/Midpoint | 3 | 100 | statements | N/A: structural or operational census | N/A / N/A | {'available': 3, 'quota': 11, 'reason': 'Insufficient distinct statements in frozen sealed families at seeds 0..9 (all five WP-2 controls); repeated sources are deduplicated. Unfilled quota redistributed round-robin.', 'selected': 3} | S08#/per_predicate_counts/Midpoint, S10#/, S09#/ |
| predicate/Parallel | 18 | 100 | statements | N/A: structural or operational census | N/A / N/A |  | S08#/per_predicate_counts/Parallel, S10#/, S09#/ |
| predicate/Perpendicular | 14 | 100 | statements | N/A: structural or operational census | N/A / N/A |  | S08#/per_predicate_counts/Perpendicular, S10#/, S09#/ |
| predicate/RightAngle | 17 | 100 | statements | N/A: structural or operational census | N/A / N/A |  | S08#/per_predicate_counts/RightAngle, S10#/, S09#/ |
| predicate/SBetween | 5 | 100 | statements | N/A: structural or operational census | N/A / N/A | {'available': 5, 'quota': 11, 'reason': 'Insufficient distinct statements in frozen sealed families at seeds 0..9 (all five WP-2 controls); repeated sources are deduplicated. Unfilled quota redistributed round-robin.', 'selected': 5} | S08#/per_predicate_counts/SBetween, S10#/, S09#/ |

### live_probe

| Measure | Count | Denominator | Unit | Null | Micro / macro | Evidence / limits | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| image accepted | 1 | 1 | live probe | N/A: structural or operational census | N/A / N/A | No truth-scored accuracy from the probe | S06#/observation/image_accepted |
| prompt_tokens | 236 | 1 | tokens per probe | N/A: structural or operational census | N/A / N/A |  | S06#/observation/usage/prompt_tokens |
| completion_tokens | 164 | 1 | tokens per probe | N/A: structural or operational census | N/A / N/A |  | S06#/observation/usage/completion_tokens |
| total_tokens | 400 | 1 | tokens per probe | N/A: structural or operational census | N/A / N/A |  | S06#/observation/usage/total_tokens |
| latency_s | 1.4512553750537336 | 1 | seconds per probe | N/A: structural or operational census | N/A / N/A |  | S06#/observation/latency_s |

### preflight

| Measure | Count | Denominator | Unit | Null | Micro / macro | Evidence / limits | Sources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vision_and_runner_contract | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/0 |
| rhjev_tests | 1 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: ran; capability-specific only | S11#/checks/1 |
| openjev_fixture | 1 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: ran; capability-specific only | S11#/checks/2 |
| newclid_import | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/3 |
| atlas_ingest_contract | 1 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: ran; capability-specific only | S11#/checks/4 |
| codex_cli | 1 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: ran; capability-specific only | S11#/checks/5 |
| lean_toolchain_presence | 1 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: ran; capability-specific only | S11#/checks/6 |
| euclid_generator_discovery | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/7 |
| newclid_jgex_roundtrip | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/8 |
| newclid_geogebra_terms | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/9 |
| rhvf_isolation | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/10 |
| explorer_scenes | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/11 |
| local_prover_host | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/12 |
| human_latency | 0 | 1 | capability check | N/A: structural or operational census | N/A / N/A | WP-0a historical status: failed; capability-specific only | S11#/checks/13 |

## Relation scoring availability

Query-set and full-record scoring remain separate, as do each measurement stage and real-data transfer. Missing results are null, never zero accuracy.

| Population | Stage | Mode | Count / denominator | Micro | Macro | Null | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sealed_synthetic | raw_perception | query_set | unknown / unknown | not established | not established | independent query guesses: recall/FPR 1/2, precision prevalence (unknown) | No committed scored predictions; corpus availability is not scored evidence |
| sealed_synthetic | raw_perception | full_record | unknown / unknown | not established | not established | N/A: no universal full-record random-set null | No committed scored predictions; corpus availability is not scored evidence |
| sealed_synthetic | coordinate_consistency | query_set | unknown / unknown | not established | not established | independent query guesses: recall/FPR 1/2, precision prevalence (unknown) | No committed scored predictions; corpus availability is not scored evidence |
| sealed_synthetic | coordinate_consistency | full_record | unknown / unknown | not established | not established | N/A: no universal full-record random-set null | No committed scored predictions; corpus availability is not scored evidence |
| sealed_synthetic | image_measurement | query_set | unknown / unknown | not established | not established | independent query guesses: recall/FPR 1/2, precision prevalence (unknown) | No committed scored predictions; corpus availability is not scored evidence |
| sealed_synthetic | image_measurement | full_record | unknown / unknown | not established | not established | N/A: no universal full-record random-set null | No committed scored predictions; corpus availability is not scored evidence |
| real_data_transfer | raw_perception | query_set | unknown / unknown | not established | not established | independent query guesses: recall/FPR 1/2, precision prevalence (unknown) | No committed scored predictions; corpus availability is not scored evidence |
| real_data_transfer | raw_perception | full_record | unknown / unknown | not established | not established | N/A: no universal full-record random-set null | No committed scored predictions; corpus availability is not scored evidence |
| real_data_transfer | coordinate_consistency | query_set | unknown / unknown | not established | not established | independent query guesses: recall/FPR 1/2, precision prevalence (unknown) | No committed scored predictions; corpus availability is not scored evidence |
| real_data_transfer | coordinate_consistency | full_record | unknown / unknown | not established | not established | N/A: no universal full-record random-set null | No committed scored predictions; corpus availability is not scored evidence |
| real_data_transfer | image_measurement | query_set | unknown / unknown | not established | not established | independent query guesses: recall/FPR 1/2, precision prevalence (unknown) | No committed scored predictions; corpus availability is not scored evidence |
| real_data_transfer | image_measurement | full_record | unknown / unknown | not established | not established | N/A: no universal full-record random-set null | No committed scored predictions; corpus availability is not scored evidence |

## Source hashes

SHA-256 covers the exact bytes in the evidence commit. JSON field pointers and policy section references accompany derived numbers. The source inventory is provenance metadata, not a statistical table.

- S01: `docs/mve/MVE_PLAN.md` — `f073240be638b9225b5f6f33da4bbe34ef75d2ba71087da7b39b2ab9d9b61908`
- S02: `docs/mve/reviews/OFFLINE_PACKETS_REVIEW_OPUS_20260927.md` — `5546164a1a8dfe9b727da17b8c5b11faf84c032b928e185799ce9198f61e3bbe`
- S03: `docs/mve/reviews/WP2_CORPUS_RECEIPT_20260927.json` — `4795282bf1aad58553744316a518fa326eb8178de3d8ca3e9652370635d68db8`
- S04: `docs/mve/reviews/WP2_CORPUS_RENDER_V2_RECEIPT_20260927.json` — `fcf71b95df8dac21e240607d57d333aaad2e841fe843d47c01dea4ba7e569f54`
- S05: `docs/mve/reviews/wp0b-live/ledger.json` — `b6a03a43f9bff4907d15b3a27f609dc9b2e12b0dcc9830170c02f5388c11553c`
- S06: `docs/mve/reviews/wp0b-live/receipt.json` — `f328968f5e3ef6ebacff4cc1226b7e90485c9eefaff0722c5285aa1f88e18cc8`
- S07: `mve/classifier/spike_receipt.json` — `c500766cafb72ad782be2ecd41fa05af60d90e86f10d46a12f5d797d06ccc9a0`
- S08: `mve/lean/artifacts/g3-taskset/g3.json` — `e2f13af8c85d41020ca96f5041bbc55bd9c47f44a00671dfbd687e98a8f69853`
- S09: `mve/lean/artifacts/g3-taskset/references.json` — `b16bf256dc447cc425de7546d676d94a4b66cf16685b0a97c6769cfbed2fb03d`
- S10: `mve/lean/artifacts/g3-taskset/tasks.json` — `19b833bf4c05e0cdb8e60684a239c1eb6c4083c9dfca6528eaf8a1611b2591da`
- S11: `mve/preflight/results/report.json` — `f5e55b7b10e57f4c2fcf0695c3a7b7a182edff6dbee809a15afba85ccc3051a5`

Missing committed sources: `mve/campaign/ledger.json`.
