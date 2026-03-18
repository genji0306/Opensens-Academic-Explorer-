"""Agent PB v2.0 — Crystal structure prediction from chemical formula.

Usage:
    python -m agent_pb.predict --formula "Ca4 S4"
    python -m agent_pb.predict --formula "Ca4 S4" --algorithm tpe --max-steps 1000
"""
import argparse
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from agent_pb.config import PBConfig, OUTPUT_DIR
from agent_pb.constraints.chemistry import parse_formula

logger = logging.getLogger("AgentPB")


@dataclass
class PBPrediction:
    """A single structure prediction result."""
    rank: int = 0
    structure_id: str = ""
    space_group: int = 1
    space_group_symbol: str = ""
    lattice: dict = field(default_factory=dict)
    formation_energy_eV_atom: float = 999.0
    energy_uncertainty_eV_atom: float = 999.0
    confidence: float = 0.0
    cif_path: str = ""
    wyckoff_sites: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class PBPredictionResult:
    """Complete Agent PB prediction output."""
    agent: str = "agent_pb"
    version: str = "2.0"
    formula: str = ""
    timestamp: str = ""
    predictions: list = field(default_factory=list)
    search_statistics: dict = field(default_factory=dict)
    wall_time_seconds: float = 0.0

    def to_dict(self):
        return {
            "agent": self.agent,
            "version": self.version,
            "formula": self.formula,
            "timestamp": self.timestamp,
            "predictions": [p.to_dict() if hasattr(p, "to_dict") else p
                            for p in self.predictions],
            "search_statistics": self.search_statistics,
            "wall_time_seconds": self.wall_time_seconds,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class AgentPB:
    """Crystal structure prediction via GNN + optimization.

    Combines graph neural network energy models with optimization algorithms
    to predict crystal structures from chemical composition.
    """

    def __init__(self, config: Optional[PBConfig] = None):
        self.config = config or PBConfig()
        self.config.ensure_dirs()
        self._ensemble = None
        self._sym_constraint = None

    def _init_ensemble(self):
        """Lazy-load GNN ensemble."""
        if self._ensemble is None:
            from agent_pb.gnn.ensemble import GNNEnsemble
            self._ensemble = GNNEnsemble(model_names=self.config.model_names)
        return self._ensemble

    def predict(self, formula: str,
                space_group_range: tuple = None,
                algorithm: str = None,
                max_steps: int = None,
                top_k: int = None) -> PBPredictionResult:
        """Predict crystal structure from chemical formula.

        Args:
            formula: Chemical formula, e.g., "Ca4 S4" or "NaCl".
            space_group_range: (min_sg, max_sg), default (2, 230).
            algorithm: "tpe", "pso", or "hybrid".
            max_steps: Maximum optimizer evaluations.
            top_k: Number of top structures to return.

        Returns:
            PBPredictionResult with ranked predictions.
        """
        start = time.time()
        sg_range = space_group_range or self.config.space_group_range
        algo = algorithm or self.config.algorithm
        steps = max_steps or self.config.max_steps
        k = top_k or self.config.top_k

        # Parse formula
        composition = parse_formula(formula.replace(" ", ""))
        if not composition:
            raise ValueError(f"Cannot parse formula: {formula}")

        elements = list(composition.keys())
        element_counts = [int(composition[e]) for e in elements]
        total_atoms = sum(element_counts)

        logger.info(f"Predicting structure for {formula} "
                    f"({total_atoms} atoms, SG {sg_range[0]}-{sg_range[1]}, "
                    f"algo={algo}, max_steps={steps})")

        # Initialize ensemble
        ensemble = self._init_ensemble()

        # Initialize symmetry constraints
        from agent_pb.constraints.symmetry import SymmetryConstraint
        sym = SymmetryConstraint(list(sg_range), element_counts)

        # Build parameter space
        bounds = dict(self.config.lattice_bounds)
        bounds["sg"] = list(sg_range)
        bounds["wp"] = [0, max(sym.max_wyckoff_count, 1)]

        # Add atomic coordinate parameters
        for i in range(1, total_atoms + 1):
            bounds[f"x{i}"] = [0.0, 1.0]
            bounds[f"y{i}"] = [0.0, 1.0]
            bounds[f"z{i}"] = [0.0, 1.0]

        # Energy function: build structure -> predict energy
        from agent_pb.constraints.geometry import GeometryConstraint
        geom = GeometryConstraint()
        eval_count = [0]
        all_results = []

        def energy_fn(params):
            eval_count[0] += 1
            structure = sym.build_structure(params, elements, element_counts)
            if structure is None:
                return 999.0

            # Geometry check
            valid, violations = geom.validate_structure(structure)
            if not valid:
                return 999.0

            # GNN energy prediction
            if ensemble.is_available:
                pred = ensemble.predict(structure)
                energy = pred.mean_energy
            else:
                # Fallback: use volume-based heuristic
                energy = _volume_heuristic_energy(structure, total_atoms)

            if energy < 900:
                all_results.append({
                    "energy": energy,
                    "params": dict(params),
                    "structure": structure,
                })

            return energy

        # Run optimizer
        optimizer = self._create_optimizer(algo, energy_fn, bounds, steps)
        opt_result = optimizer.optimize()

        # Rank and select top-K
        all_results.sort(key=lambda x: x["energy"])
        top_results = all_results[:k]

        # Build output
        predictions = []
        formula_clean = formula.replace(" ", "")
        output_dir = self.config.output_dir / formula_clean
        output_dir.mkdir(parents=True, exist_ok=True)

        for rank, res in enumerate(top_results, 1):
            structure = res["structure"]
            structure_id = f"pb_{formula_clean}_{rank:03d}"

            # Write CIF
            cif_path = output_dir / f"rank_{rank:03d}.cif"
            try:
                from agent_pb.io.cif_io import write_cif
                write_cif(structure, cif_path)
            except Exception as e:
                logger.warning(f"CIF write failed: {e}")
                cif_path = ""

            # Get space group
            try:
                sg_symbol, sg_number = structure.get_space_group_info()
            except Exception:
                sg_symbol, sg_number = "P1", 1

            # Build prediction record
            lattice = structure.lattice
            pred = PBPrediction(
                rank=rank,
                structure_id=structure_id,
                space_group=sg_number,
                space_group_symbol=sg_symbol,
                lattice={
                    "a": round(lattice.a, 4),
                    "b": round(lattice.b, 4),
                    "c": round(lattice.c, 4),
                    "alpha": round(lattice.alpha, 2),
                    "beta": round(lattice.beta, 2),
                    "gamma": round(lattice.gamma, 2),
                },
                formation_energy_eV_atom=round(res["energy"], 4),
                energy_uncertainty_eV_atom=0.0,
                confidence=max(0, min(1, 1 - abs(res["energy"]) / 10)),
                cif_path=str(cif_path),
            )
            predictions.append(pred)

        wall_time = time.time() - start

        result = PBPredictionResult(
            formula=formula,
            timestamp=datetime.now(timezone.utc).isoformat(),
            predictions=predictions,
            search_statistics={
                "total_structures_evaluated": eval_count[0],
                "valid_structures_found": len(all_results),
                "algorithm": algo,
                "max_steps": steps,
                "space_group_range": list(sg_range),
            },
            wall_time_seconds=round(wall_time, 2),
        )

        # Save JSON output
        json_path = output_dir / "predictions.json"
        json_path.write_text(result.to_json())
        logger.info(f"Results saved to {output_dir}")

        return result

    def _create_optimizer(self, algo: str, energy_fn, bounds: dict, max_steps: int):
        """Create the appropriate optimizer."""
        if algo == "tpe":
            from agent_pb.optimizer.tpe_optimizer import TPEOptimizer
            return TPEOptimizer(energy_fn, bounds, max_steps=max_steps,
                                n_init=self.config.n_init, seed=self.config.seed)
        elif algo == "pso":
            from agent_pb.optimizer.pso_optimizer import PSOOptimizer
            return PSOOptimizer(energy_fn, bounds, max_iter=max_steps,
                                seed=self.config.seed)
        elif algo == "hybrid":
            from agent_pb.optimizer.hybrid_optimizer import HybridOptimizer
            return HybridOptimizer(energy_fn, bounds, max_steps=max_steps,
                                   n_init=self.config.n_init, seed=self.config.seed)
        else:
            raise ValueError(f"Unknown algorithm: {algo}. Use 'tpe', 'pso', or 'hybrid'.")

    def predict_from_pattern_card(self, pattern_card: dict) -> PBPredictionResult:
        """Predict using constraints from an existing pattern card."""
        formula = pattern_card.get("representative_compound", "")
        sg = pattern_card.get("space_group_number")
        sg_range = (sg, sg) if sg else self.config.space_group_range

        lattice = pattern_card.get("lattice_params", {})
        if lattice:
            # Narrow bounds around known lattice
            margin = 0.2  # 20% margin
            bounds = {}
            for key in ["a", "b", "c"]:
                val = lattice.get(key, 10.0)
                bounds[key] = [val * (1 - margin), val * (1 + margin)]
            for key in ["alpha", "beta", "gamma"]:
                val = lattice.get(key, 90.0)
                bounds[key] = [max(20, val - 15), min(160, val + 15)]
            self.config.lattice_bounds = bounds

        return self.predict(formula, space_group_range=sg_range)


def _volume_heuristic_energy(structure, total_atoms: int) -> float:
    """Simple volume-based energy heuristic when no GNN is available."""
    vol_per_atom = structure.volume / total_atoms
    # Typical crystals: 8-30 A^3/atom
    if 8 <= vol_per_atom <= 30:
        return -1.0 + abs(vol_per_atom - 15) * 0.05
    return 5.0 + abs(vol_per_atom - 15) * 0.1


def run_agent_pb(formula: str, **kwargs) -> Path:
    """Top-level entry point matching existing agent pattern.

    Returns path to output directory.
    """
    config = PBConfig(formula=formula)
    for k, v in kwargs.items():
        if hasattr(config, k):
            setattr(config, k, v)

    agent = AgentPB(config)
    result = agent.predict(formula, **{k: v for k, v in kwargs.items()
                                        if k in ("space_group_range", "algorithm",
                                                  "max_steps", "top_k")})

    output_dir = config.output_dir / formula.replace(" ", "")
    return output_dir


def main():
    """CLI entry point: python -m agent_pb.predict"""
    parser = argparse.ArgumentParser(
        description="Agent PB v2.0 — Crystal Structure Prediction")
    parser.add_argument("--formula", required=True,
                        help="Chemical formula, e.g., 'Ca4 S4'")
    parser.add_argument("--algorithm", default="hybrid",
                        choices=["tpe", "pso", "hybrid"],
                        help="Optimization algorithm (default: hybrid)")
    parser.add_argument("--max-steps", type=int, default=5000,
                        help="Maximum optimizer evaluations (default: 5000)")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Number of top structures to output (default: 10)")
    parser.add_argument("--sg-min", type=int, default=2,
                        help="Minimum space group number (default: 2)")
    parser.add_argument("--sg-max", type=int, default=230,
                        help="Maximum space group number (default: 230)")
    parser.add_argument("--seed", type=int, default=-1,
                        help="Random seed (-1 for none)")
    parser.add_argument("--gpu", action="store_true",
                        help="Use GPU for model inference")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = PBConfig(
        formula=args.formula,
        algorithm=args.algorithm,
        max_steps=args.max_steps,
        top_k=args.top_k,
        space_group_range=(args.sg_min, args.sg_max),
        seed=args.seed,
        use_gpu=args.gpu,
    )

    agent = AgentPB(config)
    result = agent.predict(args.formula,
                           space_group_range=(args.sg_min, args.sg_max),
                           algorithm=args.algorithm,
                           max_steps=args.max_steps,
                           top_k=args.top_k)

    print(f"\n{'='*60}")
    print(f"Agent PB v2.0 — Prediction Results for {args.formula}")
    print(f"{'='*60}")
    print(f"Total structures evaluated: {result.search_statistics['total_structures_evaluated']}")
    print(f"Valid structures found: {result.search_statistics['valid_structures_found']}")
    print(f"Wall time: {result.wall_time_seconds:.1f}s")
    print(f"\nTop {len(result.predictions)} predictions:")
    for pred in result.predictions:
        p = pred if isinstance(pred, dict) else pred.to_dict()
        print(f"  #{p['rank']}: SG={p['space_group']} ({p['space_group_symbol']}), "
              f"E={p['formation_energy_eV_atom']:.4f} eV/atom, "
              f"a={p['lattice']['a']:.3f} b={p['lattice']['b']:.3f} c={p['lattice']['c']:.3f}")


if __name__ == "__main__":
    main()
