All four r4 blockers are **cleared under the packet’s scope rule**. WP-0a may proceed. One nonblocking documentation regression remains.

D1–D6 remain constraints. All five supplied SHA-256 values match the manifest. References below are to the [r5 plan](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/MVE_PLAN.md>) and [v5 schema](</Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Academic Explorer/.claude/worktrees/math-vision-engine-078a13/docs/mve/mve_observation_record.json>).

**1. R4 blockers 1–4**

| R4 blocker | Status | R5 evidence and disposition |
|---|---|---|
| **1. Exact-expression contract** | **cleared** | §4a and `$defs.exact` exclude π and require a canonical string in the accepted grammar, with `render(parse(value_exact)) == value_exact`. The conflicting `srepr` storage requirement is removed. WP-2 explicitly excludes unsupported coordinates; this does not require representation of every real algebraic number. Parser and normalization correctness remain implementation obligations. |
| **2. Geometry invalidation** | **cleared** | `entities[].geometries[].valid` now admits a boolean despite `additionalProperties: false`. §4a requires invalidated nodes to receive `valid=false` and prohibits new citations to them. The previously forbidden downstream state is representable. |
| **3. Exact versus approximate truth; reproducibility** | **cleared** | §11/WP-2 removes approximate authoritative truth and excludes unsupported constructions from every truth-scored set. `sources[].generator.coordinates_exact` documents eligibility. Exact mathematical outcomes are deterministic; DDAR refinement is frozen evidence recording version, budget and outcome. Changed outcomes require a new artifact hash and evidence revision. |
| **4. Truth identity versus evidence** | **cleared** | §4a and `content_hash.description` include evaluator version and distinguish mathematical inputs from candidate-class/DDAR evidence. Evidence changes update `revision` and `sources[].sha256`; changes to problem, coordinates, candidate universe, generator inputs or evaluator version create a new mathematical identity. `lineage.reason` includes `truth_identity_edit`. The generator reproducibility claim now qualifies seed by generator/version/configuration/registry/evaluator. |

**2. Each new defect listed in the r4 verdict**

| R4 defect | R5 status |
|---|---|
| Exact-value format/domain conflict | **fixed** — §4a; `$defs.exact`. |
| Unrepresentable invalidation flag | **fixed** — `entities[].geometries[].valid`. |
| Approximate truth branch | **fixed** — §11/WP-2; `sources[].generator.coordinates_exact`. |
| Truth-edit identity contradiction | **fixed** — §4a Identity; `content_hash.description`; `lineage.reason`. |
| Stale problem-contract references | **fixed** — §4a now uses addressable `sources` and goal `depends_on`; the obsolete names occur only in the historical correction log. |

**3. Remaining blockers for WP-0a, WP-1 and WP-2**

None under the stated review scope.

- **WP-0a:** The offline exemption and capability-specific preflight reporting remain explicit (§7; §11/WP-0a).
- **WP-1:** The semantic validator must enforce canonical forms, truth-source eligibility, authorization and invalidation. Fields being structurally optional does not reopen a blocker when the plan explicitly requires the semantic check.
- **WP-2:** Exact-coordinate support, mathematical evaluation and frozen proof-evidence handling have enforceable contracts. Their implementation is still required.

Preflight outcomes, parser/evaluator correctness, dependency-graph completeness, runtime capabilities, compatibility, licensing, costs, and equality with the out-of-packet authoritative schema are **UNVERIFIED**. These are not established by the source-review assertions.

**4. New defect introduced by r5**

The schema upgrade leaves two active version references stale:

- §11/WP-1 still specifies **“v4 schema.”**
- §12 still describes the record as **“schema v4.”**

Both should say **v5**. This is **nonblocking** because §4a explicitly identifies v5 as authoritative, rejects older versions, and the supplied schema fixes `schema` to `oae-mve-observation-v5`. That provides a decidable acceptance rule despite the editorial inconsistency.

No additional blocking defect was identified. No code was written; the review is returned inline because the workspace is read-only.

VERDICT: PASS (ready for WP-0a)