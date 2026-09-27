"""One reproducible 10% audit of act decisions in a named wave."""

from collections import Counter
from hashlib import sha256
from math import ceil


def sample(decisions, *, wave, seed, manager, judge):
    if not all((wave, seed, manager, judge)) or manager == judge:
        raise ValueError("audit requires a seed, wave and independent judge")
    population = [d for d in decisions if d["wave"] == wave and d["route"] == "act"]
    if len({d["id"] for d in population}) != len(population):
        raise ValueError("duplicate decision id")
    ordered = sorted(
        population,
        key=lambda d: (
            sha256((seed + "\0" + wave + "\0" + d["id"]).encode()).hexdigest(),
            d["id"],
        ),
    )
    selected = ordered[: ceil(len(population) * 0.1)]
    strata = Counter(d["question_id"] for d in population)
    covered = Counter(d["question_id"] for d in selected)
    return {
        "wave": wave,
        "seed": seed,
        "manager": manager,
        "judge": judge,
        "population": "decisions routed act in this wave",
        "population_size": len(population),
        "sample_size": len(selected),
        "selected_ids": [d["id"] for d in selected],
        "zero_coverage_strata": sorted(set(strata) - set(covered)),
        "strata": {
            q: {"population": strata[q], "sample": covered[q]} for q in sorted(strata)
        },
        "sampling_bias": "unstratified seeded sample; zero-coverage strata listed",
        "adjudicated": False,
    }
