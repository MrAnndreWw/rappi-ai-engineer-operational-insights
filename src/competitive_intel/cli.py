from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="competitive-intel")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape")
    p_scrape.add_argument("--config-dir", type=Path, default=None)
    p_scrape.add_argument("--dry-run", action="store_true")
    p_scrape.add_argument("--platform", type=str, default=None)
    p_scrape.add_argument("--headed", action="store_true")

    p_report = sub.add_parser("report")
    p_report.add_argument("--input", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "scrape":
        from competitive_intel.pipelines.run_scrape import run_scrape_pipeline

        return run_scrape_pipeline(
            config_dir=args.config_dir,
            dry_run=args.dry_run,
            platform=args.platform,
            headed=args.headed,
        )

    if args.command == "report":
        from competitive_intel.reporting.generate_report import run_report_pipeline

        return run_report_pipeline(input_path=args.input)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
