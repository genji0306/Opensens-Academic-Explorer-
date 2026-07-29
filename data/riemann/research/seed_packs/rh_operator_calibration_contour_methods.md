# Contour Manipulation Calibration

This calibration seed exists to force the research loop to encode standard
contour manipulations directly, even when they are not attached to one narrow RH
family label.

Required contour primitives:

- contour integral
- shift contour
- residue extraction
- kernel weighting
- asymptotic bookkeeping

Calibration task:

Represent a standard contour argument as a typed operator chain, normalize the
path description, and preserve the assumptions that make a contour shift legal.

This is intentionally a general analytic seed. It should remain in the
`general_analytic` family unless the corpus later grows a dedicated contour
family with its own keywords and normalization rules.
