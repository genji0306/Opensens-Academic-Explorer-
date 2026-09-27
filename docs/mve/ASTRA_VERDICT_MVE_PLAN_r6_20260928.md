ASTRA VERDICT MVE PLAN r6

**Verdict: BLOCK**

Reviewed `fc27b211c5f` against frozen r5, the integration review and SUMMARY, and both Hawking scripts/receipts. The owner’s loop is preserved. The blockers concern experimental validity and enforceable contracts.

1. **§3 “Stage 2”; §7 WO-3 — the acceptance fixture encodes incorrect claims.**  
   The labels \(10^{12},10^{21},10^{22}\) are zero **indices**, not heights. Actual heights are approximately \(2.6765×10^{11},1.4418×10^{20},1.3709×10^{21}\). Each block contains 9,999 gaps, so none satisfies the stated ≥10,000-gap replication requirement. The effective-size formula omits \(\Lambda=1.57314…\): \(N_{\rm eff}=\log(H/2π)/\sqrt{12\Lambda}\), giving approximately **2.02, 5.63, 10.26, 10.78**, rather than the table’s values. This remains an asymptotic approximation. [Primary derivation](https://arxiv.org/pdf/math/0602270).  
   **Fix:** correct labels/formula, disclose integer rounding and approximation limits, replace WO-3’s erroneous golden fixture, and classify this retrospective example as exploratory. A prospective test needs genuinely qualifying replication data and a frozen specification.

2. **§2c rules 1–6; §3 statistics; §7 WO-3 — numerical reproduction is not statistical calibration.**  
   Independent recomputation reproduces the Planck fits, nominal one-sample KS outputs, and Δloglik **−18.52, −92.38, −88.23, −85.09**. However, fitted-parameter KS requires refitting during calibration; the ordinary fixed-CDF p-values are unsuitable. [SciPy procedure](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.goodness_of_fit.html). Adjacent zero gaps and gaps within each CUE matrix are dependent; mean-normalisation introduces further dependence. Ordinary two-sample KS calibration therefore also needs justification. Likelihood sums are marginal/composite scores, not established joint likelihoods.

   **Fix:** calibrate the complete fitting, unfolding and testing procedure using suitable independent blocks/simulations; compare the primary statistic against the corrected accepted baseline, not only Wigner. Report actual fitting denominators: **12,000**, not 98,999, for the low-block likelihood and one-sample KS. Compare the measured **CDF** exponent with Planck’s **\(a\)**, not density exponent \(a−1\); predeclare the fitting interval and uncertainty test. Remove the unsupported causal assertion that low-block rejection *is* a finite-height effect. The negative Planck evidence remains useful, but its advertised inferential certification does not.

3. **§2c rule 5; §3 H1; §§5–6 GO2 — survival has contradictory definitions.**  
   H1 is explicitly explained by GUE, yet is counted as a survivor despite specificity excluding baseline-explained patterns. It is also owner-originated and unblinded, independently excluding it from GO2.

   **Fix:** separate replicated observations, baseline-explained observations and baseline-exceeding survivors; exclude H1 from GO2. Add an image-free fixed-card/check baseline or shuffled-image ablation. Otherwise generic “reject this baseline” cards can produce lift whenever real data differ from the chosen null, without useful visual perception. Under a correctly matched null, GO2 can legitimately fail; it is not mathematically impossible to pass.

4. **§5 “Unit and statistic”; §6 common rules/GO2; Risks “Multiple testing” — the confidence claim lacks its sampling assumptions.**  
   Different views of shared source data are not independent Bernoulli trials. Reporting module strata does not repair the pooled Clopper–Pearson bound. One primary statistic per card also does not bound the probability that **any** of multiple cards survives at α.

   **Fix:** define independent source blocks or a valid cluster-level analysis; freeze card limits, retries, check-selection and stopping rules; calibrate the whole visual-level procedure. Separate development from untouched replication data—“larger sample” must not silently reuse discovery observations. Predeclare meaningful contrast sensitivity; one detection alone is weak protection.

5. **§2b lifecycle/identity; §7 WO-2 — complete the immutable decision contract.**  
   The listed identity projection omits separately editable prediction and primary-statistic fields; the complete frozen check specification has no explicit schema field. `preliminary` is required elsewhere but absent from the lifecycle.

   **Fix:** hash the complete hypothesis/check specification, including baselines, α, replication selection and kill rule. Changes invalidate checks, judgments and adoption transitively. Specify current-revision, survived-only hand-off eligibility; reject direct `hyp_N` support through every formalisation path. Complete H0/H1 fixtures with actual source hashes and testable rules. Define GO1 denominators for refusals and malformed responses.

6. **§7 WO-4–WO-6; §8 budget — live readiness is overstated.**  
   Integration SUMMARY reports **known exposure only**, with campaign snapshot absent and remaining budget unknown. USD 0.000268 is not a reconciled campaign total.

   **Fix:** require aggregate-ledger reconciliation before live dispatch; verify O-M2 pricing/quota limits and reserve worst-case outputs/retries within the pilot cap. Make fleet ownership, GO3 timing and atlas status confirmation explicit pre-relay dependencies. Keep WO-2’s changelog in the addendum, preserving frozen r5.

**Non-blocking notes**

- C1–C5 ownership, outbox-only writes, human adoption and non-authorising hypotheses are sound. Strengthen WO-1 tests: OCR and unchanged `git status` alone prove neither isolation nor absence of ignored-file writes.
- CP arithmetic is correct: zero-control thresholds are **8/20, 8/40, 9/100**, and **7/10** for the pilot. These are rejection thresholds, not power estimates.
- Unfolding and circular Haar-CUE sampling construction are reasonable. Planck normalisation is \(T^{a+1}\Gamma(a+1)\zeta(a+1)\). Stage-1 BIC arithmetic reproduces. Full CUE Monte Carlo p-value reproduction was not completed.
- Offline packet order is sensible. GO3 measures operations; GO4 establishes absence from a searched corpus, not global novelty. Preserve all r5 gates as “not established.”