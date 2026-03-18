# Master Workflow — Superconductor Discovery System

End-to-end instructions for running the complete pipeline from convergence through prediction to crystal structure generation.

## Prerequisites

```bash
pip install numpy pandas
```

## Phase 1 — Convergence (CS/Sin/Ob Feedback Loop)

Runs the 3-agent system (Agent CS, Agent Sin, Agent Ob) in an iterative feedback loop until convergence >= 0.95 or max iterations reached.

```bash
# Standard run
python3 run.py --max-iterations 15 --target 0.95

# Verbose mode
python3 run.py --max-iterations 15 --target 0.95 -v
```

**Expected duration:** ~15 seconds (6 iterations x ~2.5s each)

**Outputs:**
| File | Description |
|------|-------------|
| `data/crystal_patterns/pattern_catalog_v*.json` | Versioned pattern catalogs (12 patterns) |
| `data/synthetic/iteration_*/properties.csv` | ~2400 synthetic structures per iteration |
| `data/synthetic/model_state.json` | Cumulative tuned model parameters |
| `data/refinements/iteration_*.json` | Refinement reports with convergence scores |
| `data/novel_candidates/candidates_iteration_*.csv` | Flagged high-Tc novel candidates |
| `data/reports/final_report.json` | Termination summary |
| `data/reports/convergence_history.json` | Per-iteration component scores |

**Success criteria:** `final_report.json` shows `"termination_reason": "convergence_reached"` with `"final_convergence_score"` >= 0.95.

---

## Phase 1b — Pressure-Aware Predictions (Agent P)

Adds pressure-dependent Tc predictions using Birch-Murnaghan EOS + Grüneisen phonon scaling. Use the `--pressure` flag to generate structures at a target external pressure.

```bash
# Ambient pressure (default, backward compatible)
python3 run.py --max-iterations 15 --target 0.95

# Hydride predictions at 150 GPa
python3 run.py --max-iterations 15 --target 0.95 --pressure 150

# Nickelate predictions at 14 GPa
python3 run.py --max-iterations 10 --target 0.90 --pressure 14
```

**Physics model (Agent P):**
- **Birch-Murnaghan EOS** (3rd order): Maps pressure → volume compression V(P)
- **Grüneisen scaling**: ω(V) = ω₀(V₀/V)^γ — phonon hardening under compression
- **Lambda scaling**: λ(V) = λ₀(V/V₀)^η — electron-phonon coupling pressure dependence
- **Thermal contraction**: Debye-Grüneisen model for lattice contraction at low T
- **Allen-Dynes**: Tc = (ωlog/1.2) exp[−1.04(1+λ)/(λ−μ*(1+0.62λ))] with P-corrected λ, ω

**Per-family parameters:** Each of the 12 pattern cards includes `PressureParams` with calibrated V₀, B₀, B₀', γ, η from experimental data. Key physical behaviors:
- Cuprates/MgB2/A15: Tc **decreases** under pressure (phonon hardening dominates)
- FeSe: Tc **increases** under pressure (spin-fluctuation enhancement, η < 0)
- Hydrides: Only superconducting at extreme pressure (100–300 GPa)
- Nickelates: SC onset at ~14 GPa

**Convergence scoring:** 7 components (extended from 6), including `pressure_tc_accuracy` which validates dTc/dP sign and magnitude against experimental data.

**New output columns in CSVs:** `pressure_GPa`, `volume_per_atom_A3`, `Tc_ambient_K`, `Tc_optimal_K`, `P_optimal_GPa`

---

## Phase 2 — Prediction (Agent GCD)

Takes the converged output and generates ranked high-Tc predictions organized by family, plus extrapolated new candidates.

```bash
python3 -m src.agents.agent_gcd
```

**Prerequisite:** Phase 1 must be complete (novel candidates + model_state.json must exist).

**Outputs:**
| File | Description |
|------|-------------|
| `data/predictions/gcd_predictions.json` | Master report with family summaries |
| `data/predictions/gcd_top_candidates.csv` | Top 50 candidates ranked by composite score |
| `data/predictions/gcd_all_ranked.csv` | All candidates with novelty scores and rankings |
| `data/predictions/gcd_extrapolated.csv` | New candidates generated via extrapolation |
| `data/predictions/family_reports/*.json` | Per-family detailed reports (top-10, statistics) |

**Key columns in CSVs:**
- `gcd_score`: Composite ranking (0.5 * normalized_Tc + 0.3 * stability + 0.2 * novelty)
- `novelty_score`: NEMAD 11D feature vector distance from nearest known compound (0-1)
- `predicted_Tc_K`: Superconducting critical temperature prediction

---

## Phase 3 — Crystal Building (Agent CB)

Constructs detailed crystal structure models with Wyckoff positions, evaluates feasibility, and generates CIF files.

```bash
python3 -m src.agents.agent_cb
```

**Prerequisite:** Phase 2 must be complete (GCD predictions must exist).

**Outputs:**
| File | Description |
|------|-------------|
| `data/crystal_structures/summary.csv` | All candidates ranked by feasibility score |
| `data/crystal_structures/synthesis_recommendations.json` | Grouped by synthesis method |
| `data/crystal_structures/{candidate_id}/structure.cif` | CIF crystallographic file |
| `data/crystal_structures/{candidate_id}/crystal_card.json` | Full crystal model with sites, bonds |
| `data/crystal_structures/{candidate_id}/feasibility.json` | Feasibility evaluation |

**Feasibility evaluation criteria:**
- Goldschmidt tolerance factor (perovskite-like: 0.8-1.0 is stable)
- Bond valence sums (deviation from integer formal valences)
- Minimum interatomic distance (no atom overlap)
- Synthesis difficulty: easy / moderate / hard / extreme

---

## Phase 4 — Visualization

Generate all plots using the instructions in `docs/VISUALIZATION_INSTRUCTIONS.md`.

```bash
# Run the visualization scripts (requires matplotlib, seaborn)
pip install matplotlib seaborn
# Then follow the 8 visualization code blocks in VISUALIZATION_INSTRUCTIONS.md
```

**Outputs:** 8 PNG files in `docs/`:
1. `viz_01_convergence_curve.png` — Score vs iteration
2. `viz_02_component_heatmap.png` — 6 components x 6 iterations
3. `viz_03_tc_distribution.png` — Real vs synthetic Tc per family
4. `viz_04_fix_round_waterfall.png` — Impact of each fix round
5. `viz_05_novel_candidates.png` — Discovery trajectory
6. `viz_06_parameter_evolution.png` — Lambda/boost tuning
7. `viz_07_architecture.png` — System diagram
8. `viz_08_tc_scatter.png` — Predicted vs experimental Tc

---

## Quick Start (Full Pipeline)

```bash
# 1. Convergence
python3 run.py --max-iterations 15 --target 0.95

# 2. Prediction
python3 -m src.agents.agent_gcd

# 3. Crystal Building
python3 -m src.agents.agent_cb
```

---

## Data Organization

```
data/
  experimental/
    supercon_reference.csv              # 24 real superconductors (ground truth)
  crystal_patterns/
    pattern_catalog_v000.json           # 12 seed patterns (bootstrap)
    pattern_catalog_v001.json           # Updated after iteration 0
    ...
  synthetic/
    iteration_000/properties.csv        # ~2400 structures (200 x 12 patterns)
    iteration_001/properties.csv
    ...
    model_state.json                    # Cumulative tuned parameters
  refinements/
    iteration_000.json                  # Convergence score + refinement instructions
    ...
  novel_candidates/
    candidates_iteration_000.csv        # High-Tc flagged candidates
    ...
  predictions/                          # Agent GCD output
    gcd_predictions.json                # Master report
    gcd_top_candidates.csv              # Top 50
    gcd_extrapolated.csv                # New extrapolated candidates
    family_reports/                     # Per-family analysis
  crystal_structures/                   # Agent CB output
    summary.csv                         # All structures ranked
    synthesis_recommendations.json      # Grouped by method
    {candidate_id}/
      structure.cif                     # Crystallographic file
      crystal_card.json                 # Full model
      feasibility.json                  # Evaluation
  reports/
    final_report.json                   # Termination summary
    convergence_history.json            # Component score history
```

---

## Interpreting Results

### What does the convergence score mean?
A score of 0.95 means the synthetic data generated by Agent Sin matches real experimental superconductor data to 95% across 7 metrics (Tc distribution, lattice accuracy, space group correctness, electronic properties, composition validity, coordination geometry, and pressure-Tc accuracy). This validates that the model has learned the physical patterns of known superconductors.

### What are novel candidates?
Compositions that:
- Are NOT in the 24 known experimental compounds
- Have predicted Tc > 10K
- Show Tc > 1.1x the family maximum (exceptional for their class)
- Have reasonable thermodynamic stability (E_above_hull < 50 meV/atom)

### How to prioritize candidates for synthesis?
1. Check `crystal_structures/summary.csv` — sort by `feasibility_score` (higher = more likely to be synthesizable)
2. Check `synthesis_recommendations.json` — grouped by method (solid-state is cheapest)
3. Cross-reference `predicted_Tc_K` with `synthesis_difficulty` — high Tc + easy synthesis = best targets
4. Read individual `feasibility.json` files for Goldschmidt tolerance and bond valence details

### What are the physical limits?
| Family | Theoretical Tc Limit | Current Record |
|--------|---------------------|---------------|
| Cuprate | ~200K | 133K (HgBa2Ca2Cu3O8) |
| Iron-based | ~80K | 56K (SmFeAsO) |
| MgB2-type | ~80K | 39K (MgB2) |
| A15 | ~40K | 23.2K (Nb3Ge) |
| Hydride | ~350K | 250K (LaH10 at 170 GPa) |
| Nickelate | ~120K | 80K (La3Ni2O7 at 14 GPa) |

---

## Documentation

- `docs/PROCESS_NOTES.md` — Detailed chronicle of all 6 fix rounds and convergence history
- `docs/VISUALIZATION_INSTRUCTIONS.md` — Step-by-step Python plotting instructions
- `docs/MASTER_WORKFLOW.md` — This file
- `SUPERCONDUCTOR_MULTIAGENT_PLAN.md` — Original system design document
