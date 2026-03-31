from __future__ import annotations

from typing import Any

from competitive_intel.scrapers.base import BasePlatformScraper


class DiDiFoodScraper(BasePlatformScraper):
    platform_id = "didi_food"

    def scrape_location(self, location: dict[str, Any], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError
