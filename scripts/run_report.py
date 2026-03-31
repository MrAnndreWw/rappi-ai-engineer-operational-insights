#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from competitive_intel.reporting.generate_report import run_report_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None)
    args = parser.parse_args()
    raise SystemExit(run_report_pipeline(input_path=args.input))


if __name__ == "__main__":
    main()
