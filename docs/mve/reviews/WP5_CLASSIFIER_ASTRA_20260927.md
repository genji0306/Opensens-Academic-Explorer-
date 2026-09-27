# WP-5 classifier + learning — Astra handoff, 2026-09-27

Base: `mve/integration ca7cbcf3ed738c9d10ac1ebb8bae8a234c0fbcf7`.
Branch: `codex/mve-wp5-classifier`. Built in this worktree only, offline; no hosted
calls, downloads, new package installs, pushes, or merges. Opus reviews and merges.

**G2 not established. No production refit or promotion is claimed.** The bounded
spike trains a new linear head over frozen openJev logits, not the original openJev
head/encoder. It establishes that this small adapter can learn weighted targets,
checkpoint, export to ONNX, and reproduce its in-memory fixture predictions.
It does not close the original-head-refit prerequisite in r5 §8.

## Delivered

- Nine r5 §5 questions as data, exact WP-8a vocabularies, separate abstention, target
  label sources, stage P2/P3/P5 activation, annotated-only mark question, and risk
  minima. All nine remain disabled in the production lock.
- Runtime complete-input token counting with local pinned tokenizer, including
  candidates, abstention, delimiters, question, state and special tokens. No
  truncation; 512 allowed / 513 refused before forward. Noul uses its distinct
  proposition template. Confidence includes abstention probability mass.
- Exhaustive routing data and runtime checks: code → openJev → LLM → human;
  boundaries route down, LLM refuses offline and records the human fallback.
  Mechanical failure / zero measurements stops before inference. Immutable receipts
  include input, lock and model hashes, thresholds, token count, route and reason.
- WP-8a exports supply targets, preserving human-over-manager resolution, human
  abstention, 1.0/0.5 weights and conflict provenance. Only fit rows train. Existing
  frozen family assignments are retained across training/calibration/evaluation;
  development/retrieval remain excluded. No visibility-click pseudo-labels.
- Per-label support counts across all three splits, a documented no-update outcome,
  uniform 1/K nulls, and explicit null metrics where prerequisites are absent.
- Seeded ceil(10%) audit sampler over act decisions in one named wave, stable under
  input reordering, independent declared judge, population/sample counts, and
  zero-coverage question strata. Tested on 21 act decisions → 3 samples.
- Model/tokenizer/calibrator/data pins in `mve/classifier/lock.json`; separate
  WP-5 packet pins in `mve/DEPS.lock`. Local model hashes are checked before loading.
- Historical absolute home paths localized in DEPS and the preflight report,
  retaining file hashes. Publication now normalizes future reports too. A test
  scans every tracked file under `mve/` for the forbidden absolute-home prefix.

## Measured bounded spike

| Item | Result |
|---|---:|
| Local base model | openJev 151M fp16 ONNX, 303,785,047 bytes |
| Base model SHA256 | `4db28305590c714e33c2cacb75a57ec941c72bb210e1266ba2c7d77e85ddc526` |
| Question | Q-agree-action |
| Training examples / families | 4 / 1 fit family |
| Resolved human / manager fixture rows | 2 / 2 |
| Trainable / changed parameters | 20 / 20 |
| Epochs / optimizer steps | 2 / 2 |
| Hard configuration limits | 3 epochs, 20 steps, 64 rows, 180 optimizer seconds |
| Weighted cross-entropy, before each step | 1.7108593583, 1.6790073117 |
| Training token counts | 48, 50, 46, 48 |
| Unlabelled parity fixture token counts | 44, 47, 44 |
| Exported/in-memory argmax agreement | 3 / 3 |
| Maximum absolute logit difference | 0.0 (tolerance 0.00001) |
| Reloaded checkpoint arrays equal | true |
| Spike elapsed, excluding model construction/load | 0.5564255 seconds |
| Production promotion | false |

These are parity and plumbing numbers, not accuracy estimates. All labels and
operator identities in the committed fixture are explicitly synthetic test inputs;
`human:` is a local assertion, not authentication. There is no real human audit or
independent evaluation gold in this packet. No scientific independence is inferred
from multiple renderings in one fit family.

`checkpoint.npz` and `head.onnx` are ignored under `mve/generated/wp5-spike/`; only
hashes are committed. The frozen base model remains external. The ONNX export is
the added logit head, not a combined token-to-label model. The narrow protobuf
writer emits MatMul/Add and the actual ONNX Runtime parity execution validates it.
The committed `spike_receipt.json` records configuration, hashes, support counts,
nulls, no-update reasons and the numerical results above.

## Validation

Tests were written first; the initial run failed importing the absent classifier.
Final full command:

```bash
MVE_LEAN_PACKAGES="$HOME/Developer/Opensens/Opensens Academic Explorer/lean/.lake/packages" \
  python3 -m pytest tests/mve --cov=mve.classifier --cov-report=term-missing -q
```

**648 passed, 7 failed, 0 skipped** in 48.47 seconds inside Codex's sandbox.
New modules: **338/341 statements, 99.12% coverage**; every new module is at least
95% (all except the spike runner are 100%). The subsequent focused run is 15/15
passed after test-only formatting and fixture serialization normalization.
Ruff check and file/function size checks pass. Coverage used its Python tracer
because the installed C tracer has the wrong architecture; measurement completed.

All seven failures are the established nested `sandbox-exec` restriction. Compiler
logs show `sandbox-exec: sandbox_apply: Operation not permitted` (log SHA256
`d34a4e4359a4dc36526cf5b363da32f7b7594a3a09eea17cbdfd6425b052d93e`).
The timeout test gets immediate sandbox exit instead of a running worker timeout.
Opus must rerun these outside the nested sandbox; no protection was bypassed:

1. `test_formalizer_g3.py::test_real_lean_repairs_statement_without_proof`
2. `test_formalizer_runtime.py::test_native_targets_compile_without_proofs`
3. `test_formalizer_runtime.py::test_typecheck_record_keeps_proof_separate`
4. `test_formalizer_runtime.py::test_real_lean_typechecks_from_relocated_project`
5. `test_isolation.py::test_real_subprocess_cannot_read_gold_or_connect`
6. `test_isolation.py::test_public_staging_rejects_links_and_worker_timeout`
7. `test_open_review_followups.py::test_worker_created_runtime_symlink_cannot_read_private_gold`

## Remaining acceptance gaps

G2 is not evaluated: no class floors met, no independent gold/paired Opus outcomes,
no calibration acceptance evidence, no per-question automatic-route error bounds,
and no original-openJev-head refit/promotion. Majority, code-only and previous-lock
baselines and queue-rate metrics remain null. A future packet needs genuine labels,
untouched family-disjoint evaluation, calibrated thresholds, original-head training
or an explicitly reviewed amendment accepting the added-head architecture, and the
full G2 statistical evaluator/promotion policy. No thresholds were moved by hand.

Routing receipts are standalone; inserting them into v5 record transitions is not
implemented here. The sampler requests adjudication but does not authenticate a
judge or manufacture labels. Topology remains inactive until P5.

Reproduction and API boundary details: `docs/mve/CLASSIFIER.md`.
