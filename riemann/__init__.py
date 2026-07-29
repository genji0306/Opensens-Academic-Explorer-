"""Riemann Zeta Zero Discovery — multi-agent convergence loop for finding
the functional principle of non-trivial zeros.

Architecture:
    Agent A  (pattern extractor)  -->  rule parameters from LMFDB dataset
    Agent B  (predictor)          -->  synthetic gamma_n from rule
    Agent Ob (scorer)             -->  compare synthetic vs real; score >= 0.95
    Agent C  (synthesizer)        -->  closed-form generator after convergence

Dataset: Odlyzko's zeros1 (first 100,000 non-trivial zeros, precision ~3e-9).
"""

__version__ = "0.1.0"
