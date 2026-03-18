# Multi-Agent System for Predicting Novel Superconductor Crystal Structures

## Leveraging AlphaFold 3, NEMAD, and Claude Code CLI

---

## 1. System Overview

This document describes an AI-driven multi-agent framework that discovers new superconducting crystal structures through iterative simulation, comparison, and refinement. Three specialized agents — **Agent CS**, **Agent Sin**, and **Agent Ob** — form a closed feedback loop, each running as an autonomous Claude Code CLI session, coordinated via a shared workspace and git-based synchronization.

The core premise: if we can build a simulation model whose synthetic output is statistically indistinguishable (≥95% match) from real experimental superconductor data, then the crystal patterns embedded in that model represent physically plausible — and potentially novel — superconducting structures.

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR (Claude Code)                  │
│              Launches agents · Monitors convergence             │
│              Manages shared data/ directory via git             │
└────────┬──────────────────┬──────────────────┬──────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  Agent CS    │  │  Agent Sin   │  │  Agent Ob    │
  │  (Crystal    │─▶│  (Simulation │─▶│  (Observator │
  │   Structure) │  │   Agent)     │  │   Agent)     │
  └──────────────┘  └──────────────┘  └──────┬───────┘
         ▲                                    │
         └────────────────────────────────────┘
                   Refinement feedback
```

---

## 2. The Three Agents

### 2.1 Agent CS — Crystal Structure Agent

**Role:** The knowledge curator. Agent CS owns the crystal structure knowledge base and produces structured "crystal pattern cards" that downstream agents consume.

**Functions:**

1. **Data Ingestion & Mapping**
   - Loads the NEMAD database (67,573 magnetic material entries with composition, crystal system, lattice parameters, space groups)
   - Pulls superconductor entries from the Materials Project, ICSD, AFLOW, and SuperCon databases
   - Indexes AlphaFold 3's structure prediction outputs for relevant inorganic compounds

2. **Classification & Pattern Extraction**
   - Clusters known superconductors by crystal family (perovskite, cuprate, iron-based pnictide, heavy-fermion, MgB₂-type, hydride, nickelate, etc.)
   - For each cluster, extracts a **crystal pattern card**:
     ```json
     {
       "pattern_id": "cuprate-layered-001",
       "crystal_system": "tetragonal",
       "space_group": "I4/mmm",
       "lattice_params": {"a": 3.78, "c": 13.2},
       "key_motifs": ["CuO2 planes", "charge reservoir layers"],
       "typical_Tc_range_K": [30, 135],
       "dopant_sites": ["La/Sr", "Ba/Y"],
       "electronic_features": {"d_band_filling": 0.85, "Fermi_surface": "nested"},
       "source_compounds": ["YBa2Cu3O7", "La2-xSrxCuO4", "Bi2Sr2CaCu2O8"]
     }
     ```
   - Uses NEMAD's feature engineering pipeline (elemental proportions, electronegativity, atomic weight vectors) to generate descriptors for every pattern

3. **Gap Analysis**
   - Identifies underexplored regions of crystal-chemistry space (e.g., ternary nitrides, high-pressure hydrides with novel stoichiometries)
   - Proposes **candidate patterns** — hypothetical crystal structures that interpolate or extrapolate from known families

**Claude Code CLI implementation:**
- Runs as a Claude Code session with access to Python (pandas, pymatgen, scikit-learn)
- Reads/writes pattern cards to `data/crystal_patterns/` as JSON
- Uses the NEMAD classification models (Random Forest, XGBoost) already in `NEMAD-MagneticML-main/Classification_Models/`
- Outputs a versioned `pattern_catalog.json` after each iteration

---

### 2.2 Agent Sin — Simulation Agent

**Role:** The builder. Agent Sin takes crystal pattern cards from Agent CS and constructs computational models that generate synthetic superconductor data.

**Functions:**

1. **Structure Generation**
   - Receives crystal pattern cards from `data/crystal_patterns/`
   - Uses a diffusion-based generative model (inspired by CrysVCD / CDVAE architectures) to generate candidate crystal structures that satisfy the pattern constraints
   - Applies AlphaFold 3's diffusion module paradigm: random rotations/translations for equivariance, iterative denoising to refine atomic coordinates within the unit cell

2. **Property Simulation**
   - For each generated structure, computes:
     - **Electronic band structure** (via tight-binding approximation or ML surrogate trained on DFT data)
     - **Phonon density of states** (using ML interatomic potentials — MACE, M3GNet, or CHGNet)
     - **Electron-phonon coupling** λ (via BCS/Allen-Dynes proxy models, similar to BEE-NET)
     - **Predicted Tc** from McMillan/Allen-Dynes equation
   - Uses NEMAD-derived features (magnetic moment, electronegativity, elemental proportions) as auxiliary inputs

3. **Synthetic Dataset Assembly**
   - Packages simulation outputs into a structured dataset:
     ```
     data/synthetic/
       iteration_001/
         structures.cif          # Generated CIF files
         properties.csv          # Tc, λ, band gap, DOS features
         phonon_spectra.npy      # Phonon DOS arrays
         metadata.json           # Pattern IDs, generation params
     ```
   - Each iteration produces ~500–2000 candidate structures per pattern family

**Claude Code CLI implementation:**
- Runs as a Claude Code session with access to Python (ASE, pymatgen, torch)
- Calls external simulation tools via Bash (VASP/Quantum ESPRESSO for DFT validation of top candidates, or ML surrogates for speed)
- Reads pattern cards from `data/crystal_patterns/`, writes synthetic data to `data/synthetic/`
- Can launch GPU-accelerated jobs on a remote cluster if available

---

### 2.3 Agent Ob — Observator Agent

**Role:** The critic. Agent Ob quantitatively compares synthetic data against real experimental data, identifies where the simulation falls short, and generates actionable refinement instructions.

**Functions:**

1. **Data Alignment**
   - Loads real experimental superconductor data (Tc values, crystal structures, lattice parameters from SuperCon/NEMAD/Materials Project)
   - Loads Agent Sin's synthetic data from `data/synthetic/iteration_N/`
   - Aligns datasets by crystal family, composition space, and property dimensions

2. **Statistical Comparison**
   - Computes a multi-dimensional match score:
     - **Tc distribution similarity** — Wasserstein distance between real and synthetic Tc distributions per crystal family
     - **Structural fidelity** — RMSD of lattice parameters, space group accuracy, coordination number distributions
     - **Electronic property correlation** — Pearson/Spearman correlation of band gap, DOS features, λ values
     - **Composition validity** — charge neutrality, Pauling electronegativity balance, known oxidation state constraints
   - Aggregates into a single **convergence score** (0–100%)

3. **Discrepancy Analysis & Refinement Instructions**
   - When convergence < 95%, identifies the dominant failure modes:
     - "Tc systematically overestimated for cuprate family by ~15K → adjust electron-phonon coupling model"
     - "Iron-pnictide structures have incorrect As height above Fe plane → tighten geometric constraints"
     - "Missing rare-earth substitution patterns in heavy-fermion cluster → Agent CS should expand pattern card"
   - Writes a structured **refinement report**:
     ```json
     {
       "iteration": 3,
       "convergence_score": 0.78,
       "refinements": [
         {
           "target_agent": "CS",
           "action": "expand_pattern",
           "pattern_id": "heavy-fermion-002",
           "detail": "Include Yb and Sm site substitutions based on CeCoIn5 family"
         },
         {
           "target_agent": "Sin",
           "action": "adjust_model",
           "parameter": "lambda_scaling_pnictide",
           "current": 1.2,
           "suggested": 0.95,
           "reason": "Tc overestimation in FeAs-type compounds"
         }
       ]
     }
     ```

4. **Novelty Flagging**
   - When synthetic structures with high predicted Tc do NOT match any known experimental compound → flags as **novel candidates** for DFT validation
   - Maintains a `data/novel_candidates/` directory with ranked proposals

**Claude Code CLI implementation:**
- Runs as a Claude Code session with access to Python (scipy, numpy, pandas, matplotlib)
- Reads from both `data/experimental/` and `data/synthetic/`
- Writes refinement reports to `data/refinements/iteration_N.json`
- Generates convergence plots saved to `data/reports/`

---

## 3. The Feedback Loop

### 3.1 Iterative Convergence Protocol

```
Iteration 0 (Bootstrap):
  CS → Builds initial pattern catalog from NEMAD + literature
  Sin → Generates first synthetic dataset from initial patterns
  Ob → Computes baseline convergence score

Iteration N (N ≥ 1):
  1. Ob reads synthetic data (iteration N-1) + real data
  2. Ob computes convergence score
  3. IF convergence ≥ 95% → STOP, output final candidates
  4. ELSE:
     a. Ob writes refinement report
     b. CS reads refinements targeting it → updates pattern cards
     c. Sin reads refinements targeting it + updated patterns → regenerates synthetic data
     d. → Go to step 1 with iteration N+1

Termination conditions:
  - Convergence ≥ 95%
  - Maximum iterations reached (default: 20)
  - Convergence plateau detected (Δ < 0.5% over 3 consecutive iterations)
```

### 3.2 Convergence Score Breakdown

| Component                    | Weight | Metric                                     |
|------------------------------|--------|---------------------------------------------|
| Tc distribution match        | 30%    | 1 - normalized Wasserstein distance         |
| Lattice parameter accuracy   | 25%    | Mean (1 - |Δa/a|, 1 - |Δc/c|)             |
| Space group correctness      | 15%    | Fraction of structures in correct space grp |
| Electronic property match    | 15%    | Pearson correlation of DOS/band features    |
| Composition validity         | 10%    | Fraction passing charge-neutrality check    |
| Coordination geometry        | 5%     | Mean RMSD of nearest-neighbor distances     |

### 3.3 Agent Communication via Shared Filesystem

All three agents communicate through a shared `data/` directory structure, synchronized via git:

```
data/
├── experimental/              # Real superconductor data (static reference)
│   ├── supercon_database.csv
│   ├── structures/            # CIF files of known superconductors
│   └── nemad_features.csv
├── crystal_patterns/          # Agent CS outputs (versioned)
│   ├── pattern_catalog_v001.json
│   └── pattern_catalog_v002.json
├── synthetic/                 # Agent Sin outputs
│   ├── iteration_001/
│   ├── iteration_002/
│   └── ...
├── refinements/               # Agent Ob outputs
│   ├── iteration_001.json
│   └── iteration_002.json
├── novel_candidates/          # Structures flagged as potentially new
│   ├── candidate_001.cif
│   └── candidates_ranked.csv
└── reports/                   # Convergence plots, summaries
    ├── convergence_history.png
    └── final_report.md
```

### 3.4 Claude Code CLI Orchestration

Using Claude Code's **Agent Teams** (v2.1.32+), the system orchestrates as follows:

```bash
# Orchestrator session launches the three agents
claude --agent-team \
  --agent "CS:crystal-structure-curator" \
  --agent "Sin:simulation-builder" \
  --agent "Ob:observator-critic" \
  --shared-dir ./data \
  --max-iterations 20 \
  --convergence-target 0.95
```

Alternatively, with the standard Claude Code `Agent` tool, the orchestrator spawns each agent as a subagent with specific prompts and tools:

1. **Orchestrator** (main Claude Code session) manages iteration count and convergence checks
2. Each iteration:
   - Spawns Agent CS (if refinements target it) — runs in foreground, returns updated patterns
   - Spawns Agent Sin — reads patterns + refinements, generates synthetic data
   - Spawns Agent Ob — compares, scores, writes refinement report
3. Orchestrator reads convergence score from Ob's report and decides whether to continue

---

## 4. Integrating AlphaFold 3 and NEMAD

### 4.1 AlphaFold 3 — Adapted for Inorganic Crystals

AlphaFold 3 was designed for biomolecular structure prediction, but several of its architectural innovations transfer directly to crystal structure prediction:

| AlphaFold 3 Component          | Adaptation for Crystal Structures                                           |
|---------------------------------|-----------------------------------------------------------------------------|
| **Pairformer module**           | Encodes pairwise atomic interactions in the unit cell (replacing MSA)       |
| **Diffusion-based generation**  | Generates atomic coordinates within the unit cell via iterative denoising   |
| **Equivariance via augmentation** | Random rotations/translations during training (no need for SE(3)-equivariant architecture) |
| **Confidence scoring (pLDDT)**  | Repurposed as structure stability confidence metric                         |
| **Cross-attention over tokens** | Applied to composition tokens (element + site) instead of amino acid tokens |

**How Agent Sin uses AlphaFold 3:**
- The diffusion module from `alphafold3-main/src/alphafold3/` is adapted to operate on periodic crystal unit cells rather than molecular chains
- Input: composition + space group + target lattice parameters (from Agent CS pattern card)
- Output: refined atomic positions within the unit cell, with confidence scores
- The Pairformer captures interatomic interactions (bond lengths, angles) that determine superconducting properties
- AlphaFold 3's training paradigm (diffusion denoising) naturally handles the multi-modal nature of crystal structures

**Key adaptation work needed:**
1. Replace amino acid vocabulary with element vocabulary (118 elements + oxidation states)
2. Add periodicity-aware distance calculations (minimum image convention)
3. Train on crystal structures from Materials Project / ICSD (~200K structures)
4. Fine-tune on the ~5,000 known superconductor structures

### 4.2 NEMAD — Feature Engineering and Magnetic Classification

NEMAD provides the feature engineering backbone and classification capability:

| NEMAD Component                     | Role in the System                                                        |
|--------------------------------------|---------------------------------------------------------------------------|
| **67,573-entry database**            | Reference for magnetic/structural properties; overlaps with superconductor families |
| **Feature generator** (`feature_generator_from_chemical_composition.ipynb`) | Generates descriptors for any new composition: elemental proportions, electronegativity, atomic weight, entropy, magnetic proportion |
| **Classification models** (RF, XGB)  | Agent CS uses these to pre-classify candidate materials as FM/AFM/NM, filtering relevant candidates |
| **Curie/Néel temperature models**    | Provides magnetic transition temperature predictions that correlate with superconducting behavior in some families |
| **LLM-extracted structural data**    | Crystal system, lattice structure, space group information used as ground truth for validation |

**How Agent CS uses NEMAD:**
- Loads `Dataset/Classification_FM_AFM_NM.csv` to map the composition→magnetic-phase landscape
- Uses the feature generator to create descriptors for new candidate compositions
- Many unconventional superconductors (heavy-fermion, iron-pnictide) coexist near magnetic phase boundaries — NEMAD's magnetic classification helps identify these "sweet spots"
- NEMAD's crystal structure metadata (space groups, lattice parameters) serves as ground truth for Agent Ob's validation

**How Agent Ob uses NEMAD:**
- Compares Agent Sin's predicted lattice parameters against NEMAD's experimentally-derived values
- Uses NEMAD's magnetic classification as a cross-check: if a predicted superconductor is classified as strongly ferromagnetic, it's likely a false positive (conventional BCS superconductivity is suppressed by ferromagnetism)

---

## 5. Challenges and Mitigation Strategies

### 5.1 Data Alignment

**Challenge:** Experimental superconductor databases (SuperCon, NEMAD, Materials Project) use different conventions for composition notation, space group symbols, temperature units, and measurement conditions. Merging them into a coherent reference dataset is non-trivial.

**Mitigation:**
- Build a canonical schema with pymatgen's `Structure` and `Composition` objects as the standard internal representation
- Use fuzzy matching on space group symbols (e.g., "I4/mmm" vs "139") with spglib
- Normalize all Tc values to onset temperature at ambient pressure unless explicitly stated otherwise
- Agent CS maintains a `data/experimental/data_provenance.json` tracking the source and normalization applied to each entry

### 5.2 Pattern Recognition Across Crystal Families

**Challenge:** Superconductor families are diverse — cuprates, pnictides, heavy-fermion compounds, MgB₂-types, hydrides, and nickelates have fundamentally different pairing mechanisms. A single pattern extraction approach may not capture family-specific physics.

**Mitigation:**
- Agent CS uses hierarchical clustering: first by crystal system, then by bonding motifs, then by electronic structure features
- Family-specific "physics priors" are encoded in pattern cards (e.g., cuprates need CuO₂ planes, pnictides need FeAs/FeSe layers)
- The convergence score in Agent Ob is computed per-family, so weak families don't hide behind strong ones
- Novelty candidates that don't fit any existing family are flagged separately for manual expert review

### 5.3 Simulation Fidelity

**Challenge:** ML surrogate models for electronic structure and phonons are fast but approximate. If the surrogates are systematically biased, the feedback loop may converge to a wrong answer with high confidence.

**Mitigation:**
- **Hierarchical validation**: ML surrogates for rapid screening → DFT (VASP/QE) for top-50 candidates per iteration → experimental synthesis for top-5 at convergence
- Agent Ob tracks not just mean error but **systematic bias** per crystal family (e.g., "all pnictide Tc values shifted +12K")
- Periodically (every 5 iterations), run DFT spot-checks on a random sample of synthetic structures and recalibrate the surrogate model
- Include uncertainty quantification — surrogate models should output confidence intervals, not just point predictions

### 5.4 Computational Cost

**Challenge:** AlphaFold 3's diffusion model is expensive; running DFT on thousands of structures per iteration is prohibitive.

**Mitigation:**
- Use a **funnel strategy**: generate many structures cheaply (ML), score and rank, validate only the top tier with expensive methods
- Batch GPU jobs for diffusion model inference
- Use pre-trained ML interatomic potentials (M3GNet, MACE) instead of ab-initio phonon calculations for the screening phase
- Cache computed properties in a local database to avoid redundant calculations across iterations

### 5.5 Convergence Instability

**Challenge:** The feedback loop might oscillate — Agent Ob's corrections in iteration N cause overcorrection in iteration N+1, leading to oscillating convergence scores.

**Mitigation:**
- Apply **damped refinements**: Agent Ob suggests parameter changes, but Agent Sin applies only 50–70% of the suggested adjustment (learning rate analogy)
- Track convergence history; if oscillation is detected (score alternates up/down for 3+ iterations), reduce the refinement magnitude
- Use an exponential moving average of refinement suggestions across iterations rather than applying each one independently

### 5.6 Bridging AlphaFold 3 from Proteins to Crystals

**Challenge:** AlphaFold 3 is designed for finite molecules (proteins, nucleic acids, ligands) — not infinite periodic crystal lattices. Adapting it requires fundamental changes to distance calculations and loss functions.

**Mitigation:**
- Replace Euclidean distance calculations with periodic distance (minimum image convention) using pymatgen/ASE
- Modify the diffusion target: instead of predicting all-atom coordinates, predict fractional coordinates within the asymmetric unit + lattice parameters
- Use the "unit cell as molecule" approximation for small-cell structures (<50 atoms), falling back to periodic SE(3) methods for larger cells
- Leverage existing crystal diffusion models (CDVAE, DiffCSP, CrysVCD) as starting points, incorporating AlphaFold 3's Pairformer attention mechanism

### 5.7 Novelty vs. Stability

**Challenge:** The system might predict crystal structures that are thermodynamically or dynamically unstable (negative phonon frequencies, above-hull energy).

**Mitigation:**
- Agent Sin includes a stability pre-filter: predicted structures must have:
  - Energy above hull < 50 meV/atom (thermodynamic plausibility)
  - No imaginary phonon modes (dynamical stability) — checked via ML potential
- Agent Ob cross-references predicted compositions against known decomposition pathways
- Rank novel candidates by a composite score: predicted Tc × stability confidence × synthesizability estimate

---

## 6. Implementation Roadmap

### Phase 1 — Foundation (Weeks 1–4)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Curate experimental superconductor dataset (SuperCon + NEMAD overlap) | Agent CS (manual + automated) | `data/experimental/` populated |
| Adapt NEMAD feature generator for superconductor-specific features | Agent CS | Extended `feature_generator.py` |
| Set up ML surrogate for Tc prediction (train on SuperCon) | Agent Sin | `models/tc_predictor.pt` |
| Build convergence scoring module | Agent Ob | `src/convergence.py` |
| Define JSON schemas for pattern cards, refinement reports | All | `schemas/` directory |

### Phase 2 — Core Loop (Weeks 5–10)

| Task | Owner | Deliverable |
|------|-------|-------------|
| Implement Agent CS pattern extraction pipeline | CS | Pattern catalog v1 |
| Adapt crystal diffusion model (based on CDVAE + AF3 attention) | Sin | Structure generator v1 |
| Implement Agent Ob comparison engine | Ob | Refinement report v1 |
| Run first 5 iterations, debug feedback loop | Orchestrator | Convergence history |
| Tune convergence weights based on initial results | Ob | Calibrated scoring |

### Phase 3 — Validation & Scale (Weeks 11–16)

| Task | Owner | Deliverable |
|------|-------|-------------|
| DFT validation of top novel candidates | Sin (external compute) | DFT-confirmed candidates |
| Scale to 20+ iterations, target 95% convergence | All | Final candidate list |
| Generate synthesis recommendations for top-10 candidates | CS + Ob | Synthesis report |
| Write up methodology and results | All | Publication draft |

---

## 7. Expected Outputs

1. **A refined crystal pattern catalog** — structured library of superconductor crystal motifs, machine-readable, versioned
2. **Novel superconductor candidates** — 10–50 crystal structures predicted to be superconducting, ranked by Tc and stability, with DFT validation for the top tier
3. **Trained ML models** — Tc predictor, structure generator, stability classifier, all fine-tuned on superconductor data
4. **A reusable multi-agent framework** — the CS/Sin/Ob architecture can be applied to other materials discovery problems (thermoelectrics, catalysts, battery materials) by swapping the domain-specific pattern cards and property targets

---

## 8. Running on Claude Code CLI

### Agent Spawning

Each agent runs as a Claude Code subagent. The orchestrator prompt would look like:

```python
# Pseudocode for orchestrator logic
for iteration in range(MAX_ITERATIONS):
    # Agent CS: update patterns if refinements exist
    if iteration > 0:
        spawn_agent("CS", prompt=f"""
            Read refinement report at data/refinements/iteration_{iteration-1:03d}.json.
            Update crystal pattern cards in data/crystal_patterns/ accordingly.
            Use NEMAD feature generator for any new compositions.
            Output updated pattern_catalog_v{iteration:03d}.json.
        """)

    # Agent Sin: generate synthetic data
    spawn_agent("Sin", prompt=f"""
        Read latest pattern catalog from data/crystal_patterns/.
        Read any refinements targeting you from data/refinements/.
        Generate synthetic superconductor structures and properties.
        Output to data/synthetic/iteration_{iteration:03d}/.
    """)

    # Agent Ob: compare and score
    result = spawn_agent("Ob", prompt=f"""
        Compare data/synthetic/iteration_{iteration:03d}/ against data/experimental/.
        Compute convergence score.
        If < 95%, write refinement report to data/refinements/iteration_{iteration:03d}.json.
        Flag novel candidates to data/novel_candidates/.
        Output convergence score as first line of response.
    """)

    score = parse_convergence(result)
    if score >= 0.95:
        print(f"Converged at iteration {iteration} with score {score}")
        break
```

### Required Tools per Agent

| Agent | Python Packages | External Tools | Claude Code Tools |
|-------|----------------|----------------|-------------------|
| CS    | pandas, pymatgen, scikit-learn, spglib | — | Read, Write, Bash, Glob, Grep |
| Sin   | torch, ase, pymatgen, numpy | VASP/QE (optional), GPU cluster | Read, Write, Bash |
| Ob    | scipy, numpy, pandas, matplotlib | — | Read, Write, Bash, Glob |

---

## References and Further Reading

- [NEMAD: Northeast Materials Database (Nature Communications)](https://www.nature.com/articles/s41467-025-64458-z)
- [NEMAD: Enabling Discovery of High Tc Magnetic Compounds (arXiv)](https://arxiv.org/html/2409.15675v1)
- [Generative AI for Crystal Structures: A Review (npj Computational Materials)](https://www.nature.com/articles/s41524-025-01881-2)
- [Deep Learning Generative Model for Crystal Structure Prediction (npj Computational Materials)](https://www.nature.com/articles/s41524-024-01443-y)
- [Crystal Structure Prediction Meets AI (J. Phys. Chem. Lett.)](https://pubs.acs.org/doi/10.1021/acs.jpclett.4c03727)
- [AI-Accelerated Materials Discovery in 2026 (Cypris)](https://www.cypris.ai/insights/ai-accelerated-materials-discovery-in-2025-how-generative-models-graph-neural-networks-and-autonomous-labs-are-transforming-r-d)
- [Complete AI-Accelerated Workflow for Superconductor Discovery (npj Computational Materials)](https://www.nature.com/articles/s41524-026-01964-8)
- [GNN-Powered LLM Multi-Agent AI for Alloy Design (MRS Bulletin)](https://link.springer.com/article/10.1557/s43577-025-00953-4)
- [AI-Driven Discovery of High-Tc Superconductors (arXiv)](https://arxiv.org/abs/2511.03865)
- [Guided Diffusion for Superconductor Discovery (arXiv)](https://www.arxiv.org/pdf/2509.25186)
- [Claude Code Agent Teams Documentation](https://code.claude.com/docs/en/agent-teams)
- [AlphaFold 3 — Accurate Structure Prediction (Nature)](https://www.nature.com/articles/s41586-024-07487-w)
