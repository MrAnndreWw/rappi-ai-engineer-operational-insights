"""
Resume un export `rappi_uber_didi_comparison_*.json` en métricas para informe de insights.

Genera un JSON de resumen + figuras PNG junto al archivo de entrada (mismo directorio).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


def _safe_mean(xs: list[float]) -> float | None:
    return float(mean(xs)) if xs else None


def _safe_median(xs: list[float]) -> float | None:
    return float(median(xs)) if xs else None


PROMO_PATTERNS = [
    ("oferta_gasto_minimo", re.compile(r"oferta|ahorra|gasta\s*\$", re.I)),
    ("percent_in_name", re.compile(r"-\s*\d+\s*%|\d+\s*%\s*off", re.I)),
    ("multibuy", re.compile(r"\b\d+\s*[xX]\s*\d+\b|2\s*x\s*1|3\s*x\s*2", re.I)),
    ("gratis_en_precio", re.compile(r"gratis|free\b", re.I)),
]


def _scan_promo_signals(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for label, rx in PROMO_PATTERNS:
        if rx.search(text):
            found.append(label)
    return found


def _collect_promo_from_products(products: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for p in products:
        for part in (p.get("price_raw"), p.get("name")):
            for sig in _scan_promo_signals(str(part) if part else None):
                counts[sig] += 1
    return dict(counts)


def _add_promo_counts(dst: defaultdict[str, int], src: dict[str, int]) -> None:
    for k, v in src.items():
        dst[k] += v


@dataclass
class ComparisonAgg:
    location_id: str
    chain: str
    uber_matched_deltas: list[float] = field(default_factory=list)
    uber_matched_pct: list[float] = field(default_factory=list)
    didi_matched_deltas: list[float] = field(default_factory=list)
    didi_matched_pct: list[float] = field(default_factory=list)
    delta_time_uber: list[float] = field(default_factory=list)
    delta_time_didi: list[float] = field(default_factory=list)
    fee_rappi: list[float] = field(default_factory=list)
    fee_uber: list[float] = field(default_factory=list)
    fee_didi: list[float] = field(default_factory=list)
    time_rappi: list[float] = field(default_factory=list)
    time_uber: list[float] = field(default_factory=list)
    time_didi: list[float] = field(default_factory=list)


def _accumulate_comparison(row: dict[str, Any], bucket: ComparisonAgg) -> None:
    dc = row.get("delivery_comparison") or {}
    for plat, key in (
        ("rappi", "fee_mxn"),
        ("uber_eats", "fee_mxn"),
        ("didi_food", "fee_mxn"),
    ):
        b = dc.get(plat) or {}
        v = b.get(key)
        if v is not None:
            if plat == "rappi":
                bucket.fee_rappi.append(float(v))
            elif plat == "uber_eats":
                bucket.fee_uber.append(float(v))
            else:
                bucket.fee_didi.append(float(v))
    for plat, lst in (
        ("rappi", bucket.time_rappi),
        ("uber_eats", bucket.time_uber),
        ("didi_food", bucket.time_didi),
    ):
        b = dc.get(plat) or {}
        t = b.get("time_minutes")
        if t is not None:
            lst.append(float(t))
    dt = dc.get("delta_time_minutes_uber_minus_rappi")
    if dt is not None:
        bucket.delta_time_uber.append(float(dt))
    dt2 = dc.get("delta_time_minutes_didi_food_minus_rappi")
    if dt2 is not None:
        bucket.delta_time_didi.append(float(dt2))

    for m in row.get("matched_products") or []:
        d = m.get("delta_uber_minus_rappi_mxn")
        if d is not None:
            bucket.uber_matched_deltas.append(float(d))
        p = m.get("pct_diff_vs_rappi")
        if p is not None:
            bucket.uber_matched_pct.append(float(p))

    rv = row.get("rappi_vs_didi_food")
    if isinstance(rv, dict):
        for m in rv.get("matched_products") or []:
            d = m.get("delta_didi_food_minus_rappi_mxn")
            if d is not None:
                bucket.didi_matched_deltas.append(float(d))
            p = m.get("pct_diff_vs_rappi")
            if p is not None:
                bucket.didi_matched_pct.append(float(p))


def _classify_rappi_vs_competitor(mean_delta_comp_minus_rappi: float | None) -> str:
    """delta > 0 => competidor más caro que Rappi (Rappi más barato)."""
    if mean_delta_comp_minus_rappi is None:
        return "sin_datos"
    if mean_delta_comp_minus_rappi > 1.0:
        return "rappi_mas_barato"
    if mean_delta_comp_minus_rappi < -1.0:
        return "rappi_mas_caro"
    return "similar"


def build_summary(data: dict[str, Any], source_path: Path) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = data.get("comparisons") or []
    by_loc: dict[str, list[ComparisonAgg]] = defaultdict(list)
    aggs: list[ComparisonAgg] = []

    promo_rappi: dict[str, int] = defaultdict(int)
    promo_uber: dict[str, int] = defaultdict(int)
    promo_didi: dict[str, int] = defaultdict(int)

    for c in comparisons:
        loc = str(c.get("location_id") or "")
        chain = str(c.get("chain") or "")
        agg = ComparisonAgg(location_id=loc, chain=chain)
        _accumulate_comparison(c, agg)
        aggs.append(agg)
        by_loc[loc].append(agg)

        for m in c.get("matched_products") or []:
            pr = m.get("rappi") or {}
            pu = m.get("uber_eats") or {}
            for sig in _scan_promo_signals(str(pr.get("price_raw") or "")):
                promo_rappi[sig] += 1
            for sig in _scan_promo_signals(str(pr.get("name") or "")):
                promo_rappi[sig] += 1
            for sig in _scan_promo_signals(str(pu.get("price_raw") or "")):
                promo_uber[sig] += 1
            for sig in _scan_promo_signals(str(pu.get("name") or "")):
                promo_uber[sig] += 1
        for p in c.get("rappi_only_products") or []:
            _add_promo_counts(promo_rappi, _collect_promo_from_products([p]))
        for p in c.get("uber_eats_only_products") or []:
            _add_promo_counts(promo_uber, _collect_promo_from_products([p]))
        rv = c.get("rappi_vs_didi_food")
        if isinstance(rv, dict):
            for m in rv.get("matched_products") or []:
                pd = m.get("didi_food") or {}
                for sig in _scan_promo_signals(str(pd.get("price_raw") or "")):
                    promo_didi[sig] += 1
                for sig in _scan_promo_signals(str(pd.get("name") or "")):
                    promo_didi[sig] += 1
            for p in rv.get("didi_only_products") or []:
                _add_promo_counts(promo_didi, _collect_promo_from_products([p]))

    all_uber_delta = [d for a in aggs for d in a.uber_matched_deltas]
    all_didi_delta = [d for a in aggs for d in a.didi_matched_deltas]

    global_mean_uber = _safe_mean(all_uber_delta)
    global_mean_didi = _safe_mean(all_didi_delta)

    per_cell: list[dict[str, Any]] = []
    for a in aggs:
        m_uber = _safe_mean(a.uber_matched_deltas)
        m_didi = _safe_mean(a.didi_matched_deltas)
        per_cell.append(
            {
                "location_id": a.location_id,
                "chain": a.chain,
                "price_vs_uber": {
                    "mean_delta_mxn_uber_minus_rappi": m_uber,
                    "median_delta_mxn": _safe_median(a.uber_matched_deltas),
                    "n_matched_products": len(a.uber_matched_deltas),
                    "clasificacion_rappi": "sin_datos",
                },
                "price_vs_didi": {
                    "mean_delta_mxn_didi_minus_rappi": m_didi,
                    "n_matched_products": len(a.didi_matched_deltas),
                    "clasificacion_rappi": "sin_datos",
                },
                "delivery": {
                    "delta_time_uber_minus_rappi_min": a.delta_time_uber[0] if a.delta_time_uber else None,
                    "delta_time_didi_minus_rappi_min": a.delta_time_didi[0] if a.delta_time_didi else None,
                    "rappi_fee_mxn": a.fee_rappi[0] if a.fee_rappi else None,
                    "uber_fee_mxn": a.fee_uber[0] if a.fee_uber else None,
                    "didi_fee_mxn": a.fee_didi[0] if a.fee_didi else None,
                    "rappi_time_min": a.time_rappi[0] if a.time_rappi else None,
                    "uber_time_min": a.time_uber[0] if a.time_uber else None,
                    "didi_time_min": a.time_didi[0] if a.time_didi else None,
                },
            }
        )

    for pc in per_cell:
        m_u = pc["price_vs_uber"].get("mean_delta_mxn_uber_minus_rappi")
        if m_u is not None:
            pc["price_vs_uber"]["clasificacion_rappi"] = _classify_rappi_vs_competitor(m_u)
        m_d = pc["price_vs_didi"].get("mean_delta_mxn_didi_minus_rappi")
        if m_d is not None:
            pc["price_vs_didi"]["clasificacion_rappi"] = _classify_rappi_vs_competitor(m_d)

    geo_rows: list[dict[str, Any]] = []
    for loc, cells in sorted(by_loc.items()):
        ud = [d for x in cells for d in x.uber_matched_deltas]
        geo_rows.append(
            {
                "location_id": loc,
                "n_chains": len(cells),
                "mean_delta_uber_minus_rappi_mxn": _safe_mean(ud),
                "median_delta_uber_minus_rappi_mxn": _safe_median(ud),
                "clasificacion_precio_uber_agrupada": _classify_rappi_vs_competitor(_safe_mean(ud) if ud else None),
            }
        )

    variability = {
        "across_locations": {
            "mean_delta_uber_by_location": [g["mean_delta_uber_minus_rappi_mxn"] for g in geo_rows if g["mean_delta_uber_minus_rappi_mxn"] is not None],
            "stdev_mean_delta_mxn": None,
        }
    }
    vals = [float(x) for x in variability["across_locations"]["mean_delta_uber_by_location"]]
    if len(vals) > 1:
        m = mean(vals)
        variability["across_locations"]["stdev_mean_delta_mxn"] = round(
            (sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5, 4
        )

    summary: dict[str, Any] = {
        "generated_at_insights": datetime.now(timezone.utc).isoformat(),
        "source_export": str(source_path.resolve()),
        "source_metadata": {
            "generated_at": data.get("generated_at"),
            "similarity_threshold": data.get("similarity_threshold"),
            "comparison_scope": data.get("comparison_scope"),
            "platforms": data.get("platforms"),
            "n_comparison_blocks": len(comparisons),
        },
        "comparative_analysis": {
            "price_positioning": {
                "uber_eats": {
                    "global_mean_delta_mxn_uber_minus_rappi": global_mean_uber,
                    "global_median_delta_mxn": _safe_median(all_uber_delta),
                    "n_matched_price_pairs": len(all_uber_delta),
                    "interpretacion": _interpret_price_global(global_mean_uber, "Uber Eats"),
                },
                "didi_food": {
                    "global_mean_delta_mxn_didi_minus_rappi": global_mean_didi,
                    "global_median_delta_mxn": _safe_median(all_didi_delta),
                    "n_matched_price_pairs": len(all_didi_delta),
                    "interpretacion": _interpret_price_global(global_mean_didi, "DiDi Food"),
                },
            },
            "operational_delivery": {
                "notas": "Tiempos son los capturados en tienda (ETA declarada en UI), no medición real.",
                "por_bloque": [
                    {
                        "location_id": a.location_id,
                        "chain": a.chain,
                        "delta_time_minutes_uber_minus_rappi": a.delta_time_uber[0] if a.delta_time_uber else None,
                        "delta_time_minutes_didi_minus_rappi": a.delta_time_didi[0] if a.delta_time_didi else None,
                        "rappi_time_min": a.time_rappi[0] if a.time_rappi else None,
                        "uber_time_min": a.time_uber[0] if a.time_uber else None,
                        "didi_time_min": a.time_didi[0] if a.time_didi else None,
                    }
                    for a in aggs
                ],
                "resumen": _delivery_summary(aggs),
            },
            "fees": {
                "delivery_fee": {
                    "por_bloque": [
                        {
                            "location_id": a.location_id,
                            "chain": a.chain,
                            "fee_mxn_rappi": a.fee_rappi[0] if a.fee_rappi else None,
                            "fee_mxn_uber": a.fee_uber[0] if a.fee_uber else None,
                            "fee_mxn_didi": a.fee_didi[0] if a.fee_didi else None,
                            "delta_fee_uber_minus_rappi": (a.fee_uber[0] - a.fee_rappi[0])
                            if a.fee_uber and a.fee_rappi
                            else None,
                            "delta_fee_didi_minus_rappi": (a.fee_didi[0] - a.fee_rappi[0])
                            if a.fee_didi and a.fee_rappi
                            else None,
                        }
                        for a in aggs
                    ],
                },
                "service_fee": {
                    "disponibilidad_datos": "no_capturado_en_scrape_actual",
                    "detail": "El export de comparación no incluye service fee explícito; solo fee/tiempo de entrega en delivery_comparison.",
                },
            },
            "promotional_signals": {
                "metodo": "Heurística sobre price_raw y nombres de producto (oferta, %, multi‑buy, gratis).",
                "conteos_por_tipo": {
                    "rappi": dict(promo_rappi),
                    "uber_eats": dict(promo_uber),
                    "didi_food": dict(promo_didi),
                },
                "ejemplos_oferta_texto_en_fee_o_precio": _sample_offer_strings(comparisons, limit=12),
            },
            "geographic_variability": {
                "by_location": geo_rows,
                "variability_summary": variability,
            },
        },
        "detalle_por_ubicacion_y_cadena": per_cell,
        "top_5_insights_accionables": [],
        "visualizations": [],
    }

    summary["top_5_insights_accionables"] = _build_top5_insights(
        summary, per_cell, geo_rows, aggs, global_mean_uber, global_mean_didi
    )
    return summary


def _interpret_price_global(mean_delta: float | None, competitor: str) -> str:
    if mean_delta is None:
        return f"Sin pares de precios matched para Rappi vs {competitor}."
    if mean_delta > 1.0:
        return f"En promedio {competitor} cobra más por ítem matched que Rappi (delta ≈ +{mean_delta:.2f} MXN a favor de Rappi)."
    if mean_delta < -1.0:
        return f"En promedio {competitor} cobra menos por ítem matched que Rappi (delta ≈ {mean_delta:.2f} MXN; Rappi más caro)."
    return f"Precios matched similares entre Rappi y {competitor} (delta promedio ≈ {mean_delta:.2f} MXN)."


def _delivery_summary(aggs: list[ComparisonAgg]) -> dict[str, Any]:
    dt_u = [x.delta_time_uber[0] for x in aggs if x.delta_time_uber]
    dt_d = [x.delta_time_didi[0] for x in aggs if x.delta_time_didi]
    return {
        "count_blocks_con_delta_uber": len(dt_u),
        "mean_delta_time_uber_minus_rappi": _safe_mean([float(x) for x in dt_u]),
        "count_blocks_con_delta_didi": len(dt_d),
        "mean_delta_time_didi_minus_rappi": _safe_mean([float(x) for x in dt_d]),
    }


def _sample_offer_strings(comparisons: list[dict[str, Any]], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in comparisons:
        dc = c.get("delivery_comparison") or {}
        for plat in ("rappi", "uber_eats", "didi_food"):
            raw = (dc.get(plat) or {}).get("fee_raw")
            if raw and PROMO_PATTERNS[0][1].search(str(raw)):
                s = str(raw).strip()
                if s not in seen:
                    seen.add(s)
                    out.append(f"{plat}:{s[:120]}")
        for m in c.get("matched_products") or []:
            for _lab, rx in PROMO_PATTERNS:
                for side in ("rappi", "uber_eats"):
                    pr = m.get(side) or {}
                    t = str(pr.get("price_raw") or "")
                    if rx.search(t) and len(out) < limit * 3:
                        s = f"{side}:{t[:100]}"
                        if s not in seen:
                            seen.add(s)
                            out.append(s)
        if len(out) >= limit:
            break
    return out[:limit]


def _build_top5_insights(
    summary: dict[str, Any],
    per_cell: list[dict[str, Any]],
    geo_rows: list[dict[str, Any]],
    aggs: list[ComparisonAgg],
    global_mean_uber: float | None,
    global_mean_didi: float | None,
) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []

    # 1 Global price vs Uber
    if global_mean_uber is not None:
        if global_mean_uber < -1.0:
            insights.append(
                {
                    "finding": f"En el universo de ítems emparejados, Uber Eats es en promedio {-global_mean_uber:.1f} MXN más barato por producto que Rappi.",
                    "impacto": "Riesgo de presión en conversión y percepción de precio en las mismas cadenas y zonas analizadas.",
                    "recomendacion": "Priorizar revisión de precios por categoría (desayunos/combos) y bundles alineados al menú mostrado en Uber; evaluar campañas puntuales en SKU con mayor brecha.",
                }
            )
        elif global_mean_uber > 1.0:
            insights.append(
                {
                    "finding": f"Rappi está en promedio {global_mean_uber:.1f} MXN más barato que Uber Eats en ítems matched.",
                    "impacto": "Ventaja competitiva en ticket de menú visible; útil para mensajería y growth en zonas cubiertas.",
                    "recomendacion": "Destacar precio en campañas locales y proteger SKUs donde la ventaja es mayor; monitorear respuesta de Uber.",
                }
            )

    # 2 Geografía: peor ubicación para Rappi vs Uber
    worst_loc = None
    worst_val = None
    for g in geo_rows:
        m = g.get("mean_delta_uber_minus_rappi_mxn")
        if m is not None and (worst_val is None or m < worst_val):
            worst_val = m
            worst_loc = g["location_id"]
    if worst_loc is not None and worst_val is not None and worst_val < -0.5:
        insights.append(
            {
                "finding": f"La zona «{worst_loc}» concentra la mayor desventaja de precio vs Uber (delta medio uber−rappi ≈ {worst_val:.2f} MXN: Uber más barato).",
                "impacto": "La competitividad no es homogénea: hay zonas donde el posicionamiento relativo es más débil.",
                "recomendacion": f"Profundizar pricing y promos en «{worst_loc}» (y cadenas asociadas en el bloque); considerar fee o incentivos específicos de zona.",
            }
        )

    # 3 Delivery time
    ds = summary["comparative_analysis"]["operational_delivery"]["resumen"]
    mean_dt = ds.get("mean_delta_time_uber_minus_rappi")
    if mean_dt is not None and abs(mean_dt) >= 2.0:
        if mean_dt < 0:
            insights.append(
                {
                    "finding": f"Uber declara en promedio ~{-mean_dt:.0f} min menos de entrega que Rappi en los bloques donde ambos tienen ETA ({ds['count_blocks_con_delta_uber']} casos).",
                    "impacto": "Desventaja operativa percibida en velocidad; afecta elección de plataforma en horarios críticos.",
                    "recomendacion": "Revisar SLAs mostrados (supply, radio, promesas UI) y comunicación de tiempo; alinear expectativa o mejorar cobertura en esas ubicaciones.",
                }
            )
        else:
            insights.append(
                {
                    "finding": f"Rappi declara ETA más baja que Uber en promedio (~{mean_dt:.0f} min de diferencia) donde hay datos comparables.",
                    "impacto": "Posible ventaja operativa en la promesa de tiempo.",
                    "recomendacion": "Capitalizar en messaging “más rápido” en esas zonas; validar con datos operativos reales.",
                }
            )

    # 4 Fees
    fee_rows = summary["comparative_analysis"]["fees"]["delivery_fee"]["por_bloque"]
    lower_uber = [r for r in fee_rows if r.get("delta_fee_uber_minus_rappi") is not None and r["delta_fee_uber_minus_rappi"] < -0.01]
    if lower_uber:
        insights.append(
            {
                "finding": f"En {len(lower_uber)} bloque(s) el fee de entrega mostrado en Uber es menor que en Rappi.",
                "impacto": "El costo total al checkout puede favorecer al competidor aun con precios de menú similares.",
                "recomendacion": "Modelar fee efectivo al cliente por zona/cadena; evaluar subsidio selectivo o programas de envío gratis acotados.",
            }
        )

    # 5 DiDi
    if global_mean_didi is not None and len(insights) < 5:
        insights.append(
            {
                "finding": f"DiDi Food vs Rappi (ítems matched): delta medio didi−rappi ≈ {global_mean_didi:.2f} MXN.",
                "impacto": "Tercer jugador con dinámica de precio independiente; relevante donde DiDi tiene cobertura fuerte.",
                "recomendacion": "Mantener scrape periódico DiDi y revisar triple-match para detectar desviaciones sistémicas.",
            }
        )

    # 6 Promos / variability filler
    pr = summary["comparative_analysis"]["promotional_signals"]["conteos_por_tipo"]
    uber_off = sum(pr.get("uber_eats", {}).get(k, 0) for k in ("oferta_gasto_minimo", "multibuy"))
    rappi_off = sum(pr.get("rappi", {}).get(k, 0) for k in ("oferta_gasto_minimo", "multibuy"))
    if uber_off > rappi_off + 2 and len(insights) < 5:
        insights.append(
            {
                "finding": f"Más señales heurísticas de promos/multi‑buy en Uber ({uber_off}) que en Rappi ({rappi_off}) en textos analizados.",
                "impacto": "Percepción de mayor agresividad promocional del competidor en la interfaz.",
                "recomendacion": "Auditar paridad de ofertas con marca en ubicaciones clave y visibilidad en listing.",
            }
        )

    std = summary["comparative_analysis"]["geographic_variability"]["variability_summary"]["across_locations"].get(
        "stdev_mean_delta_mxn"
    )
    if std is not None and std >= 3.0 and len(insights) < 5:
        insights.append(
            {
                "finding": f"Alta variabilidad del posicionamiento vs Uber entre zonas (desv. estándar de deltas medios ≈ {std:.2f} MXN).",
                "impacto": "Un solo precio nacional puede dejar zonas sobre o sub competitivas.",
                "recomendacion": "Avanzar a matrices de precio o promos por cluster geográfico basadas en inteligencia competitiva.",
            }
        )

    # Pad to 5 with generic if needed
    while len(insights) < 5:
        insights.append(
            {
                "finding": "Espacio reservado: incorpora un hallazgo manual a partir del detalle en la clave detalle_por_ubicacion_y_cadena.",
                "impacto": "Completa con el contexto de negocio de tu plaza (marcas, temporadas).",
                "recomendacion": "Prioriza 1–2 cadenas con mayor volumen y valida con nuevos scrapes.",
            }
        )

    return insights[:5]


def render_figures(summary: dict[str, Any], stem_prefix: Path) -> list[str]:
    import matplotlib.pyplot as plt

    paths: list[str] = []
    per_loc = summary["comparative_analysis"]["geographic_variability"]["by_location"]
    if not per_loc:

        def _placeholder(name: str, msg: str) -> str:
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.text(0.5, 0.5, msg, ha="center", va="center")
            ax.axis("off")
            p = stem_prefix.parent / f"{stem_prefix.name}_{name}.png"
            fig.savefig(p, dpi=150, bbox_inches="tight")
            plt.close(fig)
            return str(p)

        return [
            _placeholder("fig1_delta_precio_por_zona", "Sin datos geográficos para graficar"),
            _placeholder("fig2_heatmap_precio_zona_cadena", "Sin heatmap: no hay ubicaciones"),
            _placeholder("fig3_fees_entrega_por_bloque", "Sin fees para graficar"),
        ]

    labels = [g["location_id"] for g in per_loc]
    raw_means = [g.get("mean_delta_uber_minus_rappi_mxn") for g in per_loc]
    means = [float(m) if m is not None else 0.0 for m in raw_means]

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.2), 5))
    colors: list[str] = []
    for m in raw_means:
        if m is None:
            colors.append("#95a5a6")
        elif m > 0.5:
            colors.append("#2ecc71")
        elif m < -0.5:
            colors.append("#e74c3c")
        else:
            colors.append("#95a5a6")
    ax.bar(labels, means, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Delta precio medio (Uber − Rappi) por zona\n>0: Uber más caro (Rappi más barato)")
    ax.set_ylabel("MXN (ítems matched)")
    fig.autofmt_xdate()
    plt.tight_layout()
    p1 = stem_prefix.parent / f"{stem_prefix.name}_fig1_delta_precio_por_zona.png"
    fig.savefig(p1, dpi=150, bbox_inches="tight")
    plt.close(fig)
    paths.append(str(p1))

    cells = summary["detalle_por_ubicacion_y_cadena"]
    locs = sorted({c["location_id"] for c in cells})
    chains = sorted({c["chain"] for c in cells})
    if not locs or not chains:
        fig2, ax2 = plt.subplots(figsize=(6, 3))
        ax2.text(0.5, 0.5, "Sin datos para heatmap zona × cadena", ha="center", va="center")
        ax2.axis("off")
        ph = stem_prefix.parent / f"{stem_prefix.name}_fig2_heatmap_precio_zona_cadena.png"
        fig2.savefig(ph, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        paths.append(str(ph))
    else:
        mat = [[float("nan")] * len(locs) for _ in chains]
        for c in cells:
            i = chains.index(c["chain"])
            j = locs.index(c["location_id"])
            m = c["price_vs_uber"].get("mean_delta_mxn_uber_minus_rappi")
            mat[i][j] = m if m is not None else float("nan")

        fig2, ax2 = plt.subplots(figsize=(max(6, len(locs) * 1.3), max(4, len(chains) * 0.6)))
        im = ax2.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-15, vmax=15)
        ax2.set_xticks(range(len(locs)))
        ax2.set_xticklabels(locs, rotation=45, ha="right")
        ax2.set_yticks(range(len(chains)))
        ax2.set_yticklabels(chains)
        ax2.set_title("Heatmap: media (Uber − Rappi) MXN por zona y cadena\nVerde: Uber más caro")
        fig2.colorbar(im, ax=ax2, label="MXN")
        plt.tight_layout()
        pheatmap = stem_prefix.parent / f"{stem_prefix.name}_fig2_heatmap_precio_zona_cadena.png"
        fig2.savefig(pheatmap, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        paths.append(str(pheatmap))

    fee_rows = summary["comparative_analysis"]["fees"]["delivery_fee"]["por_bloque"]
    sample = fee_rows[:20] if fee_rows else []
    if not sample:
        fig3, ax3 = plt.subplots(figsize=(6, 3))
        ax3.text(0.5, 0.5, "Sin filas de fee para graficar", ha="center", va="center")
        ax3.axis("off")
        p3 = stem_prefix.parent / f"{stem_prefix.name}_fig3_fees_entrega_por_bloque.png"
        fig3.savefig(p3, dpi=150, bbox_inches="tight")
        plt.close(fig3)
        paths.append(str(p3))
    else:
        labels_f = [f"{r['location_id']}\n{r['chain'][:12]}" for r in sample]
        fr = [r.get("fee_mxn_rappi") if r.get("fee_mxn_rappi") is not None else 0 for r in sample]
        fu = [r.get("fee_mxn_uber") if r.get("fee_mxn_uber") is not None else 0 for r in sample]
        fd = [r.get("fee_mxn_didi") if r.get("fee_mxn_didi") is not None else 0 for r in sample]

        fig3, ax3 = plt.subplots(figsize=(max(10, len(labels_f) * 0.5), 5))
        x = range(len(labels_f))
        w = 0.25
        ax3.bar([i - w for i in x], fr, width=w, label="Rappi fee", color="#3498db")
        ax3.bar(x, fu, width=w, label="Uber fee", color="#9b59b6")
        ax3.bar([i + w for i in x], fd, width=w, label="DiDi fee", color="#f39c12")
        ax3.set_xticks(list(x))
        ax3.set_xticklabels(labels_f, rotation=55, ha="right", fontsize=7)
        ax3.set_ylabel("Fee entrega (MXN)")
        ax3.set_title("Fees de entrega declarados por bloque (primeros 20)")
        ax3.legend()
        plt.tight_layout()
        p3 = stem_prefix.parent / f"{stem_prefix.name}_fig3_fees_entrega_por_bloque.png"
        fig3.savefig(p3, dpi=150, bbox_inches="tight")
        plt.close(fig3)
        paths.append(str(p3))

    return paths


def run_from_path(input_json: Path) -> Path:
    data = json.loads(input_json.read_text(encoding="utf-8"))
    summary = build_summary(data, input_json)
    stem = input_json.stem
    out_json = input_json.parent / f"{stem}_insights_summary.json"
    prefix = input_json.parent / stem
    summary["visualizations"] = render_figures(summary, prefix)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_json
