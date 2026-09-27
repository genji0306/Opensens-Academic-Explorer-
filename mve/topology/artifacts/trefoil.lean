-- Certificate of the decoded PD only; no image or knot-type assertion.
namespace MVETopology
def successor : Nat → Nat
  | 1 => 2
  | 2 => 3
  | 3 => 4
  | 4 => 5
  | 5 => 6
  | 6 => 1
  | _ => 0
def walk : Nat → Nat → Nat
  | 0, a => a
  | n+1, a => successor (walk n a)
theorem one_component :
    (List.range 6).map (fun i => walk i 1) = [1, 2, 3, 4, 5, 6] ∧
    walk 6 1 = 1 := by decide
end MVETopology
