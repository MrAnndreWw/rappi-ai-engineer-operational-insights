from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_settings(
    config_dir: Path | None = None,
    *,
    env_file: str | Path | None = None,
) -> dict[str, Any]:
    load_dotenv(env_file or _repo_root() / ".env")
    base = config_dir or _repo_root() / "config"
    path = base / "default.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró configuración: {path}")
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    if os.getenv("CI_MX_ENV"):
        data.setdefault("runtime", {})["env"] = os.getenv("CI_MX_ENV")
    return data


def resolve_data_paths() -> tuple[Path, Path]:
    root = _repo_root()
    data = Path(os.getenv("CI_MX_DATA_DIR", root / "data"))
    outputs = Path(os.getenv("CI_MX_OUTPUT_DIR", root / "outputs"))
    return data, outputs
