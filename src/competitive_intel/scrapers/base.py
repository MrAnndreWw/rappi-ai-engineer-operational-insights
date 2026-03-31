from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePlatformScraper(ABC):
    platform_id: str

    @abstractmethod
    def scrape_location(self, location: dict[str, Any], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pass
