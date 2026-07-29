"""Analytical electrochemistry simulator — fully deterministic.

Produces CV / EIS baselines for sensing candidates using closed-form
expressions derived from the legacy ``src/core/sensor_models.py`` module
(Randles-Sevcik, Butler-Volmer, Warburg). This backend is offline,
dependency-free, and used both by the simulation lab itself and by the
Phase F Sensing Studio as a cheap ground-truth source.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from ..base import (
    SimulationBackend,
    SimulationKind,
    SimulationRequest,
    SimulationResult,
)


@dataclass
class AnalyticalElectrochemSimulator:
    backend: SimulationBackend = SimulationBackend(
        name="analytical_electrochem",
        kinds=("electrochem", "cv_baseline", "eis_baseline"),
        hot=True,
        cost_estimate=0.1,
    )

    def supports(self, kind: SimulationKind) -> bool:
        return kind in self.backend.kinds

    def run(self, request: SimulationRequest) -> SimulationResult:
        if not self.supports(request.kind):
            return SimulationResult(
                request=request,
                backend=self.backend.name,
                ok=False,
                error=f"kind {request.kind!r} not supported",
            )

        t0 = time.time()
        params = dict(request.parameters)
        # Defaults reproduce a reasonable Au-SPE × aqueous experiment.
        n = float(params.get("electrons", 1.0))
        area_cm2 = float(params.get("area_cm2", 0.071))       # 3 mm disk
        diffusion = float(params.get("diffusion_cm2_s", 6.7e-6))
        concentration_M = float(params.get("concentration_M", 1e-3))
        scan_rate_V_s = float(params.get("scan_rate_V_s", 0.1))
        alpha = float(params.get("alpha", 0.5))
        overpotential_V = float(params.get("overpotential_V", 0.2))

        if request.kind in ("electrochem", "cv_baseline"):
            # Randles-Sevcik peak current (298 K)
            peak_current_A = (
                2.69e5
                * (n ** 1.5)
                * area_cm2
                * math.sqrt(diffusion * scan_rate_V_s)
                * concentration_M
            )
            # Butler-Volmer anodic contribution
            bv_anodic = math.exp((1.0 - alpha) * n * overpotential_V / 0.0257)
            observables = {
                "peak_current_A": peak_current_A,
                "bv_anodic_factor": bv_anodic,
            }
            summary = (
                f"CV baseline: Ip={peak_current_A:.3e} A "
                f"(n={n}, A={area_cm2} cm², D={diffusion:.2e})"
            )
        else:
            # EIS: simplified Randles circuit, single-sine diagnostics.
            rs_ohm = float(params.get("rs_ohm", 100.0))
            rct_ohm = float(params.get("rct_ohm", 1_000.0))
            cdl_F = float(params.get("cdl_F", 1e-6))
            omega = 2 * math.pi * float(params.get("frequency_Hz", 1_000.0))
            z_real = rs_ohm + rct_ohm / (1 + (omega * rct_ohm * cdl_F) ** 2)
            z_imag = -(omega * rct_ohm ** 2 * cdl_F) / (1 + (omega * rct_ohm * cdl_F) ** 2)
            observables = {
                "z_real_ohm": z_real,
                "z_imag_ohm": z_imag,
                "rs_ohm": rs_ohm,
                "rct_ohm": rct_ohm,
            }
            summary = (
                f"EIS baseline: |Z_re|={z_real:.1f}, Z_im={z_imag:.1f} "
                f"(Rct={rct_ohm}, Cdl={cdl_F})"
            )

        return SimulationResult(
            request=request,
            backend=self.backend.name,
            ok=True,
            observables=observables,
            summary=summary,
            elapsed_s=time.time() - t0,
        )
