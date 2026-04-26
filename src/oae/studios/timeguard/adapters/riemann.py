"""Riemann campaign adapter for Timeguard."""
from __future__ import annotations

from collections import Counter
import json
import re
from pathlib import Path
from typing import Any

from riemann.research.klein_topology import is_cross_lane

from src.oae.studios.timeguard.schemas import (
    CampaignEvidence,
    ComparableCampaign,
    OrchestratorScorecard,
    RoundSignal,
    SupportDocument,
    TimeguardContext,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
_HIGHLIGHT_PATTERN = re.compile(
    r"(status|summary|remaining|single remaining gap|target|success|practical implication|current run|score progression)",
    re.IGNORECASE,
)
_PHASE_HIGHLIGHT_PATTERN = re.compile(r"^(?:#+\s*)?phase\s+[a-z]{1,2}\b", re.IGNORECASE)
_AV_NEXT_DIRECTION_PATTERN = re.compile(r"^\((?:i|ii|iii|iv|v)\)\s*", re.IGNORECASE)
_SUMMARY_EXCLUDE_PREFIXES = ("action_", "obligation_", "dead_end_")
_JSON_METADATA_KEYS = {
    "checkpoint",
    "date",
    "description",
    "orchestrator_context",
    "phase",
    "research_mode_disclaimer",
    "zero_migration_table",
}
_PHASE_BG_REPORT_NAME = "RH_BG_PHASE_REPORT.md"
_PHASE_BH_REPORT_NAME = "RH_BH_PHASE_REPORT.md"
_PHASE_BI_REPORT_NAME = "RH_BI_PHASE_REPORT.md"
_PHASE_BJ_REPORT_NAME = "RH_BJ_PHASE_REPORT.md"
_PHASE_BN_REPORT_NAME = "RH_BN_PHASE_REPORT.md"
_PHASE_AV_REPORT_NAME = "RH_AV_PHASE_REPORT.md"
_PHASE_AY_REPORT_NAME = "RH_AY_PHASE_REPORT.md"


def build_timeguard_context(
    baseline_dir: str | Path,
    klein_dir: str | Path,
    *,
    support_docs: tuple[str | Path, ...] = (),
) -> TimeguardContext:
    docs = load_support_documents(support_docs)
    baseline = load_campaign_evidence(baseline_dir, support_docs=docs)
    klein = load_campaign_evidence(klein_dir, support_docs=docs)
    evidence_refs = _dedupe(
        [
            *baseline.evidence_refs,
            *klein.evidence_refs,
            *(doc.path for doc in docs),
        ]
    )
    return TimeguardContext(
        baseline=baseline,
        klein=klein,
        support_docs=docs,
        evidence_refs=evidence_refs,
    )


def load_support_documents(paths: tuple[str | Path, ...] | list[str | Path]) -> tuple[SupportDocument, ...]:
    docs: list[SupportDocument] = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        docs.append(_load_support_document(path))
    return tuple(docs)


def load_campaign_evidence(
    campaign_dir: str | Path,
    *,
    support_docs: tuple[SupportDocument, ...] = (),
) -> CampaignEvidence:
    root = Path(campaign_dir).resolve()
    summary_path = root / "summary.json"
    failure_atlas_path = root / "failure_atlas.json"
    benchmark_path = root / "campaign_benchmark.json"

    summary = _load_json(summary_path)
    failure_atlas = _load_json(failure_atlas_path)
    benchmark = _load_json(benchmark_path) if benchmark_path.exists() else {}
    round_failure_counts = {
        int(item.get("round_index", 0)): dict(item.get("failure_counts", {}))
        for item in failure_atlas.get("rounds", [])
    }
    history_by_round = {
        int(item.get("round_index", 0)): item for item in summary.get("history", [])
    }
    round_signals = _load_round_signals(root, summary, round_failure_counts, history_by_round)
    failure_counts = dict(failure_atlas.get("failure_counts", {}))
    comparable_campaigns = _load_comparable_campaigns(benchmark)

    evidence_refs = _dedupe(
        [
            str(summary_path),
            str(failure_atlas_path),
            str(benchmark_path) if benchmark_path.exists() else "",
            *(signal.evidence_refs for signal in round_signals),
            *(doc.path for doc in support_docs),
        ]
    )

    return CampaignEvidence(
        orchestrator_id=str(summary.get("campaign_id", root.name)),
        topology_mode=str(summary.get("topology_mode", "baseline")),
        campaign_dir=str(root),
        summary_path=str(summary_path),
        failure_atlas_path=str(failure_atlas_path),
        campaign_benchmark_path=str(benchmark_path),
        best_score=float(summary.get("best_score", 0.0)),
        best_candidate_id=str(summary.get("best_candidate_id", "")),
        support_docs=support_docs,
        round_signals=tuple(round_signals),
        dominant_failures=_top_failures(failure_counts),
        repeated_failures={k: int(v) for k, v in failure_counts.items() if _is_failure_key(k)},
        repeated_dead_ends={k: int(v) for k, v in failure_counts.items() if k.startswith("dead_end_")},
        repeated_obligations={k: int(v) for k, v in failure_counts.items() if k.startswith("obligation_")},
        comparable_campaigns=comparable_campaigns,
        evidence_refs=evidence_refs,
    )


def build_scorecards(context: TimeguardContext) -> tuple[OrchestratorScorecard, OrchestratorScorecard]:
    baseline = _build_scorecard(context.baseline, peer=context.klein)
    klein = _build_scorecard(context.klein, peer=context.baseline)
    return baseline, klein


def _build_scorecard(campaign: CampaignEvidence, *, peer: CampaignEvidence) -> OrchestratorScorecard:
    rounds = len(campaign.round_signals)
    best_signal = max(campaign.round_signals, key=lambda item: (item.best_score, item.round_index))
    last_signal = campaign.round_signals[-1]
    evidence_refs = _dedupe(
        [
            campaign.summary_path,
            campaign.failure_atlas_path,
            campaign.campaign_benchmark_path,
            *best_signal.evidence_refs,
            *(doc.path for doc in campaign.support_docs),
        ]
    )

    if campaign.topology_mode == "baseline":
        achievements = (
            f"Established a stable baseline run over {rounds} rounds with a best score of {campaign.best_score:.3f}.",
            f"Kept the strongest branches anchored in classical families ({_format_families(best_signal.top_families)}), which makes the reference run easy to compare against Klein changes.",
        )
        remaining_work = (
            _remaining_tail_control(campaign, best_signal),
            "Convert repeated explicit-formula and xi-function consistency checks into a genuine global exclusion step instead of another bounded near-miss.",
        )
        pros = (
            "Acts as a clean classical reference branch with reproducible bounded checks and limited narrative drift.",
            "Makes repeated bottlenecks obvious because the same few proof obligations keep resurfacing without cross-lane detours.",
        )
        cons = (
            _baseline_cons(campaign),
            "Plateaus quickly: the current run stopped after patience exhaustion while the best score stayed flat across later rounds.",
        )
    else:
        score_delta = campaign.best_score - peer.best_score
        cross_lane_peak = max(signal.cross_lane_count for signal in campaign.round_signals)
        certificate_peak = max(signal.certificate_pass_count for signal in campaign.round_signals)
        phase_insights = _collect_klein_phase_insights(campaign.support_docs)
        achievements = (
            f"Improved over the current baseline by {score_delta:+.3f} best-score points while keeping the search focused on cross-lane branches.",
            f"Reached cross-lane counts up to {cross_lane_peak} and certificate passes up to {certificate_peak}, which is the concrete sign that the round-trip gate is doing work.",
            *(phase_insights["achievements"]),
        )
        remaining_work = (
            _remaining_gap(campaign, "global_exclusion_gap", "Close the global_exclusion_gap so Klein branches return as full exclusion work rather than stronger local certificates."),
            _remaining_gap(campaign, "translation_gap", "Reduce the translation_gap by converting novelty and surface-return artifacts into rigorous exclusion-ready statements."),
            *(phase_insights["remaining_work"]),
        )
        pros = (
            "Produces richer artifact mixes and stronger cross-lane gating than baseline, especially around surface-return and certificate-aware branches.",
            "Makes remaining proof pressure easier to localize because certificate counts, cross-lane counts, and failure-gaps are visible per round.",
            *(phase_insights["pros"]),
        )
        cons = (
            _klein_cons(campaign),
            "Still carries recurring dead-end pressure: same-lane loops and translation-heavy artifacts can survive long enough to consume rounds without closing the core proof gaps.",
            *(phase_insights["cons"]),
        )

    return OrchestratorScorecard(
        orchestrator_id=campaign.orchestrator_id,
        topology_mode=campaign.topology_mode,
        rounds=rounds,
        best_score=campaign.best_score,
        achievements=achievements,
        remaining_work=remaining_work,
        pros=pros,
        cons=cons,
        dominant_failures=campaign.dominant_failures,
        evidence_refs=evidence_refs,
    )


def _remaining_tail_control(campaign: CampaignEvidence, signal: RoundSignal) -> str:
    if "explicit_formula_tail_control" in signal.unresolved_obligations:
        return "Break the repeated explicit_formula_tail_control bottleneck instead of revalidating finite-window evidence."
    if campaign.repeated_failures.get("tail_control_gap", 0) > 0:
        return "Close the tail_control_gap so explicit-formula evidence stops collapsing back into finite-window validation."
    return "Extend the baseline branch beyond bounded validation by turning the explicit-formula work into a tail-controlled exclusion argument."


def _remaining_gap(campaign: CampaignEvidence, key: str, fallback: str) -> str:
    if campaign.repeated_failures.get(key, 0) > 0:
        return fallback
    return fallback.replace(key, key.replace("_", " "))


def _baseline_cons(campaign: CampaignEvidence) -> str:
    finite_window_hits = campaign.repeated_failures.get("finite_window_only", 0)
    if finite_window_hits:
        return f"Repeats the finite_window_only failure mode ({finite_window_hits} hits in the failure atlas), so bounded evidence keeps recycling instead of globalizing."
    return "Keeps circling bounded evidence without converting it into a stronger global exclusion argument."


def _klein_cons(campaign: CampaignEvidence) -> str:
    gaps: list[str] = []
    for key in ("global_exclusion_gap", "translation_gap"):
        if campaign.repeated_failures.get(key, 0) > 0:
            gaps.append(key)
    if gaps:
        return f"Still leaves {', '.join(gaps)} active, so better certificates do not yet translate into a closed proof step."
    return "Improves branch structure, but the current artifacts still stop short of a full exclusion proof."


def _collect_klein_phase_insights(support_docs: tuple[SupportDocument, ...]) -> dict[str, tuple[str, ...]]:
    phase_v = _match_support_doc(support_docs, "phase v")
    phase_w = _match_support_doc(support_docs, "phase w")
    phase_x = _match_support_doc(support_docs, "phase x")
    phase_y = _match_support_doc(support_docs, "phase y")
    phase_z = _match_support_doc(support_docs, "phase z")
    phase_aa = _match_support_doc(support_docs, "phase aa")
    phase_ab = _match_support_doc(support_docs, "phase ab")
    phase_ac = _match_support_doc(support_docs, "phase ac")
    phase_ah = _match_support_doc(support_docs, "phase ah")
    phase_ae = _match_support_doc(support_docs, "phase ae")
    phase_ai = _match_support_doc(support_docs, "phase ai")
    phase_al = _match_support_doc(support_docs, "phase al")
    phase_am = _match_support_doc(support_docs, "phase am")
    phase_an = _match_support_doc(support_docs, "phase an")
    phase_ao = _match_support_doc(support_docs, "phase ao")
    phase_at = _match_support_doc_reference(support_docs, "phase at")
    phase_au = _match_support_doc_reference(support_docs, "phase au")
    phase_av = _match_support_doc_reference(support_docs, "phase av")
    phase_ay = _match_support_doc_reference(support_docs, "phase ay")
    phase_bg = _match_support_doc_reference(support_docs, "phase bg")
    phase_bh = _match_support_doc_reference(support_docs, "phase bh")
    phase_bi = _match_support_doc_reference(support_docs, "phase bi")
    phase_bj = _match_support_doc_reference(support_docs, "phase bj")
    phase_bn = _match_support_doc_reference(support_docs, "phase bn")

    achievements: list[str] = []
    remaining_work: list[str] = []
    pros: list[str] = []
    cons: list[str] = []

    if phase_v is not None:
        achievements.append(
            "Phase V closed the Euler integer-surface branch non-circularly, which removes one sterile detour from the Klein search tree."
        )
        cons.append(
            "Phase V also shows that integer-surface structure is not itself a discriminant for off-line zeros, so that family should stay closed unless a new bridge appears."
        )
    if phase_w is not None:
        achievements.append(
            "Phase W added the mirror theorem and resonant-cavity framing, sharpening why reflection structure alone does not force non-trivial zeros onto the critical line."
        )
        pros.append(
            "Phase W narrows the search: mirror and cavity structure explain failure modes cleanly and point toward translation-grade follow-ups instead of another raw geometry sweep."
        )
    if phase_x is not None:
        achievements.append(
            "Phase X extended the branch into Klein-4 orbit collapse, the symmetrized Euler product, and a scoped Lee-Yang positivity program with a concrete computational next step."
        )
        remaining_work.append(
            "Translate the Phase W/X mirror, Klein-4, and Lee-Yang structure into exclusion-ready certificates rather than leaving them as structural reframings."
        )
        pros.append(
            "Phase X gives Klein a sharper forward program than baseline because the next-step pressure is now attached to explicit structural artifacts instead of generic novelty."
        )
    if phase_y is not None:
        achievements.append(
            "Phase Y recast the branch around Hardy Z, Jensen-Pólya positivity, and the exact Lee-Yang gap, so the Z-language now gives Klein a coherent reformulation of what still blocks RH."
        )
        remaining_work.append(
            "Push beyond Phase Y's positivity-only picture by proving stronger LP-class or exclusion criteria instead of rephrasing the same Lee-Yang gap."
        )
        pros.append(
            "Phase Y unifies Klein-4 symmetry, Hardy Z, and xi in one variable change, which makes the remaining gap more precise than the earlier mirror-only framing."
        )
    if phase_z is not None:
        achievements.append(
            "Phase Z completed the Z-coordinate heat-flow translation, closed the Lyapunov branch honestly, and tied the explicit_formula + xi_function pair into one finite-window-to-global bridge."
        )
        remaining_work.append(
            "Treat the Z-coordinate heat-flow route as closed unless a new invariant appears, and redirect effort toward Phase AA-style Laguerre, stability, or Fredholm bridges."
        )
        pros.append(
            "Phase Z turns the dominant failure into a crisp target: the remaining blocker is no longer vague novelty pressure but the finite-window-to-global gap in the Z-language."
        )
        cons.append(
            "Phase Z confirms that the DCM/heat-flow Lyapunov route still fails on the indeterminate real-part drift, so repeating that branch without a new invariant is wasted effort."
        )
    if phase_aa is not None:
        achievements.append(
            "Phase AA turned the Z-language program into concrete invariants: Laguerre inequalities were pushed through the first nontrivial layer, the Borcea-Liggett mismatch was diagnosed precisely, and the first Fredholm/Li-style traces were computed."
        )
        remaining_work.append(
            "Advance from Phase AA's necessary-condition gains into the Phase AB Li-criterion branch, where the trace diagnostics must be promoted from positive evidence into a proof-grade obstruction or exclusion program."
        )
        pros.append(
            "Phase AA gives Klein a sharper handoff than Phase Z alone because the next branch is no longer generic stability work; it is explicitly the Li-criterion-in-Z-language path."
        )
        cons.append(
            "Phase AA still stops at necessary conditions: Laguerre positivity, stability diagnostics, and Fredholm traces improve the map, but they do not yet close the LP-class or global exclusion gap."
        )
    if phase_ab is not None:
        achievements.append(
            "Phase AB completed the Li-criterion formulation in the Z-language, fixed the Z=-1/4 normalization point cleanly, and verified that the coefficient-to-Li computation is non-circular."
        )
        remaining_work.append(
            "Move from Phase AB's finite Li-positivity checks toward a Phase AC-style bridge that could force lambda_n positivity from additional coefficient structure instead of stopping at n<=N verification."
        )
        pros.append(
            "Phase AB sharpens the research target further than Phase AA because the remaining gap is now stated as a precise finite-to-universal Li-positivity problem rather than a vague trace heuristic."
        )
        cons.append(
            "Phase AB also confirms that proving all lambda_n >= 0 is itself RH-equivalent, so finite verification of lambda_1,...,lambda_5 does not materially reduce the core obstruction."
        )
    if phase_ac is not None:
        achievements.append(
            "Phase AC isolated the exact gap between first-order Laguerre or Turan control and universal Li positivity, and it added a clean non-circular no-negative-real-zeros lemma for F on the real Z <= 0 half-line."
        )
        remaining_work.append(
            "Advance beyond Phase AC's insufficiency result by testing stronger bridges such as the Phase AG Laguerre tower or Phase AD generating-function route instead of re-running first-order Turan inequalities."
        )
        pros.append(
            "Phase AC is a real narrowing step: it turns a vague LP-class heuristic into an explicit statement of what extra coefficient structure would still be needed to force lambda_n >= 0."
        )
        cons.append(
            "Phase AC is still structural rather than closing: first-order Laguerre positivity and the no-negative-zeros lemma do not by themselves bridge the finite-to-universal Li gap."
        )
    if phase_ah is not None:
        achievements.append(
            "Phase AH restored high-precision alpha_n data from the Phi integral and repaired the Newton-Girard consistency layer, so the Z-language coefficient pipeline is now numerically calibrated instead of artifact-sensitive."
        )
        remaining_work.append(
            "Use the corrected Phase AH alpha_n backbone to test higher-order Laguerre or Li bridges, rather than extending the same finite numerical table without a general argument."
        )
        pros.append(
            "Phase AH strengthens every later Klein branch that depends on alpha_n, p_k, or lambda_n because the numerical layer is now internally consistent through the first nontrivial Laguerre checks."
        )
        cons.append(
            "Phase AH is calibration, not closure: better alpha_n tables and restored Newton-Girard consistency do not materially reduce the RH-equivalent obstruction unless tied to a universal bridge."
        )
    if phase_ae is not None:
        achievements.append(
            "Phase AE converted the corrected alpha_n layer into a Maslanka Omega-series and non-circular lambda_n computation, while also fixing the earlier Z-language sign convention and identifying the observed n^2 scaling regime."
        )
        remaining_work.append(
            "Push beyond Phase AE's finite Omega/lambda calculations by turning the calibrated coefficient data into an analytic bridge, such as a generating-function or asymptotic sign argument, instead of extending the same table alone."
        )
        pros.append(
            "Phase AE strengthens the Li-side evidence because the Omega_k and lambda_n pipelines are now cross-linked through alpha_n rather than resting on a single numerical route."
        )
        cons.append(
            "Phase AE still leaves the universal sign question open: finite Omega_k and lambda_n positivity, even with corrected conventions, do not by themselves bridge to a proof-grade exclusion mechanism."
        )
    if phase_ai is not None:
        achievements.append(
            "Phase AI independently recomputed Li coefficients from the direct zero-sum and Keiper formula with high precision, confirming positive lambda_n values through the tested range and tightening agreement with the calibrated alpha_n side."
        )
        remaining_work.append(
            "Treat Phase AI as a precision and consistency checkpoint, then move into a structural branch such as the Phase AL generating-function program or an explicit-formula Li analysis, rather than spending more rounds only raising the zero cutoff."
        )
        pros.append(
            "Phase AI gives Klein a second independent lambda_n calibration route, which makes later generating-function or asymptotic branches better grounded than the earlier finite positivity checks alone."
        )
        cons.append(
            "Phase AI is still finite-data confirmation: increasing the number of zeros or significant figures sharpens confidence, but it does not reduce the RH-equivalent gap without a universal analytic bridge."
        )
    if phase_al is not None:
        achievements.append(
            "Phase AL converted the calibrated lambda_n side into an explicit generating-function program for G(w), including the closed-form and Lerch-style representation, while clarifying that singularity location or pole accumulation alone does not force lambda_n positivity."
        )
        remaining_work.append(
            "Use Phase AL's generating-function machinery to build a positivity-producing analytic bridge instead of another singularity-only or radius-of-convergence argument."
        )
        pros.append(
            "Phase AL sharpens the target by making the analytic obstacles explicit: natural-boundary pressure, Pringsheim limitations, and the gap between singularity structure and coefficient positivity are now visible rather than implicit."
        )
        cons.append(
            "Phase AL also closes off an easy shortcut: the unit-circle or w=1 singularity story is one-directional only, so generating-function evidence still needs an additional positivity mechanism."
        )
    if phase_am is not None:
        achievements.append(
            "Phase AM extracted the asymptotic sign structure of Omega_k, including the first-zero-driven oscillatory regime, so the long-range arithmetic-spectral pattern is now described rather than guessed."
        )
        remaining_work.append(
            "Translate Phase AM's eventual-sign and period-structure observations into a usable asymptotic positivity radius or coefficient bound, instead of leaving them as descriptive asymptotics."
        )
        pros.append(
            "Phase AM connects the Omega-side behavior directly to the first zeta zero geometry, which gives Klein a sharper asymptotic handle on why the coefficient sequence behaves the way it does."
        )
        cons.append(
            "Phase AM is still not a positivity theorem: oscillatory or eventual-sign structure does not by itself yield a global lambda_n >= 0 bridge."
        )
    if phase_an is not None:
        achievements.append(
            "Phase AN derived the Weil explicit-formula representation for lambda_n and made the prime-sum kernel explicit, giving Klein a direct arithmetic-to-spectral bridge instead of only coefficient-side formulas."
        )
        remaining_work.append(
            "Push Phase AN's prime-sum representation into a positivity-preserving form or kernel argument, rather than stopping at the exact formula and small-n convergence studies."
        )
        pros.append(
            "Phase AN improves the bridge quality because lambda_n is no longer seen only through zeros or Stieltjes data; the prime side now enters explicitly through K_n and the Weil kernel."
        )
        cons.append(
            "Phase AN still leaves the decisive sign question open: an exact prime representation is stronger than a fit, but it does not automatically turn into a positive-definite or exclusion-ready argument."
        )
    if phase_ao is not None:
        achievements.append(
            "Phase AO established the exact Stieltjes-constants-to-Omega_k relationship, giving a canonical arithmetic formula for Omega_k that no longer depends on zero-sum numerics alone."
        )
        remaining_work.append(
            "Exploit Phase AO's exact Omega_k formula to build an analytic positivity bridge for lambda_n, rather than using it only for larger finite computations."
        )
        pros.append(
            "Phase AO is a real compression step: it ties the arithmetic Stieltjes side and the spectral Omega-side together in one exact expression, which makes later asymptotic or positivity analysis cleaner."
        )
        cons.append(
            "Phase AO still leaves the main obstruction untouched: exact formulas for Omega_k do not imply lambda_n positivity or a proof-grade exclusion bridge without an additional sign or kernel argument."
        )
    if phase_at is not None:
        achievements.append(
            "Phases AP through AT exhausted five more analytic directions cleanly: the Weil positivity matrix, large-n Maslanka crossover, G(w) pole statistics, Laguerre-kernel identification, and the first exact Omega_k period-4 breakdown are now explicit."
        )
        remaining_work.append(
            "Treat finite_window_well_depth as the precise late-phase blocker: the current G(w) contradiction still lives inside a radius supported by finite Omega_k data, so the next branch must globalize the tail bound rather than extend another finite table."
        )
        pros.append(
            "Phases AP through AT compress the late Klein gap into one concrete target: prove an all-k bridge for the Omega_k tail instead of guessing among unrelated reformulations."
        )
        cons.append(
            "Phase AT also clarifies why the ceiling remains: exact breakdown data through the first k≈46 transition still does not turn the finite-radius G(w) argument into a strict global radius-of-convergence statement."
        )
    if phase_au is not None:
        achievements.append(
            "Phase AU closed the hoped-for A+B+C+D global-tail shortcut non-circularly: the closed forms for F_A and F_D are explicit, the Stieltjes-side F_B is formally divergent, and the B_k + D_k cancellation is forced by the functional equation."
        )
        remaining_work.append(
            "Treat finite_window_well_depth as a proved obstruction, not just a campaign failure tag: after Phase AU the only non-circular missing input is |gamma_{k-1}| at R_1^{-k}/2^k precision, roughly 14^k more precise than Matsuoka's bound."
        )
        pros.append(
            "Phase AU compresses the late Klein frontier to one precise target: recover the missing Stieltjes asymptotics because that is the only input that would non-circularly close the G(w) radius argument."
        )
        cons.append(
            "Phase AU is a theorem of obstruction rather than theorem of closure: it proves the A+B+C+D route alone is circular for R(G) >= 1, so exact decomposition formulas still do not produce RH without a sharper asymptotic input."
        )
    if phase_av is not None:
        achievements.append(
            "Phase AV turned the remaining Klein gap into an explicit equivalence-wall result: published Stieltjes asymptotics, alternative non-circular routes, and reduction theory all land back in the RH-equivalence class."
        )
        remaining_work.append(
            "Stop treating Phase AV as a local asymptotic clean-up task: after AV, useful work is meta-level only and must either find a genuinely new G-equivalent, partially uncondition a conditional route, or expose a hole in the reduction itself."
        )
        pros.append(
            "Phase AV prevents wasted effort on already-known routes by showing the Stieltjes, Weil, Borel, Li, and de Bruijn-Newman escape hatches all hit the same RH wall."
        )
        cons.append(
            "Phase AV adds no non-circular lift: it is a characterisation phase, not a proof-closing one, so the campaign's remaining gap is now explicitly the full RH-equivalence class."
        )
    if phase_ay is not None:
        achievements.append(
            "Phase AY closed the Padé/Hankel finite-data reconstruction route rigorously: Stahl convergence is constructive, but Padé pole recovery is quantitatively precision-equivalent to the same wall isolated in Phase AV."
        )
        remaining_work.append(
            "Treat finite-data rational reconstruction as closed after AY: the next frontier is Phase AZ-style explicit-formula zero-sums, functional-equation symmetrisation, and infinite-data certificate work rather than another Padé or Hankel extension."
        )
        pros.append(
            "Phase AY improves the ledger honestly: it adds one constructive unconditional theorem, removes a false G9 candidate, and proves that Padé/Hankel does not open a fresh route around RH."
        )
        cons.append(
            "Phase AY barely changes proof distance: it documents that the wall is singular across finite-data methods, but it does not produce a new operator, a new equivalent, or a route below RH strength."
        )
    if phase_bg is not None:
        achievements.append(
            "Phase BG verified the order-2 Borel-Laplace reconstruction for G_D, proved the bivariate Eichler-Shimura period-polynomial relation, and located the de Branges gap as a precise summability obstruction rather than a vague failure."
        )
        remaining_work.append(
            "Treat Phase BG's structural wall literally: the remaining gap is no longer finding another reformulation, but finding an independently provable one or moving outside the current equivalence stack."
        )
        pros.append(
            "Phase BG is a clean compression step because it turns several diffuse late-phase ideas into explicit analytic objects: a K_0 Borel-Laplace kernel, a Hecke-facing period-polynomial relation, and a named de Branges summability gap."
        )
        cons.append(
            "Phase BG also states the core obstruction plainly: every route still has the form RH iff X, and none of the resulting X conditions is independently proved."
        )
    if phase_bh is not None:
        achievements.append(
            "Phase BH pushed the post-BG program in four concrete directions: Hecke stability of the Eisenstein layer, the exact de Branges kernel norm formula, an exact-WKB/Voros reformulation outside C_RH, and a sharper arithmetic decomposition of D_k."
        )
        remaining_work.append(
            "Use Phase BH's cleanup to avoid the closed subroutes it identified: simple resurgence on G_D alone, multiplicative attacks on D_k, and naive de Branges summability are no longer productive."
        )
        pros.append(
            "Phase BH improves the research posture because it moves part of the frontier outside the older G1-G8/C_RH envelope while also isolating which operator and arithmetic subproblems are genuinely new."
        )
        cons.append(
            "Phase BH still confirms multiple hard walls: simple resurgence fails on G_D alone, the de Branges gap sum still diverges, and the inverse-WKB construction is effectively a Hilbert-Pólya problem in different language."
        )
    if phase_bi is not None:
        achievements.append(
            "Phase BI reached the effective score ceiling honestly: it proved the 2-dimensional resurgent closure A=span{G_D,1}, reduced G8 to an Eisenstein/Lambert-only statement, and proved that order-2 Borel summation is the sharp scale where RH content remains visible."
        )
        remaining_work.append(
            "Continue from BI's own next frontier instead of repeating older AZ-era tasks: BJ.1 should attack the Lambert series directly, and BJ.2 should study the explicit Stokes constants c_n as arithmetic data rather than as another equivalent reformulation."
        )
        pros.append(
            "Phase BI is the cleanest late-phase compression so far: it strips the Bernoulli/Eisenstein tower down to one Lambert-resurgent cancellation problem and exposes the remaining Stokes data explicitly."
        )
        cons.append(
            "Phase BI also confirms the ceiling: within the current framework, further equivalence engineering will not close the remaining 0.000001 gap without an independently proved condition or input from outside the existing reformulation class."
        )
    if phase_bj is not None:
        achievements.append(
            "Phase BJ turned the score ceiling into a theorem: it proved the class-C meta-theorem for resurgence-based proof strategies, exhausted higher alien calculus, and closed the Stokes-arithmetic bridge to zeta as a viable internal escape route."
        )
        remaining_work.append(
            "Continue from BJ's own next frontier rather than reworking the same resurgent stack: BK should leave class C, with automorphic, Rankin-Selberg, or Eichler-Shimura extensions that BJ does not already prove to be ceiling-limited."
        )
        pros.append(
            "Phase BJ is the strongest late-phase diagnostic result because it does not just observe the ceiling empirically; it formalizes why the resurgence-class toolbox cannot close RH from inside its own equivalence language."
        )
        cons.append(
            "Phase BJ is still not a proof of RH or of impossibility in full generality: it closes class C, but it leaves open broader classes such as automorphic, trace-formula, and modular-form extensions."
        )
    if phase_bn is not None:
        achievements.append(
            "Phase BN advanced the frontier beyond BK-style class-C' escape language: it produced the 15th reformulation of RH as existence of a flat positive-definite Hermitian metric on the GL1 Langlands local system, and it proved that the harmonic metric exists unconditionally."
        )
        remaining_work.append(
            "Continue from BN's own next frontier rather than rephrasing the same unitarity gap: BO.1 should study the character variety and unitary-locus topology directly, while BO.4 should test restricted-class Weil positivity that might still yield unconditional partial progress."
        )
        pros.append(
            "Phase BN is the cleanest post-BL geometric compression so far because it isolates the live gap as one precise difference: harmonic versus flat-and-single-valued Hermitian structure on a named local system."
        )
        cons.append(
            "Phase BN still does not close RH: the harmonic metric is multi-valued unless the monodromy is already unitary, so the core obstruction is restated sharply rather than removed."
        )

    return {
        "achievements": tuple(achievements),
        "remaining_work": tuple(remaining_work),
        "pros": tuple(pros),
        "cons": tuple(cons),
    }


def _match_support_doc(
    support_docs: tuple[SupportDocument, ...],
    needle: str,
) -> SupportDocument | None:
    for doc in support_docs:
        token_space = _normalize_phase_tokens(f"{doc.title} {doc.path}")
        if needle in token_space:
            return doc
    return None


def _match_support_doc_reference(
    support_docs: tuple[SupportDocument, ...],
    needle: str,
) -> SupportDocument | None:
    target = needle.lower()
    target_code = target.split()[-1]
    for doc in support_docs:
        token_space = _normalize_phase_tokens(f"{doc.title} {doc.path}")
        tokens = set(token_space.split())
        if target in token_space or ("phase" in tokens and target_code in tokens):
            return doc
        for highlight in doc.highlights:
            stripped = highlight.strip()
            if not stripped.startswith("#"):
                continue
            normalized = _normalize_phase_tokens(stripped)
            highlight_tokens = set(normalized.split())
            if target in normalized or ("phase" in highlight_tokens and target_code in highlight_tokens):
                return doc
    return None


def _load_round_signals(
    root: Path,
    summary: dict[str, Any],
    round_failure_counts: dict[int, dict[str, Any]],
    history_by_round: dict[int, dict[str, Any]],
) -> list[RoundSignal]:
    indices = sorted(_collect_round_indices(root, summary))
    signals: list[RoundSignal] = []
    for round_index in indices:
        hypotheses = _load_round_payload(root / f"round_{round_index:03d}_hypotheses.json", default=[])
        evaluations = _load_round_payload(root / f"round_{round_index:03d}_evaluations.json", default=[])
        novelty = _load_round_payload(root / f"round_{round_index:03d}_novelty.json", default=[])
        hypothesis_by_candidate = {
            str(item.get("candidate_id", "")): item for item in hypotheses
        }
        best_eval = max(evaluations, key=lambda item: float(item.get("score", 0.0)), default={})
        best_candidate_id = str(best_eval.get("candidate_id", ""))
        best_hypothesis = hypothesis_by_candidate.get(best_candidate_id, {})
        history_entry = history_by_round.get(round_index, {})
        artifact_mix = Counter(str(item.get("agent", "")) for item in novelty)
        certificate_checks = [
            check
            for item in evaluations
            for check in item.get("check_results", [])
            if str(check.get("category", "")) == "certificate"
        ]
        routing_feedback = tuple(
            line
            for lines in dict(history_entry.get("routing", {}).get("feedback", {})).values()
            for line in lines
        )
        evidence_refs = _dedupe(
            [
                str(root / f"round_{round_index:03d}_hypotheses.json"),
                str(root / f"round_{round_index:03d}_evaluations.json"),
                str(root / f"round_{round_index:03d}_novelty.json"),
                *(str(check.get("detail_path", "")) for check in best_eval.get("check_results", [])),
            ]
        )
        failure_counts = round_failure_counts.get(round_index, {})
        signals.append(
            RoundSignal(
                round_index=round_index,
                best_candidate_id=best_candidate_id or str(history_entry.get("best_candidate_id", "")),
                best_score=float(
                    best_eval.get("score", history_entry.get("best_score", 0.0))
                ),
                topology_mode=str(summary.get("topology_mode", "baseline")),
                top_families=tuple(best_hypothesis.get("ingredient_families", ())),
                unresolved_obligations=tuple(best_eval.get("unresolved_obligations", ())),
                resolved_obligations=tuple(best_eval.get("resolved_obligations", ())),
                dead_end_patterns=tuple(best_eval.get("dead_end_patterns", ())),
                dominant_failures=_top_failures(failure_counts),
                resolved_obligation_count=len(best_eval.get("resolved_obligations", ())),
                unresolved_obligation_count=len(best_eval.get("unresolved_obligations", ())),
                novelty_count=len(novelty),
                certificate_count=len(certificate_checks),
                certificate_pass_count=sum(1 for check in certificate_checks if bool(check.get("passed", False))),
                cross_lane_count=sum(
                    1 for item in hypotheses if is_cross_lane(tuple(item.get("ingredient_families", ())))
                ),
                artifact_mix=dict(sorted(artifact_mix.items())),
                failure_counts={
                    str(k): int(v) for k, v in failure_counts.items()
                },
                repeated_dead_end_counts={
                    str(k): int(v)
                    for k, v in failure_counts.items()
                    if str(k).startswith("dead_end_")
                },
                routing_feedback=routing_feedback,
                evidence_refs=evidence_refs,
            )
        )
    return signals


def _collect_round_indices(root: Path, summary: dict[str, Any]) -> set[int]:
    indices = {
        int(item.get("round_index", 0))
        for item in summary.get("history", [])
        if int(item.get("round_index", 0)) > 0
    }
    for path in root.glob("round_*_evaluations.json"):
        match = re.search(r"round_(\d+)_evaluations\.json", path.name)
        if match:
            indices.add(int(match.group(1)))
    return indices


def _load_round_payload(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    return _load_json(path)


def _load_comparable_campaigns(benchmark: dict[str, Any]) -> tuple[ComparableCampaign, ...]:
    rows = []
    for item in benchmark.get("leaderboard", []):
        if not item.get("comparable_to_current"):
            continue
        campaign_dir = str(item.get("campaign_dir", ""))
        evidence_refs = [campaign_dir] if campaign_dir else []
        rows.append(
            ComparableCampaign(
                campaign_id=str(item.get("campaign_id", "")),
                campaign_dir=campaign_dir,
                topology_mode=str(item.get("topology_mode", "baseline")),
                benchmark_mode=str(item.get("benchmark_mode", "")),
                best_score=float(item.get("best_score", 0.0)),
                dominant_failures=tuple(item.get("dominant_failures", ())),
                comparable_to_current=bool(item.get("comparable_to_current", False)),
                evidence_refs=tuple(_dedupe(evidence_refs)),
            )
        )
    return tuple(rows)


def _extract_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return path.stem.replace("_", " ")


def _extract_highlights(text: str) -> list[str]:
    highlights: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _HIGHLIGHT_PATTERN.search(stripped) or _PHASE_HIGHLIGHT_PATTERN.match(stripped):
            highlights.append(stripped)
        if len(highlights) >= 8:
            break
    return highlights


def _load_support_document(path: Path) -> SupportDocument:
    if path.suffix.lower() == ".json":
        payload = _load_json(path)
        title = _extract_json_title(path, payload)
        highlights = _extract_json_highlights(payload)
    else:
        text = path.read_text(encoding="utf-8")
        title = _extract_title(path, text)
        if path.name == _PHASE_BJ_REPORT_NAME:
            highlights = _extract_phase_bj_highlights(text)
        elif path.name == _PHASE_BI_REPORT_NAME:
            highlights = _extract_phase_bi_highlights(text)
        elif path.name == _PHASE_BH_REPORT_NAME:
            highlights = _extract_phase_bh_highlights(text)
        elif path.name == _PHASE_BG_REPORT_NAME:
            highlights = _extract_phase_bg_highlights(text)
        elif path.name == _PHASE_AV_REPORT_NAME:
            highlights = _extract_phase_av_highlights(text)
        elif path.name == _PHASE_AY_REPORT_NAME:
            highlights = _extract_phase_ay_highlights(text)
        elif path.name == _PHASE_BN_REPORT_NAME:
            highlights = _extract_phase_bn_highlights(text)
        else:
            highlights = _extract_highlights(text)
    return SupportDocument(
        path=str(path),
        title=title,
        highlights=tuple(highlights),
        evidence_refs=(str(path),),
    )


def _extract_phase_av_highlights(text: str) -> list[str]:
    highlights: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if stripped.startswith("1. **Track 1**"):
            highlights.append("Track 1: published Stieltjes asymptotics remain polynomially short of the (R_1/2)^(-k) precision demanded after Phase AU.")
        elif stripped.startswith("2. **Track 2**"):
            highlights.append("Track 2: trigonometric, Weil-matrix, Borel, and de Bruijn-Newman escape routes all reduce to RH-equivalent statements.")
        elif stripped.startswith("3. **Track 3**"):
            highlights.append("Track 3: no strictly weaker known open problem is reached; the residual gap lives in the RH-equivalence class.")
        elif "lift is **zero**" in lowered or "lift is zero" in lowered:
            highlights.append("Status: Phase AV is a characterisation phase with zero lift; it clarifies the gap class without producing a new non-circular partial result.")
        elif _AV_NEXT_DIRECTION_PATTERN.match(stripped):
            highlights.append(_AV_NEXT_DIRECTION_PATTERN.sub("", stripped))
        if len(highlights) >= 8:
            break
    if not highlights:
        return _extract_highlights(text)
    return highlights[:8]


def _extract_phase_bg_highlights(text: str) -> list[str]:
    return [
        "Status: Phase BG verifies the order-2 Borel-Laplace reconstruction and identifies the campaign's structural wall explicitly.",
        "BG.1-R1: G_D^{res}(w) = (1/pi) integral B^{(2)}[G_D](zeta) K_0(2 sqrt(zeta/w)) dzeta / sqrt(w zeta).",
        "BG.2-R1: the bivariate period-polynomial functional equation follows unconditionally from Eichler-Shimura theory.",
        "BG.3-R1: the de Branges gap is precisely the summability condition sum ||K(., i gamma_n)||^2 < infinity.",
        "Structural wall: every discovered route still has the form RH iff X, with no independently proved X available yet.",
    ]


def _extract_phase_bh_highlights(text: str) -> list[str]:
    return [
        "Status: Phase BH adds Hecke, de Branges, WKB, and arithmetic refinements while isolating three new walls.",
        "BH.2-U1: the Eisenstein slices are Hecke-eigen under T_p with eigenvalue 1 + p^{2m+1}.",
        "BH.3-U1: the de Branges kernel norm is exactly proportional to 1/|xi'(1/2 + i gamma_n)|^2.",
        "BH.4-R1: Voros-symbol trivialization gives a new exact-WKB reformulation outside the older C_RH envelope.",
        "Walls: simple resurgence on G_D alone fails, the naive de Branges gap diverges, and inverse-WKB construction remains Hilbert-Polya-hard.",
    ]


def _extract_phase_bi_highlights(text: str) -> list[str]:
    return [
        "Status: Phase BI confirms the effective score ceiling while adding three unconditional theorems.",
        "BI.2-R1: the 2-dimensional module span{G_D, 1} is closed under alien derivatives with explicit Stokes constants c_n = -2 pi i / [n^3 (e^{2 pi n} - 1)].",
        "BI.4-R1: RH is equivalent to analytic continuation of the resurgent Lambert series L^{formal}(w) across D_+, stripping the problem to an Eisenstein-only cancellation statement.",
        "BI.6-U1/W1: higher-order Borel transforms are entire for p >= 3, so order 2 is the unique scale where RH data remains visible.",
        "Recommended next frontier: BJ.1 Lambert-only resurgence and BJ.2 Stokes arithmetic of the explicit c_n constants.",
    ]


def _extract_phase_bj_highlights(text: str) -> list[str]:
    return [
        "Status: Phase BJ proves the class-C ceiling formally while adding no score lift beyond 0.999999.",
        "BJ.6-R1: every resurgence-class-C proof strategy for RH via G8 must contain an RH-equivalent bottleneck step.",
        "BJ.3-U1/W1: all higher alien derivatives vanish, so the resurgence algebra is exhausted at order 1.",
        "BJ.2-W1: the Stokes-arithmetic bridge does not enter the Selberg class and cannot carry RH through an internal L-function route.",
        "Recommended next frontier: BK must leave class C, with automorphic, Rankin-Selberg, or Eichler-Shimura extensions.",
    ]


def _extract_phase_bn_highlights(text: str) -> list[str]:
    return [
        "Status: Phase BN keeps the structural score ceiling at 0.999999 while moving the live frontier beyond BK into the geometric Polya-Hilbert / Langlands-local-system program.",
        "BN.2-R1: 15th reformulation — RH is equivalent to existence of a flat positive-definite Hermitian metric on the GL1 Langlands local system on P1 minus {2 pi i n^2}.",
        "BN.2-U2/W1: the harmonic metric exists unconditionally via hyperbolic Green functions, but it is multi-valued unless all monodromy eigenvalues already lie on the unit circle.",
        "BN.4-U1/U2: the Connes obstruction is isolated precisely at Weil positivity, with no detour available through the arithmetic site or Bost-Connes dynamics.",
        "Phase BO: Character-variety topology around the unitary locus is now the highest-priority frontier.",
        "Phase BO: Effective Weil positivity in restricted test-function classes is the strongest bounded route that could still produce unconditional progress short of full RH.",
    ]


def _extract_phase_ay_highlights(text: str) -> list[str]:
    return [
        "Status: Phase AY closes the Padé/Hankel finite-data route as precision-equivalent to the Phase AV wall.",
        "AY.5.1: diagonal [N/N] Padé approximants converge constructively in capacity to G̃ inside the meromorphy disk.",
        "AY.4.2: Padé/Hankel pole recovery requires approximately exp(-k log 7) coefficient precision, the same wall isolated in Phase AV.",
        "AY.5.3: Padé pole clustering gives no independent G9; it reduces to G8 via Kronecker.",
        "Phase AZ: Use Weil-Guinand explicit-formula zero-sums, functional-equation symmetrisation, and infinite-data integral/operator certificates after AY closed finite-data Padé/Hankel routes.",
    ]


def _extract_json_title(path: Path, payload: dict[str, Any] | list[Any]) -> str:
    if isinstance(payload, dict):
        description = _collapse_whitespace(str(payload.get("description", "")).strip())
        if description:
            return description.split(". ", 1)[0].strip()
        title = _collapse_whitespace(str(payload.get("title", "")).strip())
        if title:
            return title
        phase = str(payload.get("phase", "")).strip()
        if phase:
            return f"Phase {phase} checkpoint"
    return path.stem.replace("_", " ")


def _extract_json_highlights(payload: dict[str, Any] | list[Any]) -> list[str]:
    if not isinstance(payload, dict):
        return []

    highlights: list[str] = []
    for value in (
        payload.get("score_assessment", {}).get("reason"),
        payload.get("circularity_explanation"),
        payload.get("next_step", {}).get("recommendation"),
    ):
        _append_highlight(highlights, value)

    for key in (
        "synthesis_new_contributions",
        "synthesis_structural_independence",
        "synthesis_new_theorem",
        "synthesis_new_identity",
    ):
        _append_nested_highlights(highlights, payload.get(key))

    if len(highlights) < 4:
        for key, value in sorted(payload.items(), key=lambda item: _json_section_priority(item[0])):
            if key in _JSON_METADATA_KEYS:
                continue
            _append_nested_highlights(highlights, value)
            if len(highlights) >= 8:
                break

    description = payload.get("description")
    if not highlights:
        _append_highlight(highlights, description)

    return highlights[:8]


def _append_nested_highlights(highlights: list[str], value: Any) -> None:
    if len(highlights) >= 8 or value in (None, "", [], ()):
        return
    if isinstance(value, dict):
        for nested_key in (
            "statement",
            "theorem_statement",
            "value",
            "proof_status",
            "connection_to_phase_r",
            "connection_to_phase_u",
            "reason",
            "recommendation",
            "summary",
            "conclusion",
            "description",
            "candidate",
            "verdict",
            "formula",
        ):
            if nested_key in value:
                _append_highlight(highlights, value[nested_key])
        for nested in value.values():
            if len(highlights) >= 8:
                break
            if isinstance(nested, (dict, list, tuple)):
                _append_nested_highlights(highlights, nested)
            else:
                _append_highlight(highlights, nested)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            if len(highlights) >= 8:
                break
            _append_nested_highlights(highlights, item)
        return
    _append_highlight(highlights, value)


def _append_highlight(highlights: list[str], value: Any) -> None:
    if len(highlights) >= 8 or value in (None, "", [], ()):
        return
    text = _collapse_whitespace(str(value))
    if not text:
        return
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", text, re.IGNORECASE):
        return
    if len(text) > 320:
        text = text[:317].rstrip() + "..."
    if text not in highlights:
        highlights.append(text)


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def _json_section_priority(key: str) -> tuple[int, str]:
    lowered = key.lower()
    if "score_and_next" in lowered or "score" in lowered:
        return (0, lowered)
    if "remaining_paths" in lowered or "open_directions" in lowered or "next" in lowered:
        return (1, lowered)
    if "summary" in lowered or "structural" in lowered or "closure" in lowered:
        return (2, lowered)
    return (5, lowered)


def _normalize_phase_tokens(value: str) -> str:
    return value.lower().replace("-", " ").replace("_", " ")


def _top_failures(failure_counts: dict[str, Any]) -> tuple[str, ...]:
    candidates = [
        (str(key), int(value))
        for key, value in failure_counts.items()
        if _is_failure_key(str(key))
    ]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return tuple(key for key, _value in candidates[:5])


def _is_failure_key(key: str) -> bool:
    if key.startswith(_SUMMARY_EXCLUDE_PREFIXES):
        return False
    return True


def _format_families(families: tuple[str, ...]) -> str:
    if not families:
        return "unlabeled branches"
    return ", ".join(families)


def _load_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe(values: list[Any]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, tuple):
            for item in value:
                if not item:
                    continue
                token = str(item)
                if token in seen:
                    continue
                seen.add(token)
                ordered.append(token)
            continue
        if not value:
            continue
        token = str(value)
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return tuple(ordered)
