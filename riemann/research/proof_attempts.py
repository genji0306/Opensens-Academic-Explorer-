"""Web-sourced RH proof-attempt corpus materialized into local research data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT, RESEARCH_DIR, SEED_PACK_DIR

PROOF_ATTEMPTS_DIR = RESEARCH_DIR / "proof_attempts"
PROOF_ATTEMPT_DOCS_DIR = PROOF_ATTEMPTS_DIR / "attempts"
PROOF_ATTEMPTS_CATALOG_PATH = PROOF_ATTEMPTS_DIR / "rh_proof_attempts_catalog.json"
PROOF_ATTEMPTS_BIBLIOGRAPHY_PATH = PROOF_ATTEMPTS_DIR / "rh_proof_attempts_bibliography.md"
PROOF_ATTEMPTS_SEED_PACK_PATH = SEED_PACK_DIR / "rh_proof_attempts.json"

SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "clay_problem": {
        "title": "Riemann Hypothesis",
        "authors": ["Clay Mathematics Institute"],
        "year": 2026,
        "url": "https://www.claymath.org/millennium/Riemann-Hypothesis/",
        "kind": "official_problem_page",
        "note": "Official problem overview and current verification statement.",
    },
    "bombieri_problem_note": {
        "title": "Problems of the Millennium: the Riemann Hypothesis",
        "authors": ["Enrico Bombieri"],
        "year": 2000,
        "url": "https://www.claymath.org/wp-content/uploads/2022/05/riemann.pdf",
        "kind": "official_problem_note",
        "note": "Clay problem note on history, significance, and classical analytic structure.",
    },
    "sarnak_problem_note": {
        "title": "Problems of the Millennium: The Riemann Hypothesis",
        "authors": ["Peter Sarnak"],
        "year": 2004,
        "url": "https://www.claymath.org/library/annual_report/xSarnak_RH.pdf",
        "kind": "survey",
        "note": "Clay lecture note on outlook and modern developments.",
    },
    "conrey_survey": {
        "title": "Riemann's Hypothesis",
        "authors": ["J. Brian Conrey"],
        "year": 2019,
        "url": "https://aimath.org/~kaur/publications/90.pdf",
        "kind": "survey",
        "note": "AIM-hosted survey emphasizing equivalent criteria, computations, spacing, and operator ideas.",
    },
    "aim_outline": {
        "title": "The Riemann Hypothesis",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://aimath.org/WWN/rh/",
        "kind": "reference_index",
        "note": "AIM outline of equivalences, attacks, and supporting topics around RH.",
    },
    "aim_li_criterion": {
        "title": "Li's criterion",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/27a/",
        "kind": "reference_entry",
        "note": "AIM reference entry on Li's positivity criterion.",
    },
    "aim_beurling_nyman": {
        "title": "The Beurling-Nyman Criterion",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/29a/",
        "kind": "reference_entry",
        "note": "AIM reference entry on the Beurling-Nyman closure criterion.",
    },
    "aim_mollification_problem": {
        "title": "A mollification problem",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/88a/",
        "kind": "reference_entry",
        "note": "AIM entry connecting Baez-Duarte-style mollification to RH equivalence.",
    },
    "aim_zero_counting": {
        "title": "Zero counting functions",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/71a/",
        "kind": "reference_entry",
        "note": "AIM zero-counting entry summarizing Selberg and Conrey critical-line density results.",
    },
    "aim_density_hypothesis": {
        "title": "The Density Hypothesis",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://aimath.org/WWN/rh/articles/html/25a/",
        "kind": "reference_entry",
        "note": "AIM entry on zero-density estimates and their limitations.",
    },
    "aim_xi_z": {
        "title": "xi and Z functions",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/74a/",
        "kind": "reference_entry",
        "note": "AIM entry on the xi-function and Hardy Z-function.",
    },
    "aim_de_branges": {
        "title": "de Branges' positivity condition",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/40a/",
        "kind": "reference_entry",
        "note": "AIM entry on de Branges-style positivity and Hilbert-space constraints.",
    },
    "aim_newman": {
        "title": "Newman's criterion",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/105a/",
        "kind": "reference_entry",
        "note": "AIM entry on the de Bruijn-Newman constant and its RH equivalence.",
    },
    "aim_dirichlet_polynomials": {
        "title": "Zeros of Dirichlet polynomials",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://www.aimath.org/WWN/rh/articles/html/37a/",
        "kind": "reference_entry",
        "note": "AIM entry on Turan's route via Dirichlet polynomials and why it fails.",
    },
    "aim_berry_keating": {
        "title": "Semiclassical spectral determinant heuristics",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://aimath.org/WWN/rh/articles/html/63a/",
        "kind": "reference_entry",
        "note": "AIM entry summarizing Berry-Keating style spectral heuristics.",
    },
    "aim_connes": {
        "title": "Non-commutative number theory: around ideas of A. Connes",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://aimath.org/WWN/rh/articles/html/100a/",
        "kind": "reference_entry",
        "note": "AIM entry on Connes-inspired noncommutative routes.",
    },
    "aim_bost_connes": {
        "title": "Bost-Connes dynamical-system problem",
        "authors": ["American Institute of Mathematics"],
        "year": 2026,
        "url": "https://aimath.org/WWN/rh/articles/html/101a/",
        "kind": "reference_entry",
        "note": "AIM entry on zeta-partition-function dynamical systems in the Connes orbit.",
    },
    "spigler_survey": {
        "title": "A Brief Survey on the Riemann Hypothesis and Some Attempts to Prove It",
        "authors": ["Renato Spigler"],
        "year": 2025,
        "url": "https://www.mdpi.com/3166526",
        "kind": "survey",
        "note": "Recent survey touching zero-free regions, Li criterion, numerical work, and modern attempts.",
    },
    "jensen_pnas": {
        "title": "Jensen polynomials for the Riemann zeta function and other sequences",
        "authors": ["Michael Griffin", "Ken Ono", "Larry Rolen", "Don Zagier"],
        "year": 2019,
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6561287/",
        "kind": "research_article",
        "note": "PNAS article proving large-shift hyperbolicity results in a Polya-Jensen RH criterion.",
    },
}

PROOF_ATTEMPTS: tuple[dict[str, Any], ...] = (
    {
        "attempt_id": "zero_free_regions_program",
        "title": "Zero-free regions and zero-density program",
        "historical_family": "zero_free_regions",
        "orchestrator_family": "general_analytic",
        "status": "partial_progress",
        "summary": "Classical analytic work pushes zero-free regions toward the critical line and sharpens zero-density estimates.",
        "mechanism": "Bound zeros in sigma > 1 - 1/f(t) or count how many zeros can remain off the line, then try to squeeze the strip down to sigma = 1/2.",
        "why_not_proof": "Even strong zero-free regions and density estimates still leave room for off-line zeros.",
        "connection_note": "Feeds the orchestrator's general analytic lane and informs Observer pressure on unresolved off-line-zero obligations.",
        "keywords": ["zero-free region", "density hypothesis", "Vinogradov-Korobov", "de la Vallee Poussin"],
        "source_ids": ["bombieri_problem_note", "spigler_survey", "aim_density_hypothesis"],
    },
    {
        "attempt_id": "critical_line_density_methods",
        "title": "Mollifier and critical-line density methods",
        "historical_family": "mollifiers_and_moments",
        "orchestrator_family": "mollifier_moment",
        "status": "partial_progress",
        "summary": "Hardy, Selberg, Levinson, and Conrey style methods prove that many zeros lie on the critical line and improve the on-line proportion.",
        "mechanism": "Use mollified moments and zero-counting arguments to convert mean-value control into lower bounds for N_0(T).",
        "why_not_proof": "The program improves density on the line but has not reached 100 percent of zeros, let alone excluded every off-line zero.",
        "connection_note": "Directly matches the orchestrator's mollifier_moment family and supplies proof-obligation baselines around partial-on-line results.",
        "keywords": ["mollifier", "moment method", "Levinson", "Conrey", "critical line"],
        "source_ids": ["conrey_survey", "aim_zero_counting", "aim_mollification_problem"],
    },
    {
        "attempt_id": "hilbert_polya_program",
        "title": "Hilbert-Polya spectral operator program",
        "historical_family": "spectral_operator",
        "orchestrator_family": "hilbert_polya",
        "status": "heuristic_program",
        "summary": "A self-adjoint operator with spectrum matching the imaginary parts of non-trivial zeros would force them onto the critical line.",
        "mechanism": "Construct an operator or trace formula whose eigenvalues encode zero ordinates and inherit reality from self-adjointness.",
        "why_not_proof": "No accepted operator construction is known, and analogies alone do not identify the full zeta spectrum rigorously.",
        "connection_note": "This is the orchestrator's main operator-theoretic lane and the most direct bridge to Agent Q's spectral surrogates.",
        "keywords": ["Hilbert-Polya", "self-adjoint", "spectral operator", "eigenvalue"],
        "source_ids": ["conrey_survey", "sarnak_problem_note", "aim_berry_keating"],
    },
    {
        "attempt_id": "connes_noncommutative_program",
        "title": "Connes and Bost-Connes noncommutative program",
        "historical_family": "noncommutative_spectral",
        "orchestrator_family": "quantum_spectral",
        "status": "heuristic_program",
        "summary": "Noncommutative geometry and zeta-partition-function dynamical systems aim to recast RH as a spectral statement.",
        "mechanism": "Use C*-algebras, trace formulas, or zeta partition functions to express prime structure and zero statistics in spectral language.",
        "why_not_proof": "The frameworks are structurally rich but remain heuristic or incomplete as a full exclusion proof for off-line zeros.",
        "connection_note": "This literature lane is the clearest external analog of Agent Q's simulator-backed operator search.",
        "keywords": ["Connes", "Bost-Connes", "noncommutative", "Hamiltonian", "spectral flow"],
        "source_ids": ["aim_connes", "aim_bost_connes", "conrey_survey"],
    },
    {
        "attempt_id": "pair_correlation_random_matrix",
        "title": "Pair-correlation and random-matrix heuristics",
        "historical_family": "random_matrix",
        "orchestrator_family": "random_matrix",
        "status": "heuristic_evidence",
        "summary": "Montgomery-Odlyzko style statistics suggest that zeta zeros behave like eigenvalues of GUE random matrices.",
        "mechanism": "Compare local zero statistics, pair correlation, and spacing distributions against random-matrix laws.",
        "why_not_proof": "Statistical agreement is compelling evidence but does not force every zero onto the critical line.",
        "connection_note": "Aligns directly with the orchestrator's random_matrix family and supports the spectral interpretation without resolving it.",
        "keywords": ["pair correlation", "random matrix", "GUE", "Montgomery", "Odlyzko"],
        "source_ids": ["conrey_survey", "sarnak_problem_note"],
    },
    {
        "attempt_id": "li_keiper_criterion",
        "title": "Keiper-Li positivity criterion",
        "historical_family": "equivalent_criteria",
        "orchestrator_family": "xi_function",
        "status": "equivalent_criterion",
        "summary": "RH is equivalent to nonnegativity of the Li coefficients derived from log xi(s).",
        "mechanism": "Translate zero-location information into positivity statements for a sequence built from derivatives of the completed xi-function.",
        "why_not_proof": "The criterion is equivalent to RH, but proving positivity for all coefficients is itself as hard as RH.",
        "connection_note": "Maps into the orchestrator's xi_function lane and gives a precise positivity target for Agent B.",
        "keywords": ["Li criterion", "Keiper-Li", "xi(s)", "positivity", "entire function"],
        "source_ids": ["aim_li_criterion", "spigler_survey", "conrey_survey"],
    },
    {
        "attempt_id": "beurling_nyman_criterion",
        "title": "Beurling-Nyman closure criterion",
        "historical_family": "function_space_equivalence",
        "orchestrator_family": "general_analytic",
        "status": "equivalent_criterion",
        "summary": "RH is equivalent to a density or closure statement in L^2(0,1) for a specific function class.",
        "mechanism": "Reformulate RH as an approximation problem in a Hilbert-space-like function space generated by fractional-part functions.",
        "why_not_proof": "The criterion is exact, but the required closure estimates remain difficult and no complete proof is known.",
        "connection_note": "Extends the orchestrator's analytic lane with a precise closure problem rather than a direct zero-counting argument.",
        "keywords": ["Beurling-Nyman", "closure", "L2", "function space", "mollification"],
        "source_ids": ["aim_beurling_nyman", "aim_mollification_problem", "conrey_survey"],
    },
    {
        "attempt_id": "de_branges_positivity_program",
        "title": "de Branges positivity and Hilbert-space program",
        "historical_family": "de_branges_spaces",
        "orchestrator_family": "de_branges",
        "status": "unaccepted_program",
        "summary": "de Branges-style Hilbert spaces of entire functions aim to force RH through positivity and reproducing-kernel structure.",
        "mechanism": "Construct a de Branges space encoding xi-function positivity so that zeros inherit the required location from the space axioms.",
        "why_not_proof": "Candidate positivity conditions and space constructions have not produced an accepted proof of RH.",
        "connection_note": "Direct match to the orchestrator's de_branges family and a useful comparison point for operator-style hypotheses.",
        "keywords": ["de Branges", "Hermite-Biehler", "Hilbert space", "positivity"],
        "source_ids": ["aim_de_branges", "conrey_survey", "spigler_survey"],
    },
    {
        "attempt_id": "newman_debruijn_flow",
        "title": "de Bruijn-Newman flow and heat deformation",
        "historical_family": "xi_deformation",
        "orchestrator_family": "xi_function",
        "status": "equivalent_criterion",
        "summary": "RH is equivalent to the de Bruijn-Newman constant satisfying Lambda <= 0 under a heat-flow deformation of Xi.",
        "mechanism": "Study how zeros move under Gaussian smoothing of Xi and bound the phase transition at which nonreal zeros appear.",
        "why_not_proof": "Tight bounds on Lambda support RH-like rigidity but do not establish the exact sign needed for RH.",
        "connection_note": "A natural xi_function calibration target for the orchestrator because it turns zero motion into a single scalar obstruction.",
        "keywords": ["de Bruijn-Newman", "Xi", "heat flow", "Lambda", "entire function"],
        "source_ids": ["aim_newman", "conrey_survey"],
    },
    {
        "attempt_id": "jensen_polynomial_program",
        "title": "Polya-Jensen hyperbolicity program",
        "historical_family": "jensen_hyperbolicity",
        "orchestrator_family": "xi_function",
        "status": "partial_progress",
        "summary": "RH is equivalent to hyperbolicity of all relevant Jensen polynomials, and recent work proves wide finite-shift regimes.",
        "mechanism": "Translate RH into real-rootedness of Jensen polynomials attached to xi-derivative data and prove hyperbolicity in growing ranges.",
        "why_not_proof": "Finite-degree or large-shift hyperbolicity results still stop short of the full infinite criterion.",
        "connection_note": "This strengthens the orchestrator's xi_function lane with a concrete finite-to-infinite obstruction profile.",
        "keywords": ["Jensen polynomial", "hyperbolic", "Hermite polynomial", "xi-function"],
        "source_ids": ["jensen_pnas", "conrey_survey"],
    },
    {
        "attempt_id": "dirichlet_polynomial_turan_route",
        "title": "Turan route via Dirichlet polynomials",
        "historical_family": "dirichlet_polynomial_criteria",
        "orchestrator_family": "general_analytic",
        "status": "blocked_route",
        "summary": "Turan-type criteria try to deduce RH from zero-free properties of finite zeta partial sums or Dirichlet polynomials.",
        "mechanism": "Show that partial sums or short Dirichlet polynomials avoid zeros in a region strong enough to imply RH.",
        "why_not_proof": "Montgomery-type counter-results show that the required zero-free regions for partial sums cannot hold in the needed strength.",
        "connection_note": "Useful negative control for the orchestrator: some analytic routes are formally strong but already known to fail.",
        "keywords": ["Dirichlet polynomial", "Turan", "partial sums", "zero-free"],
        "source_ids": ["aim_dirichlet_polynomials", "conrey_survey"],
    },
    {
        "attempt_id": "explicit_formula_positivity",
        "title": "Explicit-formula and positivity route",
        "historical_family": "explicit_formula",
        "orchestrator_family": "explicit_formula",
        "status": "structural_equivalence",
        "summary": "Weil-style explicit formulas and positivity criteria tie prime sums to zero distributions with theorem-level exactness.",
        "mechanism": "Encode zero locations through prime-side test-function identities and search for positivity or incompatibility with off-line zeros.",
        "why_not_proof": "The explicit formula is exact, but turning it into a universal positivity argument strong enough for RH remains open.",
        "connection_note": "This is the orchestrator's strongest classical bridge between primes and zeros and underlies its prime-side validation checks.",
        "keywords": ["explicit formula", "Weil positivity", "prime powers", "Euler product", "xi"],
        "source_ids": ["conrey_survey", "bombieri_problem_note"],
    },
    {
        "attempt_id": "hardy_z_numerical_verification",
        "title": "Hardy Z and computational verification lane",
        "historical_family": "numerical_verification",
        "orchestrator_family": "hardy_z",
        "status": "numerical_evidence",
        "summary": "Hardy Z evaluations, Riemann-Siegel methods, and large-scale computation verify vast initial zero ranges on the critical line.",
        "mechanism": "Use critical-line formulas and high-precision computation to certify zeros and exclude violations up to large heights.",
        "why_not_proof": "Numerical verification, however large, does not prove the infinite statement of RH.",
        "connection_note": "This is the closest historical analogue to the orchestrator's current zero-fit and Z-based validation engine.",
        "keywords": ["Hardy Z", "Riemann-Siegel", "Gram point", "computation", "critical line"],
        "source_ids": ["clay_problem", "aim_xi_z", "spigler_survey"],
    },
    {
        "attempt_id": "geometric_modulus_monotonicity",
        "title": "Geometric and modulus-monotonicity route",
        "historical_family": "geometric_visualization",
        "orchestrator_family": "geometric_visualization",
        "status": "heuristic_program",
        "summary": "Visual and geometric interpretations study modulus flow, horizontal monotonicity, and critical-strip structure as a guide to zero geometry.",
        "mechanism": "Translate plots, strip symmetries, and modulus behavior into candidate invariants about how zeros can move or align.",
        "why_not_proof": "Visual regularity is suggestive, but no accepted invariant excludes off-line zeros from geometry alone.",
        "connection_note": "This is the literature bridge into the orchestrator's M lane and directly motivates OAE projection and strip synthesis.",
        "keywords": ["visualization", "geometric", "projection", "critical strip", "horizontal monotonicity"],
        "source_ids": ["spigler_survey", "sarnak_problem_note"],
    },
)


def load_attempt_catalog(path: Path | None = None) -> dict[str, Any]:
    target = path or PROOF_ATTEMPTS_CATALOG_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def materialize_proof_attempt_corpus() -> dict[str, Any]:
    PROOF_ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
    PROOF_ATTEMPT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    SEED_PACK_DIR.mkdir(parents=True, exist_ok=True)

    catalog = {
        "title": "RH proof-attempt corpus",
        "description": (
            "Curated local corpus of major documented Riemann hypothesis attempt families, "
            "assembled from authoritative web sources and normalized for the OAE research orchestrator."
        ),
        "generated_from_web_on": "2026-04-17",
        "source_registry": SOURCE_REGISTRY,
        "attempts": list(PROOF_ATTEMPTS),
    }
    PROOF_ATTEMPTS_CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    PROOF_ATTEMPTS_BIBLIOGRAPHY_PATH.write_text(_render_bibliography_markdown(catalog), encoding="utf-8")

    seed_paths: list[str] = []
    for attempt in PROOF_ATTEMPTS:
        path = PROOF_ATTEMPT_DOCS_DIR / f"{attempt['attempt_id']}.md"
        path.write_text(_render_attempt_markdown(attempt), encoding="utf-8")
        seed_paths.append(path.relative_to(PROJECT_ROOT).as_posix())

    seed_pack = {
        "name": "rh-proof-attempts",
        "description": (
            "Curated local corpus of major documented RH proof-attempt families plus the OAE local reports "
            "used to compare literature routes against orchestrator routes."
        ),
        "allowlisted_domains": [
            "aimath.org",
            "www.aimath.org",
            "claymath.org",
            "www.claymath.org",
            "mdpi.com",
            "www.mdpi.com",
            "pmc.ncbi.nlm.nih.gov",
        ],
        "seeds": seed_paths
        + [
            "data/riemann/research/seed_packs/rh_operator_calibration_functional_equation.md",
            "data/riemann/research/seed_packs/rh_operator_calibration_xi_symmetry.md",
            "data/riemann/research/seed_packs/rh_operator_calibration_contour_methods.md",
            "data/riemann/reports/rh_synthesis.md",
            "data/riemann/reports/final_report.json",
            "data/riemann/reports/math_analysis.json",
            "data/riemann/reports/rh_operator_framework.md",
            "data/riemann/reports/rh_projection.html",
            "data/riemann/reports/rh_strip.html",
            "data/riemann/reports/rh_explicit.html",
        ],
        "bibliography": [
            {
                "family": item["historical_family"],
                "title": item["title"],
                "authors": _attempt_authors(item),
                "year": _attempt_year(item),
                "note": item["summary"],
            }
            for item in PROOF_ATTEMPTS
        ],
    }
    PROOF_ATTEMPTS_SEED_PACK_PATH.write_text(json.dumps(seed_pack, indent=2), encoding="utf-8")
    return {
        "catalog_path": str(PROOF_ATTEMPTS_CATALOG_PATH),
        "bibliography_path": str(PROOF_ATTEMPTS_BIBLIOGRAPHY_PATH),
        "seed_pack_path": str(PROOF_ATTEMPTS_SEED_PACK_PATH),
        "attempt_count": len(PROOF_ATTEMPTS),
    }


def _attempt_year(attempt: dict[str, Any]) -> int:
    years = [int(SOURCE_REGISTRY[source_id]["year"]) for source_id in attempt["source_ids"]]
    return min(years)


def _attempt_authors(attempt: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    seen: set[str] = set()
    for source_id in attempt["source_ids"]:
        for author in SOURCE_REGISTRY[source_id]["authors"]:
            if author in seen:
                continue
            seen.add(author)
            authors.append(author)
    return authors


def _render_bibliography_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# RH Proof Attempt Corpus",
        "",
        "This local corpus was assembled from authoritative web sources on 2026-04-17.",
        "It is intentionally curated by major documented attempt families rather than by every individual claim ever posted about RH.",
        "",
        "## Sources",
        "",
    ]
    for source_id, source in sorted(catalog["source_registry"].items()):
        authors = ", ".join(source["authors"])
        lines.extend(
            [
                f"- `{source_id}`: {source['title']} ({source['year']})",
                f"  Authors: {authors}",
                f"  Kind: {source['kind']}",
                f"  URL: {source['url']}",
                f"  Note: {source['note']}",
            ]
        )
    lines.extend(["", "## Attempt Families", ""])
    for attempt in PROOF_ATTEMPTS:
        lines.extend(
            [
                f"- `{attempt['attempt_id']}` -> `{attempt['orchestrator_family']}`",
                f"  Historical family: {attempt['historical_family']}",
                f"  Status: {attempt['status']}",
                f"  Summary: {attempt['summary']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _render_attempt_markdown(attempt: dict[str, Any]) -> str:
    lines = [
        f"# RH Attempt: {attempt['title']}",
        "",
        f"Attempt ID: {attempt['attempt_id']}",
        f"Historical family: {attempt['historical_family']}",
        f"Orchestrator family alignment: {attempt['orchestrator_family']}",
        f"Status: {attempt['status']}",
        "",
        "Summary:",
        attempt["summary"],
        "",
        "Mechanism:",
        attempt["mechanism"],
        "",
        "Why this is not yet a proof:",
        attempt["why_not_proof"],
        "",
        "Connection to the OAE orchestrator:",
        attempt["connection_note"],
        "",
        "Keywords:",
        ", ".join(attempt["keywords"]),
        "",
        "Representative web sources:",
    ]
    for source_id in attempt["source_ids"]:
        source = SOURCE_REGISTRY[source_id]
        authors = ", ".join(source["authors"])
        lines.extend(
            [
                f"- Source ID: {source_id}",
                f"  Title: {source['title']}",
                f"  Authors: {authors}",
                f"  Year: {source['year']}",
                f"  Kind: {source['kind']}",
                f"  URL: {source['url']}",
                f"  Note: {source['note']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - manual utility
    payload = materialize_proof_attempt_corpus()
    print(json.dumps(payload, indent=2))
