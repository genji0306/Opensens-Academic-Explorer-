# Opensens Academic Agent — Animation Visualization Guideline

## Purpose

This guideline instructs Claude Sonnet on how to create **animated visualizations** of the Opensens Academic Agent RTAP superconductor discovery platform. Animations use `matplotlib.animation.FuncAnimation` and export to MP4 (via ffmpeg) or GIF (via Pillow). Output to `data/exports/`.

The animations must convey:
1. **Project architecture** — All 12 agents, their roles, data flow
2. **Discovery pipeline** — CS → Sin → Ob convergence loop with RTAP scoring
3. **Results** — Tc distributions, candidates, mechanisms, convergence

---

## 1. Project Architecture — All Agents

### 1.1 Agent Inventory

| Agent | File | Role | Pipeline |
|-------|------|------|----------|
| **CS** (Crystal Seed) | `src/agents/agent_cs.py` | Bootstrap 24 seed patterns from 14 superconductor families | V1 Core Entry |
| **Sin** (Simulation) | `src/agents/agent_sin.py` | Generate 4800 synthetic structures, predict Tc via 6 mechanisms | V1 Core Generator |
| **Ob** (Observator) | `src/agents/agent_ob.py` | Score convergence (7 v1 / 6 RTAP components), generate refinements | V1 Core Scorer |
| **P** (Pressure) | `src/agents/agent_p.py` | Birch-Murnaghan EOS, Gruneisen Tc(P) curves, decompression scans | V1 Auxiliary |
| **CB** (Crystal Builder) | `src/agents/agent_cb.py` | Build CIF structures, Wyckoff sites, synthesis feasibility | V1 Late Stage |
| **GCD** (Ranking) | `src/agents/agent_gcd.py` | Cluster, rank, extrapolate candidates; novelty via NEMAD features | V1 Final Stage |
| **PB** (GNN Predictor) | `agent_pb/predict.py` | Formula → structure via MEGNet/M3GNet + TPE/PSO optimization | V2 Standalone |
| **XC** (XRD Predictor) | `agent_xc/predict.py` | XRD pattern → structure via XtalNet CPCP/CCSG models | V2 Standalone |
| **V** (Visualization) | `agent_v/dashboard.py` | 4-panel Dash dashboard: structure viewer, convergence, status, candidates | V2 Monitor |
| **Orchestrator** | `src/orchestrator.py` | Control CS→Sin→Ob loop, detect convergence/plateau, final reports | Controller |
| **Skill Router** | `skill_v2/router.py` | Classify user intent → execution plan (6 intents) | V2 Skill |
| **Benchmark** | `benchmarks/compare_agents.py` | Cross-agent comparison on supercon_24 and seed_patterns_12 datasets | V2 Test |

### 1.2 Core Support Modules

| Module | File | Purpose |
|--------|------|---------|
| **tc_models** | `src/core/tc_models.py` | 6 Tc mechanisms: BCS, Eliashberg, spin-fluctuation, flat-band, excitonic, hydride-cage |
| **schemas** | `src/core/schemas.py` | PatternCard, SyntheticStructure, RefinementReport, ComponentScores |
| **config** | `src/core/config.py` | Paths, weights, thresholds (v1/v2/RTAP) |

### 1.3 Pipeline Flow

```
V1 CORE LOOP (iterative):
  CS (24 patterns) ──→ Sin (4800 structures) ──→ Ob (score + refine)
       ↑                     │                        │
       │                     ↓                        ↓
       │                  P (pressure)           [converged?]
       │                                         ↓ no     ↓ yes
       └──── refinements ◄────────────────────────┘        │
                                                           ↓
                                              GCD (rank + extrapolate)
                                                           ↓
                                              CB (build CIF + feasibility)
                                                           ↓
                                              V (dashboard + export)

V2 STANDALONE:
  Formula ──→ PB (GNN + optimizer) ──→ CIF/structure
  XRD ──→ XC (XtalNet + simulator) ──→ CIF/structure

SKILL v2:
  User request ──→ Router (6 intents) ──→ Executor ──→ Agent dispatch
```

---

## 2. Dependencies & Setup

```python
import numpy as np
import pandas as pd
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from pathlib import Path

# Dark theme
plt.rcParams.update({
    "figure.facecolor": "#0D1117",
    "axes.facecolor":   "#161B22",
    "axes.edgecolor":   "#30363D",
    "axes.labelcolor":  "#C9D1D9",
    "text.color":       "#C9D1D9",
    "xtick.color":      "#8B949E",
    "ytick.color":      "#8B949E",
    "axes.grid":        True,
    "grid.color":       "#21262D",
    "grid.alpha":       0.6,
    "grid.linestyle":   "--",
    "font.family":      "monospace",
    "font.size":        11,
    "figure.dpi":       100,
    "savefig.dpi":      150,
})

PROJECT_ROOT = Path(__file__).resolve().parent
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def get_writer(fmt="mp4", fps=30):
    if fmt == "mp4":
        try:
            return animation.FFMpegWriter(fps=fps, metadata={"title": "RTAP Discovery"})
        except Exception:
            fmt = "gif"
    return animation.PillowWriter(fps=fps)
```

---

## 3. Color Palettes

```python
# Agent node colors (for architecture diagrams)
AGENT_COLORS = {
    "CS":           "#58A6FF",  # blue — knowledge
    "Sin":          "#F97583",  # red — generation
    "Ob":           "#56D364",  # green — evaluation
    "P":            "#D2A8FF",  # purple — physics
    "CB":           "#FFA657",  # orange — building
    "GCD":          "#79C0FF",  # light blue — ranking
    "PB":           "#FF7B72",  # coral — GNN
    "XC":           "#D29922",  # gold — XRD
    "V":            "#3FB950",  # bright green — visualization
    "Orchestrator": "#8B949E",  # gray — control
    "Router":       "#BC8CFF",  # violet — routing
    "Benchmark":    "#7EE787",  # lime — testing
}

# Family colors
FAMILY_COLORS = {
    "cuprate-layered":    "#FF6B6B",  "cuprate-multilayer": "#EE5A5A",
    "iron-pnictide":      "#4DABF7",  "iron-chalcogenide":  "#3A8FDB",
    "heavy-fermion":      "#69DB7C",  "mgb2-type":          "#38D9A9",
    "hydride":            "#FFD43B",  "hydride-lah10":      "#FCC419",
    "nickelate":          "#FF922B",  "a15":                "#748FFC",
    "chevrel":            "#8CE99A",
    "kagome":             "#DA77F2",  "ternary-hydride":    "#F06595",
    "infinite-layer":     "#74C0FC",  "topological":        "#66D9E8",
    "2d-heterostructure": "#9775FA",  "carbon-based":       "#B197FC",
    "engineered-cuprate": "#E599F7",  "mof-sc":             "#C084FC",
    "flat-band":          "#D0BFFF",
}

MECHANISM_COLORS = {
    "bcs":               "#4DABF7",  "spin_fluctuation":  "#FF6B6B",
    "flat_band":         "#D0BFFF",  "excitonic":         "#38D9A9",
    "hydride_cage":      "#F06595",  "mixed":             "#FFD43B",
}

RT_GLOW = "#FF6B6B"
RT_LINE = "#FF4444"
```

---

## 4. Data Loading

```python
def load_properties():
    synth = PROJECT_ROOT / "data" / "synthetic"
    iters = sorted(synth.glob("iteration_*"), key=lambda p: int(p.name.split("_")[1]))
    df = pd.read_csv(iters[-1] / "properties.csv")
    df["family"] = df["pattern_id"].str.rsplit("-", n=1).str[0]
    return df

def load_candidates():
    cdir = PROJECT_ROOT / "data" / "novel_candidates"
    files = sorted(cdir.glob("candidates_*.csv"), key=lambda p: int(p.stem.split("_")[-1]))
    df = pd.read_csv(files[-1])
    df["family"] = df["pattern_id"].str.rsplit("-", n=1).str[0]
    return df

def load_convergence():
    with open(PROJECT_ROOT / "data/reports/convergence_history.json") as f:
        return json.load(f)

RTAP_FAMILIES = [
    "kagome", "ternary-hydride", "infinite-layer", "topological",
    "2d-heterostructure", "carbon-based", "engineered-cuprate",
    "mof-sc", "flat-band"
]
```

---

## 5. Animation Templates

### 5.1 Agent Architecture Flow (NEW — Project Structure)

**Effect**: Agents appear as glowing nodes. Data-flow arrows animate between them, following the pipeline: CS→Sin→Ob loop, then GCD→CB→V. V2 standalone agents (PB, XC) appear separately. Each node pulses when "active".

**Duration**: ~20 seconds.

```python
def anim_architecture_flow(output="data/exports/rtap_architecture.mp4", fps=30):
    """Animated project architecture showing all 12 agents and data flow."""
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Opensens Academic Agent — Architecture", fontsize=16,
                 fontweight="bold", color="#C9D1D9", y=0.98)

    # Agent positions (x, y)
    agents = {
        # V1 Core Loop (center)
        "CS":  (3, 7, "Crystal Seed\n24 patterns"),
        "Sin": (8, 7, "Simulation\n4800 structures"),
        "Ob":  (13, 7, "Observator\nScore & Refine"),
        "P":   (8, 5, "Pressure\nTc(P) curves"),
        # V1 Late Stage
        "GCD": (13, 3, "Ranking\nTop candidates"),
        "CB":  (8, 3, "Builder\nCIF + Feasibility"),
        # V2 Standalone
        "PB":  (2, 3, "GNN Predictor\nFormula → CIF"),
        "XC":  (2, 1, "XRD Predictor\nPattern → CIF"),
        # V2 Monitor + Control
        "V":           (8, 1, "Dashboard\n4-panel Dash"),
        "Orchestrator":(8, 9, "Orchestrator\nLoop Control"),
        "Router":      (13, 1, "Skill Router\n6 intents"),
        "Benchmark":   (13, 5, "Benchmark\nCross-agent"),
    }

    # Data flow arrows: (from, to, label, phase)
    arrows = [
        ("Orchestrator", "CS",  "start",     0),
        ("CS",  "Sin", "patterns",           1),
        ("Sin", "P",   "structures",         2),
        ("Sin", "Ob",  "synthetic CSV",      3),
        ("Ob",  "CS",  "refinements",        4),  # loop back
        ("Ob",  "GCD", "novel candidates",   5),
        ("GCD", "CB",  "top-50",             6),
        ("CB",  "V",   "CIF + feasibility",  7),
        ("Benchmark", "Ob", "metrics",       8),
    ]

    n_agents = len(agents)
    n_arrows = len(arrows)
    phase_frames = 30  # frames per phase
    agent_appear_frames = n_agents * 8  # stagger agent appearance
    arrow_frames = n_arrows * phase_frames
    hold_frames = 90
    n_frames = agent_appear_frames + arrow_frames + hold_frames

    def draw_agent_node(ax, x, y, name, label, alpha=1.0, pulse=1.0):
        color = AGENT_COLORS.get(name, "#8B949E")
        # Glow
        glow = plt.Circle((x, y), 0.55 * pulse, color=color, alpha=0.15 * alpha)
        ax.add_patch(glow)
        # Node
        node = plt.Circle((x, y), 0.4, color=color, alpha=0.8 * alpha,
                           ec="#30363D", linewidth=2)
        ax.add_patch(node)
        # Name
        ax.text(x, y + 0.05, name, ha="center", va="center",
                fontsize=10, fontweight="bold", color="#0D1117", alpha=alpha)
        # Label below
        ax.text(x, y - 0.65, label, ha="center", va="top",
                fontsize=7, color="#8B949E", alpha=alpha * 0.8)

    def update(frame):
        ax.clear()
        ax.set_xlim(0, 16)
        ax.set_ylim(0, 10)
        ax.axis("off")
        ax.set_facecolor("#0D1117")
        ax.set_title("Opensens Academic Agent — Architecture",
                     fontsize=16, fontweight="bold", color="#C9D1D9", y=0.98)

        # Phase 1: Agents appear
        agent_names = list(agents.keys())
        for i, name in enumerate(agent_names):
            appear_frame = i * 8
            if frame >= appear_frame:
                x, y, label = agents[name]
                age = frame - appear_frame
                alpha = min(1.0, age / 15.0)
                pulse = 1.0 + 0.3 * max(0, 1.0 - age / 20.0)  # initial pulse
                draw_agent_node(ax, x, y, name, label, alpha, pulse)

        # Phase 2: Arrows animate
        arrow_start = agent_appear_frames
        for idx, (src, dst, label, phase) in enumerate(arrows):
            arrow_frame = arrow_start + idx * phase_frames
            if frame >= arrow_frame:
                x1, y1, _ = agents[src]
                x2, y2, _ = agents[dst]
                progress = min(1.0, (frame - arrow_frame) / (phase_frames * 0.6))
                # Ease out
                t = 1 - (1 - progress) ** 3

                mx = x1 + (x2 - x1) * t
                my = y1 + (y2 - y1) * t

                color = AGENT_COLORS.get(src, "#8B949E")
                ax.annotate("", xy=(mx, my), xytext=(x1, y1),
                           arrowprops=dict(arrowstyle="->", color=color,
                                          lw=2, alpha=0.7 * t))
                if t > 0.8:
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    ax.text(mid_x, mid_y + 0.25, label, ha="center",
                            fontsize=7, color=color, alpha=t * 0.6,
                            style="italic")

        # Section labels
        if frame > 20:
            ax.text(8, 9.7, "CONTROLLER", ha="center", fontsize=8,
                    color="#8B949E", alpha=0.5)
        if frame > 40:
            ax.text(8, 7.8, "V1 CORE LOOP", ha="center", fontsize=8,
                    color="#58A6FF", alpha=0.5)
        if frame > 60:
            ax.text(10.5, 3.8, "V1 LATE STAGE", ha="center", fontsize=8,
                    color="#FFA657", alpha=0.5)
        if frame > 70:
            ax.text(2, 2, "V2 STANDALONE", ha="center", fontsize=8,
                    color="#FF7B72", alpha=0.5)

        return []

    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
    print(f"Saved: {output}")
```

---

### 5.2 Agent Pipeline Pulse (NEW — Data Flow Heartbeat)

**Effect**: A simplified horizontal pipeline diagram where data "packets" (colored dots) travel between agents along connector lines. Each agent node lights up when a packet arrives, then dims. Shows the full CS→Sin→P→Ob→(loop)→GCD→CB→V sequence.

**Duration**: ~15 seconds.

```python
def anim_pipeline_pulse(output="data/exports/rtap_pipeline_pulse.mp4", fps=30):
    """Data packets flow through the agent pipeline."""
    fig, ax = plt.subplots(figsize=(16, 4))
    ax.set_xlim(-0.5, 15.5)
    ax.set_ylim(-1.5, 2.5)
    ax.axis("off")
    ax.set_title("RTAP Discovery Pipeline — Data Flow", fontsize=14,
                 fontweight="bold", color="#C9D1D9")

    # Pipeline nodes (x position, name, short label)
    nodes = [
        (0, "CS", "Seed\nPatterns"),
        (2.5, "Sin", "Generate\nStructures"),
        (5, "P", "Pressure\nCorrection"),
        (7.5, "Ob", "Score &\nRefine"),
        (10, "GCD", "Rank &\nExtrapolate"),
        (12.5, "CB", "Build\nCIF"),
        (15, "V", "Visualize\nResults"),
    ]

    # Packets: (start_node_idx, end_node_idx, color, label, start_frame)
    packets = [
        (0, 1, "#58A6FF", "24 patterns", 0),
        (1, 2, "#F97583", "4800 structs", 50),
        (2, 3, "#D2A8FF", "Tc(P)", 100),
        (3, 0, "#56D364", "refinements", 150),  # loop back
        (0, 1, "#58A6FF", "refined", 200),
        (1, 3, "#F97583", "iteration 2", 250),
        (3, 4, "#56D364", "candidates", 300),
        (4, 5, "#79C0FF", "top-50", 350),
        (5, 6, "#FFA657", "CIF+report", 400),
    ]

    n_frames = 500
    packet_speed = 40  # frames to traverse one link

    def update(frame):
        ax.clear()
        ax.set_xlim(-0.5, 15.5)
        ax.set_ylim(-1.5, 2.5)
        ax.axis("off")
        ax.set_facecolor("#0D1117")
        ax.set_title("RTAP Discovery Pipeline — Data Flow", fontsize=14,
                     fontweight="bold", color="#C9D1D9")

        # Draw connector lines
        for i in range(len(nodes) - 1):
            x1 = nodes[i][0]
            x2 = nodes[i + 1][0]
            ax.plot([x1, x2], [0, 0], color="#30363D", linewidth=3, zorder=0)

        # Loop-back line (Ob → CS)
        ax.annotate("", xy=(0.3, 0.5), xytext=(7.2, 0.5),
                    arrowprops=dict(arrowstyle="->", color="#56D364",
                                   connectionstyle="arc3,rad=0.4",
                                   lw=1.5, alpha=0.3))
        ax.text(3.75, 1.6, "feedback loop", ha="center", fontsize=8,
                color="#56D364", alpha=0.4, style="italic")

        # Draw nodes
        active_nodes = set()

        # Check which packets are active
        for src_i, dst_i, color, label, start in packets:
            if frame < start or frame > start + packet_speed:
                continue
            t = (frame - start) / packet_speed
            t_ease = 0.5 * (1 - np.cos(np.pi * t))

            if src_i > dst_i:  # loop back
                # Arc path
                x1, x2 = nodes[src_i][0], nodes[dst_i][0]
                px = x1 + (x2 - x1) * t_ease
                py = 0.5 + 1.2 * np.sin(np.pi * t_ease)
            else:
                x1, x2 = nodes[src_i][0], nodes[dst_i][0]
                px = x1 + (x2 - x1) * t_ease
                py = 0

            # Draw packet
            ax.plot(px, py, "o", color=color, markersize=12, zorder=10)
            ax.plot(px, py, "o", color=color, markersize=20, alpha=0.2, zorder=9)
            ax.text(px, py - 0.5, label, ha="center", fontsize=7,
                    color=color, alpha=0.8)

            # Light up destination when packet arrives
            if t > 0.9:
                active_nodes.add(dst_i)
            if t < 0.1:
                active_nodes.add(src_i)

        for i, (x, name, label) in enumerate(nodes):
            color = AGENT_COLORS.get(name, "#8B949E")
            is_active = i in active_nodes
            size = 0.35 if not is_active else 0.42
            alpha = 0.7 if not is_active else 1.0

            if is_active:
                glow = plt.Circle((x, 0), 0.55, color=color, alpha=0.2)
                ax.add_patch(glow)

            node = plt.Circle((x, 0), size, color=color, alpha=alpha,
                              ec="#C9D1D9" if is_active else "#30363D", linewidth=2)
            ax.add_patch(node)
            ax.text(x, 0, name, ha="center", va="center", fontsize=9,
                    fontweight="bold", color="#0D1117")
            ax.text(x, -0.7, label, ha="center", va="top", fontsize=7,
                    color="#8B949E")

        # RTAP score badge
        ax.text(15, 1.5, "RTAP Score\n0.9574", ha="center", fontsize=12,
                fontweight="bold", color="#56D364",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#161B22",
                         edgecolor="#56D364", alpha=0.8))

        return []

    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
    print(f"Saved: {output}")
```

---

### 5.3 Tc Mechanism Tree (NEW — 6 Mechanisms Branching)

**Effect**: A tree diagram grows from a central "Tc Models" root. Six branches extend to mechanism nodes (BCS, Eliashberg, spin-fluctuation, flat-band, excitonic, hydride-cage), each with their formula snippet and confidence level. Branches grow outward with family exemplars appearing at leaf nodes.

**Duration**: ~12 seconds.

```python
def anim_mechanism_tree(output="data/exports/rtap_mechanism_tree.mp4", fps=30):
    """Tree of 6 Tc mechanisms growing from center."""
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(-7, 7)
    ax.set_ylim(-6, 5)
    ax.axis("off")
    ax.set_title("Tc Prediction — 6 Pairing Mechanisms", fontsize=14,
                 fontweight="bold", color="#C9D1D9")

    mechanisms = [
        ("BCS\n(Allen-Dynes)", -5, 2, "#4DABF7", "Tc ~ w_log * exp(-1/lambda)",
         0.9, ["cuprate", "a15", "MgB2"]),
        ("Eliashberg", -3, 2, "#FCC419", "Gap equation\n(strong coupling)",
         0.85, ["hydride-lah10"]),
        ("Spin\nFluctuation", -1, 2, "#FF6B6B", "Tc ~ T_sf * nesting",
         0.7, ["engineered-cuprate", "infinite-layer", "topological"]),
        ("Flat Band", 1, 2, "#D0BFFF", "Tc ~ sqrt(lambda*W*w_D)",
         0.7, ["kagome", "2d-hetero", "carbon", "flat-band"]),
        ("Excitonic", 3, 2, "#38D9A9", "Tc ~ E_exciton/2kB",
         0.6, ["mof-sc"]),
        ("Hydride\nCage", 5, 2, "#F06595", "BCS + P_chem\n+ decompression",
         0.7, ["ternary-hydride"]),
    ]

    n_grow = 200  # frames to grow tree
    n_hold = 160  # frames to hold
    n_frames = n_grow + n_hold

    def update(frame):
        ax.clear()
        ax.set_xlim(-7, 7)
        ax.set_ylim(-6, 5)
        ax.axis("off")
        ax.set_facecolor("#0D1117")
        ax.set_title("Tc Prediction — 6 Pairing Mechanisms", fontsize=14,
                     fontweight="bold", color="#C9D1D9")

        # Root node
        root_alpha = min(1.0, frame / 20.0)
        ax.plot(0, -1, "s", color="#8B949E", markersize=20, alpha=root_alpha)
        ax.text(0, -1, "Tc\nModels", ha="center", va="center", fontsize=8,
                fontweight="bold", color="#0D1117", alpha=root_alpha)

        for i, (name, x, y, color, formula, conf, families) in enumerate(mechanisms):
            branch_start = 20 + i * 25
            if frame < branch_start:
                continue

            progress = min(1.0, (frame - branch_start) / 40.0)
            t = 1 - (1 - progress) ** 2  # ease out

            # Branch line
            bx = x * t
            by = -1 + (y + 1) * t
            ax.plot([0, bx], [-1, by], color=color, linewidth=2, alpha=0.6 * t)

            if t > 0.5:
                # Mechanism node
                node_alpha = min(1.0, (t - 0.5) * 4)
                ax.plot(bx, by, "o", color=color, markersize=18, alpha=node_alpha)
                ax.text(bx, by, name, ha="center", va="center", fontsize=7,
                        fontweight="bold", color="#0D1117", alpha=node_alpha)
                # Formula
                ax.text(bx, by - 0.7, formula, ha="center", fontsize=6,
                        color=color, alpha=node_alpha * 0.7, style="italic")
                # Confidence bar
                bar_y = by - 1.2
                ax.barh(bar_y, conf * 2, height=0.15, left=bx - 1,
                        color=color, alpha=node_alpha * 0.5)
                ax.text(bx + 1.1, bar_y, f"{conf:.0%}", fontsize=6,
                        color=color, alpha=node_alpha * 0.6, va="center")

            # Family leaves
            if t > 0.8:
                leaf_alpha = min(1.0, (t - 0.8) * 5)
                for j, fam in enumerate(families):
                    leaf_y = by - 1.8 - j * 0.5
                    fam_color = FAMILY_COLORS.get(fam, "#888")
                    ax.plot(bx, leaf_y, "o", color=fam_color, markersize=6,
                            alpha=leaf_alpha * 0.7)
                    ax.text(bx + 0.3, leaf_y, fam, fontsize=6,
                            color=fam_color, alpha=leaf_alpha * 0.6, va="center")

        return []

    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
    print(f"Saved: {output}")
```

---

### 5.4 Discovery Emergence (Tc vs Lambda scatter, progressive)

Structures appear one-by-one, building the full landscape. Dots glow when exceeding 273K.

```python
def anim_discovery_emergence(df, output="data/exports/rtap_emergence.mp4", fps=30):
    """Structures materialize on scatter plot, glowing above 273K."""
    df = df.sort_values("ambient_pressure_Tc_K").reset_index(drop=True)
    n = len(df)
    batch = max(1, n // 400)

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, df["electron_phonon_lambda"].max() * 1.1)
    ax.set_ylim(0, min(df["ambient_pressure_Tc_K"].max() * 1.1, 900))
    ax.set_xlabel("Electron-Phonon Coupling (lambda)")
    ax.set_ylabel("Ambient Pressure Tc (K)")
    ax.set_title("RTAP Discovery — Structure Emergence", fontweight="bold", fontsize=14)
    ax.axhline(y=273, color=RT_LINE, linestyle="--", linewidth=1.5, alpha=0.6)

    xs = df["electron_phonon_lambda"].values
    ys = df["ambient_pressure_Tc_K"].values
    colors = [MECHANISM_COLORS.get(m, "#888") for m in df["primary_mechanism"]]
    is_rt = ys >= 273
    alphas = np.zeros(n)
    sizes = np.zeros(n)
    scat = ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.0, edgecolors="none")
    counter_text = ax.text(0.02, 0.95, "", transform=ax.transAxes,
                           fontsize=12, color="#58A6FF", verticalalignment="top")
    rt_text = ax.text(0.02, 0.89, "", transform=ax.transAxes,
                      fontsize=12, color=RT_GLOW, verticalalignment="top")

    def update(frame):
        idx_end = min((frame + 1) * batch, n)
        for i in range(frame * batch, idx_end):
            alphas[i] = 1.0
            sizes[i] = 80 if is_rt[i] else 30
        mask_old = np.arange(n) < frame * batch
        alphas[mask_old] = np.clip(alphas[mask_old] * 0.97, 0.3, 1.0)
        sizes[mask_old] = np.clip(sizes[mask_old] * 0.95, 8, 80)
        sizes[is_rt & mask_old] = np.maximum(sizes[is_rt & mask_old], 15)

        scat.set_offsets(np.column_stack([xs[:idx_end], ys[:idx_end]]))
        scat.set_sizes(sizes[:idx_end])
        scat.set_facecolors(colors[:idx_end])
        scat.set_alpha(alphas[:idx_end])
        counter_text.set_text(f"Structures: {idx_end:,} / {n:,}")
        rt_text.set_text(f"RT candidates (>273K): {int(is_rt[:idx_end].sum())}")
        return scat, counter_text, rt_text

    n_frames = (n + batch - 1) // batch
    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
```

---

### 5.5 Family Tc Race (Bar chart race)

```python
def anim_family_race(df, output="data/exports/rtap_family_race.mp4", fps=30):
    """Bar chart race: family mean Tc evolves as structures discovered."""
    df_rtap = df[df["family"].isin(RTAP_FAMILIES)].sample(frac=1, random_state=42).reset_index(drop=True)
    n = len(df_rtap)
    step = max(1, n // 500)
    families = sorted(RTAP_FAMILIES)

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(range(len(families)), [0]*len(families),
                   color=[FAMILY_COLORS.get(f, "#888") for f in families], height=0.7)
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(families, fontsize=10)
    ax.set_xlabel("Mean Ambient Tc (K)")
    ax.set_title("RTAP Family Tc Race", fontsize=14, fontweight="bold")
    ax.set_xlim(0, 600)
    ax.axvline(x=273, color=RT_LINE, linestyle="--", linewidth=2, alpha=0.7)

    sums = {f: 0.0 for f in families}
    counts = {f: 0 for f in families}
    progress = ax.text(0.98, 0.02, "", transform=ax.transAxes, ha="right", fontsize=11, color="#8B949E")

    def update(frame):
        idx_end = min((frame + 1) * step, n)
        for i in range(frame * step, idx_end):
            fam = df_rtap.iloc[i]["family"]
            sums[fam] += df_rtap.iloc[i]["ambient_pressure_Tc_K"]
            counts[fam] += 1
        means = [sums[f] / counts[f] if counts[f] > 0 else 0 for f in families]
        order = np.argsort(means)
        for rank, idx in enumerate(order):
            bars[idx].set_y(rank)
            bars[idx].set_width(means[idx])
        ax.set_yticks(range(len(families)))
        ax.set_yticklabels([families[i] for i in order], fontsize=10)
        progress.set_text(f"{idx_end:,} / {n:,}")
        return list(bars) + [progress]

    n_frames = (n + step - 1) // step
    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
```

---

### 5.6 Convergence Pulse (Score line with heartbeat)

```python
def anim_convergence_pulse(history, output="data/exports/rtap_convergence_pulse.mp4", fps=30):
    """Convergence score draws with pulsing glow."""
    # Find longest run
    runs, current = [], []
    for h in history:
        if h["iteration"] == 0 and current:
            runs.append(current)
            current = []
        current.append(h)
    if current:
        runs.append(current)
    run = max(runs, key=len)
    scores = [h["convergence_score"] for h in run]
    n_iters = len(scores)

    from scipy.interpolate import interp1d
    if n_iters > 1:
        f = interp1d(range(n_iters), scores, kind="cubic", fill_value="extrapolate")
        t_smooth = np.linspace(0, n_iters - 1, 300)
        s_smooth = np.clip(f(t_smooth), 0, 1)
    else:
        t_smooth, s_smooth = np.array([0]), np.array(scores)
    n_frames = len(t_smooth)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(-0.5, max(n_iters, 1) + 0.5)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Convergence Score")
    ax.set_title("RTAP Convergence", fontsize=14, fontweight="bold")
    ax.axhline(y=0.85, color="#38D9A9", linestyle="--", linewidth=1.5, alpha=0.7, label="RTAP target")
    ax.axhline(y=0.95, color="#4DABF7", linestyle=":", linewidth=1, alpha=0.5, label="v1 target")

    line, = ax.plot([], [], color="#FF6B6B", linewidth=2.5)
    glow, = ax.plot([], [], color="#FF6B6B", linewidth=8, alpha=0.15)
    dot, = ax.plot([], [], "o", color="#FF6B6B", markersize=10, zorder=5)
    score_text = ax.text(0.02, 0.95, "", transform=ax.transAxes, fontsize=16,
                         fontweight="bold", color="#FF6B6B", verticalalignment="top")
    ax.legend(loc="lower right")
    fill_ref = [ax.fill_between([], [], alpha=0)]

    def update(frame):
        idx = frame + 1
        line.set_data(t_smooth[:idx], s_smooth[:idx])
        glow.set_data(t_smooth[:idx], s_smooth[:idx])
        dot.set_data([t_smooth[frame]], [s_smooth[frame]])
        dot.set_markersize(8 + 4 * np.sin(frame * 0.3))
        fill_ref[0].remove()
        fill_ref[0] = ax.fill_between(t_smooth[:idx], 0, s_smooth[:idx], alpha=0.08, color="#FF6B6B")
        score_text.set_text(f"Score: {s_smooth[frame]:.4f}")
        return line, glow, dot, fill_ref[0], score_text

    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
```

---

### 5.7 Top Candidates Countdown (#20 → #1)

```python
def anim_top_countdown(df, output="data/exports/rtap_countdown.mp4", fps=30):
    """Top 20 candidates revealed countdown-style."""
    top20 = df.nlargest(20, "ambient_pressure_Tc_K").iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(14, 9))
    frames_per = 12
    n_frames = 20 * frames_per + 60

    def update(frame):
        ax.clear()
        ax.set_xlim(0, top20["ambient_pressure_Tc_K"].max() * 1.15)
        ax.set_ylim(-1, 20)
        ax.set_xlabel("Ambient Pressure Tc (K)")
        ax.set_title("Top 20 RTAP Candidates", fontsize=14, fontweight="bold")
        ax.axvline(x=273, color=RT_LINE, linestyle="--", linewidth=2, alpha=0.5)

        n_shown = min(frame // frames_per + 1, 20)
        sub = frame % frames_per

        for i in range(n_shown):
            row = top20.iloc[i]
            rank = 20 - i
            color = MECHANISM_COLORS.get(row["primary_mechanism"], "#888")
            y = 20 - rank

            if i == n_shown - 1 and frame < 20 * frames_per:
                t = min(1.0, (sub + 1) / frames_per)
                t = 1 - (1 - t) ** 3
                width = row["ambient_pressure_Tc_K"] * t
                alpha = 0.5 + 0.5 * t
            else:
                width = row["ambient_pressure_Tc_K"]
                alpha = 1.0

            is_top = rank == 1 and n_shown == 20 and frame >= 20 * frames_per
            ax.barh(y, width, color=color, alpha=alpha, height=0.7,
                    edgecolor="#FFD43B" if is_top else "#30363D",
                    linewidth=3 if is_top else 0.5)
            if width > 20:
                label = f"#{rank} {row['composition']} ({row['primary_mechanism']})"
                ax.text(width + 5, y, label, va="center", fontsize=8,
                        color="#C9D1D9", alpha=alpha)
        return []

    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
```

---

### 5.8 RTAP Score Components (Animated radar)

```python
def anim_score_radar(output="data/exports/rtap_score_radar.mp4", fps=30):
    """RTAP score components fill outward on radar chart."""
    components = {
        "Ambient Tc":    0.948,
        "Stability":     1.000,
        "Synthesize":    0.946,
        "Electronic":    0.907,
        "Mechanism":     0.997,
        "Composition":   0.906,
    }
    weights = [0.30, 0.25, 0.15, 0.15, 0.10, 0.05]
    names = list(components.keys())
    vals = list(components.values())
    N = len(names)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist() + [0]

    n_fill = 180
    n_hold = 120
    n_frames = n_fill + n_hold

    colors = ["#FF6B6B", "#38D9A9", "#FFA657", "#4DABF7", "#D0BFFF", "#748FFC"]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})

    def update(frame):
        ax.clear()
        ax.set_ylim(0, 1.1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(names, fontsize=10, color="#C9D1D9")
        ax.set_yticklabels([])
        ax.set_title("RTAP Score: 0.9574", fontsize=14, fontweight="bold",
                     color="#C9D1D9", y=1.08)

        t = min(1.0, (frame + 1) / n_fill)
        t = 0.5 * (1 - np.cos(np.pi * t))

        # Individual component bars
        for i, (v, c, w) in enumerate(zip(vals, colors, weights)):
            v_scaled = v * t
            bar_angles = [angles[i]]
            ax.bar(bar_angles, [v_scaled], width=0.8, color=c, alpha=0.6, edgecolor=c)
            if t > 0.5:
                ax.text(angles[i], v_scaled + 0.08, f"{v:.0%}\n(w={w:.0%})",
                        ha="center", fontsize=7, color=c, alpha=min(1.0, (t - 0.5) * 4))

        # Composite line
        v_line = [v * t for v in vals] + [vals[0] * t]
        ax.plot(angles, v_line, "o-", color="#FF6B6B", linewidth=2, markersize=5)
        ax.fill(angles, v_line, alpha=0.1, color="#FF6B6B")

        return []

    ani = animation.FuncAnimation(fig, update, frames=n_frames,
                                  interval=1000//fps, blit=False)
    writer = get_writer("mp4", fps)
    ani.save(str(EXPORT_DIR / Path(output).name), writer=writer)
    plt.close(fig)
```

---

## 6. Master Runner

```python
#!/usr/bin/env python3
"""Generate all RTAP discovery animations with structured naming."""

from agent_v.artifact_generator import ArtifactGenerator

def main():
    df = load_properties()
    candidates = load_candidates()
    history = load_convergence()

    # Create generator — all artifacts get materialtype_date_round naming
    gen = ArtifactGenerator(material_type="superconductor")

    print("=== RTAP Animation Suite ===")
    print(f"Structures: {len(df):,}  |  Candidates: {len(candidates):,}")
    print(f"Families: {df['family'].nunique()}  |  Mechanisms: {df['primary_mechanism'].nunique()}")
    print(f"Naming: {{material_type}}_{{date}}_{{round}}_{{template}}.mp4")
    print()

    paths = gen.generate_suite()
    templates = gen.list_templates()

    for i, (path, tmpl) in enumerate(zip(paths, templates)):
        name = tmpl["name"]
        print(f"[{i+1}/8] {name} -> {path.name}")

        if name == "architecture_flow":
            anim_architecture_flow(output=str(path))
        elif name == "pipeline_pulse":
            anim_pipeline_pulse(output=str(path))
        elif name == "mechanism_tree":
            anim_mechanism_tree(output=str(path))
        elif name == "discovery_emergence":
            anim_discovery_emergence(df, output=str(path))
        elif name == "family_race":
            anim_family_race(df, output=str(path))
        elif name == "convergence_pulse":
            anim_convergence_pulse(history, output=str(path))
        elif name == "top_countdown":
            anim_top_countdown(candidates, output=str(path))
        elif name == "score_radar":
            anim_score_radar(output=str(path))

    print(f"\nAll 8 animations saved to {gen.export_dir}/")
    print(f"Manifest: {gen._manifest_path}")
    for art in gen.list_artifacts():
        print(f"  {art['filename']}")

if __name__ == "__main__":
    main()
```

---

## 7. Output Conventions

| Parameter | Value |
|-----------|-------|
| Primary format | MP4 (H.264 via ffmpeg) |
| Fallback | GIF (via Pillow) |
| Frame rate | 30 fps |
| Resolution | 150 DPI |
| Dark theme | Background #0D1117, axes #161B22 |
| Output dir | `data/exports/` |

---

## 8. Artifact Naming Convention (MANDATORY)

**All animated artifacts MUST follow this naming structure:**

```
{material_type}_{date}_{round}_{template}.{ext}
```

| Field | Format | Description | Examples |
|-------|--------|-------------|----------|
| `material_type` | lowercase, underscores | Type of material being visualized | `superconductor`, `cuprate`, `iron_pnictide`, `magnetic`, `hydride` |
| `date` | `YYYYMMDD` | UTC date of generation | `20260318` |
| `round` | `NNN` (3-digit, zero-padded) | Sequential run number for this (type, date) pair | `001`, `002`, `015` |
| `template` | lowercase, underscores | Animation template name from section 5 | `architecture_flow`, `convergence_pulse` |
| `ext` | `mp4` or `gif` | File format | `mp4` |

### Examples

```
superconductor_20260318_001_architecture_flow.mp4
cuprate_20260318_002_discovery_emergence.mp4
magnetic_20260318_001_convergence_pulse.gif
iron_pnictide_20260319_003_family_race.mp4
hydride_20260318_001_mechanism_tree.mp4
```

### Using the ArtifactGenerator

```python
from agent_v.artifact_generator import ArtifactGenerator

# Create generator for a material type
gen = ArtifactGenerator(material_type="superconductor")

# Get a single named path (auto-increments round)
path = gen.next_path("architecture_flow")
# -> data/exports/superconductor_20260318_001_architecture_flow.mp4

path = gen.next_path("pipeline_pulse", fmt="gif")
# -> data/exports/superconductor_20260318_002_pipeline_pulse.gif

# Generate paths for full 8-animation suite
paths = gen.generate_suite()
# -> [data/exports/superconductor_20260318_003_architecture_flow.mp4,
#     data/exports/superconductor_20260318_004_pipeline_pulse.mp4, ...]

# List what's been generated
gen.list_artifacts()

# Quick one-liner
from agent_v.artifact_generator import artifact_path
path = artifact_path("cuprate", "convergence_pulse")
```

### Integrating with Animation Functions

Replace hardcoded output paths in section 5 templates:

```python
# BEFORE (hardcoded):
def anim_architecture_flow(output="data/exports/rtap_architecture.mp4", fps=30):

# AFTER (structured naming):
from agent_v.artifact_generator import ArtifactGenerator

def anim_architecture_flow(gen: ArtifactGenerator = None, fps=30):
    gen = gen or ArtifactGenerator(material_type="superconductor")
    output = gen.next_path("architecture_flow")
    # ... rest of function uses str(output) for save path
```

### Manifest Tracking

All generated artifacts are tracked in `data/exports/artifact_manifest.json`:

```json
{
  "artifacts": [
    {
      "filename": "superconductor_20260318_001_architecture_flow.mp4",
      "material_type": "superconductor",
      "date": "20260318",
      "round": 1,
      "template": "architecture_flow",
      "format": "mp4",
      "created": "2026-03-18T14:30:00+00:00"
    }
  ],
  "counters": {
    "superconductor_20260318": 1
  }
}
```

---

## 9. Quick Reference

| Goal | Animation | Section | Template Name |
|------|-----------|---------|---------------|
| Show all 12 agents and data flow | Architecture Flow | 5.1 | `architecture_flow` |
| Show pipeline with data packets | Pipeline Pulse | 5.2 | `pipeline_pulse` |
| Explain 6 Tc mechanisms | Mechanism Tree | 5.3 | `mechanism_tree` |
| Show search space exploration | Discovery Emergence | 5.4 | `discovery_emergence` |
| Compare RTAP families | Family Tc Race | 5.5 | `family_race` |
| Show optimization progress | Convergence Pulse | 5.6 | `convergence_pulse` |
| Highlight best candidates | Top Countdown | 5.7 | `top_countdown` |
| Show RTAP score breakdown | Score Radar | 5.8 | `score_radar` |

---

## 10. Performance Tips

- **Large datasets (>5000)**: Subsample with `df.sample(2000)` for emergence animations
- **No ffmpeg**: `brew install ffmpeg` or fall back to GIF
- **Memory**: Always `plt.close(fig)` after saving
- **Speed**: Reduce `n_frames` for faster render; 300 frames = ~10s at 30fps
