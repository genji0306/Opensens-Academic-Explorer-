# WP-4a deterministic coordinate fixtures — partial review packet

Base e827c05717d; branch codex/mve-wp4a-fixtures. Offline only.

## Status: NumPy fixtures implemented; JSXGraph parity BLOCKED

A filesystem search of real Developer/Opensens directories (including node_modules), plus npm cache filenames and cache index content, found no local JSXGraph package. Desktop symlinks were not followed. No dependency was downloaded. Thus this packet does **not** claim a JSXGraph contract has been executed or cross-kernel parity has passed. A pinned local JSXGraph runtime is required to complete WP-4a. LeanGeo is unrelated to this packet.

The proposed numerical contract below is implemented and exercised by NumPy. It must remain versioned and subject to review when the second kernel becomes available. No learned tolerances, G1 FPR, image detection, or real-data transfer are claimed.

## Fixture contract `mve-coordinate-fixture-v1`

Input: finite pixel-top-left point coordinates, image width/height and an explicit nonnegative tolerance. Normalize both axes by the image diagonal D=hypot(width,height), preserving geometry. All angles are undirected, computed by atan2(abs(cross),dot), in degrees. Bound geometry comes from the validated v5 record. Standalone numerical fixtures need not originate from an image.

| Predicate | Nonnegative residual | Unit |
|---|---|---|
| Collinear | triangle area determinant / longest side | px_normalized |
| Concyclic | maximum deviation from mean radius after centered algebraic least-squares circle fit | px_normalized |
| Parallel | abs(cross(u,v))/(norm(u) norm(v)) | ratio |
| Perpendicular | abs(dot(u,v))/(norm(u) norm(v)) | ratio |
| EqualLength | abs(norm(u)-norm(v)) | px_normalized |
| EqualAngle | absolute difference of the two undirected angles | deg |
| Midpoint | distance from first point to midpoint of the other two | px_normalized |
| SBetween | distance from first point to the closed segment between the other two; endpoint coincidence is degenerate | px_normalized |
| RightAngle | abs(angle-90) | deg |
| Distinct / NotCollinear | 0 if separation / triangle height exceeds 1e-12, otherwise 1; tolerance must be zero | ratio (violation indicator) |

For geometry rows, repeated names/coincident points are degenerate. Concyclic also rejects any collinear triple. A nonzero normalized point separation (or concyclic triple height) below 1e-6 is near_degenerate and cannot be reported consistent. Degenerate or unmeasurable inputs have null residual. Missing/nonfinite coordinates are unmeasurable. Otherwise equality at tolerance belongs to consistent. Thresholds are numerical fixture guards, not empirical truth thresholds. Results are approximate coordinate evidence, never exact truth.

`measure_record` requires the exact selected geometry IDs, one current point geometry per argument. It appends a measurement via actor A2, pins contract/version, and moves perceived or ground_truth fixtures to measured. No implicit choice among call-1/call-2 geometries. It never reads truth artifacts, adds assumptions, edits stated premises, or claims independent image measurement. Uncertainty remains null: propagation/calibration has not been implemented, and supplied localization uncertainties are not used as confidence claims.

Tests independently specify positive/negative residuals, similarity transforms, near/fully degenerate cases, absent coordinates, tolerance boundaries, ground-truth fixtures and record lineage. A coordinate result may contradict a trusted given without rewriting that given. Full counts and coverage are recorded in the review receipt.

No hosted calls or API cost. WP-0b's verified-price gate is still required before hosted transport. Leave this branch for Opus; do not merge as a complete WP-4a PASS.

Verification on this branch: **299 full MVE tests passed**, including 43 new numerical/record fixtures; measurement package **95% statement coverage** (99/104), Ruff and file/function size checks pass. Review was local; JSXGraph parity is not included in these numbers.
