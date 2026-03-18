"""
OAE NeMAD Model Wrapper — Scikit-learn RF/XGBoost for magnetic temperature prediction.

Wraps the NEMAD approach (Random Forest + optional XGBoost) for
predicting Curie/Neel temperatures and FM/AFM/NM classification
from 94-element composition features.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("Benchmarks.NemadModels")

try:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    _SKLEARN = True
except ImportError:
    _SKLEARN = False

try:
    from xgboost import XGBRegressor, XGBClassifier
    _XGB = True
except ImportError:
    _XGB = False


# The 94 element features used by NEMAD (H through Pu)
ELEMENT_COLUMNS = [
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu",
]


def _composition_to_features(composition: str) -> np.ndarray:
    """Convert a chemical formula to a 94-element feature vector.

    Simple parser: reads element symbols and stoichiometric numbers.
    Example: "Fe3O4" -> vector with Fe=3, O=4, rest=0.
    """
    import re
    features = np.zeros(len(ELEMENT_COLUMNS))
    elem_to_idx = {el: i for i, el in enumerate(ELEMENT_COLUMNS)}

    tokens = re.findall(r"([A-Z][a-z]?)([\d.]*)", composition)
    for elem, count_str in tokens:
        count = float(count_str) if count_str else 1.0
        idx = elem_to_idx.get(elem)
        if idx is not None:
            features[idx] = count

    return features


class NemadTempPredictor:
    """Random Forest regressor for Curie/Neel temperature prediction.

    Mirrors the NEMAD approach: uses element composition fractions as features.
    """

    def __init__(self, use_xgboost: bool = False, n_estimators: int = 100):
        if not _SKLEARN:
            raise ImportError("scikit-learn required for NemadTempPredictor")

        self.use_xgboost = use_xgboost and _XGB
        self.n_estimators = n_estimators
        self._model = None

    def fit(self, compositions: list[str], temperatures: list[float]) -> dict:
        """Train on (composition, temperature) pairs.

        Returns a dict with training metrics.
        """
        X = np.array([_composition_to_features(c) for c in compositions])
        y = np.array(temperatures)

        if self.use_xgboost:
            self._model = XGBRegressor(n_estimators=self.n_estimators, random_state=42)
        else:
            self._model = RandomForestRegressor(
                n_estimators=self.n_estimators, random_state=42, n_jobs=-1
            )

        self._model.fit(X, y)

        # Training score
        y_pred = self._model.predict(X)
        mae = float(np.mean(np.abs(y - y_pred)))
        r2 = float(self._model.score(X, y))

        logger.info(f"Trained {'XGBoost' if self.use_xgboost else 'RF'} "
                    f"regressor: MAE={mae:.1f} K, R2={r2:.4f}")
        return {"mae_K": mae, "r2": r2, "n_samples": len(compositions)}

    def predict(self, compositions: list[str]) -> np.ndarray:
        """Predict temperatures for a list of compositions."""
        if self._model is None:
            raise RuntimeError("Model not trained. Call fit() first.")
        X = np.array([_composition_to_features(c) for c in compositions])
        return self._model.predict(X)


class NemadClassifier:
    """Random Forest classifier for FM/AFM/NM classification.

    Type mapping: 0=AFM, 1=FM, 2=NM.
    """

    def __init__(self, use_xgboost: bool = False, n_estimators: int = 100):
        if not _SKLEARN:
            raise ImportError("scikit-learn required for NemadClassifier")

        self.use_xgboost = use_xgboost and _XGB
        self.n_estimators = n_estimators
        self._model = None
        self._label_map = {0: "AFM", 1: "FM", 2: "NM"}

    def fit(self, compositions: list[str], labels: list[int]) -> dict:
        """Train on (composition, label) pairs."""
        X = np.array([_composition_to_features(c) for c in compositions])
        y = np.array(labels)

        if self.use_xgboost:
            self._model = XGBClassifier(n_estimators=self.n_estimators, random_state=42)
        else:
            self._model = RandomForestClassifier(
                n_estimators=self.n_estimators, random_state=42, n_jobs=-1
            )

        self._model.fit(X, y)
        acc = float(self._model.score(X, y))
        logger.info(f"Trained classifier: accuracy={acc:.4f}")
        return {"accuracy": acc, "n_samples": len(compositions)}

    def predict(self, compositions: list[str]) -> list[str]:
        """Predict magnetic class labels for compositions."""
        if self._model is None:
            raise RuntimeError("Model not trained. Call fit() first.")
        X = np.array([_composition_to_features(c) for c in compositions])
        preds = self._model.predict(X)
        return [self._label_map.get(int(p), "NM") for p in preds]
