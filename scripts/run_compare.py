#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from competitive_intel.analysis.platform_comparison import run_comparison_export


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara Rappi vs Uber Eats vs DiDi Food (ancla Rappi) desde un scrape JSONL y escribe JSON en outputs/exports.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Ruta al scrape_*.jsonl (por defecto: el más reciente en data/raw).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta del .json de salida (por defecto: outputs/exports/rappi_uber_didi_comparison_<UTC>.json).",
    )
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.9,
        metavar="0-1",
        help="Umbral mínimo de similitud de nombre (SequenceMatcher) para emparejar productos (default 0.9).",
    )
    args = parser.parse_args()
    out = run_comparison_export(
        input_path=args.input,
        output_path=args.output,
        similar_threshold=max(0.5, min(1.0, args.similarity)),
    )
    print(out)


if __name__ == "__main__":
    main()
