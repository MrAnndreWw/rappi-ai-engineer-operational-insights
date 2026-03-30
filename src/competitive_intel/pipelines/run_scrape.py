from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from competitive_intel.config import load_settings, resolve_data_paths


def run_scrape_pipeline(*, config_dir: Path | None = None, dry_run: bool = False) -> int:
    settings = load_settings(config_dir)
    data_dir, outputs_dir = resolve_data_paths()
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    exports_dir = outputs_dir / "exports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    base = config_dir or Path(__file__).resolve().parents[3] / "config"
    loc_file = base / "locations.yaml"
    if not loc_file.is_file():
        loc_file = base / "locations.template.yaml"

    locations: list[dict[str, Any]] = []
    if loc_file.is_file():
        with loc_file.open(encoding="utf-8") as f:
            loc_data = yaml.safe_load(f) or {}
        locations = list(loc_data.get("locations") or [])

    if dry_run:
        print("Dry-run OK.")
        print(f"  settings platforms: {settings.get('platforms', {})}")
        print(f"  locations file: {loc_file}")
        print(f"  locations count: {len(locations)}")
        print(f"  raw_dir: {raw_dir}")
        return 0

    manifest = {
        "status": "pending_implementation",
        "platforms": settings.get("platforms", {}),
        "locations_count": len(locations),
    }
    out_path = raw_dir / "scrape_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Escrito: {out_path}")
    return 0
