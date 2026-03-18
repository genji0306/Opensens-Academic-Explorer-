# Opensens Academic Explorer (OAE) — Crystal Structure Prediction & Material Discovery Platform

## Project Type
Multi-agent crystal structure prediction and material discovery system (Python 3.11+)

## Directory Structure

```
OAE/
├── oae.py                  # Primary CLI entry point (--rtap, --v2, --protocol)
├── run.py                  # Legacy convergence entry point
├── requirements.txt        # Dependencies
├── README.md               # Project overview + quickstart
├── CLAUDE.md               # AI assistant instructions
│
├── src/                    # v1 Core loop + shared core
│   ├── orchestrator.py     #   Feedback loop controller (CS→Sin→Ob convergence)
│   ├── agents/             #   6 convergence agents (CS, Sin, Ob, P, CB, GCD)
│   └── core/               #   Config, schemas, data registry, NEMAD adapter, Tc models, MC3D client
│
├── agent_pb/               # GNN + optimization crystal structure predictor (19 files)
│   ├── predict.py          #   AgentPB class + CLI
│   ├── gnn/                #   MEGNet + M3GNet + ensemble with UQ
│   ├── optimizer/          #   TPE, PSO, Hybrid optimizers
│   ├── constraints/        #   Symmetry, chemistry, geometry
│   ├── evaluation/         #   Metrics + benchmark harness
│   └── io/                 #   CIF read/write
│
├── agent_xc/               # XRD-to-structure predictor wrapping XtalNet (13 files)
│   ├── predict.py          #   AgentXC class + CLI
│   ├── preprocessing/      #   XRD reader, normalizer, Savitzky-Golay
│   ├── xtalnet_bridge/     #   Model loader + inference pipeline
│   └── postprocessing/     #   XRD simulator, Rwp/Rp scorer
│
├── agent_v/                # Visualization + crystal editing (20 files)
│   ├── dashboard.py        #   Tabbed Dash app: Monitor + Crystal Editor
│   ├── rtap_dashboard.py   #   RTAP exploration dashboard (port 8051)
│   ├── editor/             #   Interactive crystal editor (add/remove/move, undo/redo, CIF round-trip)
│   ├── cif/                #   CIFGenerator (IUCr v2 compliant) + CIFValidator
│   ├── viewers/            #   py3Dmol 3D + matplotlib fallback
│   ├── monitors/           #   Convergence + agent status
│   └── exporters/          #   CIF + PNG export
│
├── skill_v2/               # Intent router + execution planner (4 files)
├── benchmarks/             # Cross-agent comparison + NEMAD study (7 files)
├── laboratory/             # Superagent Laboratory — 6 protocols (11 files)
│
├── tests/                  # 343 passing tests across 18 files
├── schemas/                # JSON schemas (pattern_card, refinement_report, synthetic_metadata)
├── scripts/                # Utility scripts (enhance_cif_files.py)
│
├── data/                   # All intermediate and final outputs (file-based agent IPC)
│   ├── crystal_structures/ #   100 structures (CIF v2 + crystal_card.json + feasibility.json)
│   ├── predictions/        #   Agent predictions by family
│   ├── datasets/           #   6 benchmark datasets (JSON, embedded fallback)
│   ├── laboratory/         #   Protocol execution checkpoints
│   ├── reports/            #   Convergence history, final report, NEMAD comparison
│   ├── experimental/       #   Reference experimental data
│   └── registry.json       #   Unified material registry index
│
├── docs/                   # All documentation (10 files)
│   ├── OAE_PROGRESS_REPORT.md
│   ├── CRYSTAL_AGENTS_V2_SPECIFICATION.md   # Authoritative technical spec
│   ├── SUPERCONDUCTOR_MULTIAGENT_PLAN.md    # Original design plan
│   ├── VISUALIZE_GUIDELINE.md               # 8 static chart templates
│   ├── ANIMATION_GUIDELINE.md               # 8 animated visualization templates
│   ├── SYSTEM_SUMMARY_AND_VISUALS.md
│   ├── MASTER_WORKFLOW.md
│   ├── MAPPING_ANIMATION_AND_WEBPAGE_GUIDE.md
│   ├── VISUALIZATION_INSTRUCTIONS.md
│   └── PROCESS_NOTES.md
│
└── references/             # External/legacy packages (read-only)
    ├── xtalnet/            #   XtalNet CPCP+CCSG models (PyTorch Lightning, ~156 MB checkpoints)
    ├── nemad/              #   NEMAD magnetic materials ML (58K entries, RF/XGBoost models)
    ├── legacy_agent_pb/    #   Legacy GN-OA v0.2 code (MEGNet + Hyperopt/PSO)
    ├── alphafold/          #   AlphaFold 2/3 reference implementations
    └── utils/              #   Utility functions (phonon benchmarks, pressure data, similarity)
```

## Architecture

### v1 Core Loop (fully converged, 11 iterations)
- `src/agents/` — 6 convergence agents: CS (seed patterns), Sin (synthesis), Ob (experimental validation), P (pressure scan), CB (crystal builder), GCD (GCD composition)
- `src/orchestrator.py` — Feedback loop controller (CS->Sin->Ob convergence)
- `src/core/config.py` — Central configuration, paths, convergence weights (v1 + v2 + RTAP)
- `src/core/schemas.py` — Shared dataclasses (PatternCard, CrystalModel, MaterialEntry, etc.)
- `src/core/data_registry.py` — Unified data registry (JSON index at `data/registry.json`)
- `src/core/nemad_adapter.py` — NEMAD CSV adapter (58K magnetic materials -> MaterialEntry format)
- `run.py` / `oae.py` — CLI launchers. `--v2` activates 0.99 target; `--rtap` activates v3 RTAP; `--protocol` runs lab protocols

### v2 Agent Packages (foundation complete)
- `agent_pb/` — GNN + optimization crystal structure predictor (19 files)
  - `predict.py` — AgentPB class, CLI entry point
  - `gnn/` — MEGNetPredictor + M3GNetPredictor (pre-trained via matgl) + GNNEnsemble with uncertainty quantification
  - `optimizer/` — TPEOptimizer, PSOOptimizer, HybridOptimizer (TPE->PSO->M3GNet BFGS relaxation)
  - `constraints/` — Symmetry (Wyckoff), chemistry (charge neutrality), geometry (bond distances)
  - `evaluation/` — Metrics + benchmark harness
  - `io/` — CIF read/write
  - **Gap**: No trained .hdf5 model weights in `references/legacy_agent_pb/NN_model/` — falls back to volume heuristic
- `agent_xc/` — XRD-to-structure predictor wrapping XtalNet (13 files)
  - `predict.py` — AgentXC class, CLI entry point
  - `preprocessing/` — XRD reader (.xy/.csv/.dat), normalizer, Savitzky-Golay filter
  - `xtalnet_bridge/` — Model loader (singleton, Hydra-safe) + inference pipeline
  - `postprocessing/` — XRD simulator (pymatgen), Rwp/Rp match scorer
  - Checkpoints: `references/xtalnet/ckpt/hmof_100/CPCP/*.ckpt`, `CCSG/*.ckpt` (~156 MB each)
- `agent_v/` — Visualization agent (20 files)
  - `dashboard.py` — Tabbed Dash app: Monitor (4-panel) + Crystal Editor
  - `rtap_dashboard.py` — RTAP exploration dashboard: run loop + live animated results (port 8051)
  - `editor/` — Interactive crystal structure editor (add/remove/move atoms, lattice editing, CIF round-trip, undo/redo)
  - `cif/` — CIFGenerator (IUCr v2 compliant: symmetry ops, Wyckoff labels, bond geometry, occupancies) + CIFValidator
  - `viewers/` — py3Dmol 3D viewer with matplotlib fallback
  - `monitors/` — Convergence + agent status monitors
  - `exporters/` — CIF + PNG export
  - `artifact_generator.py` — Structured artifact naming (`{materialtype}_{date}_{round}_{template}.{ext}`) with manifest tracking
- `skill_v2/` — Intent router + execution planner (4 files)
  - `router.py` — IntentRouter: 6 intents (predict_structure, predict_from_xrd, discover_material, discover_rtsc, visualize, benchmark)
  - `executor.py` — PlanExecutor: dispatches to agent run functions with dependency resolution
  - `schemas.py` — ExecutionPlan, ExecutionStep, ExecutionResult dataclasses
- `benchmarks/` — Cross-agent comparison framework (7 files)
  - `compare_agents.py` — AgentBenchmark CLI (supports all 6 datasets, energy pair matching)
  - `datasets.py` — 6 datasets with JSON externalization + embedded fallback
  - `metrics.py` — match_rate, rmsd, energy_mae, rwp, convergence_score, rtap_discovery_score, classification_agreement, temperature_correlation
  - `nemad_comparison.py` — OAE vs NEMAD comparative study (overlap compounds, classification, temperature correlation)
  - `nemad_models.py` — NEMAD model wrapper (RF/XGBoost for Curie/Neel temperature + FM/AFM/NM classification)
- `laboratory/` — Superagent Laboratory module (11 files)
  - `protocol.py` — ProtocolStage, LabProtocol, CheckpointData dataclasses
  - `runner.py` — LabRunner: sequential stage execution with checkpoints and resume
  - `registry.py` — Protocol discovery and lookup
  - `protocols/` — 6 built-in protocols: discovery, structure_prediction, xrd_analysis, magnetic_study, rtap_exploration, verification
  - Runner dispatch: agent_cs, agent_sin, agent_ob, agent_pb, agent_cb, agent_p, agent_xc, agent_v, agent_gcd, nemad

### v3 RTAP Discovery Mode (Room-Temperature Ambient-Pressure)
- `src/core/tc_models.py` — Multi-mechanism Tc estimator (6 models: Allen-Dynes BCS, Migdal-Eliashberg, spin-fluctuation, flat-band, excitonic, hydride-cage)
- `src/core/mc3d_client.py` — Materials Cloud MC3D crystal structure database client (~32K DFT-relaxed structures)
- `src/core/config.py` — RTAP config block (target=0.85, 14 families, 6 score weights)
- 14 RTAP families: cuprate, nickelate, hydride, iron-pnictide, iron-chalcogenide, kagome, ternary-hydride, infinite-layer, topological, 2d-heterostructure, carbon-based, engineered-cuprate, mof-sc, flat-band
- RTAP score weights: ambient_tc (0.30), stability (0.25), synthesizability (0.15), electronic_indicators (0.15), mechanism_plausibility (0.10), composition_validity (0.05)

### References (read-only, under `references/`)
- `references/xtalnet/` — XtalNet CPCP+CCSG models (PyTorch Lightning, pre-trained checkpoints)
- `references/legacy_agent_pb/` — Legacy GN-OA code (MEGNet + Hyperopt/PSO), preserved as-is
- `references/nemad/` — Magnetic material ML models (58K entries: FM Curie temp, AFM Neel temp, FM/AFM/NM classification)
- `references/alphafold/` — AlphaFold 2/3 reference implementations
- `references/utils/` — Utility functions (phonon benchmarks, pressure data, similarity metrics)

## Conventions
- Agents are stateless between iterations; state persists in `data/`
- All crystal data uses pymatgen Structure objects internally
- CIF is the canonical structure exchange format (v2 with symmetry ops, Wyckoff, bonds)
- JSON pattern cards follow `schemas/pattern_card.json`
- Convergence target: v1=0.95, v2=0.99, v3 RTAP=0.85 (no experimental ground truth)
- Damping factor: 0.35 on refinement suggestions (prevents oscillation)
- Heavy optional dependencies (tensorflow, torch, dash) wrapped in try/except ImportError
- All v2 agents follow pattern: class with `run()`, module `run_agent_xxx()`, `main()` for CLI
- `python3` (not `python`) on this system

## Running
```bash
# OAE branded entry point
python3 oae.py --rtap --max-iterations 20 -v

# Laboratory protocols
python3 oae.py --list-protocols
python3 oae.py --protocol discovery
python3 oae.py --protocol rtap_exploration
python3 oae.py --protocol magnetic_study

# Full convergence pipeline (v1)
python3 run.py --max-iterations 20 --target 0.95 -v

# v2 convergence (99% target, rebalanced weights)
python3 run.py --v2 --max-iterations 20 -v

# v3 RTAP discovery mode (room-temperature ambient-pressure)
python3 run.py --rtap --max-iterations 20 -v

# Crystal structure editor (standalone)
python3 -m agent_v.editor --port 8052

# Agent PB standalone
python3 -m agent_pb.predict --formula "Ca4 S4" --algorithm hybrid --top-k 10

# XRD prediction (requires torch + xtalnet checkpoints)
python3 -m agent_xc.predict --xrd pattern.xy --composition "NaCl"

# Visualization dashboard (requires dash + plotly) — includes Crystal Editor tab
python3 -m agent_v.dashboard --port 8050

# RTAP exploration dashboard — run loop + animated results
python3 -m agent_v.rtap_dashboard --port 8051

# NeMAD comparison
python3 -m benchmarks.nemad_comparison --report

# Benchmarks (6 datasets)
python3 -m benchmarks.compare_agents --dataset supercon_24
python3 -m benchmarks.compare_agents --list-datasets

# CIF batch enhancement
python3 scripts/enhance_cif_files.py --verbose

# Data registry
python3 -c "from src.core.data_registry import DataRegistry; r = DataRegistry(); print(r.stats())"
```

## Testing
```bash
pytest tests/ -v   # 343 tests across 18 files
```

## Key Dependencies
- Core: numpy, pandas, scipy, pymatgen, hyperopt
- Agent PB: tensorflow, megnet, scikit-opt, matgl, ase (optional — volume heuristic + TPE-only fallback)
- Agent XC: torch, pytorch_lightning, hydra-core, torch_geometric (optional — Bragg fallback)
- Agent V: dash, plotly, py3Dmol, matplotlib (optional — partial functionality)
- MC3D Client: requests (optional — falls back to urllib)
- NeMAD Models: scikit-learn, xgboost (optional — comparison study only)

## Implementation Status
- v1 core loop: **Complete** (11 converged iterations, 0.9479 score)
- v2 foundation scaffolding: **Complete** (~90 files across 5 packages)
- v3 RTAP discovery: **Complete** (score 0.9577, 14 families, 6 mechanisms, 2,781 RT candidates)
- OAE rename: **Complete** — cosmetic rebrand (user-facing strings only, import paths unchanged)
- Data registry: **Complete** — `src/core/data_registry.py` (unified JSON index, CRUD + queries)
- NEMAD adapter: **Complete** — `src/core/nemad_adapter.py` (wraps 58K magnetic entries)
- Crystal editor: **Complete** — `agent_v/editor/` (add/remove/move atoms, undo/redo, CIF round-trip, Dash UI)
- CIF v2 enhancement: **Complete** — 100 CIF files upgraded (symmetry ops, Wyckoff labels, bond geometry, occupancies, cell volume)
- NeMAD comparison: **Complete** — 95% classification accuracy on 20 overlap compounds, 3 complementary candidates
- Laboratory module: **Complete** — `laboratory/` (6 protocols, full agent dispatch coverage)
- Benchmark datasets: **6 datasets** with JSON externalization
- Folder reorganization: **Complete** — legacy packages moved to `references/`, docs consolidated in `docs/`
- Artifact generator: **Complete** — `agent_v/artifact_generator.py` (structured naming: `{materialtype}_{date}_{round}_{template}.{ext}`)
- Result folder display: **Complete** — protocol and RTAP runs show output paths after completion
- Tests: **343 tests** (all pass) across 18 test files
- Spec document: `docs/CRYSTAL_AGENTS_V2_SPECIFICATION.md` (authoritative reference)
- Visualization guides: `docs/VISUALIZE_GUIDELINE.md` (static), `docs/ANIMATION_GUIDELINE.md` (animated, with naming convention)

## Data Inventory
| Dataset | Records | Location |
|---------|---------|----------|
| Crystal structures (CIF v2) | 100 | `data/crystal_structures/` |
| CIF v1 backups | 100 | `data/crystal_structures/*/structure_v1.cif` |
| Synthetic structures | 4,800 | `data/synthetic/` |
| Novel RTAP candidates | 2,781 | `data/novel_candidates/` |
| GCD-ranked candidates | 313,190 | `data/predictions/` |
| Experimental references | 25 | `data/experimental/` |
| NEMAD FM (Curie temp.) | 15,577 | `references/nemad/` |
| NEMAD AFM (Neel temp.) | 7,893 | `references/nemad/` |
| NEMAD Classification | 35,037 | `references/nemad/` |
| Benchmark datasets | 6 | `data/datasets/` |
