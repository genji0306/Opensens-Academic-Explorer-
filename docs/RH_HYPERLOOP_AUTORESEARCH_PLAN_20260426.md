# RH Klein → Hyperloop Autoresearch: Upgrade Plan

Date: 2026-04-26
Status: scaffolded as `feature/rh-hyperloop-phase0`; Phase BP paused.

## 1. Diagnosis — why the current orchestrator orbits

Campaign memory shows 56 phases, 69 unconditionals, 16 reformulations, three meta-theorems. Best Klein scores stuck around `0.61` against baselines around `0.57–0.60`. The latest [RH RI Functional Vector Report](RH_RI_FUNCTIONAL_VECTOR_REPORT_20260426.md) self-diagnoses the wall:

- Klein lift over baseline collapsed to `+0.0157 → +0.0455`.
- Score peaks in round 1 then declines.
- Same dominant failure classes recur: `finite_window_only`, `large_obligation_load`, `the_explicit_formula_is_exact_but_not_by_itself_a_proof_of_rh`, `no_accepted_operator_construction_is_known`, `candidate_spaces_have_not_yielded_an_accepted_proof`.
- Timeguard ranks the same five work packages every cycle.

**Root cause.** Every campaign produces JSON scorecards and prose reformulations. None of those artifacts are *monotone* — a future campaign can re-derive, re-score, and re-justify the same idea without contradicting anything. The orchestrator has no committed ground truth that future runs are *forced to extend*. Klein topology already enforces a surface↔depth round-trip (`riemann/research/klein_topology.py:51-127`), but the round-trip lives entirely in the informal layer, so its residue is also informal and erasable.

The orbit is structural, not motivational: **soft artifacts cannot break a research orbit**.

## 2. The disruptor — Hyperloop = Klein ⊗ Lean ⊗ Gödel

A hyperloop adds two orthogonal axes to the Klein loop. Every cycle deposits hard residue.

| Axis | Existing | Add |
|---|---|---|
| Surface ↔ Depth | Klein (informal lanes) | — |
| Informal ↔ Formal | — | **Lean 4** via [AXLE](https://github.com/AxiomMath/axiom-lean-engine) + [axle-mcp-server](https://github.com/AxiomMath/axle-mcp-server) |
| Object ↔ Meta | — | **Gödel meta-loop** (theorems about the orchestrator itself) |

The orbit-breaker is the **Lean-monotone-residue invariant**:

> Every campaign must close with at least one of:
> (a) a new Lean lemma added to `lean/RH/Lemmas/`, or
> (b) a new Lean-checked obstruction certificate in `lean/RH/Obstructions/`, or
> (c) a Gödel-style meta-theorem proving the current branch is unproductive, also in Lean.
>
> A campaign that produces no `.lean` delta is not a campaign — it is rejected at gate.

Lean is monotone: a checked theorem cannot be silently retracted. A campaign now either advances the formal corpus or self-certifies as unproductive. Repetition becomes provably impossible without first deleting committed Lean code, which is detectable in CI.

This is the same primitive that lets Aristotle (arXiv 2510.01346), AxiomProver (12/12 Putnam 2025), and the Axiom reasoning engine escape orbits that defeated earlier informal LLM-math systems: *"When you write a proof, it's either correct or it's not. Formal verifiers like Lean provide perfect ground truth."*

## 3. External grounding

| Source | What we take | Where it lands |
|---|---|---|
| [axiom-lean-engine (AXLE)](https://github.com/AxiomMath/axiom-lean-engine) | Cloud Lean 4 verifier with `extract_decls`, 15-min timeout | `riemann/research/lean_bridge.py` |
| [axle-mcp-server](https://github.com/AxiomMath/axle-mcp-server) | MCP tools for Lean check/eval | `.mcp.json` + `lean_mcp_client.py` |
| [gdm-formal-conjectures](https://github.com/AxiomMath/gdm-formal-conjectures) | Conjecture format (NL + Lean side-by-side) | `lean/RH/Conjectures/` |
| [Putnam2025](https://github.com/AxiomMath/putnam2025) | Multi-agent ensemble: many proposers → cheap verifier → reject | `riemann/research/ensemble.py` |
| [Aristotle (arXiv 2510.01346)](https://arxiv.org/abs/2510.01346) | 3-component split: Lean search + informal lemma generator + dedicated solver | `tail_control_agent` + `klein_agent` + `lean_search_agent` |
| FunSearch (Nature 2024) | Evolutionary program search with LLM mutation | `riemann/research/evolution.py` |
| Algorithm Discovery: Evolutionary Search Meets RL (2025) | Hybrid evolution + RL credit | Population layer |
| Olympiad-level RL formal reasoning (Nature 2025) | RL signal from Lean check pass/fail | Reward backbone |
| FrontierMath / IMProofBench / EternalMath / LemmaBench | External moving-target benchmarks | `riemann/research/external_eval.py` |
| Agentic Neurosymbolic Collaboration (arXiv 2026) | Cooperative agent design | `meta_agent.py` |

## 4. Phase plan

Seven phases. Phases 0–3 create the monotone residue. Phases 4–7 amplify it.

### Phase 0 — Spike & freeze (~3 days) — SCAFFOLDED

- Pause Phase BP.
- Wire AXLE bridge with mock fallback so CI passes without an API key.
- Formalize one trivial RH-adjacent lemma (functional-equation mirror) in `lean/RH/Lemmas/FunctionalEquationMirror.lean`.
- MCP config updated for `axle-mcp-server` (env-gated).

Exit gate: one `.lean` file, one green AXLE check (or mock), one new git commit.

### Phase 1 — AXLE bridge + Lean residue gate (~2 weeks)

**New:** `lean_bridge.py`, `lean_residue.py`, `lean/RH/{Lemmas,Obstructions,MetaTheorems,Conjectures}/`
**Modify:** `orchestrator.py` (call `LeanResidueLedger.diff` per round; reject `RESIDUE_GATE_FAIL`), `certificate_program.py` (every certificate must ship a `lean_skeleton`).

This is the orbit-breaker landing.

### Phase 2 — Autoformalization round-trip (~2 weeks)

**New:** `autoformalizer.py`, `autoinformalizer.py`
**Modify:** `klein_agent.py:38-120` to emit Lean skeleton with `sorry` placeholders alongside JSON proof skeletons.

The "round_trip_canonicality" invariance becomes machine-checkable: surface→depth→surface in NL must commute with NL→Lean→NL.

### Phase 3 — Verifier-rejection ensemble (~3 weeks)

**New:** `ensemble.py`, `verifier_gate.py`, `lean_search_agent.py`, `aristotle_style_agent.py`
**Effect:** Klein `total_score` is demoted from primary signal to *tiebreaker*. Primary signal is binary Lean truth.

### Phase 4 — Live external benchmark loop (~2 weeks)

**New:** `external_eval.py` runs FrontierMath, IMProofBench, LemmaBench, gdm-formal-conjectures.
If internal score rises but external stays flat → trigger `REPLAN`.
The only signal that can falsify the campaign's self-perception of progress.

### Phase 5 — Predictive dead-end vaccination (~1 week)

Train classifier on `dead_end_library`. Reject candidates with `risk > 0.85` unless they cite the lemma that nullifies the blocker.

### Phase 6 — Gödel meta-loop / orbit-breaker certificates (~2 weeks)

Three meta-theorems (extending the existing three universal closures):

- **MT-α (Lean-Monotone Residue):** any campaign with empty Lean delta and ≥1 persistent obstruction class is unproductive.
- **MT-β (Obstruction Closure):** if obstruction `C` survived ≥`N` campaigns, no proposer in family `F(C)` is promoted without a Lean exclusion certificate against `C`.
- **MT-γ (Reformulation Bound):** if a reformulation reduces to a previously-tracked one under the canonical operator signature, it is rejected.

**New:** `meta_agent.py` — output lands in `lean/RH/MetaTheorems/`.

### Phase 7 — Hyperloop topology fusion (~2 weeks)

`hyperloop_topology.py` defines the `Hyperloop` mode with three feedback signals: `klein_score` (soft tiebreaker), `lean_residue_delta` (hard gate), `meta_closure_signal` (hard gate).
CLI: `--topology hyperloop`.
Tri-arm benchmark: `baseline` vs `klein` vs `hyperloop` on the same seed packs.

## 5. Concrete file inventory

| New | Existing to modify |
|---|---|
| `lean/RH/lakefile.lean`, `lean-toolchain` | `riemann/research/orchestrator.py` |
| `lean/RH/{Lemmas,Obstructions,MetaTheorems,Conjectures}/` | `riemann/research/klein_agent.py` |
| `riemann/research/lean_bridge.py` | `riemann/research/klein_topology.py` |
| `riemann/research/lean_residue.py` | `riemann/research/certificate_program.py` |
| `riemann/research/autoformalizer.py` | `riemann/research/dead_end_library.py` |
| `riemann/research/autoinformalizer.py` | `riemann/research/obligation_ledger.py` |
| `riemann/research/ensemble.py` | `riemann/research/observer_agent.py` |
| `riemann/research/verifier_gate.py` | `riemann_research.py` (CLI flag) |
| `riemann/research/external_eval.py` | `.mcp.json` (axle-mcp-server) |
| `riemann/research/evolution.py` | `pack/pg_klein_orchestrator.py` |
| `riemann/research/meta_agent.py` | |
| `riemann/research/hyperloop_topology.py` | |
| `riemann/research/lean_search_agent.py` | |
| `riemann/research/aristotle_style_agent.py` | |
| `tests/test_lean_bridge.py`, `test_lean_residue.py`, `test_verifier_gate.py`, `test_meta_agent.py`, `test_hyperloop_topology.py` | extend `tests/test_riemann_research_orchestrator.py` |

## 6. Sequencing & gates

```
Phase 0 (3d) ─► Phase 1 (2w) ─► Phase 2 (2w) ─► Phase 3 (3w) ─►
                                                              │
                       Phase 4 (2w) ◄── Phase 5 (1w) ◄────────┤
                            │                                  │
                            ▼                                  ▼
                       Phase 6 (2w) ─────────────────► Phase 7 (2w)
```

Hard gates:

- **Gate 1:** Phase 1 ships only when one full RH campaign produces a non-empty `lean/RH/**` delta on every round.
- **Gate 3:** Phase 3 ships only when verifier rejection rate exceeds 70% on a synthetic-hypothesis holdout drawn from `dead_end_library`.
- **Gate 6:** Phase 6 ships only after MT-α is checked in Lean and applied to one real past campaign log.
- **Gate 7:** Phase 7 ships only when head-to-head `klein` vs `hyperloop` on `rh-ri-functional-vector` shows hyperloop strictly dominates klein on the *external* scorecard, even if internal score drops.

The willingness to **let internal score drop** at Gate 7 is the cultural shift that operationalizes the disruptor.

## 7. Theoretical claim

Three orbit-breakers, individually well-known, composed:

1. **Monotone formal residue** (Lean) — destroys "soft reformulation" cycles.
2. **External moving-target evaluation** — destroys "score your own homework" cycles.
3. **Object-level / meta-level diagonalization** (Gödel meta-loop) — destroys "paraphrase the same approach" cycles.

The Klein topology is the right *spatial* primitive (round-trip, surface↔depth) but operates only on axis 1. The hyperloop replicates that primitive on three orthogonal axes. The phrase "infinite loop of research based on mapping" maps cleanly: failure is *one-axis* mapping; remedy is *higher-dimensional* mapping with hard residue per axis.

## 8. Risk register

| Risk | Mitigation |
|---|---|
| AXLE rate limits stall campaigns | Cache verified lemmas locally; Phase 1 budget assumes ~200 Lean checks per round; AXLE permits 20 concurrent ≤15 min |
| Lean formalization is too expensive vs informal speed | Constrain initial scope to *statement-only* Lean (statements + `sorry`); residue is statement count, not proof depth |
| Klein score collapses under residue gate | Expected for 2–3 campaigns. Internal score is no longer the success metric after Phase 4 |
| Meta-theorem trivialization | Require every meta-theorem to predicate on a concrete obstruction class with ≥3 historical occurrences |
| Scope creep across 7 phases | Hard gates force per-phase ship-or-rollback. No phase merges without green tests + one full campaign run |

## 9. What this disrupts

- Phase BP / BQ / BR tail is replaced by phases that *cannot* repeat by construction.
- "Klein lift over baseline of +0.0157 to +0.0455" plateau is no longer the success axis. Success becomes *Lean delta count* and *external scorecard* — both monotone, both falsifiable.
- Existing Klein topology is preserved and elevated: it becomes the spatial substrate of the hyperloop's first axis. Nothing in `klein_topology.py` is deleted; it is *demoted from primary to substrate*.

## 10. Phase 0 deliverables (in this branch)

- This document.
- `lean/RH/lakefile.lean`, `lean-toolchain`, `Lemmas/FunctionalEquationMirror.lean`.
- `riemann/research/lean_bridge.py` with three backends (`mcp`, `http`, `mock`); auto-falls-back to `mock` when `AXLE_API_KEY` is unset.
- `tests/test_lean_bridge.py` covering shape contract + mock-mode round-trip.
- `.mcp.json` updated to register `axle-mcp-server` (gated by `AXLE_API_KEY`).
- `lean/README.md` describing the residue protocol.

## Sources

- [AxiomMath](https://github.com/AxiomMath) · [axiom-lean-engine](https://github.com/AxiomMath/axiom-lean-engine) · [axle-mcp-server](https://github.com/AxiomMath/axle-mcp-server) · [gdm-formal-conjectures](https://github.com/AxiomMath/gdm-formal-conjectures) · [Putnam2025](https://github.com/AxiomMath/putnam2025)
- [Aristotle: IMO-level Automated Theorem Proving (arXiv 2510.01346)](https://arxiv.org/abs/2510.01346)
- [Building the Reasoning Engine at Axiom (Jan 2026)](https://www.blog.ajabbi.com/2026/01/building-reasoning-engine-at-axiom.html)
- [awesome-ai-for-math (seewoo5)](https://seewoo5.github.io/awesome-ai-for-math/)
- [Lean 4](https://lean-lang.org/fro/about/)
