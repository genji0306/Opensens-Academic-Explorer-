"""
Agent P — Pressure Agent
==========================
Responsible for:
  1. Computing V(P) via 3rd-order Birch-Murnaghan equation of state
  2. Grüneisen-corrected omega_log(P) and lambda(P)
  3. Thermal contraction model (Debye-Grüneisen)
  4. Pressure-scan to find optimal Tc for each candidate
  5. Calibration against benchmark_pressure V(P) data
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import brentq
from scipy.integrate import quad

from src.core.schemas import (
    PressureParams,
    PressureResult,
    SyntheticStructure,
    PatternCard,
)
from src.agents.agent_sin import allen_dynes_tc

logger = logging.getLogger("AgentP")


# ---------------------------------------------------------------------------
# Core physics: Birch-Murnaghan equation of state
# ---------------------------------------------------------------------------

def birch_murnaghan_pressure(V: float, V0: float, B0_GPa: float, Bp: float) -> float:
    """
    3rd-order Birch-Murnaghan equation of state (forward).

    P(V) = (3B₀/2) × [(V₀/V)^(7/3) - (V₀/V)^(5/3)]
           × {1 + ¾(B₀'-4) × [(V₀/V)^(2/3) - 1]}

    Args:
        V: volume per atom (Å³)
        V0: ambient volume per atom (Å³)
        B0_GPa: bulk modulus at P=0 (GPa)
        Bp: pressure derivative of bulk modulus (dimensionless)

    Returns:
        Pressure in GPa.
    """
    if V <= 0 or V0 <= 0:
        return 0.0
    x = V0 / V
    f = x ** (7 / 3) - x ** (5 / 3)
    correction = 1.0 + 0.75 * (Bp - 4.0) * (x ** (2 / 3) - 1.0)
    return 1.5 * B0_GPa * f * correction


def volume_at_pressure(P_GPa: float, V0: float, B0_GPa: float, Bp: float) -> float:
    """
    Numerically invert Birch-Murnaghan to find V at given P.
    Uses Brent's method on P_BM(V) - P_target = 0.

    Args:
        P_GPa: target pressure (GPa)
        V0: ambient volume per atom (Å³)
        B0_GPa: bulk modulus (GPa)
        Bp: dB/dP (dimensionless)

    Returns:
        Volume per atom (Å³) at target pressure.
    """
    if P_GPa <= 0.0:
        return V0

    V_min = V0 * 0.3   # extreme compression (~300 GPa)
    V_max = V0 * 1.01   # slight expansion tolerance

    def residual(V):
        return birch_murnaghan_pressure(V, V0, B0_GPa, Bp) - P_GPa

    try:
        return brentq(residual, V_min, V_max, xtol=1e-6)
    except ValueError:
        # P_GPa too extreme for this V range
        logger.warning(f"BM inversion failed at P={P_GPa} GPa (V0={V0}), returning V_min")
        return V_min


# ---------------------------------------------------------------------------
# Grüneisen phonon frequency scaling
# ---------------------------------------------------------------------------

def gruneisen_omega_log(
    V: float, V0: float, omega_log_0_K: float, gamma: float
) -> float:
    """
    Grüneisen scaling of logarithmic average phonon frequency.

    ω_log(V) = ω_log_0 × (V₀/V)^γ

    Compression (V < V₀) → higher frequencies (stiffer lattice).
    """
    if V <= 0 or V0 <= 0:
        return omega_log_0_K
    return omega_log_0_K * (V0 / V) ** gamma


# ---------------------------------------------------------------------------
# Electron-phonon coupling pressure dependence
# ---------------------------------------------------------------------------

def lambda_at_volume(
    V: float, V0: float, lambda_0: float, eta: float
) -> float:
    """
    Volume-dependent electron-phonon coupling constant.

    λ(V) = λ₀ × (V/V₀)^η

    Derived from McMillan relation: λ ∝ N(Ef)⟨I²⟩/(M⟨ω²⟩)
    where N(Ef) ~ V^(2/3) and ⟨ω²⟩ ~ V^(-2γ).
    Net exponent: η ≈ 2γ - 2/3 (typically 2-4).

    For most materials η > 0: compression decreases λ.
    FeSe is anomalous (η < 0): spin-fluctuation enhancement
    dominates over phonon hardening under pressure.
    """
    if V <= 0 or V0 <= 0:
        return lambda_0
    return lambda_0 * (V / V0) ** eta


# ---------------------------------------------------------------------------
# Thermal contraction (Debye-Grüneisen model)
# ---------------------------------------------------------------------------

def _debye_energy_per_atom(T_K: float, debye_T_K: float) -> float:
    """
    Internal energy per atom from Debye model: U(T) = 3k_B T × D(Θ/T).

    Returns energy in eV.
    """
    kB = 8.617333262e-5  # eV/K

    if T_K <= 0:
        return 0.0

    x = debye_T_K / T_K

    if x < 0.1:
        # High-T limit: D(x→0) → 1
        return 3.0 * kB * T_K
    elif x > 30:
        # Low-T limit: D(x→∞) → (π⁴/5)/x³
        return 3.0 * kB * T_K * (np.pi ** 4 / (5.0 * x ** 3))
    else:
        # Numerical Debye function
        def integrand(t):
            if t < 1e-12:
                return 0.0
            return t ** 3 / (np.exp(t) - 1.0)

        result, _ = quad(integrand, 0, x, limit=100)
        D_x = 3.0 / x ** 3 * result
        return 3.0 * kB * T_K * D_x


def thermal_contraction_volume(
    T_K: float, V0_A3: float, gamma_th: float, debye_T_K: float, B0_GPa: float
) -> float:
    """
    Debye-Grüneisen thermal contraction from 300K to temperature T.

    ΔV/V₀ = γ_th × [U(T) - U(300K)] / (B₀ × V₀)

    Cooling (T < 300K) → negative ΔV → lattice contracts.

    Returns:
        Corrected volume per atom at temperature T (ų).
    """
    eV_to_GPa_A3 = 160.2176634  # 1 eV = 160.2 GPa·Å³

    U_T = _debye_energy_per_atom(T_K, debye_T_K)
    U_300 = _debye_energy_per_atom(300.0, debye_T_K)

    denominator = B0_GPa * V0_A3 / eV_to_GPa_A3
    if abs(denominator) < 1e-12:
        return V0_A3

    delta_V_frac = gamma_th * (U_T - U_300) / denominator
    return V0_A3 * (1.0 + delta_V_frac)


# ---------------------------------------------------------------------------
# Pressure scan: Tc(P) curve for a single candidate
# ---------------------------------------------------------------------------

def pressure_scan_tc(
    lambda_0: float,
    omega_log_0_K: float,
    pressure_params: PressureParams,
    mu_star: float = 0.13,
    tc_boost: float = 1.0,
    n_points: int = 20,
) -> PressureResult:
    """
    Scan Tc across the valid pressure range for one candidate.

    For each pressure point:
      1. V(P) from Birch-Murnaghan
      2. ω_log(P) from Grüneisen scaling
      3. λ(P) from volume-dependent coupling
      4. Tc(P) from Allen-Dynes formula

    Returns PressureResult with ambient Tc, optimal Tc, and full Tc(P) curve.
    """
    pp = pressure_params
    P_values = np.linspace(pp.P_min_GPa, pp.P_max_GPa, max(n_points, 2))
    Tc_vs_P = []

    for P in P_values:
        V_P = volume_at_pressure(P, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
        omega_P = gruneisen_omega_log(V_P, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)
        lambda_P = lambda_at_volume(V_P, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)
        Tc_P = allen_dynes_tc(lambda_P, omega_P, mu_star) * tc_boost
        if pp.Tc_ceiling_K > 0:
            Tc_P = min(Tc_P, pp.Tc_ceiling_K)
        Tc_vs_P.append([round(float(P), 2), round(float(Tc_P), 2)])

    # Find optimal pressure
    Tc_array = np.array([t[1] for t in Tc_vs_P])
    P_array = np.array([t[0] for t in Tc_vs_P])
    idx_max = int(np.argmax(Tc_array))
    Tc_optimal = float(Tc_array[idx_max])
    P_optimal = float(P_array[idx_max])

    # Ambient values (at P_min)
    V_amb = volume_at_pressure(pp.P_min_GPa, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
    lambda_amb = lambda_at_volume(V_amb, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)
    omega_amb = gruneisen_omega_log(V_amb, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)
    Tc_ambient = allen_dynes_tc(lambda_amb, omega_amb, mu_star) * tc_boost
    if pp.Tc_ceiling_K > 0:
        Tc_ambient = min(Tc_ambient, pp.Tc_ceiling_K)

    # Thermal contraction correction at T = Tc
    thermal_correction = 0.0
    if Tc_ambient > 1.0:
        V_at_Tc = thermal_contraction_volume(
            Tc_ambient, pp.V0_per_atom_A3, pp.thermal_gruneisen, pp.debye_T_K, pp.B0_GPa
        )
        lambda_th = lambda_at_volume(V_at_Tc, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)
        omega_th = gruneisen_omega_log(V_at_Tc, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)
        Tc_thermal = allen_dynes_tc(lambda_th, omega_th, mu_star) * tc_boost
        if pp.Tc_ceiling_K > 0:
            Tc_thermal = min(Tc_thermal, pp.Tc_ceiling_K)
        thermal_correction = Tc_thermal - Tc_ambient

    return PressureResult(
        structure_id="",
        Tc_ambient_K=round(Tc_ambient, 2),
        Tc_at_target_K=round(Tc_ambient, 2),  # Updated by caller for specific target
        target_pressure_GPa=pp.P_min_GPa,
        V_at_target_A3=round(V_amb, 4),
        lambda_at_target=round(lambda_amb, 4),
        omega_log_at_target_K=round(omega_amb, 2),
        Tc_optimal_K=round(Tc_optimal, 2),
        P_optimal_GPa=round(P_optimal, 2),
        Tc_vs_P=Tc_vs_P,
        thermal_correction_K=round(thermal_correction, 2),
    )


# ---------------------------------------------------------------------------
# Decompression scan for high-pressure hydrides
# ---------------------------------------------------------------------------

def ambient_decompression_scan(
    lambda_0: float,
    omega_log_0_K: float,
    pressure_params,
    mechanism: str = "bcs",
    mu_star: float = 0.13,
    n_points: int = 50,
) -> dict:
    """
    For hydride-like families: scan Tc(P) as P decreases from P_stable toward 0.

    Returns dict with:
      - tc_at_ambient: Tc at P=0 GPa (may be 0 if structure decomposes)
      - min_survival_pressure_GPa: minimum P for structural survival
      - tc_at_min_survival: Tc at minimum survival pressure
      - metastable_trapping_plausible: whether rapid quench could preserve structure
      - tc_vs_p: list of [P, Tc] pairs
    """
    from src.core.tc_models import allen_dynes_tc as ad_tc

    pp = pressure_params
    P_max = pp.P_max_GPa
    P_min = 0.0

    tc_vs_p = []
    for i in range(n_points):
        P = P_max - (P_max - P_min) * i / (n_points - 1)
        try:
            V_P = volume_at_pressure(P, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
            omega_P = gruneisen_omega_log(V_P, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)
            lambda_P = lambda_at_volume(V_P, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)
            tc_P = ad_tc(lambda_P, omega_P, mu_star)
            if pp.Tc_ceiling_K > 0:
                tc_P = min(tc_P, pp.Tc_ceiling_K)
        except Exception:
            tc_P = 0.0
        tc_vs_p.append([round(P, 2), round(tc_P, 2)])

    # Find minimum survival pressure (where Tc drops below 10% of max)
    max_tc = max(t[1] for t in tc_vs_p) if tc_vs_p else 0
    threshold = max_tc * 0.1
    min_survival_P = 0.0
    tc_at_min = 0.0
    for P, tc in reversed(tc_vs_p):  # from low P to high P
        if tc > threshold:
            min_survival_P = P
            tc_at_min = tc
            break

    # Ambient Tc
    tc_ambient = tc_vs_p[-1][1] if tc_vs_p else 0.0

    # Metastable trapping: plausible if structure has high bulk modulus
    # and the volume change from P_stable to ambient is < 30%
    metastable = False
    if pp.B0_GPa > 80 and P_max < 100:
        try:
            V_high = volume_at_pressure(P_max * 0.5, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
            volume_change = abs(V_high - pp.V0_per_atom_A3) / pp.V0_per_atom_A3
            metastable = volume_change < 0.30
        except Exception:
            pass

    return {
        "tc_at_ambient": tc_ambient,
        "min_survival_pressure_GPa": min_survival_P,
        "tc_at_min_survival": tc_at_min,
        "metastable_trapping_plausible": metastable,
        "tc_vs_p": tc_vs_p,
        "max_tc": max_tc,
    }


# ---------------------------------------------------------------------------
# Chemical pre-compression convenience wrapper
# ---------------------------------------------------------------------------

def chemical_precompression_with_trapping(
    stabilizer_electronegativity: float,
    H_fraction: float,
    B0_GPa: float = 0.0,
    P_max_GPa: float = 0.0,
    V0_per_atom_A3: float = 0.0,
) -> dict:
    """
    Convenience wrapper around tc_models.chemical_precompression_effective_P
    that also assesses whether metastable trapping is plausible.

    Metastable trapping heuristic:
      - Effective chemical P must be > 30% of external P_max
      - Bulk modulus > 80 GPa (stiff cage)
      - Volume contraction at P_max/2 < 30% of V0

    Returns dict with:
      - effective_P_GPa: chemical pre-compression estimate
      - metastable_trapping_plausible: bool
      - trapping_rationale: human-readable explanation
    """
    from src.core.tc_models import chemical_precompression_effective_P

    P_chem = chemical_precompression_effective_P(stabilizer_electronegativity, H_fraction)

    trapping = False
    reasons = []

    if P_chem > 0.3 * P_max_GPa and P_max_GPa > 0:
        reasons.append(f"Chemical P ({P_chem:.1f} GPa) > 30% of P_max ({P_max_GPa:.1f} GPa)")
    else:
        reasons.append(f"Chemical P ({P_chem:.1f} GPa) too low vs P_max ({P_max_GPa:.1f} GPa)")

    if B0_GPa > 80:
        reasons.append(f"High bulk modulus ({B0_GPa:.0f} GPa) supports cage rigidity")
        trapping = P_chem > 0.3 * P_max_GPa if P_max_GPa > 0 else False
    else:
        reasons.append(f"Low bulk modulus ({B0_GPa:.0f} GPa) — cage may collapse")

    if V0_per_atom_A3 > 0 and B0_GPa > 0 and P_max_GPa > 0:
        try:
            V_half = volume_at_pressure(P_max_GPa * 0.5, V0_per_atom_A3, B0_GPa, 4.0)
            vol_change = abs(V_half - V0_per_atom_A3) / V0_per_atom_A3
            if vol_change < 0.30:
                reasons.append(f"Moderate volume change ({vol_change:.1%}) at half P_max")
            else:
                reasons.append(f"Large volume change ({vol_change:.1%}) at half P_max — trapping unlikely")
                trapping = False
        except Exception:
            pass

    return {
        "effective_P_GPa": round(P_chem, 2),
        "metastable_trapping_plausible": trapping,
        "trapping_rationale": "; ".join(reasons),
    }


# ---------------------------------------------------------------------------
# Agent P class
# ---------------------------------------------------------------------------

class AgentP:
    """Pressure Agent — computes pressure-dependent superconducting properties."""

    def correct_tc_for_pressure(
        self,
        structure: SyntheticStructure,
        pattern: PatternCard,
        target_pressure_GPa: float = 0.0,
        omega_log_0_K: float = 300.0,
        mu_star: float = 0.13,
        tc_boost: float = 1.0,
    ) -> tuple[float, Optional[PressureResult]]:
        """
        Correct a single structure's Tc for pressure effects.

        Returns:
            (corrected_Tc, PressureResult) or (original_Tc, None) if no pressure data.
        """
        if pattern.pressure_params is None:
            return structure.predicted_Tc_K, None

        pp = pattern.pressure_params
        lambda_0 = structure.electron_phonon_lambda

        # Full pressure scan
        result = pressure_scan_tc(
            lambda_0=lambda_0,
            omega_log_0_K=omega_log_0_K,
            pressure_params=pp,
            mu_star=mu_star,
            tc_boost=tc_boost,
        )
        result.structure_id = structure.structure_id

        # Compute Tc at the specific target pressure
        V_t = volume_at_pressure(target_pressure_GPa, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
        lambda_t = lambda_at_volume(V_t, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)
        omega_t = gruneisen_omega_log(V_t, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)
        Tc_t = allen_dynes_tc(lambda_t, omega_t, mu_star) * tc_boost

        result.target_pressure_GPa = target_pressure_GPa
        result.Tc_at_target_K = round(Tc_t, 2)
        result.V_at_target_A3 = round(V_t, 4)
        result.lambda_at_target = round(lambda_t, 4)
        result.omega_log_at_target_K = round(omega_t, 2)

        return Tc_t, result

    def validate_against_experiment(
        self,
        pattern: PatternCard,
        omega_log_0_K: float,
        tc_boost: float = 1.0,
    ) -> dict:
        """
        Check if the model's dTc/dP matches experimental value for this family.
        Uses numerical differentiation at P=0 (or P_min).
        """
        if pattern.pressure_params is None:
            return {"status": "no_pressure_params"}
        if pattern.pressure_params.dTc_dP_exp_K_per_GPa is None:
            return {"status": "no_experimental_data"}

        pp = pattern.pressure_params
        lambda_0 = 1.0
        if pattern.electronic_features and pattern.electronic_features.electron_phonon_lambda:
            lambda_0 = pattern.electronic_features.electron_phonon_lambda

        # Numerical dTc/dP at P_min
        P0 = pp.P_min_GPa
        dP = 0.5  # GPa step
        P1 = P0 + dP

        V0 = volume_at_pressure(P0, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)
        V1 = volume_at_pressure(P1, pp.V0_per_atom_A3, pp.B0_GPa, pp.B0_prime)

        omega_0 = gruneisen_omega_log(V0, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)
        omega_1 = gruneisen_omega_log(V1, pp.V0_per_atom_A3, omega_log_0_K, pp.gruneisen_gamma)

        lambda_at_P0 = lambda_at_volume(V0, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)
        lambda_at_P1 = lambda_at_volume(V1, pp.V0_per_atom_A3, lambda_0, pp.eta_lambda)

        Tc_0 = allen_dynes_tc(lambda_at_P0, omega_0) * tc_boost
        Tc_1 = allen_dynes_tc(lambda_at_P1, omega_1) * tc_boost

        dTc_dP_model = (Tc_1 - Tc_0) / dP
        dTc_dP_exp = pp.dTc_dP_exp_K_per_GPa

        return {
            "status": "validated",
            "dTc_dP_model_K_per_GPa": round(dTc_dP_model, 3),
            "dTc_dP_exp_K_per_GPa": dTc_dP_exp,
            "error_K_per_GPa": round(abs(dTc_dP_model - dTc_dP_exp), 3),
            "sign_match": (dTc_dP_model > 0) == (dTc_dP_exp > 0),
        }


# ---------------------------------------------------------------------------
# Benchmark calibration (optional, for fitting EOS from DFT data)
# ---------------------------------------------------------------------------

def calibrate_B0_from_benchmark(
    benchmark_dir: Path, mat_id: str
) -> Optional[dict]:
    """
    Fit Birch-Murnaghan B0 and B0' from benchmark_pressure PBE V(P) data.

    Reads data/P000/pbe.csv through data/P150/pbe.csv, extracts
    volume_per_atom at 7 pressures, fits BM EOS.

    Returns:
        Dict with fitted {V0_per_atom_A3, B0_GPa, B0_prime} or None.
    """
    import pandas as pd
    from scipy.optimize import minimize

    pressures = [0, 25, 50, 75, 100, 125, 150]
    volumes = []

    for P in pressures:
        csv_path = benchmark_dir / f"P{P:03d}" / "pbe.csv"
        if not csv_path.exists():
            return None
        df = pd.read_csv(csv_path)
        row = df[df["mat_id"] == mat_id]
        if row.empty:
            return None
        volumes.append(float(row["volume_per_atom"].iloc[0]))

    V_data = np.array(volumes)
    P_data = np.array(pressures, dtype=float)

    def bm_residual(params):
        V0, B0, Bp = params
        P_calc = np.array([
            birch_murnaghan_pressure(V, V0, B0, Bp) for V in V_data
        ])
        return float(np.sum((P_calc - P_data) ** 2))

    result = minimize(
        bm_residual,
        x0=[V_data[0], 100.0, 4.0],
        bounds=[
            (V_data[-1] * 0.9, V_data[0] * 1.1),
            (10.0, 500.0),
            (2.0, 8.0),
        ],
    )

    if result.success:
        V0_fit, B0_fit, Bp_fit = result.x
        return {
            "V0_per_atom_A3": round(float(V0_fit), 4),
            "B0_GPa": round(float(B0_fit), 2),
            "B0_prime": round(float(Bp_fit), 3),
        }
    return None


# ---------------------------------------------------------------------------
# Batch entry point for laboratory dispatch
# ---------------------------------------------------------------------------

def run_agent_p(target_pressure_GPa: float = 0.0) -> dict:
    """Batch pressure scan over all crystal structures with pressure_params.

    Loads pattern catalog, iterates candidates with PressureParams, runs
    pressure_scan_tc for each, and saves results to data/reports/.

    Returns:
        Dict with {n_scanned, results_path, summary}.
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    from src.core.config import DATA_DIR, CRYSTAL_PATTERNS_DIR
    from src.core.schemas import load_pattern_catalog

    logger.info("=== Agent P: Batch Pressure Scan Starting ===")

    # Load latest pattern catalog
    catalogs = sorted(CRYSTAL_PATTERNS_DIR.glob("pattern_catalog_v*.json"))
    if not catalogs:
        logger.warning("No pattern catalogs found — nothing to scan")
        return {"n_scanned": 0, "results_path": None, "summary": {}}

    patterns = load_pattern_catalog(catalogs[-1])
    agent = AgentP()

    results = []
    for pattern in patterns:
        if pattern.pressure_params is None:
            continue

        pp = pattern.pressure_params
        lambda_0 = 1.0
        if pattern.electronic_features and pattern.electronic_features.electron_phonon_lambda:
            lambda_0 = pattern.electronic_features.electron_phonon_lambda

        omega_log_0 = 300.0
        if pattern.electronic_features and pattern.electronic_features.omega_log_K:
            omega_log_0 = pattern.electronic_features.omega_log_K

        pr = pressure_scan_tc(
            lambda_0=lambda_0,
            omega_log_0_K=omega_log_0,
            pressure_params=pp,
        )
        pr.structure_id = pattern.pattern_id

        results.append({
            "pattern_id": pattern.pattern_id,
            "family": pattern.family,
            "Tc_ambient_K": pr.Tc_ambient_K,
            "Tc_optimal_K": pr.Tc_optimal_K,
            "P_optimal_GPa": pr.P_optimal_GPa,
            "thermal_correction_K": pr.thermal_correction_K,
        })

        logger.info(
            f"  {pattern.pattern_id}: Tc_amb={pr.Tc_ambient_K:.1f}K, "
            f"Tc_opt={pr.Tc_optimal_K:.1f}K @ {pr.P_optimal_GPa:.1f} GPa"
        )

    # Save report
    reports_dir = DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "pressure_scan_report.json"
    report = {
        "timestamp": _dt.now(_tz.utc).isoformat(),
        "target_pressure_GPa": target_pressure_GPa,
        "n_scanned": len(results),
        "results": results,
    }
    with open(report_path, "w") as f:
        _json.dump(report, f, indent=2)

    logger.info(f"=== Agent P: Scanned {len(results)} candidates, saved to {report_path} ===")
    return {"n_scanned": len(results), "results_path": str(report_path), "summary": report}
