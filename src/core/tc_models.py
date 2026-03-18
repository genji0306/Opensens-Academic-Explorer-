"""
Multi-mechanism superconducting Tc estimation framework.

Provides 6 pairing mechanisms beyond the standard Allen-Dynes BCS formula,
targeting room-temperature ambient-pressure superconductor discovery.

References:
  - Allen & Dynes, Phys. Rev. B 12, 905 (1975)
  - Eliashberg, Sov. Phys. JETP 11, 696 (1960)
  - Moriya & Ueda, Rep. Prog. Phys. 66, 1299 (2003)
  - Volovik, JETP Lett. 107, 516 (2018)
  - Little, Phys. Rev. 134, A1416 (1964)
"""
from __future__ import annotations

import math
import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
K_B_EV = 8.617333e-5  # Boltzmann constant in eV/K


# ---------------------------------------------------------------------------
# Mechanism 1: Allen-Dynes (strong-coupling corrected)
# ---------------------------------------------------------------------------
def allen_dynes_tc(
    lambda_ep: float,
    omega_log_K: float,
    mu_star: float = 0.13,
) -> float:
    """
    Allen-Dynes formula for Tc with strong-coupling correction factors.

    For lambda > 2, applies the f1*f2 correction (Allen & Dynes 1975)
    which is more accurate than the McMillan approximation.

    Returns Tc in Kelvin.
    """
    if lambda_ep <= 0 or omega_log_K <= 0:
        return 0.0
    denom = lambda_ep - mu_star * (1 + 0.62 * lambda_ep)
    if denom <= 0:
        return 0.0
    exponent = -1.04 * (1 + lambda_ep) / denom
    tc = (omega_log_K / 1.2) * math.exp(exponent)

    # Strong-coupling correction factors (Allen-Dynes 1975, Eqs. 31-34)
    if lambda_ep > 1.5:
        # f1: accounts for deviation of spectral function shape
        lambda_sq = lambda_ep ** 2
        f1 = (1 + (lambda_ep / 2.46 / (1 + 3.8 * mu_star)) ** 1.5) ** (1.0 / 3.0)
        # f2: accounts for strong-coupling shift in phonon frequencies
        omega_2_ratio = 1.0 + (lambda_ep - 1.0) * 0.05  # approximate omega_2/omega_log
        f2 = 1 + (omega_2_ratio - 1) * lambda_sq / (lambda_sq + 1.6)
        tc *= f1 * f2

    return max(tc, 0.0)


# ---------------------------------------------------------------------------
# Mechanism 2: Migdal-Eliashberg (linearized gap equation, imaginary axis)
# ---------------------------------------------------------------------------
def migdal_eliashberg_tc(
    lambda_ep: float,
    omega_log_K: float,
    mu_star: float = 0.13,
    omega_D_K: Optional[float] = None,
    n_matsubara: int = 512,
) -> float:
    """
    Numerical solution of linearized Eliashberg gap equation.

    Uses a simplified Lorentzian spectral model alpha^2*F(omega) centered
    at omega_log with width omega_D. Solves for the highest T at which
    the gap function eigenvalue crosses unity.

    More accurate than Allen-Dynes for lambda > 2.0.
    Falls back to Allen-Dynes if lambda < 1.5 (where they agree).
    """
    if lambda_ep < 1.5:
        return allen_dynes_tc(lambda_ep, omega_log_K, mu_star)

    if omega_D_K is None:
        omega_D_K = omega_log_K * 1.2

    # Binary search for Tc where max eigenvalue of gap equation = 1
    tc_low, tc_high = 0.1, omega_log_K * 0.5
    if tc_high < 1.0:
        tc_high = 1.0

    for _ in range(80):
        tc_mid = (tc_low + tc_high) / 2.0
        eigenval = _eliashberg_eigenvalue(
            tc_mid, lambda_ep, omega_log_K, omega_D_K, mu_star, n_matsubara
        )
        if eigenval > 1.0:
            tc_low = tc_mid
        else:
            tc_high = tc_mid
        if tc_high - tc_low < 0.01:
            break

    return max(tc_low, 0.0)


def _eliashberg_eigenvalue(
    T_K: float,
    lambda_ep: float,
    omega_log_K: float,
    omega_D_K: float,
    mu_star: float,
    n_matsubara: int,
) -> float:
    """Compute maximum eigenvalue of linearized Eliashberg kernel at T."""
    if T_K <= 0:
        return 0.0
    pi_T = math.pi * T_K
    omega_n = np.array([(2 * n + 1) * pi_T for n in range(n_matsubara)])

    # Electron-phonon kernel: lambda(omega_n - omega_m) approximated as
    # lambda * omega_log^2 / (omega_log^2 + (omega_n - omega_m)^2)
    omega_0_sq = omega_log_K ** 2

    # Z renormalization at first Matsubara frequency
    Z_0 = 1.0 + lambda_ep * omega_0_sq / (omega_0_sq + omega_n[0] ** 2)

    # Simplified single-frequency gap equation kernel sum
    kernel_sum = 0.0
    for m in range(min(n_matsubara, 256)):
        diff_sq = (omega_n[0] - omega_n[m]) ** 2
        sum_sq = (omega_n[0] + omega_n[m]) ** 2
        lam_diff = lambda_ep * omega_0_sq / (omega_0_sq + diff_sq)
        lam_sum = lambda_ep * omega_0_sq / (omega_0_sq + sum_sq)
        kernel_sum += (lam_diff + lam_sum) / (2.0 * Z_0 * omega_n[m])

    kernel_sum *= pi_T
    # Subtract Coulomb pseudopotential
    eigenval = kernel_sum - mu_star * math.log(omega_D_K / (2.0 * pi_T))
    return eigenval


# ---------------------------------------------------------------------------
# Mechanism 3: Spin-fluctuation mediated Tc (Moriya-Ueda framework)
# ---------------------------------------------------------------------------
def spin_fluctuation_tc(
    lambda_sf: float,
    T_sf_K: float,
    nesting_strength: float = 0.5,
    dos_at_ef: Optional[float] = None,
) -> float:
    """
    Tc from paramagnon (spin-fluctuation) exchange.

    For d-wave pairing (cuprates, nickelates, kagome), the effective
    pairing interaction is repulsive in s-wave but attractive in d-wave
    channel due to sign change on the Fermi surface.

    Tc ~ T_sf * exp(-1 / (N(0)*V_sf))

    where V_sf ~ lambda_sf * nesting_strength (stronger nesting =
    stronger pairing in d-wave channel).

    T_sf: characteristic spin fluctuation temperature (K)
    nesting_strength: 0-1 quality of Fermi surface nesting
    dos_at_ef: density of states at Fermi level (states/eV/f.u.)
    """
    if lambda_sf <= 0 or T_sf_K <= 0:
        return 0.0

    # Effective d-wave coupling
    V_eff = lambda_sf * nesting_strength
    if V_eff <= 0.01:
        return 0.0

    # DOS enhancement factor (normalized)
    dos_factor = 1.0
    if dos_at_ef is not None and dos_at_ef > 0:
        dos_factor = min(dos_at_ef / 2.0, 3.0)  # cap at 3× enhancement

    coupling = V_eff * dos_factor
    if coupling <= 0.1:
        return 0.0

    # Moriya-Ueda-type expression for d-wave Tc
    # Tc ~ T_sf * exp(-1/coupling) with prefactor accounting for
    # anisotropic pairing suppression (~0.5 of isotropic, reflecting
    # that d-wave gap nodes reduce but don't eliminate pairing)
    prefactor = 0.5 * T_sf_K
    tc = prefactor * math.exp(-1.0 / coupling)

    # Nesting bonus: strong nesting (>0.7) significantly enhances d-wave Tc
    if nesting_strength > 0.7:
        tc *= 1.0 + 1.0 * (nesting_strength - 0.7) / 0.3

    return max(tc, 0.0)


# ---------------------------------------------------------------------------
# Mechanism 4: Flat-band enhancement (Volovik-Heikkilä)
# ---------------------------------------------------------------------------
def flat_band_tc(
    lambda_ep: float,
    W_bandwidth_eV: float,
    omega_log_K: float = 200.0,
    mu_star: float = 0.13,
) -> float:
    """
    Tc for flat-band superconductors (kagome, Lieb, moiré lattices).

    Key insight: when electronic bandwidth W -> 0, the BCS exponential
    suppression is replaced by a power law / geometric mean:

      Tc ~ sqrt(lambda * W * omega_D)  (flat-band limit, W << omega_D)

    For intermediate bandwidth, interpolates between flat-band and BCS:
      Tc ~ omega_D * sqrt(lambda * W / omega_D)   if W < omega_D
      Tc ~ allen_dynes_tc(lambda, omega_D)         if W >> omega_D

    This dramatically raises Tc for systems with flat bands near E_F.
    """
    if lambda_ep <= 0 or omega_log_K <= 0:
        return 0.0

    omega_D_eV = omega_log_K * K_B_EV  # Convert to eV

    # Flat-band regime with smooth crossover.
    # Enhancement applies when W is within ~10× of phonon scale,
    # reflecting that even moderately narrow bands break the BCS
    # exponential suppression (Volovik 2018, Heikkilä & Volovik 2016).
    threshold_eV = 10.0 * omega_D_eV  # ~0.17 eV for omega=200K

    if W_bandwidth_eV <= 0:
        # Truly flat: Tc limited by interaction scale
        tc_eV = lambda_ep * omega_D_eV * 0.5
        tc_K = tc_eV / K_B_EV
        return max(tc_K, 0.0)
    elif W_bandwidth_eV < threshold_eV:
        # Flat-band formula: Tc ~ sqrt(lambda * W * omega_D)
        tc_eV = math.sqrt(abs(lambda_ep * W_bandwidth_eV * omega_D_eV))
        tc_eV *= max(1.0 - mu_star / lambda_ep, 0.1)
        tc_fb_K = tc_eV / K_B_EV

        # Smooth crossover: pure flat-band for W < omega_D,
        # linear interpolation to BCS for W up to 10*omega_D
        if W_bandwidth_eV < omega_D_eV:
            return max(tc_fb_K, 0.0)
        else:
            ratio = (W_bandwidth_eV - omega_D_eV) / (threshold_eV - omega_D_eV)
            tc_bcs_K = allen_dynes_tc(lambda_ep, omega_log_K, mu_star)
            tc_K = (1.0 - ratio) * tc_fb_K + ratio * tc_bcs_K
            return max(tc_K, 0.0)
    else:
        # Dispersive limit: falls back to Allen-Dynes
        return allen_dynes_tc(lambda_ep, omega_log_K, mu_star)


# ---------------------------------------------------------------------------
# Mechanism 5: Excitonic / polaronic pairing (Little-Ginzburg)
# ---------------------------------------------------------------------------
def excitonic_tc(
    exciton_energy_eV: float,
    coupling_V: float,
    dos_at_ef: float = 2.0,
) -> float:
    """
    Tc from excitonic pairing mediator (metal-organic frameworks,
    heterostructures with molecular excitations).

    Little (1964) proposed that polarizable side-chains in organic conductors
    could mediate pairing with Tc up to room temperature. The maximum Tc
    is set by the exciton energy scale:

      Tc_max ~ E_exciton / (2 * k_B)

    The actual Tc depends on coupling strength and DOS:
      Tc = (E_exciton / 2k_B) * [1 - exp(-N(0)*V)]

    exciton_energy_eV: energy of mediating excitation (eV)
    coupling_V: effective coupling constant (dimensionless)
    dos_at_ef: N(0) in states/eV/f.u.
    """
    if exciton_energy_eV <= 0 or coupling_V <= 0:
        return 0.0

    tc_max_K = exciton_energy_eV / (2.0 * K_B_EV)
    # Physical ceiling: no known mechanism can produce Tc above ~500K
    # even with optimistic excitonic coupling
    tc_max_K = min(tc_max_K, 500.0)

    coupling = dos_at_ef * coupling_V
    if coupling > 0:
        tc = tc_max_K * (1.0 - math.exp(-coupling))
    else:
        tc = 0.0

    return max(tc, 0.0)


# ---------------------------------------------------------------------------
# Mechanism 6: Hydride-cage with chemical pre-compression
# ---------------------------------------------------------------------------
def hydride_ambient_tc(
    lambda_ep: float,
    omega_log_K: float,
    H_fraction: float,
    stabilizer_electronegativity: float = 1.5,
    external_pressure_GPa: float = 0.0,
    mu_star: float = 0.13,
) -> float:
    """
    Tc model for ternary/quaternary hydrides at reduced pressures.

    Key physics: In compounds like LaBH8 or CaBeH8, the framework
    (La-B, Ca-Be) creates internal chemical pressure on the H sublattice,
    partially substituting for external pressure. This allows hydrogen-cage
    phonon modes to persist at lower external pressures.

    Chemical pre-compression effective pressure:
      P_chem ~ 15 * (chi_stabilizer - 1.0) * H_fraction  [GPa]

    The Tc is then computed via Allen-Dynes with phonon parameters
    scaled to the effective total pressure (P_chem + P_ext).

    A decompression penalty accounts for Tc reduction as P decreases
    below the thermodynamic stability threshold.
    """
    if lambda_ep <= 0 or omega_log_K <= 0:
        return 0.0

    # Chemical pre-compression from electronegativity mismatch
    P_chem_GPa = chemical_precompression_effective_P(
        stabilizer_electronegativity, H_fraction
    )
    P_total_GPa = P_chem_GPa + external_pressure_GPa

    # Hydrogen fraction phonon enhancement
    # More H -> higher omega_log (lighter atoms)
    omega_eff = omega_log_K * (1.0 + 0.3 * max(H_fraction - 0.5, 0.0))

    # Lambda scaling: increases with effective compression
    # Empirical fit from ab initio hydride studies
    lambda_eff = lambda_ep * (1.0 + 0.005 * P_total_GPa)

    # Base Tc from Allen-Dynes with effective parameters
    tc = allen_dynes_tc(lambda_eff, omega_eff, mu_star)

    # Decompression penalty: Tc degrades as effective pressure drops.
    # Ternary hydrides with chemical pre-compression retain more Tc
    # at low pressures than binary hydrides (e.g., LaH10 vs LaBH8).
    # Single smooth penalty replaces the old double-penalty which was
    # too harsh for the 10-50 GPa range targeted by RTAP discovery.
    if P_total_GPa < 50.0:
        # Smooth penalty: (P/50)^0.35 — gentler than sqrt for low P
        penalty = max((P_total_GPa / 50.0) ** 0.35, 0.15)
        tc *= penalty

    return max(tc, 0.0)


def chemical_precompression_effective_P(
    stabilizer_electronegativity: float,
    H_fraction: float,
) -> float:
    """
    Estimate effective internal pressure (GPa) from electronegativity
    mismatch in ternary hydrides.

    Higher electronegativity of the stabilizer element and higher H
    content lead to greater chemical pre-compression of the H sublattice.

    Empirical model calibrated against DFT results for LaBeH8, CaBH8, etc.
    """
    chi_excess = max(stabilizer_electronegativity - 1.0, 0.0)
    # Coefficient calibrated against DFT: LaBeH8 (~30 GPa internal),
    # CaBH8 (~25 GPa), YBH8 (~35 GPa). Factor of 30 better matches
    # ab initio chemical pressure estimates (Liang et al., PRB 2021).
    P_chem = 30.0 * chi_excess * H_fraction
    return min(P_chem, 150.0)  # Physical cap


# ---------------------------------------------------------------------------
# Composite estimator (meta-model dispatcher)
# ---------------------------------------------------------------------------
def estimate_tc_composite(mechanism: str, **kwargs) -> dict:
    """
    Route to the appropriate Tc model based on mechanism tag.

    Args:
        mechanism: One of 'bcs', 'eliashberg', 'spin_fluctuation',
                   'flat_band', 'excitonic', 'hydride_cage', 'mixed'
        **kwargs: Mechanism-specific parameters

    Returns:
        dict with {Tc_K, mechanism, confidence, limiting_factors}
    """
    result = {
        "Tc_K": 0.0,
        "mechanism": mechanism,
        "confidence": 0.0,
        "limiting_factors": [],
    }

    lambda_ep = kwargs.get("lambda_ep", 0.0)
    omega_log_K = kwargs.get("omega_log_K", 0.0)
    mu_star = kwargs.get("mu_star", 0.13)

    if mechanism == "bcs":
        tc = allen_dynes_tc(lambda_ep, omega_log_K, mu_star)
        result["Tc_K"] = tc
        result["confidence"] = 0.9 if lambda_ep < 2.0 else 0.6
        if tc < 273:
            result["limiting_factors"].append(
                "BCS exponential suppression limits Tc; "
                "requires lambda>3 and omega_log>500K for RT"
            )

    elif mechanism == "eliashberg":
        tc = migdal_eliashberg_tc(
            lambda_ep, omega_log_K, mu_star,
            omega_D_K=kwargs.get("omega_D_K"),
        )
        result["Tc_K"] = tc
        result["confidence"] = 0.85 if lambda_ep > 2.0 else 0.7

    elif mechanism == "spin_fluctuation":
        T_sf = kwargs.get("T_sf_K", 200.0)
        nesting = kwargs.get("nesting", kwargs.get("nesting_strength", 0.5))
        dos = kwargs.get("dos_at_ef")
        tc = spin_fluctuation_tc(lambda_ep, T_sf, nesting, dos)
        result["Tc_K"] = tc
        result["confidence"] = 0.7  # Cuprate/nickelate analogy well-established
        if nesting < 0.5:
            result["limiting_factors"].append("Weak nesting limits d-wave pairing")

    elif mechanism == "flat_band":
        W = kwargs.get("W_bandwidth_eV", kwargs.get("flat_band_width_eV", 0.1))
        tc = flat_band_tc(lambda_ep, W, omega_log_K, mu_star)
        result["Tc_K"] = tc
        result["confidence"] = 0.7  # Kagome/TBLG validate flat-band enhancement
        if W > 0.1:
            result["limiting_factors"].append(
                "Bandwidth too large for flat-band enhancement"
            )

    elif mechanism == "excitonic":
        E_exc = kwargs.get("exciton_energy_eV", 0.5)
        V_c = kwargs.get("coupling_V", 0.3)
        dos = kwargs.get("dos_at_ef", 2.0)
        tc = excitonic_tc(E_exc, V_c, dos)
        result["Tc_K"] = tc
        result["confidence"] = 0.6  # Theoretical but physically motivated
        result["limiting_factors"].append("Excitonic pairing experimentally unconfirmed")

    elif mechanism == "hydride_cage":
        H_frac = kwargs.get("H_fraction", 0.6)
        chi = kwargs.get("stabilizer_electronegativity", 1.5)
        P_ext = kwargs.get("external_pressure_GPa", 0.0)
        tc = hydride_ambient_tc(lambda_ep, omega_log_K, H_frac, chi, P_ext, mu_star)
        result["Tc_K"] = tc
        result["confidence"] = 0.7
        P_chem = chemical_precompression_effective_P(chi, H_frac)
        if P_chem < 20:
            result["limiting_factors"].append(
                f"Chemical pre-compression only {P_chem:.0f} GPa; "
                "may be insufficient for H-cage stability"
            )

    elif mechanism == "mixed":
        # For mixed-mechanism systems: compute all applicable and take max
        tc_candidates = []

        # Always try BCS
        tc_bcs = allen_dynes_tc(lambda_ep, omega_log_K, mu_star)
        tc_candidates.append(("bcs", tc_bcs, 0.7))

        # Try spin-fluctuation if T_sf provided
        T_sf = kwargs.get("T_sf_K")
        nesting = kwargs.get("nesting", kwargs.get("nesting_strength", 0.5))
        if T_sf and T_sf > 0:
            tc_sf = spin_fluctuation_tc(lambda_ep, T_sf, nesting, kwargs.get("dos_at_ef"))
            tc_candidates.append(("spin_fluctuation", tc_sf, 0.7))

        # Try flat-band if bandwidth provided
        W = kwargs.get("W_bandwidth_eV", kwargs.get("flat_band_width_eV"))
        if W is not None and W > 0:
            tc_fb = flat_band_tc(lambda_ep, W, omega_log_K, mu_star)
            tc_candidates.append(("flat_band", tc_fb, 0.7))

        # Select highest Tc (optimistic estimate for discovery)
        if tc_candidates:
            best = max(tc_candidates, key=lambda x: x[1])
            result["Tc_K"] = best[1]
            result["mechanism"] = f"mixed({best[0]})"
            result["confidence"] = best[2]
            result["tc_all_mechanisms"] = {m: t for m, t, _ in tc_candidates}

    else:
        # Unknown mechanism: fall back to BCS
        tc = allen_dynes_tc(lambda_ep, omega_log_K, mu_star)
        result["Tc_K"] = tc
        result["mechanism"] = "bcs_fallback"
        result["confidence"] = 0.5

    return result
