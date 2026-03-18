# Visualization Instructions for Claude Sonnet

These are step-by-step Python instructions to generate all visualizations for the Superconductor Multi-Agent System. Each section is self-contained and can be run independently.

**Prerequisites:** `pip install matplotlib numpy pandas seaborn`

**Data location:** All paths are relative to the project root.

---

## Setup (run once)

```python
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['figure.dpi'] = 150
matplotlib.rcParams['font.size'] = 11
matplotlib.rcParams['figure.figsize'] = (10, 6)

PROJECT_ROOT = "."  # Adjust to project root path

# Load convergence history
with open(f"{PROJECT_ROOT}/data/reports/convergence_history.json") as f:
    convergence_history = json.load(f)

# Load final report
with open(f"{PROJECT_ROOT}/data/reports/final_report.json") as f:
    final_report = json.load(f)

# Load model state
with open(f"{PROJECT_ROOT}/data/synthetic/model_state.json") as f:
    model_state = json.load(f)
```

---

## Visualization 1: Convergence Curve

Line plot of weighted convergence score vs iteration with 0.95 target threshold.

```python
iterations = [h["iteration"] for h in convergence_history]
scores = [h["convergence_score"] for h in convergence_history]

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(iterations, scores, 'b-o', linewidth=2, markersize=8, label='Convergence Score', zorder=3)
ax.axhline(y=0.95, color='r', linestyle='--', linewidth=1.5, label='Target (0.95)')
ax.fill_between(iterations, scores, 0.95, where=[s >= 0.95 for s in scores],
                alpha=0.2, color='green', label='Above Target')

# Annotate final score
ax.annotate(f'{scores[-1]:.4f}', xy=(iterations[-1], scores[-1]),
            xytext=(iterations[-1]-1.5, scores[-1]+0.015),
            arrowprops=dict(arrowstyle='->', color='black'),
            fontsize=12, fontweight='bold')

ax.set_xlabel('Iteration', fontsize=13)
ax.set_ylabel('Convergence Score', fontsize=13)
ax.set_title('Multi-Agent System Convergence', fontsize=15)
ax.set_ylim(0.80, 1.0)
ax.set_xticks(iterations)
ax.legend(loc='lower right', fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_01_convergence_curve.png")
plt.show()
```

---

## Visualization 2: Component Score Heatmap

6 components x 6 iterations as a color-coded matrix.

```python
components = ["tc_distribution", "lattice_accuracy", "space_group_correctness",
              "electronic_property_match", "composition_validity", "coordination_geometry"]
labels = ["Tc Distribution\n(0.30)", "Lattice Accuracy\n(0.25)", "Space Group\n(0.15)",
          "Electronic Match\n(0.15)", "Composition\n(0.10)", "Coordination\n(0.05)"]

matrix = np.zeros((len(components), len(convergence_history)))
for j, entry in enumerate(convergence_history):
    for i, comp in enumerate(components):
        matrix[i, j] = entry["component_scores"][comp]

fig, ax = plt.subplots(figsize=(12, 6))
im = ax.imshow(matrix, aspect='auto', cmap='RdYlGn', vmin=0.5, vmax=1.0)

# Add text annotations
for i in range(len(components)):
    for j in range(len(convergence_history)):
        val = matrix[i, j]
        color = 'white' if val < 0.7 else 'black'
        ax.text(j, i, f'{val:.3f}', ha='center', va='center', fontsize=10, color=color)

ax.set_xticks(range(len(convergence_history)))
ax.set_xticklabels([f'Iter {h["iteration"]}' for h in convergence_history])
ax.set_yticks(range(len(components)))
ax.set_yticklabels(labels)
ax.set_title('Component Scores Across Iterations', fontsize=14)
plt.colorbar(im, ax=ax, label='Score')
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_02_component_heatmap.png")
plt.show()
```

---

## Visualization 3: Tc Distribution Comparison (Real vs Synthetic)

Per-family box plots comparing experimental and synthetic Tc values.

```python
# Experimental reference data
experimental = {
    "cuprate": [92, 38, 85, 133, 125],
    "iron_pnictide": [26, 38, 52],
    "iron_chalcogenide": [8, 14],
    "heavy_fermion": [2.3, 2.1, 18.5],
    "mgb2_type": [39, 32, 37],
    "a15": [18.3, 23.2, 17.1],
    "hydride": [203, 250],
    "nickelate": [15, 80],
    "chevrel": [15],
}

# Load synthetic data from final iteration
synth_df = pd.read_csv(f"{PROJECT_ROOT}/data/synthetic/iteration_005/properties.csv")

# Map pattern_id to family
def get_family(pid):
    prefix = pid.rsplit("-", 1)[0]
    family_map = {
        "cuprate-layered": "cuprate", "cuprate-multilayer": "cuprate",
        "iron-pnictide": "iron_pnictide", "iron-chalcogenide": "iron_chalcogenide",
        "heavy-fermion": "heavy_fermion", "mgb2-type": "mgb2_type",
        "a15": "a15", "hydride": "hydride", "hydride-lah10": "hydride",
        "nickelate": "nickelate", "chevrel": "chevrel",
    }
    return family_map.get(prefix, prefix.replace("-", "_"))

synth_df["family"] = synth_df["pattern_id"].apply(get_family)

families = list(experimental.keys())
fig, axes = plt.subplots(3, 3, figsize=(16, 14))
axes = axes.flatten()

for i, family in enumerate(families):
    ax = axes[i]
    exp_vals = experimental[family]
    syn_vals = synth_df[synth_df["family"] == family]["predicted_Tc_K"].values

    data = [exp_vals, syn_vals[:50]]  # Limit synthetic for visual clarity
    bp = ax.boxplot(data, labels=["Experimental", "Synthetic"],
                    patch_artist=True, widths=0.6)
    bp['boxes'][0].set_facecolor('#4ECDC4')
    bp['boxes'][1].set_facecolor('#FF6B6B')

    ax.set_title(family.replace("_", " ").title(), fontsize=12, fontweight='bold')
    ax.set_ylabel('Tc (K)')
    ax.grid(True, alpha=0.3)

# Hide unused subplot
if len(families) < len(axes):
    for j in range(len(families), len(axes)):
        axes[j].set_visible(False)

plt.suptitle('Tc Distribution: Experimental vs Synthetic (Final Iteration)', fontsize=15, y=1.01)
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_03_tc_distribution.png", bbox_inches='tight')
plt.show()
```

---

## Visualization 4: Fix Round Impact Waterfall

Shows the convergence delta achieved by each fix round.

```python
rounds = ["Baseline", "Round 1\nTc Norm", "Round 2\nPer-Family λ",
          "Round 3\nCumulative", "Round 4\nKey Fix", "Round 5\nDamping",
          "Round 6\nSeed Diversity"]
scores_by_round = [0.78, 0.89, 0.893, 0.893, 0.94, 0.941, 0.953]
deltas = [scores_by_round[0]] + [scores_by_round[i] - scores_by_round[i-1] for i in range(1, len(scores_by_round))]

fig, ax = plt.subplots(figsize=(12, 6))

cumulative = 0
colors = []
for i, d in enumerate(deltas):
    if i == 0:
        colors.append('#2196F3')  # Base: blue
    elif d > 0.01:
        colors.append('#4CAF50')  # Big improvement: green
    elif d > 0:
        colors.append('#8BC34A')  # Small improvement: light green
    else:
        colors.append('#FFC107')  # No change: yellow

    bottom = cumulative if i > 0 else 0
    bar = ax.bar(i, d if i > 0 else scores_by_round[0], bottom=bottom,
                 color=colors[-1], edgecolor='white', linewidth=1.5, width=0.7)
    # Annotate
    mid = bottom + (d if i > 0 else scores_by_round[0]) / 2
    label = f'+{d:.3f}' if i > 0 and d > 0 else f'{scores_by_round[0]:.2f}' if i == 0 else f'{d:.3f}'
    ax.text(i, scores_by_round[i] + 0.005, f'{scores_by_round[i]:.3f}',
            ha='center', va='bottom', fontsize=10, fontweight='bold')
    cumulative = scores_by_round[i]

ax.axhline(y=0.95, color='r', linestyle='--', linewidth=1.5, label='Target (0.95)')
ax.set_xticks(range(len(rounds)))
ax.set_xticklabels(rounds, fontsize=10)
ax.set_ylabel('Convergence Score', fontsize=13)
ax.set_title('Fix Round Impact on Convergence', fontsize=15)
ax.set_ylim(0, 1.05)
ax.legend(fontsize=11)
ax.grid(True, alpha=0.2, axis='y')
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_04_fix_round_waterfall.png")
plt.show()
```

---

## Visualization 5: Novel Candidates Trajectory

Bar chart showing candidate count per iteration with trend line.

```python
import glob

candidate_files = sorted(glob.glob(f"{PROJECT_ROOT}/data/novel_candidates/candidates_iteration_*.csv"))
iter_counts = []
for f in candidate_files:
    df = pd.read_csv(f)
    iter_num = int(f.split("_iteration_")[1].replace(".csv", ""))
    iter_counts.append({"iteration": iter_num, "count": len(df)})

iter_df = pd.DataFrame(iter_counts)

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(iter_df["iteration"], iter_df["count"], color='#3F51B5',
              edgecolor='white', linewidth=1, alpha=0.85)

# Add count labels on bars
for bar, count in zip(bars, iter_df["count"]):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
            str(count), ha='center', va='bottom', fontsize=10, fontweight='bold')

# Trend line
z = np.polyfit(iter_df["iteration"], iter_df["count"], 2)
p = np.poly1d(z)
x_smooth = np.linspace(iter_df["iteration"].min(), iter_df["iteration"].max(), 100)
ax.plot(x_smooth, p(x_smooth), 'r--', linewidth=2, label='Trend (quadratic fit)')

ax.set_xlabel('Iteration', fontsize=13)
ax.set_ylabel('Novel Candidates Flagged', fontsize=13)
ax.set_title(f'Novel Candidate Discovery (Total: {iter_df["count"].sum():,})', fontsize=15)
ax.set_xticks(iter_df["iteration"])
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_05_novel_candidates.png")
plt.show()
```

---

## Visualization 6: Parameter Evolution

Multi-line plot of lambda_scaling and tc_boost per family across iterations.

```python
# Load refinement reports to track parameter evolution
param_history = {}
for i in range(6):
    ref_path = f"{PROJECT_ROOT}/data/refinements/iteration_{i:03d}.json"
    try:
        with open(ref_path) as f:
            report = json.load(f)
        # Extract Sin-targeted refinements
        for ref in report.get("refinements", []):
            if ref.get("target_agent") == "Sin" and ref.get("parameter"):
                param = ref["parameter"]
                if param not in param_history:
                    param_history[param] = []
                param_history[param].append({"iteration": i, "value": ref.get("suggested_value", 1.0)})
    except FileNotFoundError:
        pass

# If refinement parsing doesn't capture history, use final model_state as static display
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Lambda scaling
lambda_params = {k: v for k, v in model_state.items() if k.startswith("lambda_scaling")}
families_l = [k.replace("lambda_scaling_", "").replace("_", " ").title() for k in lambda_params]
values_l = list(lambda_params.values())

colors = plt.cm.Set2(np.linspace(0, 1, len(families_l)))
bars1 = ax1.barh(families_l, values_l, color=colors, edgecolor='white', height=0.6)
ax1.axvline(x=1.0, color='gray', linestyle='--', linewidth=1, label='Baseline (1.0)')
for bar, val in zip(bars1, values_l):
    ax1.text(val + 0.03, bar.get_y() + bar.get_height()/2, f'{val:.3f}',
             va='center', fontsize=10)
ax1.set_xlabel('Lambda Scaling Factor', fontsize=12)
ax1.set_title('Electron-Phonon Coupling Multipliers', fontsize=13)
ax1.legend(fontsize=10)

# Tc boost
boost_params = {k: v for k, v in model_state.items() if k.startswith("tc_boost")}
families_b = [k.replace("tc_boost_", "").replace("_", " ").title() for k in boost_params]
values_b = list(boost_params.values())

bars2 = ax2.barh(families_b, values_b, color=colors[:len(families_b)], edgecolor='white', height=0.6)
ax2.axvline(x=1.0, color='gray', linestyle='--', linewidth=1, label='Baseline (1.0)')
for bar, val in zip(bars2, values_b):
    ax2.text(val + 0.03, bar.get_y() + bar.get_height()/2, f'{val:.3f}',
             va='center', fontsize=10)
ax2.set_xlabel('Tc Boost Factor', fontsize=12)
ax2.set_title('Unconventional Pairing Multipliers', fontsize=13)
ax2.legend(fontsize=10)

plt.suptitle('Final Tuned Model Parameters by Family', fontsize=15, y=1.02)
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_06_parameter_evolution.png", bbox_inches='tight')
plt.show()
```

---

## Visualization 7: Architecture Flow Diagram

```python
fig, ax = plt.subplots(figsize=(14, 8))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.axis('off')

# Agent boxes
boxes = [
    {"label": "Agent CS\n(Crystal Structure)", "xy": (1, 6), "color": "#4ECDC4"},
    {"label": "Agent Sin\n(Simulation)", "xy": (5.5, 6), "color": "#FF6B6B"},
    {"label": "Agent Ob\n(Observator)", "xy": (10, 6), "color": "#45B7D1"},
    {"label": "Orchestrator\n(run.py)", "xy": (5.5, 9), "color": "#96CEB4"},
]

for box in boxes:
    rect = plt.Rectangle(box["xy"], 3, 1.5, facecolor=box["color"],
                         edgecolor='black', linewidth=2, alpha=0.85, zorder=2)
    ax.add_patch(rect)
    ax.text(box["xy"][0]+1.5, box["xy"][1]+0.75, box["label"],
            ha='center', va='center', fontsize=11, fontweight='bold', zorder=3)

# Data artifacts
artifacts = [
    {"label": "pattern_catalog\n_v{N}.json", "xy": (2, 4), "color": "#FFF3E0"},
    {"label": "properties.csv\n+ metadata", "xy": (6.5, 4), "color": "#FFF3E0"},
    {"label": "refinements/\n+ candidates", "xy": (11, 4), "color": "#FFF3E0"},
]
for art in artifacts:
    rect = plt.Rectangle(art["xy"], 2.5, 1.2, facecolor=art["color"],
                         edgecolor='gray', linewidth=1.5, linestyle='--', zorder=2)
    ax.add_patch(rect)
    ax.text(art["xy"][0]+1.25, art["xy"][1]+0.6, art["label"],
            ha='center', va='center', fontsize=9, zorder=3)

# Arrows: CS → Sin → Ob
ax.annotate('', xy=(5.5, 6.75), xytext=(4, 6.75),
            arrowprops=dict(arrowstyle='->', lw=2, color='#333'))
ax.annotate('', xy=(10, 6.75), xytext=(8.5, 6.75),
            arrowprops=dict(arrowstyle='->', lw=2, color='#333'))

# Feedback arrow: Ob → CS
ax.annotate('', xy=(2.5, 7.5), xytext=(10, 7.7),
            arrowprops=dict(arrowstyle='->', lw=2, color='red',
                          connectionstyle='arc3,rad=0.3'))
ax.text(6.5, 8.3, 'Refinement Feedback', ha='center', fontsize=10,
        color='red', fontstyle='italic')

# Down arrows to artifacts
for x_from, x_to in [(2.5, 3.25), (7, 7.75), (11.5, 12.25)]:
    ax.annotate('', xy=(x_to, 5.2), xytext=(x_from, 6),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='gray'))

# Convergence badge
ax.text(7, 2, 'CONVERGED: 0.9533 (6 iterations, 1632 novel candidates)',
        ha='center', fontsize=13, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#C8E6C9', edgecolor='green', lw=2))

ax.set_title('Multi-Agent Superconductor Discovery System', fontsize=16, fontweight='bold', pad=20)
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_07_architecture.png", bbox_inches='tight')
plt.show()
```

---

## Visualization 8: Family Tc Scatter (Predicted vs Experimental)

```python
# Experimental reference Tc by family
exp_tc = {
    "cuprate": {"mean": 94.6, "max": 133, "compounds": 5},
    "iron_pnictide": {"mean": 38.7, "max": 52, "compounds": 3},
    "iron_chalcogenide": {"mean": 11.0, "max": 14, "compounds": 2},
    "heavy_fermion": {"mean": 7.6, "max": 18.5, "compounds": 3},
    "mgb2_type": {"mean": 36.0, "max": 39, "compounds": 3},
    "a15": {"mean": 19.5, "max": 23.2, "compounds": 3},
    "hydride": {"mean": 226.5, "max": 250, "compounds": 2},
    "nickelate": {"mean": 47.5, "max": 80, "compounds": 2},
    "chevrel": {"mean": 15.0, "max": 15, "compounds": 1},
}

# Synthetic mean Tc from final iteration
synth_df = pd.read_csv(f"{PROJECT_ROOT}/data/synthetic/iteration_005/properties.csv")
synth_df["family"] = synth_df["pattern_id"].apply(get_family)  # Reuse get_family from Viz 3
synth_tc = synth_df.groupby("family")["predicted_Tc_K"].agg(["mean", "max", "std"]).to_dict("index")

fig, ax = plt.subplots(figsize=(10, 10))

colors_map = {
    "cuprate": "#E53935", "iron_pnictide": "#1E88E5", "iron_chalcogenide": "#43A047",
    "heavy_fermion": "#8E24AA", "mgb2_type": "#FB8C00", "a15": "#00ACC1",
    "hydride": "#D81B60", "nickelate": "#5E35B1", "chevrel": "#6D4C41",
}

for family in exp_tc:
    if family in synth_tc:
        exp_mean = exp_tc[family]["mean"]
        syn_mean = synth_tc[family]["mean"]
        syn_std = synth_tc[family].get("std", 0)
        color = colors_map.get(family, "gray")

        ax.scatter(exp_mean, syn_mean, s=200, c=color, edgecolors='black',
                   linewidths=1.5, zorder=3, label=family.replace("_", " ").title())
        ax.errorbar(exp_mean, syn_mean, yerr=syn_std, fmt='none',
                    ecolor=color, alpha=0.5, capsize=5)

# Perfect prediction line
max_tc = 300
ax.plot([0, max_tc], [0, max_tc], 'k--', linewidth=1, alpha=0.5, label='Perfect Match')
ax.fill_between([0, max_tc], [0, max_tc*0.8], [0, max_tc*1.2],
                alpha=0.1, color='green', label='+/-20% Band')

ax.set_xlabel('Experimental Mean Tc (K)', fontsize=13)
ax.set_ylabel('Synthetic Mean Tc (K)', fontsize=13)
ax.set_title('Predicted vs Experimental Tc by Superconductor Family', fontsize=15)
ax.legend(loc='upper left', fontsize=10)
ax.set_xlim(0, max_tc)
ax.set_ylim(0, max_tc)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(f"{PROJECT_ROOT}/docs/viz_08_tc_scatter.png")
plt.show()
```

---

## Summary of Outputs

| # | Visualization | File |
|---|--------------|------|
| 1 | Convergence Curve | `docs/viz_01_convergence_curve.png` |
| 2 | Component Score Heatmap | `docs/viz_02_component_heatmap.png` |
| 3 | Tc Distribution Comparison | `docs/viz_03_tc_distribution.png` |
| 4 | Fix Round Waterfall | `docs/viz_04_fix_round_waterfall.png` |
| 5 | Novel Candidates Trajectory | `docs/viz_05_novel_candidates.png` |
| 6 | Parameter Evolution | `docs/viz_06_parameter_evolution.png` |
| 7 | Architecture Diagram | `docs/viz_07_architecture.png` |
| 8 | Family Tc Scatter | `docs/viz_08_tc_scatter.png` |
