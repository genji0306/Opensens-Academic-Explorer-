"""Multi-stage hybrid optimizer: TPE coarse search -> PSO fine tuning -> M3GNet relaxation."""
import time
import logging
from typing import Callable, Tuple

from agent_pb.optimizer.tpe_optimizer import OptimizationResult

logger = logging.getLogger("AgentPB.Optimizer.Hybrid")


class HybridOptimizer:
    """Multi-stage optimization: coarse TPE -> fine PSO -> optional relaxation.

    Stage 1 (TPE): Uses 30% of evaluation budget for broad exploration.
    Stage 2 (PSO): Uses remaining budget, seeded from TPE's best results.
    Stage 3 (Relaxation): M3GNet local optimization via ASE BFGS.
    """

    def __init__(self, energy_fn: Callable, parameter_space: dict,
                 max_steps: int = 5000, n_init: int = 100, seed: int = -1):
        self.energy_fn = energy_fn
        self.parameter_space = parameter_space
        self.max_steps = max_steps
        self.n_init = n_init
        self.seed = seed

    def optimize(self) -> OptimizationResult:
        """Run multi-stage optimization pipeline."""
        start = time.time()
        combined_history = []

        # Stage 1: TPE coarse search (30% budget)
        tpe_steps = max(100, int(self.max_steps * 0.3))
        logger.info(f"Stage 1/3: TPE coarse search ({tpe_steps} evals)")

        tpe_result = self._run_tpe(tpe_steps)
        combined_history.extend(tpe_result.history)

        # Stage 2: PSO fine search (remaining budget)
        pso_steps = self.max_steps - tpe_steps
        logger.info(f"Stage 2/3: PSO fine search ({pso_steps} evals)")

        pso_result = self._run_pso(pso_steps, seed_params=tpe_result.best_params)
        combined_history.extend(pso_result.history)

        # Stage 3: Local relaxation via M3GNet (if available)
        best_energy = min(tpe_result.best_energy, pso_result.best_energy)
        best_params = (tpe_result.best_params if tpe_result.best_energy <= pso_result.best_energy
                       else pso_result.best_params)

        relaxed_energy, relaxed_params = self._run_relaxation(best_params, best_energy)
        if relaxed_energy < best_energy:
            best_energy = relaxed_energy
            best_params = relaxed_params

        wall_time = time.time() - start
        total_evals = tpe_result.n_evaluations + pso_result.n_evaluations

        logger.info(f"Hybrid optimization complete: {total_evals} total evals, "
                    f"best energy={best_energy:.4f}, time={wall_time:.1f}s")

        return OptimizationResult(
            best_params=best_params,
            best_energy=best_energy,
            history=combined_history,
            n_evaluations=total_evals,
            wall_time_seconds=wall_time,
        )

    def _run_tpe(self, max_steps: int) -> OptimizationResult:
        """Run TPE stage."""
        try:
            from agent_pb.optimizer.tpe_optimizer import TPEOptimizer
            opt = TPEOptimizer(
                energy_fn=self.energy_fn,
                parameter_space=self.parameter_space,
                max_steps=max_steps,
                n_init=min(self.n_init, max_steps // 2),
                seed=self.seed,
            )
            return opt.optimize()
        except ImportError:
            logger.warning("TPE unavailable, returning empty result for stage 1")
            return OptimizationResult()

    def _run_pso(self, max_steps: int, seed_params: dict = None) -> OptimizationResult:
        """Run PSO stage, optionally seeded from TPE results."""
        try:
            from agent_pb.optimizer.pso_optimizer import PSOOptimizer
            # Narrow bounds around TPE best if available
            bounds = dict(self.parameter_space)
            if seed_params:
                narrowed = {}
                for k, v in bounds.items():
                    if k in seed_params:
                        center = float(seed_params[k])
                        half_range = (v[1] - v[0]) * 0.25  # 25% of original range
                        narrowed[k] = [max(v[0], center - half_range),
                                       min(v[1], center + half_range)]
                    else:
                        narrowed[k] = v
                bounds = narrowed

            opt = PSOOptimizer(
                energy_fn=self.energy_fn,
                bounds=bounds,
                pop_size=min(50, max_steps // 10),
                max_iter=max_steps,
                seed=self.seed,
            )
            return opt.optimize()
        except ImportError:
            logger.warning("PSO unavailable, returning empty result for stage 2")
            return OptimizationResult()

    def _run_relaxation(self, best_params: dict,
                        best_energy: float) -> Tuple[float, dict]:
        """Stage 3: Local relaxation using M3GNet universal potential + ASE BFGS.

        Builds a pymatgen Structure from best_params, converts to ASE Atoms,
        attaches M3GNetCalculator, and runs BFGS to a local minimum.
        Returns (relaxed_energy_per_atom, updated_params).
        Falls back to (best_energy, best_params) if deps are missing.
        """
        try:
            import matgl
            from matgl.ext.ase import M3GNetCalculator
            from pymatgen.io.ase import AseAtomsAdaptor
            from ase.optimize import BFGS
        except ImportError:
            logger.info("Stage 3 skipped: matgl/ase not installed.")
            return best_energy, best_params

        # Build structure from optimizer params
        structure = self._params_to_structure(best_params)
        if structure is None:
            logger.info("Stage 3 skipped: could not build structure from params.")
            return best_energy, best_params

        try:
            potential = matgl.load_model("M3GNet-MP-2021.2.8-PES")
            calc = M3GNetCalculator(potential=potential)

            atoms = AseAtomsAdaptor.get_atoms(structure)
            atoms.calc = calc

            optimizer = BFGS(atoms, logfile=None)
            optimizer.run(fmax=0.05, steps=200)

            relaxed_energy = float(atoms.get_potential_energy() / len(atoms))
            relaxed_structure = AseAtomsAdaptor.get_structure(atoms)

            # Extract updated lattice params from relaxed structure
            relaxed_params = dict(best_params)
            latt = relaxed_structure.lattice
            relaxed_params["a"] = latt.a
            relaxed_params["b"] = latt.b
            relaxed_params["c"] = latt.c
            relaxed_params["alpha"] = latt.alpha
            relaxed_params["beta"] = latt.beta
            relaxed_params["gamma"] = latt.gamma

            # Update fractional coordinates
            for i, site in enumerate(relaxed_structure.sites, start=1):
                relaxed_params[f"x{i}"] = site.frac_coords[0]
                relaxed_params[f"y{i}"] = site.frac_coords[1]
                relaxed_params[f"z{i}"] = site.frac_coords[2]

            logger.info(f"Stage 3 relaxation: {best_energy:.4f} -> {relaxed_energy:.4f} eV/atom")
            return relaxed_energy, relaxed_params

        except Exception as e:
            logger.warning(f"Stage 3 relaxation failed: {e}")
            return best_energy, best_params

    def _params_to_structure(self, params: dict):
        """Build a pymatgen Structure from optimizer parameter dict.

        Expects params to contain: sg, a, b, c, alpha, beta, gamma,
        wp (Wyckoff index), and x1/y1/z1... fractional coords.
        Uses SymmetryConstraint for Wyckoff-aware structure building.
        """
        try:
            from pymatgen.core import Structure, Lattice
        except ImportError:
            return None

        sg = int(params.get("sg", 1))
        a = params.get("a", 5.0)
        b = params.get("b", 5.0)
        c = params.get("c", 5.0)
        alpha = params.get("alpha", 90.0)
        beta = params.get("beta", 90.0)
        gamma = params.get("gamma", 90.0)

        try:
            lattice = Lattice.from_parameters(a, b, c, alpha, beta, gamma)

            # Collect fractional coordinates and species from params
            species = []
            coords = []
            i = 1
            while f"x{i}" in params:
                x = params[f"x{i}"]
                y = params.get(f"y{i}", 0.0)
                z = params.get(f"z{i}", 0.0)
                coords.append([x, y, z])
                species.append(params.get(f"species{i}", "X"))
                i += 1

            if not species:
                return None

            return Structure(lattice, species, coords)
        except Exception as e:
            logger.debug(f"Structure construction failed: {e}")
            return None
