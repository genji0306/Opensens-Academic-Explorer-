"""Offline full corpus generation; no model or network transport."""

import argparse
import json
import subprocess
from pathlib import Path
from mve.generator.corpus import build_corpus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    code_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()

    def progress(done, total):
        if done % 100 == 0 or done == total:
            print(f"{done}/{total} diagrams", flush=True)

    report = build_corpus(args.output, code_sha=code_sha, progress=progress)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "items"}, indent=2
        )
    )
    return 0 if report["acceptance"] == "generated_counts_met" else 1


if __name__ == "__main__":
    raise SystemExit(main())
