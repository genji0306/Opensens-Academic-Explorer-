import Mathlib.Geometry.Euclidean.Angle.Unoriented.Affine
import Mathlib.Geometry.Euclidean.Sphere.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
set_option autoImplicit false
abbrev Point := EuclideanSpace ℝ (Fin 2)
def collinear (A B C : Point) : Prop := Collinear ℝ ({A,B,C} : Set Point)
def concyclic (A B C D : Point) : Prop := EuclideanGeometry.Concyclic ({A,B,C,D} : Set Point)
def parallel (A B C D : Point) : Prop := AffineSubspace.Parallel (affineSpan ℝ ({A,B} : Set Point)) (affineSpan ℝ ({C,D} : Set Point))
def perpendicular (A B C D : Point) : Prop := inner ℝ (B-A) (D-C) = 0
def equalLength (A B C D : Point) : Prop := dist A B = dist C D
def equalAngle (A B C D E F : Point) : Prop := EuclideanGeometry.angle A B C = EuclideanGeometry.angle D E F
def mid (M A B : Point) : Prop := M = midpoint ℝ A B
def between (B A C : Point) : Prop := Sbtw ℝ A B C
def right (A B C : Point) : Prop := EuclideanGeometry.angle A B C = Real.pi / 2
def distinct (A B : Point) : Prop := A ≠ B
def notCollinear (A B C : Point) : Prop := ¬ Collinear ℝ ({A,B,C} : Set Point)
#check collinear
#check concyclic
#check parallel
#check perpendicular
#check equalLength
#check equalAngle
#check mid
#check between
#check right
#check distinct
#check notCollinear
