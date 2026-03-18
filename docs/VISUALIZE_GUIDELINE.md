# RTAP Superconductor Discovery — Visualization Guideline for Claude Sonnet

## Purpose

This guideline instructs Claude Sonnet on how to generate visualizations for the Opensens Academic Agent RTAP (Room-Temperature Ambient-Pressure) superconductor discovery results. All charts use **matplotlib** and **pandas** (no Dash/Plotly dependency required). Output PNG files to `data/exports/`.

---

## 1. Data Sources

### 1.1 Properties CSV
**Path**: `data/synthetic/iteration_NNN/properties.csv`

| Column | Type | Description |
|--------|------|-------------|
| structure_id | str | Unique hex ID |
| pattern_id | str | Seed pattern (e.g., `flat-band-001`) |
| composition | str | Chemical formula |
| crystal_system | str | cubic, tetragonal, hexagonal, etc. |
| space_group | str | Hermann-Mauguin symbol |
| a, b, c | float | Lattice parameters (Angstrom) |
| alpha, beta, gamma | float | Lattice angles (degrees) |
| predicted_Tc_K | float | Raw predicted Tc (K) |
| electron_phonon_lambda | float | Electron-phonon coupling |
| energy_above_hull_meV | float | Thermodynamic stability |
| stability_confidence | float | 0-1 confidence |
| pressure_GPa | float | Operating pressure |
| volume_per_atom_A3 | float | Volume per atom |
| primary_mechanism | str | bcs, spin_fluctuation, flat_band, excitonic, hydride_cage |
| mechanism_confidence | float | 0-1 |
| ambient_pressure_Tc_K | float | Tc at ambient pressure (the key RTAP metric) |

### 1.2 Novel Candidates CSV
**Path**: `data/novel_candidates/candidates_iteration_NNN.csv`
Same 20-column schema as properties.csv, filtered to novel candidates only.

### 1.3 Convergence History JSON
**Path**: `data/reports/convergence_history.json`
```json
[
  {
    "iteration": 0,
    "convergence_score": 0.7311,
    "component_scores": {
      "tc_distribution": 0.23,
      "lattice_accuracy": 0.95,
      "space_group_correctness": 1.0,
      "electronic_property_match": 0.99,
      "composition_validity": 0.98,
      "coordination_geometry": 1.0,
      "pressure_tc_accuracy": 0.5
    },
    "timestamp": "2026-03-16T19:45:27Z"
  }
]
```

### 1.4 Final Report JSON
**Path**: `data/reports/final_report.json`
```json
{
  "termination_reason": "rtap_convergence_reached",
  "total_iterations": 1,
  "final_convergence_score": 0.9122,
  "convergence_history": [
    {"iteration": 0, "score": 0.9122, "elapsed_seconds": 3.88, "rtap_candidates_flagged": 0}
  ],
  "total_novel_candidates": 2576,
  "timestamp": "2026-03-17T15:50:05Z"
}
```

---

## 2. Color Palettes

### 2.1 Superconductor Family Colors
```python
FAMILY_COLORS = {
    "cuprate":            "#E63946",
    "iron-pnictide":      "#457B9D",
    "iron-chalcogenide":  "#1D3557",
    "heavy-fermion":      "#A8DADC",
    "mgb2-type":          "#2A9D8F",
    "hydride":            "#E9C46A",
    "nickelate":          "#F4A261",
    "a15":                "#264653",
    "chevrel":            "#606C38",
    "organic":            "#DDA15E",
    # RTAP-specific families
    "kagome":             "#7209B7",
    "ternary-hydride":    "#F72585",
    "infinite-layer":     "#4361EE",
    "topological":        "#4CC9F0",
    "2d-heterostructure": "#3A0CA3",
    "carbon-based":       "#560BAD",
    "engineered-cuprate": "#B5179E",
    "mof-sc":             "#480CA8",
    "flat-band":          "#7400B8",
}
```

### 2.2 Mechanism Colors
```python
MECHANISM_COLORS = {
    "bcs":               "#457B9D",
    "spin_fluctuation":  "#E63946",
    "flat_band":         "#7400B8",
    "excitonic":         "#2A9D8F",
    "hydride_cage":      "#F72585",
    "migdal_eliashberg": "#E9C46A",
}
```

### 2.3 Convergence Component Colors
```python
COMPONENT_COLORS = {
    "tc_distribution":          "#E63946",
    "lattice_accuracy":         "#457B9D",
    "space_group_correctness":  "#2A9D8F",
    "electronic_property_match":"#E9C46A",
    "composition_validity":     "#F4A261",
    "coordination_geometry":    "#264653",
    "pressure_tc_accuracy":     "#A8DADC",
}
```

### 2.4 RTAP Score Component Colors
```python
RTAP_SCORE_COLORS = {
    "ambient_tc_score":           "#E63946",
    "ambient_stability_score":    "#2A9D8F",
    "synthesizability_score":     "#F4A261",
    "electronic_indicator_score": "#457B9D",
    "mechanism_plausibility_score":"#7400B8",
    "composition_validity":       "#264653",
}
```

---

## 3. Standard Chart Templates

### 3.1 Tc Distribution by Family (Violin + Strip)

**When to use**: Overview of predicted Tc across all superconductor families.

```python
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

df = pd.read_csv("data/synthetic/iteration_000/properties.csv")

# Extract family from pattern_id (everything before the last dash-number)
df["family"] = df["pattern_id"].str.rsplit("-", n=1).str[0]

# Filter to RTAP families only
rtap_families = [
    "kagome", "ternary-hydride", "infinite-layer", "topological",
    "2d-heterostructure", "carbon-based", "engineered-cuprate",
    "mof-sc", "flat-band"
]
df_rtap = df[df["family"].isin(rtap_families)]

fig, ax = plt.subplots(figsize=(14, 7))

families = sorted(df_rtap["family"].unique())
positions = range(len(families))

for i, fam in enumerate(families):
    subset = df_rtap[df_rtap["family"] == fam]["ambient_pressure_Tc_K"]
    color = FAMILY_COLORS.get(fam, "#999999")
    parts = ax.violinplot(subset, positions=[i], showmedians=True, widths=0.7)
    for pc in parts["bodies"]:
        pc.set_facecolor(color)
        pc.set_alpha(0.6)

ax.axhline(y=273, color="#E63946", linestyle="--", linewidth=2, label="273K RT threshold")
ax.set_xticks(positions)
ax.set_xticklabels(families, rotation=45, ha="right", fontsize=10)
ax.set_ylabel("Ambient Pressure Tc (K)", fontsize=12)
ax.set_title("RTAP Discovery: Tc Distribution by Family", fontsize=14, fontweight="bold")
ax.legend()
plt.tight_layout()
plt.savefig("data/exports/rtap_tc_violin.png", dpi=200)
```

### 3.2 Tc vs Lambda Scatter (colored by mechanism)

**When to use**: Show relationship between electron-phonon coupling and Tc, revealing mechanism clusters.

```python
fig, ax = plt.subplots(figsize=(12, 8))

for mech, color in MECHANISM_COLORS.items():
    subset = df[df["primary_mechanism"] == mech]
    ax.scatter(
        subset["electron_phonon_lambda"],
        subset["ambient_pressure_Tc_K"],
        c=color, label=mech.replace("_", " ").title(),
        alpha=0.5, s=20, edgecolors="none"
    )

ax.axhline(y=273, color="#E63946", linestyle="--", linewidth=1.5, alpha=0.7)
ax.set_xlabel("Electron-Phonon Coupling (lambda)", fontsize=12)
ax.set_ylabel("Ambient Pressure Tc (K)", fontsize=12)
ax.set_title("Tc vs Coupling Strength by Mechanism", fontsize=14, fontweight="bold")
ax.legend(loc="upper left", framealpha=0.9)
ax.set_xlim(0, ax.get_xlim()[1])
ax.set_ylim(0, ax.get_ylim()[1])
plt.tight_layout()
plt.savefig("data/exports/rtap_tc_vs_lambda.png", dpi=200)
```

### 3.3 Convergence Score Over Iterations (Line + Area)

**When to use**: Track optimization progress across iterations.

```python
import json

with open("data/reports/convergence_history.json") as f:
    history = json.load(f)

iterations = [h["iteration"] for h in history]
scores = [h["convergence_score"] for h in history]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[2, 1])

# Top: composite score
ax1.plot(iterations, scores, "o-", color="#E63946", linewidth=2, markersize=6)
ax1.axhline(y=0.85, color="#2A9D8F", linestyle="--", label="RTAP target (0.85)")
ax1.axhline(y=0.95, color="#457B9D", linestyle=":", label="v1 target (0.95)")
ax1.fill_between(iterations, scores, alpha=0.15, color="#E63946")
ax1.set_ylabel("Convergence Score", fontsize=12)
ax1.set_title("RTAP Convergence Progress", fontsize=14, fontweight="bold")
ax1.legend()
ax1.set_ylim(0, 1.05)

# Bottom: stacked component scores
components = list(history[0]["component_scores"].keys())
bottom = [0] * len(iterations)
for comp in components:
    vals = [h["component_scores"].get(comp, 0) for h in history]
    color = COMPONENT_COLORS.get(comp, "#999999")
    ax2.bar(iterations, vals, bottom=bottom, color=color, label=comp.replace("_", " ").title(), width=0.8)
    bottom = [b + v for b, v in zip(bottom, vals)]

ax2.set_xlabel("Iteration", fontsize=12)
ax2.set_ylabel("Component Scores (stacked)", fontsize=12)
ax2.legend(fontsize=7, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.15))
plt.tight_layout()
plt.savefig("data/exports/rtap_convergence.png", dpi=200)
```

### 3.4 Top Candidates Table (horizontal bar)

**When to use**: Rank top 20 RT-SC candidates by ambient Tc.

```python
df_novel = pd.read_csv("data/novel_candidates/candidates_iteration_000.csv")
top20 = df_novel.nlargest(20, "ambient_pressure_Tc_K")

fig, ax = plt.subplots(figsize=(12, 8))

labels = [f"{row['composition']} ({row['primary_mechanism']})" for _, row in top20.iterrows()]
colors = [MECHANISM_COLORS.get(row["primary_mechanism"], "#999") for _, row in top20.iterrows()]

bars = ax.barh(range(len(top20)), top20["ambient_pressure_Tc_K"], color=colors, edgecolor="white")
ax.axvline(x=273, color="#E63946", linestyle="--", linewidth=2, label="273K threshold")
ax.set_yticks(range(len(top20)))
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("Ambient Pressure Tc (K)", fontsize=12)
ax.set_title("Top 20 RTAP Candidates", fontsize=14, fontweight="bold")
ax.invert_yaxis()
ax.legend()
plt.tight_layout()
plt.savefig("data/exports/rtap_top_candidates.png", dpi=200)
```

### 3.5 Stability vs Tc Trade-off (scatter with size = lambda)

**When to use**: Identify candidates balancing high Tc with low energy above hull.

```python
fig, ax = plt.subplots(figsize=(12, 8))

scatter = ax.scatter(
    df["energy_above_hull_meV"],
    df["ambient_pressure_Tc_K"],
    c=[FAMILY_COLORS.get(f, "#999") for f in df["family"]],
    s=df["electron_phonon_lambda"] * 20,
    alpha=0.4, edgecolors="none"
)

ax.axhline(y=273, color="#E63946", linestyle="--", alpha=0.7)
ax.axvline(x=100, color="#264653", linestyle="--", alpha=0.5, label="Stability cutoff (100 meV)")
ax.set_xlabel("Energy Above Hull (meV)", fontsize=12)
ax.set_ylabel("Ambient Pressure Tc (K)", fontsize=12)
ax.set_title("Stability vs Tc Trade-off", fontsize=14, fontweight="bold")

# Highlight sweet spot (upper-left quadrant)
ax.fill_between([0, 100], [273, 273], [ax.get_ylim()[1]] * 2,
                alpha=0.08, color="#2A9D8F", label="Target region")
ax.legend()
plt.tight_layout()
plt.savefig("data/exports/rtap_stability_tradeoff.png", dpi=200)
```

### 3.6 Mechanism Pie + RT Fraction (dual subplot)

**When to use**: Summarize mechanism diversity and RT success rate.

```python
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Left: mechanism distribution
mech_counts = df["primary_mechanism"].value_counts()
colors = [MECHANISM_COLORS.get(m, "#999") for m in mech_counts.index]
ax1.pie(mech_counts, labels=[m.replace("_", " ").title() for m in mech_counts.index],
        colors=colors, autopct="%1.1f%%", startangle=90)
ax1.set_title("Mechanism Distribution", fontsize=13, fontweight="bold")

# Right: RT fraction per RTAP family
rt_stats = df_rtap.groupby("family").agg(
    total=("ambient_pressure_Tc_K", "count"),
    rt_count=("ambient_pressure_Tc_K", lambda x: (x >= 273).sum())
).reset_index()
rt_stats["rt_frac"] = rt_stats["rt_count"] / rt_stats["total"]
rt_stats = rt_stats.sort_values("rt_frac", ascending=True)

colors_bar = [FAMILY_COLORS.get(f, "#999") for f in rt_stats["family"]]
ax2.barh(rt_stats["family"], rt_stats["rt_frac"], color=colors_bar)
ax2.set_xlabel("Fraction Above 273K", fontsize=11)
ax2.set_title("RT Success Rate by Family", fontsize=13, fontweight="bold")
ax2.set_xlim(0, 1)
for i, (_, row) in enumerate(rt_stats.iterrows()):
    ax2.text(row["rt_frac"] + 0.02, i, f"{row['rt_frac']:.0%}", va="center", fontsize=9)

plt.tight_layout()
plt.savefig("data/exports/rtap_mechanism_overview.png", dpi=200)
```

### 3.7 Crystal System Distribution (stacked bar by family)

**When to use**: Show structural diversity across families.

```python
ct = pd.crosstab(df_rtap["family"], df_rtap["crystal_system"])

fig, ax = plt.subplots(figsize=(12, 6))
ct.plot(kind="bar", stacked=True, ax=ax, colormap="Set3")
ax.set_ylabel("Count", fontsize=12)
ax.set_xlabel("Family", fontsize=12)
ax.set_title("Crystal Systems by Family", fontsize=14, fontweight="bold")
ax.legend(title="Crystal System", bbox_to_anchor=(1.02, 1), loc="upper left")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("data/exports/rtap_crystal_systems.png", dpi=200)
```

### 3.8 RTAP Score Radar (per family)

**When to use**: Multi-dimensional comparison of a single family's strengths.

```python
import numpy as np

# Example: compare top 3 families on RTAP score dimensions
categories = ["Ambient Tc", "Stability", "Synthesizability",
              "Electronic\nIndicators", "Mechanism\nPlausibility"]
N = len(categories)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

# Replace these with actual per-family mean scores from agent_ob
# Example placeholder data:
family_scores = {
    "flat-band":          [0.95, 0.60, 0.70, 0.90, 0.85],
    "engineered-cuprate": [0.80, 0.75, 0.65, 0.85, 0.90],
    "ternary-hydride":    [0.70, 0.50, 0.55, 0.75, 0.80],
}

for fam, scores in family_scores.items():
    vals = scores + scores[:1]
    ax.plot(angles, vals, "o-", label=fam, color=FAMILY_COLORS.get(fam, "#999"), linewidth=2)
    ax.fill(angles, vals, alpha=0.1, color=FAMILY_COLORS.get(fam, "#999"))

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=10)
ax.set_ylim(0, 1)
ax.set_title("RTAP Score Profile by Family", fontsize=14, fontweight="bold", y=1.08)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
plt.tight_layout()
plt.savefig("data/exports/rtap_radar.png", dpi=200)
```

---

## 4. RTAP Score Weights Reference

When computing or displaying RTAP scores, use these weights:

| Component | Weight | Description |
|-----------|--------|-------------|
| ambient_tc_score | 0.30 | Tc at P <= 1 GPa, targeting >= 273K |
| ambient_stability_score | 0.25 | Thermodynamic stability at ambient |
| synthesizability_score | 0.15 | Practical synthesis feasibility |
| electronic_indicator_score | 0.15 | Flat bands, nesting, van Hove proximity |
| mechanism_plausibility_score | 0.10 | Self-consistency of pairing mechanism |
| composition_validity | 0.05 | Basic chemical sanity |

---

## 5. Key Thresholds to Annotate

Always add reference lines/regions for these physical thresholds:

| Threshold | Value | Style | Color |
|-----------|-------|-------|-------|
| Room temperature | 273 K | dashed | #E63946 |
| Liquid nitrogen | 77 K | dotted | #457B9D |
| Current ambient record (Hg-cuprate) | 135 K | dot-dash | #F4A261 |
| Current high-P record (LaH10) | 250 K | dot-dash | #7400B8 |
| Stability cutoff | 100 meV above hull | dashed | #264653 |
| Max pressure (RTAP) | 1 GPa | dashed | #2A9D8F |
| RTAP convergence target | 0.85 | dashed | #2A9D8F |
| v1 convergence target | 0.95 | dotted | #457B9D |

---

## 6. Figure Style Defaults

```python
import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "#FAFAFA",
    "axes.grid":        True,
    "grid.alpha":       0.3,
    "grid.linestyle":   "--",
    "font.family":      "sans-serif",
    "font.size":        11,
    "axes.titlesize":   14,
    "axes.labelsize":   12,
    "legend.fontsize":  10,
    "figure.dpi":       150,
    "savefig.dpi":      200,
    "savefig.bbox":     "tight",
})
```

---

## 7. Data Loading Boilerplate

Use this at the top of every visualization script:

```python
import pandas as pd
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent  # adjust as needed
DATA_DIR = PROJECT_ROOT / "data"

def load_latest_properties():
    """Load properties.csv from the highest-numbered iteration."""
    synth_dir = DATA_DIR / "synthetic"
    iters = sorted(synth_dir.glob("iteration_*"), key=lambda p: int(p.name.split("_")[1]))
    if not iters:
        raise FileNotFoundError("No iteration directories found")
    return pd.read_csv(iters[-1] / "properties.csv")

def load_latest_candidates():
    """Load novel candidates from highest iteration."""
    cand_dir = DATA_DIR / "novel_candidates"
    files = sorted(cand_dir.glob("candidates_iteration_*.csv"),
                   key=lambda p: int(p.stem.split("_")[-1]))
    if not files:
        raise FileNotFoundError("No candidate files found")
    return pd.read_csv(files[-1])

def load_convergence():
    """Load convergence history."""
    with open(DATA_DIR / "reports" / "convergence_history.json") as f:
        return json.load(f)

def load_final_report():
    """Load final report."""
    with open(DATA_DIR / "reports" / "final_report.json") as f:
        return json.load(f)

def extract_family(df):
    """Add 'family' column from pattern_id."""
    df["family"] = df["pattern_id"].str.rsplit("-", n=1).str[0]
    return df

RTAP_FAMILIES = [
    "kagome", "ternary-hydride", "infinite-layer", "topological",
    "2d-heterostructure", "carbon-based", "engineered-cuprate",
    "mof-sc", "flat-band"
]

def filter_rtap(df):
    """Filter to RTAP-specific families."""
    return df[df["family"].isin(RTAP_FAMILIES)]
```

---

## 8. Output Conventions

- Save all PNGs to `data/exports/` with prefix `rtap_`
- DPI: 200 for publication, 150 for dashboard
- Format: PNG (default), SVG for vector (add `plt.savefig(..., format="svg")`)
- Always call `plt.tight_layout()` before saving
- Always `plt.close(fig)` after saving to free memory
- File naming: `rtap_{chart_type}_{optional_qualifier}.png`
  - Examples: `rtap_tc_violin.png`, `rtap_convergence.png`, `rtap_top_candidates.png`

---

## 9. Quick Reference — Which Chart For What Question

| Question | Chart | Section |
|----------|-------|---------|
| Which families produce RT candidates? | Violin (3.1) | Tc by family |
| What mechanisms reach highest Tc? | Scatter (3.2) | Tc vs lambda |
| Is the optimization converging? | Line+Area (3.3) | Convergence |
| What are the best candidates? | Horizontal bar (3.4) | Top candidates |
| Are high-Tc candidates stable? | Scatter (3.5) | Stability trade-off |
| How diverse are mechanisms? | Pie + bar (3.6) | Mechanism overview |
| What structures dominate? | Stacked bar (3.7) | Crystal systems |
| Family strengths comparison? | Radar (3.8) | RTAP radar |
