# WP-2 generator — Opus review fixes

Rebased on github/mve/integration 0550144a895. Offline only; leave codex/mve-wp2-generator unmerged for review.

## E1a exact truth and candidate universe (B1)

The registry now stores executable distinct-argument pairs and noncollinear triples alongside the clarified degeneracy strings. The generator, exact evaluator and coordinate fixture kernel use that shared policy. EqualLength allows cross-pair sharing but excludes identical segments up to endpoint reversal. EqualAngle allows cross-triple sharing but requires all three points in each triple to be distinct, including A≠C and D≠F, and excludes identical angle triples up to endpoint reversal. Zero-length segments/angle arms and repeated angle endpoints are degenerate. Parallel and Perpendicular still require all four named points distinct. The other rows retain their existing rules.

Six named points produce **2,257** canonical candidates, including 1,770 nontrivial EqualAngle pairs and 105 nontrivial EqualLength pairs. Universe SHA-256: `1c099592b432d42c94a3afe2a0895a46b0d0983541234e7d2fd0302e623f581a`. Exact evaluator version is `mve-algebraic-plane-v1-e1a`. Tests independently count unordered segments/angles and check true isosceles/bisector facts, zero arms, self-angle exclusion and excluded shared-point Parallel/Perpendicular.

Only algebraic constructions have authoritative truth. Exact arithmetic decides true/false/degenerate. Default DDAR remains explicitly unsupported: exact-true non-premises are incidental_unproved. Proof outcomes are frozen, never silently rerun; a purported proof of exact false excludes the diagram. Rendering does not enter mathematical identity. No hosted call or Newclid success is claimed.

## Corpus accounting and split labels (B2, M1)

`corpus_report` computes both image and mathematical-coordinate collisions across every split, records both counts and requires both to be zero for acceptance. A regression injects a coordinate-only collision while preserving within-split counts and unique image hashes; acceptance must fail.

Canonical corpus labels are development, retrieval, fit, calibration and sealed. Records, manifest rows and split.json use the same label; the production sealed set contains 500 diagrams. The schema explicitly permits development/retrieval. The shared split reader retains support for historical manifests labelled evaluation, but one manifest cannot mix the two labels for its evaluation role.

`mve.generator.receipts.write_receipts` verifies artifact hashes, all v5 records, scene contracts and per-item split labels, then recomputes the corpus report. Both tracked receipts come from that code: `WP2_CORPUS_RECEIPT_20260927.json` is the generation summary; `WP2_CORPUS_RENDER_V2_RECEIPT_20260927.json` is the artifact audit of the same E1a corpus. Previous receipts are archived, not accepted current evidence. The regenerated corpus contains 2,000 fit and 500 sealed diagrams plus development/retrieval/calibration fixtures; exact outcome counts are in the generated receipts.

The deterministic render-v2 recipe varies orientation/scale. Thin style is covered by the corpus; thin/bold rendering is tested. `render_pinned=false`; cross-platform PNG-byte reproducibility is not promised. The backend-neutral scene schema and explicit coordinate guard reject negative x/y, nonfinite values, unknown endpoints and out-of-frame coordinates (M2). No JSXGraph library is required or claimed.

## Reproduction and scope

Run `python3 -m mve.generator --output <new-directory> --workers 8 --generation-receipt <path> --audit-receipt <path>`. Workers are bounded local CPU processes; ordered output is regression-tested equal to serial generation. No model workers or network transport are involved. The review corpus runs from a git-archived copy of the committed implementation under the same permitted worktree, allowing independent WP-6a work without changing code under the generator processes. The receipts pin that implementation commit.

Euclid generator discovery: failed: no local checkout; no network fetch in offline packets. JSXGraph and LeanGeo remain unavailable locally; vendoring is deferred to an owner-approved packet. WP-0b must refuse unverified prices before hosted transport. These are local implementation receipts, not an Opus PASS or a perception-accuracy gate.

E1a regression tests independently count the segment/angle pairs, reproduce both four-point reviewer probes, reject both forms of repeated angle endpoints (including distinct names at coincident coordinates), and verify frozen truth excludes the trivial facts. The shared required_nondegeneracy policy now requires all six within-angle Distinct pairs. Formalizer tests independently remove A≠C and D≠F in turn and confirm emission refuses each missing premise. The coordinate kernel and native semantics map follow the same registry.

The E1 corpus receipts are archived as superseded. E1a regeneration and audit run from a committed immutable source snapshot; the current receipts will pin that snapshot and contain the computed final counts.
