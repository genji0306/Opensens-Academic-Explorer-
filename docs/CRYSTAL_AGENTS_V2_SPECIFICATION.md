# Crystal Structure Prediction Agent Suite — v2.0 Specification

> **Document Version**: 2.0
> **Date**: 2026-03-17
> **Status**: Draft Specification
> **Branch**: `feature/lab-sequence-rehab`
> **Supersedes**: `SUPERCONDUCTOR_MULTIAGENT_PLAN.md` (v1.0 core loop agents)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [CLAUDE.md & Skill v2.0 — Foundational Material Research Skill](#3-claudemd--skill-v20)
4. [Agent PB — Crystal Structure Prediction (GNN + Optimization)](#4-agent-pb)
5. [Crystal Agent Improvement — Convergence to 99% Accuracy](#5-crystal-agent-improvement)
6. [Agent V — Visualization Agent](#6-agent-v)
7. [Agent XC — XRD End-to-End Prediction Agent](#7-agent-xc)
8. [Cross-Agent Integration & Data Flow](#8-cross-agent-integration)
9. [Performance Benchmarking Framework](#9-performance-benchmarking-framework)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Executive Summary

This specification defines five interconnected modules that extend the existing
superconductor multi-agent system (Agents CS, Sin, Ob, P, CB, GCD) into a
general-purpose crystal structure prediction platform:

| Module | Purpose | Target Accuracy |
|--------|---------|-----------------|
| **Skill v2.0** | Foundational material research orchestration | N/A (meta-layer) |
| **Agent PB** | GNN + optimization structure prediction | >=99% |
| **Crystal Agent** | Enhanced convergence loop (v1 agents) | >=99% |
| **Agent V** | CIF visualization, dashboard, real-time monitoring | N/A (visualization) |
| **Agent XC** | End-to-end prediction from powder XRD data | >=95% match rate |

All agents share a common data schema (CIF, `.osens` crystal cards, CSV
property tables) and communicate through the file-based message bus established
in v1.0 under `data/`.

---

## 2. System Architecture Overview

```
+------------------------------------------------------------------+
|                        CLAUDE.md / Skill v2.0                     |
|          (Orchestration, requirement parsing, routing)            |
+------+---+---+---+---+------------------------------------------+
       |   |   |   |   |
       v   v   v   v   v
  +-------+ +-------+ +-------+ +-------+ +-------+
  |Crystal| |Agent  | |Agent  | |Agent  | |Agent  |
  |Agent  | |PB     | |V      | |XC     | |GCD/CB |
  |v1->v2 | |GNN+OA | |Visual.| |XRD E2E| |(exist)|
  +---+---+ +---+---+ +---+---+ +---+---+ +---+---+
      |         |          ^         |          |
      |         |          |         |          |
      v         v          |         v          v
  +------------------------------------------------------------------+
  |                    Shared Data Layer                              |
  |  data/experimental/  data/synthetic/  data/predictions/          |
  |  data/crystal_structures/  data/xrd_input/  data/benchmarks/     |
  +------------------------------------------------------------------+
```

### Communication Protocol

All agents exchange data via JSON files and CSV tables in the `data/` directory
tree. No network sockets are required. The orchestrator (`orchestrator.py`)
manages execution order; Skill v2.0 extends the orchestrator with
intent-routing capabilities.

---

## 3. CLAUDE.md & Skill v2.0 — Foundational Material Research Skill

### 3.1 Purpose

Skill v2.0 acts as the **meta-orchestration layer** that translates
human-defined material requirements into structured agent execution plans. It
replaces ad-hoc CLI invocations with intent-driven routing.

### 3.2 CLAUDE.md Definition

A project-level `CLAUDE.md` file provides persistent instructions to any AI
coding assistant operating on this repository:

```markdown
# CLAUDE.md — Opensens Academic Agent

## Project Type
Multi-agent crystal structure prediction system (Python 3.11+)

## Architecture
- `src/agents/` — Six core agents (CS, Sin, Ob, P, CB, GCD)
- `Agent PB/` — GNN-OA crystal predictor (TensorFlow/MEGNet + Hyperopt/PSO)
- `xtalnet/` — XRD-to-structure transformer (PyTorch Lightning)
- `src/orchestrator.py` — Feedback loop controller
- `data/` — All intermediate and final outputs

## Conventions
- Agents are stateless between iterations; state persists in `data/`
- All crystal data uses pymatgen Structure objects internally
- CIF is the canonical structure exchange format
- JSON pattern cards follow `schemas/pattern_card.json`
- Convergence target: 0.95 (v1), 0.99 (v2)
- Damping factor: 0.35 on refinement suggestions

## Running
- Full pipeline: `python run.py --max-iterations 20 --target 0.99`
- Agent PB standalone: `python -m agent_pb.predict --input gnoa.in`
- XRD agent: `python -m agent_xc.predict --xrd <pattern.xy>`
- Visualization: `python -m agent_v.dashboard`

## Testing
- `pytest tests/ -v`
- Benchmark: `python -m benchmarks.compare_agents`

## Key Dependencies
numpy, pandas, scipy, torch, pytorch_lightning, pymatgen, tensorflow,
megnet, hyperopt, scikit-opt, hydra-core, matplotlib, plotly, dash
```

### 3.3 Skill v2.0 Functional Specification

**Skill Name**: `material-research-v2`

**Input**: Natural language requirement string
**Output**: Structured execution plan + agent selection + parameter configuration

#### 3.3.1 Capability Matrix

| Capability | v1.0 (Current) | v2.0 (Target) | v3.0 (Future) |
|------------|----------------|----------------|----------------|
| Requirement parsing | Manual CLI flags | NL intent extraction | Conversational refinement |
| Agent selection | Fixed pipeline order | Conditional routing by task type | Adaptive multi-path execution |
| Property prediction | Tc only (Allen-Dynes) | Tc + band gap + elastic moduli | Full DFT-surrogate property suite |
| Data sources | NEMAD + hardcoded refs | + Materials Project API + AFLOW | + ICSD + COD + user uploads |
| Accuracy target | 95% convergence | 99% convergence | 99.5% + uncertainty quantification |
| Output format | CSV + JSON | + CIF + interactive dashboard | + synthesis protocol + cost estimate |

#### 3.3.2 Intent Router

Skill v2.0 classifies user requests into one of five execution paths:

```python
INTENT_MAP = {
    "predict_structure": {
        "agents": ["agent_pb", "crystal_agent"],
        "description": "Predict crystal structure from composition",
        "required_input": ["chemical_formula"],
        "optional_input": ["space_group_range", "pressure_gpa", "target_properties"]
    },
    "predict_from_xrd": {
        "agents": ["agent_xc"],
        "description": "Predict structure from experimental XRD pattern",
        "required_input": ["xrd_pattern_file"],
        "optional_input": ["composition_hint", "wavelength"]
    },
    "discover_material": {
        "agents": ["agent_cs", "agent_sin", "agent_ob", "agent_p", "agent_gcd"],
        "description": "Discover novel materials via iterative convergence",
        "required_input": ["material_family"],
        "optional_input": ["target_tc", "pressure_range", "max_iterations"]
    },
    "visualize": {
        "agents": ["agent_v"],
        "description": "Visualize crystal structures and prediction results",
        "required_input": ["structure_source"],
        "optional_input": ["animation", "export_format"]
    },
    "benchmark": {
        "agents": ["agent_pb", "crystal_agent", "agent_xc"],
        "description": "Compare prediction agents on reference dataset",
        "required_input": ["benchmark_dataset"],
        "optional_input": ["metrics", "agents_to_compare"]
    }
}
```

#### 3.3.3 Configuration Schema

```json
{
  "skill_version": "2.0",
  "execution_plan": {
    "intent": "predict_structure",
    "agents": ["agent_pb"],
    "parameters": {
      "chemical_formula": "Ca4S4",
      "space_group_range": [2, 230],
      "algorithm": "tpe",
      "max_steps": 5000,
      "convergence_target": 0.99,
      "output_formats": ["cif", "json", "dashboard"]
    },
    "post_processing": ["agent_v"],
    "benchmark_against": ["crystal_agent"]
  }
}
```

#### 3.3.4 Future Version Roadmap

**v2.1** — Active learning loop: Agent identifies which compositions to query
next for maximum information gain, reducing the number of DFT calculations
needed.

**v2.5** — Multi-objective optimization: Simultaneously optimize Tc, stability,
synthesizability, and cost. Pareto front visualization via Agent V.

**v3.0** — Conversational material design: User describes desired properties in
natural language ("I need a room-temperature superconductor that can be
synthesized below 50 GPa"). The skill iteratively refines requirements,
proposes candidates, and explains trade-offs.

---

## 4. Agent PB — Crystal Structure Prediction (GNN + Optimization)

### 4.1 Overview

Agent PB (Prediction by Bayesian/PSO optimization) combines a **Graph Neural
Network** energy model with **optimization algorithms** to predict crystal
structures from chemical composition. It extends the existing GN-OA codebase
(`Agent PB/predict_structure.py`) with modern architectures and a 99% accuracy
target.

### 4.2 Directory Structure

```
Agent PB/
├── README.md                       # (existing) GN-OA documentation
├── predict_structure.py            # (existing) v0.2 monolithic predictor
├── GN-OA_0.2.0.zip               # (existing) original release
├── qmdb__v1_8__022026.sql.gz     # (existing) quantum materials database
├── NN_model/
│   └── orig_megnet.py             # (existing) MEGNet wrapper
├── utils/
│   ├── wyckoff_position/          # (existing) Wyckoff combinatorics
│   ├── file_utils.py              # (existing)
│   ├── read_input.py              # (existing)
│   ├── compound_utils.py          # (existing)
│   ├── algo_utils.py              # (existing)
│   └── print_utils.py             # (existing)
├── data/                           # (existing) training data
├── example/                        # (existing) example inputs
├── images/                         # (existing) documentation images
│
│  ── NEW v2.0 additions ──────────────────────────────────────────
│
├── agent_pb/                       # New: modular agent package
│   ├── __init__.py
│   ├── predict.py                  # Entry point: CLI + programmatic API
│   ├── config.py                   # Agent-specific configuration
│   ├── gnn/
│   │   ├── __init__.py
│   │   ├── megnet_model.py         # Refactored MEGNet wrapper
│   │   ├── cgcnn_model.py          # NEW: Crystal Graph CNN
│   │   ├── alignn_model.py         # NEW: Atomistic Line Graph NN
│   │   ├── m3gnet_model.py         # NEW: M3GNet universal potential
│   │   └── ensemble.py             # NEW: Model ensemble + uncertainty
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── tpe_optimizer.py        # Bayesian (Tree-Parzen Estimator)
│   │   ├── pso_optimizer.py        # Particle Swarm Optimization
│   │   ├── cma_es_optimizer.py     # NEW: CMA-ES for continuous spaces
│   │   ├── genetic_optimizer.py    # NEW: Genetic algorithm for discrete
│   │   └── hybrid_optimizer.py     # NEW: Multi-stage optimization
│   ├── constraints/
│   │   ├── __init__.py
│   │   ├── symmetry.py             # Space group + Wyckoff enforcement
│   │   ├── chemistry.py            # Charge neutrality, oxidation states
│   │   ├── geometry.py             # Bond length/angle constraints
│   │   └── stability.py            # Energy above hull filter
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py              # Match rate, RMSD, fingerprint distance
│   │   └── benchmark.py            # Cross-agent comparison harness
│   └── io/
│       ├── __init__.py
│       ├── cif_io.py               # CIF read/write
│       ├── poscar_io.py            # VASP POSCAR format
│       └── pattern_card_io.py      # JSON pattern card exchange
├── tests/
│   ├── test_gnn_models.py
│   ├── test_optimizers.py
│   ├── test_constraints.py
│   └── test_end_to_end.py
└── benchmarks/
    ├── reference_structures/       # Known structures for validation
    ├── run_benchmark.py
    └── results/
```

### 4.3 Architecture

```
                        Chemical Formula
                              |
                    +---------v----------+
                    | Input Parser       |
                    | (composition,      |
                    |  constraints,      |
                    |  space group range)|
                    +---------+----------+
                              |
                    +---------v----------+
                    | Wyckoff Enumerator |
                    | (all valid site    |
                    |  combinations)     |
                    +---------+----------+
                              |
              +---------------+----------------+
              |                                |
    +---------v----------+          +----------v---------+
    | GNN Energy Model   |          | Optimizer          |
    | (Ensemble of:      |<-------->| (Hybrid strategy:  |
    |  MEGNet, CGCNN,    |  energy  |  CMA-ES for        |
    |  ALIGNN, M3GNet)   |  score   |  continuous params,|
    |                    |          |  GA for discrete    |
    +--------------------+          |  space group)       |
                                    +----------+---------+
                                               |
                                    +----------v---------+
                                    | Constraint Filter  |
                                    | (symmetry,         |
                                    |  chemistry,        |
                                    |  geometry,         |
                                    |  stability)        |
                                    +----------+---------+
                                               |
                                    +----------v---------+
                                    | Ranking & Output   |
                                    | (top-K structures, |
                                    |  CIF files,        |
                                    |  confidence scores)|
                                    +--------------------+
```

### 4.4 GNN Model Ensemble

Agent PB uses an ensemble of four GNN architectures to predict formation
enthalpy. Ensemble disagreement provides built-in uncertainty quantification.

| Model | Graph Representation | Strengths | Role in Ensemble |
|-------|---------------------|-----------|-----------------|
| **MEGNet** | Global state + node + edge | Broad coverage, pre-trained on MP | Baseline energy predictor |
| **CGCNN** | Crystal graph with Gaussian distance | Fast inference, good for screening | High-throughput filter |
| **ALIGNN** | Atom graph + line graph (bond angles) | Captures angular information | Geometry-sensitive correction |
| **M3GNet** | Multi-body interactions, universal potential | Forces + stress + energy | Relaxation surrogate |

**Ensemble Strategy**:
```python
def ensemble_predict(structure: Structure) -> Tuple[float, float]:
    """Returns (mean_energy, uncertainty)."""
    predictions = [model.predict(structure) for model in self.models]
    mean_energy = np.mean(predictions)
    uncertainty = np.std(predictions)
    return mean_energy, uncertainty
```

**Confidence Threshold**: Structures with ensemble uncertainty > 0.15 eV/atom
are flagged for DFT validation and excluded from final rankings.

### 4.5 Optimization Pipeline

The v2.0 optimizer uses a **hybrid multi-stage** strategy:

**Stage 1 — Coarse Search (Genetic Algorithm)**
- Discrete space: enumerate space groups, Wyckoff combinations
- Population: 500, generations: 100
- Fitness: ensemble energy prediction
- Selects top-50 (space group, Wyckoff template) candidates

**Stage 2 — Fine Optimization (CMA-ES)**
- Continuous space: lattice parameters (a, b, c, alpha, beta, gamma) +
  fractional coordinates (x, y, z per free Wyckoff site)
- Per candidate from Stage 1
- Sigma_init: 0.1 (relative to parameter range)
- Max evaluations: 2000 per candidate
- Constraint handling: penalty function for geometry violations

**Stage 3 — Local Relaxation (M3GNet)**
- Gradient-based relaxation of top-10 structures from Stage 2
- FIRE algorithm, fmax = 0.01 eV/A
- Produces final optimized coordinates

### 4.6 Input / Output

**Input**:
```json
{
  "chemical_formula": "Ca4S4",
  "space_group_range": [2, 230],
  "lattice_bounds": {
    "a": [2, 30], "b": [2, 30], "c": [2, 30],
    "alpha": [20, 160], "beta": [20, 160], "gamma": [20, 160]
  },
  "optimization": {
    "algorithm": "hybrid",
    "ga_population": 500,
    "ga_generations": 100,
    "cmaes_max_evals": 2000,
    "relax_fmax": 0.01
  },
  "gnn_models": ["megnet", "cgcnn", "alignn", "m3gnet"],
  "top_k": 10
}
```

**Output**:
```json
{
  "agent": "agent_pb",
  "version": "2.0",
  "formula": "Ca4S4",
  "timestamp": "2026-03-17T14:00:00Z",
  "predictions": [
    {
      "rank": 1,
      "structure_id": "pb_Ca4S4_001",
      "space_group": 225,
      "space_group_symbol": "Fm-3m",
      "lattice": {"a": 5.69, "b": 5.69, "c": 5.69, "alpha": 90, "beta": 90, "gamma": 90},
      "formation_energy_eV_atom": -1.842,
      "energy_uncertainty_eV_atom": 0.023,
      "energy_above_hull_eV_atom": 0.0,
      "confidence": 0.97,
      "cif_path": "data/predictions/agent_pb/Ca4S4/rank_001.cif",
      "wyckoff_sites": [
        {"element": "Ca", "site": "4a", "x": 0.0, "y": 0.0, "z": 0.0},
        {"element": "S", "site": "4b", "x": 0.5, "y": 0.5, "z": 0.5}
      ]
    }
  ],
  "search_statistics": {
    "total_structures_evaluated": 52340,
    "stage1_candidates": 50,
    "stage2_candidates": 10,
    "wall_time_seconds": 3420,
    "convergence_history": [...]
  }
}
```

### 4.7 Performance Targets

| Metric | Definition | Target |
|--------|-----------|--------|
| **Structure match rate** | Fraction of known structures correctly recovered (StructureMatcher, ltol=0.2, stol=0.3, angle_tol=5) | >= 99% on MatBench test set |
| **Space group accuracy** | Correct space group in top-1 prediction | >= 95% |
| **Energy MAE** | Mean absolute error of formation energy vs DFT | <= 0.05 eV/atom |
| **RMSD** | Root mean square distance of predicted vs true atomic positions (after alignment) | <= 0.15 A |
| **Wall time** | Time to predict one structure (8-atom cell, single GPU) | <= 30 minutes |
| **Fingerprint distance** | CrystalNN structure fingerprint cosine distance | <= 0.05 |

### 4.8 Comparison Framework

Agent PB includes a benchmarking harness that evaluates any prediction agent
against a reference dataset:

```python
# benchmarks/run_benchmark.py
class AgentBenchmark:
    """Compare structure prediction agents on standardized datasets."""

    DATASETS = {
        "matbench_mp_e_form": "Formation energy prediction (132k structures)",
        "matbench_mp_gap": "Band gap prediction (106k structures)",
        "csp_50": "Crystal structure prediction benchmark (50 known structures)",
        "supercon_24": "Superconductor reference set (24 structures from Agent Ob)",
    }

    METRICS = {
        "match_rate": structure_match_rate,      # pymatgen StructureMatcher
        "space_group_accuracy": sg_accuracy,     # Exact SG match
        "rmsd": atomic_rmsd,                     # After optimal alignment
        "energy_mae": energy_mae,                # vs DFT reference
        "fingerprint_distance": fp_distance,     # CrystalNN fingerprint
        "wall_time": wall_time,                  # Seconds per structure
    }

    def compare(self, agents: List[str], dataset: str) -> pd.DataFrame:
        """Run all agents on dataset, return metrics comparison table."""
        ...
```

**Output**: `data/benchmarks/comparison_{dataset}_{timestamp}.csv`

| Agent | Match Rate | SG Acc. | RMSD (A) | Energy MAE | FP Dist. | Time (s) |
|-------|-----------|---------|----------|-----------|---------|---------|
| Agent PB v2.0 | 0.990 | 0.960 | 0.12 | 0.04 | 0.03 | 1800 |
| Crystal Agent v2 | 0.985 | 0.940 | 0.14 | 0.06 | 0.05 | 45 |
| Agent XC | 0.920 | 0.880 | 0.18 | N/A | 0.08 | 20 |

---

## 5. Crystal Agent Improvement — Convergence to 99% Accuracy

### 5.1 Current State (v1.0)

The existing multi-agent loop (CS -> Sin -> Ob) achieves a convergence target
of **95%** across 7 weighted components. The v1.0 system is fully functional
with 6 agents:

| Agent | File | Lines | Status |
|-------|------|-------|--------|
| CS (Crystal Structure) | `src/agents/agent_cs.py` | ~800 | Production |
| Sin (Simulation) | `src/agents/agent_sin.py` | ~500 | Production |
| Ob (Observator) | `src/agents/agent_ob.py` | ~700 | Production |
| P (Pressure) | `src/agents/agent_p.py` | ~300 | Production |
| GCD (Prediction) | `src/agents/agent_gcd.py` | ~350 | Production |
| CB (Crystal Building) | `src/agents/agent_cb.py` | ~600 | Production |

### 5.2 Gap Analysis: 95% -> 99%

The 4-point gap decomposes across the 7 convergence components:

| Component | Weight | v1.0 Typical | v2.0 Target | Gap | Root Cause |
|-----------|--------|-------------|-------------|-----|-----------|
| Tc distribution | 30% | 0.92 | 0.99 | 0.07 | Limited family-specific λ models |
| Lattice accuracy | 25% | 0.96 | 0.99 | 0.03 | Gaussian noise too coarse |
| Space group | 15% | 0.98 | 1.00 | 0.02 | Some families undersampled |
| Electronic match | 15% | 0.90 | 0.98 | 0.08 | λ estimation is empirical |
| Composition validity | 10% | 0.97 | 1.00 | 0.03 | Missing charge balance for hydrides |
| Coordination geometry | 5% | 0.99 | 1.00 | 0.01 | Adequate |
| Pressure-Tc | 13% | 0.88 | 0.98 | 0.10 | Anomalous η poorly handled |

### 5.3 Proposed Enhancements

#### 5.3.1 Agent CS Improvements

**A. Data Source Expansion**
- Integrate Materials Project API (mp-api) for real-time lattice parameter
  retrieval instead of hardcoded seed patterns
- Add AFLOW database queries for Wyckoff prototype matching
- Increase seed patterns from 12 to 50+ (covering all ICSD-reported
  superconductor prototypes)

**B. ML-Augmented Pattern Cards**
- Train a Random Forest on NEMAD features to predict optimal lattice
  parameters per family, replacing fixed seed values
- Add uncertainty bounds to each pattern card parameter

```python
# Enhanced pattern card with ML-predicted bounds
{
  "pattern_id": "cuprate-layered-v2",
  "lattice_params": {
    "a": {"mean": 3.85, "std": 0.08, "source": "ml_nemad_rf"},
    "c": {"mean": 13.2, "std": 0.5, "source": "ml_nemad_rf"}
  },
  "electronic_features": {
    "electron_phonon_lambda": {"mean": 2.1, "std": 0.3, "model": "alignn_lambda"}
  }
}
```

#### 5.3.2 Agent Sin Improvements

**A. Replace Empirical Lambda with ML Surrogate**
- Train ALIGNN model on electron-phonon coupling dataset
  (EPW-calculated λ values from Materials Project phonon database)
- Expected improvement: electronic match component 0.90 -> 0.97

**B. Structure-Aware Generation**
- Replace random Gaussian perturbation with learned displacement vectors
- Use a conditional variational autoencoder (CVAE) trained on known
  structures within each family
- Generate structures that respect symmetry constraints by construction

**C. Adaptive Noise Schedule**
- Start with large perturbations (exploration) and anneal to small
  perturbations (exploitation) as iterations progress
- Noise scale: sigma(iter) = sigma_0 * exp(-iter / tau), tau = 5

#### 5.3.3 Agent Ob Improvements

**A. Expanded Reference Database**
- Increase from 24 to 200+ reference superconductors
- Include non-superconducting materials as negative examples
- Per-family sample size >= 15 (currently some families have 2-3)

**B. Distribution-Aware Scoring**
- Replace point-estimate Wasserstein distance with kernel density
  estimation (KDE) overlap integral
- Use bootstrapped confidence intervals on each component score

**C. Smarter Refinement Targeting**
- Currently: proportional correction ("reduce Tc by 15%")
- v2.0: gradient-informed correction using sensitivity analysis
  (how much does each Sin parameter affect each Ob component?)

#### 5.3.4 Agent P Improvements

**A. Anharmonic Corrections**
- Add 4th-order Birch-Murnaghan EOS for high-pressure regime (>100 GPa)
- Include thermal expansion anharmonicity (beyond quasi-harmonic)

**B. Phase Transition Detection**
- Flag structural phase transitions (volume discontinuities in P-V curve)
- Automatically split pressure scans at transition boundaries

### 5.4 Comparison with Agent PB

To identify strengths and weaknesses, the Crystal Agent and Agent PB are
evaluated on the same reference structures:

```
Crystal Agent strengths:
  - Physics-informed (Allen-Dynes, Birch-Murnaghan, Gruneisen)
  - Handles pressure dependence natively
  - Iterative self-improvement via feedback loop
  - Generates multiple candidates per family simultaneously
  - Fast: ~2.5 seconds per iteration

Crystal Agent weaknesses:
  - Empirical λ estimation (no direct phonon calculation)
  - Limited to superconductor families
  - Perturbation-based generation (not truly ab initio)

Agent PB strengths:
  - Direct energy minimization via GNN
  - General-purpose (any composition, not limited to superconductors)
  - Finds global minimum structures (not perturbations of templates)
  - Ensemble uncertainty quantification

Agent PB weaknesses:
  - Slow (minutes to hours per structure)
  - No property prediction beyond energy
  - No iterative refinement
  - Requires trained GNN models
```

**Complementary Usage**: Run Agent PB for high-confidence structure prediction,
then feed its output into the Crystal Agent loop for property enrichment
(Tc, λ, pressure response). This hybrid approach targets 99%+ accuracy on
both structure and property prediction.

### 5.5 Updated Convergence Weights (v2.0)

```python
SCORE_WEIGHTS_V2 = {
    "tc_distribution": 0.25,        # was 0.30 — reduced, now more precise
    "lattice_accuracy": 0.22,       # was 0.25
    "space_group": 0.13,            # was 0.15
    "electronic_match": 0.18,       # was 0.15 — increased, key differentiator
    "composition_validity": 0.08,   # was 0.10
    "coordination_geometry": 0.04,  # was 0.05
    "pressure_tc": 0.10,            # was 0.13 — reduced after improvements
}
```

---

## 6. Agent V — Visualization Agent

### 6.1 Purpose

Agent V provides real-time visual feedback for all prediction and analysis
agents. It generates CIF files, renders interactive 3D crystal structures, and
displays live progress dashboards.

### 6.2 Directory Structure

```
agent_v/
├── __init__.py
├── dashboard.py                # Main Dash/Plotly application
├── config.py                   # Visualization configuration
├── cif/
│   ├── __init__.py
│   ├── generator.py            # Full CIF generation from crystal models
│   ├── parser.py               # CIF parsing and validation
│   └── templates/              # CIF template files per space group
├── viewers/
│   ├── __init__.py
│   ├── structure_viewer.py     # 3D crystal structure (three.js / py3Dmol)
│   ├── unit_cell_viewer.py     # Unit cell with bonds and polyhedra
│   ├── supercell_viewer.py     # Supercell expansion viewer
│   └── animation_viewer.py     # Structural transition animations
├── editors/
│   ├── __init__.py
│   ├── atom_editor.py          # Add/remove/move atoms
│   ├── lattice_editor.py       # Modify lattice parameters
│   └── symmetry_editor.py      # Apply/change space group
├── monitors/
│   ├── __init__.py
│   ├── convergence_monitor.py  # Real-time convergence score tracking
│   ├── agent_status_monitor.py # Per-agent progress and state
│   └── candidate_monitor.py    # Novel candidate discovery feed
├── exporters/
│   ├── __init__.py
│   ├── cif_export.py           # CIF file export
│   ├── poscar_export.py        # VASP POSCAR export
│   ├── xyz_export.py           # XYZ format export
│   ├── png_export.py           # High-resolution structure images
│   └── pdf_report.py           # PDF summary report generation
└── static/
    ├── css/
    ├── js/
    └── assets/
```

### 6.3 CIF Generation Module

Agent V generates **standard-compliant CIF files** (IUCr CIF 1.1 / CIF 2.0)
from any crystal model in the system.

**Input Sources**:
- Agent CB `crystal_card.json` output
- Agent PB predicted structures
- Agent XC reconstructed structures
- User-uploaded partial structures

**CIF Fields Generated**:

```
data_<structure_id>
_symmetry_space_group_name_H-M   '<space_group_symbol>'
_symmetry_Int_Tables_number      <space_group_number>
_cell_length_a                   <a>
_cell_length_b                   <b>
_cell_length_c                   <c>
_cell_angle_alpha                <alpha>
_cell_angle_beta                 <beta>
_cell_angle_gamma                <gamma>
_cell_volume                     <volume>
_cell_formula_units_Z            <Z>
_chemical_formula_sum            '<formula>'

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
_atom_site_U_iso_or_equiv
<atom_data>
```

**Validation**: Every generated CIF is validated against pymatgen's
`CifParser` before export. Invalid files raise `CIFValidationError`.

### 6.4 Interactive Dashboard

The dashboard is a Plotly Dash application with four main panels:

```
+------------------------------------------------------------------+
| Agent V Dashboard                               [Export] [Config] |
+------------------------------------------------------------------+
|                    |                                               |
|  Structure Viewer  |   Convergence Monitor                        |
|  (3D interactive)  |   [Line chart: score vs iteration]           |
|                    |   [Bar chart: 7 component scores]            |
|  - Rotate/zoom     |   [Progress: iteration 12/20, score 0.974]  |
|  - Select atoms    |                                               |
|  - Measure dist.   +-----------------------------------------------+
|  - Toggle bonds    |                                               |
|  - Show polyhedra  |   Agent Status Panel                         |
|  - Supercell NxNxN |   [CS: idle] [Sin: running iter 13]         |
|                    |   [Ob: waiting] [P: complete]                |
+--------------------+   [PB: running 2340/5000 evals]              |
|                    |   [XC: idle]                                  |
|  Candidate Feed    |                                               |
|  [Table: top-10    +-----------------------------------------------+
|   novel candidates |                                               |
|   with Tc, stab.,  |   Property Explorer                          |
|   family, conf.]   |   [Scatter: Tc vs lambda, colored by family] |
|                    |   [Histogram: formation energy distribution]  |
|  [Click to view    |   [Heatmap: element co-occurrence in top-50] |
|   structure above] |                                               |
+--------------------+-----------------------------------------------+
```

**Technology Stack**:
- **Backend**: Python Dash (Plotly) on Flask
- **3D Viewer**: py3Dmol (Jupyter-compatible) or Crystal Toolkit (pymatgen)
- **Charts**: Plotly.js (interactive scatter, line, bar, heatmap)
- **Real-time**: Dash intervals polling `data/` directory for updates

### 6.5 Structure Editing

The editor module allows interactive modification of crystal structures:

| Action | Implementation | Constraint Check |
|--------|---------------|-----------------|
| Move atom | Drag fractional coordinates | Min distance validation |
| Add atom | Click position + element selector | Charge neutrality recalculated |
| Remove atom | Select + delete | Stoichiometry warning |
| Change lattice | Slider for a, b, c, alpha, beta, gamma | Volume bounds check |
| Apply symmetry | Space group dropdown | Wyckoff compatibility |
| Animate | Interpolate between two structures | Frame-by-frame CIF sequence |

**Edit -> Re-predict workflow**: After manual edits, the user can re-submit
the modified structure to Agent PB or the Crystal Agent for energy evaluation
and property prediction.

### 6.6 Animation Capabilities

- **Convergence animation**: Animate structural evolution across iterations
  (morph between iteration 0 and final structure)
- **Pressure sweep**: Animate lattice compression under increasing pressure
  (from Agent P pressure scan data)
- **Phonon modes**: Visualize atomic displacement patterns for key phonon modes
  (requires phonon eigenvector data from ML potential)
- **Phase transition**: Show before/after structures at phase boundaries

### 6.7 Data Inputs / Outputs

**Inputs** (watched directories):
- `data/crystal_structures/*/structure.cif` — Agent CB outputs
- `data/predictions/agent_pb/*/rank_*.cif` — Agent PB predictions
- `data/predictions/agent_xc/*/predicted.cif` — Agent XC reconstructions
- `data/refinements/iteration_*.json` — Convergence scores
- `data/novel_candidates/candidates_iteration_*.csv` — Discovery feed
- `data/reports/final_report.json` — Pipeline completion status

**Outputs**:
- `data/exports/structures/*.cif` — Edited/exported CIF files
- `data/exports/images/*.png` — High-resolution structure images
- `data/exports/reports/*.pdf` — PDF summary reports
- `data/exports/animations/*.gif` — Structure animation GIFs

---

## 7. Agent XC — XRD End-to-End Prediction Agent

### 7.1 Overview

Agent XC (X-ray Crystallography) performs **end-to-end crystal structure
prediction from experimental powder X-ray diffraction (PXRD) data**. It is
built on top of the XtalNet framework (`xtalnet/`) which implements a
two-stage pipeline:

1. **CPCP Module**: Composition + Powder pattern -> Composition + Crystal properties
2. **CCSG Module**: Crystal properties -> Complete crystal structure (3D coordinates)

### 7.2 Foundation: XtalNet Architecture

From the paper "End-to-End Crystal Structure Prediction from Powder X-Ray
Diffraction" (Lai et al., Advanced Science 2025):

```
Experimental PXRD Pattern (2theta, intensity)
            |
            v
+------------------------+
| CPCP Module            |
| (Transformer encoder)  |
| - BertModel backbone   |
| - Multihead attention  |
| - Sinusoidal distance  |
|   embeddings           |
+--------+---------------+
         |
         | Predicted: composition, lattice params,
         |            space group, # atoms
         v
+------------------------+
| CCSG Module            |
| (CSPNet generator)     |
| - Graph neural network |
| - CSP layers with      |
|   distance embeddings  |
| - Iterative refinement |
+--------+---------------+
         |
         v
  Predicted Crystal Structure (CIF)
```

**Pre-trained Checkpoints**: `xtalnet/ckpt/` (HMOF-100 and HMOF-400 models)

### 7.3 Agent XC Directory Structure

```
agent_xc/
├── __init__.py
├── predict.py                  # Main entry point
├── config.py                   # Agent configuration
├── preprocessing/
│   ├── __init__.py
│   ├── xrd_reader.py           # Read .xy, .csv, .raw, .xrdml formats
│   ├── background_subtract.py  # Polynomial background removal
│   ├── peak_finder.py          # Peak detection (scipy find_peaks)
│   ├── normalizer.py           # Intensity normalization (0-1 scaling)
│   ├── interpolator.py         # Resample to fixed 2theta grid
│   └── noise_filter.py         # Savitzky-Golay smoothing
├── xtalnet_bridge/
│   ├── __init__.py
│   ├── cpcp_wrapper.py         # Wraps xtalnet CPCP module
│   ├── ccsg_wrapper.py         # Wraps xtalnet CCSG module
│   ├── model_loader.py         # Load pre-trained checkpoints
│   └── inference.py            # End-to-end inference pipeline
├── postprocessing/
│   ├── __init__.py
│   ├── structure_refiner.py    # Rietveld-like refinement of predicted structure
│   ├── xrd_simulator.py        # Simulate XRD from predicted structure (for comparison)
│   ├── match_scorer.py         # Compare predicted vs input XRD pattern
│   └── cif_writer.py           # Write validated CIF output
├── evaluation/
│   ├── __init__.py
│   ├── metrics.py              # Rwp, Rp, chi-squared, match rate
│   └── benchmark.py            # Evaluate on reference datasets
└── tests/
    ├── test_preprocessing.py
    ├── test_inference.py
    └── test_postprocessing.py
```

### 7.4 Data Pipeline

```
Raw XRD File (.xy / .csv / .raw / .xrdml)
    |
    v
[1] Preprocessing
    - Format detection and parsing
    - Background subtraction (Sonneveld-Visser or polynomial fit)
    - Kalpha2 stripping (if dual-wavelength)
    - Noise filtering (Savitzky-Golay, window=11, polyorder=3)
    - Normalization to [0, 1] intensity range
    - Resampling to fixed grid: 2theta = 5-90 deg, step = 0.02 deg
    |
    v
[2] Feature Extraction (CPCP Module)
    - Input: 1D diffraction pattern (4250 intensity values)
    - Optional: composition hint (chemical formula)
    - Transformer encoder predicts:
      * Chemical composition (element types + stoichiometry)
      * Lattice parameters (a, b, c, alpha, beta, gamma)
      * Space group number (1-230)
      * Number of atoms in unit cell
    - Confidence scores for each prediction
    |
    v
[3] Structure Generation (CCSG Module)
    - Input: CPCP predictions (composition + lattice + space group)
    - CSPNet graph neural network generates:
      * Fractional coordinates for each atom
      * Site occupancies
    - Multiple candidate structures generated (num_evals configurable)
    |
    v
[4] Postprocessing & Validation
    - Simulate XRD pattern from each predicted structure
    - Compare simulated vs input experimental pattern
    - Score by Rwp (weighted profile R-factor):
      Rwp = sqrt( sum[w_i(y_obs_i - y_calc_i)^2] / sum[w_i * y_obs_i^2] )
    - Rank candidates by Rwp (lower is better)
    - Optional: Rietveld-like coordinate refinement to minimize Rwp
    |
    v
[5] Output
    - Best-match CIF file
    - Comparison plot (observed vs calculated XRD pattern)
    - Confidence metrics (Rwp, Rp, match rate)
    - JSON summary with all predictions and scores
```

### 7.5 Input Specification

**Primary Input**: Experimental PXRD pattern file

Supported formats:
| Format | Extension | Description |
|--------|-----------|-------------|
| XY | `.xy`, `.dat` | Two-column text (2theta, intensity) |
| CSV | `.csv` | Comma-separated with header |
| Bruker RAW | `.raw` | Binary Bruker diffractometer format |
| PANalytical XRDML | `.xrdml` | XML format from PANalytical instruments |

**Optional Inputs**:
- `composition_hint`: Chemical formula (e.g., "Cu2H8C28N6O8") — improves accuracy
- `wavelength`: X-ray wavelength in Angstroms (default: 1.5406 Cu Kalpha1)
- `two_theta_range`: Override default [5, 90] degree range
- `num_candidates`: Number of structure candidates to generate (default: 10)

### 7.6 Output Specification

```json
{
  "agent": "agent_xc",
  "version": "1.0",
  "input_file": "experimental_pattern.xy",
  "wavelength_angstrom": 1.5406,
  "predictions": [
    {
      "rank": 1,
      "composition": "Cu2H8C28N6O8",
      "space_group": 14,
      "space_group_symbol": "P2_1/c",
      "lattice": {
        "a": 8.234, "b": 11.567, "c": 7.891,
        "alpha": 90.0, "beta": 102.3, "gamma": 90.0
      },
      "num_atoms": 52,
      "rwp": 0.043,
      "rp": 0.031,
      "confidence": 0.92,
      "cif_path": "data/predictions/agent_xc/pattern_001/rank_001.cif",
      "xrd_comparison_plot": "data/predictions/agent_xc/pattern_001/comparison_001.png"
    }
  ],
  "cpcp_predictions": {
    "composition_accuracy": 0.95,
    "lattice_mae": {"a": 0.12, "b": 0.08, "c": 0.15},
    "space_group_top1_accuracy": 0.88,
    "space_group_top5_accuracy": 0.96
  },
  "processing_time_seconds": 18.5
}
```

### 7.7 Performance Targets

| Metric | Definition | Target |
|--------|-----------|--------|
| **Composition accuracy** | Fraction of elements correctly identified from XRD alone | >= 90% |
| **Space group top-1** | Correct space group in highest-ranked prediction | >= 85% |
| **Space group top-5** | Correct space group in top-5 predictions | >= 95% |
| **Lattice MAE** | Mean absolute error of lattice parameters (A / degrees) | a,b,c: <= 0.2 A; angles: <= 2 deg |
| **Rwp** | Weighted profile R-factor (simulated vs observed XRD) | <= 0.10 (10%) |
| **Structure match** | StructureMatcher success rate (ltol=0.3, stol=0.5) | >= 80% |
| **Inference time** | Wall time per structure (V100 GPU) | <= 20 seconds |

### 7.8 Integration with Other Agents

**Agent XC -> Agent V**: Predicted CIF files are automatically detected by
Agent V's file watcher and rendered in the dashboard. The XRD comparison plot
(observed vs calculated) is displayed alongside the 3D structure.

**Agent XC -> Agent PB**: When Agent XC's confidence is low (Rwp > 0.15),
the predicted composition and approximate lattice are forwarded to Agent PB
for energy-based structure refinement. Agent PB uses the XC output as an
informed starting point rather than searching from scratch.

**Agent XC -> Crystal Agent**: For superconductor candidates, Agent XC's
predicted structures are fed into the Crystal Agent loop for Tc estimation
and property enrichment.

```
Experimental XRD
      |
      v
  Agent XC (structure from diffraction)
      |
      +---> Agent V (visualize)
      |
      +---> Agent PB (refine structure if low confidence)
      |
      +---> Crystal Agent (predict Tc, lambda if superconductor)
```

---

## 8. Cross-Agent Integration & Data Flow

### 8.1 Master Data Flow Diagram

```
                    User Input
                        |
            +-----------+-----------+
            |                       |
     Chemical Formula          XRD Pattern
            |                       |
            v                       v
    +-------+--------+     +-------+--------+
    | Skill v2.0     |     | Skill v2.0     |
    | Intent Router  |     | Intent Router  |
    +--+----+----+---+     +-------+--------+
       |    |    |                  |
       v    |    v                  v
  Agent PB  | Crystal Agent    Agent XC
       |    |    |                  |
       |    |    v                  |
       |    | CS->Sin->Ob->P       |
       |    |    |                  |
       |    |    v                  |
       |    +->GCD->CB             |
       |         |                  |
       +----+----+----+------------+
            |         |
            v         v
        Agent V    Benchmark
        (Dashboard)  Framework
            |
            v
     CIF / PDF / Dashboard
```

### 8.2 Shared Data Contracts

All agents communicate via these standardized formats:

| Format | Schema | Used By | Direction |
|--------|--------|---------|-----------|
| Pattern Card (JSON) | `schemas/pattern_card.json` | CS -> Sin, CS -> CB | Internal |
| Refinement Report (JSON) | `schemas/refinement_report.json` | Ob -> CS, Ob -> Sin | Internal |
| Synthetic Metadata (JSON) | `schemas/synthetic_metadata.json` | Sin -> Ob | Internal |
| CIF File | IUCr CIF 1.1 | PB, XC, CB -> V | Output |
| Properties CSV | Columns: structure_id, composition, Tc, lambda, stability, ... | Sin, GCD -> Ob, V | Internal |
| XRD Pattern (.xy) | Two-column: 2theta, intensity | External -> XC | Input |
| Benchmark Results (CSV) | Columns: agent, metric, value, dataset | Benchmark -> V | Internal |
| Execution Plan (JSON) | Skill v2.0 schema | Skill -> All agents | Control |

### 8.3 Agent Interaction Matrix

```
              CS    Sin    Ob     P     GCD    CB    PB    XC    V
  CS          -     data   ref    -     -      -     -     -     mon
  Sin         pat   -      data   pres  -      -     -     -     mon
  Ob          ref   ref    -      -     -      -     -     -     mon
  P           -     phys   -      -     -      -     -     -     -
  GCD         -     -      cand   -     -      data  -     -     mon
  CB          -     -      -      -     pred   -     -     -     data
  PB          -     -      -      -     -      -     -     seed  data
  XC          -     -      -      -     -      -     seed  -     data
  V           -     -      -      -     -      -     -     -     -

  Legend: data = structural data, pat = pattern cards, ref = refinements,
          pres = pressure calculations, cand = novel candidates,
          pred = GCD predictions, phys = physics parameters,
          seed = initial structure seed, mon = monitoring data
```

---

## 9. Performance Benchmarking Framework

### 9.1 Reference Datasets

| Dataset | Size | Source | Purpose |
|---------|------|--------|---------|
| **CSP-50** | 50 structures | Hand-curated from ICSD | Primary structure prediction benchmark |
| **SuperCon-24** | 24 structures | Agent Ob hardcoded references | Superconductor-specific validation |
| **MatBench-EForm** | 132,752 | Materials Project | Energy prediction accuracy |
| **HMOF-100** | 100 structures | XtalNet dataset | XRD-to-structure benchmark |
| **HMOF-400** | 400 structures | XtalNet dataset | Extended XRD benchmark |
| **QMDB** | ~1M entries | `qmdb__v1_8__022026.sql.gz` | Large-scale validation (Agent PB) |

### 9.2 Evaluation Metrics

```python
METRIC_DEFINITIONS = {
    # Structure prediction metrics
    "match_rate": {
        "description": "Fraction of structures matched by StructureMatcher",
        "implementation": "pymatgen.analysis.structure_matcher.StructureMatcher",
        "parameters": {"ltol": 0.2, "stol": 0.3, "angle_tol": 5},
        "target": {"agent_pb": 0.99, "crystal_agent": 0.99, "agent_xc": 0.80}
    },
    "rmsd": {
        "description": "Root mean square displacement after optimal alignment",
        "implementation": "pymatgen StructureMatcher.get_rms_dist",
        "unit": "Angstrom",
        "target": {"agent_pb": 0.15, "crystal_agent": 0.20, "agent_xc": 0.30}
    },
    "space_group_accuracy": {
        "description": "Fraction with correct space group (exact match)",
        "target": {"agent_pb": 0.95, "crystal_agent": 0.95, "agent_xc": 0.85}
    },
    "energy_mae": {
        "description": "Mean absolute error of formation energy vs DFT",
        "unit": "eV/atom",
        "target": {"agent_pb": 0.05, "crystal_agent": 0.10}
    },

    # XRD-specific metrics (Agent XC)
    "rwp": {
        "description": "Weighted profile R-factor",
        "formula": "sqrt(sum[w*(y_obs-y_calc)^2] / sum[w*y_obs^2])",
        "target": {"agent_xc": 0.10}
    },
    "composition_accuracy": {
        "description": "Fraction of elements correctly identified from XRD",
        "target": {"agent_xc": 0.90}
    },

    # Superconductor-specific metrics (Crystal Agent)
    "tc_mae": {
        "description": "Mean absolute error of Tc prediction",
        "unit": "Kelvin",
        "target": {"crystal_agent": 5.0}
    },
    "convergence_score": {
        "description": "7-component weighted convergence (v1.0 metric)",
        "target": {"crystal_agent": 0.99}
    },

    # Efficiency metrics
    "wall_time": {
        "description": "Wall clock time per structure prediction",
        "unit": "seconds",
        "target": {"agent_pb": 1800, "crystal_agent": 2.5, "agent_xc": 20}
    }
}
```

### 9.3 Benchmark Execution

```bash
# Compare all agents on CSP-50 dataset
python -m benchmarks.compare_agents \
    --dataset csp_50 \
    --agents agent_pb crystal_agent agent_xc \
    --metrics match_rate rmsd space_group_accuracy wall_time \
    --output data/benchmarks/comparison_csp50.csv

# Agent PB vs Crystal Agent on superconductor structures
python -m benchmarks.compare_agents \
    --dataset supercon_24 \
    --agents agent_pb crystal_agent \
    --metrics match_rate tc_mae convergence_score \
    --output data/benchmarks/comparison_supercon.csv

# Agent XC on HMOF datasets
python -m benchmarks.compare_agents \
    --dataset hmof_100 hmof_400 \
    --agents agent_xc \
    --metrics rwp composition_accuracy match_rate \
    --output data/benchmarks/comparison_xrd.csv
```

### 9.4 Automated Regression Testing

Every code change triggers benchmark re-evaluation on CSP-50:

```python
# tests/test_benchmark_regression.py
def test_agent_pb_accuracy_regression():
    results = run_benchmark("agent_pb", "csp_50")
    assert results["match_rate"] >= 0.98, \
        f"Agent PB match rate regressed: {results['match_rate']}"

def test_crystal_agent_convergence_regression():
    results = run_benchmark("crystal_agent", "supercon_24")
    assert results["convergence_score"] >= 0.98, \
        f"Crystal Agent convergence regressed: {results['convergence_score']}"

def test_agent_xc_rwp_regression():
    results = run_benchmark("agent_xc", "hmof_100")
    assert results["rwp"] <= 0.12, \
        f"Agent XC Rwp regressed: {results['rwp']}"
```

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

| Week | Task | Deliverable | Owner |
|------|------|-------------|-------|
| 1 | Create `CLAUDE.md`, project restructuring | `CLAUDE.md`, updated directory layout | Lead |
| 1 | Set up benchmark framework | `benchmarks/compare_agents.py`, CSP-50 dataset | ML Eng |
| 2 | Refactor Agent PB into modular package | `agent_pb/` package with MEGNet wrapper | ML Eng |
| 2 | Agent V scaffold with CIF generator | `agent_v/cif/generator.py`, basic Dash app | Frontend |
| 3 | Add CGCNN and ALIGNN models to Agent PB | `agent_pb/gnn/cgcnn_model.py`, `alignn_model.py` | ML Eng |
| 3 | Agent XC preprocessing pipeline | `agent_xc/preprocessing/` complete | ML Eng |
| 4 | Agent PB hybrid optimizer (GA + CMA-ES) | `agent_pb/optimizer/hybrid_optimizer.py` | ML Eng |
| 4 | Agent V 3D structure viewer | `agent_v/viewers/structure_viewer.py` | Frontend |

### Phase 2: Core Development (Weeks 5-10)

| Week | Task | Deliverable | Owner |
|------|------|-------------|-------|
| 5 | Agent PB ensemble prediction + uncertainty | `agent_pb/gnn/ensemble.py` | ML Eng |
| 5 | Agent XC XtalNet bridge (CPCP + CCSG) | `agent_xc/xtalnet_bridge/` complete | ML Eng |
| 6 | Crystal Agent v2 enhancements (CS, Sin, Ob) | Updated `src/agents/` with ML-augmented patterns | ML Eng |
| 6 | Agent V convergence dashboard | `agent_v/monitors/convergence_monitor.py` | Frontend |
| 7 | Agent PB M3GNet relaxation stage | `agent_pb/gnn/m3gnet_model.py` integration | ML Eng |
| 7 | Agent XC postprocessing (Rietveld, XRD sim) | `agent_xc/postprocessing/` complete | ML Eng |
| 8 | Cross-agent integration testing | Integration tests, data flow validation | All |
| 8 | Agent V structure editor | `agent_v/editors/` complete | Frontend |
| 9 | Skill v2.0 intent router | `skill_v2/router.py` with 5 execution paths | Lead |
| 10 | Agent V real-time monitoring | `agent_v/monitors/` all monitors | Frontend |

### Phase 3: Optimization & Validation (Weeks 11-16)

| Week | Task | Deliverable | Owner |
|------|------|-------------|-------|
| 11 | Agent PB accuracy tuning (target 99%) | Benchmark results >= 99% on CSP-50 | ML Eng |
| 11 | Crystal Agent v2 convergence tuning | Convergence >= 99% on SuperCon-24 | ML Eng |
| 12 | Agent XC validation on experimental data | Rwp <= 0.10 on HMOF-400 | ML Eng |
| 12 | Full benchmark comparison report | `data/benchmarks/final_comparison.csv` | All |
| 13 | Agent V animation system | Phase transition + pressure sweep animations | Frontend |
| 13 | Skill v2.0 NL intent parsing | Natural language requirement parsing | Lead |
| 14 | End-to-end system testing | Full pipeline from NL input to CIF output | All |
| 15 | Performance optimization | GPU utilization, batch inference, caching | ML Eng |
| 16 | Documentation, deployment scripts | User guide, Docker compose, CI/CD | All |

### Phase 4: Future (Post Week 16)

- Active learning integration (Skill v2.1)
- Multi-objective Pareto optimization (Skill v2.5)
- DFT validation pipeline (VASP/QE integration)
- Experimental synthesis feedback loop
- Cloud deployment (DarkLab cluster integration)
- Conversational material design interface (Skill v3.0)

---

## Appendix A: Dependencies

```
# Core
numpy>=1.24
pandas>=2.0
scipy>=1.10

# ML / Deep Learning
torch>=2.0
pytorch_lightning>=2.0
tensorflow>=2.12
megnet>=1.3

# Materials Science
pymatgen>=2024.1
ase>=3.22
matminer>=0.9

# Optimization
hyperopt>=0.2.7
scikit-opt>=0.6.6
cma>=3.3               # CMA-ES optimizer

# GNN Models
cgcnn                   # Crystal Graph CNN (pip install cgcnn)
alignn>=2024.1          # Atomistic Line Graph NN
m3gnet>=0.2             # M3GNet universal potential
chgnet>=0.3             # CHGNet (alternative universal potential)

# Configuration
hydra-core>=1.3

# Visualization
plotly>=5.18
dash>=2.14
py3Dmol>=2.0
crystal-toolkit>=2023.11
matplotlib>=3.8
seaborn>=0.13

# XRD Processing
lmfit>=1.2              # Curve fitting for Rietveld refinement

# Logging
wandb>=0.16

# Testing
pytest>=7.4
```

## Appendix B: Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 8 cores | 16+ cores (parallel agent execution) |
| RAM | 16 GB | 64 GB (QMDB loading, large datasets) |
| GPU | 1x NVIDIA V100 (16 GB) | 2x A100 (80 GB) or 4x V100 |
| Storage | 100 GB SSD | 500 GB NVMe (QMDB: 21 GB compressed) |
| Network | Optional | Required for Materials Project API queries |

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **ALIGNN** | Atomistic Line Graph Neural Network — GNN that encodes bond angles |
| **CCSG** | Crystal Composition to Structure Generation (XtalNet module) |
| **CGCNN** | Crystal Graph Convolutional Neural Network |
| **CIF** | Crystallographic Information File (IUCr standard) |
| **CMA-ES** | Covariance Matrix Adaptation Evolution Strategy |
| **CPCP** | Composition + Powder to Composition + Crystal Properties (XtalNet module) |
| **CSP** | Crystal Structure Prediction |
| **GN-OA** | Graph Network + Optimization Algorithm (Agent PB foundation) |
| **M3GNet** | Materials 3-body Graph Network (universal potential) |
| **MEGNet** | MatErials Graph Network |
| **PXRD** | Powder X-Ray Diffraction |
| **Rwp** | Weighted profile R-factor (XRD pattern match quality) |
| **Wyckoff** | Crystallographic site symmetry positions within a space group |
