#!/usr/bin/env python3
"""Genera resumen de insights + figuras a partir de un JSON rappi_uber_didi_comparison_*.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from competitive_intel.reporting.competitive_insights_from_export import run_from_path
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from competitive_intel.reporting.competitive_insights_from_export import run_from_path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Escribe *_insights_summary.json y 3 PNG junto al export de comparación."
    )
    p.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Ruta al JSON de comparación (default: más reciente rappi_uber_didi_comparison_*.json en outputs/exports)",
    )
    args = p.parse_args()
    input_path = args.input
    if input_path is None:
        exports = Path(__file__).resolve().parents[1] / "outputs" / "exports"
        candidates = sorted(exports.glob("rappi_uber_didi_comparison_*.json"), key=lambda x: x.stat().st_mtime)
        if not candidates:
            print("No hay rappi_uber_didi_comparison_*.json en outputs/exports", file=sys.stderr)
            return 1
        input_path = candidates[-1]
    if not input_path.is_file():
        print(f"No existe: {input_path}", file=sys.stderr)
        return 1
    out = run_from_path(input_path)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
