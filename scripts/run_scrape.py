#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from competitive_intel.pipelines.run_scrape import run_scrape_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_scrape_pipeline(config_dir=args.config_dir, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
