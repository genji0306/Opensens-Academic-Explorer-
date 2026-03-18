"""Agent XC configuration — paths, XRD defaults, model checkpoint locations."""
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
XTALNET_ROOT = PROJECT_ROOT / "references" / "xtalnet"
XTALNET_SRC = XTALNET_ROOT / "xtalnet"
CKPT_DIR = XTALNET_ROOT / "ckpt"
CONF_DIR = XTALNET_ROOT / "conf"
SCRIPTS_DIR = XTALNET_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "predictions" / "agent_xc"

# XRD defaults
DEFAULT_WAVELENGTH = 1.5406  # Cu K-alpha1 (Angstrom)
DEFAULT_TWO_THETA_RANGE = (5.0, 90.0)
DEFAULT_STEP = 0.02  # degrees
DEFAULT_NUM_CANDIDATES = 10

# Savitzky-Golay filter defaults
DEFAULT_SG_WINDOW = 11
DEFAULT_SG_POLYORDER = 3


@dataclass
class XCConfig:
    """Configuration for an Agent XC prediction run."""
    dataset: str = "hmof_100"  # "hmof_100" or "hmof_400"
    wavelength: float = DEFAULT_WAVELENGTH
    two_theta_range: tuple = DEFAULT_TWO_THETA_RANGE
    step: float = DEFAULT_STEP
    num_candidates: int = DEFAULT_NUM_CANDIDATES
    output_dir: Path = OUTPUT_DIR

    @property
    def cpcp_ckpt_dir(self) -> Path:
        return CKPT_DIR / self.dataset / "CPCP"

    @property
    def ccsg_ckpt_dir(self) -> Path:
        return CKPT_DIR / self.dataset / "CCSG"

    def ensure_dirs(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
