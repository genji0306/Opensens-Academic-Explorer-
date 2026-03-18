"""GNN ensemble with uncertainty quantification."""
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from agent_pb.gnn.megnet_model import MEGNetPredictor, M3GNetPredictor
from agent_pb.config import ENSEMBLE_UNCERTAINTY_THRESHOLD

logger = logging.getLogger("AgentPB.GNN.Ensemble")


@dataclass
class EnsemblePrediction:
    """Result of ensemble energy prediction."""
    mean_energy: float
    uncertainty: float
    predictions: dict = field(default_factory=dict)  # model_name -> energy

    @property
    def is_confident(self) -> bool:
        return self.uncertainty < ENSEMBLE_UNCERTAINTY_THRESHOLD


class GNNEnsemble:
    """Ensemble of GNN models for energy prediction with uncertainty.

    Currently supports MEGNet. CGCNN, ALIGNN, and M3GNet can be added
    by installing their respective packages.
    """

    def __init__(self, model_names: Optional[list] = None):
        if model_names is None:
            model_names = ["m3gnet", "megnet"]  # prefer m3gnet (pre-trained)

        self._models = {}
        for name in model_names:
            model = self._load_model(name)
            if model is not None:
                self._models[name] = model

        if not self._models:
            logger.warning("No GNN models loaded. Ensemble predictions unavailable.")
        else:
            logger.info(f"Ensemble initialized with {len(self._models)} model(s): "
                        f"{list(self._models.keys())}")

    def _load_model(self, name: str):
        """Load a model by name. Returns None if unavailable."""
        if name == "megnet":
            pred = MEGNetPredictor()
            return pred if pred.is_available else None
        elif name == "cgcnn":
            try:
                from cgcnn.model import CrystalGraphConvNet  # noqa: F401
                logger.info("CGCNN available but not yet integrated.")
            except ImportError:
                logger.info("CGCNN not installed. Skipping.")
            return None
        elif name == "alignn":
            try:
                import alignn  # noqa: F401
                logger.info("ALIGNN available but not yet integrated.")
            except ImportError:
                logger.info("ALIGNN not installed. Skipping.")
            return None
        elif name == "m3gnet":
            pred = M3GNetPredictor()
            return pred if pred.is_available else None
        else:
            logger.warning(f"Unknown model: {name}")
            return None

    def predict(self, structure) -> EnsemblePrediction:
        """Ensemble prediction with uncertainty from model disagreement.

        If only one model is available, uncertainty is estimated via
        bootstrap perturbation of the input structure.
        """
        predictions = {}
        for name, model in self._models.items():
            energy = model.predict_energy(structure)
            if energy < 900:  # filter failures (999.0)
                predictions[name] = energy

        if not predictions:
            return EnsemblePrediction(
                mean_energy=999.0,
                uncertainty=999.0,
                predictions={},
            )

        energies = list(predictions.values())
        mean_energy = float(np.mean(energies))

        if len(energies) >= 2:
            uncertainty = float(np.std(energies))
        else:
            # Single model: estimate uncertainty via lattice perturbation
            uncertainty = self._bootstrap_uncertainty(structure, list(self._models.values())[0])

        return EnsemblePrediction(
            mean_energy=mean_energy,
            uncertainty=uncertainty,
            predictions=predictions,
        )

    def _bootstrap_uncertainty(self, structure, model, n_samples: int = 5,
                               noise_scale: float = 0.01) -> float:
        """Estimate uncertainty by perturbing the structure slightly."""
        try:
            from pymatgen.core import Structure
        except ImportError:
            from pymatgen import Structure

        energies = []
        base_energy = model.predict_energy(structure)
        if base_energy >= 900:
            return 999.0
        energies.append(base_energy)

        for _ in range(n_samples):
            perturbed = structure.copy()
            perturbed.perturb(noise_scale)
            e = model.predict_energy(perturbed)
            if e < 900:
                energies.append(e)

        return float(np.std(energies)) if len(energies) > 1 else 0.1

    def available_models(self) -> list:
        """List of successfully loaded model names."""
        return list(self._models.keys())

    @property
    def is_available(self) -> bool:
        return len(self._models) > 0
