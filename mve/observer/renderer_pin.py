"""Read-only derived Chrome bundle pin and operator smoke recorder."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess

from mve.observer import capture_policy as policy

LOCK = Path(__file__).resolve().parents[1] / "DEPS.lock"
VERSION = re.compile(r"\d+\.\d+\.\d+\.\d+")


def record(name):
    return json.loads(LOCK.read_text())["pinned_renderers"][name]


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def framework_hash(root):
    """Hash sorted per-file shasum lines, preserving spaces in filenames."""
    files = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
        for name in names:
            path = Path(directory) / name
            if not path.is_symlink() and path.is_file():
                rel = "./" + path.relative_to(root).as_posix()
                if "\n" in rel or "\\" in rel:
                    raise policy.RendererPinError("ambiguous framework filename")
                files.append((rel, path))
    if not files:
        raise policy.RendererPinError("empty framework")
    result = hashlib.sha256()
    for rel, path in sorted(files):
        result.update(f"{sha(path)}  {rel}\n".encode())
    return result.hexdigest()


def layout(chrome):
    chrome = Path(chrome)
    contents = chrome.parent.parent
    if chrome != contents / "MacOS/Google Chrome":
        raise policy.RendererPinError("unexpected launcher location")
    versions = contents / "Frameworks/Google Chrome Framework.framework/Versions"
    return contents, versions


def symlinks(contents):
    """Inventory every bundle symlink without following one outside the bundle."""
    links = {}
    for directory, dirs, names in os.walk(contents, followlinks=False):
        for name in dirs + names:
            path = Path(directory) / name
            if path.is_symlink():
                rel = path.relative_to(contents).as_posix()
                target = os.readlink(path)
                if "\n" in rel or "\n" in target:
                    raise policy.RendererPinError("ambiguous symlink")
                links[rel] = target
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
    return dict(sorted(links.items()))


def candidate(chrome):
    """Print-ready candidate derived solely from bytes of an operator bundle."""
    contents, versions = layout(chrome)
    with (contents / "Info.plist").open("rb") as stream:
        version = plistlib.load(stream)["CFBundleShortVersionString"]
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise policy.RendererPinError("invalid bundle version")
    current = versions / "Current"
    if not current.is_symlink() or os.readlink(current) != version:
        raise policy.RendererPinError("framework selection mismatch")
    tree = versions / version
    if tree.is_symlink() or not tree.is_dir():
        raise policy.RendererPinError("framework missing")
    return dict(
        browser_version=version,
        framework_tree_sha256=framework_hash(tree),
        launcher_sha256=sha(chrome),
        info_plist_sha256=sha(contents / "Info.plist"),
        versions_current_target=os.readlink(current),
        bundle_symlinks=symlinks(contents),
    )


def verify(chrome, name):
    if name is None:
        return policy.browser_version(chrome)
    try:
        expected = record(name)
        actual = candidate(chrome)
        if any(actual[k] != expected[k] for k in actual):
            raise policy.RendererPinError("derived renderer bundle mismatch")
        return actual["browser_version"]
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        plistlib.InvalidFileException,
    ) as exc:
        if isinstance(exc, policy.RendererPinError):
            raise
        raise policy.RendererPinError("derived renderer bundle check failed") from exc


def preflight(chrome, name):
    """Verify all pinned bytes and bounded native --version before evidence writes."""
    expected = verify(chrome, name)
    if name is None:
        return expected
    try:
        result = subprocess.run(
            [str(chrome), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        match = re.fullmatch(r"Google Chrome (\d+\.\d+\.\d+\.\d+)\s*", result.stdout)
        return policy.one_version([expected, match.group(1) if match else None])
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise policy.RendererPinError("pinned renderer version probe failed") from exc


def smoke(source, chrome, output):
    """Native operator only: record source, exact plist edits, launch and signature."""
    source = Path(source)
    chrome = Path(chrome)
    output = Path(output)
    if any(part == "mve" for part in output.parts) and "generated" in output.parts:
        raise ValueError("smoke record must be outside generated evidence")
    source_chrome = source / "Contents/MacOS/Google Chrome"
    before = candidate(source_chrome)
    after = candidate(chrome)
    before_plist = plistlib.loads((source / "Contents/Info.plist").read_bytes())
    after_plist = plistlib.loads((chrome.parent.parent / "Info.plist").read_bytes())
    edits = {
        k: {"before": before_plist.get(k), "after": after_plist.get(k)}
        for k in sorted(set(before_plist) | set(after_plist))
        if before_plist.get(k) != after_plist.get(k)
    }
    try:
        version_run = subprocess.run(
            [str(chrome), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        native_version_output = version_run.stdout.strip()[:256]
    except (OSError, subprocess.SubprocessError):
        native_version_output = None
    try:
        signature = subprocess.run(
            ["codesign", "--verify", "--verbose=2", str(chrome.parent.parent.parent)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        codesign_succeeded = signature.returncode == 0
        codesign_output = (signature.stdout + signature.stderr)[:4096]
    except (OSError, subprocess.SubprocessError):
        codesign_succeeded = False
        codesign_output = "codesign probe failed"
    context_version = None
    launch_succeeded = False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                "",
                executable_path=str(chrome),
                headless=True,
                timeout=policy.PASS_OVERHEAD_SECONDS * 1000,
                args=[
                    "--headless=new",
                    "--no-sandbox",
                    "--no-first-run",
                    "--disable-background-networking",
                ],
            )
            try:
                context_version = context.browser.version
                launch_succeeded = True
            finally:
                context.close()
    except Exception:
        pass  # The immutable smoke record captures failed launch without exception text.
    result = dict(
        schema="mve-renderer-smoke-v1",
        source_copy={
            "basename": source.name,
            "framework_tree_sha256": before["framework_tree_sha256"],
        },
        info_plist_edits=edits,
        info_plist_before_sha256=before["info_plist_sha256"],
        info_plist_after_sha256=after["info_plist_sha256"],
        final_bundle=after,
        native_version_output=native_version_output,
        browser_context_version=context_version,
        launch_succeeded=launch_succeeded,
        codesign_verify_succeeded=codesign_succeeded,
        codesign_output=codesign_output,
    )
    raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["sha256"] = hashlib.sha256(raw).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return result["sha256"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--candidate", type=Path, metavar="CHROME")
    group.add_argument("--smoke", type=Path, metavar="SOURCE_BUNDLE")
    parser.add_argument("--chrome", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.candidate:
        print(json.dumps(candidate(args.candidate), sort_keys=True, indent=2))
    else:
        if args.chrome is None or args.output is None:
            parser.error("--smoke requires --chrome and --output")
        print(smoke(args.smoke, args.chrome, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
