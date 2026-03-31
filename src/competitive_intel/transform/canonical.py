from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from competitive_intel.models.schemas import OfferSnapshot, PlatformId


def raw_rows_to_snapshots(rows: list[dict[str, Any]]) -> list[OfferSnapshot]:
    out: list[OfferSnapshot] = []
    for row in rows:
        platform = row.get("platform")
        if platform not in ("rappi", "uber_eats", "didi_food"):
            continue
        out.append(
            OfferSnapshot(
                observed_at=row.get("observed_at") or datetime.now(timezone.utc),
                platform=cast(PlatformId, platform),
                location_id=str(row["location_id"]),
                reference_product_id=row.get("reference_product_id"),
                product_name_raw=row.get("product_name_raw"),
                store_name=row.get("store_name"),
                product_price=row.get("product_price"),
                delivery_fee=row.get("delivery_fee"),
                service_fee=row.get("service_fee"),
                estimated_delivery_minutes=row.get("estimated_delivery_minutes"),
                active_discounts=row.get("active_discounts"),
                availability=row.get("availability"),
                total_checkout_price=row.get("total_checkout_price"),
                currency=str(row.get("currency") or "MXN"),
                source_url=row.get("source_url"),
            )
        )
    return out
