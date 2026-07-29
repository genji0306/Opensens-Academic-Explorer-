# Functional Equation Calibration

This calibration seed exists to force the operator language to encode the
classical functional equation in a compact, typed form.

Use the completed xi-function and the gamma factor explicitly:

- xi-function `XI(s)`
- zeta `ZETA(s)`
- gamma factor `GAMMA(s/2)`
- log-gamma `LOG_GAMMA(s/2)`
- critical restriction `CRITICAL_RESTRICTION`

Core calibration statement:

`XI(s) = XI(1-s)`

Equivalent functional-equation form:

`pi^(-s/2) * GAMMA(s/2) * ZETA(s) = pi^(-(1-s)/2) * GAMMA((1-s)/2) * ZETA(1-s)`

The purpose is not novelty. The purpose is to ensure the operator grammar can
normalize a known xi-function symmetry and functional-equation identity before
it is allowed to score new RH constructions.
