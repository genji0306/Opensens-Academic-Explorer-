"""
Agent GCD — Prediction Agent
==============================
Responsible for:
  1. Loading converged novel candidates from the CS/Sin/Ob feedback loop
  2. Clustering and ranking candidates by family
  3. Extrapolating new high-Tc predictions beyond existing candidates
  4. Computing novelty scores via NEMAD feature vector distance
  5. Generating per-family reports and a global top-candidates list
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.core.config import (
    NOVEL_CANDIDATES_DIR,
    SYNTHETIC_DIR,
    CRYSTAL_PATTERNS_DIR,
    DATA_DIR,
    ensure_dirs,
)
from src.core.schemas import (
    PatternCard,
    SyntheticStructure,
    LatticeParams,
    load_pattern_catalog,
)
from src.agents.agent_sin import (
    generate_structures_for_pattern,
    get_family_key,
    estimate_omega_log,
    PATTERN_FAMILY_MAP,
)
from src.agents.agent_p import pressure_scan_tc
from src.agents.agent_cs import (
    parse_composition,
    compute_feature_vector,
    ELEMENT_DATA,
)

logger = logging.getLogger("AgentGCD")

PREDICTIONS_DIR = DATA_DIR / "predictions"
FAMILY_REPORTS_DIR = PREDICTIONS_DIR / "family_reports"

# Known experimental compounds (for novelty filtering)
KNOWN_COMPOUNDS = {
    "YBa2Cu3O7", "La1.85Sr0.15CuO4", "Bi2Sr2CaCu2O8", "HgBa2Ca2Cu3O8",
    "Tl2Ba2Ca2Cu3O10", "LaFeAsO0.9F0.1", "Ba0.6K0.4Fe2As2", "NdFeAsO0.86F0.14",
    "FeSe", "FeSe0.5Te0.5", "CeCoIn5", "CeRhIn5", "PuCoGa5",
    "MgB2", "Mg0.9Al0.1B2", "MgB1.8C0.2",
    "Nb3Sn", "Nb3Ge", "V3Si", "H3S", "LaH10",
    "Nd0.8Sr0.2NiO2", "La3Ni2O7", "PbMo6S8",
}

# Physical Tc limits by family (K) — used for extrapolation bounds
FAMILY_TC_LIMITS = {
    "cuprate": 200.0,
    "iron_pnictide": 80.0,
    "iron_chalcogenide": 100.0,
    "heavy_fermion": 30.0,
    "mgb2_type": 80.0,
    "a15": 40.0,
    "hydride": 350.0,
    "nickelate": 120.0,
    "chevrel": 25.0,
}

# Raised ceilings for RTAP (Room-Temperature Ambient Pressure) discovery
RTAP_FAMILY_TC_LIMITS = {
    "cuprate": 250.0,
    "engineered_cuprate": 350.0,
    "kagome": 80.0,
    "ternary_hydride": 300.0,
    "infinite_layer": 150.0,
    "topological": 30.0,
    "2d_heterostructure": 50.0,
    "carbon_based": 60.0,
    "iron_pnictide": 80.0,
    "iron_chalcogenide": 100.0,
    "nickelate": 200.0,
    "hydride": 350.0,
    "mof_sc": 100.0,
    "flat_band": 200.0,
    "heavy_fermion": 10.0,
    "mgb2_type": 80.0,
    "a15": 40.0,
    "chevrel": 20.0,
}


class AgentGCD:
    """Prediction Agent — generates high-Tc superconductor predictions."""

    def __init__(self):
        ensure_dirs()
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        FAMILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def load_candidates(self) -> pd.DataFrame:
        """Load all novel candidates from data/novel_candidates/."""
        csv_files = sorted(NOVEL_CANDIDATES_DIR.glob("candidates_iteration_*.csv"))
        if not csv_files:
            raise FileNotFoundError("No novel candidate files found")

        dfs = []
        for f in csv_files:
            df = pd.read_csv(f)
            iter_num = int(f.stem.split("_")[-1])
            df["source_iteration"] = iter_num
            dfs.append(df)

        combined = pd.concat(dfs, ignore_index=True)
        # Deduplicate by structure_id (same candidate may appear in multiple iterations)
        combined = combined.drop_duplicates(subset="structure_id", keep="last")
        logger.info(f"Loaded {len(combined)} unique novel candidates from {len(csv_files)} files")
        return combined

    def load_tuned_params(self) -> dict:
        """Load model_state.json (converged parameters)."""
        state_path = SYNTHETIC_DIR / "model_state.json"
        if state_path.exists():
            with open(state_path) as f:
                params = json.load(f)
            logger.info(f"Loaded {len(params)} tuned parameters")
            return params
        logger.warning("No model_state.json found, using defaults")
        return {}

    def load_patterns(self) -> list[PatternCard]:
        """Load latest pattern catalog."""
        catalogs = sorted(CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"))
        if not catalogs:
            raise FileNotFoundError("No pattern catalogs found")
        path = catalogs[-1]
        patterns = load_pattern_catalog(path)
        logger.info(f"Loaded {len(patterns)} patterns from {path.name}")
        return patterns

    def cluster_by_family(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Group candidates by superconductor family."""
        df = df.copy()
        df["family"] = df["pattern_id"].apply(
            lambda pid: get_family_key(pid) if isinstance(pid, str) else "unknown"
        )
        groups = {}
        for family, group_df in df.groupby("family"):
            groups[family] = group_df.sort_values("predicted_Tc_K", ascending=False)
        logger.info(f"Clustered into {len(groups)} families: {list(groups.keys())}")
        return groups

    def compute_novelty_score(self, composition: str) -> float:
        """
        Score based on compositional distance from known superconductors.
        Uses NEMAD feature vectors: Euclidean distance in 11D feature space.
        Returns 0-1 (higher = more novel).
        """
        comp = parse_composition(composition)
        if not comp:
            return 0.0

        candidate_vec = np.array(compute_feature_vector(comp))

        # Compute distance to all known compounds
        min_dist = float("inf")
        for known in KNOWN_COMPOUNDS:
            known_comp = parse_composition(known)
            if known_comp:
                known_vec = np.array(compute_feature_vector(known_comp))
                dist = np.linalg.norm(candidate_vec - known_vec)
                min_dist = min(min_dist, dist)

        # Normalize: typical distances are 0-100, map to 0-1
        # Sigmoid-like scaling: novelty increases with distance
        novelty = 1.0 - np.exp(-min_dist / 50.0)
        return round(float(novelty), 4)

    def rank_within_family(self, family_df: pd.DataFrame) -> pd.DataFrame:
        """
        Rank candidates within a family by composite score.
        Score = 0.5 * normalized_Tc + 0.3 * stability_confidence + 0.2 * novelty_score
        """
        df = family_df.copy()

        # Compute novelty scores
        df["novelty_score"] = df["composition"].apply(self.compute_novelty_score)

        # Normalize Tc within family
        tc_max = df["predicted_Tc_K"].max()
        tc_min = df["predicted_Tc_K"].min()
        if tc_max > tc_min:
            df["normalized_Tc"] = (df["predicted_Tc_K"] - tc_min) / (tc_max - tc_min)
        else:
            df["normalized_Tc"] = 1.0

        # Composite score
        df["gcd_score"] = (
            0.5 * df["normalized_Tc"]
            + 0.3 * df["stability_confidence"]
            + 0.2 * df["novelty_score"]
        )

        return df.sort_values("gcd_score", ascending=False)

    def rank_within_family_rtap(self, family_df):
        """RTAP ranking: ambient Tc is primary, stability is secondary."""
        df = family_df.copy()

        # Use ambient_pressure_Tc_K if available
        tc_col = "ambient_pressure_Tc_K" if "ambient_pressure_Tc_K" in df.columns else "predicted_Tc_K"

        # Normalize Tc to [0, 1]
        tc_max = df[tc_col].max()
        tc_min = df[tc_col].min()
        if tc_max > tc_min:
            df["ambient_tc_normalized"] = (df[tc_col] - tc_min) / (tc_max - tc_min)
        else:
            df["ambient_tc_normalized"] = 0.5

        # Electronic indicator: favor high lambda
        if "electron_phonon_lambda" in df.columns:
            lam_max = df["electron_phonon_lambda"].max()
            df["lambda_normalized"] = df["electron_phonon_lambda"] / max(lam_max, 0.01)
        else:
            df["lambda_normalized"] = 0.5

        df["rtap_score"] = (
            0.40 * df["ambient_tc_normalized"]
            + 0.25 * df.get("stability_confidence", 0.5)
            + 0.20 * df["lambda_normalized"]
            + 0.15 * df.get("novelty_score", 0.5)
        )

        return df.sort_values("rtap_score", ascending=False)

    def extrapolate_high_tc(
        self, pattern: PatternCard, tuned_params: dict, num_structures: int = 500
    ) -> list[SyntheticStructure]:
        """
        Generate NEW predictions beyond existing candidates.
        Uses tuned parameters with wider perturbation for more aggressive exploration.
        """
        # Use tuned params but with wider exploration
        exploration_params = dict(tuned_params)
        exploration_params["perturbation_scale"] = 0.15  # 3x normal
        # Don't filter by stability threshold — keep more candidates
        # generate_structures_for_pattern uses STABILITY_THRESHOLD_MEV (50 meV)
        # We generate more to compensate for the stability filter

        structures = generate_structures_for_pattern(
            pattern=pattern,
            num_structures=num_structures,
            iteration=999,  # Mark as extrapolation
            model_adjustments=exploration_params,
        )
        return structures

    def extrapolate_rtap_candidates(self, patterns, tuned_params, num_per_pattern=500):
        """Aggressive RTAP exploration with widened perturbation and cross-family substitution."""
        from src.agents.agent_sin import generate_structures_for_pattern
        from src.core.config import RTAP_STABILITY_THRESHOLD_MEV

        exploration_params = dict(tuned_params)
        exploration_params["perturbation_scale"] = 0.25  # 5x normal

        all_candidates = []
        for pattern in patterns:
            structures = generate_structures_for_pattern(
                pattern=pattern,
                num_structures=num_per_pattern,
                iteration=999,  # Sentinel for extrapolation
                model_adjustments=exploration_params,
            )
            all_candidates.extend(structures)

        # Sort by ambient Tc, take top candidates
        all_candidates.sort(key=lambda s: s.ambient_pressure_Tc_K, reverse=True)
        return all_candidates[:50]  # Top 50 RTAP candidates

    def generate_family_report(
        self, family: str, ranked_df: pd.DataFrame, extrapolated: list[SyntheticStructure]
    ) -> dict:
        """Generate a per-family report with top candidates and statistics."""
        top_10 = ranked_df.head(10)

        report = {
            "family": family,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "existing_candidates": {
                "total_count": len(ranked_df),
                "tc_statistics": {
                    "mean": round(float(ranked_df["predicted_Tc_K"].mean()), 2),
                    "max": round(float(ranked_df["predicted_Tc_K"].max()), 2),
                    "min": round(float(ranked_df["predicted_Tc_K"].min()), 2),
                    "std": round(float(ranked_df["predicted_Tc_K"].std()), 2),
                },
                "top_10": top_10[
                    [c for c in ["structure_id", "composition", "predicted_Tc_K", "electron_phonon_lambda",
                     "stability_confidence", "novelty_score", "gcd_score",
                     "Tc_ambient_K", "Tc_optimal_K", "P_optimal_GPa"] if c in top_10.columns]
                ].to_dict("records"),
            },
            "extrapolated_candidates": {
                "total_generated": len(extrapolated),
                "tc_statistics": {},
                "top_10": [],
            },
            "tc_physical_limit_K": FAMILY_TC_LIMITS.get(family, 100),
        }

        if extrapolated:
            extrap_tcs = [s.predicted_Tc_K for s in extrapolated]
            report["extrapolated_candidates"]["tc_statistics"] = {
                "mean": round(float(np.mean(extrap_tcs)), 2),
                "max": round(float(np.max(extrap_tcs)), 2),
                "min": round(float(np.min(extrap_tcs)), 2),
            }
            # Top 10 extrapolated by Tc
            sorted_extrap = sorted(extrapolated, key=lambda s: s.predicted_Tc_K, reverse=True)
            report["extrapolated_candidates"]["top_10"] = [
                {
                    "structure_id": s.structure_id,
                    "composition": s.composition,
                    "predicted_Tc_K": s.predicted_Tc_K,
                    "electron_phonon_lambda": s.electron_phonon_lambda,
                    "energy_above_hull_meV": s.energy_above_hull_meV,
                    "stability_confidence": s.stability_confidence,
                }
                for s in sorted_extrap[:10]
            ]

        return report

    def _add_pressure_predictions(
        self, ranked_df: pd.DataFrame, pattern_map: dict, tuned_params: dict
    ) -> pd.DataFrame:
        """Run pressure scans on top 10 candidates and add Tc_optimal / P_optimal columns."""
        df = ranked_df.copy()
        df["Tc_ambient_K"] = df["predicted_Tc_K"]
        df["Tc_optimal_K"] = df["predicted_Tc_K"]
        df["P_optimal_GPa"] = 0.0

        top_indices = df.head(10).index
        for idx in top_indices:
            row = df.loc[idx]
            pid = row.get("pattern_id", "")
            if pid not in pattern_map:
                continue
            pattern = pattern_map[pid]
            if pattern.pressure_params is None:
                continue

            family_key = get_family_key(pid)
            mu_star = tuned_params.get("mu_star", 0.13)
            boost = tuned_params.get(f"tc_boost_{family_key}", 1.0)
            lambda_0 = row.get("electron_phonon_lambda", 0.5)
            omega_0 = estimate_omega_log(pattern)

            try:
                result = pressure_scan_tc(
                    lambda_0=lambda_0,
                    omega_log_0_K=omega_0,
                    pressure_params=pattern.pressure_params,
                    mu_star=mu_star,
                    tc_boost=boost,
                )
                df.at[idx, "Tc_optimal_K"] = round(result.Tc_optimal_K, 2)
                df.at[idx, "P_optimal_GPa"] = round(result.P_optimal_GPa, 2)
            except Exception as exc:
                logger.warning(f"Pressure scan failed for {row.get('structure_id', '?')}: {exc}")

        return df

    def run(self) -> Path:
        """Main entry: load -> cluster -> rank -> extrapolate -> save predictions."""
        logger.info("=== Agent GCD: Prediction Agent Starting ===")

        # 1. Load data
        candidates_df = self.load_candidates()
        tuned_params = self.load_tuned_params()
        patterns = self.load_patterns()
        pattern_map = {p.pattern_id: p for p in patterns}

        # 2. Cluster by family
        family_groups = self.cluster_by_family(candidates_df)

        # 3. Rank within each family
        all_ranked = []
        family_reports = {}
        all_extrapolated = []

        for family, family_df in family_groups.items():
            logger.info(f"Processing family: {family} ({len(family_df)} candidates)")

            # Rank existing candidates
            ranked = self.rank_within_family(family_df)

            # Run pressure scans on top 10 candidates
            ranked = self._add_pressure_predictions(ranked, pattern_map, tuned_params)
            all_ranked.append(ranked)

            # Find patterns for this family and extrapolate
            family_patterns = [
                p for p in patterns if get_family_key(p.pattern_id) == family
            ]
            extrapolated = []
            for pattern in family_patterns:
                new_structures = self.extrapolate_high_tc(pattern, tuned_params)
                extrapolated.extend(new_structures)
                all_extrapolated.extend(new_structures)

            logger.info(f"  Extrapolated {len(extrapolated)} new structures for {family}")

            # Generate report
            report = self.generate_family_report(family, ranked, extrapolated)
            family_reports[family] = report

            # Save per-family report
            report_path = FAMILY_REPORTS_DIR / f"{family}.json"
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2)

        # 4. Combine all ranked candidates
        if all_ranked:
            combined_ranked = pd.concat(all_ranked, ignore_index=True)
            combined_ranked = combined_ranked.sort_values("gcd_score", ascending=False)

            # Save top 50
            top_50 = combined_ranked.head(50)
            top_50_path = PREDICTIONS_DIR / "gcd_top_candidates.csv"
            top_50.to_csv(top_50_path, index=False)
            logger.info(f"Saved top 50 candidates to {top_50_path}")

            # Save all ranked
            all_ranked_path = PREDICTIONS_DIR / "gcd_all_ranked.csv"
            combined_ranked.to_csv(all_ranked_path, index=False)

        # 5. Save extrapolated candidates
        if all_extrapolated:
            extrap_rows = []
            for s in all_extrapolated:
                extrap_rows.append({
                    "structure_id": s.structure_id,
                    "pattern_id": s.pattern_id,
                    "family": get_family_key(s.pattern_id),
                    "composition": s.composition,
                    "crystal_system": s.crystal_system,
                    "space_group": s.space_group,
                    "a": s.lattice_params.a,
                    "b": s.lattice_params.b,
                    "c": s.lattice_params.c,
                    "predicted_Tc_K": s.predicted_Tc_K,
                    "electron_phonon_lambda": s.electron_phonon_lambda,
                    "energy_above_hull_meV": s.energy_above_hull_meV,
                    "stability_confidence": s.stability_confidence,
                    "pressure_GPa": s.pressure_GPa,
                    "volume_per_atom_A3": s.volume_per_atom_A3,
                })
            extrap_df = pd.DataFrame(extrap_rows)
            extrap_df = extrap_df.sort_values("predicted_Tc_K", ascending=False)
            extrap_path = PREDICTIONS_DIR / "gcd_extrapolated.csv"
            extrap_df.to_csv(extrap_path, index=False)
            logger.info(f"Saved {len(extrap_df)} extrapolated candidates to {extrap_path}")

        # 6. Save master predictions report
        master_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "existing_candidates_analyzed": len(candidates_df),
            "families_processed": list(family_reports.keys()),
            "extrapolated_total": len(all_extrapolated),
            "tuned_parameters": tuned_params,
            "family_summaries": {
                family: {
                    "existing_count": r["existing_candidates"]["total_count"],
                    "existing_max_Tc": r["existing_candidates"]["tc_statistics"]["max"],
                    "extrapolated_count": r["extrapolated_candidates"]["total_generated"],
                    "extrapolated_max_Tc": (
                        r["extrapolated_candidates"]["tc_statistics"].get("max", 0)
                    ),
                    "tc_limit_K": r["tc_physical_limit_K"],
                }
                for family, r in family_reports.items()
            },
        }
        master_path = PREDICTIONS_DIR / "gcd_predictions.json"
        with open(master_path, "w") as f:
            json.dump(master_report, f, indent=2)
        logger.info(f"Saved master predictions to {master_path}")

        logger.info("=== Agent GCD: Complete ===")
        return PREDICTIONS_DIR


def run_agent_gcd() -> Path:
    """Main entry point for Agent GCD."""
    agent = AgentGCD()
    return agent.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    path = run_agent_gcd()
    print(f"Predictions saved to: {path}")
