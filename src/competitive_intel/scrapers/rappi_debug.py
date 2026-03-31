from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from competitive_intel.config import resolve_data_paths

logger = logging.getLogger("scrape")


def rappi_debug_enabled(settings: dict[str, Any]) -> bool:
    r = (settings.get("scraping") or {}).get("rappi") or {}
    return bool(r.get("debug_page_dumps"))


def rappi_debug_dir(settings: dict[str, Any]) -> Path:
    r = (settings.get("scraping") or {}).get("rappi") or {}
    raw = r.get("debug_page_dir")
    if raw is not None and str(raw).strip():
        p = Path(str(raw).strip())
        return p if p.is_absolute() else Path.cwd() / p
    data_dir, _ = resolve_data_paths()
    return data_dir / "debug" / "rappi_pages"


def dump_rappi_page(
    page: Any,
    settings: dict[str, Any],
    location_id: str,
    step: str,
    *,
    full_page_screenshot: bool = False,
) -> Path | None:
    """
    Guarda HTML completo (`page.content()`), captura PNG y un .meta.json con URL/título.
    Nombres: `{location}__{step}__{timestamp}.html`
    """
    if not rappi_debug_enabled(settings):
        return None
    d = rappi_debug_dir(settings)
    d.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^\w\-\.]+", "_", str(location_id))[:48]
    safe_step = re.sub(r"[^\w\-\.]+", "_", step)[:56]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    stem = f"{safe_id}__{safe_step}__{stamp}"
    html_p = d / f"{stem}.html"
    meta_p = d / f"{stem}.meta.json"
    png_p = d / f"{stem}.png"
    url = ""
    title = ""
    try:
        url = page.url
        title = page.title()
        html_p.write_text(page.content(), encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("rappi debug: no se pudo volcar HTML step=%s: %s", step, e)
        return None
    try:
        meta_p.write_text(
            json.dumps(
                {"url": url, "title": title, "location_id": location_id, "step": step},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    try:
        page.screenshot(path=str(png_p), full_page=full_page_screenshot)
    except Exception:
        try:
            page.screenshot(path=str(png_p), full_page=False)
        except Exception:
            logger.debug("rappi debug: screenshot omitido step=%s", step)
    logger.info("rappi debug volcado step=%s -> %s", step, html_p)
    return html_p
