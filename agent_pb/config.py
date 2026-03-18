"""Agent PB configuration — paths, defaults, dataclasses."""
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_PB_ROOT = PROJECT_ROOT / "references" / "legacy_agent_pb"
MODEL_DIR = LEGACY_PB_ROOT / "NN_model"
WYCKOFF_DIR = LEGACY_PB_ROOT / "utils" / "wyckoff_position"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "predictions" / "agent_pb"

# Defaults
DEFAULT_ALGORITHM = "hybrid"
DEFAULT_MAX_STEPS = 5000
DEFAULT_N_INIT = 100
DEFAULT_TOP_K = 10
DEFAULT_SG_RANGE = (2, 230)
DEFAULT_LATTICE_BOUNDS = {
    "a": [2, 30], "b": [2, 30], "c": [2, 30],
    "alpha": [20, 160], "beta": [20, 160], "gamma": [20, 160],
}
ENSEMBLE_UNCERTAINTY_THRESHOLD = 0.15  # eV/atom


@dataclass
class PBConfig:
    """Configuration for an Agent PB prediction run."""
    formula: str = ""
    space_group_range: tuple = DEFAULT_SG_RANGE
    lattice_bounds: dict = field(default_factory=lambda: dict(DEFAULT_LATTICE_BOUNDS))
    algorithm: str = DEFAULT_ALGORITHM
    max_steps: int = DEFAULT_MAX_STEPS
    n_init: int = DEFAULT_N_INIT
    top_k: int = DEFAULT_TOP_K
    model_names: list = field(default_factory=lambda: ["megnet"])
    seed: int = -1
    use_gpu: bool = False
    output_dir: Path = OUTPUT_DIR

    def ensure_dirs(self):
        """Create output directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
