"""Local card intake and offline regression replay. No hosted transport exists."""

import argparse
import json
from pathlib import Path
from .card import Card, card_hash, spec_hash


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    card = sub.add_parser("card").add_subparsers(dest="operation", required=True)
    new = card.add_parser("new")
    new.add_argument("spec", type=Path)
    new.add_argument("--output", type=Path, required=True)
    regression = sub.add_parser("regression")
    regression.add_argument("--cache", type=Path, required=True)
    regression.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "card":
        d = json.loads(args.spec.read_text())
        d.update(revision=1, status="draft", judgments=[], artifacts=[], history=[])
        d["check_spec"]["spec_sha256"] = spec_hash(d["check_spec"])
        d["content_hash"] = card_hash(d)
        output = Card.from_dict(d).to_dict()
    else:
        from .checks.regression import reproduce, compare

        output = reproduce(args.cache)
        output["comparison"] = compare(output)
    with args.output.open("x") as f:
        f.write(json.dumps(output, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
