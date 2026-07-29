"""Agent C — ingest and normalize RH source material into approach cards."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from src.oae.research.trace import ResearchTrace

from .config import RiemannResearchConfig, ensure_dirs
from .schemas import ApproachCard, CorpusIngestionResult, SourceRecord

_FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hilbert_polya": ("hilbert-polya", "hilbert pólya", "self-adjoint", "spectral operator"),
    "explicit_formula": ("explicit formula", "psi(x)", "prime powers", "euler product", "-zeta'/zeta"),
    "hardy_z": ("hardy z", "riemann-siegel", "z(t)", "theta(t)", "gram point"),
    "random_matrix": ("random matrix", "gue", "pair correlation", "montgomery"),
    "de_branges": ("de branges", "hermite-biehler"),
    "xi_function": ("xi-function", "xi(s)", "laguerre-polya", "entire function"),
    "mollifier_moment": ("mollifier", "moment method", "levinson", "conrey"),
    "geometric_visualization": ("projection", "visualization", "3d", "4d", "spiral", "critical strip"),
    "quantum_spectral": ("hamiltonian", "quantum", "operator", "eigenvalue", "spectral flow"),
}

_FAMILY_LIBRARY: dict[str, dict[str, tuple[str, ...] | str]] = {
    "hilbert_polya": {
        "mechanism": "Search for a self-adjoint operator whose spectrum matches the non-trivial zeros.",
        "assumptions": (
            "operator spectrum should remain real and ordered",
            "critical-line confinement must arise from self-adjoint structure",
        ),
        "proof_obligations": (
            "construct the operator rigorously",
            "prove the operator spectrum matches every non-trivial zero",
            "show no off-line zeros survive the construction",
        ),
        "blockers": (
            "no accepted operator construction is known",
            "spectral analogies alone do not imply RH",
        ),
        "checks": ("spectral_surrogate_consistency", "critical_line_identity"),
        "claim": "Operator-theoretic structure could force all non-trivial zeros onto the critical line.",
    },
    "explicit_formula": {
        "mechanism": "Use the explicit formula to tie zero distributions to prime oscillations.",
        "assumptions": (
            "prime-zero duality must be tracked quantitatively",
            "candidate identities must preserve the explicit formula",
        ),
        "proof_obligations": (
            "bound all error terms in the explicit formula",
            "show prime oscillations are incompatible with off-line zeros",
        ),
        "blockers": (
            "the explicit formula is exact but not by itself a proof of RH",
        ),
        "checks": ("explicit_formula_consistency", "prime_power_alignment"),
        "claim": "Prime fluctuations and zero locations are linked strongly enough that any proof strategy must respect the explicit formula.",
    },
    "hardy_z": {
        "mechanism": "Reframe critical-line values through the real Hardy Z-function and Riemann-Siegel phase.",
        "assumptions": (
            "critical-line analysis should preserve the Hardy-Z phase decomposition",
        ),
        "proof_obligations": (
            "extend critical-line control into a proof that no off-line zeros exist",
        ),
        "blockers": (
            "critical-line identities are classical and do not exclude off-line zeros",
        ),
        "checks": ("critical_line_identity", "gram_point_alignment"),
        "claim": "The Hardy-Z formulation gives the cleanest critical-line parametrization but still needs a global exclusion argument.",
    },
    "random_matrix": {
        "mechanism": "Use GUE-like spacing statistics as evidence for spectral structure.",
        "assumptions": (
            "spacing statistics capture relevant zero correlations",
        ),
        "proof_obligations": (
            "upgrade probabilistic/statistical evidence into a theorem",
        ),
        "blockers": (
            "statistical agreement does not imply theorem-level critical-line confinement",
        ),
        "checks": ("spacing_profile_check", "spectral_surrogate_consistency"),
        "claim": "Random-matrix statistics give strong evidence for zero spacing regularity but not a proof.",
    },
    "de_branges": {
        "mechanism": "Seek a de Branges space whose structure forces RH.",
        "assumptions": (
            "an appropriate Hilbert space can encode xi-function positivity",
        ),
        "proof_obligations": (
            "construct the required de Branges space",
            "verify all positivity and closure conditions",
        ),
        "blockers": (
            "candidate spaces have not yielded an accepted proof",
        ),
        "checks": ("xi_symmetry_check", "space_construction_consistency"),
        "claim": "Function-space methods remain a serious but incomplete RH program.",
    },
    "xi_function": {
        "mechanism": "Work with the completed xi-function and its entire-function constraints.",
        "assumptions": (
            "xi-function symmetries encode decisive global information",
        ),
        "proof_obligations": (
            "translate xi-function regularity into zero-location exclusion",
        ),
        "blockers": (
            "symmetry and entire-function structure still leave the core zero-location problem open",
        ),
        "checks": ("xi_symmetry_check", "functional_equation_consistency"),
        "claim": "Xi-function structure is necessary context for any global proof but has not closed the argument alone.",
    },
    "mollifier_moment": {
        "mechanism": "Use moment and mollifier methods to prove large fractions of zeros lie on the critical line.",
        "assumptions": (
            "asymptotic moment control can be sharpened",
        ),
        "proof_obligations": (
            "upgrade partial critical-line density results to 100 percent",
        ),
        "blockers": (
            "fractional-on-line results still fall short of RH",
        ),
        "checks": ("moment_bound_consistency",),
        "claim": "Moment methods get close in density terms but do not yet prove every zero is on the line.",
    },
    "geometric_visualization": {
        "mechanism": "Use projection geometry to generate candidate invariants about the critical line.",
        "assumptions": (
            "visual structure must be translated into a falsifiable invariant",
        ),
        "proof_obligations": (
            "state the visual intuition as a rigorous invariant or operator claim",
            "prove the invariant excludes off-line zeros",
        ),
        "blockers": (
            "visual intuition alone is not a theorem",
        ),
        "checks": ("projection_identity_check", "strip_symmetry_check"),
        "claim": "Projection geometry can guide conjecture formation, but only testable invariants count as mathematical progress.",
    },
    "quantum_spectral": {
        "mechanism": "Use quantum-inspired spectral surrogates as a search space for operator-style RH hypotheses.",
        "assumptions": (
            "toy Hamiltonians may expose operator constraints worth testing",
        ),
        "proof_obligations": (
            "promote any surrogate into a rigorous self-adjoint operator construction",
            "prove the surrogate predictions survive exact analysis",
        ),
        "blockers": (
            "simulators generate heuristics, not proofs",
        ),
        "checks": ("spectral_surrogate_consistency", "quantum_gap_stability"),
        "claim": "Quantum-inspired modelling is an idea generator unless it yields a rigorous operator argument.",
    },
    "general_analytic": {
        "mechanism": "Track analytic approaches that do not fit a narrower family yet.",
        "assumptions": ("analytic structure matters",),
        "proof_obligations": ("turn the approach into explicit proof obligations",),
        "blockers": ("approach family is too generic to score strongly yet",),
        "checks": ("functional_equation_consistency",),
        "claim": "The source is RH-relevant but requires stronger normalization before it can drive synthesis.",
    },
}


class CorpusAgent:
    """Seed-driven source ingestion with local caching and deterministic normalization."""

    name = "C"

    def run(
        self,
        cfg: RiemannResearchConfig,
        trace: ResearchTrace | None = None,
    ) -> CorpusIngestionResult:
        ensure_dirs(cfg)
        queue: list[tuple[str, int, str]] = [(seed, 0, "") for seed in cfg.crawl_seeds]
        seen_locators: set[str] = set()
        seen_hashes: set[str] = set()
        sources: list[SourceRecord] = []
        approaches: list[ApproachCard] = []
        skipped: list[str] = []

        while queue and len(sources) < cfg.max_sources:
            locator, depth, parent = queue.pop(0)
            if locator in seen_locators:
                continue
            seen_locators.add(locator)
            try:
                source, body = self._fetch_source(locator, cfg, parent)
            except Exception as exc:  # pragma: no cover - exact failures vary
                skipped.append(f"{locator}: {exc}")
                continue

            if source.retrieval_hash in seen_hashes:
                continue
            seen_hashes.add(source.retrieval_hash)
            sources.append(source)
            approaches.append(self._build_approach(source, body))
            if trace is not None:
                trace.log_retrieval("corpus", source=locator, n_hits=1)

            if depth >= cfg.max_crawl_depth:
                continue
            links = self._extract_links(body, locator)
            added = 0
            for link in links:
                if added >= cfg.max_discovered_links_per_source:
                    break
                if link in seen_locators:
                    continue
                if self._is_url(link) and not self._is_allowed_url(link, cfg):
                    continue
                queue.append((link, depth + 1, locator))
                added += 1

        approaches.sort(key=lambda item: item.approach_id)
        return CorpusIngestionResult(
            sources=tuple(sorted(sources, key=lambda item: item.source_id)),
            approaches=tuple(approaches),
            skipped=tuple(skipped),
        )

    def _fetch_source(
        self,
        locator: str,
        cfg: RiemannResearchConfig,
        parent: str = "",
    ) -> tuple[SourceRecord, str]:
        if self._is_url(locator):
            if not self._is_allowed_url(locator, cfg):
                raise ValueError(f"disallowed source domain for {locator}")
            body = self._read_url(locator, timeout_s=cfg.fetch_timeout_s)
            source_kind = "url"
            title = self._extract_title(body, fallback=urlparse(locator).path.rsplit("/", 1)[-1] or locator)
        else:
            path = self._resolve_local_path(locator)
            body = path.read_text(encoding="utf-8")
            source_kind = "local_file"
            title = self._extract_title(body, fallback=path.stem)

        digest = hashlib.sha1(body.encode("utf-8")).hexdigest()
        ext = ".html" if "<html" in body.lower() else ".txt"
        cache_path = cfg.cache_dir / f"{digest}{ext}"
        cache_path.write_text(body, encoding="utf-8")

        source = SourceRecord(
            source_id=f"src-{digest[:12]}",
            locator=locator,
            title=title,
            source_kind=source_kind,
            retrieval_hash=digest,
            cache_path=str(cache_path),
            year=self._extract_year(body),
            provenance={
                "parent": parent,
                "normalized_title": title,
            },
        )
        return source, body

    def _build_approach(self, source: SourceRecord, body: str) -> ApproachCard:
        family = self._classify_family(source, body)
        template = _FAMILY_LIBRARY[family]
        summary = self._first_sentence(body)
        core_claim = str(template["claim"])
        if summary:
            core_claim = f"{core_claim} Source cue: {summary}"

        approach_id = f"approach-{hashlib.sha1((source.source_id + family).encode('utf-8')).hexdigest()[:12]}"
        return ApproachCard(
            approach_id=approach_id,
            family=family,
            core_claim=core_claim,
            assumptions=tuple(template["assumptions"]),
            mechanism=str(template["mechanism"]),
            proof_obligations=tuple(template["proof_obligations"]),
            known_blockers=tuple(template["blockers"]),
            cited_sources=(source.source_id,),
            executable_checks=tuple(template["checks"]),
            observer_scores={"source_year": float(source.year or 0)},
            summary=summary or source.title,
        )

    def _classify_family(self, source: SourceRecord, body: str) -> str:
        aligned = re.search(r"orchestrator family alignment:\s*([a-z_]+)", body, flags=re.IGNORECASE)
        if aligned:
            family = aligned.group(1).strip().lower()
            if family in _FAMILY_LIBRARY:
                return family
        text = f"{source.title}\n{body}".lower()
        scores: dict[str, int] = {}
        for family, keywords in _FAMILY_KEYWORDS.items():
            score = sum(text.count(keyword) for keyword in keywords)
            scores[family] = score
        best_family, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score <= 0:
            return "general_analytic"
        return best_family

    def _extract_links(self, body: str, base: str) -> list[str]:
        links: list[str] = []
        for match in re.findall(r'href=["\']([^"\']+)["\']', body, flags=re.IGNORECASE):
            links.append(urljoin(base, match))
        for match in re.findall(r'\[[^\]]+\]\(([^)]+)\)', body):
            links.append(urljoin(base, match))
        deduped: list[str] = []
        seen: set[str] = set()
        for link in links:
            if not link or link.startswith("#"):
                continue
            if link in seen:
                continue
            seen.add(link)
            deduped.append(link)
        return deduped

    def _read_url(self, locator: str, timeout_s: float) -> str:
        req = Request(locator, headers={"User-Agent": "OAE-RiemannResearch/1.0"})
        with urlopen(req, timeout=timeout_s) as response:  # noqa: S310 - allowlisted fetch only
            body = response.read().decode("utf-8", errors="replace")
        return body

    def _is_allowed_url(self, locator: str, cfg: RiemannResearchConfig) -> bool:
        domain = urlparse(locator).netloc.lower()
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in cfg.allowlisted_domains)

    def _resolve_local_path(self, locator: str) -> Path:
        if locator.startswith("file://"):
            return Path(urlparse(locator).path)
        return Path(locator).expanduser()

    def _is_url(self, locator: str) -> bool:
        scheme = urlparse(locator).scheme.lower()
        return scheme in {"http", "https"}

    def _extract_title(self, body: str, fallback: str) -> str:
        markdown = re.search(r"^\s*#\s+(.+)$", body, flags=re.MULTILINE)
        if markdown:
            return markdown.group(1).strip()
        html = re.search(r"<title>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
        if html:
            return re.sub(r"\s+", " ", html.group(1)).strip()
        return fallback.strip() or "untitled"

    def _extract_year(self, body: str) -> int | None:
        match = re.search(r"\b(19|20)\d{2}\b", body)
        if not match:
            return None
        return int(match.group(0))

    def _first_sentence(self, body: str) -> str:
        text = body
        if self._looks_like_json(body):
            try:
                parsed = json.loads(body)
                text = json.dumps(parsed, sort_keys=True)
            except json.JSONDecodeError:
                text = body
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
        return sentence[:220]

    def _looks_like_json(self, body: str) -> bool:
        stripped = body.lstrip()
        return stripped.startswith("{") or stripped.startswith("[")


def replace_observer_scores(card: ApproachCard, **scores: float) -> ApproachCard:
    merged = dict(card.observer_scores)
    merged.update(scores)
    return replace(card, observer_scores=merged)
