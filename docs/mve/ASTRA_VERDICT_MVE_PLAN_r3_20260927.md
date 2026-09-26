r3 still needs revision before WP-1 and WP-2 acceptance. Read-only WP-0a inspection can proceed; its local-inference prerequisite needs clarification.

All five supplied file hashes match the manifest. D1–D6 remain constraints. Findings below are from packet inspection. Implementations, executable dependency capabilities, licensing conclusions, costs, and equality with the out-of-packet authoritative schema are **UNVERIFIED**. No code or files were written.

References: [r3 plan](<MVE_PLAN.md>), [v3 schema](<mve_observation_record.json>), [r2 verdict](<ASTRA_VERDICT_MVE_PLAN_r2_20260927.md>), [r2 plan](<MVE_PLAN_r2_20260927.md>). “Fixed” or “cleared” refers to the specification, not demonstrated implementation.

**1. Disposition of r2 blockers 1–7**

| Blocker | Status | Evidence and remaining issue |
|---|---|---|
| **1. Preflight ordering** | **partly** | r3 §§7, 11 split WP-0a/WP-0b, place the paid probe after enforcement, count it within P0, and distinguish toolchain presence from WP-6a’s build. However, §7 still requires infrastructure before **any model call**, while WP-0a explicitly performs openJev inference and calls itself “no model calls.” |
| **2. Evidence references and authorization** | **partly** | §4a and `problem.texts/premises/nondegeneracy/goal` provide addressable text and propositions; formal dependencies are mandatory; human-only confirmation and successful matching derivations are explicit. Remaining gaps: truth artifacts lack an addressable object; `problem_text` and `goal_source` authorization do not require proposition equality; visible confirmation still directly authorizes formal content. |
| **3. Canonical mathematical representation** | **partly** | §4a freezes the active predicate names and arities, chooses strict `SBetween`, adds `Distinct`/`NotCollinear`, typed `problem.binders`, and `value_exact`. Argument roles, symmetry canonicalization and predicate-specific degeneracy rules remain unspecified in the packet. The exact-expression field supplies a lexical convention, not complete expression semantics. |
| **4. Replay and dependency invalidation** | **partly** | §4a adds operations, `depends_on`, source-specific geometry IDs and revisioned patches. But several essential links remain outside that graph, and proof/render artifacts have no IDs that `events[].invalidates` can name. Conflict handling remains “resolved by revision” without a resolution rule. |
| **5. Validation authority and stages** | **partly** | §4a selects schema authority, rejects older versions, allocates semantic checks and permits early records without fitted measurement contracts. Observation/goal structure and absent residuals improve. Stage transitions and proof acceptance remain incomplete or inconsistent; several newly claimed conditional guarantees are weaker in the schema. |
| **6. Ground truth and isolation** | **partly** | §§4a, 9, 11 clarify legitimate annotated inputs, candidate enumeration, class precedence, split artifacts and a two-hour Euclid discovery stop. Exact evaluator semantics, reproducible derivation outcomes, truth-artifact structure and mathematical-versus-rendered geometry remain insufficiently defined. Actual generator/dependency viability is **UNVERIFIED**. |
| **7. Deterministic versus execution identity** | **partly** | §4a and `content_hash`, `record_id`, `provenance.request_nonce` separate execution metadata and retain the nonce. However, the new content-hash recipe conflicts with conditional PNG determinism, omits the truth artifact, and references entity-level `source`, which does not exist. Identity across revisions is also unresolved. |

**2. Each new defect listed under r2**

| r2 defect | Status in r3 |
|---|---|
| Preflight ordering contradiction | **not fixed completely** — paid ordering is corrected; the openJev/“any model call” contradiction remains (§7). |
| Evidence-reference dead ends and optional formal citations | **not fixed completely** — problem/text IDs and required dependencies are added, but truth-artifact references still have no defined addressable target (`image.ground_truth_ref`, `image.truth`). |
| Model confirmation becoming `human_confirmed` | **fixed** — §4a and `formal.propositions[].support` explicitly exclude model judges. |
| Inexpressible nondegeneracy | **fixed** — `Distinct` and `NotCollinear` are available and assigned to `problem.nondegeneracy`. |
| Unmeasurable outcome requiring a numeric residual | **fixed** — `measurements[].residual` may be null or absent for `unmeasurable`; no numeric placeholder is necessary. |
| Nonce/timestamp conflicting with deterministic content | **fixed as originally stated** — both are excluded from mathematical identity. The replacement hash introduces separate defects described below. |
| Routing equality contradiction | **fixed** — A3 consistently sends threshold equality to the lower route. |
| G2 accepting threshold-only refitting | **fixed** — §8/G2 requires a real weight refit, ONNX export and inference parity, preserving D1. |
| Closure log overstating completion | **not fixed** — §13 acknowledges some remaining work, but still overstates uniform dependency coverage, complete authorization and deterministic identity. Naming SnapPy operations is corrected; their executable availability remains **UNVERIFIED**. |

**3. Remaining blocking items**

The numbering below preserves the original blocker numbers.

1. **WP-0a: reconcile local inference with the prerequisite.**  
   In §7, explicitly exempt offline fixture inference from the “any model call” prerequisite, or move it behind the required infrastructure. The paid-probe ordering is otherwise resolved. WP-0a results must remain capability-specific: import success cannot establish later build, training, hosting or integration success.

2. **WP-1: close source and authorization gaps.**  
   In §4a’s authorization table, `problem_text` currently checks only that dependencies are premise/nondegeneracy IDs. A formal proposition could cite an unrelated premise without violating that stated rule. Likewise, `goal_source` requires `[goal_1]` and role `goal`, but does not require the formal goal to match `problem.goal.proposition`. Require matching under an explicit binder/entity mapping and restrict goal-role authorization consistently.

   Visible confirmation and assumption adoption also remain conflated: A6 offers separate actions, but §4a lets a human `confirm` directly authorize a formal hypothesis. Require adoption, or explicitly define confirmation as an adoption action with corresponding recorded meaning.

   Finally, `image.ground_truth_ref` and sourced propositions may reference a truth-artifact `geo_N`, but `image.truth` has no `id` field or external ID-resolution contract. Its `additionalProperties: false` prevents simply adding one.

3. **WP-1, then WP-2: finish the frozen predicate contract.**  
   The active-name list is an improvement, but does not specify, for example, which argument is the midpoint, which is between the others, or the permitted argument permutations for each predicate. WP-2’s canonical candidate enumeration depends on precisely those choices.

   Specify argument roles, symmetry groups, repeated-point policy, degeneracy outcomes and supported mathematical mappings. Restore the r2 `PointLiesOnLine → Collinear` mapping with distinct line-defining points, which disappeared in the §4a rewrite. Define exact-expression parsing, valid domains and normalization; `$defs.exact` alone accepts strings outside the stated mathematical convention.

4. **WP-1: make the dependency graph and revision protocol representable.**  
   §4a says invalidation follows **only** `depends_on`, but:

   - Premises and goals link to text through `source`; neither has `depends_on`. Editing `txt_N` therefore has no specified graph path to its propositions.
   - `judgments[].target` need not occur in `judgments[].depends_on`.
   - Entity/binder changes have no complete required dependency mapping.
   - `formal.proof` and `formal.render_back` have dependencies but no IDs; `events[].invalidates` accepts IDs only. Typecheck and equivalence artifacts also lack explicit dependency coverage.

   Define graph nodes and mandatory edges, including these artifacts. Specify rejection or explicit merging of competing edits from the same predecessor revision, and how invalidated artifacts cease to authorize downstream work.

5. **WP-1: complete stage and acceptance invariants.**  
   The new operation table has no transition to `reviewed`, although atlas ingestion requires it. `measure` requires `perceived`, leaving no specified path for WP-4a’s synthetic measurement fixtures before WP-3. `perceive` permits “stage ≥ ingested” and resets the stage without describing invalidation of later artifacts.

   Static schema inspection also shows:

   - `formal.status = proved` permits `dependency_closure_checked = false`, `typecheck.ok = false`, and null statement/IR hashes.
   - A counterexample witness may be `{}`.
   - A consistent measurement may have `residual_unit = null`.

   These are structural allowances, **not proof that the future semantic validator will accept them**. Explicitly allocate their rejection and reconcile the minimal §4a stage rules with A5’s stronger acceptance requirements. Also replace the stale **v2** contract references in WP-1 and §12.

6. **WP-2: specify reproducible truth artifacts and evaluator outcomes.**  
   §11 names an independent exact evaluator without specifying its supported exact-coordinate representation, predicate semantics or evidence artifact. `image.truth` can be empty and carries no required evaluator/version information.

   Define the frozen artifact’s candidate list, exact mathematical coordinates, class/evidence mapping, evaluator version and derivation policy. Specify how DDAR timeout or unsupported results affect classification, and how disagreement between derivation and exact evaluation is handled. A wall-clock-dependent “proved/not proved” boundary cannot silently change deterministic truth classes.

   For not-to-scale controls, distinguish mathematical coordinates from rendered pixel coordinates. Otherwise “exact truth on sampled coordinates” is ambiguous. The revised input-isolation policy and Euclid discovery stop criterion are adequate specification improvements; execution remains **UNVERIFIED**.

7. **WP-1/WP-2: replace the inconsistent hash recipe.**  
   `content_hash` includes `image.sha256`, while WP-2 promises equal content hashes for equal seeds but guarantees PNG-byte determinism only with a pinned renderer. Those promises cannot both hold without an additional condition.

   The schema describes filtering “entities with `source=ground_truth`,” although source lives under `entities[].geometries[]`. It also omits `image.truth.artifact_sha256`, despite WP-2 describing the hash as covering truth.

   Define one canonical projection and serialization, including exactly which geometry, labels and truth evidence participate. Scope determinism to pinned generator/configuration versions. Specify whether content edits create a new execution identity or a revision of the existing one, and preserve explicit lineage.

**4. New defects or contradictions introduced by r3**

- **The replacement hash has new internal contradictions:** image-byte dependence, an incorrect source-field path and omitted truth evidence. These are distinct from the repaired nonce problem; blocker **7**.
- **The new uniform-graph contract cannot encode all promised invalidations:** source links bypass it and proof/render nodes are unaddressable in the invalidation list; blocker **4**.
- **The new transition table lacks necessary paths:** review completion and synthetic measurement are examples; blocker **5**.
- **The v3 upgrade leaves conflicting v2 instructions:** WP-1 and §12 still prescribe v2 while §4a rejects older schemas; blocker **5**.
- **Q-claim-workflow labeling now contradicts itself:** §5 explicitly says relation confirm/reject clicks do **not** label that question, while §5a step 2 says a relation click **does**. Correct before WP-5 label collection; it does not independently block offline WP-0a.
- **The §4a rewrite removes the explicit incidence mapping and its nondegeneracy condition** while claiming the registry is frozen; blocker **3**.

VERDICT: REVISE — blocking items: 1, 2, 3, 4, 5, 6, 7.