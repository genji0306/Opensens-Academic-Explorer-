# ASTRA VERDICT MVE PLAN r6.1

**Verdict: BLOCK**

Reviewed `fe3cdf175a8`, read-only. Script and input SHA256s match the receipt. A complete v2 rerun reproduced **every block statistic and dependence diagnostic exactly**. Four blockers are closed at the plan-contract level; B2 and B4 remain partial.

1. **B1 — CLOSED: labels, sample sizes and effective matrix size (§3; §7 WO-3).**  
   Odlyzko headers confirm high-block median heights **2.6765339693×10¹¹, 1.4417689751×10²⁰, 1.3709199099×10²¹**. Each contains 10,000 zeros and **9,999 gaps**. Independently applying  
   \(N_{\rm eff}=\log(H/2\pi)/\sqrt{12(1.57314)}\) gives **2.020410, 5.633131, 10.260364, 10.778725**, rounded to CUE **2, 6, 10, 11**. The formula matches the [primary derivation](https://arxiv.org/pdf/math/0602270). Rounding, asymptotic limitations, retrospective status and replacement of the v1 fixture are now explicit.

2. **B2 — PARTIAL; remaining blocker: calibration (§2c rules 3–5; §3; §7 WO-3).**  
   `lane_check_v2.py:277–289` correctly refits each Planck bootstrap sample. Actual denominators are **33,000 / 3,333 / 3,333 / 3,333**. Observed KS D values **0.02319, 0.03273, 0.02705, 0.03387** exceed bootstrap maxima **0.00589, 0.01931, 0.02067, 0.02091**.

   However, line 283 generates **iid** samples. Thinning leaves correlations down to **−0.046**; small linear autocorrelations do not establish calibration of the fitted-KS tail. CUE(50)’s **95th-percentile** check does not validate Planck’s **1% rejection threshold**. Concatenated finite-CUE spectra also do not establish the dependence law of zero sequences; transferring the null from 3,333 to 33,000 remains unvalidated.

   **Required fix:** validate dependence-preserving, refitted null calibration at the actual sample sizes, or label these outputs nominal/exploratory and prevent WO-3 from treating their reproduction as inferential certification. Bootstrap the discrepancy between measured and fitted-model-implied exponents jointly. Declare/calibrate the combined kill rule: **KS at 1% OR exclusion by a 95% CI is not an overall 1% test**.

3. **B3 — CLOSED: survival definitions (§2c rule 6; §3; §5).**  
   `baseline_explained` and `baseline_exceeding_survivor` are separated. H1 is explicitly excluded from GO2 and hand-off. Image-free and shuffled-image arms are added. Their implementation must satisfy B4’s experimental-design fixes.

4. **B4 — PARTIAL; remaining blocker: GO2 sampling assumptions (§5 “Independence” and “Frozen procedure”; §6 GO2).**  
   Clustering shared views, freezing retries/stopping, separating replication and requiring 3/4 contrast detections are improvements. But **disjoint intervals do not establish independent Bernoulli trials**. Pooling different families/heights also lacks a specified common sampling distribution supporting the binomial CP calculation. [Binomial assumptions](https://csrc.nist.gov/glossary/term/binomial_distribution).

   The total visual count per cluster remains unfrozen; “≤3 cards per visual” therefore leaves total opportunities unspecified. One fixed image-free card is not automatically comparable to multiple image-derived checks.

   **Required fix:** specify source-block sampling, arm allocation, discovery→replication pairing and dependence assumptions, or use a justified stratified/cluster analysis. Freeze total views/cards/check opportunities per cluster and match budgets across ablations, or calibrate their differences explicitly.

5. **B5 — CLOSED at specification level (§2b; §6 GO1; §7 WO-2).**  
   The hash includes prediction, primary statistic and complete `check_spec`; transitive invalidation, `preliminary`, current-revision survivor-only hand-off and rejection of `hyp_N` through every formalisation path are explicit. Requested-slot denominators and real-hash fixtures are acceptance requirements. These remain implementation obligations, not completed tests.

6. **B6 — CLOSED at specification level (§2d; §§7–9).**  
   USD 0.000268 is correctly “known exposure.” Reconciliation, verified pricing/quota and worst-case reservation precede dispatch; fleet ownership, GO3 timing and atlas confirmation precede relay.

**Non-blocking notes**

- **GO2’s intersection–union construction is correct:** requiring all three valid level-5% comparisons controls the global union null, despite shared real-arm data. It does not establish simultaneous 95% coverage of all reported intervals. [IUT derivation](https://stat.ethz.ch/CRAN/web/packages/twoCoprimary/vignettes/overview.html). Thresholds **7/10, 8/20, 8/40, 9/100** reproduce.
- High-block exponent CIs **[2.5314,3.2004], [2.5644,3.2607], [2.7466,3.4306]** exclude Planck \(a=\)**4.3269,4.3040,4.3751** and independently integrated finite-interval predictions **3.7495,3.7233,3.7835**. Refined Gaudin quadrature gives **2.9164**; maximum CDF change is **8.46×10⁻⁷**.
- **H0 `inconclusive` is contractually correct** for retrospective, undersized replication. Preserve the negative exploratory evidence; do not retrospectively lower 10,000 to 9,999.
- Report **Monte Carlo p = 1/201**, not a certified upper bound. Zero exceedances among 200 gives a one-sided 95% tail-probability upper bound of **0.01487**.