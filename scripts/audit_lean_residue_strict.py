"""Phase 3 honest-verification audit.

Runs the strict Lean bridge backend across every .lean file under lean/RH/
and reports the gap between mock-passes (sorry-filled skeletons accepted)
and strict-passes (sorry-filled skeletons rejected as unproven).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from riemann.research.lean_bridge import verify_file


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    lean_root = repo_root / "lean" / "RH"
    if not lean_root.exists():
        print(f"no lean/RH/ at {lean_root}")
        return

    files = sorted(lean_root.rglob("*.lean"))
    print(f"scanning {len(files)} .lean files under {lean_root.relative_to(repo_root)}\n")

    mock_pass = strict_pass = sorry_total = 0
    by_subdir: dict[str, dict[str, int]] = {}
    strict_pass_files: list[str] = []

    for f in files:
        rel = f.relative_to(repo_root)
        subdir = rel.parts[2] if len(rel.parts) > 2 else "root"
        by_subdir.setdefault(subdir, {"files": 0, "mock_pass": 0, "strict_pass": 0, "sorry": 0})
        by_subdir[subdir]["files"] += 1

        mock_r = verify_file(f, backend="mock")
        strict_r = verify_file(f, backend="strict")

        if mock_r.passed:
            mock_pass += 1
            by_subdir[subdir]["mock_pass"] += 1
        if strict_r.passed:
            strict_pass += 1
            by_subdir[subdir]["strict_pass"] += 1
            strict_pass_files.append(str(rel))
        sorry_total += mock_r.sorry_count
        by_subdir[subdir]["sorry"] += mock_r.sorry_count

    print("=== AGGREGATE ===")
    print(f"  files:          {len(files)}")
    print(f"  mock-pass:      {mock_pass} ({100*mock_pass/max(1,len(files)):.1f}%)")
    print(f"  strict-pass:    {strict_pass} ({100*strict_pass/max(1,len(files)):.1f}%)")
    print(f"  total sorries:  {sorry_total}")
    print(f"  HONEST GAP:     {mock_pass - strict_pass} files would pass mock but fail strict\n")

    print("=== BY SUBDIRECTORY ===")
    for subdir, s in sorted(by_subdir.items(), key=lambda kv: -kv[1]["files"]):
        print(f"  {subdir:35s}  files={s['files']:>4}  mock={s['mock_pass']:>4}  strict={s['strict_pass']:>4}  sorries={s['sorry']:>5}")

    print("\n=== STRICT-PASSING FILES (truly proven, no sorry) ===")
    if strict_pass_files:
        for f in strict_pass_files[:20]:
            print(f"  {f}")
        if len(strict_pass_files) > 20:
            print(f"  ... and {len(strict_pass_files) - 20} more")
    else:
        print("  (none)")

    out = {
        "scanned_files": len(files),
        "mock_pass_count": mock_pass,
        "strict_pass_count": strict_pass,
        "sorry_total": sorry_total,
        "honest_gap": mock_pass - strict_pass,
        "by_subdirectory": by_subdir,
        "strict_pass_files": strict_pass_files,
    }
    out_path = repo_root / "data" / "riemann" / "research" / "phase3_strict_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\naudit report → {out_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
