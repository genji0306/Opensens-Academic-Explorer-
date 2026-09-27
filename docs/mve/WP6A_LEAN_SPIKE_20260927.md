# WP-6a native Mathlib spike — review packet

Base e827c05717d; branch codex/mve-wp6a-lean-spike. Offline only, no merge.

## Result

The isolated `mve/lean/` Lake project builds using Lean 4.29.0 and Mathlib `8a178386ffc0f5fef0b77738bb5449d50efeea95`. All eleven active predicate targets typecheck, including the nine P1 rows. The trusted synthetic midpoint fixture completes Record → evidence-preserving IR → native Mathlib emission → actual Lean subprocess → v5 `formal.status=typechecked`. No theorem proof, axiom-policy check, or semantic-equivalence certificate is claimed. No `sorry`, fabricated proof or hosted call is used.

`mve/lean/artifacts/` retains the actual isolated Lake build log/receipt, emitted midpoint statement, IR, typecheck log/receipt and resulting v5 record. The fixture is drawn from WP-2's **fit** partition, never evaluation; source provenance is in `mve/lean/fixtures/provenance.json`. The public statement is `Midpoint(C,A,B) → Distinct(A,B) → Collinear(A,B,C)` under Point binders. The compiler checks the proposition is well typed; it does not prove the implication.

Reproduce the record check with:

```
python3 -m mve.formalizer --record mve/lean/fixtures/trusted_midpoint.json --output mve/lean/checks/review
```

The local machine's package cache paths are explicit in `mve/lean/lock.json`. The isolated project's ignored `.lake/packages` symlinks point to those pinned caches. No packages are vendored and the command does not fetch them. The runtime checks project-file hashes, Lean binary hash, package Git revisions and clean tracked source trees before compiling. Both the Lake build and direct Lean subprocess run under a network-denying macOS sandbox. Missing cache, stale pins or unavailable sandbox fail closed. Lock portability requires an explicitly verified cache on another machine; no automatic installation is attempted.

## IR and semantics

Only validated explicit problem premises/nondegeneracy/goals become statements. Their authorizing node and source refs remain in the IR and formal proposition dependencies. Measurements, observations, classifier labels and informal judgments never become premises. Point binders map to deterministic safe names, preserving binder-to-entity authority and blocking identifier injection. No-goal inputs emit separate assumption propositions and no theorem. Empty statements, inactive predicates, non-Point binders and scalar constants outside this P1 subset fail closed. This spike does not implement adopted-assumption/derived-premise selection or repair.

Native targets use Mathlib collinearity/concyclicity, affine-span parallelism, inner-product orthogonality, distances, undirected angles, midpoint and strict betweenness. RightAngle converts the registry's 90 degrees to Mathlib's `Real.pi / 2`. No implicit nondegeneracy assumptions are inserted. `SemanticsMap.json` names the targets and the limited evidence level. Typechecking these targets does not establish exact-evaluator equivalence or a LeanGeo bridge.

Emission and typecheck are separate validated A4 transitions; success never sets `proved`. Errors/timeouts leave only the emitted artifact. Source, lock, IR and compiler log hashes are retained. Existing record identity is preserved and revisions advance twice on success.

## Missing integrations and owner steering

Owner response confirms no local LeanGeo or JSXGraph exists. Both are recorded in DEPS.lock as **failed: not present locally; vendoring deferred to owner-approved packet**. Per that response, this spike targets native Mathlib only. `LeanGeoAdapter` is an interface with a fixture-tested unavailable implementation returning unsupported, no statement and `integration_checked=false`; its integration check stays open. JSXGraph is deferred to A6/WP-7 and is not a WP-6a dependency.

No hosted calls, API cost zero. WP-0b must still refuse unverified prices before any hosted model transport. These are implementation and local validation receipts for Opus review, not an Opus PASS.

Verification: **266 full MVE tests passed**, with **82%** coverage of the complete formalizer package including the CLI (150/183 statements). The CLI also ran on the retained trusted fixture. Local regressions cover all native targets, record transitions, timeout/error behavior, dependency pin refusal, safe binder names/aliases, no-goal output and the disabled LeanGeo interface. Ruff and file/function size checks pass. The isolated Lake build returned 0 with networking denied.

The source WP-2 batch used for this one symbolic fixture was later retired because of duplicate raster images. Its exact mathematical truth and the midpoint premise are unchanged. Retaining the fixture's original provenance does not revive that batch's evaluation acceptance. The accepted replacement corpus is documented on `codex/mve-wp2-generator` in `WP2_CORPUS_RENDER_V2_RECEIPT_20260927.json`.
