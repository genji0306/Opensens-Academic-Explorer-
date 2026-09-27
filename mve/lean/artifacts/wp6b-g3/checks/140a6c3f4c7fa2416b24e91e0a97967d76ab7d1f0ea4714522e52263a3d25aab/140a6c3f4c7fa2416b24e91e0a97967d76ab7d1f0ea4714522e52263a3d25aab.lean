import Mathlib.Geometry.Euclidean.Angle.Unoriented.Affine
import Mathlib.Geometry.Euclidean.Sphere.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
set_option autoImplicit false
abbrev Point := EuclideanSpace ℝ (Fin 2)
def statement Prop := ∀ (p0 p1 p2 : Point), (p2 = midpoint ℝ p0 p1) → (p0 ≠ p1) → (p0 ≠ p2) → (p1 ≠ p2) → (Collinear ℝ ({p0,p1,p2} : Set Point))
#check statement
