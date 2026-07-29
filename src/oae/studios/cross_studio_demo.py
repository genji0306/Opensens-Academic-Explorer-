"""Phase I cross-studio end-to-end demo.

Stitches Material Explorer (Phase D MOF pack) → Simulation Lab
(Phase H) → Snorkel verifier (Phase E) into one deterministic run, so
the Phase I exit criterion "end-to-end cross-studio demo" can be
exercised from a test or the CLI without any external dependencies.

Flow
----
1. Take the top-N MOF family seeds from :class:`MOFPack`.
2. For each candidate submit a ``relaxation`` + ``cv_baseline`` pair to
   the offline :class:`SimulationLab`.
3. Lift the simulation observables into the candidate metadata so the
   Snorkel verifier LFs (``lf_structure_plausibility``,
   ``lf_synthesis_feasibility``, ``lf_mp_energy_sanity``) have
   something to bite on.
4. Run the :class:`SnorkelVerifier` and return a :class:`CrossStudioReport`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.oae.kernel.schemas import VerificationBundle
from src.oae.kernel.verification import SnorkelVerifier, VerifierReport
from src.oae.simulation import SimulationLab, SimulationRequest, SimulationResult


@dataclass
class _DemoCandidate:
    candidate_id: str
    family: str
    composition: str
    mechanism: str = "porous-coordination"
    predicted_property: float = 0.0
    energy_above_hull_meV: float = 0.0
    confidence: float = 0.6
    metadata: dict = field(default_factory=dict)


@dataclass
class _DemoBatch:
    candidates: list[_DemoCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class CrossStudioReport:
    """Output of the Phase I cross-studio demo."""

    n_candidates: int
    simulation_results: tuple[SimulationResult, ...]
    verification_bundles: dict[str, VerificationBundle]
    verifier_report: VerifierReport

    def avg_credibility(self) -> float:
        if not self.verification_bundles:
            return 0.0
        total = sum(
            b.posterior.credibility_prob for b in self.verification_bundles.values()
        )
        return total / len(self.verification_bundles)

    def passes_phase_i(self) -> bool:
        """Exit gate — at least 50 % average credibility on a MOF batch."""
        return self.avg_credibility() >= 0.5 and self.n_candidates >= 3


def _seed_candidates(limit: int) -> list[_DemoCandidate]:
    try:
        from src.oae.domains.mof import MOFPack

        pack = MOFPack()
        families = [getattr(f, "name", "") for f in getattr(pack, "families", ())]
        families = [f for f in families if f][:limit]
    except Exception:
        families = []

    if not families:
        families = ["ZIF", "UiO", "MIL", "HKUST", "PCN"][:limit]

    return [
        _DemoCandidate(
            candidate_id=f"demo-{family.lower()}-000",
            family=family,
            composition=f"{family}-000",
        )
        for family in families
    ]


def run_cross_studio_demo(
    *,
    limit: int = 5,
    lab: SimulationLab | None = None,
    verifier: SnorkelVerifier | None = None,
) -> CrossStudioReport:
    """Execute the cross-studio pipeline and return the Phase I report."""
    lab = lab or SimulationLab()
    verifier = verifier or SnorkelVerifier()

    candidates = _seed_candidates(limit)

    requests: list[SimulationRequest] = []
    for cand in candidates:
        requests.append(
            SimulationRequest(
                kind="relaxation",
                candidate_id=cand.candidate_id,
                composition=cand.composition,
                family=cand.family,
            )
        )
        requests.append(
            SimulationRequest(
                kind="cv_baseline",
                candidate_id=cand.candidate_id,
                composition=cand.composition,
                family=cand.family,
                parameters={"concentration_M": 1e-3, "scan_rate_V_s": 0.1},
            )
        )

    batch = lab.submit_batch(requests)
    simulation_results = batch.results

    # Fold simulation observables back into candidate metadata so the
    # verifier's LFs see a complete picture.
    per_candidate: dict[str, dict[str, float]] = {}
    for result in simulation_results:
        if not result.ok:
            continue
        bucket = per_candidate.setdefault(result.request.candidate_id, {})
        bucket.update({k: float(v) for k, v in result.observables.items()})

    for cand in candidates:
        obs = per_candidate.get(cand.candidate_id, {})
        e_form = obs.get("formation_energy_per_atom_eV")
        e_hull = obs.get("energy_above_hull_meV")
        if e_hull is not None:
            cand.energy_above_hull_meV = e_hull
        cand.metadata.update(
            {
                "has_energy_estimate": e_hull is not None,
                "synthesizability": 0.75,
                "formation_energy_per_atom": e_form if e_form is not None else -1.5,
            }
        )

    bundles, report = verifier.verify_batch(
        _DemoBatch(candidates=candidates),
        domain="mof",
    )

    return CrossStudioReport(
        n_candidates=len(candidates),
        simulation_results=simulation_results,
        verification_bundles=bundles,
        verifier_report=report,
    )
