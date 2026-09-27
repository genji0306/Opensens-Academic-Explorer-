"""Offline full corpus generation; no model or network transport."""

import argparse
import json
import subprocess
from pathlib import Path
from mve.generator.corpus import build_corpus
from mve.generator.receipts import write_receipts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--generation-receipt", type=Path)
    parser.add_argument("--audit-receipt", type=Path)
    args = parser.parse_args()
    if bool(args.generation_receipt) != bool(args.audit_receipt):
        parser.error("both receipt paths are required together")
    root = Path(__file__).resolve().parents[2]
    code_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()

    def progress(done, total):
        if done % 100 == 0 or done == total:
            print(f"{done}/{total} diagrams", flush=True)

    report = build_corpus(
        args.output, code_sha=code_sha, progress=progress, workers=args.workers
    )
    if args.generation_receipt:
        write_receipts(args.output, args.generation_receipt, args.audit_receipt)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "items"}, indent=2
        )
    )
    return 0 if report["acceptance"] == "generated_counts_met" else 1


if __name__ == "__main__":
    raise SystemExit(main())
