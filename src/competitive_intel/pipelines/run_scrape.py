from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from competitive_intel.config import load_settings, resolve_data_paths
from competitive_intel.scrapers.flows import FLOW_REGISTRY
from competitive_intel.scrapers.throttle import sleep_between_locations, sleep_between_platforms

_LOG = logging.getLogger("scrape")


def _configure_scrape_logging(*, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    # Menos ruido de librerías
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def _config_dir(config_dir: Path | None) -> Path:
    return config_dir or Path(__file__).resolve().parents[3] / "config"


def _load_locations(base: Path) -> tuple[Path, list[dict[str, Any]]]:
    loc_file = base / "locations.yaml"
    if not loc_file.is_file():
        loc_file = base / "locations.template.yaml"
    locations: list[dict[str, Any]] = []
    if loc_file.is_file():
        with loc_file.open(encoding="utf-8") as f:
            loc_data = yaml.safe_load(f) or {}
        locations = list(loc_data.get("locations") or [])
    return loc_file, locations


def _load_products(base: Path) -> list[dict[str, Any]]:
    path = base / "reference_products.yaml"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("reference_products") or [])


def run_scrape_pipeline(
    *,
    config_dir: Path | None = None,
    dry_run: bool = False,
    platform: str | None = None,
    headed: bool = False,
    verbose: bool = False,
    rappi_dump_pages: bool = False,
    max_locations: int | None = None,
) -> int:
    _configure_scrape_logging(verbose=verbose)
    settings = load_settings(config_dir)
    if rappi_dump_pages:
        scraping = settings.setdefault("scraping", {})
        rcfg = scraping.setdefault("rappi", {})
        rcfg["debug_page_dumps"] = True
        _LOG.debug("Rappi: volcado de página activo (HTML/PNG/meta en data/debug/rappi_pages o debug_page_dir)")
    base = _config_dir(config_dir)
    loc_file, locations = _load_locations(base)
    products = _load_products(base)
    auth_file = base / "auth.json"

    data_dir, outputs_dir = resolve_data_paths()
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed"
    exports_dir = outputs_dir / "exports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print("Dry-run OK.")
        print(f"  locations file: {loc_file}")
        print(f"  locations: {len(locations)}")
        print(f"  products ref: {len(products)}")
        print(f"  platforms: {settings.get('platforms', {}).get('enabled', [])}")
        return 0

    if not locations:
        print("No hay ubicaciones: crea config/locations.yaml (copia desde locations.template.yaml).")
        return 1

    if max_locations is not None and max_locations > 0:
        locations = locations[:max_locations]
        _LOG.debug("Limitando ubicaciones a max_locations=%s", max_locations)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Falta Playwright: pip install playwright && playwright install chromium")
        return 1

    enabled = list(settings.get("platforms", {}).get("enabled") or [])
    if platform:
        if platform not in FLOW_REGISTRY:
            print(f"Plataforma desconocida: {platform}. Opciones: {', '.join(FLOW_REGISTRY)}")
            return 1
        enabled = [platform]

    scrape_cfg = settings.get("scraping") or {}
    headless = bool(scrape_cfg.get("headless", True))
    if headed:
        headless = False
    timeout_ms = int(scrape_cfg.get("navigation_timeout_ms", 45000))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = raw_dir / f"scrape_{stamp}.jsonl"
    all_rows: list[dict[str, Any]] = []

    t_run = time.perf_counter()
    with sync_playwright() as p:
        t0 = time.perf_counter()
        browser = p.chromium.launch(headless=headless, channel="chrome")
        _LOG.debug("playwright chromium.launch %.2fs (headless=%s, channel=chrome)", time.perf_counter() - t0, headless)
        first_platform = True
        for plat in enabled:
            flow = FLOW_REGISTRY.get(plat)
            if not flow:
                print(f"Omitido (sin flujo): {plat}")
                continue

            context_kwargs: dict[str, Any] = {
                "locale": "es-MX",
                "timezone_id": "America/Mexico_City",
                "viewport": {"width": 1365, "height": 900},
            }
            if plat == "rappi" and auth_file.is_file():
                _LOG.debug("Cargando sesión desde %s para %s", auth_file, plat)
                context_kwargs["storage_state"] = str(auth_file)

            context = browser.new_context(**context_kwargs)
            context.set_default_navigation_timeout(timeout_ms)
            page = context.new_page()

            if plat == "rappi" and not auth_file.is_file() and not headless:
                _LOG.info("=== INICIO DE SESIÓN MANUAL ===")
                try:
                    page.goto("https://www.rappi.com.mx", wait_until="load")
                    print("\n" + "=" * 60)
                    print("Por favor, inicia sesión manualmente en la ventana del navegador de Rappi.")
                    print("Una vez logueado correctamente,")
                    input("PRESIONA ENTER AQUÍ EN LA TERMINAL PARA CONTINUAR...")
                    print("=" * 60 + "\n")
                    context.storage_state(path=str(auth_file))
                    _LOG.debug("Sesión inicial guardada en %s", auth_file)
                except Exception as e:
                    _LOG.warning("No se pudo completar el flujo de inicio de sesión: %s", e)

            if not first_platform:
                t_plat_pause = time.perf_counter()
                sleep_between_platforms(settings)
                _LOG.debug("pause between_platforms %.2fs", time.perf_counter() - t_plat_pause)
            first_platform = False

            t_plat = time.perf_counter()
            for j, loc in enumerate(locations):
                if j > 0:
                    t_loc_pause = time.perf_counter()
                    sleep_between_locations(settings)
                    _LOG.debug("pause between_locations %.2fs", time.perf_counter() - t_loc_pause)
                lid = str(loc.get("id", j))
                rows = flow(page, loc, settings)
                all_rows.extend(rows)
                _LOG.info("scrape: plataforma=%s ubicación=%s filas=%d", plat, lid, len(rows))
            _LOG.debug("platform=%s total_wall=%.2fs", plat, time.perf_counter() - t_plat)

            if plat == "rappi":
                try:
                    context.storage_state(path=str(auth_file))
                    _LOG.debug("Sesión guardada en %s", auth_file)
                except Exception as e:
                    _LOG.warning("No se pudo guardar la sesión: %s", e)
            
            context.close()

        browser.close()
    _LOG.info("scrape run total_wall=%.2fs rows=%d", time.perf_counter() - t_run, len(all_rows))

    out_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows),
        encoding="utf-8",
    )

    comparison_path: Path | None = None
    if all_rows:
        try:
            from competitive_intel.analysis.platform_comparison import run_comparison_export

            scrape_cfg = settings.get("scraping") or {}
            sim = scrape_cfg.get("comparison_similarity", 0.9)
            try:
                sim_f = float(sim)
            except (TypeError, ValueError):
                sim_f = 0.9
            sim_f = max(0.5, min(1.0, sim_f))

            comparison_path = exports_dir / f"rappi_uber_comparison_{stamp}.json"
            run_comparison_export(
                input_path=out_path,
                output_path=comparison_path,
                similar_threshold=sim_f,
            )
            _LOG.info("Comparacion Rappi/Uber escrita en %s", comparison_path)
        except Exception as e:
            _LOG.warning("No se pudo generar la comparacion Rappi/Uber (JSON): %s", e)

    meta = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "jsonl": str(out_path),
        "rows": len(all_rows),
        "platforms": enabled,
        "locations_file": str(loc_file),
        "reference_products": len(products),
        "comparison_json": str(comparison_path) if comparison_path else None,
    }
    meta_path = raw_dir / f"scrape_{stamp}_meta.json"
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=== scrape: filas ===", flush=True)
    print(json.dumps(all_rows, ensure_ascii=False, indent=2), flush=True)
    print("=== scrape: meta ===", flush=True)
    print(json.dumps(meta, ensure_ascii=False, indent=2), flush=True)
    files_msg = f"{out_path} | {meta_path}"
    if comparison_path:
        files_msg += f" | {comparison_path}"
    print(f"=== archivos: {files_msg} ===", flush=True)
    return 0
