"""
Comparación multi-plataforma a partir de filas JSONL del scrape (ancla Rappi).

- Rappi vs Uber Eats (campos de nivel superior: matched_products, counts, …).
- Rappi vs DiDi Food en `rappi_vs_didi_food` cuando existe fila didi_food.

Requiere fila `rappi` por (location_id, chain); Uber y DiDi son opcionales pero
al menos una debe existir para generar un bloque.
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
    elif plat in ("uber_eats", "didi_food"):
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


def _delivery_block_didi(row: dict[str, Any]) -> dict[str, Any]:
    """DiDi puede no exponer fee/tiempo en la fila scrape aún; deja campos listos."""
    fee_raw = row.get("store_delivery_fee") or row.get("delivery_fee_raw")
    time_raw = row.get("store_delivery_time") or row.get("delivery_eta_raw")
    return {
        "fee_raw": fee_raw,
        "time_raw": time_raw,
        "fee_mxn": parse_delivery_fee_mxn(fee_raw),
        "time_minutes": parse_delivery_minutes(time_raw),
    }


def match_rappi_against_platform(
    rappi_items: list[dict[str, Any]],
    other_items: list[dict[str, Any]],
    other_platform: str,
    *,
    similar_threshold: float = 0.9,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Empareja menú Rappi con uber_eats o didi_food. other_platform: 'uber_eats' | 'didi_food'."""
    if other_platform not in ("uber_eats", "didi_food"):
        raise ValueError(f"other_platform: {other_platform}")
    delta_key = (
        "delta_uber_minus_rappi_mxn"
        if other_platform == "uber_eats"
        else "delta_didi_food_minus_rappi_mxn"
    )
    used_other: set[int] = set()
    matched_rappi: set[int] = set()
    matches: list[dict[str, Any]] = []

    for i, rp in enumerate(rappi_items):
        rname = rp["name"]
        rprice = rp.get("price_mxn")
        best_j: int | None = None
        best_sim = -1.0
        best_dist = float("inf")

        for j, op in enumerate(other_items):
            if j in used_other:
                continue
            sim = name_similarity(rname, op["name"])
            if sim < similar_threshold:
                continue
            oprice = op.get("price_mxn")
            if rprice is not None and oprice is not None:
                dist = abs(rprice - oprice)
            else:
                dist = float("inf")

            if sim > best_sim or (sim == best_sim and dist < best_dist):
                best_sim = sim
                best_j = j
                best_dist = dist

        if best_j is not None:
            used_other.add(best_j)
            matched_rappi.add(i)
            op = other_items[best_j]
            ur, opx = rprice, op.get("price_mxn")
            delta = None
            if ur is not None and opx is not None:
                delta = round(opx - ur, 2)
            pct = None
            if ur and ur > 0 and opx is not None:
                pct = round(100.0 * (opx - ur) / ur, 2)
            matches.append(
                {
                    "match_type": (
                        "exact"
                        if normalize_product_name(rname) == normalize_product_name(op["name"])
                        else "similar"
                    ),
                    "similarity": round(best_sim, 4),
                    "rappi": {"name": rname, "price_mxn": rprice, "price_raw": rp.get("price_raw")},
                    other_platform: {
                        "name": op["name"],
                        "price_mxn": op.get("price_mxn"),
                        "price_raw": op.get("price_raw"),
                    },
                    delta_key: delta,
                    "pct_diff_vs_rappi": pct,
                }
            )

    rappi_only = [rappi_items[k] for k in range(len(rappi_items)) if k not in matched_rappi]
    other_only = [other_items[j] for j in range(len(other_items)) if j not in used_other]
    return matches, rappi_only, other_only


def match_products_cross_platform(
    rappi_items: list[dict[str, Any]],
    uber_items: list[dict[str, Any]],
    *,
    similar_threshold: float = 0.9,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Devuelve (matches, rappi_solo, uber_solo). Compatibilidad; usa match_rappi_against_platform."""
    return match_rappi_against_platform(
        rappi_items, uber_items, "uber_eats", similar_threshold=similar_threshold
    )


def _triple_matched_products(
    matches_ru: list[dict[str, Any]],
    matches_rd: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Intersección de matches Rappi–Uber y Rappi–DiDi (mismo nombre Rappi normalizado)."""
    ru_by_nr: dict[str, dict[str, Any]] = {}
    for m in matches_ru:
        nr = normalize_product_name(m["rappi"]["name"])
        ru_by_nr[nr] = m
    triple: list[dict[str, Any]] = []
    for m in matches_rd:
        nr = normalize_product_name(m["rappi"]["name"])
        if nr not in ru_by_nr:
            continue
        a = ru_by_nr[nr]
        triple.append(
            {
                "rappi": a["rappi"],
                "uber_eats": a.get("uber_eats"),
                "didi_food": m.get("didi_food"),
                "similarity_rappi_uber": a.get("similarity"),
                "similarity_rappi_didi": m.get("similarity"),
                "delta_uber_minus_rappi_mxn": a.get("delta_uber_minus_rappi_mxn"),
                "delta_didi_food_minus_rappi_mxn": m.get("delta_didi_food_minus_rappi_mxn"),
            }
        )
    return triple


def _infer_chain_from_uber_row(row: dict[str, Any]) -> str:
    """Fallback para scrapes viejos sin campo chain en Uber Eats."""
    u = (row.get("url") or row.get("final_url") or "").lower()
    if "mcdonald" in u or "mc-donald" in u:
        return "McDonald's"
    if "burger" in u and "king" in u:
        return "Burger King"
    if "starbucks" in u:
        return "Starbucks"
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
        if plat not in ("rappi", "uber_eats", "didi_food"):
            continue
        if row.get("status") == "error":
            continue
        loc = str(row.get("location_id") or "")
        chain = str(row.get("chain") or "").strip()
        if plat in ("uber_eats", "didi_food") and not chain:
            chain = _infer_chain_from_uber_row(row)
        if not loc or not chain:
            continue
        key = (loc, chain)
        by_key.setdefault(key, {})
        by_key[key][str(plat)] = row

    blocks: list[dict[str, Any]] = []
    for (loc_id, chain), sides in sorted(by_key.items()):
        rr = sides.get("rappi")
        if not rr:
            continue
        ur = sides.get("uber_eats")
        dr = sides.get("didi_food")
        if not ur and not dr:
            continue

        r_items = extract_flat_products(rr)

        if ur:
            u_items = extract_flat_products(ur)
            matches_ru, r_only_ru, u_only = match_rappi_against_platform(
                r_items, u_items, "uber_eats", similar_threshold=similar_threshold
            )
        else:
            matches_ru, r_only_ru, u_only = [], list(r_items), []

        rappi_vs_didi: dict[str, Any] | None = None
        if dr:
            d_items = extract_flat_products(dr)
            matches_rd, r_only_rd, d_only = match_rappi_against_platform(
                r_items, d_items, "didi_food", similar_threshold=similar_threshold
            )
            rappi_vs_didi = {
                "matched_products": matches_rd,
                "rappi_only_products": r_only_rd,
                "didi_food_only_products": d_only,
                "counts": {
                    "matched": len(matches_rd),
                    "rappi_only": len(r_only_rd),
                    "didi_food_only": len(d_only),
                    "rappi_total": len(r_items),
                    "didi_food_total": len(d_items),
                },
            }

        d_r = _delivery_block_rappi(rr)
        d_u = _delivery_block_uber(ur) if ur else None
        d_d = _delivery_block_didi(dr) if dr else None

        dt_u = None
        df_u = None
        if ur and d_r.get("time_minutes") is not None and d_u and d_u.get("time_minutes") is not None:
            dt_u = d_u["time_minutes"] - d_r["time_minutes"]
        if ur and d_r.get("fee_mxn") is not None and d_u and d_u.get("fee_mxn") is not None:
            df_u = round(d_u["fee_mxn"] - d_r["fee_mxn"], 2)

        dt_d = None
        df_d = None
        if dr and d_r.get("time_minutes") is not None and d_d and d_d.get("time_minutes") is not None:
            dt_d = d_d["time_minutes"] - d_r["time_minutes"]
        if dr and d_r.get("fee_mxn") is not None and d_d and d_d.get("fee_mxn") is not None:
            df_d = round(d_d["fee_mxn"] - d_r["fee_mxn"], 2)

        delivery_comparison: dict[str, Any] = {
            "rappi": d_r,
            "uber_eats": d_u,
            "didi_food": d_d,
            "delta_time_minutes_uber_minus_rappi": dt_u,
            "delta_fee_mxn_uber_minus_rappi": df_u,
            "delta_time_minutes_didi_food_minus_rappi": dt_d,
            "delta_fee_mxn_didi_food_minus_rappi": df_d,
        }

        platforms_present = [p for p in ("rappi", "uber_eats", "didi_food") if sides.get(p)]
        uber_total = len(extract_flat_products(ur)) if ur else 0
        triple_rows: list[dict[str, Any]] = []
        if ur and dr:
            triple_rows = _triple_matched_products(matches_ru, matches_rd)

        blocks.append(
            {
                "location_id": loc_id,
                "chain": chain,
                "platforms_present": platforms_present,
                "delivery_comparison": delivery_comparison,
                "matched_products": matches_ru,
                "rappi_only_products": r_only_ru,
                "uber_eats_only_products": u_only,
                "counts": {
                    "matched": len(matches_ru),
                    "rappi_only": len(r_only_ru),
                    "uber_only": len(u_only),
                    "rappi_total": len(r_items),
                    "uber_total": uber_total,
                },
                "rappi_vs_didi_food": rappi_vs_didi,
                "triple_matched_products": triple_rows,
                "counts_triple": {"matched_three_platforms": len(triple_rows)},
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "similarity_threshold": similar_threshold,
        "comparison_scope": "rappi_anchored_multi_platform",
        "platforms": ["rappi", "uber_eats", "didi_food"],
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
        output_path = paths.outputs_exports / f"rappi_uber_didi_comparison_{stamp}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
