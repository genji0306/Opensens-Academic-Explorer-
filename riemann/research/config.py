"""Configuration for the recursive Riemann research orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from riemann.core.config import REPORT_DIR

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = PROJECT_ROOT / "data" / "riemann" / "research"
SEED_PACK_DIR = RESEARCH_DIR / "seed_packs"

DEFAULT_CRAWL_SEEDS = (
    str(SEED_PACK_DIR / "rh_operator_calibration_functional_equation.md"),
    str(SEED_PACK_DIR / "rh_operator_calibration_xi_symmetry.md"),
    str(SEED_PACK_DIR / "rh_operator_calibration_contour_methods.md"),
    str(REPORT_DIR / "rh_synthesis.md"),
    str(REPORT_DIR / "final_report.json"),
    str(REPORT_DIR / "math_analysis.json"),
    str(REPORT_DIR / "rh_operator_framework.md"),
    str(REPORT_DIR / "rh_projection.html"),
    str(REPORT_DIR / "rh_strip.html"),
    str(REPORT_DIR / "rh_explicit.html"),
)

DEFAULT_ALLOWLIST = (
    "arxiv.org",
    "doi.org",
    "projecteuclid.org",
    "annals.math.princeton.edu",
    "claymath.org",
    "www-users.cse.umn.edu",
    "aimath.org",
    "www.aimath.org",
    "mdpi.com",
    "www.mdpi.com",
    "pmc.ncbi.nlm.nih.gov",
)


@dataclass(frozen=True)
class RiemannResearchConfig:
    """Controls the RH recursive research campaign."""

    campaign_id: str = "latest"
    research_root: Path = field(default_factory=lambda: RESEARCH_DIR)
    seed_pack_names: tuple[str, ...] = field(default_factory=tuple)
    crawl_seeds: tuple[str, ...] = field(default_factory=lambda: DEFAULT_CRAWL_SEEDS)
    allowlisted_domains: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALLOWLIST)
    max_sources: int = 500
    max_rounds: int = 50
    max_crawl_depth: int = 1
    max_discovered_links_per_source: int = 8
    max_hypotheses_per_round: int = 8
    max_worker_runs_per_round: int = 16
    patience: int = 6
    proof_target: float = 0.92
    checkpoint_every_round: bool = True
    fetch_timeout_s: float = 10.0
    resume: bool = False
    family_coverage_round_limit: int = 4
    overused_family_penalty_start_round: int = 5
    overused_family_penalty_threshold: int = 4
    overused_family_penalty_scale: float = 0.03
    overused_family_penalty_cap: float = 0.18
    topology_mode: str = "baseline"
    preferred_route_family: str = ""
    route_lock_strict: bool = False
    route_lock_bonus_primary: float = 0.35
    route_lock_bonus_support: float = 0.08
    route_lock_penalty_off_route: float = 0.06

    # Numeric worker policy.
    use_saved_riemann_report: bool = True
    riemann_report_path: Path = field(default_factory=lambda: REPORT_DIR / "final_report.json")
    operator_framework_path: Path = field(default_factory=lambda: REPORT_DIR / "rh_operator_framework.md")
    numeric_worker_n_zeros: int = 512
    numeric_worker_target: float = 0.90
    numeric_worker_max_iterations: int = 6
    numeric_worker_patience: int = 3

    # Fixed observer weights from the approved plan.
    weight_proof_obligation_reduction: float = 0.35
    weight_consistency_with_known_results: float = 0.25
    weight_reproducibility: float = 0.15
    weight_contradiction_penalty: float = 0.15
    weight_numerical_support: float = 0.07
    weight_novelty: float = 0.03
    weight_visualization_coherence: float = 0.00

    @property
    def campaign_dir(self) -> Path:
        return self.research_root / self.campaign_id

    @property
    def cache_dir(self) -> Path:
        return self.campaign_dir / "cache"

    @property
    def checkpoints_dir(self) -> Path:
        return self.campaign_dir / "checkpoints"

    @property
    def workers_dir(self) -> Path:
        return self.campaign_dir / "workers"

    @property
    def dossiers_dir(self) -> Path:
        return self.campaign_dir / "dossiers"

    @property
    def traces_dir(self) -> Path:
        return self.campaign_dir / "traces"

    @property
    def memory_dir(self) -> Path:
        return self.campaign_dir / "research_memory"

    @property
    def approach_map_path(self) -> Path:
        return self.campaign_dir / "approach_map.json"

    @property
    def summary_path(self) -> Path:
        return self.campaign_dir / "summary.json"

    @property
    def seed_manifest_path(self) -> Path:
        return self.campaign_dir / "seed_manifest.json"

    @property
    def operator_language_path(self) -> Path:
        return self.campaign_dir / "operator_language_v0.json"

    @property
    def operator_calibration_path(self) -> Path:
        return self.campaign_dir / "operator_calibration.json"

    @property
    def failure_atlas_path(self) -> Path:
        return self.campaign_dir / "failure_atlas.json"

    @property
    def certificate_report_path(self) -> Path:
        return self.campaign_dir / "certificate_report.json"

    @property
    def obligation_ledger_path(self) -> Path:
        return self.campaign_dir / "obligation_ledger.json"

    @property
    def campaign_benchmark_path(self) -> Path:
        return self.campaign_dir / "campaign_benchmark.json"

    @property
    def dead_end_library_path(self) -> Path:
        return self.campaign_dir / "dead_end_library.json"

    @property
    def dashboard_path(self) -> Path:
        return self.campaign_dir / "research_dashboard.html"

    @property
    def lean_rh_root(self) -> Path:
        return PROJECT_ROOT / "lean" / "RH"

    @property
    def lean_residue_path(self) -> Path:
        return self.campaign_dir / "lean_residue.json"

    @property
    def literature_connection_map_path(self) -> Path:
        return self.campaign_dir / "attempt_connection_map.json"

    @property
    def literature_connection_dashboard_path(self) -> Path:
        return self.campaign_dir / "attempt_connection_dashboard.html"


def ensure_dirs(cfg: RiemannResearchConfig) -> None:
    for path in (
        cfg.research_root,
        SEED_PACK_DIR,
        cfg.campaign_dir,
        cfg.cache_dir,
        cfg.checkpoints_dir,
        cfg.workers_dir,
        cfg.dossiers_dir,
        cfg.traces_dir,
        cfg.memory_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
