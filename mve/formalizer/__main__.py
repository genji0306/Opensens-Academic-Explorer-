"""Offline native Mathlib statement check; never runs a prover or fetches packages."""

import argparse
import json
from pathlib import Path
from mve.record import Record
from mve.formalizer.repairs import formalize


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--project", type=Path, default=Path(__file__).resolve().parents[1] / "lean"
    )
    args = parser.parse_args(argv)
    record = Record.from_json(args.record.read_text())
    result, receipt = formalize(record, args.project, args.output)
    (args.output / "record.json").write_text(result.to_json())
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "typechecked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
