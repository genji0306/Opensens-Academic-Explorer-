"""Klein-topology helpers for the recursive RH research loop.

The Klein mode treats RH research as a forced round trip:

* descend into a local or simulator-backed lane,
* translate the result through a global analytic lane, and
* return with a stricter off-line-zero exclusion obligation.

This keeps the campaign from orbiting indefinitely around finite-window
evidence or purely descriptive critical-line identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .schemas import HypothesisCandidate


TopologyMode = Literal["baseline", "klein"]
Lane = Literal["surface", "depth", "neutral"]

SURFACE_FAMILIES = frozenset(
    {
        "explicit_formula",
        "xi_function",
        "de_branges",
        "general_analytic",
    }
)
DEPTH_FAMILIES = frozenset(
    {
        "hardy_z",
        "geometric_visualization",
        "quantum_spectral",
        "hilbert_polya",
        "random_matrix",
        "mollifier_moment",
    }
)
GLUE_FAMILIES = frozenset(
    {
        "explicit_formula",
        "xi_function",
        "hardy_z",
        "hilbert_polya",
        "de_branges",
    }
)

_OBSTRUCTION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("finite_window_only", ("finite_window_only", "finite window", "bounded window", "sampled")),
    (
        "global_exclusion_gap",
        ("off-line zeros", "off line zeros", "zero-location exclusion", "global exclusion"),
    ),
    (
        "critical_identity_gap",
        ("critical-line", "critical line", "classical identity", "visual intuition"),
    ),
    (
        "tail_control_gap",
        ("bound all error terms", "tail bound", "explicit formula", "prime oscillations"),
    ),
    (
        "operator_rigor_gap",
        ("operator", "surrogate", "self-adjoint", "spectral", "de branges"),
    ),
    (
        "translation_gap",
        ("translate", "translation", "restate", "invariant", "certificate"),
    ),
)

_NOISE_KEYS = frozenset(
    {
        "action_continue_bounded_validation",
        "novelty_requires_translation",
    }
)


def family_lane(family: str) -> Lane:
    if family in SURFACE_FAMILIES:
        return "surface"
    if family in DEPTH_FAMILIES:
        return "depth"
    return "neutral"


def group_lane_counts(families: tuple[str, ...] | list[str] | set[str]) -> dict[str, int]:
    counts = {"surface": 0, "depth": 0, "neutral": 0}
    for family in families:
        counts[family_lane(str(family))] += 1
    return counts


def is_cross_lane(families: tuple[str, ...] | list[str] | set[str]) -> bool:
    counts = group_lane_counts(families)
    return counts["surface"] > 0 and counts["depth"] > 0


def klein_pairing_bonus(anchor_family: str, partner_family: str) -> float:
    lanes = {family_lane(anchor_family), family_lane(partner_family)}
    if "surface" in lanes and "depth" in lanes:
        bonus = 0.12
        if {anchor_family, partner_family} & GLUE_FAMILIES:
            bonus += 0.04
        if {anchor_family, partner_family} & {"explicit_formula", "xi_function"}:
            bonus += 0.02
        return bonus
    if anchor_family == partner_family:
        return -0.02
    if family_lane(anchor_family) == family_lane(partner_family) != "neutral":
        return -0.03
    return 0.0


def klein_checks_for_families(families: tuple[str, ...]) -> tuple[str, ...]:
    checks: list[str] = []
    if is_cross_lane(families):
        checks.append("klein_crosscap_bridge")
    if is_cross_lane(families) and set(families) & {"explicit_formula", "xi_function"}:
        checks.append("klein_surface_return")
    if set(families) & {"hardy_z", "geometric_visualization"} and set(families) & {"explicit_formula", "xi_function"}:
        checks.append("klein_local_global_glue")
    return tuple(checks)


def klein_feedback_from_failure_counts(failure_counts: dict[str, int]) -> dict[str, tuple[str, ...]]:
    keys = set(failure_counts)
    feedback: dict[str, tuple[str, ...]] = {}
    if "finite_window_only" in keys:
        feedback["B"] = (
            "force the next round to add a surface-return certificate with explicit tail control",
        )
    if {
        "critical_line_identity_is_classical",
        "critical_line_identities_are_classical_and_do_not_exclude_off_line_zeros",
    } & keys:
        feedback["A"] = (
            "pair one depth-local lane with one surface-rigor lane before promoting the next hypothesis",
        )
    if (
        "the_explicit_formula_is_exact_but_not_by_itself_a_proof_of_rh" in keys
        or "global_exclusion_gap" in keys
    ):
        feedback["M"] = (
            "convert local invariants into a round-trip exclusion claim instead of another local descriptive certificate",
        )
    if {
        "surrogate_is_not_unique",
        "spectral_matching_is_not_a_proof",
        "operator_rigor_gap",
    } & keys:
        feedback["Q"] = (
            "only keep operator branches that return through xi or explicit-formula constraints",
        )
    return feedback


@dataclass(frozen=True)
class KleinMetrics:
    surface_ratio: float
    depth_ratio: float
    bridge_score: float
    reintegration_score: float
    obstruction_score: float
    homology_signal: float
    noise_penalty: float
    total_score: float
    dominant_obstructions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_ratio": self.surface_ratio,
            "depth_ratio": self.depth_ratio,
            "bridge_score": self.bridge_score,
            "reintegration_score": self.reintegration_score,
            "obstruction_score": self.obstruction_score,
            "homology_signal": self.homology_signal,
            "noise_penalty": self.noise_penalty,
            "total_score": self.total_score,
            "dominant_obstructions": list(self.dominant_obstructions),
        }


def compute_klein_metrics(
    hypothesis: HypothesisCandidate,
    *,
    campaign_failure_counts: dict[str, int] | None = None,
) -> KleinMetrics:
    counts = group_lane_counts(hypothesis.ingredient_families)
    non_neutral = max(1, counts["surface"] + counts["depth"])
    surface_ratio = counts["surface"] / non_neutral
    depth_ratio = counts["depth"] / non_neutral
    cross_lane = 1.0 if counts["surface"] and counts["depth"] else 0.0
    glue_bonus = min(1.0, len(set(hypothesis.ingredient_families) & GLUE_FAMILIES) / 2.0)
    bridge_score = min(1.0, 0.70 * cross_lane + 0.20 * glue_bonus + 0.10 * surface_ratio)
    reintegration_score = 1.0 - abs(counts["surface"] - counts["depth"]) / non_neutral

    dominant_obstructions = _dominant_obstructions(
        hypothesis.unresolved_proof_obligations,
        hypothesis.risk_flags,
        campaign_failure_counts=campaign_failure_counts or {},
    )
    obstruction_score = min(1.0, len(dominant_obstructions) / 3.0)
    homology_signal = _homology_signal(dominant_obstructions, campaign_failure_counts or {})

    noise_penalty = 0.0
    if not cross_lane:
        noise_penalty += 0.35
    noise_penalty += 0.05 * sum(1 for item in hypothesis.risk_flags if _slug(item) in _NOISE_KEYS)
    noise_penalty += 0.04 * max(0, len(hypothesis.risk_flags) - len(dominant_obstructions))
    noise_penalty = max(0.0, min(1.0, noise_penalty))

    total_score = (
        0.30 * bridge_score
        + 0.25 * reintegration_score
        + 0.25 * obstruction_score
        + 0.20 * homology_signal
        - 0.20 * noise_penalty
    )
    return KleinMetrics(
        surface_ratio=max(0.0, min(1.0, surface_ratio)),
        depth_ratio=max(0.0, min(1.0, depth_ratio)),
        bridge_score=max(0.0, min(1.0, bridge_score)),
        reintegration_score=max(0.0, min(1.0, reintegration_score)),
        obstruction_score=max(0.0, min(1.0, obstruction_score)),
        homology_signal=max(0.0, min(1.0, homology_signal)),
        noise_penalty=noise_penalty,
        total_score=max(0.0, min(1.0, total_score)),
        dominant_obstructions=dominant_obstructions,
    )


def _dominant_obstructions(
    obligations: tuple[str, ...],
    risk_flags: tuple[str, ...],
    *,
    campaign_failure_counts: dict[str, int],
) -> tuple[str, ...]:
    text = " ".join((*obligations, *risk_flags)).lower()
    matches: list[str] = []
    for key, needles in _OBSTRUCTION_RULES:
        if any(needle in text for needle in needles):
            matches.append(key)

    high_mass = sorted(
        (
            key
            for key, value in campaign_failure_counts.items()
            if value >= 8 and key in {"finite_window_only", "global_exclusion_gap", "tail_control_gap"}
        ),
        key=lambda item: (-campaign_failure_counts[item], item),
    )
    for key in high_mass:
        if key not in matches:
            matches.append(key)
    return tuple(matches[:4])


def _homology_signal(obstructions: tuple[str, ...], failure_counts: dict[str, int]) -> float:
    if not obstructions:
        return 0.0
    if not failure_counts:
        return min(1.0, 0.35 + 0.20 * len(obstructions))
    relevant = [float(failure_counts.get(item, 0.0)) for item in obstructions]
    if not relevant:
        return 0.0
    peak = max(float(value) for value in failure_counts.values()) or 1.0
    return max(0.0, min(1.0, sum(relevant) / (len(relevant) * peak)))


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in cleaned.split("_") if part)
