from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from competitive_intel.scrapers.cookies import try_dismiss_cookies
from competitive_intel.scrapers.throttle import sleep_between_rappi_chains, sleep_scrape_delay

try:
    from playwright.sync_api import Locator, Page
except ImportError:
    Locator = Any  # type: ignore[misc, assignment]
    Page = Any  # type: ignore[misc, assignment]

logger = logging.getLogger("scrape")


def _base_record(platform: str, location: dict[str, Any]) -> dict[str, Any]:
    addr = location.get("address_line") or location.get("label") or ""
    return {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform,
        "location_id": str(location.get("id", "")),
        "address_used": addr,
        "status": "error",
        "error": None,
        "final_url": None,
        "products_sample": [],
    }


def _still_on_landing(platform: str, url: str) -> bool:
    p = urlparse(url)
    host = (p.netloc or "").lower()
    path_raw = p.path or "/"
    if platform == "rappi":
        path = path_raw.rstrip("/") or "/"
        return host.endswith("rappi.com.mx") and path == "/"
    if platform == "uber_eats":
        return bool("ubereats.com" in host and re.match(r"^/mx/?$", path_raw, re.I))
    if platform == "didi_food":
        return bool("didi-food.com" in host and re.match(r"^/es-mx/food/?$", path_raw, re.I))
    return False


def _apply_navigation_result(rec: dict[str, Any], platform: str, url: str, err: str | None) -> None:
    rec["final_url"] = url
    if err:
        rec["status"] = "error"
        rec["error"] = err[:800]
        return
    if _still_on_landing(platform, url):
        rec["status"] = "partial"
        rec["error"] = "URL sigue en landing; dirección o autocompletado no aplicó (revisa selectores o elige sugerencia)."
        return
    rec["status"] = "ok"
    rec["error"] = None


def _rappi_scrape_cfg(settings: dict[str, Any]) -> dict[str, Any]:
    return (settings.get("scraping") or {}).get("rappi") or {}


def _rappi_chain_list(cfg: dict[str, Any]) -> list[str]:
    chains = cfg.get("chains")
    if isinstance(chains, list) and chains:
        return [str(c).strip() for c in chains if str(c).strip()]
    legacy = cfg.get("store_search_query")
    if legacy:
        return [str(legacy).strip()]
    return ["McDonald's"]


def _rappi_chain_link_regex(chain: str) -> re.Pattern[str]:
    c = chain.strip()
    aliases: dict[str, str] = {
        "McDonald's": r"McDonald",
        "Little Caesars": r"Little\s*Caesar",
        "KFC": r"\bKFC\b",
        "Subway": r"Subway",
        "Burger King": r"Burger\s*King",
    }
    return re.compile(aliases.get(c, re.escape(c)), re.I)


def _rappi_url_looks_like_chain(url: str, chain: str) -> bool:
    u = url.lower()
    c = chain.strip().lower()
    if "mcdonald" in c:
        return "mcdonald" in u
    if "caesar" in c or "little" in c:
        return "caesar" in u or "caesars" in u
    if "kfc" in c:
        return "kfc" in u
    if "subway" in c:
        return "subway" in u
    if "burger" in c and "king" in c:
        return "burger" in u and "king" in u
    return chain.lower().replace(" ", "-")[:12] in u


def _rappi_chain_href_fragment(chain: str) -> str | None:
    c = chain.strip().lower()
    if "mcdonald" in c:
        return "mcdonald"
    if "caesar" in c or "little" in c:
        return "caesar"
    if "kfc" in c:
        return "kfc"
    if "subway" in c:
        return "subway"
    if "burger" in c and "king" in c:
        return "burger"
    return None


def _rappi_wait_store_ready(page: Page, timeout_ms: int = 12000) -> None:
    """Espera a que la vista de tienda muestre productos o bloque store-info."""
    try:
        page.wait_for_selector(
            '[data-qa^="product-item-"], [data-qa="store-info"]',
            timeout=timeout_ms,
        )
    except Exception:
        page.wait_for_timeout(1800)


def _rappi_wait_results_after_search(page: Page, chain: str, timeout_ms: int = 9000) -> None:
    frag = _rappi_chain_href_fragment(chain)
    try:
        if frag:
            page.locator(f'a[href*="/restaurantes/"][href*="{frag}"]').first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
        else:
            page.wait_for_selector('a[href*="/restaurantes/"]', timeout=timeout_ms)
    except Exception:
        page.wait_for_timeout(2400)


def _rappi_global_search_candidates(page: Page) -> list[Locator]:
    ph = re.compile(
        r"Comida|restaurantes|tiendas|productos|buscar|¿Qué|que quieres|pedir|en Rappi",
        re.I,
    )
    return [
        page.get_by_role("searchbox").first,
        page.locator('input[type="search"]').first,
        page.get_by_placeholder(ph).first,
        page.locator('[data-testid*="search" i]').first,
        page.locator('input[aria-label*="buscar" i], input[aria-label*="search" i]').first,
        page.locator("header").locator('input[type="text"]:not([placeholder*="recibir" i]):not([placeholder*="compra" i])').first,
    ]


def _rappi_wait_global_search(page: Page, timeout_ms: int = 28000) -> Locator:
    end = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < end:
        for loc in _rappi_global_search_candidates(page):
            try:
                if loc.count() == 0:
                    continue
                loc.wait_for(state="visible", timeout=1200)
                return loc
            except Exception:
                continue
        page.wait_for_timeout(400)
    raise TimeoutError("No se encontró la barra de búsqueda global (placeholder / searchbox / header).")


def _rappi_top_search_visible(page: Page) -> bool:
    try:
        _rappi_wait_global_search(page, timeout_ms=4000)
        return True
    except Exception:
        return False


def _rappi_should_scrape_menu(rec: dict[str, Any], page: Page) -> bool:
    if rec.get("status") == "ok":
        return True
    if rec.get("status") == "partial" and _rappi_top_search_visible(page):
        return True
    return False


def _rappi_open_chain_store(
    page: Page,
    settings: dict[str, Any],
    chain: str,
    *,
    use_carousel_link: bool,
) -> None:
    rx = _rappi_chain_link_regex(chain)
    if use_carousel_link:
        sleep_scrape_delay(settings, for_rappi=True)
        try:
            link = page.get_by_role("link", name=rx).first
            if link.is_visible(timeout=7000):
                link.click(timeout=15000)
                _rappi_wait_store_ready(page, timeout_ms=12000)
                page.wait_for_load_state("load", timeout=35000)
                if _rappi_url_looks_like_chain(page.url, chain):
                    return
        except Exception:
            pass

    sleep_scrape_delay(settings, for_rappi=True)
    search = _rappi_wait_global_search(page, timeout_ms=30000)
    search.click()
    search.fill("", timeout=2000)
    search.fill(chain, timeout=10000)
    page.wait_for_timeout(450)
    page.keyboard.press("Enter")
    _rappi_wait_results_after_search(page, chain, timeout_ms=9000)
    page.wait_for_load_state("load", timeout=35000)

    try:
        hit = page.locator("a").filter(has_text=rx).first
        hit.wait_for(state="visible", timeout=15000)
        hit.click(timeout=15000)
    except Exception:
        frag = _rappi_chain_href_fragment(chain)
        if frag:
            page.locator(f'a[href*="{frag}"]').first.click(timeout=15000)
        else:
            raise
    _rappi_wait_store_ready(page, timeout_ms=12000)
    page.wait_for_load_state("load", timeout=35000)


def _rappi_price_regex() -> re.Pattern[str]:
    return re.compile(r"(MX\$\s*[\d,.]+|\$\s*[\d,.]+|MXN\s*[\d,.]+)", re.I)


def _rappi_name_price_from_text(text: str) -> tuple[str, str | None]:
    raw = " ".join(text.split())
    m = _rappi_price_regex().search(raw)
    if not m:
        return raw[:180], None
    name = raw[: m.start()].strip()
    if len(name) < 2:
        name = raw[m.end() :].strip()
        name = _rappi_price_regex().sub("", name).strip()[:180] or "producto"
    return name[:200], m.group(1)


def _rappi_row_to_item(name: str, price_raw: str, seen: set[tuple[str, str]]) -> dict[str, Any] | None:
    if len(name) < 2 or not price_raw:
        return None
    key = (name[:50].lower(), price_raw)
    if key in seen:
        return None
    seen.add(key)
    num: float | None = None
    try:
        digits = re.sub(r"[^\d.]", "", price_raw)
        if digits:
            num = float(digits)
    except Exception:
        pass
    return {"name": name, "price_raw": price_raw, "price": num}


def _rappi_extract_menu_items_data_qa(page: Page, limit: int, seen: set[tuple[str, str]]) -> list[dict[str, Any]]:
    """Rappi (Chakra): tarjetas con data-qa product-item-*; título en h4 dentro de product-info; precio en span.chakra-text ($ 99.00)."""
    raw_list = page.evaluate(
        """(lim) => {
          const out = [];
          const seen = new Set();
          const priceLine = /^\\$\\s*[\\d,.]+$/;
          const skipTitle = /^(envío|calificación|menú|restaurantes similares|preguntas frecuentes|horario)/i;

          function add(name, price_raw) {
            if (out.length >= lim) return;
            const n = name.replace(/\\u00a0/g, ' ').trim().replace(/\\s+/g, ' ');
            if (n.length < 3 || n.length > 200) return;
            if (skipTitle.test(n)) return;
            const k = (n.slice(0, 60) + price_raw).toLowerCase();
            if (seen.has(k)) return;
            seen.add(k);
            out.push({ name: n, price_raw: price_raw.trim() });
          }

          for (const card of document.querySelectorAll('[data-qa^="product-item-"]')) {
            if (out.length >= lim) break;
            const info = card.querySelector('[data-qa^="product-info-"]') || card;
            let name = '';
            const h = info.querySelector('h2.chakra-text, h3.chakra-text, h4.chakra-text, h5.chakra-text, h2, h3, h4, h5');
            if (h) {
              name = (h.textContent || '').replace(/\\u00a0/g, ' ').trim().replace(/\\s+/g, ' ');
            }
            if (name.length < 3) {
              const p = info.querySelector('p.chakra-text, p');
              if (p) {
                name = (p.textContent || '').replace(/\\u00a0/g, ' ').trim().replace(/\\s+/g, ' ');
              }
            }
            let price_raw = null;
            for (const sp of card.querySelectorAll('span.chakra-text')) {
              const t = (sp.textContent || '').replace(/\\u00a0/g, ' ').trim();
              if (priceLine.test(t)) {
                price_raw = t;
                break;
              }
            }
            if (name.length >= 3 && price_raw) add(name, price_raw);
          }
          return out;
        }""",
        limit,
    )
    items: list[dict[str, Any]] = []
    for row in raw_list or []:
        name = str(row.get("name") or "")
        pr = str(row.get("price_raw") or "")
        item = _rappi_row_to_item(name, pr, seen)
        if item:
            items.append(item)
    return items


def _rappi_extract_menu_items_headings(page: Page, limit: int, seen: set[tuple[str, str]]) -> list[dict[str, Any]]:
    raw_list = page.evaluate(
        """(lim) => {
          const out = [];
          const seen = new Set();
          const priceFind = /\\$\\s*[\\d,.]+/;
          const priceTail = /((?:MX\\$|\\$)\\s*[\\d,.]+)\\s*$/i;
          const skipFooter = /^(dirección|direccion|especialidad|especialidades|rating|horario|sobre\\s|preguntas|calificaciones|ubicación|ubicacion)$/i;
          const sectionExact = new Set([
            'big mac + coca', 'mc para todos', 'mctrios comida', 'mctrio comida', 'tu fav',
            'a la carta comida', 'a la carta', 'postres', 'bebidas', 'cajita feliz',
            'combos', 'super combos', 'ensaladas', 'complementos', 'papas', 'galletas',
            'snacks', 'kids', 'promociones', 'lanzamientos', 'especialidades', 'pizzas',
            'lo nuevo', 'lo nuevo!', 'todos los subs', 'sub series', 'sub series combos',
            'nuevos king de pollo', 'combos para 1', 'noches bk', 'promociones bk',
            'family king', 'big krunch burger', 'kfc wöw', 'kfc wow', 'burgers', 'boxes',
            'buckets para compartir', 'ke tiras lovers', 'caesar dips', 'caesar dips¨',
            'promociones', 'lo nuevo', 'big krunch burger',
          ]);
          const skipTitle = /^(envío|calificación|menú|restaurantes similares|preguntas frecuentes|horario)/i;

          function looksLikeSectionTitle(name) {
            const t = name.replace(/\\u00a0/g, ' ').trim();
            const lower = t.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
            if (sectionExact.has(lower)) return true;
            if (skipFooter.test(t)) return true;
            if (t.length >= 3 && t.length <= 36 && t === t.toUpperCase() && /[A-ZÁÉÍÓÚÑ]/.test(t)) return true;
            return false;
          }

          function add(name, price_raw) {
            if (out.length >= lim) return;
            const n = name.replace(/\\u00a0/g, ' ').trim().replace(/\\s+/g, ' ');
            if (n.length < 3 || n.length > 200) return;
            if (skipTitle.test(n)) return;
            if (priceFind.test(n)) return;
            if (looksLikeSectionTitle(n)) return;
            const k = (n.slice(0, 60) + price_raw).toLowerCase();
            if (seen.has(k)) return;
            seen.add(k);
            out.push({ name: n, price_raw: price_raw.trim() });
          }

          function priceFromLine(line) {
            const L = (line || '').replace(/\\u00a0/g, ' ').trim();
            if (!L || /^-\\d+%/.test(L)) return null;
            let m = L.match(priceTail);
            if (m) return m[1];
            let best = null;
            const re = /((?:MX\\$|\\$)\\s*[\\d,.]+)/gi;
            let mm;
            while ((mm = re.exec(L)) !== null) best = mm[1];
            return best;
          }

          function lastPriceLine(lines) {
            for (let i = lines.length - 1; i >= 0; i--) {
              const p = priceFromLine(lines[i]);
              if (p) return p;
            }
            return null;
          }

          const root =
            document.querySelector('#rappi-temporary-web-container') ||
            document.querySelector('#__next') ||
            document.querySelector('main') ||
            document.querySelector('[role="main"]') ||
            document.body;
          for (const a of root.querySelectorAll('a[href]')) {
            if (out.length >= lim) break;
            const href = (a.getAttribute('href') || '');
            if (href.startsWith('#') || href.startsWith('javascript:')) continue;
            const text = (a.innerText || '').replace(/\\u00a0/g, ' ').trim();
            if (!text.includes('$') || text.length > 3500) continue;
            const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
            if (lines.length === 0) continue;
            let priceLine = null;
            let name = '';
            if (lines.length === 1) {
              const one = lines[0];
              const m = one.match(/^(.{3,180}?)\\s+((?:MX\\$|\\$)\\s*[\\d,.]+)\\s*$/i);
              if (m) {
                name = m[1].trim();
                priceLine = m[2].trim();
              }
            } else {
              priceLine = lastPriceLine(lines);
              name = lines[0];
            }
            if (!priceLine || !name) continue;
            if (looksLikeSectionTitle(name)) continue;
            if (name.length < 3) continue;
            add(name, priceLine);
          }
          if (out.length < lim && root !== document.body) {
            for (const a of document.body.querySelectorAll('a[href]')) {
              if (out.length >= lim) break;
              const href = (a.getAttribute('href') || '');
              if (href.startsWith('#') || href.startsWith('javascript:')) continue;
              const text = (a.innerText || '').replace(/\\u00a0/g, ' ').trim();
              if (!text.includes('$') || text.length > 3500) continue;
              const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
              if (lines.length === 0) continue;
              let priceLine = null;
              let name = '';
              if (lines.length === 1) {
                const m = lines[0].match(/^(.{3,180}?)\\s+((?:MX\\$|\\$)\\s*[\\d,.]+)\\s*$/i);
                if (m) {
                  name = m[1].trim();
                  priceLine = m[2].trim();
                }
              } else {
                priceLine = lastPriceLine(lines);
                name = lines[0];
              }
              if (!priceLine || !name) continue;
              if (looksLikeSectionTitle(name)) continue;
              if (name.length < 3) continue;
              add(name, priceLine);
            }
          }

          for (const h of document.querySelectorAll('h6, h5, h4')) {
            if (out.length >= lim) break;
            let title = (h.textContent || '').replace(/\\u00a0/g, ' ').trim().replace(/\\s+/g, ' ');
            if (title.length < 3 || title.length > 180) continue;
            if (skipTitle.test(title)) continue;
            if (priceFind.test(title)) continue;
            if (looksLikeSectionTitle(title)) continue;
            let m = null;
            let n = h.nextElementSibling;
            for (let i = 0; i < 14 && n; i++) {
              const t = (n.textContent || '').replace(/\\u00a0/g, ' ');
              const mm = t.match(priceFind);
              if (mm) { m = mm; break; }
              n = n.nextElementSibling;
            }
            if (!m) {
              const card = h.closest('div');
              if (card) {
                const block = (card.innerText || '').replace(/\\u00a0/g, ' ');
                const idx = block.indexOf(title);
                if (idx >= 0) {
                  const tail = block.slice(idx + title.length);
                  const mm = tail.match(priceFind);
                  if (mm) m = mm;
                }
              }
            }
            if (m) add(title, m[0]);
          }
          return out;
        }""",
        limit,
    )
    items: list[dict[str, Any]] = []
    for row in raw_list or []:
        name = str(row.get("name") or "")
        pr = str(row.get("price_raw") or "")
        item = _rappi_row_to_item(name, pr, seen)
        if item:
            items.append(item)
    return items


def _rappi_extract_menu_items_links(page: Page, limit: int, seen: set[tuple[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    pat = re.compile(r"\$|MX\$", re.I)
    links = page.locator("a").filter(has=page.locator("text=/\\$|MX\\$/"))
    n = min(links.count(), 80)
    for i in range(n):
        if len(items) >= limit:
            break
        el = links.nth(i)
        try:
            if not el.is_visible():
                continue
            txt = el.inner_text(timeout=2000)
        except Exception:
            continue
        if not pat.search(txt):
            continue
        name, price_raw = _rappi_name_price_from_text(txt)
        row = _rappi_row_to_item(name, price_raw, seen)
        if row:
            items.append(row)
    return items


def _rappi_extract_menu_items_eval(page: Page, limit: int, seen: set[tuple[str, str]]) -> list[dict[str, Any]]:
    raw_list = page.evaluate(
        """(lim) => {
          const out = [];
          const seen = new Set();
          const rxEnd = /((?:MX\\$|\\$)\\s*[\\d,.]+)\\s*$/i;
          const rxOnly = /^(?:MX\\$|\\$)\\s*[\\d,.]+$/i;
          const add = (name, price_raw) => {
            if (out.length >= lim) return;
            const k = (name.slice(0,50) + price_raw).toLowerCase();
            if (seen.has(k) || name.length < 2) return;
            seen.add(k);
            out.push({ name: name.slice(0, 200), price_raw });
          };
          for (const el of document.querySelectorAll('span, p, h3, h4, h5, div')) {
            if (out.length >= lim) break;
            const t = (el.textContent || '').trim().replace(/\\s+/g, ' ');
            if (t.length < 3 || t.length > 42) continue;
            if (!rxOnly.test(t)) continue;
            const m = t.match(/((?:MX\\$|\\$)\\s*[\\d,.]+)/i);
            if (!m) continue;
            const price_raw = m[1];
            const card = el.closest('a') || el.closest('li, article, [class*="product"], [class*="Product"], [class*="Item"]');
            if (!card) continue;
            const full = (card.innerText || '').trim().replace(/\\s+/g, ' ');
            if (full.length > 500) continue;
            let name = full.replace(price_raw, '').trim().split('\\n').filter(Boolean)[0] || '';
            name = name.replace(/^[+\\d\\smin.-]+/i, '').trim();
            if (name.length >= 2) add(name, price_raw);
          }
          for (const a of document.querySelectorAll('a[href]')) {
            if (out.length >= lim) break;
            const full = (a.innerText || '').trim();
            if (full.length < 8 || full.length > 400) continue;
            const lines = full.split('\\n').map(s => s.trim()).filter(Boolean);
            const last = lines[lines.length - 1] || '';
            const m = last.match(/^((?:MX\\$|\\$)\\s*[\\d,.]+)$/i);
            if (!m) continue;
            const price_raw = m[1];
            let name = lines.slice(0, -1).join(' ') || lines[0];
            if (name === last) name = full.replace(price_raw, '').trim().split('\\n')[0];
            if (name.length >= 2) add(name, price_raw);
          }
          return out;
        }""",
        limit,
    )
    items: list[dict[str, Any]] = []
    for row in raw_list or []:
        name = str(row.get("name") or "")
        pr = str(row.get("price_raw") or "")
        item = _rappi_row_to_item(name, pr, seen)
        if item:
            items.append(item)
    return items


def _rappi_extract_menu_items(page: Page, limit: int) -> list[dict[str, Any]]:
    try:
        page.wait_for_selector(
            "#rappi-temporary-web-container, #__next, main, [role='main'], [data-qa^='product-item-']",
            timeout=15000,
        )
    except Exception:
        pass
    try:
        page.wait_for_selector("h3, h4, h5, a, [data-qa^='product-item-']", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(1100)
    try:
        n = page.locator('[data-qa^="product-item-"]').count()
    except Exception:
        n = 0
    scroll_rounds = 4 if n >= limit else 6
    for _ in range(scroll_rounds):
        page.mouse.wheel(0, 480)
        page.wait_for_timeout(160)
    page.wait_for_timeout(450)
    seen: set[tuple[str, str]] = set()
    items = _rappi_extract_menu_items_data_qa(page, limit, seen)
    if len(items) < limit:
        items.extend(_rappi_extract_menu_items_headings(page, limit, seen))
    if len(items) < limit:
        items.extend(_rappi_extract_menu_items_links(page, limit, seen))
    if len(items) < limit:
        items.extend(_rappi_extract_menu_items_eval(page, limit, seen))
    return items[:limit]


def _rappi_extract_store_operational_meta(page: Page) -> dict[str, str | None]:
    """Tiempo/envío: barra lateral del shell (no está dentro de store-info). Calificación: ratingScore en store-info."""
    raw = page.evaluate(
        """() => {
          const norm = (s) => (s || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
          const shell =
            document.querySelector('#rappi-temporary-web-container') ||
            document.body;
          const storeInfo =
            document.querySelector('[data-qa="store-info"]') ||
            document.querySelector('[data-qa="store-information"]') ||
            shell;

          function rowValueAfterLabel(searchRoot, labelExact) {
            const labs = searchRoot.querySelectorAll('span[data-testid="typography"], p[data-testid="typography"]');
            for (const lab of labs) {
              if (norm(lab.textContent) !== labelExact) continue;
              const hdr = lab.closest('div');
              if (!hdr || !hdr.parentElement) continue;
              const row = hdr.parentElement;
              const sk = row.querySelector('.chakra-skeleton');
              if (sk) {
                const v = norm(sk.innerText || sk.textContent || '');
                if (v) return v;
              }
              let sib = hdr.nextElementSibling;
              while (sib) {
                const t = norm(sib.innerText || sib.textContent || '');
                if (t && t.length > 0 && t.length < 120) return t;
                sib = sib.nextElementSibling;
              }
            }
            return null;
          }

          let delivery_eta_raw = rowValueAfterLabel(shell, 'Delivery');
          let delivery_fee_raw = rowValueAfterLabel(shell, 'Envío');

          const blobShell = norm(shell.innerText || '');
          if (!delivery_eta_raw) {
            const m = blobShell.match(
              /Delivery[\\s\\S]{0,200}?(\\d+(?:\\s*-\\s*\\d+)?\\s*min(?:utos)?)/i
            );
            if (m) delivery_eta_raw = norm(m[1]);
          }
          if (!delivery_fee_raw) {
            const j = blobShell.indexOf('Envío');
            if (j >= 0) {
              const slice = blobShell.slice(j, j + 220);
              const g = slice.match(
                /Envío[\\s\\S]{0,160}?(Gratis(?:\\s*\\([^)]+\\))?|\\$\\s*[\\d,.]+|MX\\$\\s*[\\d,.]+)/i
              );
              if (g) delivery_fee_raw = norm(g[1]);
            }
          }

          let store_rating_raw = null;
          const rs = storeInfo.querySelector('[data-testid="ratingScore"]');
          if (rs) store_rating_raw = norm(rs.textContent || '');

          if (!store_rating_raw) {
            const cr = rowValueAfterLabel(shell, 'Calificación');
            if (cr) store_rating_raw = (cr.split(/\\s+/)[0] || null);
          }
          if (!store_rating_raw) {
            const m = norm(storeInfo.innerText || '').match(
              /Calificación[\\s\\S]{0,80}?([\\d]+(?:\\.[\\d]+)?)/i
            );
            if (m) store_rating_raw = m[1];
          }

          return {
            delivery_eta_raw,
            delivery_fee_raw,
            store_rating_raw,
          };
        }"""
    )
    if not isinstance(raw, dict):
        return {"delivery_eta_raw": None, "delivery_fee_raw": None, "store_rating_raw": None}
    return {
        "delivery_eta_raw": raw.get("delivery_eta_raw") if raw.get("delivery_eta_raw") else None,
        "delivery_fee_raw": raw.get("delivery_fee_raw") if raw.get("delivery_fee_raw") else None,
        "store_rating_raw": raw.get("store_rating_raw") if raw.get("store_rating_raw") else None,
    }


def _rappi_scrape_one_chain(
    page: Page,
    rec: dict[str, Any],
    settings: dict[str, Any],
    chain: str,
    *,
    use_carousel_link: bool,
) -> None:
    cfg = _rappi_scrape_cfg(settings)
    limit = int(cfg.get("menu_items_limit") or 10)
    menu_err: str | None = None
    products: list[dict[str, Any]] = []
    rec["delivery_eta_raw"] = None
    rec["delivery_fee_raw"] = None
    rec["store_rating_raw"] = None
    t_chain = time.perf_counter()
    try:
        t0 = time.perf_counter()
        _rappi_open_chain_store(page, settings, chain, use_carousel_link=use_carousel_link)
        logger.info("rappi timing chain=%s open_store=%.2fs", chain, time.perf_counter() - t0)
        sleep_scrape_delay(settings, for_rappi=True)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        try:
            page.wait_for_selector(
                '[data-qa="store-info"], [data-testid="ratingScore"], span[data-testid="typography"]',
                timeout=10000,
            )
        except Exception:
            pass
        page.wait_for_timeout(400)
        t1 = time.perf_counter()
        meta = _rappi_extract_store_operational_meta(page)
        rec["delivery_eta_raw"] = meta["delivery_eta_raw"]
        rec["delivery_fee_raw"] = meta["delivery_fee_raw"]
        rec["store_rating_raw"] = meta["store_rating_raw"]
        logger.info("rappi timing chain=%s store_meta=%.2fs", chain, time.perf_counter() - t1)
        t2 = time.perf_counter()
        products = _rappi_extract_menu_items(page, limit)
        logger.info(
            "rappi timing chain=%s menu_items=%.2fs (n=%s)",
            chain,
            time.perf_counter() - t2,
            len(products),
        )
        if not products:
            menu_err = "No se encontraron productos con precio en la vista actual."
    except Exception as e:
        menu_err = str(e)[:600]
    logger.info(
        "rappi timing chain=%s total=%.2fs url=%s",
        chain,
        time.perf_counter() - t_chain,
        page.url[:80],
    )
    rec["products_sample"] = products
    rec["chain"] = chain
    rec["menu_items_limit"] = limit
    rec["final_url"] = page.url
    if menu_err:
        rec["menu_error"] = menu_err


def _rappi_select_address_suggestion(page: Page) -> bool:
    selectors = (
        '[role="listbox"] [role="option"]',
        '[role="menu"] [role="menuitem"]',
        '[role="option"]',
        "ul li >> visible=true",
    )
    for sel in selectors:
        try:
            opt = page.locator(sel).first
            opt.wait_for(state="visible", timeout=6000)
            opt.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


def _click_didi_search(page: Page, timeout_ms: int) -> None:
    last: Exception | None = None
    candidates = [
        lambda: page.get_by_role("button", name=re.compile(r"Buscar comida", re.I)).first.click(timeout=timeout_ms),
        lambda: page.locator("button").filter(has_text=re.compile(r"Buscar", re.I)).first.click(timeout=timeout_ms),
        lambda: page.get_by_text(re.compile(r"Buscar\s+comida", re.I)).click(timeout=timeout_ms),
        lambda: page.locator('input[type="submit"]').first.click(timeout=timeout_ms),
    ]
    for fn in candidates:
        try:
            fn()
            return
        except Exception as e:
            last = e
    if last:
        raise last


def scrape_rappi_location(page: Page, location: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    rec = _base_record("rappi", location)
    addr = rec["address_used"]
    if not str(addr).strip():
        rec["error"] = "Falta address_line o label en la ubicación"
        return [rec]
    err: str | None = None
    t_addr = time.perf_counter()
    try:
        sleep_scrape_delay(settings, for_rappi=True)
        page.goto("https://www.rappi.com.mx", wait_until="load", timeout=_nav_timeout(settings))
        try_dismiss_cookies(page)
        sleep_scrape_delay(settings, for_rappi=True)
        loc = page.get_by_placeholder(re.compile(r"recibir|compra", re.I)).first
        loc.wait_for(state="visible", timeout=20000)
        loc.click()
        loc.fill("", timeout=2000)
        loc.press_sequentially(addr, delay=35, timeout=60000)
        page.wait_for_timeout(2000)
        if not _rappi_select_address_suggestion(page):
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        if _still_on_landing("rappi", page.url):
            if _rappi_select_address_suggestion(page):
                page.wait_for_timeout(2000)
            else:
                page.keyboard.press("Enter")
                page.wait_for_timeout(2500)
        page.wait_for_load_state("load", timeout=25000)
    except Exception as e:
        err = str(e)
    _apply_navigation_result(rec, "rappi", page.url, err)
    logger.info(
        "rappi timing location=%s address_setup=%.2fs status=%s",
        rec.get("location_id"),
        time.perf_counter() - t_addr,
        rec.get("status"),
    )

    if rec["status"] == "error" or not _rappi_should_scrape_menu(rec, page):
        return [rec]

    cfg = _rappi_scrape_cfg(settings)
    chains = _rappi_chain_list(cfg)
    rows: list[dict[str, Any]] = []
    t_chains = time.perf_counter()
    for idx, chain in enumerate(chains):
        if idx > 0:
            t_pause = time.perf_counter()
            sleep_between_rappi_chains(settings)
            logger.info("rappi timing pause_between_chains=%.2fs", time.perf_counter() - t_pause)
        rc: dict[str, Any] = _base_record("rappi", location)
        rc["address_used"] = rec["address_used"]
        rc["location_id"] = rec["location_id"]
        rc["status"] = rec["status"]
        rc["error"] = rec["error"] if rec["status"] != "partial" else None
        _rappi_scrape_one_chain(
            page,
            rc,
            settings,
            chain,
            use_carousel_link=(idx == 0),
        )
        if rc.get("products_sample") and rc.get("status") == "partial":
            rc["status"] = "ok"
            rc["error"] = None
        rows.append(rc)
    logger.info(
        "rappi timing location=%s all_chains=%.2fs (chains=%s)",
        rec.get("location_id"),
        time.perf_counter() - t_chains,
        len(chains),
    )
    return rows


def scrape_uber_eats_location(page: Page, location: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    rec = _base_record("uber_eats", location)
    addr = rec["address_used"]
    if not str(addr).strip():
        rec["error"] = "Falta address_line o label en la ubicación"
        return [rec]
    err: str | None = None
    try:
        sleep_scrape_delay(settings)
        page.goto("https://www.ubereats.com/mx", wait_until="load", timeout=_nav_timeout(settings))
        try_dismiss_cookies(page)
        sleep_scrape_delay(settings)
        loc = page.get_by_placeholder(re.compile(r"dirección.*entrega|entrega", re.I)).first
        loc.wait_for(state="visible", timeout=20000)
        loc.click()
        loc.fill(addr, timeout=10000)
        sleep_scrape_delay(settings)
        page.wait_for_timeout(1200)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        try:
            search = page.get_by_role("button", name=re.compile(r"Buscar comida", re.I))
            search.first.click(timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        page.wait_for_load_state("load", timeout=30000)
    except Exception as e:
        err = str(e)
    _apply_navigation_result(rec, "uber_eats", page.url, err)
    return [rec]


def scrape_didi_food_location(page: Page, location: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, Any]]:
    rec = _base_record("didi_food", location)
    addr = rec["address_used"]
    if not str(addr).strip():
        rec["error"] = "Falta address_line o label en la ubicación"
        return [rec]
    err: str | None = None
    t = min(25000, _nav_timeout(settings))
    try:
        sleep_scrape_delay(settings)
        page.goto("https://www.didi-food.com/es-MX/food/", wait_until="load", timeout=_nav_timeout(settings))
        try_dismiss_cookies(page)
        sleep_scrape_delay(settings)
        loc = page.get_by_placeholder(re.compile(r"dirección.*entrega|entrega|dirección", re.I)).first
        loc.wait_for(state="visible", timeout=20000)
        loc.click()
        loc.fill(addr, timeout=10000)
        sleep_scrape_delay(settings)
        page.wait_for_timeout(1200)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        _click_didi_search(page, t)
        page.wait_for_timeout(2500)
        page.wait_for_load_state("load", timeout=30000)
    except Exception as e:
        err = str(e)
    _apply_navigation_result(rec, "didi_food", page.url, err)
    return [rec]


def _nav_timeout(settings: dict[str, Any]) -> int:
    s = settings.get("scraping") or {}
    return int(s.get("navigation_timeout_ms", 45000))


FLOW_REGISTRY: dict[str, Callable[[Page, dict[str, Any], dict[str, Any]], list[dict[str, Any]]]] = {
    "rappi": scrape_rappi_location,
    "uber_eats": scrape_uber_eats_location,
    "didi_food": scrape_didi_food_location,
}
