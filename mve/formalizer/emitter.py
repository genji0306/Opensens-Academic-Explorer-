"""Native Mathlib propositions only; emission supplies no proofs or implicit assumptions."""

import re
from mve.predicates import canonical_proposition

HEADER = """import Mathlib.Geometry.Euclidean.Angle.Unoriented.Affine
import Mathlib.Geometry.Euclidean.Sphere.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
set_option autoImplicit false
abbrev Point := EuclideanSpace ℝ (Fin 2)
"""


def native(proposition, mapping):
    prop = canonical_proposition(proposition)
    try:
        p = [mapping[name] for name in prop["args"]]
    except KeyError as exc:
        raise ValueError("unbound point") from exc
    if any(not re.fullmatch(r"p[0-9]+", name) for name in p):
        raise ValueError("unsafe Lean name")
    pred = prop["pred"]
    group = "{" + ",".join(p) + "}"
    if pred in {"Collinear", "NotCollinear"}:
        return (
            "¬ " if pred == "NotCollinear" else ""
        ) + f"Collinear ℝ ({group} : Set Point)"
    if pred == "Concyclic":
        return f"EuclideanGeometry.Concyclic ({group} : Set Point)"
    if pred == "Parallel":
        return f"AffineSubspace.Parallel (affineSpan ℝ ({{{p[0]},{p[1]}}} : Set Point)) (affineSpan ℝ ({{{p[2]},{p[3]}}} : Set Point))"
    if pred == "Perpendicular":
        return f"inner ℝ ({p[1]}-{p[0]}) ({p[3]}-{p[2]}) = 0"
    if pred == "EqualLength":
        return f"dist {p[0]} {p[1]} = dist {p[2]} {p[3]}"
    if pred == "EqualAngle":
        return f'EuclideanGeometry.angle {" ".join(p[:3])} = EuclideanGeometry.angle {" ".join(p[3:])}'
    if pred == "Midpoint":
        return f"{p[0]} = midpoint ℝ {p[1]} {p[2]}"
    if pred == "SBetween":
        return f"Sbtw ℝ {p[1]} {p[0]} {p[2]}"
    if pred == "RightAngle":
        return f'EuclideanGeometry.angle {" ".join(p)} = Real.pi / 2'
    if pred == "Distinct":
        return f"{p[0]} ≠ {p[1]}"
    raise ValueError("unsupported native target")


def emit(ir):
    if ir.get("schema") != "mve-formal-ir-v1" or ir.get("exact_constants") != []:
        raise ValueError("unsupported IR or scalar constants")
    binders = ir["binders"]
    if not binders or any(b["type"] != "Point" for b in binders):
        raise ValueError("nonempty Point binders required")
    mapping = {b["name"]: f"p{i}" for i, b in enumerate(binders)}
    if len(mapping) != len(binders):
        raise ValueError("duplicate binders")
    args = " ".join(mapping.values())
    for i, binder in enumerate(binders):
        if binder.get("entity"):
            mapping.setdefault(binder["entity"], f"p{i}")
    premises = [native(n["proposition"], mapping) for n in ir["premises"]]
    if ir["goal"] is None:
        if not premises:
            raise ValueError("no authorized statements")
        return (
            HEADER
            + "\n".join(
                f"def assumption_{i} ({args} : Point) : Prop := {p}"
                for i, p in enumerate(premises)
            )
            + "\n"
        )
    goal = native(ir["goal"]["proposition"], mapping)
    body = " → ".join(f"({p})" for p in [*premises, goal])
    return (
        HEADER
        + f"def statement : Prop := ∀ ({args} : Point), {body}\n#check statement\n"
    )
