"""GNN energy model wrappers — MEGNet (legacy) and M3GNet (pre-trained).

MEGNet requires trained .hdf5 weights in Agent PB/NN_model/.
M3GNet ships pre-trained via matgl and works out of the box.
"""
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AgentPB.GNN.MEGNet")

# Try importing MEGNet dependencies (legacy)
_MEGNET_AVAILABLE = False
try:
    import numpy as np
    from agent_pb.config import LEGACY_PB_ROOT, MODEL_DIR

    _legacy_path = str(LEGACY_PB_ROOT)
    if _legacy_path not in sys.path:
        sys.path.insert(0, _legacy_path)

    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")
    from NN_model.orig_megnet import OrigMEGNet
    _MEGNET_AVAILABLE = True
except ImportError as e:
    logger.info(f"MEGNet not available: {e}")

# Try importing M3GNet via matgl (pre-trained, no weights file needed)
_M3GNET_AVAILABLE = False
try:
    import matgl
    from matgl.ext.ase import M3GNetCalculator
    _M3GNET_AVAILABLE = True
except ImportError:
    logger.info("matgl not installed. M3GNet predictor unavailable. "
                "Install with: pip install matgl")


class MEGNetPredictor:
    """Wrapper around OrigMEGNet for formation energy prediction.

    Gracefully handles missing tensorflow/megnet installations.
    """

    def __init__(self, model_path: Optional[Path] = None):
        self._model = None
        if not _MEGNET_AVAILABLE:
            logger.warning("MEGNet dependencies not installed. Predictor inactive.")
            return

        if model_path is None:
            candidates = list(MODEL_DIR.glob("*.hdf5")) + list(MODEL_DIR.glob("*.h5"))
            if candidates:
                model_path = candidates[0]
                logger.info(f"Auto-detected model: {model_path.name}")
            else:
                logger.warning(f"No model files found in {MODEL_DIR}. "
                               "Train a model first or provide model_path.")
                return

        try:
            self._model = OrigMEGNet.from_file(str(model_path))
            logger.info(f"MEGNet model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load MEGNet model: {e}")

    def predict_energy(self, structure) -> float:
        """Predict formation energy (eV/atom) for a pymatgen Structure.

        Returns 999.0 if prediction fails.
        """
        if self._model is None:
            return 999.0
        try:
            result = self._model.predict_structure(structure).reshape(-1)[0]
            return float(result)
        except Exception as e:
            logger.debug(f"Prediction failed: {e}")
            return 999.0

    def predict_batch(self, structures: list) -> list:
        return [self.predict_energy(s) for s in structures]

    @property
    def is_available(self) -> bool:
        return self._model is not None


class M3GNetPredictor:
    """M3GNet universal potential via matgl — works out of the box.

    Uses the pre-trained M3GNet-MP-2021.2.8-PES model for
    energy prediction. No custom weights needed.
    """

    def __init__(self):
        self._potential = None
        if not _M3GNET_AVAILABLE:
            logger.warning("matgl not installed. M3GNet predictor inactive.")
            return

        try:
            self._potential = matgl.load_model("M3GNet-MP-2021.2.8-PES")
            logger.info("M3GNet pre-trained potential loaded (MP-2021.2.8-PES)")
        except Exception as e:
            logger.error(f"Failed to load M3GNet potential: {e}")

    def predict_energy(self, structure) -> float:
        """Predict energy (eV/atom) for a pymatgen Structure."""
        if self._potential is None:
            return 999.0
        try:
            from matgl.ext.ase import M3GNetCalculator
            from pymatgen.io.ase import AseAtomsAdaptor
            atoms = AseAtomsAdaptor.get_atoms(structure)
            calc = M3GNetCalculator(potential=self._potential)
            atoms.calc = calc
            energy = atoms.get_potential_energy()
            return float(energy / len(atoms))
        except Exception as e:
            logger.debug(f"M3GNet prediction failed: {e}")
            return 999.0

    def predict_batch(self, structures: list) -> list:
        return [self.predict_energy(s) for s in structures]

    @property
    def is_available(self) -> bool:
        return self._potential is not None
