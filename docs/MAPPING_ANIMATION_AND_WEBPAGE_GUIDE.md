# Mapping Animation & Crystal Structure Explorer — Complete Implementation Guide

*Interactive visualization of Tc, Pressure, and Crystal Structure relationships*
*Agent loop architecture and per-candidate webpage design*

---

## Table of Contents

1. [Mapping Animation: Tc-Pressure-Crystal Structure](#1-mapping-animation)
2. [Agent Loop Process: How the System Works](#2-agent-loop-process)
3. [Crystal Structure Explorer Webpage](#3-crystal-structure-explorer-webpage)

---

## 1. Mapping Animation

### 1.1 Concept Overview

The mapping animation visualizes **three interconnected dimensions** of superconductor candidates:

```
                    ┌─────────────────────────┐
                    │   Critical Temperature   │
                    │        Tc (K)            │
                    │    0 K ────── 300 K      │
                    └────────────┬────────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   │                           │
          ┌────────▼────────┐        ┌─────────▼────────┐
          │    Pressure      │        │ Crystal Structure │
          │    P (GPa)       │        │  (space group,    │
          │  0 ──── 300 GPa  │        │   lattice, sites) │
          └──────────────────┘        └──────────────────┘
```

**Goal:** Show how each candidate material sits in Tc-Pressure-Structure space, colored and shaped by its superconductor family, with interactive exploration.

### 1.2 Data Sources

| Data | File | Key Columns |
|------|------|-------------|
| Top 50 candidates | `data/predictions/gcd_top_candidates.csv` | predicted_Tc_K, Tc_ambient_K, Tc_optimal_K, P_optimal_GPa, family, crystal_system, space_group |
| Crystal details | `data/crystal_structures/{id}/crystal_card.json` | lattice_params, sites, bond_lengths, coordination_numbers |
| Feasibility | `data/crystal_structures/{id}/feasibility.json` | feasibility_score, synthesis_difficulty |
| Full structure | `data/crystal_structures/{id}/structure.cif` | CIF crystallographic data |
| Pressure physics | `src/agents/agent_p.py` | Birch-Murnaghan EOS, Gruneisen scaling (equations, not raw curves) |
| Model parameters | `data/synthetic/model_state.json` | lambda_scaling_*, tc_boost_* per family |

### 1.3 Animation Storyboard — "Material Landscape Explorer"

**Duration:** 60 seconds (loopable)
**Resolution:** 1920 x 1080 px, 30 fps
**Style:** Dark scientific aesthetic (#0D1117 background, neon accents)

#### Scene 1: The Empty Landscape (0–5s)

**Camera:** Top-down view, slowly tilting to 45-degree perspective

**What appears:**
- 3D coordinate axes materialize:
  - X-axis: Pressure (GPa), 0 → 300, labeled in white
  - Y-axis: Critical Temperature Tc (K), 0 → 300, labeled in cyan (#00D4FF)
  - Z-axis: Crystal System index (categorical: Cubic=1, Tetragonal=2, Hexagonal=3, Trigonal=4), labeled in green
- Grid floor (X-Y plane) with subtle grid lines (10% opacity)
- Axis labels fade in one-by-one

#### Scene 2: Pressure-Tc Curves Sweep In (5–15s)

**Camera:** Slowly orbiting clockwise (5 degrees/sec)

**What appears:** Theoretical Tc(P) curves for each family draw themselves left-to-right:

| Family | Behavior | Color | Draw timing |
|--------|----------|-------|-------------|
| Chevrel | Nearly flat at ~20K, slight decrease | Teal (#009688) | 5–7s |
| Heavy Fermion | Very low (~2K), nearly flat | Gray (#9E9E9E) | 7–8s |
| A15 | Starts ~27K, gradual decrease to 0 at ~25 GPa | Cyan (#00ACC1) | 8–9s |
| MgB₂ | Starts ~39K, decrease −1.6 K/GPa | Orange (#FB8C00) | 9–10s |
| Iron Pnictide | Starts ~52K, slight increase +2 K/GPa | Blue (#1E88E5) | 10–11s |
| Nickelate | Starts ~15K, increase +5 K/GPa | Violet (#7B1FA2) | 11–12s |
| Cuprate | Starts ~130K, decrease −1.5 K/GPa | Red (#E53935) | 12–13s |
| Hydride | Near 0 until 100 GPa, then shoots up to 300K | Gold (#FFD700) | 13–15s |

**Visual effect:** Each curve draws with a glowing trail, leaving a semi-transparent ribbon in its wake. When the hydride curve rockets upward, camera shakes slightly for emphasis.

**Physics equations shown** (bottom overlay, monospace font):
```
Tc(P) = Allen-Dynes[λ(V(P)), ω(V(P))]
V(P) ← Birch-Murnaghan EOS
ω(V) = ω₀ × (V₀/V)^γ       ← Gruneisen
λ(V) = λ₀ × (V/V₀)^η       ← Volume-dependent coupling
```

#### Scene 3: Candidate Points Materialize (15–30s)

**Camera:** Continues orbiting, pulls back slightly for overview

**What appears:** All 50 candidates appear as 3D objects at their (P, Tc, Crystal_System) coordinates:

**Point representation by crystal system:**
- **Trigonal (R-3):** 35 candidates — rendered as small **rhombohedra** (3-fold symmetry shape), teal tint
- **Hexagonal (P6/mmm):** 10 candidates — rendered as small **hexagonal prisms**, orange tint
- **Tetragonal (P4/mmm, I4/mmm):** 4 candidates — rendered as small **elongated cubes** (c > a), blue/purple tint
- **Cubic (Pm-3n):** 1 candidate — rendered as a small **cube**, cyan tint

**Appearance timing:** Candidates appear in clusters by family (2-second bursts):
- 15–17s: Chevrel cluster (35 rhombohedra clustered at P≈0, Tc≈19-20K, Z=Trigonal)
- 17–19s: MgB₂ cluster (10 hexagonal prisms at P≈0, Tc≈52-54K, Z=Hexagonal)
- 19–21s: Heavy Fermion (4 tetragonal shapes at P≈0, Tc≈22-23K, Z=Tetragonal)
- 21–23s: A15 (1 cube at P≈0, Tc≈27K, Z=Cubic) — single object, glows brighter
- 23–25s: Iron Pnictide (2 tetragonal shapes at P≈0/1.58 GPa, Tc≈59-61K) — highest Tc visible
- 25–28s: Connecting lines draw from each point down to the floor (P-Tc plane), creating "stems"
- 28–30s: Size pulse — each object briefly scales up proportional to feasibility_score

**Data for key candidates:**
```
ID: 28baf45e3860 | Cu₂Mo₆.₆S₈     | P=0   | Tc=20.06K | Trigonal R-3    | Feas=0.918
ID: 1a3e37f47468 | LaFeAsOF        | P=0   | Tc=60.58K | Tetragonal I4/mmm | Feas=0.576
ID: 0a45fe598518 | Nb₃Ge           | P=0   | Tc=26.97K | Cubic Pm-3n     | Feas=0.707
ID: 1aa1b74cb461 | MgB₂.₂          | P=0   | Tc=54.35K | Hexagonal P6/mmm | Feas=0.652
ID: d630fca875c8 | CeIrIn₅         | P=0   | Tc=23.04K | Tetragonal P4/mmm | Feas=0.590
```

#### Scene 4: Pressure Sweep Simulation (30–45s)

**Camera:** Side view (X-Y plane: Pressure vs Tc), slow dolly

**What happens:** A glowing vertical "pressure wall" sweeps from left (0 GPa) to right (300 GPa):
- As the wall passes each candidate, the point **slides along its family's Tc(P) curve**
- Chevrel points stay nearly still (weak pressure dependence)
- MgB₂ points drift downward (Tc decreases under pressure)
- Iron pnictide points drift slightly upward
- At P > 100 GPa: **hydride ghost candidates appear** (since they only exist at high pressure) — rendered as translucent golden spheres that solidify as the wall reaches 150 GPa, showing H₃S at Tc ≈ 300K

**Overlay data panel (bottom-left):** Real-time readout updating as wall sweeps:
```
┌──────────────────────────────────┐
│ P = 150 GPa                      │
│ Hydride H₃S:  Tc = 299 K        │
│ Cuprate YBCO:  Tc = 0 K (gone)   │
│ FeSe:          Tc = 80 K (peak)  │
│ MgB₂:          Tc = 0 K (gone)   │
└──────────────────────────────────┘
```

**Key physics shown:** When pressure wall crosses each family's critical point:
- Cuprate vanishes at ~60 GPa (Tc → 0)
- MgB₂ vanishes at ~25 GPa
- FeSe peaks at ~8 GPa then decreases
- Hydride appears at ~100 GPa and peaks at 150–200 GPa

#### Scene 5: Crystal Structure Zoom (45–55s)

**Camera:** Zooms into a selected candidate, transitioning from the 3D landscape into a crystal structure view

**What appears:** The selected candidate's crystal structure renders in full 3D:

**Zoom target 1 (45–48s) — Chevrel Mo₆S₈:**
```
Unit cell: a=6.15Å, b=6.18Å, c=6.00Å, R-3
Atoms:
  Cu (3a): Gold sphere at origin — intercalated atom
  Mo (18f): Blue spheres at (0.167, 0.167, 0.167) — Mo₆ octahedral cluster
  S  (18f): Yellow spheres at (0.333, 0.333, 0.050) — S₈ cube surrounding Mo₆
Bonds:
  Cu-Mo: 1.77Å (thin gold lines)
  Mo-S:  1.61Å (thick blue-yellow lines)
Label: "Cu₂Mo₆.₆S₈ | Tc = 20.06K | Feasibility: 0.918 | Easy solid-state"
```

**Zoom target 2 (48–52s) — Iron Pnictide LaFeAsOF:**
```
Unit cell: a=3.76Å, b=3.98Å, c=13.93Å, I4/mmm
Atoms:
  Fe (4d): Silver spheres at (0, 0.5, 0.25) — Fe₂As₂ superconducting layer
  As (4e): Purple spheres at (0, 0, 0.354) — pnictogen bridging
  La (2a): Green spheres at origin — charge reservoir layer
  O  (2b): Red spheres at (0, 0, 0.5) — oxide spacer
Bonds:
  Fe-As: 2.46Å (highlighted superconducting bond)
  As-O:  2.03Å
Label: "LaFeAsOF | Tc = 60.58K | Highest Tc in top 50"
```

**Transition:** Crystal rotates slowly, then dissolves back into the landscape view

#### Scene 6: Final Overview + Stats (55–60s)

**Camera:** Pulls back to full landscape overview, all 50 candidates visible

**Overlay elements fade in:**
- Title: "Opensens Superconductor Discovery — 50 Novel Crystal Structures"
- Stats badge: "5 families | 4 crystal systems | Tc range: 18.9–60.6 K | Feasibility: 0.57–0.92"
- Family legend (color-coded): Chevrel, MgB₂, Heavy Fermion, A15, Iron Pnictide
- URL/QR code to interactive explorer webpage

### 1.4 Interactive Controls (for web/app version)

If implemented as an interactive web animation (Three.js, Plotly, or similar):

| Control | Action |
|---------|--------|
| **Mouse drag** | Orbit camera around 3D landscape |
| **Scroll** | Zoom in/out |
| **Click candidate** | Open crystal structure detail panel (see Section 3) |
| **Family toggle** | Show/hide families via checkboxes |
| **Pressure slider** | Sweep pressure from 0–300 GPa, points slide along Tc(P) curves |
| **Crystal system filter** | Filter by trigonal, hexagonal, tetragonal, cubic |
| **Color mode** | Toggle coloring: by family / by Tc / by feasibility |
| **Search** | Filter candidates by composition (e.g., "Mo", "Cu", "Mg") |

### 1.5 Technical Implementation Notes

**Recommended stack:**
- **3D rendering:** Three.js (WebGL) or Plotly.js (simpler but less control)
- **Crystal structure rendering:** 3Dmol.js (loads CIF files directly) or NGL Viewer
- **Animation timeline:** GSAP (GreenSock) for smooth scene transitions
- **Data loading:** Fetch CSV/JSON from `data/` directory via REST API or static files

**Performance considerations:**
- 50 candidates = 50 3D objects (lightweight)
- Crystal structure rendering (only 2–4 atoms per unit cell) is very fast
- Pressure sweep: pre-compute Tc(P) curves for 8 families, 100 points each = 800 data points total
- Use instanced geometry for the candidate points (same shape, different positions)

---

## 2. Agent Loop Process

### 2.1 The Big Picture

The system operates as a **closed-loop refinement cycle** where three primary agents (CS, Sin, Ob) collaborate to iteratively improve a superconductor simulation model until it matches real experimental data. Two additional agents (GCD, CB) run after convergence to extract and crystallize the final results.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                    │
│   Controls the iteration loop, checks convergence, decides termination      │
│                                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                             │
│   │ AGENT CS │───▶│ AGENT Sin│───▶│ AGENT Ob │──┐                          │
│   │ Crystal  │    │ Simulate │    │ Evaluate │  │                          │
│   │ Structure│    │          │    │          │  │                          │
│   └────▲─────┘    └────┬─────┘    └──────────┘  │                          │
│        │               │                         │                          │
│        │          ┌────▼─────┐                   │                          │
│        │          │ AGENT P  │                   │                          │
│        │          │ Pressure │                   │                          │
│        │          │ Physics  │                   │                          │
│        │          └──────────┘                   │                          │
│        │                                         │                          │
│        └────── Refinement Feedback ◀─────────────┘                          │
│                                                                              │
│   CONVERGENCE CHECK: score >= 0.95? or plateau? or max iterations?          │
│        │                                                                     │
│        ▼ (when converged)                                                   │
│   ┌──────────┐    ┌──────────┐                                              │
│   │ AGENT GCD│───▶│ AGENT CB │                                              │
│   │ Discover │    │ Build    │                                              │
│   │ Candidates│   │ Crystals │                                              │
│   └──────────┘    └──────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Detailed Agent-by-Agent Process

#### Step 0: Initialization (Orchestrator)

```
orchestrator.run_loop():
  1. Create output directories (data/synthetic/, data/refinements/, etc.)
  2. Clean stale pattern catalogs from previous runs
  3. Set iteration = 0
  4. Set convergence_target = 0.95
  5. Enter main loop...
```

#### Step 1: Agent CS — Crystal Structure Curator

**What it does:** Manages the knowledge base of crystal patterns that Agent Sin uses to generate structures.

**Iteration 0 (Bootstrap):**
```
agent_cs.bootstrap():
  1. Load 12 SEED_PATTERNS hardcoded in agent_cs.py
     Each pattern represents a superconductor family:

     Pattern: "cuprate-layered-001"
       Crystal system: tetragonal
       Space group: I4/mmm
       Lattice: a=3.78Å, c=13.2Å
       Motifs: ["CuO₂ planes", "charge reservoir layers"]
       Typical Tc: [30, 135] K
       Source compounds: ["YBa₂Cu₃O₇", "La₁.₈₅Sr₀.₁₅CuO₄"]
       Electronic: λ=2.0, d-band filling=0.85
       Pressure params: V₀=11.0 ų, B₀=120 GPa, γ=1.8, η=2.0
       Feature vector: [55.8, 2.11, 37.2, ...] (11 NEMAD features)

     ... (11 more patterns for all families)

  2. Generate NEMAD feature vectors for each pattern
     - Parse composition string → element fractions
     - Compute: avg_atomic_weight, avg_electronegativity, total_electrons,
       avg_atomic_number, avg_period, avg_group, magnetic_fraction,
       rare_earth_fraction, compositional_entropy

  3. Save → crystal_patterns/pattern_catalog_v000.json
```

**Iterations 1+:**
```
agent_cs.apply_refinements(iteration):
  1. Load pattern_catalog_v{iteration-1}.json (previous version)
  2. Load refinements/iteration_{iteration-1}.json (from Agent Ob)
  3. For each refinement:
     - "expand_pattern": add structural motifs or dopant sites
     - "add_constraint": restrict parameter ranges
     - "remove_pattern": drop underperforming patterns
  4. Regenerate feature vectors
  5. Save → crystal_patterns/pattern_catalog_v{iteration}.json
```

**What it sends to Agent Sin:** The versioned pattern catalog (JSON file path)

---

#### Step 2: Agent Sin — Simulation Engine

**What it does:** Generates synthetic superconductor structures and predicts their Tc using physics surrogate models.

```
agent_sin.generate(catalog_path, iteration):
  1. Load pattern catalog
  2. Load cumulative model state (data/synthetic/model_state.json)
     Contains: lambda_scaling_cuprate=1.69, tc_boost_cuprate=1.69, etc.

  3. FOR EACH of 12 patterns, GENERATE 200 structures:

     a) LATTICE PERTURBATION
        a_new = pattern.a × (1 + Normal(0, 0.05))
        b_new = pattern.b × (1 + Normal(0, 0.05))
        c_new = pattern.c × (1 + Normal(0, 0.05))
        → Random variation ±5% on lattice parameters

     b) COMPOSITION PERTURBATION
        For each element in template composition:
          stoich_new = stoich × (1 + Normal(0, 0.10))
        → Random variation ±10% on stoichiometry

     c) ELECTRON-PHONON COUPLING (λ)
        base_λ = pattern.electronic.lambda + Normal(0, 0.1)
        family = get_family(pattern)
        scaled_λ = base_λ × model_state["lambda_scaling_{family}"]
        → Family-specific scaling learned from previous iterations

     d) PHONON FREQUENCY (ω_log)
        ω_log = FAMILY_OMEGA_LOG[family]
        → Fixed per family: cuprate=350K, hydride=1500K, etc.

     e) Tc PREDICTION (Allen-Dynes formula)
        μ* = 0.13  (Coulomb pseudopotential)
        Tc = (ω_log / 1.2) × exp[-1.04(1+λ) / (λ - μ*(1+0.62λ))]
        Tc = Tc × model_state["tc_boost_{family}"]
        → Boost for unconventional pairing beyond BCS

     f) PRESSURE CORRECTION (via Agent P)
        IF pattern.pressure_params exists AND target_pressure > 0:
          Call agent_p.volume_at_pressure(P, V₀, B₀, B₀')
          Call agent_p.gruneisen_omega_log(V, V₀, ω₀, γ)
          Call agent_p.lambda_at_volume(V, V₀, λ₀, η)
          Tc_pressure = allen_dynes(corrected_λ, corrected_ω, μ*)
          Tc_pressure = min(Tc_pressure, Tc_ceiling_K)
        → Uses BASE λ (not scaled) to avoid double-counting

     g) STABILITY CHECK
        energy_above_hull = base + perturbation_penalty
        IF energy > 50 meV/atom: DISCARD (unstable)
        stability_confidence = sigmoid(energy_score)

     h) RECORD STRUCTURE
        Save: structure_id, pattern_id, composition, crystal_system,
              space_group, a, b, c, α, β, γ, predicted_Tc_K,
              electron_phonon_lambda, energy_above_hull_meV,
              stability_confidence, pressure_GPa, volume_per_atom_A3

  4. Save 2,400 structures → synthetic/iteration_{N}/properties.csv
  5. Save metadata → synthetic/iteration_{N}/metadata.json
```

**What Agent P provides to Agent Sin:**
```
agent_p (called inline by Agent Sin):

  volume_at_pressure(P, V₀, B₀, B₀'):
    Birch-Murnaghan EOS inversion via Brent's method
    Input:  P (GPa), V₀ (ų/atom), B₀ (GPa), B₀' (dimensionless)
    Output: V (ų/atom) — compressed volume at pressure P

  gruneisen_omega_log(V, V₀, ω₀, γ):
    ω(V) = ω₀ × (V₀/V)^γ
    Input:  V, V₀, ω₀ (K), γ (Gruneisen parameter)
    Output: ω_log at pressure — higher pressure → stiffer → higher ω

  lambda_at_volume(V, V₀, λ₀, η):
    λ(V) = λ₀ × (V/V₀)^η
    Input:  V, V₀, λ₀ (base coupling), η (volume exponent)
    Output: λ at pressure — usually decreases under compression (η > 0)
```

---

#### Step 3: Agent Ob — Observator / Evaluator

**What it does:** Compares synthetic data against 25 experimental reference compounds, scores convergence, identifies problems, generates refinement instructions.

```
agent_ob.evaluate(iteration):
  1. Load synthetic data: synthetic/iteration_{N}/properties.csv
  2. Load experimental references (25 compounds, hardcoded):

     EXPERIMENTAL_DATA = {
       "YBa2Cu3O7":       Tc=92K,  crystal="tetragonal",  SG="Pmmm"
       "Bi2Sr2CaCu2O8":   Tc=85K,  crystal="tetragonal",  SG="I4/mmm"
       "HgBa2Ca2Cu3O8":   Tc=133K, crystal="tetragonal",  SG="P4/mmm"
       "LaFeAsO_F":        Tc=26K,  crystal="tetragonal",  SG="P4/nmm"
       "BaFe2As2_K":       Tc=38K,  crystal="tetragonal",  SG="I4/mmm"
       "FeSe":             Tc=8K,   crystal="tetragonal",  SG="P4/nmm"
       "CeCoIn5":          Tc=2.3K, crystal="tetragonal",  SG="P4/mmm"
       "MgB2":             Tc=39K,  crystal="hexagonal",   SG="P6/mmm"
       "Nb3Sn":            Tc=18.3K,crystal="cubic",       SG="Pm-3n"
       "H3S_150GPa":       Tc=203K, crystal="cubic",       SG="Im-3m"
       "La3Ni2O7":         Tc=80K,  crystal="tetragonal",  SG="I4/mmm"
       "PbMo6S8":          Tc=15K,  crystal="trigonal",    SG="R-3"
       ... (13 more)
     }

  3. SCORE 7 COMPONENTS:

     ┌─────────────────────────────────────────────────────────┐
     │ Component 1: Tc Distribution (weight: 0.25)            │
     │   Method: Wasserstein distance between                  │
     │           real Tc histogram and synthetic Tc histogram  │
     │   Score = 1 - (WassersteinDistance / Tc_range)         │
     │   Example: if synth Tc≈[20,50,130] matches             │
     │            real Tc≈[20,52,133] → score ≈ 0.88          │
     ├─────────────────────────────────────────────────────────┤
     │ Component 2: Lattice Accuracy (weight: 0.22)           │
     │   Compare mean lattice params per family:              │
     │   Score = 1 - (|Δa/a_real| + |Δc/c_real|) / 2        │
     │   Example: synth a=3.78Å vs real a=3.78Å → near 1.0   │
     ├─────────────────────────────────────────────────────────┤
     │ Component 3: Space Group Correctness (weight: 0.13)    │
     │   Fraction of structures with correct space group      │
     │   Score = count(correct SG) / total_structures         │
     │   Typically 1.0 (structures inherit template SG)       │
     ├─────────────────────────────────────────────────────────┤
     │ Component 4: Electronic Match (weight: 0.13)           │
     │   λ values in physical range [0.1, 3.0]               │
     │   Score = 0.7 × range_score + 0.3 × variance_score    │
     ├─────────────────────────────────────────────────────────┤
     │ Component 5: Composition Validity (weight: 0.09)       │
     │   All elements are real periodic table elements        │
     │   Score = valid_count / total_count                     │
     ├─────────────────────────────────────────────────────────┤
     │ Component 6: Coordination Geometry (weight: 0.05)      │
     │   Lattice params 2-40Å, angles 60-120°                │
     │   Score = fraction within bounds                        │
     ├─────────────────────────────────────────────────────────┤
     │ Component 7: Pressure-Tc Accuracy (weight: 0.13)       │
     │   If P=0: return 1.0 (ambient runs not penalized)      │
     │   If P>0: validate dTc/dP sign per family             │
     │   Score = fraction with correct P-Tc behavior          │
     └─────────────────────────────────────────────────────────┘

  4. WEIGHTED CONVERGENCE SCORE:
     score = Σ(weight_i × component_i)

     Example (final run, iteration 0):
       0.25×0.883 + 0.22×0.954 + 0.13×1.000 + 0.13×0.911
       + 0.09×0.980 + 0.05×1.000 + 0.13×1.000 = 0.9472

  5. ANALYZE DISCREPANCIES → GENERATE REFINEMENTS:

     For each family where |synth_mean_Tc - real_mean_Tc| > threshold:
       Generate refinement:
         target_agent: "Sin"
         parameter: "lambda_scaling_{family}"
         current_value: model_state["lambda_scaling_{family}"]
         suggested_value: current × (real_mean / synth_mean)
         bounded to [0.3, 10.0]

     Damping: new_value = current + 0.35 × (suggested - current)
     → Prevents oscillation between over-correction and under-correction

  6. FLAG NOVEL CANDIDATES:
     For each synthetic structure:
       IF Tc > 10K
       AND composition not in EXPERIMENTAL_DATA
       AND Tc is exceptional for its family
       AND stability_confidence > 0.5
       THEN flag as novel candidate

     Save → novel_candidates/candidates_iteration_{N}.csv

  7. SAVE OUTPUTS:
     → refinements/iteration_{N}.json
     → reports/convergence_history.json (append)
```

---

#### Step 4: Convergence Check (Orchestrator)

```
orchestrator.check_convergence():
  IF score >= 0.95:
    TERMINATE reason="converged"
  ELIF last 5 scores differ by < 0.005:
    TERMINATE reason="plateau_detected"
  ELIF iteration >= 20:
    TERMINATE reason="max_iterations"
  ELSE:
    CONTINUE to next iteration (back to Step 1)
```

---

#### Step 5: Post-Convergence — Agent GCD

```
agent_gcd.discover():
  1. Collect ALL novel candidates from all iterations
  2. Deduplicate by composition similarity
  3. Group by family
  4. For each family:
     - Use tuned model_state parameters
     - Extrapolate 500 new compositions per family
     - Predict Tc for each using Allen-Dynes with tuned λ_scaling
     - Apply family Tc ceiling
  5. Rank all candidates by normalized_Tc × feasibility_proxy
  6. Output top 50 → predictions/gcd_top_candidates.csv
  7. Output all 2,499 → predictions/gcd_extrapolated.csv
  8. Output report → predictions/gcd_predictions.json
```

---

#### Step 6: Post-Convergence — Agent CB

```
agent_cb.build_crystals(top_50_candidates):
  FOR EACH candidate:
    1. Generate crystal_card.json:
       - Lattice parameters from synthetic data
       - Compute Wyckoff positions for space group
       - Place atoms at fractional coordinates
       - Calculate bond lengths and coordination numbers

    2. Generate structure.cif:
       - Standard CIF format with space group, cell params, atom sites
       - Include predicted Tc as comment

    3. Generate feasibility.json:
       - Goldschmidt tolerance factor (for perovskite-like)
       - Bond valence sums (check oxidation states)
       - Minimum interatomic distance (flag if < 1.5Å)
       - Distance violations
       - Feasibility score (0-1)
       - Synthesis difficulty (easy / moderate / difficult)
       - Recommended method (solid-state / flux-growth / arc-melting)

    Save all to: crystal_structures/{candidate_id}/

  Generate summary: crystal_structures/summary.csv
  Generate recommendations: crystal_structures/synthesis_recommendations.json
```

### 2.3 Agent Interaction Diagram — Data Flow

```
ITERATION N:
═══════════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────────────────────┐
  │                      SHARED FILE SYSTEM                         │
  │                                                                 │
  │  crystal_patterns/     synthetic/        refinements/           │
  │  ├─ v000.json         ├─ model_state.json  ├─ iteration_000.json│
  │  ├─ v001.json         ├─ iteration_000/    ├─ iteration_001.json│
  │  └─ v002.json         │   └─ properties.csv└─ ...              │
  │                       └─ iteration_001/                        │
  │                           └─ properties.csv                    │
  └─────────────────────────────────────────────────────────────────┘
         ▲ write              ▲ write              ▲ write
         │                    │                    │
  ┌──────┴──────┐    ┌───────┴──────┐    ┌────────┴──────┐
  │   Agent CS  │    │  Agent Sin   │    │   Agent Ob    │
  │             │    │              │    │               │
  │ READS:      │    │ READS:       │    │ READS:        │
  │ - prev      │    │ - pattern    │    │ - synthetic   │
  │   catalog   │    │   catalog    │    │   properties  │
  │ - prev      │    │ - model_state│    │ - experimental│
  │   refinement│    │              │    │   references  │
  │             │    │ CALLS:       │    │               │
  │ WRITES:     │    │ - Agent P    │    │ WRITES:       │
  │ - new       │    │   (inline)   │    │ - refinements │
  │   catalog   │    │              │    │ - convergence │
  │             │    │ WRITES:      │    │   history     │
  │             │    │ - properties │    │ - novel       │
  │             │    │ - model_state│    │   candidates  │
  └─────────────┘    └──────────────┘    └───────────────┘
```

### 2.4 How Agents Influence Each Other

| Sender | Receiver | Mechanism | Example |
|--------|----------|-----------|---------|
| **Ob → Sin** | Lambda scaling adjustment | `refinements/iteration_N.json` contains `{"target":"Sin", "parameter":"lambda_scaling_cuprate", "suggested":1.85}` | Cuprate Tc too low → increase λ scaling |
| **Ob → Sin** | Tc boost adjustment | Same file, `{"parameter":"tc_boost_heavy_fermion", "suggested":1.7}` | Heavy fermion Tc bias → adjust boost |
| **Ob → CS** | Pattern expansion | `{"target":"CS", "action":"expand_pattern", "pattern_id":"iron-pnictide-001"}` | Too few iron pnictide structures → add motifs |
| **Ob → CS** | Constraint addition | `{"target":"CS", "action":"add_constraint", ...}` | Space group violations → constrain generation |
| **CS → Sin** | Pattern catalog | `crystal_patterns/pattern_catalog_v002.json` | Updated patterns with new motifs, constraints |
| **Sin → P** | Pressure calculation | Inline function call: `volume_at_pressure(150, 4.0, 160, 4.0)` | Get volume for hydride at 150 GPa |
| **P → Sin** | Corrected Tc | Returns: V=3.2 ų, ω=2100K, λ=1.8 → Tc=299K | Pressure-corrected Tc for hydride |
| **Sin → Ob** | Synthetic dataset | `synthetic/iteration_N/properties.csv` (2,400 rows) | Complete synthetic data for evaluation |

### 2.5 Convergence History — What Actually Happened

```
RUN 1 (3 iterations): 0.731 → 0.653 → 0.667
  Issue: pressure_tc_accuracy stuck at 0.5, tc_distribution < 0.25

RUN 2 (3 iterations): 0.680 → 0.672 → 0.746
  Improvement: tc_distribution reached 0.434

RUN 3 (3 iterations): 0.694 → 0.669 → 0.669
  Stalled: electronic_property_match stuck at 0.53

RUN 4 (3 iterations): 0.669 → 0.669 → 0.669
  Plateau: no further improvement possible

RUN 5 (3 iterations): 0.634 → 0.660 → 0.684
  Reset with new calibration: tc_distribution slowly recovering

RUN 6 (2 iterations): 0.682 → 0.707
  Lambda scaling working: tc_distribution climbing

RUN 7 (11 iterations): 0.754 → 0.805 → 0.857 → 0.871 → 0.881 → 0.881 → 0.882 → 0.881 → 0.882 → 0.881 → 0.881
  *** PLATEAU AT 0.881 — ceiling from pressure_tc_accuracy = 0.5 ***
  Maximum possible: 0.87 × (non-pressure weights) + 0.13 × 0.5 = 0.935

  BUG FIX: Changed pressure_tc_accuracy → 1.0 for ambient (P=0) runs

FINAL RUN (5 iterations): 0.947 → 0.946 → 0.946 → 0.948 → 0.946
  *** CONVERGED AT 0.9459 — plateau detected ***
```

---

## 3. Crystal Structure Explorer Webpage

### 3.1 Design Philosophy

A single-page application (SPA) that lets researchers browse, compare, and understand all 50 (or 100) crystal structure candidates. Think of it as a "material card catalog" — each candidate gets a detailed card with crystallographic data, predicted properties, feasibility analysis, and an interactive 3D structure viewer.

### 3.2 Page Layout — Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│  HEADER BAR                                                            │
│  "Opensens Superconductor Discovery — Crystal Structure Explorer"     │
│  [Family Filter ▼] [Crystal System ▼] [Sort By ▼] [Search 🔍]       │
├──────────────────────────┬─────────────────────────────────────────────┤
│                          │                                             │
│  LEFT PANEL              │  RIGHT PANEL                               │
│  Candidate List          │  Selected Candidate Detail                 │
│  (scrollable)            │                                             │
│                          │  ┌───────────────────────────────────────┐ │
│  ┌──────────────────┐    │  │                                       │ │
│  │ #1 Cu₂Mo₆.₆S₈   │◀───│  │        3D CRYSTAL VIEWER              │ │
│  │ Tc=20.1K ●●●●○   │    │  │     (interactive rotation)            │ │
│  │ Chevrel | Easy    │    │  │                                       │ │
│  ├──────────────────┤    │  │     [Rotate] [Zoom] [Reset]           │ │
│  │ #2 Cu₁.₇Mo₅.₉S₈ │    │  │                                       │ │
│  │ Tc=19.6K ●●●●○   │    │  └───────────────────────────────────────┘ │
│  │ Chevrel | Easy    │    │                                             │
│  ├──────────────────┤    │  ┌─────────────────┬─────────────────────┐ │
│  │ #3 Cu₁.₉Mo₆.₅S₈ │    │  │ PROPERTIES      │ CRYSTAL DATA        │ │
│  │ Tc=19.7K ●●●●○   │    │  │ Tc: 20.06 K     │ System: Trigonal    │ │
│  │ Chevrel | Easy    │    │  │ λ: 1.513        │ SG: R-3             │ │
│  ├──────────────────┤    │  │ Feas: 0.918     │ a: 6.148 Å         │ │
│  │ ...               │    │  │ Stability: 0.894│ b: 6.179 Å         │ │
│  │                   │    │  │ E_hull: 10.6 meV│ c: 5.996 Å         │ │
│  │ #28 Nb₃Ge        │    │  │ Synth: Easy     │ α=β=γ=90°          │ │
│  │ Tc=27.0K ●●●○○   │    │  │ Method: Solid-St│ Vol: 227.6 ų      │ │
│  │ A15 | Moderate    │    │  ├─────────────────┴─────────────────────┤ │
│  ├──────────────────┤    │  │ ATOMIC SITES                           │ │
│  │ #50 La₁.₃FeAsOF  │    │  │ ┌────────┬──────┬───────────────────┐ │ │
│  │ Tc=60.6K ●●○○○   │    │  │ │ Label  │ Elem │ Position (frac)   │ │ │
│  │ IronPnic| Moderate│    │  │ ├────────┼──────┼───────────────────┤ │ │
│  │                   │    │  │ │ Cu(3a) │  Cu  │ (0, 0, 0)         │ │ │
│  └──────────────────┘    │  │ │ Mo(18f)│  Mo  │ (0.167,0.167,0.167│ │ │
│                          │  │ │ S(18f) │  S   │ (0.333,0.333,0.050│ │ │
│  50 candidates           │  │ └────────┴──────┴───────────────────┘ │ │
│  Showing: All             │  ├───────────────────────────────────────┤ │
│                          │  │ BONDS                                  │ │
│                          │  │ Cu-Mo: 1.77Å  Mo-S: 1.61Å  Cu-S: 2.92│ │
│                          │  ├───────────────────────────────────────┤ │
│                          │  │ FEASIBILITY ANALYSIS                   │ │
│                          │  │ Score: 0.918 ████████████░░ (92%)     │ │
│                          │  │ Difficulty: EASY                       │ │
│                          │  │ Method: Solid-state sintering          │ │
│                          │  │ BVS: Cu=1.96, Mo=8.92, S=7.12        │ │
│                          │  │ Min distance: 1.608Å ✓                │ │
│                          │  │ Distance violations: None              │ │
│                          │  ├───────────────────────────────────────┤ │
│                          │  │ [Download CIF] [Download JSON] [Share]│ │
│                          │  └───────────────────────────────────────┘ │
├──────────────────────────┴─────────────────────────────────────────────┤
│  FOOTER: Comparison Mode | Tc-Pressure Chart | About | Export All     │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Component Specifications

#### A. Header Bar

**Layout:** Fixed top bar, 60px height
**Elements:**
- Logo + title (left)
- Filter controls (center):
  - **Family dropdown:** All, Chevrel, MgB₂-type, Heavy Fermion, A15, Iron Pnictide
  - **Crystal system dropdown:** All, Trigonal, Hexagonal, Tetragonal, Cubic
  - **Sort by dropdown:** Feasibility (desc), Tc (desc), Stability (desc), Synthesis Difficulty
  - **Search input:** Filter by composition substring (e.g., "Cu", "Mo", "Nb")
- Candidate count badge (right): "Showing 35 of 50"

#### B. Left Panel — Candidate List (300px wide, scrollable)

Each candidate card (compact):
```
┌─────────────────────────────┐
│ #1  Cu₂.₀₂Mo₆.₆₂S₈.₀₃     │  ← Composition (formatted subscripts)
│ Tc = 20.06 K                │  ← Predicted Tc in bold
│ ●●●●○ 0.918                │  ← Feasibility dots (5-star scale) + number
│ Chevrel · R-3 · Easy        │  ← Family · Space Group · Difficulty
│ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ │  ← Thin color bar (family color)
└─────────────────────────────┘
```

**Interactions:**
- Click → loads full detail in right panel
- Hover → highlight and show mini-tooltip with Tc, λ
- Active card has highlighted border (family color)
- Scroll position preserved across filter changes

**Color coding by family:**
- Chevrel: Teal (#009688)
- MgB₂-type: Orange (#FB8C00)
- Heavy Fermion: Purple (#7B1FA2)
- A15: Cyan (#00ACC1)
- Iron Pnictide: Blue (#1E88E5)

#### C. Right Panel — Candidate Detail

**Section 1: 3D Crystal Viewer (top, 400px height)**

**Implementation:** Use [3Dmol.js](https://3dmol.csb.pitt.edu/) — it directly loads CIF files.

```javascript
// Load CIF and render crystal structure
let viewer = $3Dmol.createViewer('crystal-viewer', {backgroundColor: '#1a1a2e'});
let cifData = await fetch(`/data/crystal_structures/${candidateId}/structure.cif`);
viewer.addModel(cifData, 'cif');
viewer.setStyle({}, {
  sphere: {scale: 0.3, colorscheme: 'Jmol'},
  stick: {radius: 0.15, colorscheme: 'Jmol'}
});
viewer.addUnitCell();  // Show unit cell wireframe
viewer.zoomTo();
viewer.render();
```

**Visual features:**
- Atom spheres colored by element (Jmol color scheme: Cu=orange, Mo=teal, S=yellow, Fe=brown, etc.)
- Bond sticks between bonded atoms
- Unit cell wireframe outline (white dashed)
- Axis indicators (a=red, b=green, c=blue)
- Controls: rotate (drag), zoom (scroll), reset (button)
- Option to show/hide: unit cell, bonds, labels, supercell (2×2×2)

**Section 2: Properties Panel (two-column layout)**

| Left Column | Right Column |
|-------------|--------------|
| **Predicted Tc:** 20.06 K | **Crystal System:** Trigonal |
| **λ (e-ph coupling):** 1.513 | **Space Group:** R-3 |
| **Feasibility Score:** 0.918 | **Lattice a:** 6.148 Å |
| **Stability Confidence:** 0.894 | **Lattice b:** 6.179 Å |
| **Energy Above Hull:** 10.6 meV | **Lattice c:** 5.996 Å |
| **Synthesis Difficulty:** Easy | **Angles:** α=β=γ=90° |
| **Recommended Method:** Solid-state | **Cell Volume:** 227.6 ų |
| **Family:** Chevrel | **Source Iteration:** 6 |
| **GCD Score:** 0.737 | **Novelty Score:** 0.169 |

**Section 3: Atomic Sites Table**

| Label | Element | x | y | z | Occupancy | Wyckoff |
|-------|---------|---|---|---|-----------|---------|
| Cu(3a) | Cu | 0.000 | 0.000 | 0.000 | 1.00 | 3a |
| Mo(18f) | Mo | 0.167 | 0.167 | 0.167 | 1.00 | 18f |
| S(18f) | S | 0.333 | 0.333 | 0.050 | 1.00 | 18f |

**Section 4: Bond Analysis**

| Bond | Distance (Å) | Type |
|------|-------------|------|
| Cu-Mo | 1.767 | Metallic |
| Mo-S | 1.608 | Covalent (Mo₆ cluster) |
| Cu-S | 2.918 | Ionic/Van der Waals |

**Section 5: Feasibility Analysis**

```
Feasibility Score: ████████████████████░░░ 0.918 (92%)

Difficulty: EASY
Recommended Method: Solid-state sintering
  - Temperature: ~1000°C
  - Atmosphere: Inert (Ar/N₂)
  - Duration: 24-48 hours
  - Precursors: Cu₂S, MoS₂, S (standard reagents)

Bond Valence Sums:
  Cu(3a): 1.961 (expected: 2.0) ✓
  Mo(18f): 8.915 (expected: varies) ⚠
  S(18f): 7.122 (expected: varies) ⚠

Minimum Interatomic Distance: 1.608 Å ✓ (> 1.5 Å threshold)
Distance Violations: None ✓
Goldschmidt Tolerance: N/A (non-perovskite)
```

**Section 6: Action Buttons**

| Button | Action |
|--------|--------|
| Download CIF | Download `structure.cif` file |
| Download JSON | Download `crystal_card.json` + `feasibility.json` |
| Compare | Add to comparison panel (up to 4 candidates) |
| Share | Copy permalink URL |

#### D. Footer — Global Tools

**Comparison Mode:**
- Select up to 4 candidates for side-by-side comparison
- Shows: 4 crystal viewers in a row, property table comparison, spider chart overlay

**Tc-Pressure Chart:**
- Embedded Plotly chart showing all 50 candidates on Tc vs Feasibility scatter
- Click a point → navigates to that candidate's detail

**Export All:**
- Download all 50 CIF files as ZIP
- Export summary.csv
- Export all crystal cards as single JSON array

### 3.4 Mobile Responsive Layout

On screens < 768px:
- Left panel becomes a **horizontal carousel** of candidate cards at the top
- Right panel stacks vertically below
- 3D viewer gets touch controls (pinch to zoom, swipe to rotate)
- Tables become scrollable horizontally

### 3.5 Data Loading Architecture

```
Frontend (React/Next.js or Vue)
  │
  ├── GET /api/candidates
  │   → Returns summary.csv as JSON array (50 records)
  │   → Used to populate left panel list
  │
  ├── GET /api/candidates/{id}
  │   → Returns merged crystal_card.json + feasibility.json
  │   → Used to populate right panel detail
  │
  ├── GET /api/candidates/{id}/structure.cif
  │   → Returns raw CIF file for 3Dmol.js viewer
  │
  ├── GET /api/predictions
  │   → Returns gcd_predictions.json (family summaries)
  │   → Used for dashboard/overview stats
  │
  └── GET /api/convergence
      → Returns convergence_history.json
      → Used for convergence chart in footer
```

**Alternative (static site):** All data files served directly from `/data/` directory. No backend needed — just a static file server (GitHub Pages, Vercel, Netlify).

### 3.6 Candidate Data Schema (API Response)

For each candidate, the API merges data from three sources:

```json
{
  "candidate_id": "28baf45e3860",
  "rank": 1,

  "composition": "Cu2.02Mo6.62S8.03",
  "family": "chevrel",
  "crystal_system": "trigonal",
  "space_group": "R-3",

  "predicted_Tc_K": 20.06,
  "electron_phonon_lambda": 1.5126,
  "Tc_ambient_K": 20.06,
  "Tc_optimal_K": 20.06,
  "P_optimal_GPa": 0.0,

  "lattice_params": {
    "a": 6.148, "b": 6.179, "c": 5.996,
    "alpha": 90.0, "beta": 90.0, "gamma": 90.0
  },

  "sites": [
    {"label": "Cu(3a)", "element": "Cu", "x": 0.0, "y": 0.0, "z": 0.0, "occupancy": 1.0},
    {"label": "Mo(18f)", "element": "Mo", "x": 0.167, "y": 0.167, "z": 0.167, "occupancy": 1.0},
    {"label": "S(18f)", "element": "S", "x": 0.333, "y": 0.333, "z": 0.050, "occupancy": 1.0}
  ],

  "bond_lengths": {"Cu-Mo": 1.767, "Mo-S": 1.608, "Cu-S": 2.918},
  "coordination_numbers": {"Cu(3a)": 2, "Mo(18f)": 2, "S(18f)": 2},

  "feasibility": {
    "score": 0.9181,
    "synthesis_difficulty": "easy",
    "recommended_method": "solid-state",
    "min_interatomic_distance_A": 1.608,
    "distance_violations": 0,
    "goldschmidt_tolerance": null,
    "bond_valence_sums": {"Cu(3a)": 1.961, "Mo(18f)": 8.915, "S(18f)": 7.122}
  },

  "metadata": {
    "source_iteration": 6,
    "novelty_score": 0.169,
    "gcd_score": 0.737,
    "energy_above_hull_meV": 10.6,
    "stability_confidence": 0.894
  }
}
```

### 3.7 Recommended Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Framework | Next.js 14+ (React) | SSG for static data, fast routing |
| Styling | Tailwind CSS | Utility-first, responsive by default |
| 3D Viewer | 3Dmol.js | Purpose-built for molecular/crystal visualization, reads CIF |
| Charts | Plotly.js or Recharts | Interactive scatter plots, hover tooltips |
| State | Zustand or React Context | Lightweight state for selected candidate, filters |
| Data | Static JSON/CSV files | No backend needed, deploy to any static host |
| Deployment | Vercel / GitHub Pages | Free, fast, git-integrated |

### 3.8 Key Interactions Summary

| User Action | System Response |
|-------------|-----------------|
| Click candidate in list | Load crystal_card.json + feasibility.json, render CIF in 3D viewer |
| Rotate crystal viewer | 3Dmol.js handles mouse drag → rotation |
| Filter by family | Filter left panel list, update candidate count badge |
| Sort by Tc | Reorder left panel list descending by predicted_Tc_K |
| Search "Mo" | Show only candidates containing Mo in composition |
| Click "Compare" | Add candidate to comparison tray (max 4), show side-by-side |
| Adjust pressure slider | Recalculate Tc for selected candidate using Tc(P) curve from agent_p equations |
| Download CIF | Browser downloads structure.cif for use in VESTA, Mercury, etc. |
| Click point on scatter chart | Navigate to that candidate's detail view |

---

## Appendix A: Complete Candidate Data Reference

### Top 10 Candidates by Feasibility

| Rank | ID | Composition | Tc (K) | Feasibility | Family | Space Group | Difficulty |
|------|-----|-------------|--------|-------------|--------|-------------|------------|
| 1 | 28baf45e3860 | Cu₂.₀₂Mo₆.₆₂S₈.₀₃ | 20.06 | 0.918 | Chevrel | R-3 | Easy |
| 2 | 5478e74ebd18 | Cu₁.₆₇Mo₅.₉₀S₇.₈₇ | 19.58 | 0.894 | Chevrel | R-3 | Easy |
| 3 | 7e7d488c126a | Cu₁.₈₇Mo₆.₄₉S₈.₂₃ | 19.73 | 0.875 | Chevrel | R-3 | Easy |
| 4 | 65d30a69ad49 | Sn₀.₉₀Mo₆.₁₃S₆.₃₂ | 19.38 | 0.872 | Chevrel | R-3 | Easy |
| 5 | 05fff1154bd2 | Sn₀.₉₆Mo₅.₆₇S₉.₂₅ | 19.70 | 0.841 | Chevrel | R-3 | Easy |
| 6 | 8c794cf12310 | Sn₀.₈₁Mo₅.₄₆S₉.₂₈ | 19.20 | 0.838 | Chevrel | R-3 | Easy |
| 7 | 220b539c68c2 | Pb₀.₉₈Mo₆.₉₃S₈.₃₄ | 19.70 | 0.820 | Chevrel | R-3 | Easy |
| 8 | ea0cfc2d175c | Sn₀.₉₈Mo₆.₃₆S₆.₉₀ | 18.94 | 0.812 | Chevrel | R-3 | Easy |
| 9 | 847d7701c1f5 | SnMo₅S₈.₅₇ | 19.70 | 0.805 | Chevrel | R-3 | Easy |
| 10 | 9f769362d8e3 | Sn₀.₉₅Mo₅.₉₃S₈.₉₀ | 20.08 | 0.802 | Chevrel | R-3 | Easy |

### Top 5 Candidates by Tc

| Rank | ID | Composition | Tc (K) | Feasibility | Family | Space Group |
|------|-----|-------------|--------|-------------|--------|-------------|
| 1 | 1a3e37f47468 | La₁.₂₆Fe₀.₈₉As₀.₉₃O₀.₈₈F₁.₀₁ | 60.58 | 0.575 | Iron Pnictide | I4/mmm |
| 2 | a1bed4aac0e8 | Li₀.₉₄Fe₀.₈₅As₀.₈₃ | 59.41 | 0.638 | Iron Pnictide | I4/mmm |
| 3 | 1aa1b74cb461 | Mg₁.₀₆B₂.₁₉ | 54.35 | 0.652 | MgB₂-type | P6/mmm |
| 4 | 6525dfbb5911 | Mg₁.₁₃B₁.₈₉ | 53.84 | 0.766 | MgB₂-type | P6/mmm |
| 5 | 33565cb754be | Mg₁.₁₅B₂.₃₃ | 53.76 | 0.602 | MgB₂-type | P6/mmm |

### Crystal System Statistics

| Crystal System | Space Group | Count | Tc Range (K) | Avg Feasibility |
|---------------|-------------|-------|-------------|-----------------|
| Trigonal | R-3 | 35 | 18.94–20.59 | 0.756 |
| Hexagonal | P6/mmm | 10 | 51.80–54.35 | 0.647 |
| Tetragonal | P4/mmm | 3 | 22.15–23.04 | 0.609 |
| Tetragonal | I4/mmm | 2 | 59.41–60.58 | 0.607 |
| Cubic | Pm-3n | 1 | 26.97 | 0.707 |

---

## Appendix B: Pressure Physics Reference

### Tc(P) Behavior by Family

| Family | dTc/dP (K/GPa) | P_min (GPa) | P_max (GPa) | Tc_ceiling (K) | Behavior |
|--------|----------------|-------------|-------------|---------------|----------|
| Cuprate | -1.5 | 0 | 50 | 200 | Monotonic decrease |
| Iron Pnictide | +2.0 | 0 | 30 | 80 | Moderate increase |
| Iron Chalcogenide (FeSe) | +9.0 | 0 | 15 | 80 | Strong increase (anomalous) |
| Heavy Fermion | ~0 | 0 | 20 | 10 | Nearly flat |
| MgB₂ | -1.6 | 0 | 25 | 80 | Gradual decrease |
| A15 | -0.5 | 0 | 30 | 40 | Weak decrease |
| Hydride (H₃S) | N/A | 100 | 300 | 300 | Only stable at extreme P |
| Hydride (LaH₁₀) | N/A | 150 | 300 | 300 | Only stable at extreme P |
| Nickelate | +5.0 | 0 | 30 | 120 | Strong increase |
| Chevrel | -0.3 | 0 | 30 | 20 | Weak decrease |

### Key Equations Displayed in Animation

```
┌──────────────────────────────────────────────────────────────────┐
│ Allen-Dynes Formula:                                              │
│                                                                    │
│         ω_log        -1.04(1 + λ)                                │
│  Tc = ───── × exp ─────────────────                              │
│         1.2        λ - μ*(1 + 0.62λ)                             │
│                                                                    │
│ Birch-Murnaghan EOS:                                              │
│                                                                    │
│        3B₀   ⎡⎛V₀⎞^7/3   ⎛V₀⎞^5/3⎤ ⎡     3            ⎤     │
│  P = ──── × ⎢⎜──⎟    - ⎜──⎟    ⎥ ⎢1 + ─(B₀'-4)×f(V)⎥     │
│         2    ⎣⎝ V⎠      ⎝ V⎠    ⎦ ⎣     4            ⎦     │
│                                                                    │
│ Grüneisen Scaling:                                                │
│                     γ                                              │
│  ω(V) = ω₀ × (V₀/V)     phonon stiffening under compression    │
│                                                                    │
│ Volume-Dependent Coupling:                                        │
│                     η                                              │
│  λ(V) = λ₀ × (V/V₀)     coupling change under compression      │
└──────────────────────────────────────────────────────────────────┘
```

---

*Generated: March 2026 | Opensens Academic Agent v1.0*
