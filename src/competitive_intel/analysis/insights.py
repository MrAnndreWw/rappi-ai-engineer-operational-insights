from __future__ import annotations

from pathlib import Path
from typing import Any


def load_normalized_table(path: Path) -> Any:
    import pandas as pd

    if path.is_dir():
        raise ValueError("Especifica un archivo JSONL o CSV.")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        return pd.read_json(path, lines=True)
    return pd.read_json(path)


def top_actionable_insights(df: Any, *, n: int = 5) -> list[dict[str, Any]]:
    _ = df
    return [
        {"rank": i + 1, "title": "Pendiente", "detail": "Sin datos normalizados aún."}
        for i in range(n)
    ]
