"""
Comparación Rappi vs Uber Eats a partir de filas JSONL del scrape.

Empareja productos por nombre (exacto normalizado o similitud alta) y contrasta
envío / tiempo cuando ambas plataformas tienen fila para la misma ubicación y cadena.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from competitive_intel.utils.paths import project_paths


def load_scrape_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def normalize_product_name(name: str) -> str:
    s = (name or "").replace("\u00a0", " ").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_product_name(a), normalize_product_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def parse_mxn_price(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("$", "$$"):
        return None
    m = re.search(r"\$\s*([\d,]+\.?\d*)", s)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    m = re.search(r"MXN\s*([\d,.]+)", s, re.I)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    m = re.search(r"([\d,]+\.?\d*)\s*$", s)
    if m and re.search(r"\d", m.group(1)):
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def parse_delivery_minutes(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.search(r"(\d+)\s*min", str(raw), re.I)
    if m:
        return int(m.group(1))
    return None


def parse_delivery_fee_mxn(raw: str | None) -> float | None:
    if not raw:
        return None
    s = str(raw)
    if re.search(r"gratis|free|MXN\s*0\b|MXN0\b|\$\s*0\b", s, re.I):
        return 0.0
    return parse_mxn_price(s)


def _is_junk_uber_item(name: str, price_raw: str | None) -> bool:
    n = (name or "").strip()
    pr = (price_raw or "").strip()
    if len(n) < 2:
        return True
    if re.fullmatch(r"\d+(\.\d+)?", n):
        return True
    if re.match(r"^-\s*\d+\s*%", n):
        return True
    if pr in ("$", "$$") and len(n) < 10:
        return True
    if "elige" in n.lower() and "x" in n.lower() and "$" not in pr:
        return True
    return False


def extract_flat_products(row: dict[str, Any]) -> list[dict[str, Any]]:
    plat = row.get("platform")
    out: list[dict[str, Any]] = []
    if plat == "rappi":
        for p in row.get("products_sample") or []:
            name = str(p.get("name") or "").strip()
            if len(name) < 2:
                continue
            price = p.get("price")
            if price is None:
                price = parse_mxn_price(str(p.get("price_raw") or ""))
            out.append(
                {
                    "name": name,
                    "price_mxn": price,
                    "price_raw": p.get("price_raw"),
                }
            )
    elif plat == "uber_eats":
        for p in row.get("menu_items") or []:
            name = str(p.get("name") or "").strip()
            pr = p.get("price_raw")
            if _is_junk_uber_item(name, str(pr) if pr is not None else None):
                continue
            price = parse_mxn_price(str(pr) if pr is not None else "")
            if price is None:
                continue
            out.append({"name": name, "price_mxn": price, "price_raw": pr})
    return out


def _delivery_block_rappi(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fee_raw": row.get("delivery_fee_raw"),
        "time_raw": row.get("delivery_eta_raw"),
        "fee_mxn": parse_delivery_fee_mxn(row.get("delivery_fee_raw")),
        "time_minutes": parse_delivery_minutes(row.get("delivery_eta_raw")),
    }


def _delivery_block_uber(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fee_raw": row.get("store_delivery_fee"),
        "time_raw": row.get("store_delivery_time"),
        "fee_mxn": parse_delivery_fee_mxn(row.get("store_delivery_fee")),
        "time_minutes": parse_delivery_minutes(row.get("store_delivery_time")),
    }


def match_products_cross_platform(
    rappi_items: list[dict[str, Any]],
    uber_items: list[dict[str, Any]],
    *,
    similar_threshold: float = 0.9,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Devuelve (matches, rappi_solo, uber_solo)."""
    used_uber: set[int] = set()
    matched_rappi: set[int] = set()
    matches: list[dict[str, Any]] = []

    for i, rp in enumerate(rappi_items):
        rname = rp["name"]
        rprice = rp.get("price_mxn")
        best_j: int | None = None
        best_sim = -1.0
        best_dist = float("inf")

        for j, up in enumerate(uber_items):
            if j in used_uber:
                continue
            sim = name_similarity(rname, up["name"])
            if sim < similar_threshold:
                continue
            uprice = up.get("price_mxn")
            if rprice is not None and uprice is not None:
                dist = abs(rprice - uprice)
            else:
                dist = float("inf")

            if sim > best_sim or (sim == best_sim and dist < best_dist):
                best_sim = sim
                best_j = j
                best_dist = dist

        if best_j is not None:
            used_uber.add(best_j)
            matched_rappi.add(i)
            up = uber_items[best_j]
            ur, upx = rprice, up.get("price_mxn")
            delta = None
            if ur is not None and upx is not None:
                delta = round(upx - ur, 2)
            pct = None
            if ur and ur > 0 and upx is not None:
                pct = round(100.0 * (upx - ur) / ur, 2)
            matches.append(
                {
                    "match_type": "exact" if normalize_product_name(rname) == normalize_product_name(up["name"]) else "similar",
                    "similarity": round(best_sim, 4),
                    "rappi": {"name": rname, "price_mxn": rprice, "price_raw": rp.get("price_raw")},
                    "uber_eats": {"name": up["name"], "price_mxn": up.get("price_mxn"), "price_raw": up.get("price_raw")},
                    "delta_uber_minus_rappi_mxn": delta,
                    "pct_diff_vs_rappi": pct,
                }
            )

    rappi_only = [rappi_items[k] for k in range(len(rappi_items)) if k not in matched_rappi]
    uber_only = [uber_items[j] for j in range(len(uber_items)) if j not in used_uber]
    return matches, rappi_only, uber_only


def _infer_chain_from_uber_row(row: dict[str, Any]) -> str:
    """Fallback para scrapes viejos sin campo chain en Uber Eats."""
    u = (row.get("url") or row.get("final_url") or "").lower()
    if "mcdonald" in u or "mc-donald" in u:
        return "McDonald's"
    if "burger" in u and "king" in u:
        return "Burger King"
    if "kfc" in u:
        return "KFC"
    if "subway" in u:
        return "Subway"
    if "little" in u and "caesar" in u:
        return "Little Caesars"
    return ""


def build_comparison_payload(
    rows: list[dict[str, Any]],
    *,
    similar_threshold: float = 0.9,
) -> dict[str, Any]:
    by_key: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        plat = row.get("platform")
        if plat not in ("rappi", "uber_eats"):
            continue
        if row.get("status") == "error":
            continue
        loc = str(row.get("location_id") or "")
        chain = str(row.get("chain") or "").strip()
        if plat == "uber_eats" and not chain:
            chain = _infer_chain_from_uber_row(row)
        if not loc or not chain:
            continue
        key = (loc, chain)
        by_key.setdefault(key, {})
        by_key[key][str(plat)] = row

    blocks: list[dict[str, Any]] = []
    for (loc_id, chain), sides in sorted(by_key.items()):
        rr = sides.get("rappi")
        ur = sides.get("uber_eats")
        if not rr or not ur:
            continue

        r_items = extract_flat_products(rr)
        u_items = extract_flat_products(ur)
        matches, r_only, u_only = match_products_cross_platform(
            r_items, u_items, similar_threshold=similar_threshold
        )

        dr = _delivery_block_rappi(rr)
        du = _delivery_block_uber(ur)
        dt = None
        if dr.get("time_minutes") is not None and du.get("time_minutes") is not None:
            dt = du["time_minutes"] - dr["time_minutes"]
        df = None
        if dr.get("fee_mxn") is not None and du.get("fee_mxn") is not None:
            df = round(du["fee_mxn"] - dr["fee_mxn"], 2)

        blocks.append(
            {
                "location_id": loc_id,
                "chain": chain,
                "delivery_comparison": {
                    "rappi": dr,
                    "uber_eats": du,
                    "delta_time_minutes_uber_minus_rappi": dt,
                    "delta_fee_mxn_uber_minus_rappi": df,
                },
                "matched_products": matches,
                "rappi_only_products": r_only,
                "uber_eats_only_products": u_only,
                "counts": {
                    "matched": len(matches),
                    "rappi_only": len(r_only),
                    "uber_only": len(u_only),
                    "rappi_total": len(r_items),
                    "uber_total": len(u_items),
                },
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "similarity_threshold": similar_threshold,
        "comparisons": blocks,
    }


def run_comparison_export(
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    similar_threshold: float = 0.9,
) -> Path:
    paths = project_paths()
    paths.outputs_exports.mkdir(parents=True, exist_ok=True)

    if input_path is None:
        raw_dir = paths.data_raw
        if not raw_dir.is_dir():
            raise FileNotFoundError(f"No existe data/raw: {raw_dir}")
        candidates = sorted(raw_dir.glob("scrape_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise FileNotFoundError(f"No hay scrape_*.jsonl en {raw_dir}")
        input_path = candidates[0]

    rows = load_scrape_jsonl(input_path)
    payload = build_comparison_payload(rows, similar_threshold=similar_threshold)
    payload["source_scrape_file"] = str(input_path.resolve())

    if output_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = paths.outputs_exports / f"rappi_uber_comparison_{stamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
