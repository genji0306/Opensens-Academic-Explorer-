"""Offline discovery roots select locations, while pins retain integrity authority."""

import hashlib
import json
import subprocess
import pytest
from mve.formalizer import runtime


@pytest.fixture
def pinned_cache(tmp_path, monkeypatch):
    project = tmp_path / "checkout/deep/project"
    project.mkdir(parents=True)
    elan = tmp_path / "elan cache"
    binary = elan / "toolchains/leanprover--lean4---v4.29.0/bin/lean"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"offline executable fixture")
    binary.chmod(0o700)
    packages = tmp_path / "package cache"
    package = packages / "mathlib"
    (package / ".lake/build/lib/lean").mkdir(parents=True)
    manifest = package / "lake-manifest.json"
    manifest.write_text("{}\n")
    lock = {
        "lean_binary": "bin/lean",
        "lean_toolchain": "leanprover/lean4:v4.29.0",
        "lean_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "project_files": {},
        "packages": [
            {
                "name": "mathlib",
                "path": "mathlib",
                "rev": "a" * 40,
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            }
        ],
    }
    (project / "lock.json").write_text(json.dumps(lock))
    monkeypatch.setenv("ELAN_HOME", str(elan))
    monkeypatch.setenv("MVE_LEAN_PACKAGES", str(packages))
    monkeypatch.setattr(runtime.subprocess, "check_output", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(
        runtime.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
    )
    return project, lock, binary, package


def test_roots_resolve_independent_of_checkout_depth(pinned_cache, tmp_path):
    project, lock, binary, package = pinned_cache
    relocated = tmp_path / "elsewhere/at/another/depth/project"
    relocated.mkdir(parents=True)
    (relocated / "lock.json").write_text(json.dumps(lock))
    assert runtime.lean_available(relocated)
    assert runtime.verify_project(relocated) == lock
    env = runtime.lean_environment(relocated, lock)
    assert env["PATH"].split(":")[0] == str(binary.parent)
    assert env["LEAN_PATH"] == str(package / ".lake/build/lib/lean")
    assert set(env) == {"PATH", "HOME", "LEAN_PATH"}


@pytest.mark.parametrize("target", ["binary", "manifest"])
def test_configured_roots_do_not_bypass_hashes(pinned_cache, target):
    project, _, binary, package = pinned_cache
    path = binary if target == "binary" else package / "lake-manifest.json"
    path.write_text("tampered")
    with pytest.raises(ValueError, match="pin mismatch"):
        runtime.verify_project(project)


def test_configured_roots_still_require_pinned_revision(pinned_cache, monkeypatch):
    project, _, _, _ = pinned_cache
    monkeypatch.setattr(runtime.subprocess, "check_output", lambda *a, **k: "b" * 40)
    with pytest.raises(ValueError, match="dependency pin mismatch"):
        runtime.verify_project(project)


def test_missing_configured_cache_never_falls_back(pinned_cache, monkeypatch, tmp_path):
    project, _, _, _ = pinned_cache
    monkeypatch.setenv("MVE_LEAN_PACKAGES", str(tmp_path / "absent"))
    assert not runtime.lean_available(project)
    with pytest.raises(ValueError):
        runtime.verify_project(project)


def test_default_elan_home_and_project_package_cache(
    pinned_cache, monkeypatch, tmp_path
):
    project, lock, binary, package = pinned_cache
    home = tmp_path / "home"
    home.mkdir()
    (home / ".elan").symlink_to(binary.parents[3], target_is_directory=True)
    local_packages = project / ".lake/packages"
    local_packages.mkdir(parents=True)
    (local_packages / "mathlib").symlink_to(package, target_is_directory=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ELAN_HOME")
    monkeypatch.delenv("MVE_LEAN_PACKAGES")
    assert runtime.lean_available(project)
    assert runtime.verify_project(project) == lock


def test_unused_package_need_not_have_compiled_oleans(pinned_cache):
    project, lock, _, package = pinned_cache
    optional = package.parent / "Cli"
    optional.mkdir()
    (optional / "lake-manifest.json").write_bytes(
        (package / "lake-manifest.json").read_bytes()
    )
    lock["packages"].append({**lock["packages"][0], "name": "Cli", "path": "Cli"})
    (project / "lock.json").write_text(json.dumps(lock))
    assert runtime.lean_available(project)
    assert runtime.verify_project(project) == lock
