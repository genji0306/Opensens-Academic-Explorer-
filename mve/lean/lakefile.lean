import Lake
open Lake DSL
package mve where
  leanOptions := #[⟨`autoImplicit, false⟩]
require mathlib from git "https://github.com/leanprover-community/mathlib4.git" @ "v4.29.0"
@[default_target]
lean_lib MVE where
  roots := #[`MVE.Spike]
