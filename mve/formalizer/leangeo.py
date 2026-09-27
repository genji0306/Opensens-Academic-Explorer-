"""LeanGeo adapter interface only; no local runtime or semantic bridge is attested."""

from typing import Protocol
from mve.identity import digest


class LeanGeoAdapter(Protocol):
    def translate(self, ir: dict) -> dict: ...


class UnavailableLeanGeo:
    def translate(self, ir: dict) -> dict:
        return {
            "status": "unsupported",
            "target": "leangeo",
            "ir_sha256": digest(ir),
            "reason": "failed: not present locally; vendoring deferred to owner-approved packet",
            "statement": None,
            "integration_checked": False,
        }
