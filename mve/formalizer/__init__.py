"""Offline native Mathlib formalizer; LeanGeo is unavailable, proof authority unchanged."""

from mve.formalizer.ir import build_ir
from mve.formalizer.emitter import emit
from mve.formalizer.repairs import formalize

__all__ = ["build_ir", "emit", "formalize"]
