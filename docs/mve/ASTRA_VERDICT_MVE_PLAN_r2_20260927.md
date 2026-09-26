All five supplied SHA-256 hashes match the manifest. D1–D6 remain constraints. This is a packet review; external capabilities, execution results, licensing conclusions and budget feasibility remain **UNVERIFIED**. No code or files were written.

References: **r2** = [MVE_PLAN.md](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/MVE_PLAN.md>); **schema** = [mve_observation_record.json](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/mve_observation_record.json>). “Applied” means the correction is adequately specified, not implemented or demonstrated. Items follow their original order.

**1. Disposition of r1 §1**

**WP-1 — Record model and validation**

| Item | Status and evidence |
|---|---|
| 1. Operation-level transitions | **partly** — r2 §4a adds revisions/invalidation, but no operation/permission table or complete transition prerequisites. |
| 2. Evidence per assumption and goal | **partly** — r2 §4a requires individual support; schema `formal.propositions[].cites` remains optional and text sources lack addressable IDs. |
| 3. Frozen P1 predicate registry | **partly** — r2 §4a maps PointLiesOnLine and specifies registry contents, but does not explicitly freeze the nine active rows. |
| 4. Arity, geometry and conventions | **partly** — r2 §4a and `entities[].geometry` add conventions; betweenness strictness, several entity geometries and kind-specific validation remain unspecified. |
| 5. Claim provenance and confidence | **partly** — `observations[].call/confidence` and evidence IDs exist; measurement localization uncertainty and geometry-to-call provenance remain absent. |
| 6. Decision versions and immutable history | **partly** — `versions`, `decisions`, `events` exist; decision-state hash, label version, replayable edits and stored request nonce remain missing. |
| 7. Structural and semantic validation | **partly** — positive dimensions, some hashes and ranges are constrained; unique IDs, normalization and numerous conditional requirements remain unspecified. |
| 8. Schema authority, migration and stages | **partly** — v2 permits null perceiver provenance; authoritative-copy policy, v1 migration and explicit stage requirements remain undecided. |

**WP-2 — Generator and ground truth**

| Item | Status and evidence |
|---|---|
| 1. Vendored engine contract | **partly** — r2 §11 requires revision/notices; executable entry point and dependency closure remain **UNVERIFIED**, without a specific generator preflight. |
| 2. Finite ground-truth universe | **partly** — r2 §§2, 11 name the universe and five classes, but omit enumeration and class-assignment rules. |
| 3. Determinism definition | **partly** — r2 §11 names geometry/labels/record determinism; schema nonce-based identity and creation timestamps conflict with literal record determinism. |
| 4. Independent splits and diagram controls | **partly** — r2 §§7, 11 require disjoint family splits and controls; style coverage, degeneracies and not-to-scale cases remain unspecified. |

**WP-3 — Perceiver**

| Item | Status and evidence |
|---|---|
| 1. Two calls and disagreement protocol | **partly** — r2 A1 chooses two charged calls and Hungarian alignment; merge/abstention rules and alignment thresholds remain deferred. |
| 2. Appearance versus annotated tracks | **partly** — r2 §4a/A0 separates tracks and stores OCR frame; coordinate transforms and legitimate-premise access need clarification. |
| 3. Entity coordinates and failure handling | **partly** — r2 A1 and `entities[].geometry` improve coverage; occlusion, strand/region geometry and structured failure outcomes remain incomplete. |
| 4. Vision adapter contract | **applied** — r2 §3/A1/WP-0 explicitly requires interface preflight, bounded retries and raw retention; actual behavior **UNVERIFIED**. |

**WP-4 — Measurement and Newclid**

| Item | Status and evidence |
|---|---|
| 1. Coordinate consistency versus image measurement | **applied** — r2 A2 and `measurements[].method` explicitly distinguish them. |
| 2. JSXGraph versus NumPy contract | **applied** — r2 §4a/WP-4 requires the same contract and cross-kernel agreement tests. |
| 3. Mark association and annotation precedence | **applied** — r2 A2 specifies template matching, association, OCR evidence and annotation precedence. |
| 4. Predicate-specific residuals and negatives | **partly** — r2 §4a/G1/WP-4 requires suitable negatives; normalization, localization uncertainty and near-degenerate treatment remain undefined. |
| 5. Explicit premise source and derivation trace | **partly** — r2 §4a/A2 prohibits measurement premises; schema cannot reference ID-less problem premises and makes trace artifacts optional. |
| 6. Newclid outcomes and interfaces | **partly** — outcomes are explicit in `derivations[].outcome`; export/checker contracts and sufficient proof evidence remain **UNVERIFIED**. |

**WP-5 — Decision layer and learning**

| Item | Status and evidence |
|---|---|
| 1. Abstention and overlapping labels | **partly** — r2 §5 separates abstention; Q-shape still lacks exclusivity rules for triangle/quadrilateral/polygon_n/mixed. |
| 2. Truth judgments versus workflow decisions | **applied** — r2 §5 removes mathematical truth questions and makes drift a review flag only. |
| 3. Complete serialized input limit | **applied** — r2 §5 specifies runtime counting, 512 tokens and over-limit abstention without truncation. |
| 4. Exhaustive routing and boundaries | **partly** — r2 A3 defines routes/confidence but contradicts its own threshold-equality rule. |
| 5. Per-class, per-split support | **applied** — r2 §5 requires ten examples per label in each split; those floors govern the provisional size target. |
| 6. Training/calibration/evaluation separation | **applied** — r2 §5a specifies three family-grouped splits and retirement of development-influenced evaluation sets. |
| 7. Trainable openJev pipeline | **applied** — r2 §5a/WP-5 explicitly makes training/export/parity a spike; its feasibility remains **UNVERIFIED**. |
| 8. Label targets, conflicts and corrections | **partly** — r2 §5 names targets/sources; an A6 confirm/reject click still does not define Q-claim-workflow’s four labels. |
| 9. Promotion metrics and queue behavior | **partly** — r2 §5a/G2 improves coverage/error rules; uncertainty handling for promotion and unanswered-case scoring remain incomplete. |
| 10. Staged activation | **applied** — r2 §5 stages questions and disables those lacking support; §7 puts verdict capture before learning. |
| 11. Independent, reproducible audits | **partly** — r2 §5a specifies sampling/adjudication requirements; eligibility and sampling-bias reporting remain undefined. |

**WP-6 — Formalizer**

| Item | Status and evidence |
|---|---|
| 1. Supported subset and fail-closed behavior | **applied** — r2 A4/§12 explicitly targets a supported subset and rejects unsupported predicates. |
| 2. Problem, binders, premises and goal | **partly** — `problem` exists, but nondegeneracy is inexpressible, binders are untyped strings and goal fields are optional. |
| 3. Compatible isolated Lean dependencies | **applied** — r2 §3/WP-6 requires an isolated pinned project; compatibility remains **UNVERIFIED**. |
| 4. Meaning-preserving repairs | **applied** — r2 A4 limits repairs and treats semantic changes as formalization failures. |
| 5. Separate equivalence evidence levels | **partly** — r2 §12 defines levels; `formal.equivalence` does not require evaluator/artifact evidence or preserve a structured variable mapping/rationale. |
| 6. Retrieval and reference isolation | **applied** — r2 §§2, 8–9/WP-6 requires family separation, retrieval exclusions and frozen evaluation context. |
| 7. Typechecking versus proof checking | **applied** — r2 A4–A5 separates artifacts and requires dependency-closure checking for proof acceptance. |

**WP-7 — Prover and counterexamples**

| Item | Status and evidence |
|---|---|
| 1. Counterexample search contract | **partly** — r2 A5 requires domain/budget/witness; tolerance policy and exact or certified witness validation remain absent. |
| 2. Trusted proof acceptance | **partly** — r2 A5 requires trusted checking and listed axioms; an allowed-axiom policy remains unspecified. |
| 3. Comparable prover conditions | **partly** — r2 A5/G4a declares resources/attempts; model revisions, repair allocation and timeout accounting remain incomplete; hosting **UNVERIFIED**. |
| 4. Fifty eligible statements and selection | **applied** — r2 G4a requires fifty frozen accepted statements, incomplete otherwise, with explicit selection/tie-break and end-to-end reporting. |

**WP-8 — Co-observer surface**

| Item | Status and evidence |
|---|---|
| 1. Visibility versus rejection/adoption | **partly** — r2 A6 separates these actions, but schema judgment values do not explicitly encode adopt/decline or their mapping. |
| 2. Revision, conflicts and invalidation | **partly** — r2 §4a/A6 states intent; transitive dependencies, conflict rules and replayable edit contents remain unspecified. |
| 3. Supported render-back and realizations | **partly** — r2 A6 defines round-trip intent; `formal.render_back` cannot explicitly distinguish no/multiple realizations. |
| 4. Atlas host and packaging contract | **partly** — r2 §3/WP-0/WP-8/WP-9 assigns discovery; exact host inputs, packaging and checks remain **UNVERIFIED**. |

**WP-9 — Fleet and ledger**

| Item | Status and evidence |
|---|---|
| 1. Aggregate budget accounting | **applied** — r2 D4/A7/§10 covers all chargeable calls, aggregate allocation, reservations, retries and reconciliation. |
| 2. Runtime enforcement tests | **applied** — r2 §7/WP-9 specifies simulated charges, concurrency, retries and crash/resume tests. |
| 3. Windows, prices and quota accounting | **partly** — r2 §3/A7/§10 requires pinning and separate accounts; clock behavior remains unspecified; live claims **UNVERIFIED**. |
| 4. Stop precedence and restart | **applied** — r2 A7/§9 gives mechanical stops precedence and assigns restart authority to Opus. |
| 5. Integration branches and external dependencies | **applied** — r2 §§3, 6, 11 requires the integration branch and path/script hashes in DEPS.lock. |

**WP-10 — Topology**

| Item | Status and evidence |
|---|---|
| 1. Diagram grammar and traversal | **partly** — r2 WP-10 requires a grammar and preserved gaps; numbering, orientation, mirror and rejection conventions remain unspecified. |
| 2. Exact versus canonicalized scoring | **partly** — r2 G5 separates scores; permitted relabelings, component ordering and canonicalization remain undefined. |
| 3. Synthetic versus external evaluation | **applied** — r2 G5 requires separate sets and marks missing external evaluation incomplete; permitted external use **UNVERIFIED**. |
| 4. Exact SnapPy operation | **not applied** — r2 WP-10 says the invariant step must be “named exactly” but never names an operation or certificate. |
| 5. Surface/genus prerequisites | **applied** — r2 §5 removes Q-genus and §§12–13 defers surface support in favor of a PD component certificate. |
| 6. Complete error taxonomy | **partly** — r2 G5 adds unknowns and §13 permits unresolved causes; traversal/association/canonicalization categories are still not specified. |

**WP-11 — Evaluation**

| Item | Status and evidence |
|---|---|
| 1. Frozen benchmark and matched chance | **applied** — r2 §8/G0 freezes the comparison and recomputes sample-specific chance; execution remains **UNVERIFIED**. |
| 2. Candidates, matching and denominators | **partly** — r2 G1 fixes queries and includes failures; micro/macro aggregation and query-versus-record scoring remain undefined. |
| 3. Isolation beyond filenames | **partly** — r2 A0/§9 requires isolation, but blanket exclusion of premises conflicts with annotated-problem inputs. |
| 4. Separate appearance/annotation/problem tasks | **partly** — r2 §9 names three tasks; `image.track` provides two tracks without a separate evaluation-task discriminator. |
| 5. Declared null or N/A | **applied** — r2 §§8–9 distinguishes stochastic nulls from structural/typechecking/proof checks. |
| 6. Evaluation infrastructure built early | **partly** — r2 §7 moves it forward, but WP-0’s model calls precede the infrastructure required before any model call. |

**2. Disposition of r1 §2**

| Item | Status and evidence |
|---|---|
| 1. Elaboration is verification | **applied** — r2 §2/A4 separates well-formedness, proof and representation fidelity. |
| 2. Coordinate recomputation is remeasurement | **applied** — r2 A2 explicitly names coordinate consistency and its hallucination limitation. |
| 3. Non-derived means true only in this figure | **applied** — r2 §4a explicitly uses unknown and “numerically consistent; derivability unresolved.” |
| 4. One supported relation authorizes formal content | **partly** — r2 §4a fixes the principle; optional citations and ambiguous support authorization remain in v2. |
| 5. Fixed labels prevent hallucination | **applied** — r2 §5 explicitly says finite labels do not prevent false answers. |
| 6. Q-cyclic contradicts “never a truth judge” | **applied** — r2 §5 removes Q-cyclic and routes mathematical questions to code with uncertainty. |
| 7. Calibration called independent held-out evaluation | **applied** — r2 §5a explicitly separates calibration and untouched evaluation. |
| 8. Three hundred labels meet all floors | **applied** — r2 §5 withdraws that claim and requires per-class, per-split floors before activation. |
| 9. ConvNeXt’s 3–5× training-speed claim | **applied** — r2 §2 withdraws the speed ratio and identifies the size comparison; actual speedup **UNVERIFIED**. |
| 10. CLIP categorically fails on line drawings | **applied** — r2 §2 explicitly withdraws the broad claim; the unchanged source review remains historical material. |
| 11. Perception is universally the bottleneck | **applied** — r2 §2 restricts the finding to task-specific failures. |
| 12. Cascade retention and fee ratio conflated | **applied** — r2 §2 separates the results and denies unmeasured transfer to local openJev. |
| 13. Newer Lean implies dependency compatibility | **applied** — r2 §3 requires a pinned isolated build; compatibility **UNVERIFIED**. |
| 14. Two same-model perceptions are independent | **applied** — r2 A1/§9 treats disagreement as instability and denies verification from agreement. |
| 15. Skeleton connectivity recovers crossing orientation | **applied** — r2 WP-10 requires preserved gap evidence; actual transcription performance **UNVERIFIED**. |
| 16. Genus follows from unrestricted Euler characteristic | **applied** — r2 §5 removes Q-genus; §12 confines the initial certificate to decoded PD connectivity. |
| 17. Stripping labels prevents leakage | **partly** — r2 §4a/A0 improves tracks/isolation, but §9’s blanket premise exclusion needs an input-access rule. |
| 18. Published scores are local chance/baselines | **applied** — r2 §2/G0/G1/G5 distinguishes observed scores, matched evaluations and conditional nulls. |
| 19. Newclid containment settles GeoGebra licensing | **applied** — r2 D2 explicitly marks sufficiency **UNVERIFIED** and requires checking actual terms. |

The five additional capability bullets in r1 §2:

| Item | Status and evidence |
|---|---|
| U1. Local signatures, tests, ledger and integration | **applied** — r2 §3/WP-0 labels them **UNVERIFIED** pending executable checks. |
| U2. Models, images, prices, windows, calibration | **applied** — r2 reading rule/WP-0/§5a requires live preflight or local measurement; results **UNVERIFIED**. |
| U3. Generator, Newclid, LeanGeo, rendering, hosting | **applied** — r2 reading rule and relevant spikes retain **UNVERIFIED** status; WP-0 alone cannot establish all later capabilities. |
| U4. Literature numbers, maintenance and licenses | **applied** — r2 §14 treats them as secondary assertions, **UNVERIFIED** as reproduced acceptance evidence. |
| U5. Calendar and sample-count affordability | **applied** — r2 §7 removes the calendar pending a cost model; feasibility remains **UNVERIFIED**. |

**3. Remaining blockers for WP-0, WP-1 or WP-2**

Read-only dependency inspection can start. The following block executing or accepting the first packets under the stated contracts.

1. **WP-0: preflight precedes its mandatory infrastructure.** r2 §7 puts WP-0 first, then requires WP-9a/WP-11a before *any* model call; WP-0 explicitly includes model inference and a paid live call. Split offline preflight from model probes, put required infrastructure first, and count the probe within the P0 allocation. Also distinguish WP-0’s environment smoke tests from the later WP-6 isolated-project build and WP-9 integration acceptance. A “ran” result must identify which capability was actually exercised.

2. **WP-1: evidence references and authorization are incomplete.** `problem.premises`, goal and nondegeneracy propositions have no IDs, yet derivations and formal artifacts must cite them. Text-adopted assumptions also require citations without an addressable text source. `formal.propositions[].cites` is optional. r2 §4a permits a human-or-model `confirm` to support `human_confirmed`, and does not explicitly restrict derived support to successful, matching derivations. Define addressable sources and authorization rules, distinguish visible confirmation from assumption adoption, and preserve an unproved goal’s source without treating it as an established hypothesis.

3. **WP-1: the canonical mathematical representation cannot express its required content.** `problem.nondegeneracy` uses a predicate enum with neither distinctness nor negation, so it cannot encode its advertised distinctness/non-collinearity assumptions. `problem.goal.binders` has no declared types, and `$defs.proposition.value` has no exact-expression convention. Freeze the initial registry and strictness/degeneracy rules, and define a representation sufficient for the supported subset before generator or Lean mappings depend on it.

4. **WP-1: revisions and evidence dependencies are not replayable.** r2 §4a’s invalidation rule follows `cites`, while derivations use `premises`, judgments use `target`, and proof/render artifacts have no equivalent dependency links. `events[].touches` plus a note does not preserve an edit or identify its predecessor revision. Two perception calls and independent measurement also lack a defined mapping to distinct geometry evidence. Specify the dependency graph, transitive invalidation—including proofs—and revision/conflict semantics.

5. **WP-1: validation authority and stage invariants remain unresolved.** Choose the authoritative schema and migration/rejection policy, and explicitly allocate checks between JSON Schema and the semantic validator. The supplied schema admits, for example, a proposition observation without a proposition, an empty goal object, and `formal.status = proved` without proof evidence. It requires numeric residuals even for unmeasurable results, while units are optional. Stage requirements must permit ingestion/synthetic records before a fitted measurement contract exists. These are contract decisions, not merely missing implementation.

6. **WP-2: exact ground-truth and input-isolation contracts remain underspecified.** r2 names a finite universe and five classes without defining enumeration, overlap precedence, or evidence distinguishing consequence, incidental truth, false and unknown. Specify the independent exact evaluator and frozen candidate/split metadata artifact. Clarify that legitimate annotated givens remain available to the appropriate stages while hidden construction premises, answers and reference artifacts remain isolated. The Euclid entry point, dependency closure and usable generator remain **UNVERIFIED** and need an explicit discovery/stop criterion before vendoring.

7. **WP-2: deterministic records conflict with execution identity.** r2 §11 promises deterministic records, but schema `record_id` requires a fresh request nonce and provenance requires `created_at`; the nonce itself is not retained. Define deterministic mathematical content separately from execution metadata, with a canonical hash and reproducible synthetic identity policy.

**4. New defects introduced by r2**

- **Preflight ordering contradiction:** WP-0 performs calls before infrastructure that §7 mandates before any model call — blocker **1**.
- **New evidence-reference dead ends:** v2 introduces ID-based premise citations without IDs on problem premises/goal, and leaves supposedly mandatory formal citations optional — blocker **2**.
- **Model confirmation can become “human_confirmed”:** r2 §4a’s judgment support rule admits model judges without a human-only or explicit-adoption prerequisite — blocker **2**.
- **New nondegeneracy field is inexpressible:** its allowed proposition vocabulary cannot encode the conditions its description requires — blocker **3**.
- **New unmeasurable outcome still requires a number:** `measurements[].outcome = unmeasurable` cannot represent an absent residual without inventing a numeric placeholder — blocker **5**.
- **Record determinism versus nonce identity:** the new identity recipe conflicts with WP-2’s strengthened determinism claim — blocker **7**.
- **Routing equality contradiction:** r2 A3 assigns `c = τ_high` to `act` and `c = τ_low` to `llm`, then says boundaries belong to the lower route. Resolve before WP-5.
- **G2 weakens the adopted refit gate:** r2 permits threshold-only refitting to pass G2, whereas the r1 replacement gate required an actual refit/export. Threshold-only operation is a reasonable interim result, but cannot establish that D1’s recursive model-learning requirement has been delivered.
- **Closure log overstates completion:** r2 §13 says nothing was knowingly unapplied and claims a named SnapPy step, although WP-10 still supplies no operation name. It should reflect the partial applications above.

VERDICT: REVISE — blocking items: 1, 2, 3, 4, 5, 6, 7.