"""Phase-E Snorkel verifier — weak-supervision verification pipeline.

This package converts a scored batch of candidates into a mapping of
``VerificationBundle`` objects via a library of labeling functions, a
majority-vote label model, and per-slice diagnostics.

All components are offline, deterministic, and dependency-free so the
discovery loop's ``verify`` hook can call them from test contexts.
"""
from __future__ import annotations

from .labeling_functions import (
    CandidateContext,
    DEFAULT_LABELING_FUNCTIONS,
    LabelingFunction,
    lf_connector_agreement,
    lf_cross_source_consensus,
    lf_dft_agreement,
    lf_mp_energy_sanity,
    lf_novel_but_unbacked,
    lf_sensor_robustness,
    lf_sensor_selectivity,
    lf_structure_plausibility,
    lf_synthesis_feasibility,
    lf_theory_contradiction,
    lf_theory_support,
)
from .label_model import MajorityVoteLabelModel
from .slices import SliceDefinition, build_slice_reports, default_slice_definitions
from .verifier import SnorkelVerifier, VerifierReport

__all__ = [
    "CandidateContext",
    "DEFAULT_LABELING_FUNCTIONS",
    "LabelingFunction",
    "lf_connector_agreement",
    "lf_cross_source_consensus",
    "lf_dft_agreement",
    "lf_mp_energy_sanity",
    "lf_novel_but_unbacked",
    "lf_sensor_robustness",
    "lf_sensor_selectivity",
    "lf_structure_plausibility",
    "lf_synthesis_feasibility",
    "lf_theory_contradiction",
    "lf_theory_support",
    "MajorityVoteLabelModel",
    "SliceDefinition",
    "build_slice_reports",
    "default_slice_definitions",
    "SnorkelVerifier",
    "VerifierReport",
]
