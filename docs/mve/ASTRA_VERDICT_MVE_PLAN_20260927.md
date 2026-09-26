**MVE implementation review — 2026-09-27**

**Verdict: revise before implementation.** The architecture is a useful starting point, but WP-1’s evidence model, WP-4’s measurement semantics, WP-5’s evaluation design, and WP-6’s formalization contract need decisions before their acceptance criteria are implementable.

I read the README first, then both documents and the supplied schema. All three supplied SHA-256 hashes match the manifest.

References below use **Plan** for [MVE_PLAN.md](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/MVE_PLAN.md>), **Review** for [MVE_REVIEW_OF_SOURCES.md](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/MVE_REVIEW_OF_SOURCES.md>), and **Schema** for [mve_observation_record.json](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/mve_observation_record.json>).

This is a packet review. **UNVERIFIED** means the packet does not establish the claimed behavior or capability; a source-review assertion is not an executable demonstration. Proposed resolutions below are recommendations, not existing capabilities or new owner decisions. D1–D6 remain constraints.

The session is read-only, so this response is the Markdown verdict; no file or code was written.

**1. Ambiguities that block work packets**

**WP-1 — Record model and validation**

| Blocking sentence or contract | Decision needed before implementation |
|---|---|
| §10: “invalid status transitions rejected (`perceived` → `formal` refused)” | `formal` is a record field, not a relation status. Specify an operation-level transition table, including permissions, prerequisites, rejection, correction, and downstream invalidation. JSON Schema alone cannot check historical transitions. |
| Schema root: “Nothing enters `formal` unless `measured` or `derived` supports it”; `formal.description`: “at least one relation” is measured, derived, or human-confirmed | These differ. One supported relation must not authorize every other relation. Require evidence references for **each emitted assumption and goal**, and distinguish an explicitly adopted assumption from a verified fact. |
| §1: “seven predicates”; §7 P1 lists nine; §7 P3 requires “every schema predicate” | Freeze a versioned P1 predicate registry. The schema has 22 predicate labels, including topology and `Other`; G1’s `PointLiesOnLine` is absent. Define its mapping and nondegeneracy conditions. |
| Schema: unrestricted `args`, `px`, `measured_px`, and `on` arrays | Define predicate arity, argument types/order, entity geometry, coordinate frame, units, and degeneracy rules. Specify line versus segment, strict versus non-strict betweenness, directed versus undirected angles, and circle representation. |
| §1: “provenance and confidence per claim” | Relation confidence is optional; free-text claims have no source field. There are no relation IDs or evidence dependencies. Define required provenance and distinguish model confidence, measurement uncertainty, and classifier confidence. |
| §5a: “every record names the weights version”; A6 records human verdicts | No declared fields capture weights version, decision-state hash, judge verdict, label version, or human event history. Add immutable evidence/decision events and stable IDs. The current record-ID recipe also cannot distinguish repeated identical requests or later revisions. |
| Schema validation generally | Specify uniqueness and referential integrity, positive dimensions, coordinate lengths, hash formats, confidence ranges, probability normalization, numeric units, and unknown-field handling. The current schema permits structurally plausible but unusable records. |
| §7 P0: validation against the repository schema; README supplies a flat copy | Declare the authoritative schema artifact and migration policy. Also define stage-specific records: synthetic ground truth and ingestion should not need fictitious perceiver provenance. |

**Proposed resolution:** maintain separate fields for observed evidence, adopted mathematical assumptions, computational derivations, human judgments, and formal artifacts. A single mutable status cannot represent all five reliably.

**WP-2 — Generator and ground truth**

| Blocking sentence | Decision needed |
|---|---|
| §7 P0: “Pull the Euclid image engine … as a vendored generator” | Pin the repository revision, actual generator entry point, dependency closure, and required license notices. The reusable engine interface is **UNVERIFIED**; Review §4 explicitly calls part of the rendering pipeline inferred. |
| §10: “full-predicate ground truth” | Define a finite candidate universe and distinguish construction premises, consequences, incidental coordinate relations, false predicates, and unknowns. “All relations” is not an implementable specification. |
| §10: “2,000 diagrams … determinism by seed” | Specify whether determinism means identical geometry, labels, records, or PNG bytes. Pin renderer settings and dependencies accordingly. |
| §7 P1: 2,000 fitting diagrams and 500 held-out diagrams | State whether these are disjoint, and split by construction family before generating alternate renderings. Specify styles, degeneracies, near-miss negatives, and annotation-bearing/not-to-scale diagrams. Seed separation alone does not establish independent evaluation. |

**WP-3 — Perceiver**

| Blocking sentence | Decision needed |
|---|---|
| A1: “One call per image” and “Two independent calls” | Choose two calls for the disagreement protocol and include both in cost accounting. Define entity alignment, disagreement thresholds, merging, and abstention. Same-model calls with different naming prompts are not established as independent. |
| A0: images “OCR’d once”; §8.5: “labels are stripped” | Define separate appearance-only and annotated-problem tracks. Preserve legitimate point identifiers and mathematical givens where the task requires them; exclude answer text and hidden reference data. Specify OCR storage and coordinate transforms. |
| A1: “pixel coordinates for every entity” | Specify coordinates for circles, curves, marks, polygons, and crossings—not just points. Define handling of occlusion, missing entities, malformed JSON, refusal, and out-of-image coordinates. |
| §3/§10: wrap the vision cell by path | The callable interface, retry behavior, image limits, thinking-mode behavior, and spend-ledger integration are **UNVERIFIED**. Pin an adapter contract, keep retries bounded, and retain raw responses for replay. |

**WP-4 — Measurement and Newclid**

| Blocking sentence | Decision needed |
|---|---|
| A2: relations are “recomputed from `px` coordinates” | Is A2 checking consistency of predicted coordinates, or independently locating geometry in the image? These are different measurements. Specify the independent image evidence, if any. |
| §0 D2: “JSXGraph for … measurement”; A2 allows “plain numpy” | Specify whether numerical helpers implement the same JSXGraph measurement contract or introduce another kernel. Establish canonical coordinates and cross-kernel agreement tests. |
| §2: remeasure “every tick/arc/arrow claim” | Coordinate arithmetic cannot identify which segments share a tick convention. Specify mark detection, mark-to-entity association, OCR evidence, and precedence when drawn dimensions disagree with annotations. |
| §7 P1: tolerances fitted so “false-positive rate on random point triples is ≤ 2%” | Define residuals and suitable negatives for each predicate. Triples do not test equal angles, parallel lines, equal lengths, or four-point concyclicity. Include scale normalization, localization uncertainty, and near-degenerate cases. |
| A2: “given the measured construction … derivable from the stated premises” | Identify the actual premise source. Do not silently promote measured relations into premises and then call their consequences verified. Store a derivation trace and its dependencies. |
| §10: “Newclid derivable/drawn split on 50 fixtures” | Define outcomes as proved, counterexample found, unknown, unsupported, or timeout. Specify supported imports/exports and proof evidence. Export to `.ggb`/JGEX and the claimed checker interfaces are **UNVERIFIED**. |

**WP-5 — Decision layer and learning**

| Blocking sentence | Decision needed |
|---|---|
| §5: each question has labels ending in `other` | Noul and Score do not have that listed answer, and Q-solver omits it. Specify abstention separately from mathematical/classification labels. Resolve overlapping labels such as `tangent` and `internally_tangent`. |
| §5 catalogue versus “never a truth judge” | Q-cyclic, Q-genus, Q-knot-type, and Q-drift cross into mathematical or semantic judgments. Route computable results through code; let Jev select a workflow or request review. Its answer must not authorize mathematical truth. |
| §5: “state template ≤140 words”; §10: “token length asserted ≤512” | Count the **complete serialized model input**, including question, labels, delimiters, and special tokens, at runtime. Define truncation or abstention without silently dropping relevant evidence. |
| §5: τ-high/τ-low, risk floors, and the shaded band going to a human | Elsewhere the middle route is an LLM. Specify an exhaustive routing table, threshold boundary behavior, missing-evidence handling, and whether confidence means selected-label probability or something else. |
| §7 P2: “300 items … at least 10 yes / 10 no per question” | Most questions are multiclass or ordinal. Define per-class support and split-specific floors. With 12 binary questions, 300 total examples cannot provide 10 positive and 10 negative examples per question in both halves. |
| §5a: held-out half is used to fit thresholds and accept refits | Separate training, calibration, and final evaluation. Define construction/diagram grouping, repeat-label assignment, and replacement of evaluation sets after their results influence development. |
| §5a: “Fine-tune the openJev head” | The packet establishes an ONNX inference artifact, not an available training pipeline. Training checkpoint, trainable parameters, objective, weighting, export, and inference-parity procedure are **UNVERIFIED**. |
| §5a: human verdicts override manager labels | Define target labels for each question. A “confirm this relation” click does not label domain, solver choice, or drift. Define `not visible`, disagreement between humans, corrections, and the role of synthetic truth versus human annotations. |
| §5a: refit accepted only if accuracy never drops and queue never rises | Specify accuracy denominator, selective error, coverage, uncertainty, and treatment of unanswered items. A queue increase may be the correct response to increased uncertainty. |
| §7 P2 activates all 12 questions | Knot/genus inputs arrive in P5, solver inputs in P3/P4, and the human interface in P4. Stage question activation; missing classes or evidence must remain disabled/inconclusive. |
| §5a: manager labels and audit outcomes become training labels | Define one reproducible audit sample, its eligibility population, independent adjudication, and how sampling bias is reported. Keep evaluation gold separate from the manager whose accuracy is being compared. |

**WP-6 — Formalizer**

| Blocking sentence | Decision needed |
|---|---|
| A4: “deterministic translation for every predicate in the schema” | Specify the supported subset and fail closed outside it. `Other` has no deterministic semantics; genus, knots, plots, and surfaces lack a defined target representation. |
| A4: LLM may “choose the goal when the problem text gives one” | The schema has no structured problem text, goal, binders, or premise/goal distinction. Define these, including existence and nondegeneracy assumptions. With no supplied goal, emit an observation/assumption record rather than inventing a theorem. |
| §7 P3: LeanGeo dependency; toolchain minimum “already satisfied” | Pin compatible Lean, Mathlib, LeanGeo, and tactic revisions in an isolated project. Exact compatibility and the claimed symbol mappings are **UNVERIFIED**. |
| §7 P3: repair “≤3 rounds” | Define legal repairs. Repairs must preserve binders, hypotheses, and goal meaning; changing the proposition to make compilation succeed is a formalization failure. |
| A4: E3 “else a Sol judgment” | Define separate machine-checked, human/model-judged, unknown, and unsupported outcomes. Add evaluator identity, method, artifact hashes, and evidence to the record. |
| §7 P3: references used as retrieval exemplars and equivalence targets | Split theorem families before retrieval. Exclude the test theorem and equivalent variants from retrieval and repair context. Render givens without turning the desired conclusion into an input annotation. |
| WP-6: “no `sorry` accepted as success” versus G3’s statement elaboration | Specify separate statement-typechecking and proof-checking artifacts. Statement elaboration should not require a fabricated proof; proof acceptance must check the dependency closure, not merely search generated text for `sorry`. |

**WP-7 — Prover and counterexamples**

| Blocking sentence | Decision needed |
|---|---|
| A5: “counterexample search … before any proof attempt” | Define its mathematical domain, search budget, witness format, tolerance policy, and exact/certified validation. No found counterexample is an unknown result, not evidence of truth. |
| §10: “kernel acceptance parsed from Lean output” | Specify a trusted compilation environment and axiom policy. Preserve the intended theorem and audit dependencies; a successful process exit alone is insufficient. |
| §0 D3/§7 P4: same 50 statements, same 120 seconds | Specify hardware, model revisions, quantization, decoding, attempts, repair allocation, and what the timeout includes. MLX compatibility, memory fit, and usable model artifacts are **UNVERIFIED**. |
| G4: “30% of G3’s equivalent statements” | G3 requires only 20 of 50 statements judged equivalent. Define where the 50 valid comparison statements come from and report both conditional proof success and end-to-end success. Predeclare a default-selection and tie-break rule. |

**WP-8 — Co-observer surface**

| Blocking sentence | Decision needed |
|---|---|
| A6: confirm/reject/“not visible” each writes confirmed/rejected | `Not visible` is not rejection. Add an abstention/visibility event; distinguish confirming an image reading from adopting a theorem assumption. |
| A6: editable table and verdict endpoint | Define revision control, human identity, conflicting edits, label correction, and invalidation of measurements, formalizations, proofs, and renders after an edit. |
| A6: “render-back of the statement” | Define a supported mathematical subset, handling of multiple/no realizations, renderer constraints, and a semantic round-trip test. A generic Lean-to-Penrose/ProofWidgets renderer is **UNVERIFIED**. |
| §10: “atlas labs check passes”; §3 says this worktree lacks atlas code | Specify the host integration contract, build inputs, exact check, and packaging across repositories. Assign P6 integration ownership to WP-8/WP-9/WP-11. |

**WP-9 — Fleet and ledger**

| Blocking sentence | Decision needed |
|---|---|
| D4: USD 20 cap “in every wave manifest” | Enforce an aggregate P0–P2 budget across waves, not USD 20 per wave. Include reserved in-flight costs, retries, OCR, both perception calls, other model calls, and reconciliation after failures. |
| §10: “cap enforced in dry-run” | Define tests that simulate chargeable calls, concurrency, retries, crashes, and resume. A manifest containing a cap does not establish runtime enforcement. |
| §6: “off-peak … runner already waits”; §9 budgets | Pin timezone/window, applicable providers, pricing, and clock behavior. Rates and runner enforcement are **UNVERIFIED**. Account-quota calls and API-dollar calls need distinct accounting. |
| §6: zero measured relations stops a lane; §8.6: stop only when decision layer is confident | Define precedence, stop reasons, restart authority, and audit eligibility. Mechanical failures and empty measurements should not wait for classifier confidence. |
| §10: every branch starts from the original branch | Define integration branches or explicit dependency commits for later packets. `git archive HEAD` also needs a lock of external by-path dependencies; it does not capture them. |

**WP-10 — Topology**

| Blocking sentence | Decision needed |
|---|---|
| A2/P5: skeleton → crossings → PD code | Specify accepted diagram conventions, broken underpasses, traversal, arc numbering, crossing order, orientation, mirror conventions, and malformed-diagram rejection. |
| G5: “strict PD transcription” | Choose exact serialization or equivalence under an explicit canonicalization. These are different scores. Define component ordering and relabeling treatment. |
| G5 uses KnotBench; WP-10 acceptance uses synthetic knots | Require separate synthetic and external results. The KnotBench subset, annotations, scoring rules, and permitted use are **UNVERIFIED**. |
| §10: “SnapPy verify” | Name the exact operation and certificate/result it produces. Computing an invariant, recognizing a knot type, and verifying image transcription are different tasks. |
| P5: Q-genus live | Knot diagrams and surface diagrams need different representations. Specify connectedness, orientability, boundaries, and a validated cell decomposition before inferring genus. Otherwise defer surface support. |
| G5: every error traced to skeleton or orientation | Include traversal, arc association, labels, canonicalization, unsupported conventions, and ambiguous source images. Permit unresolved causes. |

**WP-11 — Evaluation**

| Blocking sentence | Decision needed |
|---|---|
| G0: 300-item stratified Geoperception sample, random baseline 16.4% | Freeze item IDs, task format, parser, weighting, and answer spaces. Recompute chance for that sample; the published aggregate is not automatically its chance rate. |
| G1: relation precision/recall and real benchmark average | Define candidate generation, entity matching, micro/macro averaging, abstentions, invalid outputs, and query-versus-full-record scoring. Use fixed denominators. |
| §8: sealed sets and controls | Hide answers, premises, reference paths, and metadata from the inference process. HMAC filenames alone do not isolate gold. Separate prompt development, tolerance fitting, retrieval, calibration, and evaluation data. |
| §8.5: text-free visual tasks | Separate geometric appearance, annotation reading, and full problem understanding. Their inputs and correct answers differ. |
| §8: every metric has “chance + baseline” | Define a null for stochastic classification and use “N/A—no defined random-output distribution” for structural validity, elaboration, and proof checks. Do not invent universal chance rates. |
| WP-11 appears after the model packets | Deliver its split, scoring, and control infrastructure before their first evaluated runs. Otherwise earlier gate results cannot meet the stated protocol. |

**2. Claims I believe are wrong or unsupported in a consequential way**

| Citation | Assessment and correction |
|---|---|
| Plan §2: “Lean elaboration is the verifier” | **Wrong if this means mathematical correctness.** Elaboration checks that a statement is well formed. It does not prove it or show that it represents the diagram. These need separate statuses. |
| Plan A2: coordinate recomputation as “re-measurement” | **Overclaimed.** A perfectly consistent set of hallucinated coordinates passes this check. Call it coordinate-consistency checking unless A2 obtains independent image evidence. |
| Plan A2: non-derived relations are “true in this figure, not in general” | **Wrong inference.** Failure to derive does not establish nonderivability, and a small pixel residual establishes neither exact truth nor a counterexample to general truth. Use “numerically consistent; derivability unresolved.” |
| Schema `formal.description`: one measured/derived/human-confirmed relation permits formal content | **Insufficient evidence rule.** It allows unrelated unsupported assumptions into the same artifact. Formalization needs support or explicit assumption status per proposition. |
| Plan §5: Jev “cannot hallucinate” because labels are fixed | **Wrong.** A finite answer list prevents arbitrary output strings, not unsupported or false answers. |
| Plan §5 Q-cyclic versus §6 “never … ‘is this true’” | **Internal contradiction.** Q-cyclic asks for a mathematical truth judgment already addressed by a numerical residual. It should be a code result with uncertainty, not a classifier certification. |
| Plan §5a: “held-out” threshold fitting and repeated acceptance testing | **Mischaracterized as independent evaluation.** These examples are calibration/model-selection data. Reusing them for promotion decisions makes their reported performance development-dependent. |
| Plan §7 P2: 300 labels and binary floors for 12 questions | **Inconsistent specification.** The stated split cannot meet both binary floors for every question, and binary floors do not cover multiclass/ordinal questions. |
| Plan §2: “ConvNeXt learns geometry 3–5× faster” | **Not supported by its own companion review.** Review §4 says the comparator encoders are 3–5× larger. That is a size claim, not a measured training-speed ratio. Actual speedup is **UNVERIFIED**. |
| Plan §2/Review §2: CLIP encoders “fail on line drawings” | **Too broad.** Review §4 describes the successful Euclid encoder as CLIP-pretrained. Distinguish architecture, pretraining, task, and evaluation rather than treating CLIP as categorically unsuitable. |
| Plan §0: perception, “not reasoning,” is the bottleneck | **Unsupported as a universal claim.** Review §5 reports a different error distribution and warns that its taxonomy conflates failure types. The packet supports task-specific perception failures, not one universal bottleneck. |
| Plan §0: cascade achieves 99% accuracy retention “at 0.36% of the fee” | **UNVERIFIED conflation.** Review §6 attributes the fee ratio to the judge comparison and separately describes cascade retention. It does not establish the cascade’s combined cost, or transfer either result to the local 151M model. |
| Plan §7 P3: toolchain minimum satisfied, therefore dependency ready | **Invalid compatibility inference.** A version being newer than a minimum does not establish that the project’s Lean/Mathlib/dependency revisions compile together. |
| Plan A1/§8: “two independent perceptions” | **UNVERIFIED independence.** Naming perturbations of one model can expose instability but do not establish independent errors. Agreement is not verification. |
| Plan A2: over/under orientation “re-checked against the skeleton” | **Insufficient in general.** A representation that discards over/under information cannot recover it merely by checking its connectivity. Preserve the relevant gap/occlusion evidence and admit ambiguous inputs. |
| Plan §5 Q-genus: ordered answers 0–5 from Euler characteristic | **Incomplete mathematical specification.** The relationship depends on the surface class, components, and boundaries; the range also excludes other possibilities. Require validated hypotheses and an unknown/unsupported route. |
| Plan §8.5/§11: stripping labels prevents answer leakage | **Not sufficient and potentially task-changing.** It can remove necessary point identities and stated givens, while leaving answer-bearing metadata or annotations elsewhere. |
| Plan G0/G1/G5: published random/frontier scores used as local baselines | **Invalid without matched evaluation.** Different subsets, weighting, inputs, and scorers can change the baseline. In particular, 0/100 is an observed model result, not a chance rate. |
| Plan §11: “GeoGebra only inside Newclid” as licensing mitigation | **UNVERIFIED sufficiency.** Containment does not itself establish permission for the actual dependency and use. Exact artifacts and applicable terms are absent from the packet. |

The following material capability claims also remain **UNVERIFIED**:

- **Plan §3:** reusable function signatures, ledger behavior, the 308-test result, external checkout contents, atlas integration checks, and current dependency compatibility. The README permits assuming the stated context exists; it does not supply these contracts or execution evidence.
- **Plan §§0, 4, 9 / Review §§6–7:** current model identifiers, image capabilities, prices, off-peak windows, and local classifier calibration. Treat these as preflight checks before paid execution.
- **Review §§4, 7:** generator completeness, Newclid export/checker support, LeanGeo predicate coverage, E3 applicability, automatic render-back, and local prover hosting.
- **Review §§0–7:** numerical literature results, repository maintenance statistics, and license conclusions are secondary assertions in this packet. They can motivate experiments; they cannot serve as reproduced acceptance evidence.
- **Plan §7:** the calendar schedule and whether the proposed sample counts fit the caps. No measured latency, staffing, annotation-time, or complete call-count model establishes them.

**3. Build order I would use**

I would split packets into early infrastructure and later completion slices, without changing their ownership.

| Order | Work | Reason for changing §7 |
|---|---|---|
| 1 | Resolve WP-1 semantics; freeze the initial predicate registry, premise/goal contract, and dependency interfaces | All subsequent stages depend on these meanings. |
| 2 | WP-1 plus the manifest/budget portion of WP-9 and split/scorer portion of WP-11 | Budget enforcement and evaluation isolation must exist before model calls. |
| 3 | WP-2, including independent exact ground truth and adversarial controls | Provides fixtures for perception, measurement, formalization, and calibration. |
| 4 | A narrow WP-6 spike on trusted synthetic premises; WP-4 deterministic measurement fixtures | Exposes representation and Lean compatibility failures before investing in image throughput. |
| 5 | WP-3 and the remaining WP-4 image-measurement/Newclid bridge | Now evaluate perception against frozen ground truth and meaningful residuals. |
| 6 | Minimal WP-8 verdict capture; WP-5 inference, routing, labels, then training/export | Human labels must have a usable collection path before the learning loop. Activate only questions with supported inputs. |
| 7 | Complete WP-6, including repair restrictions and semantic evaluation | Freeze the intended statements before proving them. |
| 8 | WP-7 comparison; full WP-8 render-back and integration | Proof and render tests now operate on a stable formal contract. |
| 9 | Complete WP-9/WP-11 integration and first P6 evidence submission | These packets have been supporting every preceding gate; this completes their reporting/integration duties. |
| 10 | WP-10, with its own representation and gates | Geometry’s observation contract should be stable before adding PD codes and surfaces. |

A complete `image → record → supported assumptions → statement → proof status → verdict` slice should precede broad predicate expansion. Jev is an optional routing participant in that slice; proof validity must not depend on it.

**4. Revised gate table**

All thresholds below are **proposed acceptance rules**. Their attainability is **UNVERIFIED**. A budget-limited or statistically underpowered run is **inconclusive**, not a pass.

Common rules:

- Freeze the evaluation units, candidate sets, scorer, retrieval exclusions, model versions, and repair budgets before opening test results.
- Use construction/diagram-level splits. Report confidence intervals and counts; multiple relations from one diagram are not automatically independent samples.
- Include malformed outputs, abstentions, and timeouts in declared denominators.
- Maintain the USD 20 aggregate P0–P2 cap. Retain G0’s USD 2 ceiling and P1’s USD 8 ceiling as explicit phase allocations; P2 uses only the remaining balance. All chargeable calls count.
- Do not begin chargeable P3+ work on the assumption that D4 authorized an additional budget.

| Gate | Replacement test and pass rule | Chance/null and baseline |
|---|---|---|
| **G0 — Foundations** | Validate 100 independently generated records **and** negative fixtures for references, arities, evidence authorization, revisions, and invalid transitions. Meet the specified coverage target. Run the same frozen 300 benchmark items through three explicitly pinned models and scorers within the cap; otherwise mark the comparison incomplete. | Structural validation: **N/A**. For single-answer item \(i\) with \(k_i\) options, chance is \(1/k_i\), aggregated with the scorer’s weights. Other answer formats need their own explicit random-answer procedure. Include a frequency/majority baseline. |
| **G1 — Perception and measurement** | On 500 sealed incidence diagrams with fixed candidate queries, require precision ≥0.90 and recall ≥0.70. Fit no tolerance on this set. Separately test each supported predicate on appropriate negatives; require the one-sided 95% upper bound on FPR to be ≤0.02, otherwise report insufficient evidence. Compare raw perception, coordinate-only checking, and independent image measurement. Real-data results are a separate transfer evaluation; a written explanation does not satisfy a failed numeric gate. | For independent binary guessing with positive probability ½: expected recall/FPR ½ and population precision equal to positive prevalence \(\pi\). All-positive baseline: precision \(\pi\), recall 1. Published Geoperception results are contextual references until reproduced under matched conditions. |
| **G2 — Classifier and refit** | Activate only supported questions. Use separate training, calibration, and untouched evaluation groups with class-specific support. Against independent gold, require a paired 95% lower confidence bound on cascade-minus-Opus accuracy ≥−0.03, human-queue rate ≤25%, and a one-sided 95% upper bound on automatic-route error ≤5% per active question. If support is insufficient, keep that question disabled. Demonstrate one actual refit/export, replay parity, and promotion-or-rollback decision. | Binary balanced guessing: ½; uniform \(k\)-class exact accuracy: \(1/k\). Also report majority, code-only, and previous-lock baselines. No universal chance rate for routing cost or queue size. Opus’s labels cannot simultaneously be the independent gold for measuring Opus accuracy. |
| **G3 — Formalization** | On 100 sealed tasks containing explicit premises **and goals**, require ≥80 first-pass and ≥95 post-repair well-typed statement artifacts. Separately, on 50 retrieval-disjoint reference tasks, require ≥20 to pass a blinded semantic rubric covering binders, premises, goal, and nondegeneracy; unresolved reviews count as not established. Report machine-supported equivalence and reviewer judgments separately. | Elaborability and semantic equivalence: **N/A** without a specified random program distribution. Run empty/trivial statement controls, nearest-retrieval baseline, and deliberately weakened/strengthened statements. Valid Lean syntax must not earn semantic credit. |
| **G4a — Provers** | Freeze 50 semantically accepted statements before prover tuning. Run both D3 models with the same 120-second per-statement search budget and declared resource conditions. Require the selected default to prove ≥15/50 with accepted proof dependencies; publish both models’ proved/timeout/error counts, latency, and memory. Choose by proved count, then predeclared latency tie-break, retaining DeepSeek on an exact tie. Also report end-to-end pipeline success. | Proof acceptance: **N/A**. Run a fixed trivial-tactic baseline with a stated budget. If 50 eligible statements are unavailable, the comparison gate is incomplete. |
| **G4b — Co-observer loop** | Conduct the planned 30-minute, 20-diagram session. Require persisted verdicts, correct `not visible` handling, revision invalidation, label-source provenance, and replayable routing effects. Trigger calibration only when support floors are met; either a supported update or a documented no-update/rollback is valid. Require the pinned atlas integration test from the archived build. | **N/A**. Baseline is the previous lock and an unchanged-record round trip. A threshold need not move merely because a session happened. |
| **G5 — Topology** | Freeze the supported diagram grammar and PD scorer. Require ≥30% complete PD transcription on separate synthetic and permitted external ≤7-crossing test sets; a missing external evaluation leaves that part incomplete. Report exact and canonicalized scores separately, component validity, crossing/orientation errors, unknowns, and invariant consistency. Do not call invariant agreement transcript verification. | General PD transcription: **N/A** without a defined random encoding sampler. With the projection and numbering already correct and \(c\) independent unbiased crossing choices, an orientation-only null is \(2^{-c}\); label it conditional. Knot-type guessing is \(1/k\) for a uniform \(k\)-label task, plus a majority baseline. |
| **G6 — Atlas integration** | Submit one reproducible record with linked image, revisions, evidence, formal assumptions, statement hash, actual check statuses, baseline results, and Sol review. Pass the actual ingestion/validation contract. A negative or inconclusive observation is acceptable; success must not require manufacturing a positive finding. | Integration: **N/A**. Any scientific visual claim needs its own declared null, baseline, and evaluation unit. |

**5. Answers to §11’s open questions**

**GeoIR or a Lean-typed field per relation?**

Use a **typed, language-independent observation record as the canonical representation**, followed by a small formalization IR that makes binders, premises, goals, exact constants, and evidence references explicit.

Do not make arbitrary Lean strings the authoritative meaning of individual relations. They are difficult to validate consistently and couple perception to a particular library version. Store generated Lean artifacts and per-relation mappings as derived outputs.

MechGeo’s actual reusable GeoIR implementation and grammar are **UNVERIFIED**. Borrowing the architectural idea does not require adopting an unavailable format.

**LeanGeo or native Mathlib for P3?**

Choose **native Mathlib as the canonical semantic target for the initial supported plane-geometry subset**, with a small MVE adapter defining the chosen conventions. Keep a LeanGeo adapter for reference tasks and tactics where its semantics match.

This avoids making the whole observation model depend on a plane-geometry dialect while preserving access to LeanGeo examples. Exact mappings and compilation compatibility are **UNVERIFIED** until the early WP-6 spike.

Pin one coherent toolchain/dependency set. Neither the global Lean version nor the stated minimum establishes compatibility. Unsupported predicates should produce an explicit unsupported result.

**How should equivalence be scored when E3 does not cover the dialect?**

Use distinct evidence levels:

1. **Structural agreement:** canonicalized objects, binders, premise sets, and goals match under an explicit variable mapping.
2. **Machine-supported correspondence:** relevant implications or transformations are checked under a shared interpretation, with artifacts retained.
3. **Reviewer-judged agreement:** blinded rubric assessment, reviewer identity, and rationale are recorded.
4. **Unknown/unsupported:** retained in the denominator and never converted into agreement by default.

Do not collapse these into one `equivalent` field. Report counts and rates by method.

Whole-theorem logical equivalence alone is too coarse for faithful translation: two separately provable theorems can imply each other while describing different geometry. The evaluation must preserve the intended objects, assumptions, and goal. Use weakened, strengthened, vacuous, and unrelated-but-provable statements as controls.

E3’s supported dialects and the availability of suitable checked transformations remain **UNVERIFIED**.

**What should the first topology statement in Lean be?**

Start with a finite combinatorial certificate:

> For this validated PD record \(D\), the arc-successor relation obtained by following strands through crossings has exactly one component.

Define the traversal so it follows strands through a crossing without joining the over- and under-strands. Check arc-label validity and the component count for a fixed fixture.

This proves a property of the **decoded combinatorial record**. Connecting it to the pictured link requires a correct transcription; connecting the representation to a topological link requires a separate interpretation argument. Neither should be implied by the first certificate.

The exact Lean definitions, fixture, and reusable library support are **UNVERIFIED**. P5 can therefore legitimately finish with validated PD and invariant records. Unknot recognition, genus identification, and general knot equivalence should not be prerequisites for its first useful deliverable.