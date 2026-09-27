# WP-8a offline verdict capture

Use `mve.verdicts` with immutable `Record` values, or the local JSON CLI. No UI,
network transport, authentication provider, training runtime, or new dependency is used.
Actor identities are explicit local operator assertions (`human:alice`, `model:opus`);
the API does not authenticate them. A host must supply the correct actor kind and identity.
Opus acting as a manager model is `model:opus`, never `human:opus`.

```python
from mve.verdicts import capture, propose, revise, export_labels, export_verdicts

updated = capture(record, target="obs_1", verdict="confirm", actor="human:alice",
                  from_revision=record.to_dict()["revision"], at="2026-09-27T01:00:00Z")
```

`capture` accepts observations, measurements, derivations, judgments, candidates, and
existing formal propositions. Verdicts are `confirm`, `reject`, `not_visible`, `unsure`,
`adopt`, `decline`, and `label`. A model may neither adopt nor decline; the core semantic validator refuses both,
including direct transition calls. Confirmation is
visibility evidence. Only human adoption through this API appends an assumption. Adoption
requires a proposition-bearing target, so adopting a judgment itself is refused: adopt its
underlying candidate/observation/measurement/derivation instead. No `human_confirmed`
support exists. The pre-existing text/policy adoption routes remain in the core operations.

`propose(record, proposition=..., actor=..., from_revision=..., at=..., text=None)` appends
an optional `can_N` candidate. Use entity IDs in the canonical proposition. The candidate
cites every argument entity, records the proposer, and has no formal authority. A candidate
with `text` can be a free-text claim target for `Q-claim-workflow`. Editing an entity or
candidate invalidates its downstream judgments, assumptions, and formal artifacts.

`revise(record, judgment="jud_1", verdict="reject", actor="human:alice",
from_revision=..., at=..., label=None, rationale=None)` corrects that human's own verdict
with an RFC 6902 edit. Its prior dependents are invalidated through `mve.graph`. A new
judgment is an additional opinion; use `revise` to withdraw/change a previously adopted
verdict. Another actor must append their own opinion. Generic edits also cannot rewrite
judgment/proposer/assumption owners or edit another actor's judgment/candidate.

All operations reject a stale revision. Ordinary capture/proposal/edit advances one
revision; adoption advances two existing transitions (`judged` then `assumed`, or `edited`
then `assumed`). The immutable API returns only the final record. The CLI writes both
transitions together, never a half-adoption. Use the returned revision for the next request.
Timestamps require an explicit RFC 3339 timezone; selection order uses revision history,
not caller wall clocks. Capture/adoption do not change the mathematical or execution ID.

## CLI

Start with a valid existing record. Save this request as `request.json`:

```json
{"operation":"capture","target":"obs_1","verdict":"adopt","actor":"human:alice","from_revision":1,"at":"2026-09-27T01:00:00Z"}
```

```bash
python3 -m mve.verdicts apply record.json request.json
```

`operation` is `capture`, `propose`, `revise`, or `edit`. The first three take the Python API
arguments above. `edit` takes `actor`, `from_revision`, `patch`, optional `at`, and optional
`request_nonce` for a mathematical lineage change. CLI timestamps default to current UTC.
CLI errors return exit code 2. A `.lock` sidecar serializes cooperating writers; the current
record is read under the lock, then validated and atomically replaced using a flushed
same-directory temporary file. Failed validation or replacement leaves the old record.
All writers must use this protocol and the same canonical record path; direct external
file writes and hard-link aliases are outside this local store's concurrency contract.

## Labels and family isolation

Explicit `verdict="label"` requires one of the frozen §5 questions and its exact label
vocabulary. Example: `question="Q-agree-action", label="remeasure"`. Visibility clicks
never label catalogue questions. `Q-claim-workflow` requires a free-text target and one of
`restates_measured`, `propose_new_measurement`, `contradicts_measured`, or `discard`.
`not_visible` / `unsure` remain abstentions, including on catalogue questions.

For each (target, question), a current human judgment wins over every model judgment;
within the same actor kind the latest revision wins (then numeric judgment ID for a batch).
Human weight is 1.0; manager model weight is 0.5. Capture and revision record conflicts in
the event note; exports list conflicting judgment IDs. A human abstention suppresses a
model label. Invalidated judgments never export. Audit-role judgments are not silently
recast as manager-model identities; use explicit human/model capture for this label path.

`export_labels(records, frozen_split, purpose="training")` returns only resolved, explicit
catalogue labels. `export_verdicts(...)` also exports resolved visibility, adoption, and
abstention evidence with `verdict`, `abstained`, and `label_scope`; their `label` is null
unless explicitly supplied for a catalogue question. These evidence rows are not classifier
training targets. Row provenance includes actor kind, identity, weight, timestamp, target,
judgment/revision, record/revision, image SHA, content hash, family, split, and split hash.
Both exporters operate on current records, not a mix of historical snapshots.

The `FrozenSplit` item IDs **must be image SHA256s**. This binds a record to its frozen family
without accepting a caller-provided item ID that could disguise a sealed record as a fit
item. All renderings of a family must occupy one split. If `image.truth` is present, its
family and split must agree exactly with the manifest. Duplicate images, unknown images,
retired splits, and observed same-content cross-split collisions are refused.

WP-2 corpus split IDs are opaque diagram IDs. To adapt one, replace each ID with that item's
`image_sha256` from its corpus manifest, preserving every original family and split. Validate
that derived object with `FrozenSplit`, persist it, and pin its new SHA. Do not repartition
families or reuse the old hash. No truth artifacts or candidate gold are needed for this
metadata conversion. For user images, family assignment must be frozen externally before
label export; this packet does not infer construction families from pixels.

```bash
python3 -m mve.verdicts export --split image-family-split.json \
  --split-sha256 PINNED_SHA256 record.json > training-labels.jsonl
python3 -m mve.verdicts export --kind verdicts --split image-family-split.json \
  --split-sha256 PINNED_SHA256 record.json > verdict-evidence.jsonl
```

Training exports include **only `fit`**. Calibration requires `--purpose calibration`;
evaluation/sealed requires `--purpose evaluation`. Development/retrieval are never training
exports. Neither exporter includes image bytes, truth artifacts, rationale, or candidate
propositions. No classifier activation, refit, threshold change, routing execution, or
G4b session acceptance is claimed by WP-8a.
