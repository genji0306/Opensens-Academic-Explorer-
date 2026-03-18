"""Tree-Parzen Estimator (Bayesian) optimizer — extracted from GN-OA."""
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger("AgentPB.Optimizer.TPE")

try:
    import hyperopt as hy
    _HYPEROPT_AVAILABLE = True
except ImportError:
    _HYPEROPT_AVAILABLE = False
    logger.info("hyperopt not installed. TPE optimizer unavailable.")


@dataclass
class OptimizationResult:
    """Result of an optimization run."""
    best_params: dict = field(default_factory=dict)
    best_energy: float = 999.0
    history: list = field(default_factory=list)
    n_evaluations: int = 0
    wall_time_seconds: float = 0.0


def _hy_parameter_setting(name: str, bounds: list, ptype: str = "float"):
    """Create hyperopt parameter space (from legacy algo_utils.py)."""
    if ptype == "int":
        return hy.hp.randint(name, bounds[0], bounds[1] + 1)
    return hy.hp.uniform(name, bounds[0], bounds[1])


class TPEOptimizer:
    """Tree-Parzen Estimator Bayesian optimization for crystal structures."""

    def __init__(self, energy_fn: Callable, parameter_space: dict,
                 max_steps: int = 5000, n_init: int = 100, seed: int = -1):
        if not _HYPEROPT_AVAILABLE:
            raise ImportError("hyperopt is required for TPE optimization. "
                              "Install with: pip install hyperopt>=0.2.7")
        self.energy_fn = energy_fn
        self.parameter_space = parameter_space
        self.max_steps = max_steps
        self.n_init = n_init
        self.seed = seed
        self._history = []

    def optimize(self) -> OptimizationResult:
        """Run TPE optimization and return best result."""
        start = time.time()

        # Build hyperopt search space
        space = {}
        for name, bounds in self.parameter_space.items():
            if name in ("sg",):
                space[name] = _hy_parameter_setting(name, bounds, ptype="int")
            else:
                space[name] = _hy_parameter_setting(name, bounds, ptype="float")

        rstate = None if self.seed == -1 else np.random.RandomState(self.seed)

        trials = hy.Trials()
        algo = hy.partial(hy.tpe.suggest, n_startup_jobs=self.n_init)

        self._eval_count = 0

        def objective(params):
            self._eval_count += 1
            energy = self.energy_fn(params)
            self._history.append({"step": self._eval_count, "energy": energy,
                                  "params": {k: float(v) for k, v in params.items()
                                             if isinstance(v, (int, float))}})
            return {"loss": energy, "status": hy.STATUS_OK}

        best = hy.fmin(
            fn=objective,
            space=space,
            algo=algo,
            max_evals=self.max_steps,
            trials=trials,
            rstate=rstate,
            show_progressbar=False,
        )

        wall_time = time.time() - start
        best_energy = min(t["result"]["loss"] for t in trials.trials
                          if t["result"]["status"] == hy.STATUS_OK)

        logger.info(f"TPE completed: {self._eval_count} evals, "
                    f"best energy={best_energy:.4f}, time={wall_time:.1f}s")

        return OptimizationResult(
            best_params=best,
            best_energy=best_energy,
            history=self._history,
            n_evaluations=self._eval_count,
            wall_time_seconds=wall_time,
        )
