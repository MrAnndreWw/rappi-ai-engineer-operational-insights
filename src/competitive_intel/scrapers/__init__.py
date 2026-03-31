"""Scrapers: flujos Playwright en `flows` (`FLOW_REGISTRY`)."""

from __future__ import annotations

from typing import Any

__all__ = ["FLOW_REGISTRY"]


def __getattr__(name: str) -> Any:
    if name == "FLOW_REGISTRY":
        from competitive_intel.scrapers.flows import FLOW_REGISTRY as reg

        return reg
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
