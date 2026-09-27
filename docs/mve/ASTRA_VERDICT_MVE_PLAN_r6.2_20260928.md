# ASTRA VERDICT MVE PLAN r6.2

**Verdict: PASS WITH CHANGES**

Reviewed commit `12821397e75`, read-only. Script, receipt and input hashes match. A complete sanity rerun reproduced **all four blocks’ output statistics exactly**.

**B2 — CLOSED at plan-contract level** (§2c rules 4–5a, 7; §3; §7 WO-3).

The revision implements the explicitly permitted exploratory route. `lane_check_v2_status.json` records `inferential: false`; every v2 p-value is nominal; WO-3 certifies code reproduction only; H0 remains `inconclusive`.

The sanity script resamples blocks at the actual sizes, refits each KS replicate, and jointly bootstraps measured minus fitted-model-implied exponents. Its output remains explicitly unvalidated. Arithmetic checks:

- Original: \(p_{MC}=1/201=0.004975\); zero-exceedance 95% upper bound **0.014867**.
- Sanity: \(p_{MC}=1/401=0.002494\); upper bound **0.007461**.
- Future Bonferroni rule: **0.005 + 0.005 ≤ 0.01**. The sanity upper bound does **not** certify the 0.005 component threshold.

Actual inferential calibration remains a future implementation obligation, not an accomplishment claimed here.

**B4 — CLOSED at specification level, conditional on A1/A2** (§5; §6 GO2; §7 WO-4/WO-6).

The plan now specifies strata, discovery/replication pairs, exclusive donors, seeded allocation, fixed stopping and matched opportunities: **2 views × 3 slots × 1 check = 6 slots per cluster/arm/observer**; pilot **3 slots**. Empty or failed slots remain in denominators. Image-free cards receive the same check budget; equal hosted-call spending is unnecessary for this comparison.

Under independent clusters and symmetric differences, the exact upper-tail calculation is
\(p_k=2^{-K}\#\{\epsilon:\sum_c\epsilon_cd_{c,k}\ge T_k\}\).
These are substantive assumptions; shuffling call order does not establish them. [Sign-flip validity conditions](https://pmc.ncbi.nlm.nih.gov/articles/PMC4010955/).

The arithmetic is correct:

- Minimum attainable p: **\(2^{-K'}\)**; at least **5 nonzero differences** are necessary.
- Equal-magnitude thresholds: **9/10, 15/20, 26/40**, with null tails **0.010742, 0.020695, 0.040345**.
- Stated powers reproduce: **0.375810, 0.804208, 0.416371, 0.807448**.
- Intersection–union is valid: requiring all three rejections gives \(P(\text{all reject})\le0.05\) whenever any component null holds. Shared real-arm data do not invalidate that argument.
- **K ≥ 20 across ≥2 strata** is enforced; the ten-cluster pilot cannot pass GO2.

**Remaining blockers: none at plan-contract level.** B1, B3, B5 and B6 remain CLOSED: corrected labels/counts/N_eff, survivor exclusions, hash/lifecycle/formalisation safeguards, and dispatch/relay prerequisites are preserved.

**Non-blocking changes**

- **§5 power wording:** label these as *single-comparison, equal-magnitude, independent, no-tie illustrations*. Twenty clusters do not guarantee 80% overall GO2 power. Replace “weaker effects are not detectable” with “weaker effects have lower power.”
- **§5–§6:** describe superiority conclusions as conditional on A1/A2; symmetry-null rejection is not an assumption-free test of nonpositive mean lift.
- **§5:** call the \(K>20\) calculation Monte Carlo, specify its p-value convention, and label pooled-slot CP intervals nominal; clustering prevents guaranteed binomial coverage.