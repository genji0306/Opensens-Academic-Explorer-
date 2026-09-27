# WP-4 geometry-selection review follow-ups

Branch `codex/mve-wp4-geometry-guards` starts from github/mve/integration `8da83b3c2a2`. It is unmerged for Opus review. No production behavior changed.

Eight added tests cover duplicate and unknown geometry IDs, a nonpoint owner, an invalid owner, invalid geometry, two selected geometries for the same entity, and the wrong-frame defensive guard. A sentinel asserts that selection failures happen before the numeric kernel. All fixtures except the wrong-frame defense are validated v5 Records. Since v5 itself prohibits a wrong frame, that case first confirms schema refusal and then exercises the adapter guard with an explicitly invalid input stub.

The successful measurement test asserts that `content_hash` and `record_id` are unchanged, revision increases by one, one measurement is appended, and the original immutable record is unchanged.

Validation: `COVERAGE_CORE=pytrace python3 -m pytest tests/mve -q --cov=mve.measurement --cov-report=term-missing` — **317 passed**, **98% measurement coverage**, **100% records.py coverage**. Ruff and diff checks pass. Offline only; zero hosted calls or downloads. Shared wiki refresh files are absent from this checkout. No independent review PASS or merge is claimed.
