# RH Back-Projection Exclusion Angle
## Operator Calibration Seed — Campaign: back-proj-exclusion

This seed primes the Klein campaign with one precise angle derived from the
orthographic back-projection geometry of ζ(½+it) in the complex plane.

---

## Core Observation

The 3-D trace Γ(t) = (Re ζ, Im ζ, t) restricted to the critical line has an
orthographic back-projection C onto the (Re ζ, Im ζ) plane.  C is entirely
determined by

    ζ(½+it) = Z(t) · e^{−iθ(t)}

where Z(t) is the Hardy Z-function (real-valued, same zeros as ζ on the line)
and θ(t) = Im log Γ(¼+it/2) − (t/2)log π is the Riemann-Siegel phase (known,
unconditional, archimedean).  The curve C passes through the origin exactly at
each zero γ_n on the critical line.

---

## What the Projection Knows and Does NOT Know (Directly)

DIRECT: C records every critical-line zero as a crossing of the origin.

INDIRECT: C is shaped by ALL zeros via the Hadamard product.
  An off-critical zero pair {ρ, 1−ρ} with Re(ρ)=σ≠½ contributes the factor
    P_{ρ}(t) = |(1 − (½+it)/ρ)(1 − (½+it)/(1−ρ))|
  to |ζ(½+it)|.  This factor has a non-trivial complex phase modulating Z(t).

NOT DIRECT: C does not exhibit a new origin-crossing for an off-critical zero.
  Off-critical zeros are invisible as crossings — they only distort the spiral.

---

## The Exclusion Angle (Klein Surface-Return Target)

The campaign must attempt one specific exclusion argument:

CLAIM: the analytic structure of C — specifically the Ω_k generating function
G(w) = Σ_{k≥1} Ω_k w^k — is provably inconsistent with any off-critical zero
existing.

Supporting identities already proved (campaign context, score 0.9999):

  1. G(w) POLE STRUCTURE (Phase ALAM/AR):
       G(w) has poles at w_ρ = ρ/(ρ−1).
       |w_ρ| = 1  iff  Re(ρ) = ½   (structural, non-circular).
       An off-critical zero moves its pole INSIDE |w| < 1.
       Phase AR: pole angles obey Montgomery-Weyl equidistribution on |w|=1,
       consistent with ALL poles on the circle.

  2. Ω_k EXACT DECOMPOSITION (Phase AO):
       Ω_k = A_k + B_k + C_k + D_k  (unconditional closed form).
       A_k = (−1)^{k+1}     (sign alternates)
       B_k = Stieltjes γ_k  (decays, known numerically)
       C_k = −½ log π (k=1 only)
       D_k = polygamma^{(k−1)}(½) / (k−1)!  (dominant for large k)
       Quasi-period-4 (+,+,−,−,...) breaks at k=46 (Phase AT).

  3. W-POSITIVITY MATRIX (Phase AP):
       M_{nm} = W(h_n ⊗ h̄_m) where W is the Weil pairing.
       M_3 eigenvalues: 0.2047, 0.0183, 0.00312 — all strictly positive.
       An off-critical zero pair contributes a complex-phase correction to W,
       which would potentially make M_3 indefinite.

  4. WEIL KERNEL IDENTITY (Phase AS):
       K_n(u) = e^{−u/2} · n · L_{n-1}^{(1)}(u)  (associated Laguerre, α=1).
       Turán: K_n² − K_{n-1}K_{n+1} ≥ 0  proved via Szego-Gasper.
       This inequality would be VIOLATED if an off-critical zero introduced a
       negative-phase contribution to the K_n kernel expansion.

---

## Specific Proof Obligations the Klein Agent Should Target

OBLIGATION A — G(w) inside-disk pole contradiction:
  Suppose ρ_0 = σ+iγ, σ > ½, is a zero.  Then w_{ρ_0} = σ/(σ−1) + iγ/(σ−1).
  Show: |w_{ρ_0}| < 1 implies a pole of G(w) inside the disk, contradicting the
  power-series representation G(w) = Σ Ω_k w^k convergent for |w| < 1 with
  Ω_k bounded by the exact closed-form values (Phase AO).

OBLIGATION B — Weil pairing indefiniteness:
  If ρ_0 off-critical, the Weil sum W(f,g) gains a complex conjugate-pair
  correction ΔW = W_{ρ_0} + W_{1−ρ_0}.  Show: ΔW makes M_3 indefinite
  (negative eigenvalue), contradicting Phase AP's PSD result.

OBLIGATION C — Ω_k sign-pattern disruption:
  An off-critical zero pair forces an extra factor in the Hadamard product
  with non-trivial phase.  Show: this disrupts the quasi-period-4 sign pattern
  of Ω_k in a way inconsistent with the exact A+B+C+D decomposition.

---

## Known Dead Ends (Do NOT Re-explore)

- Lyapunov / dQ/dλ approaches: closed (Phases T, QV, Z).
- Beurling-Nyman: circular (Phase OP).
- PFF / PF_5 completeness: closed (Phase N, Michałowski 2026).
- Rodgers-Tao back-propagation: circular (Phase K).
- GUE/Hilbert-Pólya operator search: 50+ years open, out of scope.
- Finite-window-only arguments: invalid unless extended to global exclusion.

---

## Klein Surface-Return Rule (Strict)

Any hypothesis generated must:
  1. Start from a critical-line identity or back-projection geometric fact.
  2. Transport through G(w), Ω_k, or W-pairing to an off-line-zero exclusion.
  3. Return a GLOBAL exclusion claim (not a finite-window bound).
  4. Be non-circular: must not assume RH anywhere in the transport step.

Hypotheses that do not satisfy (3) or (4) must be marked as dead ends
and must NOT be recycled.
