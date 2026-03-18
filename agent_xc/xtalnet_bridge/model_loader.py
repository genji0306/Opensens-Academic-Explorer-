"""Load pre-trained XtalNet CPCP and CCSG model checkpoints."""
import sys
import logging
from pathlib import Path
from typing import Optional

from agent_xc.config import XTALNET_ROOT, XTALNET_SRC, CKPT_DIR, CONF_DIR, SCRIPTS_DIR

logger = logging.getLogger("AgentXC.Bridge.ModelLoader")

# Ensure xtalnet paths are importable
for p in [str(XTALNET_ROOT), str(XTALNET_SRC), str(SCRIPTS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

_TORCH_AVAILABLE = False
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    logger.info("PyTorch not installed. XtalNet models unavailable.")


class XtalNetModelLoader:
    """Load pre-trained CPCP and CCSG model checkpoints.

    Manages the singleton constraint of Hydra config initialization.
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, dataset: str = "hmof_100"):
        if XtalNetModelLoader._initialized:
            return
        self.dataset = dataset
        self._cpcp_model = None
        self._ccsg_model = None
        self._device = "cuda" if _TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
        XtalNetModelLoader._initialized = True

    def load_cpcp_model(self):
        """Load CPCP (PXRD encoder) model from checkpoint."""
        if self._cpcp_model is not None:
            return self._cpcp_model

        if not _TORCH_AVAILABLE:
            logger.error("PyTorch required for CPCP model.")
            return None

        ckpt_dir = CKPT_DIR / self.dataset / "CPCP"
        ckpt_files = list(ckpt_dir.glob("*.ckpt")) if ckpt_dir.exists() else []

        if not ckpt_files:
            logger.warning(f"No CPCP checkpoints found in {ckpt_dir}")
            return None

        try:
            from eval_utils import load_model_ckpt
            # load_model_ckpt returns (model, test_loader, cfg) tuple
            model, _, _ = load_model_ckpt(
                str(ckpt_dir), str(ckpt_files[0]), load_data=False)
            model.to(self._device)
            model.eval()
            self._cpcp_model = model
            logger.info(f"CPCP model loaded from {ckpt_files[0].name}")
        except Exception as e:
            logger.error(f"Failed to load CPCP model: {e}")

        return self._cpcp_model

    def load_ccsg_model(self):
        """Load CCSG (structure generator) model from checkpoint."""
        if self._ccsg_model is not None:
            return self._ccsg_model

        if not _TORCH_AVAILABLE:
            logger.error("PyTorch required for CCSG model.")
            return None

        ckpt_dir = CKPT_DIR / self.dataset / "CCSG"
        ckpt_files = list(ckpt_dir.glob("*.ckpt")) if ckpt_dir.exists() else []

        if not ckpt_files:
            logger.warning(f"No CCSG checkpoints found in {ckpt_dir}")
            return None

        try:
            from eval_utils import load_model_ckpt
            # load_model_ckpt returns (model, test_loader, cfg) tuple
            model, _, _ = load_model_ckpt(
                str(ckpt_dir), str(ckpt_files[0]), load_data=False)
            model.to(self._device)
            model.eval()
            self._ccsg_model = model
            logger.info(f"CCSG model loaded from {ckpt_files[0].name}")
        except Exception as e:
            logger.error(f"Failed to load CCSG model: {e}")

        return self._ccsg_model

    @property
    def is_available(self) -> bool:
        """Check if both models can be loaded."""
        return _TORCH_AVAILABLE and CKPT_DIR.exists()

    @property
    def device(self) -> str:
        return self._device
