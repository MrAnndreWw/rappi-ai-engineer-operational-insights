from __future__ import annotations

from typing import Any


def pick_str(payload: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        if k in payload and payload[k] is not None:
            return str(payload[k])
    return None


def pick_float(payload: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        v = payload.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None
