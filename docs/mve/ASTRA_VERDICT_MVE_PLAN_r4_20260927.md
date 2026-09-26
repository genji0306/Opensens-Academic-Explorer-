R4 still requires revision for WP-1 and WP-2. **WP-0a has no remaining specification blocker.** D1–D6 remain constraints.

I applied the README’s scope rule: a stated, decidable contract is sufficient; its implementation and tests need not already exist. All five supplied file hashes match the manifest. Runtime capabilities, dependency compatibility, licensing, costs, and equality with the out-of-packet authoritative schema are **UNVERIFIED**. No code was written.

References below identify sections of the [r4 plan](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/MVE_PLAN.md>) and fields in the [v4 schema](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/mve_observation_record.json>).

**1. Blockers 1–7**

| Blocker | Status | R4 evidence and disposition |
|---|---|---|
| **1. Preflight ordering** | **cleared** | §7 expressly exempts offline, unmetered openJev fixture inference. Hosted calls require enforcement and isolation infrastructure first. §11 makes preflight conclusions capability-specific. |
| **2. Evidence references and authorization** | **cleared** | §4a requires proposition equality under binder/entity mapping, reserves `goal_source` for the matching goal, and replaces direct human confirmation with adoption through an assumption. `sources[]`, `image.truth.source`, and `image.ground_truth_ref` provide addressable truth artifacts. Semantic enforcement is explicitly assigned to WP-1. |
| **3. Canonical mathematical representation** | **partly** | §4a supplies argument roles, symmetry groups, degeneracy rules and the restored incidence mapping. However, §4a and `$defs.exact` disagree internally about the exact-expression domain and stored representation; see blocking item 1 below. |
| **4. Replay and invalidation** | **partly** | §4a adds source dependencies, formal-artifact IDs, mandatory judgment-target edges and optimistic-concurrency rejection. But `entities[].geometries[]` cannot represent the required invalidation state; see item 2. |
| **5. Validation authority and stages** | **cleared** | §4a adds review/atlas-ingest transitions, synthetic measurement and invalidating re-perception. `formal.allOf` enforces the strengthened proved conditions and non-null hashes; `derivations[].allOf` requires witness coordinates and `exact`; `measurements[].allOf` excludes null units for numeric outcomes. WP-1 and §12 now prescribe v4. Remaining semantic checks are assigned explicitly. |
| **6. Ground truth and isolation** | **partly** | §11 defines artifact contents, evaluator metadata, exact-first evaluation, DDAR outcomes, conflicts and separate mathematical/rendered coordinates. Isolation and the Euclid discovery stop remain adequate. The approximate-coordinate branch and reproducibility of final classes still need a consistent contract; see item 3. |
| **7. Deterministic versus execution identity** | **partly** | §4a removes synthetic image bytes from mathematical identity and defines revision/lineage behavior. But the projection still omits class/evidence content and evaluator metadata while promising that truth edits change identity; see item 4. |

**2. Each new defect listed in the r3 verdict’s section 4**

| R3 defect | Status in r4 |
|---|---|
| Replacement hash contradictions | **not fixed** — image-byte dependence and the nonexistent entity-level source path are fixed; truth-evidence coverage remains incomplete. |
| Uniform graph cannot encode promised invalidations | **not fixed** — source links and formal-artifact IDs are repaired, but geometry invalidation cannot be serialized. |
| Transition table lacks necessary paths | **fixed** — review, atlas ingest and measurement from `ground_truth` are specified (§4a). |
| V3 upgrade leaves conflicting v2 instructions | **fixed** — active WP-1 and §12 requirements now say v4. Historical log references do not prescribe the current schema. |
| Q-claim-workflow labeling contradiction | **fixed** — §§5 and 5a consistently require the four dedicated claim-workflow buttons; relation confirmation/rejection supplies visibility evidence only. |
| Incidence mapping and nondegeneracy condition removed | **fixed** — §4a restores `PointLiesOnLine(P, line AB) → Collinear(P,A,B)` with `Distinct(A,B)`. |

**3. Remaining blocking items**

1. **WP-1/WP-2 — make the exact-expression contract internally consistent.**  
   §4a and `$defs.exact` admit `pi` but restrict the domain to real algebraic numbers. Those requirements conflict: π is transcendental. The schema also says the canonical stored `value_exact` is an `srepr()` string, while its grammar admits integers, `sqrt`, `pi` and arithmetic—not the constructor syntax of a symbolic representation.

   Specify one accepted domain and one stored format that round-trips through the parser. Either exclude π from algebraic values or define its supported symbolic use separately. This is a specification contradiction, not a demand for the parser to exist already.

2. **WP-1 — make geometry invalidation representable.**  
   §4a and `events[].invalidates` require every invalidated node to receive `valid=false`. Geometries are graph nodes, and a ground-truth geometry depends on its truth source. However, `entities[].geometries[].properties` has no `valid` field and sets `additionalProperties: false`.

   Invalidating a truth source therefore requires a downstream state that the schema forbids. Add the field or consistently specify another invalidation representation. General dependency-graph completeness can remain a WP-1 test obligation; this concrete structural contradiction cannot.

3. **WP-2 — settle exact versus approximate truth and final-class reproducibility.**  
   §11 permits coordinates with `exact=false` and relative tolerance `1e-9`, yet routes them through an “exact evaluator” returning true/false/degenerate. It does not say whether predicates are evaluated exactly on the stored rational approximations or approximately against the intended construction. A small nonzero residual can produce different answers under those interpretations. A relative tolerance alone does not define predicate-specific equality or degeneracy decisions.

   Restrict authoritative truth to supported exact constructions, or explicitly define the approximate branch’s semantics and eligibility for scoring.

   The deterministic true/false core is improved, but final labels still change between `consequence` and `incidental_unproved` when DDAR succeeds versus times out; `sources[].generator.ddar_budget_s` is a time budget. Explicitly scope determinism to the mathematical result and preserve proof classification as frozen run evidence, or specify a reproducible derivation limit. The packet should not promise deterministic final classes without that distinction.

4. **WP-1/WP-2 — align truth identity with the canonical projection.**  
   §4a and `content_hash.description` include candidate-universe and mathematical-coordinate hashes, but exclude the referenced truth artifact’s `sources[].sha256`, evaluator version, DDAR budget, and candidate class/evidence assignments.

   Consequently, changing a candidate’s evidence or classification while retaining the candidate universe and coordinates leaves the specified projection unchanged. That conflicts with “a problem or truth edit changes `content_hash`.”

   Define which truth changes affect mathematical identity and which affect evidence revision. Then include the corresponding hashes/metadata or narrow the edit rule. Also qualify “equal seed” by equal generator version, configuration and other projection inputs.

**4. New defects introduced by r4**

- **Exact-value format/domain conflict:** the new grammar and normalization contract introduce the incompatibilities in blocking item 1.
- **Unrepresentable invalidation flag:** the new universal `valid=false` rule excludes geometry nodes structurally; item 2.
- **Approximate truth branch:** the newly admitted `exact=false` coordinates lack a compatible truth-evaluation rule; item 3.
- **Truth-edit identity contradiction:** the new lineage rule promises an identity change for edits that its projection omits; item 4.
- **Stale problem-contract references:** §4a still names `problem.texts` and `problem.goal.source`; v4 disallows both and uses `sources[]` plus `depends_on`. Correct those references. This does not independently block work because the replacement mapping is otherwise explicit.

WP-0a may proceed within its offline scope. WP-1 acceptance is blocked by items **1, 2 and 4**; WP-2 acceptance by **1, 3 and 4**. Unexecuted preflights, graph-completeness tests and algebraic-evaluator implementation remain **UNVERIFIED**, rather than additional blockers.

VERDICT: REVISE