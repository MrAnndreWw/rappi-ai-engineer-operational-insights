from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

PlatformId = Literal["rappi", "uber_eats", "didi_food"]


class OfferSnapshot(BaseModel):
    observed_at: datetime
    platform: PlatformId
    location_id: str
    reference_product_id: str | None = None
    product_name_raw: str | None = None
    store_name: str | None = None
    product_price: float | None = None
    delivery_fee: float | None = None
    service_fee: float | None = None
    estimated_delivery_minutes: int | None = None
    active_discounts: str | None = None
    availability: bool | None = None
    total_checkout_price: float | None = None
    currency: str = "MXN"
    source_url: str | None = None
