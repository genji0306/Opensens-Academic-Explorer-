"""CLI tool for comparing crystal prediction agents on standardized datasets.

Usage:
    python -m benchmarks.compare_agents --dataset supercon_24 --agents crystal_agent agent_pb
    python -m benchmarks.compare_agents --list-datasets
"""
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

from benchmarks.datasets import AVAILABLE_DATASETS, load_dataset
from benchmarks.metrics import convergence_score
from benchmarks.report import generate_comparison_table, print_comparison

logger = logging.getLogger("Benchmarks")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "benchmarks" / "results"


class AgentBenchmark:
    """Compare prediction agents on standardized datasets."""

    def __init__(self, dataset: str, agents: list, metrics: list = None):
        self.dataset = dataset
        self.agents = agents
        self.metrics = metrics or ["convergence_score", "n_structures"]

    def run(self) -> dict:
        """Execute benchmarks for all agents on dataset."""
        data = load_dataset(self.dataset)
        results = {}

        for agent_name in self.agents:
            logger.info(f"Benchmarking {agent_name} on {self.dataset}...")
            start = time.time()

            try:
                agent_results = self._benchmark_agent(agent_name, data)
                agent_results["wall_time_seconds"] = round(time.time() - start, 2)
                results[agent_name] = agent_results
            except Exception as e:
                logger.error(f"Benchmark failed for {agent_name}: {e}")
                results[agent_name] = {"error": str(e)}

        return results

    def _benchmark_agent(self, agent_name: str, data: list) -> dict:
        """Run benchmark for a single agent."""
        if agent_name == "crystal_agent":
            return self._benchmark_crystal_agent(data)
        elif agent_name == "agent_pb":
            return self._benchmark_agent_pb(data)
        elif agent_name == "agent_xc":
            return self._benchmark_agent_xc(data)
        else:
            return {"error": f"Unknown agent: {agent_name}"}

    def _benchmark_crystal_agent(self, data: list) -> dict:
        """Benchmark the v1/v2 Crystal Agent (convergence loop)."""
        score = convergence_score()
        return {
            "convergence_score": score,
            "n_structures": len(data),
            "agent_type": "convergence_loop",
        }

    def _benchmark_agent_pb(self, data: list) -> dict:
        """Benchmark Agent PB structure predictions against reference data."""
        from benchmarks.metrics import match_rate, rmsd, energy_mae
        results = {"n_structures": len(data), "agent_type": "gnn_optimization"}

        pb_dir = PROJECT_ROOT / "data" / "predictions" / "agent_pb"
        if not pb_dir.exists():
            results["n_predicted"] = 0
            results["note"] = "No predictions found. Run agent_pb.predict first."
            return results

        # Collect predicted CIF structures
        cif_files = sorted(pb_dir.glob("**/rank_001.cif"))
        results["n_predicted"] = len(cif_files)

        if not cif_files:
            return results

        # Try to load predicted structures and compute metrics vs reference
        try:
            from pymatgen.io.cif import CifParser
            predicted_structures = []
            for cif_path in cif_files:
                try:
                    parser = CifParser(str(cif_path))
                    structures = parser.parse_structures()
                    if structures:
                        predicted_structures.append(structures[0])
                except Exception:
                    pass

            results["n_valid_structures"] = len(predicted_structures)

            # Load reference structures from dataset if available
            reference_structures = self._load_reference_structures(data)
            if predicted_structures and reference_structures:
                results["match_rate"] = match_rate(
                    predicted_structures, reference_structures)
                # Compute pairwise RMSD for matched structures
                rmsd_values = []
                for p, r in zip(predicted_structures, reference_structures):
                    val = rmsd(p, r)
                    if val >= 0:
                        rmsd_values.append(val)
                if rmsd_values:
                    results["mean_rmsd"] = round(
                        sum(rmsd_values) / len(rmsd_values), 4)

            # Load energy predictions from JSON results
            energy_pred, energy_ref = self._load_energy_pairs(pb_dir, data)
            if energy_pred and energy_ref:
                results["energy_mae"] = energy_mae(energy_pred, energy_ref)

        except ImportError:
            logger.info("pymatgen not available — skipping structural metrics.")

        return results

    def _benchmark_agent_xc(self, data: list) -> dict:
        """Benchmark Agent XC XRD predictions against reference data."""
        from benchmarks.metrics import rwp
        import numpy as np
        results = {"n_structures": len(data), "agent_type": "xrd_prediction"}

        xc_dir = PROJECT_ROOT / "data" / "predictions" / "agent_xc"
        if not xc_dir.exists():
            results["n_predicted"] = 0
            results["note"] = "No predictions found. Run agent_xc.predict first."
            return results

        # Count predictions
        json_files = list(xc_dir.glob("**/predictions.json"))
        cif_files = list(xc_dir.glob("**/*.cif"))
        results["n_predicted"] = len(json_files)
        results["n_cif_files"] = len(cif_files)

        if not json_files:
            return results

        # Compute Rwp for predictions that include simulated XRD
        import json
        rwp_values = []
        for jf in json_files:
            try:
                pred_data = json.loads(jf.read_text())
                candidates = pred_data if isinstance(pred_data, list) else pred_data.get("candidates", [])
                for cand in candidates:
                    if "rwp" in cand:
                        rwp_values.append(float(cand["rwp"]))
            except Exception:
                pass

        if rwp_values:
            results["mean_rwp"] = round(sum(rwp_values) / len(rwp_values), 4)
            results["best_rwp"] = round(min(rwp_values), 4)

        # Try structural metrics if CIFs exist
        try:
            from pymatgen.io.cif import CifParser
            from benchmarks.metrics import match_rate
            predicted_structures = []
            for cif_path in sorted(cif_files)[:len(data)]:
                try:
                    parser = CifParser(str(cif_path))
                    structures = parser.parse_structures()
                    if structures:
                        predicted_structures.append(structures[0])
                except Exception:
                    pass

            results["n_valid_structures"] = len(predicted_structures)
            reference_structures = self._load_reference_structures(data)
            if predicted_structures and reference_structures:
                results["match_rate"] = match_rate(
                    predicted_structures, reference_structures)
        except ImportError:
            pass

        return results

    def _load_reference_structures(self, data: list) -> list:
        """Build pymatgen Structure objects from dataset reference data."""
        structures = []
        try:
            from pymatgen.core import Lattice, Structure, Composition
            for record in data:
                try:
                    a = record.get("lattice_a", 0)
                    b = record.get("lattice_b", a)
                    c = record.get("lattice_c", 0)
                    alpha = record.get("lattice_alpha", 90)
                    beta = record.get("lattice_beta", 90)
                    gamma = record.get("lattice_gamma", 90)
                    comp = record.get("composition", "")
                    if not (a > 0 and c > 0 and comp):
                        continue
                    lattice = Lattice.from_parameters(a, b, c, alpha, beta, gamma)
                    composition = Composition(comp)
                    species = [str(el) for el in composition.elements]
                    coords = [[0.0, 0.0, i / max(len(species), 1)]
                              for i in range(len(species))]
                    struct = Structure(lattice, species, coords)
                    structures.append(struct)
                except Exception:
                    pass
        except ImportError:
            pass
        return structures

    def _load_energy_pairs(self, pred_dir: Path, data: list) -> tuple:
        """Load predicted vs reference formation energies."""
        import json
        predicted, reference = [], []

        # Build reference energy lookup from dataset
        ref_energies = {}
        for record in data:
            comp = record.get("composition", "")
            e_ref = record.get("formation_energy_eV_atom")
            if comp and e_ref is not None:
                ref_energies[comp] = float(e_ref)

        # Match predictions to reference
        for pred_json in sorted(pred_dir.glob("**/predictions.json")):
            try:
                results = json.loads(pred_json.read_text())
                formula = results.get("formula", "").replace(" ", "")
                preds = results.get("predictions", [])
                if preds and formula in ref_energies:
                    best = preds[0]
                    e_pred = best.get("formation_energy_eV_atom",
                                     best.get("energy", None))
                    if e_pred is not None and abs(e_pred) < 900:
                        predicted.append(float(e_pred))
                        reference.append(ref_energies[formula])
            except Exception:
                pass

        return predicted, reference

    def save_results(self, results: dict, output_path: Path = None):
        """Save results to CSV."""
        if output_path is None:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = RESULTS_DIR / f"comparison_{self.dataset}_{ts}.csv"

        generate_comparison_table(results, output_path)
        return output_path


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Crystal Agents Benchmark Comparison")
    parser.add_argument("--dataset", default="supercon_24",
                        help=f"Dataset name. Available: {list(AVAILABLE_DATASETS.keys())}")
    parser.add_argument("--agents", nargs="+",
                        default=["crystal_agent", "agent_pb", "agent_xc"],
                        help="Agents to compare (default: all)")
    parser.add_argument("--metrics", nargs="+", default=None,
                        help="Metrics to compute (default: all available)")
    parser.add_argument("--output", default=None,
                        help="Output CSV path (default: auto-generated)")
    parser.add_argument("--list-datasets", action="store_true",
                        help="List available datasets and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.list_datasets:
        print("\nAvailable benchmark datasets:")
        for name, desc in AVAILABLE_DATASETS.items():
            print(f"  {name}: {desc}")
        return

    benchmark = AgentBenchmark(
        dataset=args.dataset,
        agents=args.agents,
        metrics=args.metrics,
    )

    results = benchmark.run()
    print_comparison(results)

    output = Path(args.output) if args.output else None
    path = benchmark.save_results(results, output)
    print(f"Results saved to: {path}")


if __name__ == "__main__":
    main()
