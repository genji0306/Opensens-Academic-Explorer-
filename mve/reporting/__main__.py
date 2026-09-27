"""Generate SUMMARY.md and SUMMARY.json entirely from a pinned local Git commit."""

import argparse
from pathlib import Path
from mve.reporting.current import build_report, CAMPAIGN
from mve.reporting.render import markdown, serialize


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument(
        "--campaign",
        default=CAMPAIGN,
        help="committed BudgetLedger.snapshot() JSON, repository-relative",
    )
    parser.add_argument("--output", type=Path, default=Path("docs/mve/reports"))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    report = build_report(root, args.revision, campaign_path=args.campaign)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "SUMMARY.json").write_text(serialize(report), encoding="utf-8")
    (args.output / "SUMMARY.md").write_text(markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
