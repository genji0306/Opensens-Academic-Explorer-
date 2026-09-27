"""One-sided binomial error bounds for explicitly declared independent trials."""

import math
from scipy.stats import binomtest


def error_gate(errors, trials, *, independent, unit, limit=0.02):
    if type(errors) is not int or type(trials) is not int or not 0 <= errors <= trials:
        raise ValueError("integer counts must satisfy 0 <= errors <= trials")
    if type(independent) is not bool or not isinstance(unit, str) or not unit.strip():
        raise ValueError("sampling independence and unit must be declared")
    if type(limit) not in (int, float) or not math.isfinite(limit) or not 0 < limit < 1:
        raise ValueError("finite gate limit between zero and one required")
    result = {
        "errors": errors,
        "trials": trials,
        "unit": unit,
        "independent": independent,
        "confidence": 0.95,
        "method": "one-sided Clopper-Pearson",
        "limit": limit,
        "upper95": None,
        "status": "insufficient_evidence",
    }
    if trials and independent:
        result["upper95"] = float(
            binomtest(errors, trials, alternative="less")
            .proportion_ci(0.95, method="exact")
            .high
        )
        if result["upper95"] <= limit:
            result["status"] = "component_pass"
    return result
