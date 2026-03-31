from __future__ import annotations

import json
from pathlib import Path

from competitive_intel.analysis.platform_comparison import (
    build_comparison_payload,
    normalize_product_name,
    parse_delivery_minutes,
    parse_mxn_price,
    run_comparison_export,
)


def test_normalize_product_name() -> None:
    assert normalize_product_name("McFlurry  Oreo") == normalize_product_name("mcflurry oreo")


def test_parse_mxn_price() -> None:
    assert parse_mxn_price("$ 59.00") == 59.0
    assert parse_mxn_price("$169.00") == 169.0


def test_parse_delivery_minutes() -> None:
    assert parse_delivery_minutes("13 min") == 13
    assert parse_delivery_minutes("12 min ") == 12


def test_build_comparison_payload_minimal(tmp_path: Path) -> None:
    jl = tmp_path / "s.jsonl"
    jl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "platform": "rappi",
                        "location_id": "x1",
                        "chain": "TestChain",
                        "status": "ok",
                        "delivery_fee_raw": "Gratis",
                        "delivery_eta_raw": "10 min",
                        "products_sample": [{"name": "Item A", "price_raw": "$ 100.00", "price": 100.0}],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "platform": "uber_eats",
                        "location_id": "x1",
                        "chain": "TestChain",
                        "status": "ok",
                        "store_delivery_fee": "Costo de envío a MXN0",
                        "store_delivery_time": "15 min",
                        "menu_items": [{"name": "Item A", "price_raw": "$110.00"}],
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    from competitive_intel.analysis.platform_comparison import load_scrape_jsonl

    rows = load_scrape_jsonl(jl)
    payload = build_comparison_payload(rows)
    assert len(payload["comparisons"]) == 1
    c0 = payload["comparisons"][0]
    assert c0["delivery_comparison"]["delta_time_minutes_uber_minus_rappi"] == 5
    assert len(c0["matched_products"]) == 1
    assert c0["matched_products"][0]["delta_uber_minus_rappi_mxn"] == 10.0


def test_run_comparison_export_writes_file(tmp_path: Path) -> None:
    f = tmp_path / "scrape_test.jsonl"
    f.write_text(
        json.dumps(
            {
                "platform": "rappi",
                "location_id": "l",
                "chain": "C",
                "status": "ok",
                "products_sample": [{"name": "Item X", "price": 1.0, "price_raw": "$1"}],
                "delivery_eta_raw": "5 min",
                "delivery_fee_raw": "Gratis",
            },
            ensure_ascii=False,
        )
        + "\n"
        + json.dumps(
            {
                "platform": "uber_eats",
                "location_id": "l",
                "chain": "C",
                "status": "ok",
                "menu_items": [{"name": "Item X", "price_raw": "$2.00"}],
                "store_delivery_time": "6 min",
                "store_delivery_fee": "MXN0",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    path = run_comparison_export(input_path=f, output_path=out)
    assert path == out
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["comparisons"] and data["comparisons"][0]["matched_products"]
