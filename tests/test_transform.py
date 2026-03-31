from datetime import datetime, timezone

from competitive_intel.transform.canonical import raw_rows_to_snapshots


def test_raw_rows_to_snapshots_filters_unknown_platform():
    rows = [
        {
            "platform": "rappi",
            "location_id": "x",
            "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "product_price": 99.0,
        },
        {"platform": "other", "location_id": "y"},
    ]
    snaps = raw_rows_to_snapshots(rows)
    assert len(snaps) == 1
    assert snaps[0].platform == "rappi"
    assert snaps[0].product_price == 99.0
