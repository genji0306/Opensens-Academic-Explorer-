-- MT-β-finite_window_only-005: Obstruction Closure (MT-β)
-- Obstruction class 'finite_window_only' survived 5 campaigns (threshold 3).
theorem mt_beta_finite_window_only :
    ∀ (campaign : RHCampaign) (proposer : CandidateFamily),
    campaign.obstruction_class = "finite_window_only" →
    campaign.historical_count ≥ 5 →
    ¬proposer.promoted_without_lean_exclusion_certificate := by
  sorry
