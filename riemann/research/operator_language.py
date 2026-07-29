"""Operator-language support for the recursive RH research loop.

This module turns the operator-framework note into concrete machine-side
artifacts:

* a versioned operator-language spec,
* canonical signatures for operator-style novelty claims,
* a bounded complexity metric, and
* calibration/report helpers for the orchestrator.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .schemas import ApproachCard

OPERATOR_LANGUAGE_VERSION = "v0.1"

PRIMITIVE_FAMILIES: dict[str, tuple[str, ...]] = {
    "analytic": (
        "ZETA",
        "XI",
        "GAMMA",
        "LOG_GAMMA",
        "DIRICHLET_SUM",
        "EULER_PRODUCT",
    ),
    "transform": (
        "MELLIN",
        "FOURIER",
        "LAPLACE",
        "INVERSE_MELLIN",
        "CONV",
    ),
    "geometric_contour": (
        "CONTOUR_INT",
        "SHIFT_CONTOUR",
        "RESIDUE",
        "SYMMETRIZE",
    ),
    "zero_oscillation": (
        "ARG_VARIATION",
        "ZERO_COUNT",
        "GRAM_POINT",
        "Z_FUNCTION",
        "CRITICAL_RESTRICTION",
    ),
    "positivity": (
        "IS_POSITIVE",
        "IS_MONOTONE",
        "QUADRATIC_FORM",
        "ENERGY",
        "BOUNDS",
    ),
    "spectral_operator": (
        "SELF_ADJOINT",
        "EIGENVALUE_MAP",
        "TRACE_FORMULA",
        "KERNEL_OPERATOR",
        "COMMUTATOR",
    ),
    "structural": (
        "COMPOSE",
        "ADD",
        "MULTIPLY",
        "NEGATE",
        "SCALE",
        "RESTRICT",
        "DUALIZE",
    ),
}

TYPE_CLASSES = (
    "scalar_analytic_function",
    "kernel",
    "contour_expression",
    "operator",
    "inequality_statement",
    "asymptotic_statement",
    "zero_statistics_object",
    "spectral_object",
)

NORMALIZATION_PIPELINE = (
    "expand_trivial_aliases",
    "normalize_variable_names_and_ordering",
    "apply_symmetry_reductions",
    "collapse_equivalent_transform_compositions",
    "normalize_contour_descriptors",
    "push_constants_to_standard_positions",
    "attach_domain_assumptions_explicitly",
    "emit_canonical_signature",
)

CALIBRATION_TARGETS: tuple[dict[str, Any], ...] = (
    {
        "task": "functional_equation",
        "label": "Encode the functional equation",
        "families": ("xi_function", "general_analytic"),
    },
    {
        "task": "completed_zeta_symmetry",
        "label": "Encode completed-zeta symmetry",
        "families": ("xi_function", "de_branges"),
    },
    {
        "task": "explicit_formula",
        "label": "Encode an explicit formula",
        "families": ("explicit_formula",),
    },
    {
        "task": "hardy_z_representation",
        "label": "Encode Hardy Z(t)",
        "families": ("hardy_z",),
    },
    {
        "task": "positivity_or_zero_counting",
        "label": "Encode a positivity or zero-counting relation",
        "families": ("de_branges", "mollifier_moment", "hardy_z"),
    },
    {
        "task": "contour_manipulation",
        "label": "Encode a standard contour manipulation",
        "families": ("general_analytic", "xi_function"),
    },
)


def build_operator_language_spec(framework_path: Path) -> dict[str, Any]:
    text = framework_path.read_text(encoding="utf-8") if framework_path.exists() else ""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest() if text else ""
    return {
        "version": OPERATOR_LANGUAGE_VERSION,
        "framework_path": str(framework_path),
        "framework_hash": digest,
        "primitive_families": PRIMITIVE_FAMILIES,
        "type_classes": TYPE_CLASSES,
        "normalization_pipeline": NORMALIZATION_PIPELINE,
        "complexity_formula": "a*T + b*D + c*S + d*A + e*N + f*U",
        "complexity_terms": {
            "T": "operator node count",
            "D": "maximum depth",
            "S": "distinct primitive families used",
            "A": "explicit domain assumptions",
            "N": "numerical instability penalty",
            "U": "auxiliary lemma burden",
        },
        "search_targets": (
            "equivalent_reformulations",
            "positivity_certificates",
            "monotonicity_or_convexity_claims",
            "spectral_surrogates",
            "explicit_formula_reorganizations",
            "barrier_statements",
        ),
        "calibration_targets": CALIBRATION_TARGETS,
        "source_excerpt": _excerpt(text),
    }


def canonicalize_operator_claim(
    *,
    operator_family: str,
    operator_primitives: Iterable[str],
    input_types: Iterable[str],
    output_type: str,
    assumptions: Iterable[str] = (),
    branch_constraints: Iterable[str] = (),
    invariances: Iterable[str] = (),
) -> dict[str, Any]:
    payload = {
        "operator_family": operator_family,
        "operator_primitives": sorted(set(str(item) for item in operator_primitives)),
        "input_types": sorted(set(str(item) for item in input_types)),
        "output_type": str(output_type),
        "assumptions": sorted(set(str(item) for item in assumptions)),
        "branch_constraints": sorted(set(str(item) for item in branch_constraints)),
        "invariances": sorted(set(str(item) for item in invariances)),
        "normalization_pipeline": NORMALIZATION_PIPELINE,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["canonical_signature"] = hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:20]
    return payload


def complexity_score(
    *,
    node_count: int,
    depth: int,
    primitive_families: int,
    assumptions_count: int,
    numerical_instability: float,
    auxiliary_lemma_count: int,
    branch_cut_penalty: float = 0.0,
    contour_fragility_penalty: float = 0.0,
    spectral_nonconstructiveness_penalty: float = 0.0,
) -> tuple[float, dict[str, float]]:
    terms = {
        "T": float(max(node_count, 0)),
        "D": float(max(depth, 0)),
        "S": float(max(primitive_families, 0)),
        "A": float(max(assumptions_count, 0)),
        "N": float(max(numerical_instability, 0.0)),
        "U": float(max(auxiliary_lemma_count, 0)),
        "branch_cut_penalty": float(max(branch_cut_penalty, 0.0)),
        "contour_fragility_penalty": float(max(contour_fragility_penalty, 0.0)),
        "spectral_nonconstructiveness_penalty": float(max(spectral_nonconstructiveness_penalty, 0.0)),
    }
    raw = (
        0.24 * terms["T"]
        + 0.20 * terms["D"]
        + 0.18 * terms["S"]
        + 0.12 * terms["A"]
        + 0.14 * terms["N"]
        + 0.12 * terms["U"]
        + 0.10 * terms["branch_cut_penalty"]
        + 0.10 * terms["contour_fragility_penalty"]
        + 0.10 * terms["spectral_nonconstructiveness_penalty"]
    )
    terms["raw"] = raw
    return raw, terms


def build_proof_skeleton(
    *,
    statement: str,
    canonical_signature: str,
    obligations: Iterable[str],
    validation_recipe: Iterable[str],
    failure_modes: Iterable[str],
) -> tuple[str, ...]:
    steps = [
        f"statement: {statement}",
        f"canonical_form: {canonical_signature}",
        "obligations: " + "; ".join(str(item) for item in obligations),
        "validation: " + "; ".join(str(item) for item in validation_recipe),
    ]
    failures = tuple(str(item) for item in failure_modes)
    if failures:
        steps.append("failure_modes: " + "; ".join(failures))
    return tuple(steps)


def build_calibration_report(
    approaches: Iterable[ApproachCard],
    framework_path: Path,
) -> dict[str, Any]:
    families = {item.family for item in approaches}
    tasks = []
    completed = 0
    for target in CALIBRATION_TARGETS:
        matched = sorted(family for family in target["families"] if family in families)
        is_complete = bool(matched)
        tasks.append(
            {
                "task": target["task"],
                "label": target["label"],
                "families": list(target["families"]),
                "matched_families": matched,
                "completed": is_complete,
            }
        )
        completed += 1 if is_complete else 0

    return {
        "framework_path": str(framework_path),
        "completed_tasks": completed,
        "total_tasks": len(CALIBRATION_TARGETS),
        "coverage": completed / max(len(CALIBRATION_TARGETS), 1),
        "tasks": tasks,
        "missing_tasks": [item["task"] for item in tasks if not item["completed"]],
    }


def merge_feedback(
    base: dict[str, tuple[str, ...]],
    extra: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    merged: dict[str, tuple[str, ...]] = {key: tuple(value) for key, value in base.items()}
    for key, values in extra.items():
        merged[key] = tuple(dict.fromkeys((*merged.get(key, ()), *values)))
    return merged


def _excerpt(text: str, limit: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
