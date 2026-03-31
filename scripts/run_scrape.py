#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from competitive_intel.pipelines.run_scrape import run_scrape_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--platform", type=str, default=None, help="Solo esta plataforma (rappi|uber_eats|didi_food)")
    parser.add_argument("--headed", action="store_true", help="Navegador visible (headless=false)")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log DEBUG (timings, Playwright, sesión, detalle por cadena)",
    )
    parser.add_argument(
        "--rappi-dump-pages",
        action="store_true",
        help="Rappi: guardar HTML+PNG+meta por paso en data/debug/rappi_pages (optimizar flujo de dirección)",
    )
    parser.add_argument(
        "--max-locations",
        type=int,
        default=None,
        metavar="N",
        help="Solo las primeras N ubicaciones (útil con --rappi-dump-pages)",
    )
    args = parser.parse_args()
    raise SystemExit(
        run_scrape_pipeline(
            config_dir=args.config_dir,
            dry_run=args.dry_run,
            platform=args.platform,
            headed=args.headed,
            verbose=args.verbose,
            rappi_dump_pages=args.rappi_dump_pages,
            max_locations=args.max_locations,
        )
    )


if __name__ == "__main__":
    main()
