from __future__ import annotations

import random
import time
from typing import Any


def sleep_scrape_delay(settings: dict[str, Any], *, for_rappi: bool = False) -> None:
    s = settings.get("scraping") or {}
    if for_rappi:
        rcfg = s.get("rappi") or {}
        if rcfg.get("delay_seconds") is not None:
            base = float(rcfg["delay_seconds"])
            jitter = float(rcfg.get("delay_jitter_seconds", s.get("delay_jitter_seconds", 1)))
            time.sleep(max(0, base + random.uniform(0, jitter)))
            return
    base = float(s.get("delay_seconds", 2))
    jitter = float(s.get("delay_jitter_seconds", 1))
    time.sleep(max(0, base + random.uniform(0, jitter)))


def sleep_between_locations(settings: dict[str, Any]) -> None:
    s = settings.get("scraping") or {}
    extra = float(s.get("between_locations_seconds", 3))
    jitter = float(s.get("delay_jitter_seconds", 1))
    time.sleep(max(0, extra + random.uniform(0, jitter)))


def sleep_between_platforms(settings: dict[str, Any]) -> None:
    s = settings.get("scraping") or {}
    extra = float(s.get("between_platforms_seconds", 5))
    jitter = float(s.get("delay_jitter_seconds", 1))
    time.sleep(max(0, extra + random.uniform(0, jitter)))


def sleep_between_rappi_chains(settings: dict[str, Any]) -> None:
    s = settings.get("scraping") or {}
    cfg = s.get("rappi") or {}
    extra = float(cfg.get("between_chains_seconds", 5))
    jitter = float(s.get("delay_jitter_seconds", 1))
    time.sleep(max(0, extra + random.uniform(0, jitter)))


def sleep_between_uber_eats_chains(settings: dict[str, Any]) -> None:
    s = settings.get("scraping") or {}
    cfg = s.get("uber_eats") or {}
    extra = float(cfg.get("between_chains_seconds", 5))
    jitter = float(s.get("delay_jitter_seconds", 1))
    time.sleep(max(0, extra + random.uniform(0, jitter)))


def sleep_between_didi_chains(settings: dict[str, Any]) -> None:
    s = settings.get("scraping") or {}
    cfg = s.get("didi_food") or {}
    extra = float(cfg.get("between_chains_seconds", 5))
    jitter = float(s.get("delay_jitter_seconds", 1))
    time.sleep(max(0, extra + random.uniform(0, jitter)))
