"""Agent A — synthesize bounded RH hypotheses from mapped approaches."""
from __future__ import annotations

import hashlib
from itertools import combinations

from .klein_topology import (
    family_lane,
    is_cross_lane,
    klein_checks_for_families,
    klein_pairing_bonus,
)
from .schemas import ApproachCard, HypothesisCandidate

_FAMILY_CONSEQUENCES: dict[str, tuple[str, ...]] = {
    "explicit_formula": (
        "prime reconstruction stays stable under the candidate law",
        "off-line zeros would create detectable prime-side distortion",
    ),
    "hardy_z": (
        "critical-line phase decomposition remains consistent",
        "zero markers align across real and imaginary projections",
    ),
    "hilbert_polya": (
        "a self-adjoint surrogate spectrum remains real under perturbation",
    ),
    "geometric_visualization": (
        "projection features can be restated as a measurable invariant",
    ),
    "quantum_spectral": (
        "toy Hamiltonian gap profiles remain stable under simulation",
    ),
}

_FAMILY_COVERAGE_PRIORITY = (
    "hilbert_polya",
    "de_branges",
    "random_matrix",
    "general_analytic",
    "mollifier_moment",
    "quantum_spectral",
    "geometric_visualization",
    "hardy_z",
    "xi_function",
    "explicit_formula",
)

_QUANTUM_PREFERRED_PARTNERS = (
    "hilbert_polya",
    "explicit_formula",
    "xi_function",
    "hardy_z",
)

# Families whose claims have mechanically checkable semantics against the
# Odlyzko zero table (must match _CHECKABLE_FAMILIES in odlyzko_benchmark.py).
# In hyperloop topology, Agent A biases ranking toward these families so the
# external scorer has actually-falsifiable hypotheses to grade.
_FALSIFIABILITY_CHECKABLE_FAMILIES = frozenset({
    "hardy_z",
    "explicit_formula",
    "de_branges",
    "xi_function",
    "random_matrix",
    "mollifier_moment",
})

# Magnitude of the per-family ranking bonus for checkable families in hyperloop
# mode. Calibrated to be larger than the family-usage spread (max 0.08) and
# the route-lock support bonus, but smaller than route-lock primary, so it
# reshapes the family distribution without overriding explicit route locking.
_HYPERLOOP_FALSIFIABILITY_BONUS = 0.80

# Additional pairing bonus when both anchor and partner are checkable
# (hyperloop wants checkable × checkable cross-lane pairs).
_HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS = 0.30

_ROUTE_LOCK_PRIMARY = {
    "operator": ("quantum_spectral", "hilbert_polya", "de_branges"),
    "symmetrisation": ("xi_function", "de_branges", "hilbert_polya"),
    "explicit_formula": ("explicit_formula", "hardy_z", "xi_function"),
    "tail_control": ("explicit_formula", "hardy_z", "xi_function"),
    "finite_data": ("xi_function", "de_branges"),
    "equivalence_search": ("xi_function", "de_branges"),
}

_ROUTE_LOCK_SUPPORT = {
    "operator": ("xi_function", "explicit_formula", "hardy_z"),
    "symmetrisation": ("explicit_formula", "hardy_z"),
    "explicit_formula": ("random_matrix", "general_analytic", "mollifier_moment"),
    "tail_control": ("general_analytic", "random_matrix"),
    "finite_data": ("explicit_formula", "hardy_z"),
    "equivalence_search": ("explicit_formula", "hardy_z", "general_analytic"),
}


class HypothesisAgent:
    """Combine strong, compatible approaches into explicit candidate hypotheses."""

    name = "A"

    def run(
        self,
        approaches: tuple[ApproachCard, ...],
        *,
        round_index: int,
        max_hypotheses: int,
        topology_mode: str = "baseline",
        prior_evaluations: tuple[dict[str, float], ...] = (),
        feedback: dict[str, tuple[str, ...]] | None = None,
        family_usage: dict[str, int] | None = None,
        family_coverage_round_limit: int = 4,
        overused_family_penalty_start_round: int = 5,
        overused_family_penalty_threshold: int = 4,
        overused_family_penalty_scale: float = 0.03,
        overused_family_penalty_cap: float = 0.18,
        preferred_route_family: str = "",
        route_lock_strict: bool = False,
        route_lock_bonus_primary: float = 0.35,
        route_lock_bonus_support: float = 0.08,
        route_lock_penalty_off_route: float = 0.06,
        falsification_ledger: object | None = None,
    ) -> tuple[HypothesisCandidate, ...]:
        usage = dict(family_usage or {})
        feedback_text = self._feedback_text(feedback or {})
        route_lock_primary, route_lock_support = self._route_lock_sets(preferred_route_family)
        effective_route_lock_strict = bool(route_lock_strict and route_lock_primary)
        ranked = self._rank_approaches(
            approaches,
            prior_evaluations,
            feedback_text,
            usage,
            round_index=round_index,
            overused_family_penalty_start_round=overused_family_penalty_start_round,
            overused_family_penalty_threshold=overused_family_penalty_threshold,
            overused_family_penalty_scale=overused_family_penalty_scale,
            overused_family_penalty_cap=overused_family_penalty_cap,
            route_lock_primary=route_lock_primary,
            route_lock_support=route_lock_support,
            route_lock_strict=effective_route_lock_strict,
            route_lock_bonus_primary=route_lock_bonus_primary,
            route_lock_bonus_support=route_lock_bonus_support,
            route_lock_penalty_off_route=route_lock_penalty_off_route,
            topology_mode=topology_mode,
            falsification_ledger=falsification_ledger,
        )
        candidates: list[HypothesisCandidate] = []
        seen_groups: set[tuple[str, ...]] = set()
        coverage_active = round_index <= max(0, family_coverage_round_limit)

        if coverage_active:
            for group in self._coverage_groups(
                ranked,
                usage,
                max_hypotheses=max_hypotheses,
                topology_mode=topology_mode,
                feedback_text=feedback_text,
                route_lock_primary=route_lock_primary,
                route_lock_support=route_lock_support,
            ):
                key = tuple(sorted(card.approach_id for card in group))
                if key in seen_groups:
                    continue
                if not self._group_matches_route_lock(
                    group,
                    route_lock_primary=route_lock_primary,
                    route_lock_support=route_lock_support,
                    route_lock_strict=effective_route_lock_strict,
                ):
                    continue
                compatible, checks = self._compatibility(group, topology_mode=topology_mode)
                if not compatible:
                    continue
                candidates.append(
                    self._synthesize(
                        group,
                        round_index,
                        checks,
                        topology_mode=topology_mode,
                        feedback_text=feedback_text,
                    )
                )
                seen_groups.add(key)
                if len(candidates) >= max_hypotheses:
                    break

        ranked_pool = ranked[: min(8, len(ranked))]
        for size in (2, 1):
            for group in combinations(ranked_pool, size):
                if len(candidates) >= max_hypotheses:
                    break
                key = tuple(sorted(card.approach_id for card in group))
                if key in seen_groups:
                    continue
                if not self._group_matches_route_lock(
                    group,
                    route_lock_primary=route_lock_primary,
                    route_lock_support=route_lock_support,
                    route_lock_strict=effective_route_lock_strict,
                ):
                    continue
                compatible, checks = self._compatibility(group, topology_mode=topology_mode)
                if not compatible:
                    continue
                candidates.append(
                    self._synthesize(
                        group,
                        round_index,
                        checks,
                        topology_mode=topology_mode,
                        feedback_text=feedback_text,
                    )
                )
                seen_groups.add(key)

        # Hyperloop falsifiability filter: reject candidates whose unresolved
        # obligation load exceeds 2× the count of checkable ingredient families.
        # This is the upstream-of-Gate-7 mechanism: hyperloop refuses to ship
        # candidates that pile up untestable obligations, which is precisely
        # the orbit klein gets stuck in. Rejected candidates are swapped for
        # any remaining acceptable ones from the synthesis pool.
        if topology_mode == "hyperloop":
            def _checkable_count(cand: HypothesisCandidate) -> int:
                return sum(1 for fam in cand.ingredient_families
                           if fam in _FALSIFIABILITY_CHECKABLE_FAMILIES)

            def _accept(cand: HypothesisCandidate) -> bool:
                checkable = _checkable_count(cand)
                obligation_budget = max(1, 1 * checkable)
                return len(cand.unresolved_proof_obligations) <= obligation_budget

            candidates = [c for c in candidates if _accept(c)]

        candidates.sort(key=lambda item: (-item.synthesis_score, item.candidate_id))
        return tuple(candidates[:max_hypotheses])

    def _rank_approaches(
        self,
        approaches: tuple[ApproachCard, ...],
        prior_evaluations: tuple[dict[str, float], ...],
        feedback_text: str,
        family_usage: dict[str, int],
        *,
        round_index: int,
        overused_family_penalty_start_round: int,
        overused_family_penalty_threshold: int,
        overused_family_penalty_scale: float,
        overused_family_penalty_cap: float,
        route_lock_primary: frozenset[str],
        route_lock_support: frozenset[str],
        route_lock_strict: bool,
        route_lock_bonus_primary: float,
        route_lock_bonus_support: float,
        route_lock_penalty_off_route: float,
        topology_mode: str = "baseline",
        falsification_ledger: object | None = None,
    ) -> list[ApproachCard]:
        ingredient_bonus: dict[str, float] = {}
        for item in prior_evaluations:
            for approach_id in item.get("ingredient_approach_ids", ()):
                ingredient_bonus[approach_id] = ingredient_bonus.get(approach_id, 0.0) + float(item.get("score", 0.0))

        # Phase 4: per-family falsification count → ranking penalty.
        # Family contradicted N times anywhere in the ledger gets -0.05 * N
        # (capped -0.30) penalty in approach ranking. Causes Agent A to
        # demote families with poor empirical accuracy across rounds.
        family_falsification_count: dict[str, int] = {}
        if falsification_ledger is not None:
            try:
                family_falsification_count = falsification_ledger.family_falsification_count()
            except AttributeError:
                pass

        def score(card: ApproachCard) -> tuple[float, str]:
            base = float(card.observer_scores.get("baseline_proximity", 0.0))
            penalty = float(card.observer_scores.get("contradiction_burden", 0.0))
            bonus = ingredient_bonus.get(card.approach_id, 0.0) * 0.10
            bonus += max(0.0, 0.08 - 0.02 * family_usage.get(card.family, 0))
            if round_index >= overused_family_penalty_start_round:
                overuse = max(0, family_usage.get(card.family, 0) - overused_family_penalty_threshold)
                penalty += min(overused_family_penalty_cap, overused_family_penalty_scale * overuse)
            bonus += self._family_feedback_bonus(card.family, feedback_text)
            bonus += self._route_lock_bonus(
                card.family,
                route_lock_primary=route_lock_primary,
                route_lock_support=route_lock_support,
                route_lock_strict=route_lock_strict,
                route_lock_bonus_primary=route_lock_bonus_primary,
                route_lock_bonus_support=route_lock_bonus_support,
                route_lock_penalty_off_route=route_lock_penalty_off_route,
            )
            # Hyperloop bias: in hyperloop mode, prefer families whose claims
            # the Odlyzko external benchmark can mechanically grade.
            if topology_mode == "hyperloop" and card.family in _FALSIFIABILITY_CHECKABLE_FAMILIES:
                bonus += _HYPERLOOP_FALSIFIABILITY_BONUS
            # Phase 4: family-level falsification penalty.
            f_count = family_falsification_count.get(card.family, 0)
            penalty += min(0.30, 0.05 * f_count)
            return (base - penalty + bonus, card.approach_id)

        return sorted(approaches, key=score, reverse=True)

    def _coverage_groups(
        self,
        ranked: list[ApproachCard],
        family_usage: dict[str, int],
        *,
        max_hypotheses: int,
        topology_mode: str,
        feedback_text: str,
        route_lock_primary: frozenset[str],
        route_lock_support: frozenset[str],
    ) -> list[tuple[ApproachCard, ...]]:
        family_heads = self._family_heads(ranked)
        # Hyperloop bias: in hyperloop mode, sort checkable families ahead of
        # non-checkable ones (within the same route-lock tier and usage tier).
        # This is what makes hyperloop produce structurally different
        # hypotheses than klein — the upstream half of Gate 7.
        def hyperloop_checkable_rank(family: str) -> int:
            if topology_mode != "hyperloop":
                return 0
            return 0 if family in _FALSIFIABILITY_CHECKABLE_FAMILIES else 1

        ordered_families = sorted(
            family_heads,
            key=lambda family: (
                0 if family in route_lock_primary else 1 if family in route_lock_support else 2,
                hyperloop_checkable_rank(family),
                family_usage.get(family, 0),
                self._family_priority(family),
                -self._approach_strength(family_heads[family]),
            ),
        )
        groups: list[tuple[ApproachCard, ...]] = []
        for family in ordered_families[:max_hypotheses]:
            if len(groups) >= max_hypotheses:
                break
            anchor = family_heads[family]
            if anchor.family == "quantum_spectral":
                for branch_group in self._quantum_branch_groups(
                    anchor,
                    ranked,
                    topology_mode=topology_mode,
                    feedback_text=feedback_text,
                ):
                    groups.append(branch_group)
                    if len(groups) >= max_hypotheses:
                        break
                continue
            partner = self._best_partner(
                anchor,
                ranked,
                family_usage,
                topology_mode=topology_mode,
                feedback_text=feedback_text,
            )
            if partner is not None:
                groups.append((anchor, partner))
            else:
                groups.append((anchor,))
        return groups

    def _family_heads(self, ranked: list[ApproachCard]) -> dict[str, ApproachCard]:
        heads: dict[str, tuple[tuple[float, float, str], ApproachCard]] = {}
        for card in ranked:
            candidate_key = self._family_head_key(card)
            current = heads.get(card.family)
            if current is None or candidate_key > current[0]:
                heads[card.family] = (candidate_key, card)
        return {family: item[1] for family, item in heads.items()}

    def _family_head_key(self, card: ApproachCard) -> tuple[float, float, str]:
        text = f"{card.summary}\n{card.core_claim}".lower()
        literature_bonus = 0.12 if "rh attempt:" in text else 0.0
        quantum_bonus = 0.0
        if card.family == "quantum_spectral":
            if any(token in text for token in ("connes", "bost-connes", "bost connes")):
                quantum_bonus += 0.18
            if "operator language" in text or "calibration" in text:
                quantum_bonus -= 0.08
        return (
            self._approach_strength(card) + literature_bonus + quantum_bonus,
            literature_bonus + quantum_bonus,
            card.approach_id,
        )

    def _best_partner(
        self,
        anchor: ApproachCard,
        ranked: list[ApproachCard],
        family_usage: dict[str, int],
        *,
        topology_mode: str,
        feedback_text: str,
    ) -> ApproachCard | None:
        candidates: list[tuple[float, ApproachCard]] = []
        for partner in ranked:
            if partner.approach_id == anchor.approach_id:
                continue
            if partner.family == anchor.family:
                continue
            compatible, _checks = self._compatibility((anchor, partner), topology_mode=topology_mode)
            if not compatible:
                continue
            score = self._approach_strength(partner)
            score += max(0.0, 0.06 - 0.02 * family_usage.get(partner.family, 0))
            if partner.family in {"explicit_formula", "xi_function", "hardy_z"}:
                score += 0.04
            score += self._family_feedback_bonus(partner.family, feedback_text)
            score += self._pairing_bonus(anchor, partner, topology_mode=topology_mode, feedback_text=feedback_text)
            candidates.append((score, partner))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1].approach_id))
        return candidates[0][1]

    def _quantum_branch_groups(
        self,
        anchor: ApproachCard,
        ranked: list[ApproachCard],
        *,
        topology_mode: str,
        feedback_text: str,
    ) -> list[tuple[ApproachCard, ...]]:
        groups: list[tuple[ApproachCard, ...]] = []
        seen_partners: set[str] = set()
        for family in ("hilbert_polya", "explicit_formula"):
            compatible_candidates: list[ApproachCard] = []
            for partner in ranked:
                if partner.approach_id == anchor.approach_id or partner.family != family:
                    continue
                compatible, _checks = self._compatibility((anchor, partner), topology_mode=topology_mode)
                if compatible:
                    compatible_candidates.append(partner)
            if compatible_candidates:
                compatible_candidates.sort(
                    key=lambda item: (
                        -(
                            self._approach_strength(item)
                            + self._family_feedback_bonus(item.family, feedback_text)
                            + self._pairing_bonus(anchor, item, topology_mode=topology_mode, feedback_text=feedback_text)
                        ),
                        item.approach_id,
                    )
                )
                chosen = compatible_candidates[0]
                if chosen.approach_id not in seen_partners:
                    groups.append((anchor, chosen))
                    seen_partners.add(chosen.approach_id)
        if groups:
            return groups
        fallback = self._best_partner(anchor, ranked, {}, topology_mode=topology_mode, feedback_text=feedback_text)
        return [(anchor, fallback)] if fallback is not None else [(anchor,)]

    def _pairing_bonus(
        self,
        anchor: ApproachCard,
        partner: ApproachCard,
        *,
        topology_mode: str,
        feedback_text: str = "",
    ) -> float:
        # Hyperloop bias: bonus when BOTH lanes of the pair are checkable.
        # Klein pairing bonus is also applied in hyperloop (Klein ⊆ Hyperloop).
        klein_or_hyper = topology_mode in ("klein", "hyperloop")
        dual_checkable_bonus = 0.0
        if topology_mode == "hyperloop":
            if (anchor.family in _FALSIFIABILITY_CHECKABLE_FAMILIES
                    and partner.family in _FALSIFIABILITY_CHECKABLE_FAMILIES):
                dual_checkable_bonus = _HYPERLOOP_DUAL_CHECKABLE_PAIR_BONUS

        if anchor.family == "quantum_spectral":
            try:
                rank = _QUANTUM_PREFERRED_PARTNERS.index(partner.family)
            except ValueError:
                rank = len(_QUANTUM_PREFERRED_PARTNERS)
            bonus = max(0.0, 0.20 - 0.04 * rank)
            if klein_or_hyper:
                bonus += klein_pairing_bonus(anchor.family, partner.family)
            return (
                bonus
                + dual_checkable_bonus
                + self._feedback_pairing_bonus((anchor.family, partner.family), feedback_text)
            )
        if anchor.family == "hilbert_polya" and partner.family == "quantum_spectral":
            base = 0.18 + (klein_pairing_bonus(anchor.family, partner.family) if klein_or_hyper else 0.0)
            return (
                base
                + dual_checkable_bonus
                + self._feedback_pairing_bonus((anchor.family, partner.family), feedback_text)
            )
        base = klein_pairing_bonus(anchor.family, partner.family) if klein_or_hyper else 0.0
        return (
            base
            + dual_checkable_bonus
            + self._feedback_pairing_bonus((anchor.family, partner.family), feedback_text)
        )

    def _route_lock_sets(self, preferred_route_family: str) -> tuple[frozenset[str], frozenset[str]]:
        route = preferred_route_family.strip().lower()
        return (
            frozenset(_ROUTE_LOCK_PRIMARY.get(route, ())),
            frozenset(_ROUTE_LOCK_SUPPORT.get(route, ())),
        )

    def _route_lock_bonus(
        self,
        family: str,
        *,
        route_lock_primary: frozenset[str],
        route_lock_support: frozenset[str],
        route_lock_strict: bool,
        route_lock_bonus_primary: float,
        route_lock_bonus_support: float,
        route_lock_penalty_off_route: float,
    ) -> float:
        if family in route_lock_primary:
            return route_lock_bonus_primary
        if family in route_lock_support:
            return route_lock_bonus_support
        if route_lock_strict and route_lock_primary:
            return -route_lock_penalty_off_route
        return 0.0

    def _group_matches_route_lock(
        self,
        group: tuple[ApproachCard, ...],
        *,
        route_lock_primary: frozenset[str],
        route_lock_support: frozenset[str],
        route_lock_strict: bool,
    ) -> bool:
        if not route_lock_strict or not route_lock_primary:
            return True
        families = {card.family for card in group}
        return bool(families & route_lock_primary)

    def _approach_strength(self, card: ApproachCard) -> float:
        base = float(card.observer_scores.get("baseline_proximity", 0.0))
        penalty = float(card.observer_scores.get("contradiction_burden", 0.0))
        return base - penalty

    def _family_priority(self, family: str) -> int:
        try:
            return _FAMILY_COVERAGE_PRIORITY.index(family)
        except ValueError:
            return len(_FAMILY_COVERAGE_PRIORITY)

    def _compatibility(
        self,
        group: tuple[ApproachCard, ...],
        *,
        topology_mode: str,
    ) -> tuple[bool, tuple[str, ...]]:
        assumptions: set[str] = set()
        exclusive_tags: set[str] = set()
        negated_tags: set[str] = set()
        families = {card.family for card in group}
        checks = ["shared_goal=critical_line"]

        for card in group:
            for assumption in card.assumptions:
                assumptions.add(assumption)
                if assumption.startswith("exclusive:"):
                    exclusive_tags.add(assumption.split(":", 1)[1])
                if assumption.startswith("not:"):
                    negated_tags.add(assumption.split(":", 1)[1])

        if len(exclusive_tags) > 1:
            return False, ("conflict:exclusive_assumptions",)
        if exclusive_tags & negated_tags:
            return False, ("conflict:positive_vs_negative_assumption",)
        if families == {"geometric_visualization", "quantum_spectral"}:
            checks.append("novel_lane_pairing")
        if "explicit_formula" in families and "hardy_z" in families:
            checks.append("phase_prime_bridge")
        if topology_mode == "klein":
            checks.extend(klein_checks_for_families(tuple(sorted(families))))
        return True, tuple(checks + ["no_direct_assumption_conflict"])

    def _synthesize(
        self,
        group: tuple[ApproachCard, ...],
        round_index: int,
        checks: tuple[str, ...],
        *,
        topology_mode: str,
        feedback_text: str = "",
    ) -> HypothesisCandidate:
        families = tuple(sorted(card.family for card in group))
        ingredient_ids = tuple(card.approach_id for card in group)
        assumptions = self._dedupe(item for card in group for item in card.assumptions)
        obligations = self._dedupe(item for card in group for item in card.proof_obligations)
        blockers = self._dedupe(item for card in group for item in card.known_blockers)
        predicted = self._dedupe(
            consequence
            for family in families
            for consequence in _FAMILY_CONSEQUENCES.get(family, ())
        )
        risk_flags = list(blockers)
        if any(family in {"geometric_visualization", "quantum_spectral"} for family in families):
            risk_flags.append("novelty_requires_translation")
        if len(obligations) >= 4:
            risk_flags.append("large_obligation_load")
        if topology_mode == "klein" and len(group) > 1 and not is_cross_lane(families):
            risk_flags.append("klein_same_lane_loop")

        branch_checks = checks
        if topology_mode == "klein" and "klein_surface_return" in branch_checks:
            claim = (
                "Klein return branch: transport a depth-lane critical-line invariant through the "
                "surface analytic lane and demand that it come back as a stricter off-line-zero "
                "exclusion certificate with explicit tail control."
            )
        elif topology_mode == "klein" and "klein_crosscap_bridge" in branch_checks:
            claim = (
                "Klein bridge branch: combine one surface-rigor lane with one depth-local lane so "
                "the next round can test a genuine round-trip argument instead of another one-way heuristic."
            )
        elif families == ("explicit_formula", "hardy_z"):
            claim = (
                "Use the explicit-formula prime bridge and Hardy-Z phase decomposition "
                "to derive a testable invariant that would make off-line zeros incompatible "
                "with both prime oscillations and critical-line amplitude zeros."
            )
        elif families == ("explicit_formula", "quantum_spectral"):
            branch_checks = checks + ("quantum_branch=operator_bridge",)
            claim = (
                "Operator-bridge branch: use the explicit-formula prime bridge to stress-test a "
                "quantum spectral surrogate before promoting any operator-style RH claim."
            )
        elif "hilbert_polya" in families and "quantum_spectral" in families:
            branch_checks = checks + ("quantum_branch=operator_hard",)
            claim = (
                "Operator-hard branch: use simulator-backed operator surrogates to constrain a "
                "Hilbert-Polya style construction, but only promote spectra that survive "
                "explicit-formula and critical-line checks."
            )
        else:
            claim = (
                f"Synthesize {' + '.join(families)} into a bounded RH program that reduces "
                "proof obligations while preserving explicit-formula and critical-line consistency."
            )

        base_score = sum(float(card.observer_scores.get("baseline_proximity", 0.0)) for card in group) / max(len(group), 1)
        base_score += self._group_feedback_bonus(families, feedback_text)
        if topology_mode == "klein":
            if is_cross_lane(families):
                base_score += 0.08
                if set(families) & {"explicit_formula", "xi_function"}:
                    base_score += 0.04
            elif len(group) > 1 and family_lane(families[0]) == family_lane(families[-1]) != "neutral":
                base_score -= 0.06
        base_score -= 0.05 * len(risk_flags)
        digest = hashlib.sha1(f"{round_index}|{'|'.join(ingredient_ids)}".encode("utf-8")).hexdigest()[:12]
        return HypothesisCandidate(
            candidate_id=f"rh-hyp-{round_index:02d}-{digest}",
            claim=claim,
            ingredient_approach_ids=ingredient_ids,
            ingredient_families=families,
            compatibility_checks=branch_checks,
            assumptions=assumptions,
            unresolved_proof_obligations=obligations,
            predicted_consequences=predicted,
            risk_flags=tuple(sorted(set(risk_flags))),
            synthesis_score=max(0.0, min(1.0, base_score)),
        )

    def _feedback_text(self, feedback: dict[str, tuple[str, ...]]) -> str:
        return " ".join(" ".join(values) for values in feedback.values()).lower()

    def _family_feedback_bonus(self, family: str, feedback_text: str) -> float:
        if not feedback_text:
            return 0.0
        bonus = 0.0
        family_tokens = (
            family,
            family.replace("_", " "),
            family.replace("_", "-"),
        )
        if any(token in feedback_text for token in family_tokens):
            bonus += 0.05
        if any(token in feedback_text for token in ("tail control", "tail-control", "error-term", "error budget", "window-escape")):
            if family == "explicit_formula":
                bonus += 0.12
            elif family in {"xi_function", "hardy_z", "general_analytic"}:
                bonus += 0.05
        if any(token in feedback_text for token in ("off-line", "off line", "exclusion")):
            if family in {"explicit_formula", "hardy_z", "xi_function"}:
                bonus += 0.04
        if any(
            token in feedback_text
            for token in (
                "statistical concentration",
                "variance-collapse",
                "variance collapse",
                "sampled-line",
                "sampled line",
                "exceptional-zero",
                "exceptional zero",
            )
        ):
            if family == "random_matrix":
                bonus += 0.12
            elif family in {"explicit_formula", "xi_function", "hardy_z"}:
                bonus += 0.06
        if any(
            token in feedback_text
            for token in (
                "zero atlas",
                "pi-normalized",
                "pi normalized",
                "counting law",
                "2pi",
                "2 pi",
                "zero sum",
                "zero-sum",
            )
        ):
            if family == "geometric_visualization":
                bonus += 0.12
            elif family in {"xi_function", "random_matrix"}:
                bonus += 0.08
        if any(token in feedback_text for token in ("surrogate", "uniqueness")):
            if family in {"hilbert_polya", "de_branges", "xi_function"}:
                bonus += 0.04
            elif family == "quantum_spectral":
                bonus -= 0.02
        if any(
            token in feedback_text
            for token in (
                "lyapunov",
                "unconditional",
                "wasserstein",
                "entropy",
                "dissipation",
                "transport",
                "zero measure",
                "zero-measure",
            )
        ):
            if family in {"explicit_formula", "xi_function"}:
                bonus += 0.12
            elif family == "general_analytic":
                bonus += 0.06
            elif family in {"de_branges", "hardy_z"}:
                bonus -= 0.03
        return bonus

    def _feedback_pairing_bonus(self, families: tuple[str, str], feedback_text: str) -> float:
        if not feedback_text:
            return 0.0
        pair = frozenset(families)
        bonus = 0.0
        if any(token in feedback_text for token in ("tail control", "tail-control", "error-term", "error budget", "window-escape")):
            if pair == {"explicit_formula", "xi_function"}:
                bonus += 0.12
            elif pair == {"explicit_formula", "hardy_z"}:
                bonus += 0.10
            elif pair == {"explicit_formula", "general_analytic"}:
                bonus += 0.06
        if any(token in feedback_text for token in ("off-line", "off line", "exclusion")) and pair in (
            {"explicit_formula", "xi_function"},
            {"explicit_formula", "hardy_z"},
        ):
            bonus += 0.05
        if any(
            token in feedback_text
            for token in (
                "statistical concentration",
                "variance-collapse",
                "variance collapse",
                "sampled-line",
                "sampled line",
                "exceptional-zero",
                "exceptional zero",
            )
        ):
            if pair == {"explicit_formula", "random_matrix"}:
                bonus += 0.12
            elif pair == {"random_matrix", "xi_function"}:
                bonus += 0.10
            elif pair == {"hardy_z", "random_matrix"}:
                bonus += 0.08
        if any(
            token in feedback_text
            for token in (
                "zero atlas",
                "pi-normalized",
                "pi normalized",
                "counting law",
                "2pi",
                "2 pi",
                "zero sum",
                "zero-sum",
            )
        ):
            if pair == {"geometric_visualization", "xi_function"}:
                bonus += 0.14
            elif pair == {"geometric_visualization", "random_matrix"}:
                bonus += 0.10
            elif pair == {"explicit_formula", "geometric_visualization"}:
                bonus += 0.08
        if any(
            token in feedback_text
            for token in (
                "lyapunov",
                "unconditional",
                "wasserstein",
                "entropy",
                "dissipation",
                "transport",
                "zero measure",
                "zero-measure",
            )
        ):
            if pair == {"explicit_formula", "xi_function"}:
                bonus += 0.14
            elif pair in (
                {"explicit_formula", "general_analytic"},
                {"general_analytic", "xi_function"},
            ):
                bonus += 0.08
        return bonus

    def _group_feedback_bonus(self, families: tuple[str, ...], feedback_text: str) -> float:
        if not feedback_text:
            return 0.0
        bonus = sum(self._family_feedback_bonus(family, feedback_text) for family in families) / max(len(families), 1)
        if len(families) >= 2:
            bonus += self._feedback_pairing_bonus((families[0], families[-1]), feedback_text)
        return bonus

    def _dedupe(self, items) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return tuple(ordered)
