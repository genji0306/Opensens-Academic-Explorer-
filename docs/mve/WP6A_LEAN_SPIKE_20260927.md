# WP-6a native Mathlib spike — Opus review fixes

Rebased on github/mve/integration 8da83b3c2a2. Branch codex/mve-wp6a-lean-spike stays unmerged for review. Offline only; no packages downloaded or hosted calls made.

## Nondegeneracy guard (B1)

The same E1a registry policy used by WP-2 now supplies the formalizer's required Distinct pairs and NotCollinear triples. Before emission, every hypothesis and goal is checked against the **explicit hypothesis set**. Missing requirements raise a ValueError naming each missing Distinct/NotCollinear proposition. The guard never adds premises, and a goal cannot authorize a hypothesis. Binder/entity aliases are normalized with the same precedence as emission.

Tests exercise each active geometric row, remove each requirement in turn, cover no-goal assumptions, and show that shared-point EqualLength/EqualAngle require nonzero segments/arms and, for each angle, distinct endpoints (A≠C and D≠F). Cross-half sharing remains permitted. Parallel/Perpendicular require full distinctness; Concyclic additionally requires every three-point subset noncollinear. Measurements/observations remain excluded from the authorized premise set.

The retained midpoint fixture is regenerated from a completed **fit** artifact in the E1 corpus, not sealed evaluation. Fraction arithmetic independently verifies its midpoint and three distinct points before the fixture explicitly states all three Distinct premises. Its lineage/source receipt remains in `mve/lean/fixtures/provenance.json`. No implicit nondegeneracy is invented by the runtime.

## Portable pins and receipts (B2, M1)

Real-Lean test availability resolves `lock.json`'s configured `lean_binary` relative to the project; no username or machine path is hard-coded. A temporary alternate-path fixture tests that gate. Missing local binary skips only the real compiler tests; the guard tests still run.

Every dependency/binary path in `mve/lean/lock.json` is project-relative. Stored statement/log paths are relative to each receipt's output directory. Tests check path resolution and reject absolute lock paths. Hashes still pin project files, Lean executable, Git revisions and source-tree cleanliness. The local package cache is not vendored or fetched automatically.

## Compiler boundary (M2, M3, L1)

`compile_source` passes an explicit environment containing only PATH, HOME and LEAN_PATH. A sentinel-secret test checks that arbitrary parent environment values are absent. The sandbox **denies network only**: its allow-default profile does **not restrict filesystem access**. This is not a filesystem-containment claim. Both the isolated Lake build and direct Lean checks use that network-denying profile.

`Spike.lean` now starts with exactly the emitter's HEADER; the unnecessary RealInnerProductSpace scope is removed. All eleven active native targets typecheck in Lean 4.29.0 with pinned Mathlib 8a178386ffc0f5fef0b77738bb5449d50efeea95. A successful record check moves emitted → typechecked, never proved. Errors/timeouts retain emitted status. No proof, axiom-policy verification or semantic-equivalence certificate is claimed.

Reproduce with `python3 -m mve.formalizer --record mve/lean/fixtures/trusted_midpoint.json --output mve/lean/checks/review`. Current build and typecheck receipts are in `mve/lean/artifacts/`. The statement declares Point binders, Midpoint(C,A,B), Distinct(A,B), Distinct(A,C), Distinct(B,C), then Collinear(A,B,C); typechecking is not proving that implication.

LeanGeo remains an interface with an unavailable implementation and fixture test; integration stays open. LeanGeo/JSXGraph are failed: not present locally; vendoring deferred to an owner-approved packet. WP-0b's verified-price refusal remains mandatory before hosted transport. No independent Opus PASS or merge is implied.

Validation: the full MVE suite passed 338 tests (84% combined formalizer/shared-policy coverage; the refusal guard is 100%). Two additional path/registry consistency checks were added afterward and the complete runtime test file passed again. The isolated Lake build and stored midpoint typecheck both succeeded.
