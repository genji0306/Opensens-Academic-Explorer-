"""Lean verification bridge used by the RH research residue gate.

The real AXLE/MCP backends are optional.  Local research and CI use the
deterministic ``mock`` backend, which extracts Lean declaration names and
counts ``sorry`` placeholders without requiring a Lean toolchain or API key.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

LeanBackend = Literal["mock", "http", "mcp"]

_DECL_RE = re.compile(
    r"^\s*(?:noncomputable\s+)?(?:private\s+)?"
    r"(theorem|lemma|def|abbrev|axiom|constant|structure|class|inductive)\s+"
    r"([A-Za-z_][A-Za-z0-9_'.]*)",
    re.MULTILINE,
)
_SORRY_RE = re.compile(r"\bsorry\b")


@dataclass(frozen=True)
class LeanCheckResult:
    """Result returned by :func:`verify` and :func:`verify_file`."""

    passed: bool
    backend: str
    decls: tuple[str, ...]
    sorry_count: int
    messages: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "backend": self.backend,
            "decls": list(self.decls),
            "sorry_count": self.sorry_count,
            "messages": list(self.messages),
            "errors": list(self.errors),
        }


def extract_decls(source: str) -> tuple[str, ...]:
    """Extract top-level Lean declaration names from source text."""
    decls = [match.group(2) for match in _DECL_RE.finditer(source)]
    return tuple(dict.fromkeys(decls))


def _verify_mock(source: str, *, backend_label: str = "mock") -> LeanCheckResult:
    decls = extract_decls(source)
    sorry_count = len(_SORRY_RE.findall(source))
    return LeanCheckResult(
        passed=bool(decls),
        backend=backend_label,
        decls=decls,
        sorry_count=sorry_count,
        messages=("mock verifier: declaration extraction only",),
        errors=() if decls else ("no declarations found",),
    )


def verify(source: str, *, backend: LeanBackend = "mock") -> LeanCheckResult:
    """Verify Lean source with the selected backend.

    ``http`` and ``mcp`` currently require external AXLE configuration.  When
    that configuration is absent, they intentionally fall back to the same
    deterministic mock verifier used by local tests.
    """
    if backend == "mock":
        return _verify_mock(source)

    if not os.environ.get("AXLE_API_KEY"):
        result = _verify_mock(source, backend_label="mock")
        return LeanCheckResult(
            passed=result.passed,
            backend=result.backend,
            decls=result.decls,
            sorry_count=result.sorry_count,
            messages=(
                f"{backend} backend requested without AXLE_API_KEY; fell back to mock",
                *result.messages,
            ),
            errors=result.errors,
        )

    result = _verify_mock(source, backend_label="mock")
    return LeanCheckResult(
        passed=result.passed,
        backend=result.backend,
        decls=result.decls,
        sorry_count=result.sorry_count,
        messages=(
            f"{backend} backend is not wired in this checkout; fell back to mock",
            *result.messages,
        ),
        errors=result.errors,
    )


def verify_file(path: str | Path, *, backend: LeanBackend = "mock") -> LeanCheckResult:
    """Verify a Lean file by reading it as UTF-8 source."""
    lean_path = Path(path)
    try:
        source = lean_path.read_text(encoding="utf-8")
    except OSError as exc:
        return LeanCheckResult(
            passed=False,
            backend=backend,
            decls=(),
            sorry_count=0,
            messages=(),
            errors=(f"{type(exc).__name__}: {exc}",),
        )
    return verify(source, backend=backend)
