# Math Vision Engine (MVE) — Review and Development Plan

**Date:** 2026-09-27 · **Author:** Claude Fable 5.1 (planning session, worktree
`claude/math-vision-engine-078a13`) · **Builder:** Codex Astra (`gpt-6-astra`) ·
**Reviewer and fleet operator:** Claude Opus · **Core vision worker:** DeepSeek V4.1 Flash ·
**Support:** Codex Sol (`gpt-5.6-sol`), Claude Opus · **Critical-strategy cross-review:** Astra + Fable.

Companion files (same folder): `MVE_REVIEW_OF_SOURCES.md` (per-paper review),
`../../schemas/mve_observation_record.json` (the record every stage reads and writes),
`README_FOR_ASTRA.md` (packet manifest and dispatch command).

---

## 0. Summary and the decisions the owner must make

**What we are building.** An engine that lets an AI *look* at a mathematical picture
(geometry figure, topological diagram, plot, atlas panel), write down what it sees as a
typed observation record, decide the fixed-list questions with a fast classifier (Jev),
re-measure every claim on a canvas before trusting it, turn the surviving facts into a
Lean 4 statement, try to prove it, and render the statement back into a picture so a human
and the AI can look at the same thing together. That last step is the co-observer loop the
Darklab vision asks for: the human brings geometric intuition, the AI brings language and
Lean, and the engine is the table they meet at.

**What the literature says, in one line each.**

- The six requested sources give us data recipes, a diagram encoder lesson, a formal-caption
  objective and a small-model decision layer. None of them emits propositions or Lean, and
  none handles topology. Details in `MVE_REVIEW_OF_SOURCES.md`.
- Perception, not reasoning, is the bottleneck. Frontier VLMs score 16–29% on "which point
  is on this line" (Geoperception) and 0/100 on strict knot-diagram transcription
  (KnotBench). Reasoning on top of a wrong parse compounds the error.
- The shortest credible path already exists in pieces: DeepSeek V4.1 Flash for pixels,
  a GeoIR-style typed record, canvas re-measurement (Draw2Think pattern), Newclid as a
  derivability checker, LeanGeo/Mathlib as the Lean target, Goedel-Prover-V2 or
  DeepSeek-Prover-V2 for proofs, ProofWidgets4 + Penrose for render-back.
- Jev is a decision layer, never a truth judge. It is text-only, so it classifies the
  perceiver's description, not the pixels. Its known weak spots are derivation checks and
  polished wrong answers; the cascade (act when confident, escalate when unsure) recovers
  99% of a strong judge's accuracy at 0.36% of the fee.

**What is already on this machine and reusable.** A DeepSeek vision worker that sends PNGs
and writes `observations[] {image, what, confidence}` (`rh_deepseek_vision_cell.py`), a
clean DeepSeek client with a spend ledger (`rhjev/pilot/deepseek.py`), the Jev harness with
four backends and 308 tests, the blinded observer and scoring stack from the RH visual
pilot (`rhvf`), a Mathlib v4.29.0 Lake project, Lean 4.34.1, the Evidence Atlas ingest
channel, and the Explorer scenes (geometry, quaternion/Clifford torus, field lab) as a
source of diagrams. Full paths in §3.

**Decisions only the owner can make (blocking, in order):**

| # | Decision | Default if no word |
|---|---|---|
| D1 | Jev backend for MVE: TypeSafe hosted key (`JEV_API_KEY`), local openJev 151M, or both ("run both" was the 09-26 word for the RH harness) | both, hosted inert until the key exists |
| D2 | Canvas kernel: JSXGraph (LGPL/MIT, commercial-safe) or GeoGebra (apps non-commercial without agreement; Newclid reads `.ggb`) | JSXGraph for the UI, GeoGebra only inside Newclid |
| D3 | Prover on this Mac: Goedel-Prover-V2-8B (Apache-2.0, needs MLX conversion) vs DeepSeek-Prover-V2-7B vs AXLE MCP (currently down) | DeepSeek-Prover-V2-7B via the existing local MLX worker pattern; AXLE when it returns |
| D4 | Budget for P0–P2 DeepSeek Flash calls and Jev calls | USD 10 total, off-peak only, hard cap in every manifest |
| D5 | Whether MVE lives in this repo as `mve/` (sibling of `laboratory/`) or in `~/Developer/Opensens/mve` beside the RH tools | this repo, `mve/`, with the RH-worktree scripts vendored by path, not copied |
| D6 | Licensing stance on GeoX and MultiMath data (HF cards carry no license; GeoX alignment data is disputed by the PGPS9K author) | use only Euclid/Geoperception (Apache-2.0), Geometry3K, LeanGeo, LeanEuclid; cite GeoX and MultiMath |

---

## 1. Vision, and why a vision engine

The owner's framing: humans do geometry by instinct, from the picture; AI does mathematics
by language, and now by Lean. Today the two never meet in the same medium. A human
co-observer looks at a figure and says "those three points are collinear, obviously"; the AI
has no way to *see* that, only to be told. The engine's job is to make the picture a shared
input: the AI produces a record of what it sees, the human corrects or confirms it in place,
and the corrected record becomes a Lean statement both can trust.

Three consequences shape every design choice below.

1. **The record is the product, not the answer.** A benchmark score on MathVista is a side
   effect. The deliverable is a typed observation record with provenance and confidence per
   claim, because that is what a human can audit and what Lean can consume.
2. **Measure before you trust.** Every perceiver claim that *can* be checked on a canvas
   (a point on a line, an angle value, a crossing sign) is re-measured in code before it is
   believed. The RH visual pilot taught this in six rule revisions: every blinding hole was
   found by computing a simple baseline, never by reasoning about it.
3. **Start at level one.** The Mini Motorways picture in the request is the right model: one
   road between two houses first (plane geometry, seven predicates, synthetic diagrams with
   known ground truth), then grow the network only where traffic demands it (annotations,
   solid geometry, knots, atlas panels).

**Where it plugs into the RH programme.** The RH Evidence Atlas and its visual lab already
produce figures (Explorer scenes 01–08, field-lab panels, the rhvf panels). The Claude RH
fleet discovers attack lanes; their results are rendered and land in the lab. MVE closes the
loop in the other direction: a rendered result becomes an observation record, the record's
claims go through the same blinded, baselined protocol the V0 pilot used, and anything that
survives is ingested into the atlas as evidence with a Lean statement attached. The V0
result (no visual Euler fingerprint beyond spacing; observer purity 0.778 below the 0.85 bar)
is the standing warning: the engine must be able to say "nothing here beyond the baseline".

---

## 2. Review findings that drive the design

Full per-source review: `MVE_REVIEW_OF_SOURCES.md`. What matters for the build:

| Finding | Evidence | Design consequence |
|---|---|---|
| CLIP-style encoders miss line drawings; formal captions beat prose as the alignment target | GeoX (MAE on 120K diagrams; formal captions), Euclid (ConvNeXt learns geometry 3–5× faster than ViT/CLIP) | The perceiver prompt asks for a *typed* record, never prose; a small local ConvNeXt head is a P3 option, not a P0 dependency |
| Frontier VLMs fail at incidence and annotation reading | Geoperception: PointLiesOnLine 24% (Gemini-1.5-Pro), Parallel/Perpendicular/Equal hard for all; MathGlance: near-zero fine-grained grounding | Stage A2 re-measures every incidence and every tick/arc/arrow claim; A1 output alone never reaches A4 |
| Diagram→symbol transcription collapses on knots | KnotBench: 0/100 strict PD codes; 32.5% move prediction from image vs 88% from PD code | Topology track (P5) is measurement-first: crossings found in code, PD code assembled in code, the VLM only orients and labels |
| Numeric execute-and-compare is a cheap reward but not verification | GeoX SymPy executor; "proof" by string match | Lean elaboration is the verifier; Newclid decides derivable vs merely drawn; numeric agreement is a filter only |
| Synthetic diagrams with a formal premise transfer to real ones | Euclid image engine (AlphaGeometry premise language), synthetic-only training beats Gemini-1.5-Pro | Ground truth for P0–P2 comes from the Euclid engine, extended to emit full predicate sets; real benchmarks are held-out tests |
| Describe-then-solve helps; retrieval of analogous worked diagrams helps | Geo-LLaVA (+8.5 on solid geometry from image-context pairs), MultiMath caption prompt | The record is an explicit stage; A4 retrieves analogous LeanGeo/LeanEuclid statements as few-shot exemplars |
| Jev is accurate on bounded questions, weak on derivations, text-only | arXiv 2609.26550; TypeSafe docs; local openJev 512-token cap | Jev answers only catalogue questions (§5) on ≤140-word states derived from the record; derivations go to code or Lean; cascade with risk-tiered thresholds fit on a held-out set |
| Reasoning RL cannot fix a wrong parse; long CoT compounds it | GeoPQA, GeoBench | No chain-of-thought is requested from the perceiver; reasoning happens after the record is measured |
| Every local blinding hole was found by a baseline, not by thought | rhvf V0 pilot, six rule revisions | Every evaluation in this plan states its chance rate and a trivial baseline before any model number |

---

## 3. What exists locally (integration map)

Paths verified read-only on 2026-09-27.

| Asset | Path | Use in MVE |
|---|---|---|
| DeepSeek vision cell (PNG as `image_url` data URL, thinking mode with fallback, sha256 of inputs, schema `oae-rh-vision-cell-v1`) | `…/Opensens Academic Explorer/.claude/worktrees/rh-handover-opus-deepseek-dc7dc2/scripts/rh_deepseek_vision_cell.py` (226 lines) | Base of stage A1; MVE record extends its `observations[]` |
| DeepSeek worker runner (fleet, phases, concurrency, dry-run, fake-response, price table, spend ledger, generation guard) | same folder, `rh_deepseek_worker_runner.py` (529 lines) | Fleet contract for every MVE wave |
| Clean DeepSeek client + SpendLedger + off-peak pricing | `~/Developer/Opensens/rh-jev-harness/rhjev/pilot/deepseek.py` (317 lines) | Import, do not copy |
| Jev harness: backends (TypeSafe / Rule / Replay / OpenJev), routers, ledger, CLI (`route_manager`, `route_worker`, `compact`, `fleet`, `study`, `dream-dry`), 308 tests | `~/Developer/Opensens/rh-jev-harness` HEAD `de9f54e` | Stage A3 backend and the fleet/model routing |
| openJev 151M ONNX fp16 + venv | `~/Developer/Opensens/models/openjev/`, `~/Developer/Opensens/runtimes/openjev-venv` | Local Jev backend (text ≤ ~140 words) |
| jev-router (Node; `jev-claude`, `jev-codex`, `jev-explain`) | `~/Developer/Opensens/vendor/jev-router` | Model-tier routing for manager sessions; inert without `~/.jev-router.env` |
| Blinded observer stack: `observer/PROMPT.txt`, HMAC-named text-free PNGs, `V0_RULE.sha256` commitment, purity scorer, sealed held-out builder | `~/Developer/Opensens/rh-visual-fields` (`rhvf/observer.py`, `blind.py`, `scorer.py`, `heldout.py`) | Evaluation protocol for every perception claim (§8) |
| Mathlib project (toolchain v4.29.0, Mathlib in `.lake/packages`) | `~/Developer/Opensens/Opensens Academic Explorer/lean/` (Desktop twin exists) | `lake env lean` elaboration checks for A4 |
| Lean toolchains | `~/.elan` (4.29.0, 4.33.1, 4.34.0; `lean --version` 4.34.1) | LeanGeo needs ≥ 4.15 |
| AXLE routing and formalizer stages | `~/Developer/Opensens/Opensens Academic Explorer/riemann/research/axle_backend.py`, `math_verification.py`, `visual_model_provider.py` | Repair loop pattern; AXLE MCP is down this session |
| Evidence Atlas CLI (`ingest-inbox`, `review`, `validate`, `atlas-build`, `screenshot`, `serve`) | `~/Developer/Opensens/worktrees/oae-rh-atlas-p0-20260924/rh_evidence/cli.py` | Landing channel for MVE results; `atlas_labs.py` for the lab tab |
| Explorer scenes (geometry.html, scene 08 quaternion / Clifford torus, ~25 field-lab modules) | `~/Developer/Opensens/worktrees/zeta-explorer-main/dist/`; live at `http://127.0.0.1:4174/` | Diagram source for P6; captured by `rh_zze_capture.py` or `rh_evidence screenshot` |
| Local MLX worker (text only: Qwen3.5-4B/9B, R1-14B) | `~/Developer/Opensens/runtimes/qwen-local-worker` | Prover host pattern for D3; **no local vision model exists** |
| Codex CLI 0.154, models gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna | `~/.local/bin/codex`; `~/.codex/config.toml` default `gpt-6-sol` (refused on this account; use `gpt-5.6-sol`) | Astra builds, Sol reviews |

This worktree holds only the crystal-platform history (3 commits, no `rh_evidence/`, no
`riemann/`). MVE is built here as `mve/` and reaches the RH scripts by path (D5).

---

## 4. Architecture

```
            pixels                       text ≤140 words                Lean 4
  ┌──────┐   │   ┌──────────┐  record  ┌──────────┐  record   ┌──────────┐  stmt  ┌─────────┐
  │ A0   │ ─►│──►│ A1       │ ───────► │ A2       │ ────────► │ A4       │ ─────► │ A5      │
  │Ingest│       │Perceiver │          │Measurer  │           │Formalizer│        │Prover   │
  └──────┘       │DeepSeek  │          │canvas +  │           │GeoIR→Lean│        │Goedel / │
     ▲           │V4.1 Flash│          │Newclid   │           │LeanGeo   │        │DSP-V2 / │
     │           └────┬─────┘          └────┬─────┘           └────┬─────┘        │AXLE     │
     │                │ claims              │ residual questions   │ elaborate?   └────┬────┘
     │                ▼                     ▼                      ▼                   │
     │           ┌─────────────────────────────────────────────────────────┐          │
     │           │ A3 Decision layer: code → Jev (Choice/Score/Noul) →      │          │
     │           │    LLM (DeepSeek text / Opus / Sol) → human              │          │
     │           └───────────────────────────┬─────────────────────────────┘          │
     │                                       │ human queue                            │
     │           ┌───────────────────────────▼─────────────────────────────┐          │
     └───────────│ A6 Co-observer surface: image | record | Lean | render-  │◄─────────┘
                 │    back (Penrose / JSXGraph / ProofWidgets4); verdict    │
                 │    buttons write human_confirmed / human_rejected        │
                 └───────────────────────────┬─────────────────────────────┘
                                             ▼
                 ┌─────────────────────────────────────────────────────────┐
                 │ A7 Ledger + registry: manifest, spend, hashes, wave id,  │
                 │    rh_evidence ingest-inbox for atlas-bound results      │
                 └─────────────────────────────────────────────────────────┘
```

### A0 Ingest
Sources: Euclid image engine (synthetic, ground truth attached), Geoperception / Geometry3K
/ LeanGeo-Bench / KnotBench images (held-out tests), Explorer and atlas screenshots, user
uploads. Every image is hashed; text-bearing images are OCR'd once (DeepSeek-OCR-2 or the
perceiver's OCR branch) so labels are known before perception.

### A1 Perceiver (DeepSeek V4.1 Flash, `deepseek-flash`)
One call per image. The prompt asks for the record's `entities`, `relations` (status
`perceived`), `claims` and `not_determinable_from_image`, in JSON, with pixel coordinates
for every entity and **no chain of thought**. Temperature 0. Two independent calls with
shuffled entity-naming instructions give a disagreement signal; disagreement is itself a
Jev question (§5, Q-agree). DeepSeek V4-Pro has no image input and is used only as a text
judge. Claude Opus and GPT (Sol/Astra) are disagreement judges, never primary perceivers.

### A2 Measurer
- **Canvas re-measure** (Draw2Think pattern): every perceived incidence, angle, length,
  parallel/perpendicular relation is recomputed from `px` coordinates in code (JSXGraph
  headless or plain numpy). `measure_residual` is recorded; a relation becomes `measured`
  only if the residual is below a per-predicate tolerance that is itself fit on synthetic
  data (§8).
- **Symbolic derivability** (Newclid / AlphaGeometry2 DDAR): given the measured
  construction, which relations are derivable from the stated premises and which are merely
  drawn? Derivable ones become `derived`; drawn-but-not-derivable ones stay `measured` and
  are flagged for the human ("true in this figure, not in general").
- **Topology**: crossings detected in code (classical CV on the strand skeleton), PD code
  assembled in code, invariants computed by SnapPy/pyknotid. The VLM contributes over/under
  orientation and labels only, each re-checked against the skeleton.

### A3 Decision layer (Jev cascade)
Described in §5. Input is never pixels: it is a ≤140-word state built from the record.
Order of preference: code (exact, free) → Jev (bounded, calibrated) → LLM (needs words or a
derivation) → human (below the floor, `other`, or two describers disagree).

### A4 Formalizer
Record → GeoIR (MechGeo-style intermediate text) → Lean 4 statement in LeanGeo vocabulary
over Mathlib `EuclideanGeometry` (`Collinear`, `Concyclic`, `∥`, `⟂`, `dist`, `∠`,
`Wbtw/Sbtw`). Deterministic translation for every predicate in the schema; the LLM (DeepSeek
text or Sol) is used only to name hypotheses and choose the goal when the problem text gives
one. Elaboration via `lake env lean` in the Mathlib project; failures go through a bounded
repair loop (Euclean's four-stage pattern, `axle_backend.bounded_repair` shape). Statement
equivalence against a reference (LeanGeo-Bench 122, LeanEuclid 173) uses the E3 checker
where the target dialect allows it, else a Sol judgment recorded as such.

### A5 Prover
Goedel-Prover-V2-8B or DeepSeek-Prover-V2-7B locally (D3), AXLE MCP when available, with a
per-statement timeout and a counterexample search (Newclid numeric model) before any proof
attempt. Proof status is recorded; "proved" means the Lean kernel accepted it, nothing less.

### A6 Co-observer surface
A lab tab (rendered through `atlas_labs.py` conventions) showing four panes: the source
image, the record as an editable table, the Lean statement, and the render-back of the
statement (Penrose for Euclidean substance/style; JSXGraph for interactive canvases;
ProofWidgets4 inside the Lean infoview for the Lean-side view). Each relation row has
confirm / reject / "not visible" buttons; every click writes a `human_confirmed` or
`human_rejected` status with the human's id, and appends to the labelled set that fits the
Jev thresholds. This is the Human-AI co-observer loop in its minimal form.

### A7 Ledger and registry
Every wave has a `manifest.json` (pinned price table, `run_cap_usd`, model ids, prompt
hashes, code sha) and a `ledger.jsonl` (append-only). Atlas-bound results go through
`rh_evidence ingest-inbox` with the record id and the Lean statement hash. Nothing is
published from a shared worktree; build from `git archive HEAD`.

---

## 5. The Jev decision layer for geometry and topology

The two infographics in the request reduce to one root question: *do you know every
possible answer before you ask?* Applied to a diagram:

| Question about the picture | Known answer list? | Route |
|---|---|---|
| Is point C on line AB (given coordinates)? | yes, and computable | **code** (A2), never Jev |
| What is this diagram's domain? | yes: {euclidean_plane, solid, plot, chart, graph, knot, surface, other} | **Jev Choice** |
| Is this quadrilateral cyclic, given the measured record says four points are within tolerance of one circle? | yes/no, evidence in state | **Jev Noul**, threshold high |
| Is the perceiver's free-text claim a restatement of a measured relation, a new relation, or unsupported? | yes: {restates, new, unsupported, other} | **Jev Choice** |
| Which solver should try this statement first? | yes: {newclid, lean_esmt, prover, none} | **Jev Choice** |
| What is the genus of this surface diagram? | ordered small integers | **Jev Score** (0–5) after code computed Euler characteristic where possible; else human |
| Did two independent perceptions of the same image agree on the entity set? | yes/no, computable | **code** first (set difference); Jev only for near-miss naming |
| Does this angle-chase step follow from the previous ones? | needs a derivation | **LLM or Lean**, never Jev (2609.26550) |
| Is this figure's statement equivalent to reference theorem T? | needs a derivation | **E3 / Sol**, never Jev |
| Explain why this construction is impossible | generative | **LLM** |

**Question catalogue (initial).** Each has an id, a primitive, a label set that ends in
`other`, a state template ≤140 words, and two thresholds (τ_high act, τ_low escalate).

| id | primitive | labels | state template |
|---|---|---|---|
| Q-domain | Choice | euclidean_plane, solid, function_plot, chart, graph, knot, surface, braid, other | entity kind histogram + first 5 claims |
| Q-shape | Choice | triangle, quadrilateral, circle, polygon_n, line_config, other | entity kinds + incidence counts |
| Q-relation-kind | Choice | tangent, secant, disjoint, internally_tangent, concentric, other | two circle/line entities with measured residuals |
| Q-cyclic | Noul | yes/no | four points, circle-fit residual, tolerance |
| Q-claim-status | Choice | restates_measured, new_relation, unsupported, contradicts_measured, other | one free-text claim + the measured relations that mention its entities |
| Q-annotation | Choice | tick_equal, arc_equal, right_angle_box, arrow_parallel, none, other | crop description of a mark and the entities near it |
| Q-solver | Choice | newclid, lean_esmt, prover, human, none | statement head + predicate mix |
| Q-drift | Noul | yes/no | goal text vs current statement text |
| Q-knot-type | Choice | unknot, trefoil, figure_eight, 5_1, 5_2, 6_x, other | PD code + invariants computed in code (crossing number, determinant, Jones if available) |
| Q-genus | Score | 0..5 | Euler characteristic computed in code, boundary count, handle claims |
| Q-agree | Noul | yes/no | entity-set diff summary of two perceptions |
| Q-human | Noul | yes/no ("needs a human") | any record whose measured/perceived ratio < 0.5 or with contradicted relations |

**Thresholds and audits.** Thresholds are not one number: destructive or irreversible
routes (writing `formal`, ingesting into the atlas) need τ ≥ 0.9; read-only routes accept
τ ≥ 0.7; anything below τ_low = 0.5 or answered `other` goes to the human queue. Every τ is
fit on a labelled held-out set with at least 10 yes and 10 no per question (the harness's
trial floor); fewer means the question is inconclusive and its route is forced to human.
A fixed 10% of confident answers is audited by Opus each wave and the audit result is
recorded on the decision. Jev's "cannot hallucinate" holds only because the label set is
ours; the `other` label is the escape hatch and is always last.

**Two backends, one contract.** TypeSafe hosted (`jev-1.13.0`, needs `JEV_API_KEY`; the
endpoint and wire format in `rhjev/backends.py` are still assumptions and must be verified
against docs.typesafe.ai before the first live call) and local openJev 151M (Apache-2.0,
512-token cap: states must stay ≤ ~140 words, so every template is measured in tokens at
build time). Per the owner's 09-26 word for the RH harness, "highest efficiency claim or run
both": run both on the labelled set in P2 and keep whichever meets the threshold at lower
cost; the harness's ReplayBackend makes the comparison reproducible.

**The three primitives map onto the sketch in the request:** Choice is the simplex
(a+b+c=1), Score is the ordered points on [0,1] under a sigmoid, Noul is p + (1−p) = 1.
The overlapping-distributions sketch is the cascade: the shaded band between the two
thresholds is where the robot hands the item to the human.

---

## 6. Agents, roles and fleet operation

| Role | Who | Does | Never does |
|---|---|---|---|
| Builder | **Codex Astra** (`gpt-6-astra`) | Implements work packets (§10) in `mve/`, writes tests first, opens one branch per packet | Spends DeepSeek or Jev budget without a manifest cap; publishes |
| Reviewer and fleet operator | **Claude Opus** | Reviews every packet (python-reviewer + security-reviewer agents), runs waves through `rh_deepseek_worker_runner.py`, audits the 10% Jev sample, keeps the ledger, ingests results into the atlas | Edits the Jev thresholds by hand (they are fit, not chosen) |
| Structured reviews | **Codex Sol** (`gpt-5.6-sol`) | Statement-equivalence judgments, prompt reviews, packet acceptance | Primary perception |
| Critical strategy | **Astra + Fable** cross-review | Phase gates (§7), any change to the record schema, any change to §8 protocol | — |
| Core vision worker | **DeepSeek V4.1 Flash** (`deepseek-flash`) | A1 perception; A4 hypothesis naming (text) | Judging its own output |
| Text judge | DeepSeek V4-Pro / Opus / Sol | Disagreement resolution in A3's LLM tier | Looking at pixels (V4-Pro cannot) |
| Decision layer | Jev (TypeSafe / openJev) | §5 catalogue only | Any "is this true" question |
| Prover | Goedel-Prover-V2 / DeepSeek-Prover-V2 / AXLE | A5 | Being cited as "proved" without kernel acceptance |
| Local slow jobs | Qwen 3.6 / R1 (MLX) | Batch GeoIR→Lean translation drafts, overnight repair loops | Perception (text-only) |
| Co-observers | Owner, invited humans | Confirm/reject relations in A6; name features; set the goal | — |

**Fleet protocol (Opus).** Waves are numbered `mve-wNN`; each has a manifest with a price
table pinned from api-docs.deepseek.com, `run_cap_usd`, and the code sha. Waves run
off-peak (the runner already waits for the window). One runner per ledger. Every wave's
`SUMMARY.json` carries: images, records produced, relations by status, Jev routes by
question, human-queue size, cost. A wave that produces zero `measured` relations stops the
lane until a human looks (a false STOP is invisible, a false CONTINUE is caught at review).
Reviews are batched at the end of a stretch, one packet, flat folder, ≤6 files with SHA-256s.

---

## 7. Phased plan with gates

Weeks are calendar weeks of part-time work; every gate states its chance rate and baseline.

### P0 — Foundation (week 1)
- `mve/` package skeleton: `record.py` (dataclasses + JSON-schema validation against
  `schemas/mve_observation_record.json`), `ingest.py`, `perceiver.py` (wraps the vision
  cell by path), `measure.py`, `decide.py` (wraps `rhjev` backends), `formalize.py`,
  `prove.py`, `ledger.py`, `cli.py`. Tests first; no network in tests (ReplayBackend and
  `--fake-response`).
- Pull the Euclid image engine (Apache-2.0) as a vendored generator; extend it to emit the
  full predicate set per diagram as a ground-truth record (`image.ground_truth_ref`).
- Geoperception harness: run DeepSeek Flash, Claude, and one GPT model on a 300-item
  stratified sample, stateless, temperature 0; record per-predicate accuracy.
- **Gate G0:** Geoperception numbers exist for three models with the random baseline
  (16.4% average) printed beside them; the record schema validates 100 synthetic records;
  tests ≥ 80% coverage of `mve/`. Cost ≤ USD 1.

### P1 — Perception and measurement (weeks 2–3)
- Perceiver prompt v1 (JSON record, no CoT, pixel coordinates). Two-call disagreement.
- A2 canvas re-measure for Collinear, Concyclic, Parallel, Perpendicular, EqualLength,
  EqualAngle, Midpoint, Between, RightAngle; tolerances fit on 2,000 synthetic diagrams so
  that the false-positive rate on random point triples is ≤ 2%.
- Newclid integration: `.ggb`/JGEX export from the measured record; derivable vs drawn.
- **Gate G1:** on a sealed held-out set of 500 synthetic diagrams (built with
  `rhvf/heldout.py` conventions, HMAC-named, sealed before the prompt is frozen):
  PointLiesOnLine precision ≥ 0.90 and recall ≥ 0.70 *after* re-measure, versus the
  perceiver-alone number and the random baseline; on real Geoperception, ≥ Euclid-L's
  64.9 average or a written explanation of the gap. Cost ≤ USD 3.

### P2 — Decision layer (weeks 3–4)
- Question catalogue §5 implemented as data (`mve/questions/*.json`), token-measured
  templates, both backends through `rhjev`.
- Labelled set: ≥ 300 items across the 12 questions, at least 10 yes / 10 no per question,
  labels from synthetic ground truth where possible and from two humans (owner + one) where
  not; inter-rater agreement recorded.
- Fit τ_high / τ_low per question on a held-out half; freeze in a calibration lock file
  with the labelled set's SHA-256.
- **Gate G2:** cascade accuracy on the held-out half within 3 points of Opus-as-judge on the
  same items (the 2609.26550 bar), human-queue rate ≤ 25%, cost per 1,000 decisions
  reported; TypeSafe vs openJev comparison table. Jev spend ≤ USD 1.

### P3 — Formalizer (weeks 4–6)
- Deterministic GeoIR → Lean translation for every schema predicate; LeanGeo vendored as a
  Lake dependency in the Mathlib project (toolchain bump to ≥ 4.15 is already satisfied);
  elaboration via `lake env lean`; bounded repair loop (≤ 3 rounds, DeepSeek text or Sol).
- Reference alignment: LeanGeo-Bench (122) and LeanEuclid (173) statements as retrieval
  exemplars and equivalence targets.
- **Gate G3:** on 100 synthetic diagrams with known premises, ≥ 80% of generated
  statements elaborate first pass and ≥ 95% after repair; on 50 LeanGeo-Bench diagrams
  (rendered from their statements), ≥ 40% judged equivalent by Sol with the judgment
  recorded, versus a trivial baseline of "emit the nearest retrieved statement".
- Optional local perception head (Euclid ConvNeXt recipe) if G1 showed DeepSeek Flash cost
  or latency is the bottleneck.

### P4 — Prover and co-observer surface (weeks 6–8)
- A5 with D3's prover; counterexample search first; per-statement timeout 120 s.
- A6 lab tab: four panes, verdict buttons, labelled-set append; render-back via Penrose
  (Euclidean domain) and JSXGraph; ProofWidgets4 view in the Lean project.
- **Gate G4:** ≥ 30% of G3's equivalent statements proved (kernel-accepted) within budget;
  a 30-minute co-observer session with the owner on 20 real diagrams produces
  human_confirmed/rejected statuses that re-fit at least one Jev threshold; the tab is
  built from `git archive HEAD` and passes the atlas labs check.

### P5 — Topology track (weeks 8–10)
- Strand skeletonisation and crossing detection in code; PD code assembly; SnapPy /
  pyknotid invariants; VLM only for over/under orientation with per-crossing confidence.
- Q-knot-type and Q-genus live; KnotBench subset (≤ 7 crossings) as held-out.
- **Gate G5:** strict PD transcription ≥ 30% on ≤ 7 crossings (KnotBench frontier baseline
  is 0/100), knot-type accuracy versus the chance rate of the label set, and every wrong
  transcription traced to skeleton or orientation.

### P6 — RH integration (continuous from P4)
- Ingest Explorer scenes and rhvf panels; produce records; run any "feature" claim through
  the §8 protocol with baselines before it is called a finding; ingest survivors via
  `rh_evidence ingest-inbox` with the Lean statement attached.
- **Gate G6:** the first atlas record whose evidence is an MVE observation record plus a
  Lean statement, reviewed by Sol, with the V0 lesson applied (a computed baseline printed
  beside every visual claim).

---

## 8. Evaluation and honesty protocol (from the RH visual pilot)

1. **Chance and baseline first.** Every metric is reported next to its chance rate and a
   trivial baseline (nearest retrieved statement, "everything is collinear", crop length).
2. **Seal before you look.** Held-out sets are built with HMAC-named files and sealed
   hashes (`rhvf/heldout.py` pattern); the prompt/rule hash is committed before unsealing.
3. **Controls in every wave.** Positive controls (synthetic diagrams whose ground truth is
   known) and negative controls (diagrams with a deliberately corrupted label or a random
   point set). A valid control finding the too-strict check is a pass, not a defect.
4. **Two describers, one arbiter.** Disagreement between two perceiver calls is recorded
   before either is trusted.
5. **Text-free where the question is visual.** When the claim is "the picture shows X",
   labels are stripped (rhvf `pngfixed.py`) so the model cannot read the answer.
6. **Asymmetric stopping.** A lane stops only when the decision layer is confident it
   should; stopped items are audited at 10%.
7. **Claim the check you ran.** Reports say "elaborates", "kernel-accepted", "Sol-judged
   equivalent", never "verified" without the verifier's name.

---

## 9. Costs

| Item | Rate (verified 2026-09-27) | P0–P2 estimate |
|---|---|---|
| DeepSeek V4.1 Flash, off-peak | $0.15 / $0.60 per MTok in/out | ~3,000 images × ~2k tokens ≈ USD 2–4 |
| DeepSeek V4-Pro text judge | $1.32 / $3.96 peak | ≤ USD 1 (disagreements only) |
| Jev hosted | $0.042 per MTok in, output free | < USD 0.20 for 10k decisions |
| openJev local | electricity | 0 |
| Codex Sol / Astra | account quota | one packet per phase gate |
| Prover on Mac | time | overnight batches |

Owner cap D4 governs; every manifest carries `run_cap_usd`; peak-hour calls are refused by
the runner.

---

## 10. Work packets for Codex Astra

Each packet: one branch `codex/mve-wpN-<slug>` off `claude/math-vision-engine-078a13`,
tests written first, ≥ 80% coverage of new code, no network in tests, `python3` not
`python`, files ≤ 800 lines, functions ≤ 50 lines, immutable records (new objects, never
in-place), conventional commit messages, review by Opus before merge.

| WP | Deliverable | Files | Acceptance |
|---|---|---|---|
| WP-1 | Record model + validation + CLI skeleton | `mve/record.py`, `mve/cli.py`, `tests/mve/test_record.py` | 100 synthetic records validate; invalid status transitions rejected (`perceived` → `formal` refused) |
| WP-2 | Euclid generator vendored + full-predicate ground truth | `mve/gen/euclid_engine.py`, `mve/gen/predicates.py`, `data/mve/synthetic/` | 2,000 diagrams with records; determinism by seed; licence file carried |
| WP-3 | Perceiver wrapper | `mve/perceiver.py` (by-path import of the vision cell), `mve/prompts/perceiver_v1.md`, replay fixtures | dry-run and fake-response paths covered; prompt hash in provenance; V4-Pro refused for images |
| WP-4 | Measurer | `mve/measure/canvas.py`, `mve/measure/tolerances.json`, `mve/measure/newclid_bridge.py` | tolerances fit script reproducible; FP ≤ 2% on random triples; Newclid derivable/drawn split on 50 fixtures |
| WP-5 | Decision layer | `mve/decide.py`, `mve/questions/*.json`, `mve/calibration/lock.json` | both backends via `rhjev`; token length asserted ≤ 512; τ fit script; 10% audit sampler |
| WP-6 | Formalizer | `mve/formalize/geoir.py`, `mve/formalize/lean_emit.py`, `mve/formalize/repair.py`, Lake dep on LeanGeo | G3 numbers reproduced from a fixture set; `lake env lean` invoked with timeout; no `sorry` accepted as success |
| WP-7 | Prover + counterexample | `mve/prove.py` | kernel acceptance parsed from Lean output; timeouts recorded |
| WP-8 | Co-observer tab | `mve/lab/` (HTML built from `git archive HEAD`), Penrose/JSXGraph render-back, verdict endpoint writing statuses | atlas labs check passes; verdict round-trip test |
| WP-9 | Fleet + ledger | `mve/fleet/manifest.py`, `mve/fleet/wave.py` (wraps the worker runner by path) | manifest schema; cap enforced in dry-run; SUMMARY.json produced |
| WP-10 | Topology | `mve/topo/skeleton.py`, `mve/topo/pd.py`, `mve/topo/invariants.py` | strict PD on synthetic knots ≤ 7 crossings ≥ 30%; SnapPy verify |
| WP-11 | Evaluation suite | `mve/eval/geoperception.py`, `mve/eval/heldout.py` (rhvf pattern), `mve/eval/report.py` | every report prints chance + baseline; sealed-set builder; controls injected |
| WP-12 | paper2agent skills (optional) | `skills/mve-euclid-engine/`, `skills/mve-leangeo/` | run `paper2agent` on Euclid and LeanGeo repos to produce tested MCP tools for the generator and the theorem library; only if WP-2/WP-6 show repeated manual glue |

**Opus review checklist per packet:** security (no keys in code, keychain or env only;
no path traversal on image inputs; subprocess calls with timeouts and argument lists),
correctness (status transitions, tolerance fitting reproducible, hashes of every input),
honesty (every metric beside its baseline; no "verified" without a verifier name), scope
(nothing beyond the packet), tests (RED → GREEN visible in the branch history).

**Dispatch (owner or Opus session, after telling the packet's owner):**

```bash
codex exec -m gpt-6-astra -C docs/mve --sandbox read-only --skip-git-repo-check -o docs/mve/ASTRA_VERDICT_MVE_PLAN_20260927.md "Read README_FOR_ASTRA.md first, then MVE_PLAN.md and MVE_REVIEW_OF_SOURCES.md. Review the plan as the builder who will implement WP-1..WP-11: list every ambiguity that would block a work packet, every claim you believe is wrong (cite the section), the order you would build in, and a revised gate table if any gate is untestable. Do not write code."
```

Save the verdict verbatim beside the packet with its SHA-256 and apply it the way earlier
Astra verdicts were applied.

---

## 11. Risks and open questions

| Risk | Mitigation |
|---|---|
| DeepSeek V4.1 Flash image API changes or is retired (the `-vision-exp` model was already folded into it) | perceiver behind an interface; Claude/GPT fallback for perception is allowed only with a written cost note |
| Jev endpoint/wire format assumed in `rhjev/backends.py` | WP-5 verifies against docs.typesafe.ai before any live call; openJev path is independent |
| openJev 151M token cap (512) | every template token-measured at build time; ≤140 words enforced |
| GeoGebra non-commercial licence | JSXGraph default (D2); GeoGebra only inside Newclid |
| GeoX / MultiMath data licences unresolved | D6 default excludes them from training and evaluation; cite only |
| AXLE MCP down | D3 default local prover; AXLE optional |
| No local vision model on the Mac | accepted for P0–P4; Euclid ConvNeXt head is the P3 option |
| Newclid repo licence not fetched (404) | confirm before vendoring; AlphaGeometry-derived parts are CC-BY-4.0 |
| Draw2Think, MechGeo, KnotBench code licences unverified | adopt the *designs*; vendor only after a licence check |
| Perceiver reads the answer from labels | text-free renders for visual claims (§8.5) |
| Reasoning compounds a wrong parse | no CoT in A1; reasoning only after A2 |
| A false STOP is invisible | asymmetric stopping + 10% audit + human queue metrics in every SUMMARY |
| Two sessions run the same packet | tell the packet's owner before dispatch; one runner per ledger |

Open questions for the Astra review: is GeoIR the right intermediate or should the record
itself carry a Lean-typed field per relation; should the LeanGeo dialect or native Mathlib be
the emission target for P3 (LeanGeo is thin outside plane geometry); how to score
"equivalence" honestly when E3 does not cover the dialect; what the first topology
statement in Lean should even be (Mathlib has little knot theory), so P5 may end at
invariant records rather than Lean statements.

---

## 12. Sources

Requested: arXiv 2409.00147 (MultiMath), github.com/pengshuai-rin/MultiMath,
github.com/InternScience/GeoX, arXiv 2412.10455 (Geo-LLaVA), arXiv 2412.11863 (GeoX),
arXiv 2409.13729 (MathGLM-Vision), youtube.com/watch?v=TDeNkF4cElg (Jev plays Mario),
aiblewmymind.substack.com. Added: arXiv 2412.08737 (Euclid), arXiv 2609.26550 (JEV-as-a-Judge),
docs.typesafe.ai, api-docs.deepseek.com, github.com/Newclid/Newclid, github.com/project-numina/LeanGeo,
github.com/loganrjmurphy/LeanEuclid, arXiv 2608.02295 (MechGeo), arXiv 2607.19374 (Euclean),
github.com/draw2think/harness-geometry, arXiv 2605.09900 (KnotBench), arXiv 2503.20745
(MathGlance), arXiv 2412.00947 (VisOnlyQA), github.com/leanprover-community/ProofWidgets4,
github.com/penrose/penrose, github.com/Goedel-LM/Goedel-Prover-V2,
github.com/deepseek-ai/DeepSeek-Prover-V2. Local: see §3.
