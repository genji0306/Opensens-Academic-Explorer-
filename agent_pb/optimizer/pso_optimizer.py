"""Particle Swarm Optimization — extracted from GN-OA."""
import time
import logging
from typing import Callable

import numpy as np

from agent_pb.optimizer.tpe_optimizer import OptimizationResult

logger = logging.getLogger("AgentPB.Optimizer.PSO")

try:
    from sko.PSO import PSO
    _SKO_AVAILABLE = True
except ImportError:
    _SKO_AVAILABLE = False
    logger.info("scikit-opt not installed. PSO optimizer unavailable.")


class PSOOptimizer:
    """Particle Swarm Optimization for crystal structure search."""

    def __init__(self, energy_fn: Callable, bounds: dict,
                 pop_size: int = 100, max_iter: int = 5000, seed: int = -1):
        if not _SKO_AVAILABLE:
            raise ImportError("scikit-opt is required for PSO optimization. "
                              "Install with: pip install scikit-opt>=0.6.6")
        self.energy_fn = energy_fn
        self.bounds = bounds
        self.pop_size = pop_size
        self.max_iter = max_iter
        self.seed = seed
        self._param_names = list(bounds.keys())

    def optimize(self) -> OptimizationResult:
        """Run PSO and return best result."""
        start = time.time()

        if self.seed != -1:
            np.random.seed(self.seed)

        lb = [self.bounds[k][0] for k in self._param_names]
        ub = [self.bounds[k][1] for k in self._param_names]

        history = []
        eval_count = [0]

        def objective(x):
            eval_count[0] += 1
            params = {name: float(x[i]) for i, name in enumerate(self._param_names)}
            energy = self.energy_fn(params)
            history.append({"step": eval_count[0], "energy": energy})
            return energy

        pso = PSO(
            func=objective,
            n_dim=len(lb),
            pop=self.pop_size,
            max_iter=self.max_iter,
            lb=lb,
            ub=ub,
            w=0.8,
            c1=0.5,
            c2=0.5,
            verbose=False,
        )
        pso.run()

        best_params = {name: float(pso.gbest_x[i])
                       for i, name in enumerate(self._param_names)}
        best_energy = float(pso.gbest_y[0]) if hasattr(pso.gbest_y, '__len__') else float(pso.gbest_y)
        wall_time = time.time() - start

        logger.info(f"PSO completed: {eval_count[0]} evals, "
                    f"best energy={best_energy:.4f}, time={wall_time:.1f}s")

        return OptimizationResult(
            best_params=best_params,
            best_energy=best_energy,
            history=history,
            n_evaluations=eval_count[0],
            wall_time_seconds=wall_time,
        )
