# Opensens Academic Explorer (OAE)

**Multi-agent crystal structure prediction and superconductor material discovery platform.**

OAE uses a swarm of specialized AI agents to predict, validate, and discover novel superconducting materials. The system combines GNN-based crystal structure prediction, XRD pattern analysis, convergence optimization, and interactive 3D visualization.

---

## Features

- **Multi-Agent Convergence Loop** --- 6 agents (Crystal Seed, Synthesis, Observation, Pressure, Crystal Builder, GCD) iterate toward a convergence target using weighted scoring across 7 components
- **Crystal Structure Prediction** --- GNN ensemble (MEGNet + M3GNet) with TPE/PSO hybrid optimization and symmetry-aware constraints
- **XRD-to-Structure** --- Predict crystal structures from X-ray diffraction patterns via XtalNet bridge
- **Room-Temperature Discovery (RTAP)** --- 14-family search across 6 Tc mechanisms (Allen-Dynes BCS, Migdal-Eliashberg, spin-fluctuation, flat-band, excitonic, hydride-cage)
- **Interactive Dashboard** --- Real-time 4-panel Dash app with 3D crystal viewer (ball-and-stick, space-filling, polyhedral, unit-cell modes), convergence monitor, agent status, and candidate ranking
- **Crystal Editor** --- Interactive atom editing with undo/redo, CIF import/export, lattice parameter control, and 230 space groups
- **Laboratory Protocols** --- 6 built-in protocols (discovery, structure_prediction, xrd_analysis, magnetic_study, rtap_exploration, verification)
- **CIF v2 Compliant** --- Full IUCr v2 output with symmetry operations, Wyckoff labels, bond geometry, and occupancies

## Quick Start

### Installation

```bash
git clone https://gitlab.com/gnvml/oeps.git
cd oeps
pip install -r requirements.txt
```

### Run the Convergence Pipeline

```bash
# v1 convergence (0.95 target)
python3 run.py --max-iterations 20 --target 0.95 -v
```

**Example output:**
```
Iteration 0: score=0.8658
Iteration 1: score=0.8485
Iteration 2: score=0.8925
Iteration 3: score=0.9204
Iteration 4: score=0.9329
Iteration 5: score=0.9321
Iteration 6: score=0.9333  <-- peak
Iteration 7: score=0.9329
Iteration 8: score=0.9317
Terminated: plateau_detected (9 iterations)
Novel candidates found: 23,584
```

The system runs 6 agents per iteration, each refining crystal structure predictions. Convergence is scored across 7 weighted components:

| Component | Weight | Description |
|-----------|--------|-------------|
| Tc Distribution | 0.20 | Critical temperature prediction accuracy |
| Lattice Accuracy | 0.20 | Lattice parameter match to known structures |
| Space Group | 0.15 | Space group classification correctness |
| Electronic Match | 0.15 | Electronic property consistency |
| Composition Validity | 0.10 | Chemical composition feasibility |
| Coordination Geometry | 0.10 | Bond distance and angle validation |
| Pressure-Tc Accuracy | 0.10 | Pressure-dependent Tc prediction |

### Launch the Dashboard

```bash
python3 -m agent_v.dashboard --port 8050
```

Open `http://127.0.0.1:8050` to access:

- **Monitor tab** --- Crystal structure viewer with 4 view modes, live convergence charts, agent status badges, top candidate table
- **Crystal Editor tab** --- Interactive atom table, lattice parameter inputs, space group selector, CIF import/export

### RTAP Discovery Mode

Search for room-temperature ambient-pressure superconductors across 14 material families:

```bash
python3 run.py --rtap --max-iterations 20 -v
```

Best RTAP score achieved: **0.9577** across 2,781 novel candidates spanning cuprate, hydride, nickelate, iron-pnictide, kagome, and other families.

### Laboratory Protocols

```bash
# List available protocols
python3 oae.py --list-protocols

# Run a specific protocol
python3 oae.py --protocol discovery
python3 oae.py --protocol rtap_exploration
python3 oae.py --protocol magnetic_study
```

### Standalone Agents

```bash
# Crystal structure prediction
python3 -m agent_pb.predict --formula "Ca4 S4" --algorithm hybrid --top-k 10

# XRD pattern analysis (requires torch + XtalNet checkpoints)
python3 -m agent_xc.predict --xrd pattern.xy --composition "NaCl"

# Crystal editor only
python3 -m agent_v.editor --port 8052

# Benchmarks
python3 -m benchmarks.compare_agents --list-datasets
python3 -m benchmarks.compare_agents --dataset supercon_24
```

## Project Structure

```
OAE/
├── oae.py                  # CLI entry point
├── run.py                  # Convergence runner
├── src/                    # v1 core loop + shared modules
│   ├── orchestrator.py     #   Feedback loop controller
│   ├── agents/             #   6 convergence agents
│   └── core/               #   Config, schemas, Tc models, MC3D client
├── agent_pb/               # GNN crystal structure predictor (19 files)
├── agent_xc/               # XRD-to-structure predictor (13 files)
├── agent_v/                # Visualization + crystal editor (20 files)
│   ├── dashboard.py        #   4-panel Dash app
│   ├── editor/             #   Interactive crystal editor
│   ├── viewers/            #   3D viewer (4 modes via 3Dmol.js)
│   └── monitors/           #   Convergence + agent status
├── laboratory/             # 6 laboratory protocols
├── benchmarks/             # Cross-agent comparison (6 datasets)
├── skill_v2/               # Intent router + execution planner
├── tests/                  # 343 tests across 18 files
├── data/                   # Agent outputs (file-based IPC)
│   ├── crystal_structures/ #   100 CIF v2 structures
│   ├── predictions/        #   Ranked candidates
│   ├── reports/            #   Convergence history + final report
│   └── novel_candidates/   #   2,781 RTAP candidates
└── references/             # Read-only reference packages
    ├── xtalnet/            #   XtalNet checkpoints (~156 MB)
    ├── nemad/              #   NEMAD magnetic materials (58K entries)
    └── legacy_agent_pb/    #   Legacy GN-OA code
```

## Data Inventory

| Dataset | Records | Description |
|---------|---------|-------------|
| Crystal structures | 100 | CIF v2 with symmetry ops, Wyckoff labels |
| Synthetic structures | 4,800 | Generated per iteration |
| RTAP candidates | 2,781 | Room-temperature superconductor candidates |
| GCD-ranked candidates | 313,190 | Full candidate pool |
| NEMAD FM entries | 15,577 | Curie temperature data |
| NEMAD AFM entries | 7,893 | Neel temperature data |
| Benchmark datasets | 6 | Cross-agent evaluation |

## Visualization Output

The pipeline generates 8 visualization charts in `data/exports/`:

| Chart | Description |
|-------|-------------|
| `rtap_tc_violin.png` | Tc distribution by material family |
| `rtap_tc_vs_lambda.png` | Tc vs electron-phonon coupling |
| `rtap_convergence.png` | Convergence score over iterations |
| `rtap_top_candidates.png` | Top-ranked candidate materials |
| `rtap_stability_tradeoff.png` | Stability vs Tc tradeoff |
| `rtap_mechanism_overview.png` | Tc mechanism breakdown |
| `rtap_crystal_systems.png` | Crystal system distribution |
| `rtap_radar.png` | Multi-dimensional score radar |

## Dashboard Views

The interactive dashboard provides 4 crystal structure viewing modes:

- **Ball & Stick** --- Spheres at scaled Van der Waals radii with thin stick bonds and unit cell edges
- **Space Filling** --- Full VdW-radius spheres showing atomic packing
- **Polyhedral** --- Coordination polyhedra around metal centers (Cu, Fe, Ti, etc.) with translucent faces
- **Unit Cell** --- Color-coded lattice vectors (a=red, b=green, c=blue) with parameter labels

## Testing

```bash
pytest tests/ -v   # 343 tests across 18 files
```

## Dependencies

**Core:** numpy, pandas, scipy, pymatgen, hyperopt

**Visualization:** plotly, dash, matplotlib (3Dmol.js loaded via CDN --- no py3Dmol needed)

**Optional ML:** tensorflow, megnet (Agent PB); torch, pytorch_lightning (Agent XC)

## License

Opensens Proprietary --- All rights reserved.
