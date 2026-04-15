"""Central configuration for the Riemann discovery loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "riemann"
REPORT_DIR = DATA_DIR / "reports"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"

ZEROS1_URL = "https://www-users.cse.umn.edu/~odlyzko/zeta_tables/zeros1"
ZEROS1_FILE = DATA_DIR / "zeros1.txt"


@dataclass
class LoopConfig:
    """Controls the A -> B -> Ob -> (refine|C) convergence loop."""

    n_zeros: int = 10_000
    target_score: float = 0.95
    max_iterations: int = 200
    damping: float = 0.35
    # Keep loop running until score >= target_score (user request).
    run_until_converged: bool = True
    # Global patience: if no improvement for this many iterations, break.
    patience: int = 40

    # Ob component weights (sum to 1.0).
    weight_match_rate: float = 0.40
    weight_rmse: float = 0.30
    weight_rel_error: float = 0.20
    weight_spacing_fit: float = 0.10

    # Match tolerance (in units of mean spacing near that height).
    match_tol_rel: float = 0.01  # 1% of local spacing -> "matched"
    rmse_scale: float = 1.0  # RMSE reference scale (larger -> more forgiving)

    # Agent A rule: how many correction terms to fit.
    n_correction_terms: int = 3
    residual_spline_knots: int = 24

    # Output.
    flow_log: Path = field(default_factory=lambda: REPORT_DIR / "flow.jsonl")
    convergence_log: Path = field(
        default_factory=lambda: REPORT_DIR / "convergence.jsonl"
    )
    final_report: Path = field(default_factory=lambda: REPORT_DIR / "final_report.json")


def ensure_dirs() -> None:
    for p in (DATA_DIR, REPORT_DIR, CHECKPOINT_DIR):
        p.mkdir(parents=True, exist_ok=True)
