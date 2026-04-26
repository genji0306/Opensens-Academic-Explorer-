# RH Core Bibliography Seed Pack

This document is the offline-capable seed pack for Agent C in the recursive
Riemann research orchestrator. Its job is not to prove RH. Its job is to map
the main historical approach families, the proof obligations each family still
owes, and the failure modes the observer should penalize.

## Analytic Foundations

- Hadamard and de la Vallee Poussin, 1896.
  Prime number theorem via zero-free regions. This is baseline analytic control,
  not a route to RH by itself.
- Hardy, 1914.
  Infinitely many zeros on the critical line. This is decisive partial progress
  but still leaves the global exclusion problem open.
- Selberg, Levinson, Conrey.
  Mollifier and moment methods. These approaches prove large fractions of zeros
  lie on the critical line, but not all of them.

Proof obligations:
- Upgrade partial on-line density into a 100 percent result.
- Show that any remaining off-line zeros are impossible, not just rare.

## Explicit Formula And Prime-Zero Duality

- Riemann / von Mangoldt explicit formula tradition.
- Prime powers, Chebyshev psi, and the logarithmic derivative of zeta.
- Euler product structure as the prime-side anchor.

Core idea:
- Any viable proof strategy must preserve the explicit formula link between zero
  positions and prime oscillations.

Proof obligations:
- Convert the explicit formula from an exact identity into an exclusion
  argument against off-line zeros.
- Control every error term sharply enough that a contradiction can be forced.

## Hardy Z / Critical-Line Parametrization

- Hardy Z-function.
- Riemann-Siegel theta phase.
- Gram points as phase landmarks.

Core idea:
- On the critical line, `zeta(1/2 + it) = Z(t) * exp(-i theta(t))`.
- This makes the real and imaginary wall projections phase-shifted views of the
  same amplitude.

Proof obligations:
- Explain why the classical critical-line parametrization can be extended into a
  global theorem that excludes off-line zeros.

## Hilbert-Polya / Spectral Programs

- Hilbert-Polya operator heuristic.
- Self-adjoint spectral realizations.
- Random matrix and spectral analogies as supporting evidence.

Core idea:
- If the non-trivial zeros are eigenvalues of a self-adjoint operator after the
  correct normalization, reality of the spectrum could force the critical line.

Proof obligations:
- Construct the operator rigorously.
- Prove the full spectrum correspondence, not just asymptotic similarity.
- Preserve explicit-formula and functional-equation structure.

## Xi-Function And de Branges Lanes

- Xi-function as an entire-function reformulation of zeta.
- de Branges / Hilbert space programs.
- Laguerre-Polya style positivity and real-zero structures.

Core idea:
- Entire-function structure and function-space positivity may constrain zero
  locations more rigidly than raw zeta analysis.

Proof obligations:
- Build the required space or positivity machinery rigorously.
- Show that the machinery excludes every off-line zero.

## Random Matrix And Statistical Evidence

- Montgomery pair correlation.
- Odlyzko high-zero computations.
- GUE-style spacing heuristics.

Core idea:
- Zero spacing behaves spectrally and statistically like eigenvalue ensembles.

Proof obligations:
- Upgrade statistical agreement into a theorem.
- Show that the same structure excludes off-line zeros instead of merely
  predicting spacing on the line.

## Geometric / Visualization Lane

- OAE `rh_projection.html`
- OAE `rh_strip.html`
- OAE `rh_explicit.html`
- OAE `rh_synthesis.md`

Core idea:
- Projection geometry can reveal candidate invariants.
- The real and imaginary wall traces share Hardy Z amplitude and differ only by
  orthogonal phase.
- The strip and explicit-formula views keep the geometric intuition tied back to
  the analytic object and the prime side.

Rules:
- Visual intuition only counts after it is restated as a falsifiable invariant,
  operator claim, spacing law, or prime-side consequence.
- "Spiral", "energy well", and similar observations are starting points, not
  evidence.

## Quantum-Inspired Lane

- Simulator-backed Hermitian surrogates.
- Operator analogies.
- Spectral gap stability tests.

Rules:
- Quantum or Hamiltonian language only enters the main score after the claim is
  translated into a rigorous mathematical surrogate and survives explicit
  formula, functional equation, and critical-line checks.

## Observer Guidance

- Penalize contradiction-heavy synthesis.
- Penalize novelty that lacks an exact claim and validation recipe.
- Reward reduction in proof obligations, reproducibility, and consistency with
  the explicit formula and critical-line identities.
- Treat zero-prediction quality as evidence support, never as a proof.
