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
    p_scrape.add_argument("-v", "--verbose", action="store_true")
    p_scrape.add_argument("--rappi-dump-pages", action="store_true")
    p_scrape.add_argument("--max-locations", type=int, default=None, metavar="N")

    p_report = sub.add_parser("report")
    p_report.add_argument("--input", type=Path, default=None)

    p_cmp = sub.add_parser("compare", help="Comparar Rappi vs Uber desde scrape JSONL → outputs/exports")
    p_cmp.add_argument("--input", type=Path, default=None, help="scrape_*.jsonl (default: más reciente en data/raw)")
    p_cmp.add_argument("--output", type=Path, default=None)
    p_cmp.add_argument("--similarity", type=float, default=0.9, metavar="0-1")

    args = parser.parse_args(argv)

    if args.command == "scrape":
        from competitive_intel.pipelines.run_scrape import run_scrape_pipeline

        return run_scrape_pipeline(
            config_dir=args.config_dir,
            dry_run=args.dry_run,
            platform=args.platform,
            headed=args.headed,
            verbose=args.verbose,
            rappi_dump_pages=args.rappi_dump_pages,
            max_locations=args.max_locations,
        )

    if args.command == "report":
        from competitive_intel.reporting.generate_report import run_report_pipeline

        return run_report_pipeline(input_path=args.input)

    if args.command == "compare":
        from competitive_intel.analysis.platform_comparison import run_comparison_export

        out = run_comparison_export(
            input_path=args.input,
            output_path=args.output,
            similar_threshold=max(0.5, min(1.0, args.similarity)),
        )
        print(out)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
