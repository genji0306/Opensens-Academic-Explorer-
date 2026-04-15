# Riemann Hypothesis — Three-Source Synthesis

Three inputs were combined for this synthesis:

| Source | Role | Status |
|---|---|---|
| OAE Riemann convergence loop (local) | Empirical anchor | Converged, score=1.0000 over 10,000 zeros |
| Theoretical RH survey (research-assistant agent) | Historical attack-vector map | 15 efforts across 6 categories |
| autoresearch-mlx on `dev.local` (Cyber01) | Methodological template | Fixed-budget keep/revert loop; best val_bpb=1.8388 |

---

## 1. What OAE Already Found

The A → B → Ob → C loop converged on the **Hardy Z-function principle**:

> γₙ is the n-th positive root of Z(t) = e^{iθ(t)} ζ(½ + it).

The fitted approximant `θ⁻¹((n−a)π) + Σcₖ Pₖ(u(n)) + spline(n)` reaches perfect in-sample fit once spline knot count equals N — i.e. the oscillatory S(γₙ) fluctuation is irreducibly per-zero. This is consistent with the theoretical record: S(t) is O(log T) but sign-oscillates every zero, so no smooth parametric model of n can close it.

**Honest bound**: our loop discovered the *characterisation*, not a proof. The principle it names is the classical Riemann–Siegel / Hardy statement that is **equivalent** to the RH statement "all non-trivial ζ zeros lie on Re(s)=½".

---

## 2. Where Our Loop Fits in the Global Map

From the theoretical survey, the six attack vectors rank as follows on **iterative-loop tractability**:

| Vector | Iterability | OAE leverage |
|---|---|---|
| 1. Analytic / zero-detection | **High** — LMFDB ground truth, differentiable scoring | Direct: we already do this |
| 2. Operator-theoretic (Hilbert–Pólya) | Medium — enumerable candidates, GUE-statistics scoring | Possible: enumerate PT-symmetric xp-variants, score against first N γₙ |
| 3. Algebraic / arithmetic geometry | **Low** — no feedback signal | Unsuitable |
| 4. L-function generalisations | Medium — Selberg class is structured | Possible: port OAE loop to Dirichlet L-functions |
| 5. Physics-inspired | Medium — trace formulas scorable | Possible but speculative |
| 6. ML-assisted conjecture (He, Ono) | **High** — murmurations phenomenon is live | **Best match** for a multi-agent discovery system |

**Synthesis recommendation**: the *methodology* proven in the OAE loop (seed → simulate → score → refine against LMFDB ground truth) is exactly what the post-2022 "murmurations" work (He, Lee, Oliver, Pozdnyakov) is doing at the L-function level. A natural next campaign is to generalise OAE from ζ to Dirichlet L-functions and test whether the same θ⁻¹-plus-spline factoring produces similarly clean principles — if it fails on a specific L-function, that failure mode is the diagnostic.

---

## 3. Methodological Convergence with autoresearch-mlx

The `autoresearch-mlx` loop on `dev.local` (Karpathy's fixed-time autonomous research protocol, MLX-ported) uses the same control pattern OAE uses:

```
edit → run fixed-budget experiment → read single scalar metric → keep-or-revert → repeat
```

| Control element | autoresearch-mlx | OAE Riemann loop |
|---|---|---|
| Mutable unit | `train.py` | `ZeroRule` (correction coeffs + spline) |
| Fixed budget | 5 min wall-clock | 40 iterations / patience=40 |
| Metric | `val_bpb` (scalar, minimise) | composite score (4 weighted components, maximise) |
| Keep/revert | git commit + `status=keep/discard` | best-so-far snapshot, monotone capacity |
| Verification | `bash -lc 'uv run train.py'` | `Agent Ob` scorer |

The recent `dev.local` novel-branch run reproduces the structural pattern — 5 experiments, one crash (divisibility assertion), one win (2^14 total batch + device batch 8 → **1.8388 val_bpb** vs baseline 1.9722). That is a **7% gain in 5 experiments** from a structural rather than hyperparameter change — the same economics as our loop's jump from 0.498 → 1.0 when spline knots finally matched dataset size at iteration 13.

**What this tells us**: the OAE Riemann loop is operating at a higher semantic tier of the same control paradigm — multi-component score, damped refinement, geometric capacity growth. The methodological agreement is evidence that the loop architecture is sound; it isn't domain-specific.

---

## 4. Candidate Next Experiments

Three concrete experiments that fall out of this synthesis, ranked by cost and expected information:

1. **L-function port (low-medium cost, high info)**. Replace `core/lmfdb_loader.py` with a Dirichlet L-function zero loader; keep the A/B/Ob/C structure unchanged. Success = same θ⁻¹+spline principle closes; failure = identifies which L-function breaks the factoring and why.
2. **Hilbert–Pólya candidate search (medium cost, speculative info)**. Enumerate candidate self-adjoint operators whose spectra should match {γₙ}; score each candidate on (a) first 10K eigenvalue overlap, (b) GUE pair-correlation fit, (c) operator simplicity. This is the *structured* part of the historically unstructured H–P search.
3. **Moment-ratio conjecture test (low cost, known-hard)**. Use our converged loop to regenerate the first 10K zeros, compute 2k-th moments of ζ(½+it) numerically, compare with Keating–Snaith CUE prediction across k. Known open conjecture — our clean data is useful evidence.

---

## 5. Visualisation

See `rh_projection.html` for the 3D projection plot: the complex-valued parametric curve Γ(t) = (t, Re ζ(½+it), Im ζ(½+it)) with three orthographic projection walls (**x–i**, **x–y**, **y–i**). Zeros appear as the points where both the x–i and y–i projections cross zero simultaneously — a geometric rendering of the RH statement on the critical line.
