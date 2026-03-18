"""Benchmark report generation — comparison tables and summaries."""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("Benchmarks.Report")


def generate_comparison_table(results: dict,
                              output_path: Optional[Path] = None) -> pd.DataFrame:
    """Generate agent comparison table as DataFrame and optional CSV.

    Args:
        results: Dict of {agent_name: {metric_name: value}}.
        output_path: Optional path to save CSV.

    Returns:
        DataFrame with agents as rows and metrics as columns.
    """
    df = pd.DataFrame.from_dict(results, orient="index")
    df.index.name = "Agent"
    df = df.round(4)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path)
        logger.info(f"Comparison table saved to {output_path}")

    return df


def print_comparison(results: dict):
    """Pretty-print comparison table to console."""
    df = generate_comparison_table(results)

    print(f"\n{'='*70}")
    print("Crystal Agent Benchmark Comparison")
    print(f"{'='*70}")
    print(df.to_string())
    print(f"{'='*70}")

    # Highlight best per metric
    for col in df.columns:
        if col in ("n_predicted", "n_reference", "error"):
            continue
        try:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(values) == 0:
                continue
            # For most metrics, higher is better; for mae/rwp/rmsd, lower is better
            if any(k in col.lower() for k in ("mae", "rwp", "rmsd", "time")):
                best = values.idxmin()
                print(f"  Best {col}: {best} ({values[best]:.4f})")
            else:
                best = values.idxmax()
                print(f"  Best {col}: {best} ({values[best]:.4f})")
        except Exception:
            pass
    print()
