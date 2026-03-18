"""End-to-end PXRD -> crystal structure inference pipeline via XtalNet."""
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

import numpy as np

from agent_xc.config import XTALNET_ROOT, SCRIPTS_DIR
from agent_xc.preprocessing.xrd_reader import XRDPattern
from agent_xc.xtalnet_bridge.model_loader import XtalNetModelLoader

logger = logging.getLogger("AgentXC.Bridge.Inference")

# Add xtalnet scripts to path for eval_utils
for p in [str(SCRIPTS_DIR), str(XTALNET_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

_TORCH_AVAILABLE = False
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass


@dataclass
class XCPrediction:
    """A single crystal structure prediction from XRD data."""
    rank: int = 0
    structure: object = None  # pymatgen Structure or None
    composition: str = ""
    space_group: int = 1
    lattice_params: dict = field(default_factory=dict)
    num_atoms: int = 0
    confidence: float = 0.0
    cif_path: Optional[Path] = None

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "composition": self.composition,
            "space_group": self.space_group,
            "lattice_params": self.lattice_params,
            "num_atoms": self.num_atoms,
            "confidence": self.confidence,
            "cif_path": str(self.cif_path) if self.cif_path else None,
        }


class XtalNetInference:
    """End-to-end PXRD -> crystal structure inference pipeline.

    Wraps XtalNet's CPCP (composition prediction) and CCSG (structure generation)
    modules into a single inference API.
    """

    def __init__(self, model_loader: Optional[XtalNetModelLoader] = None):
        self.loader = model_loader or XtalNetModelLoader()
        self._cpcp = None
        self._ccsg = None

    def _ensure_models(self) -> bool:
        """Load models if not already loaded."""
        if self._cpcp is None:
            self._cpcp = self.loader.load_cpcp_model()
        if self._ccsg is None:
            self._ccsg = self.loader.load_ccsg_model()
        return self._cpcp is not None and self._ccsg is not None

    def predict_from_pattern(self, pattern: XRDPattern,
                             composition_hint: str = None,
                             num_candidates: int = 10) -> List[XCPrediction]:
        """Run full CPCP + CCSG pipeline on a preprocessed XRD pattern.

        Args:
            pattern: Preprocessed XRDPattern (normalized, resampled).
            composition_hint: Optional chemical formula hint.
            num_candidates: Number of structure candidates to generate.

        Returns:
            List of XCPrediction objects ranked by confidence.
        """
        if not _TORCH_AVAILABLE:
            logger.error("PyTorch required for XtalNet inference.")
            return self._fallback_predictions(pattern, composition_hint, num_candidates)

        if not self._ensure_models():
            logger.warning("XtalNet models not loaded. Using fallback predictions.")
            return self._fallback_predictions(pattern, composition_hint, num_candidates)

        try:
            return self._run_xtalnet_inference(pattern, composition_hint, num_candidates)
        except Exception as e:
            logger.error(f"XtalNet inference failed: {e}")
            return self._fallback_predictions(pattern, composition_hint, num_candidates)

    def _run_xtalnet_inference(self, pattern: XRDPattern,
                                composition_hint: str,
                                num_candidates: int) -> List[XCPrediction]:
        """Run actual XtalNet inference using loaded models.

        Follows the eval_utils API:
          construct_input(text, pxrd_x, pxrd_y) -> Batch
          diffusion_gradio(batch, ccsg_model, cpcp_model, num_evals, step_lr) -> dict
          get_pred_structure(batch_idx, idx, data, offset) -> (Structure, rank)
        """
        try:
            from eval_utils import construct_input, diffusion_gradio, get_pred_structure
        except ImportError:
            logger.error("eval_utils not importable. Check xtalnet/scripts/ path.")
            return []

        if not composition_hint:
            logger.error("Composition hint required for XtalNet inference.")
            return []

        # construct_input expects: text (formula), pxrd_x (numpy), pxrd_y (numpy)
        batch = construct_input(
            composition_hint,
            pattern.two_theta,
            pattern.intensity,
        )

        # diffusion_gradio expects: batch, ccsg_model, cpcp_model, num_evals, step_lr
        output = diffusion_gradio(
            batch,
            self._ccsg,
            self._cpcp,
            num_evals=num_candidates,
            step_lr=1e-5,
        )

        # Extract structures from diffusion output
        # get_pred_structure(batch_idx, idx, data) -> (Structure, rank_tensor)
        predictions = []
        for i in range(num_candidates):
            try:
                structure, rank = get_pred_structure(i, 0, output)

                try:
                    sg_symbol, sg_number = structure.get_space_group_info()
                except Exception:
                    sg_symbol, sg_number = "P1", 1

                # Use cosine similarity scores from output for confidence
                confidence = 0.5
                if "score_list" in output and output["score_list"]:
                    scores = torch.cat(output["score_list"]).reshape(-1)
                    if i < len(scores):
                        confidence = float(scores[i].clamp(0, 1))

                lattice = structure.lattice
                pred = XCPrediction(
                    rank=int(rank) if hasattr(rank, 'item') else i + 1,
                    structure=structure,
                    composition=structure.formula,
                    space_group=sg_number,
                    lattice_params={
                        "a": round(lattice.a, 4),
                        "b": round(lattice.b, 4),
                        "c": round(lattice.c, 4),
                        "alpha": round(lattice.alpha, 2),
                        "beta": round(lattice.beta, 2),
                        "gamma": round(lattice.gamma, 2),
                    },
                    num_atoms=len(structure),
                    confidence=confidence,
                )
                predictions.append(pred)
            except Exception as e:
                logger.debug(f"Candidate {i+1} extraction failed: {e}")

        # Sort by rank
        predictions.sort(key=lambda p: p.rank)
        return predictions

    def _extract_peaks(self, pattern: XRDPattern) -> list:
        """Extract peak positions from XRD pattern for XtalNet input."""
        try:
            from scipy.signal import find_peaks
            peak_indices, properties = find_peaks(
                pattern.intensity,
                height=0.05,  # min height (after normalization)
                distance=5,   # min distance between peaks (grid points)
                prominence=0.02,
            )
            peaks = [(float(pattern.two_theta[i]), float(pattern.intensity[i]))
                     for i in peak_indices]
            logger.info(f"Extracted {len(peaks)} peaks from XRD pattern")
            return peaks
        except ImportError:
            # Fallback: use simple threshold
            threshold = np.mean(pattern.intensity) + np.std(pattern.intensity)
            mask = pattern.intensity > threshold
            peaks = [(float(pattern.two_theta[i]), float(pattern.intensity[i]))
                     for i in np.where(mask)[0]]
            return peaks

    def _fallback_predictions(self, pattern: XRDPattern,
                               composition_hint: str,
                               num_candidates: int) -> List[XCPrediction]:
        """Generate placeholder predictions when models are unavailable.

        Uses basic peak analysis to estimate lattice parameters.
        """
        logger.info("Using fallback peak-based predictions (no ML models).")

        peaks = self._extract_peaks(pattern)
        if not peaks:
            return []

        # Estimate d-spacings from peak positions using Bragg's law
        wavelength = pattern.wavelength
        d_spacings = []
        for two_theta, intensity in peaks:
            theta_rad = np.radians(two_theta / 2)
            if theta_rad > 0:
                d = wavelength / (2 * np.sin(theta_rad))
                d_spacings.append(d)

        predictions = []
        if d_spacings:
            # Use largest d-spacing as rough estimate of lattice parameter
            d_max = max(d_spacings)

            pred = XCPrediction(
                rank=1,
                composition=composition_hint or "Unknown",
                space_group=1,
                lattice_params={
                    "a": round(d_max, 3),
                    "b": round(d_max, 3),
                    "c": round(d_max, 3),
                    "alpha": 90.0, "beta": 90.0, "gamma": 90.0,
                },
                num_atoms=0,
                confidence=0.1,
            )
            predictions.append(pred)

        return predictions
