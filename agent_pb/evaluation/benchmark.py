"""Benchmark harness for Agent PB predictions."""
import logging
from pathlib import Path
from typing import Optional

from agent_pb.evaluation import metrics

logger = logging.getLogger("AgentPB.Evaluation.Benchmark")


class AgentPBBenchmark:
    """Benchmark Agent PB against reference datasets.

    Uses the SuperCon-24 dataset from Agent Ob as default.
    """

    def __init__(self, dataset_name: str = "supercon_24"):
        self.dataset_name = dataset_name
        self._reference = None

    def load_reference_structures(self) -> list:
        """Load reference structures from Agent Ob's experimental data.

        Returns list of dicts: {composition, structure, Tc, space_group, ...}
        """
        if self._reference is not None:
            return self._reference

        try:
            from benchmarks.datasets import load_dataset
            self._reference = load_dataset(self.dataset_name)
            logger.info(f"Loaded {len(self._reference)} reference structures "
                        f"from {self.dataset_name}")
        except ImportError:
            logger.warning("Benchmarks module not available. Using empty reference.")
            self._reference = []

        return self._reference

    def run(self, predict_fn, metric_names: Optional[list] = None) -> dict:
        """Run benchmark and return metrics dict.

        Args:
            predict_fn: Callable(formula) -> Structure or None
            metric_names: Which metrics to compute. Default: all available.

        Returns:
            Dict of metric_name -> value.
        """
        reference = self.load_reference_structures()
        if not reference:
            return {"error": "No reference data available"}

        if metric_names is None:
            metric_names = ["match_rate", "space_group_accuracy", "energy_mae"]

        predicted_structures = []
        predicted_sgs = []
        reference_structures = []
        reference_sgs = []

        for ref in reference:
            formula = ref.get("composition", "")
            try:
                pred = predict_fn(formula)
                if pred is not None:
                    predicted_structures.append(pred)
                    reference_structures.append(ref.get("structure"))

                    try:
                        sg = pred.get_space_group_info()[1]
                        predicted_sgs.append(sg)
                    except Exception:
                        predicted_sgs.append(-1)

                    reference_sgs.append(ref.get("space_group", -1))
            except Exception as e:
                logger.warning(f"Prediction failed for {formula}: {e}")

        results = {}
        if "match_rate" in metric_names and predicted_structures:
            results["match_rate"] = metrics.structure_match_rate(
                predicted_structures, reference_structures)

        if "space_group_accuracy" in metric_names and predicted_sgs:
            results["space_group_accuracy"] = metrics.space_group_accuracy(
                predicted_sgs, reference_sgs)

        if "energy_mae" in metric_names:
            results["energy_mae"] = -1.0  # requires DFT reference

        results["n_predicted"] = len(predicted_structures)
        results["n_reference"] = len(reference)

        return results
