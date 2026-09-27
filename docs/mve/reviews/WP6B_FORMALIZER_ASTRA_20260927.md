# WP-6b formalizer — Astra handoff, 2026-09-27

Branch `codex/mve-wp6b-formalizer`; base `576816e73754b825967777d279c362a9b959454a`.
Sole builder: Astra. Opus reviews, reruns the sandbox-dependent checks, and pushes/merges.
Offline only: 0 hosted/model calls, 0 downloads, 0 prover calls. LeanGeo absent.

## Delivered

- Bounded repair path and CLI: at most 3 rounds, exact frozen IR/evidence and binder mapping,
  proposition and source hashes each round, deterministic missing-colon repair, unknown
  rewrites refused before Lean and logged. Malformed IR, changed provenance, syntax disguised
  semantic changes, cap exhaustion, mismatched compiler receipts, and stale output artifacts
  have regression tests. No theorem proofs, `sorry`, or added axioms are emitted.
- Explicit adopted assumptions now enter the IR with `asm_N` authority preserved in formal
  payloads. Measurements and model judgments remain non-authorizing. WP-6a nondegeneracy
  remains mandatory; complete tasks additionally refuse E1a repeated/self-identity predicates
  and a goal that simply repeats a hypothesis.
- Evidence levels in strongest-first order: kernel-checked, machine-supported,
  reviewer-judged, unresolved. Kernel equivalence has no producer here. Machine correspondence
  records IR/source identity and explicit binder mapping; it cannot pass the semantic rubric.
  Reviewer evidence binds artifacts and all four rubric components. Typechecking is never proof.
- Retrieval accepts only image-bound records in the existing frozen retrieval partition;
  sealed/evaluation, development, fit, calibration, unknown images, mismatching origins,
  duplicates, and retired manifests are refused.
- Offline G3 harness on WP-2 constructions, shared repair runner, counts, seven control kinds,
  persistent records/split/attempts/compiler receipts. Documentation: `docs/mve/FORMALIZER.md`.
- WP-8a follow-ups closed: dated v5 additive changelog in schema description and plan §13,
  covering development/retrieval, can_N, proposed, and human: grammar; schema copies byte-equal.
  Base already refused model decline in core validation. New regression pins that refusal,
  and VERDICTS.md now names the enforcement layer. Local operator identity is not authentication.

## Counts and limits

Actual run: `mve/lean/artifacts/wp6b-g3/g3.json` and `tasks.json`.

| Check | Count |
|---|---:|
| Explicit-premise/goal instances from sealed WP-2 families | 100 |
| Canonical statement templates | 3 |
| Unique compiler inputs (canonical + syntax faults) | 6 |
| Deliberately injected missing-colon first attempts | 20 |
| First-pass well-typed, actual sandbox run | 0 / 100 |
| Post-repair well-typed, actual sandbox run | 0 / 100 |
| Unique compiler invocations blocked by nested sandbox | 6 / 6 |
| Structural reference instances | 50 |
| Kernel / machine / reviewer / unresolved reference counts | 0 / 0 / 0 / 50 |
| Independent semantic-rubric passes | 0 / 50 |
| Empty / trivial / nearest-retrieval refusals | 100 / 100 each |
| Weakened / strengthened / vacuous / unrelated-provable refusals | 100 / 100 each |
| Hosted calls / proof checks | 0 / 0 |

Null: **N/A**. **G3 remains incomplete.** Every real compiler input returned
`sandbox-exec: sandbox_apply: Operation not permitted`; sources and error logs are committed.
No successful fixture receipt replaces a real result. The deterministic unit fixture has
4 first-pass and 6 post-repair successes on 6 instances; that is a rule regression, not a
Lean or LLM benchmark result.

The 100 instances reuse three manually authored midpoint consequences. The first 50 serve
only as structural reference comparisons; there is no independent blinded reference corpus
or completed reviewer rubric. Family assignments preserve WP-2's frozen split seed and
allocation; the new manifest uses image hashes. New fixtures use exact-positive constructions,
not a claim of replaying WP-2's original 500-record corpus. Three named points are formalized;
images retain six rendered points. Byte-identical Lean inputs share one receipt within the run.
Nearest-retrieval controls test refusal of substituted IR/provenance, including identical
statement templates; they do not establish that source text was never copied. The guard is
not a general inconsistency/tautology solver. No new nondegeneracy is inferred or auto-added
by repair. E1a registry semantics and Lean/Mathlib pins are unchanged.

## Validation

Tests were written and observed failing before the corresponding implementations. Final full
`tests/mve` run: **633 passed, 7 failed, 0 skipped**, 95% total statement coverage. The seven
failures are exclusively nested `sandbox-exec` launches (same OS restriction as prior packets):

1. `test_formalizer_g3.py::test_real_lean_repairs_statement_without_proof`
2. `test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
3. `test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
4. `test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
5. `test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
6. `test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
7. `test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

| New module | Covered statements |
|---|---:|
| equivalence.py | 30 / 30 |
| g3.py | 62 / 63 (98.41%) |
| repairs.py | 103 / 103 |
| retrieval.py | 39 / 39 |
| tasks.py | 46 / 46 |

Ruff checks, diff whitespace check, byte-equal schema check, and ≤50-line function check pass.
The coverage package used its Python tracer after reporting an incompatible local C tracer;
coverage collection completed. No test was skipped or relaxed to hide sandbox failures.
`validation.json` records the suite summary and new-module coverage. Manual builder review
found and fixed stale successful `record.json` after a refused rerun. No subagents were used.

Opus rerun from an ordinary Developer shell, with the already-present pinned packages:

```bash
export MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages"
python3 -m pytest -q tests/mve --cov=mve --cov-report=term-missing
python3 -m mve.formalizer.g3 --output /tmp/mve-wp6b-opus-g3
```

Do not merge on the blocked typecheck counts alone. Preserve the failed builder receipts;
record Opus's new run separately. Independent semantic review and broader, non-template
reference tasks remain necessary before G3 can pass. The Lean process is network-denied,
not filesystem-contained. This packet does not activate hosted calls or change §7 order.
