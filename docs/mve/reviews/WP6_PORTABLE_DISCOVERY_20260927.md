# WP-6a portable offline discovery follow-up

Branch `codex/mve-wp6-portable-discovery` starts from github/mve/integration `0550144a895` and remains unmerged for Opus review. This is separate from WP-2's E1a mathematical-policy revision.

Lean is resolved from `ELAN_HOME` (default `~/.elan`), the pinned toolchain name `leanprover/lean4:v4.29.0`, and the lock's relative `bin/lean`. Package paths are relative to `MVE_LEAN_PACKAGES`; when unset, the default is the project's existing `.lake/packages`. Both roots may refer to an existing offline cache. No checkout-depth assumption, installer, download or network fallback remains in this discovery path.

For another checkout, set `MVE_LEAN_PACKAGES` to the existing directory containing `mathlib`, `batteries`, `aesop` and the other pinned packages. Set `ELAN_HOME` if the installed toolchain is outside `~/.elan`, then run `python3 -m pytest tests/mve/test_formalizer_runtime.py -q`. Explicitly configured missing roots are never silently replaced by another cache.

Location configuration does not grant integrity authority: compile_source still verifies the Lean executable SHA-256, project file hashes, each package's Git revision and clean tracked tree. It now also checks the already-recorded package manifest SHA-256 values. The binary, package revisions and hash values are unchanged in lock.json. Parent directories and absolute paths are refused inside the lock's relative path fields; absolute cache roots belong in the environment configuration only.

The compiler receives only PATH, HOME and LEAN_PATH. ELAN_HOME/MVE_LEAN_PACKAGES are used by discovery and are not forwarded to Lean. The sandbox denies network only; it does not contain filesystem access. Typechecking still never claims proof authority.

The real-Lean test gate checks local binary/cache availability and prints one explanatory line when unavailable. Missing packages are diagnosed through MVE_LEAN_PACKAGES. The Mathlib compiled cache must exist; unused transitive packages such as Cli need not have compiled artifacts, although their source manifest/revision pins are still verified before compilation. Present but tampered caches fail verification instead of being skipped.

Tests cover custom roots, default roots, a relocated project at a different directory depth, missing-root refusal, binary/manifest/revision tampering, the unused-package case, and exactly one skip diagnostic. The real relocated-project test copies only the pinned project files and lock, then typechecks a record using the configured shared cache.

A fresh successful midpoint receipt is under `mve/lean/artifacts/portable-midpoint/`; it pins the new lock and uses output-relative statement/log paths. Earlier midpoint and Lake receipts remain historical evidence for their original lock/configuration. No files were fetched or merged, and hosted calls remain zero. Validation counts follow below.

Validation: `COVERAGE_CORE=pytrace python3 -m pytest tests/mve -q --cov=mve.formalizer --cov-report=term-missing` — **357 passed, none skipped**, including all three real-Lean checks and the relocated-project case. Formalizer coverage is 85%; runtime.py is 95%. Ruff, source pins, unchanged dependency-integrity pins and file/function limits pass.
