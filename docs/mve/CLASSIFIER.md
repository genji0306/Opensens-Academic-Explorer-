# WP-5 offline classifier and learning boundary

`mve/questions/catalogue.json` freezes all nine r5 §5 vocabularies, target-label
sources, activation stages, annotated-track restriction, and a distinct abstention.
`routing.json` states every route and boundary. Truth predicates are outside this
catalogue. Nothing in this package adopts assumptions or writes formal propositions.

`mve.classifier.runtime.decide` returns an immutable routing receipt with the complete
serialized-input hash, actual token count, answer/abstention, confidence, requested
and final routes, thresholds, trace, model hash, and classifier-lock hash. The code
tier checks mechanical failure, zero measurements, activation, track, and evidence
before inference. Mechanical failures return `stop`. Eligibility refusals return
`human`, with zero input tokens because no inference input was tokenized. These are
standalone receipts, not v5 `decisions` insertions; record transition integration is
not included in this packet.

`LocalEngine` verifies the model, tokenizer, calibrator, and data hashes, disables
tokenizer truncation/padding, and counts the complete openJev v1.4 prompt including
candidates, abstention candidate, delimiters, context, question, and special tokens.
At 513 tokens it abstains before forwarding; 512 is allowed. The selected-label
probability includes abstention mass and uses the pinned per-K temperature. The
low and high boundaries route downward. The offline LLM stub raises a refusal,
which becomes a human-queue receipt retaining `requested_route="llm"`.

All nine questions in the shipped lock are disabled. Thresholds are the plan's
starting risk minima, not fitted thresholds. `support` requires ten distinct images
per label in each of training/calibration/evaluation. No question is activated,
no threshold is adjusted, and no production weight is promoted by the spike.

`learning.label_sets(records, frozen_split)` wraps WP-8a `export_labels` for the
three learning uses. It preserves the upstream five-way family manifest; development
and retrieval remain outside learning, and all renderings of a family remain together.
Only `fit` exports pass the training boundary. Human overrides manager, a human
abstention suppresses a manager label, and ordinary visibility clicks create no
catalogue label. `human:` remains a local operator assertion, not authentication.
The tiny committed fixture has four explicit synthetic plumbing labels in one fit
family; its empty calibration/evaluation label sets provide no acceptance evidence.
`labels.json` is the WP-8a export, checked against a fresh export on every spike run.

`audit.sample` chooses ceil(10% of the wave's act population) by seeded hash ordering,
independent of input order. It reports population/sample counts and every question
stratum with no sampled decision. The declared judge must differ from the compared
manager. The sampler does not authenticate identities or adjudicate the sample;
audited labels must come back through WP-8a, never through automatic pseudo-labeling.

## Reproduce the bounded spike

No install, download, network SDK, or hosted call is needed. The existing local
openJev runtime provides tokenizers and ONNX Runtime; the system Python supplies
the repository's existing validation dependencies. From the worktree root:

```bash
PYTHONPATH="$PWD/mve/preflight/guard:$HOME/Developer/Opensens/runtimes/openjev-venv/lib/python3.13/site-packages:$PWD" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python3 -m mve.classifier.run_spike
```

The Python audit hook denies network/DNS and keychain access. No new dependency is
installed. The writer in `onnx_head.py` emits only a float32 MatMul/Add graph using
ONNX protobuf wire fields, then ONNX Runtime actually loads and executes it. This
avoids needing an absent `onnx` exporter package.

The spike learns a **new 20-parameter linear head over frozen openJev logits** for
Q-agree-action, using human=1.0 / manager=0.5 weighted cross-entropy. It does **not**
train the original openJev encoder or original head. Checkpoint (`checkpoint.npz`)
and ONNX head (`head.onnx`) stay in ignored `mve/generated/wp5-spike/`. The frozen
303,785,047-byte base model remains at its existing local path. The two ONNX files
are separate stages; the exported head alone does not take token IDs. Training is
full-batch deterministic SGD, two configured epochs/steps, with hard configuration
limits of three epochs, twenty steps, 64 rows, and 180 seconds for optimization.
The committed receipt records hashes and numerical parity on three unlabelled
state fixtures, independently of the four training states. It makes no accuracy claim.

`G2 not established`: no production class floors, independent gold or paired Opus
predictions, calibrated thresholds, or original-head refit/promotion evidence.
There is no G2 evaluator or promotion implementation pretending these are present.
The no-update report preserves null metrics and uniform 1/K nulls; majority,
code-only, previous-lock, queue and error-bound measurements await an eligible wave.
