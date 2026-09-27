"""python3 -m mve.verdicts apply RECORD REQUEST | export --split ... RECORD..."""

import argparse
import json
from pathlib import Path
import sys
from mve.record import Record
from mve.evaluation.splits import FrozenSplit
from mve.verdicts.labels import export_labels, export_verdicts
from mve.verdicts.store import apply_request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    apply = commands.add_parser("apply", help="atomically apply a local JSON request")
    apply.add_argument("record", type=Path)
    apply.add_argument("request", type=Path)
    export = commands.add_parser("export", help="write explicit catalogue labels as JSONL")
    export.add_argument("--split", required=True, type=Path)
    export.add_argument("--split-sha256", required=True)
    export.add_argument(
        "--purpose", choices=["training", "calibration", "evaluation"], default="training"
    )
    export.add_argument("--kind", choices=["labels", "verdicts"], default="labels")
    export.add_argument("records", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            result = apply_request(args.record, json.loads(args.request.read_text()))
            data = result.to_dict()
            print(json.dumps({"record_id": data["record_id"], "revision": data["revision"]}))
        else:
            split = FrozenSplit.load(args.split.read_text(), expected_sha256=args.split_sha256)
            records = [Record.from_json(path.read_text()) for path in args.records]
            exporter = export_labels if args.kind == "labels" else export_verdicts
            rows = exporter(records, split, purpose=args.purpose)
            for row in rows:
                print(json.dumps(row, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"verdicts: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
