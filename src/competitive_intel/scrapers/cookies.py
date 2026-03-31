from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


def try_dismiss_cookies(page: Page) -> None:
    labels = (
        "Ok, entendido",
        "Ok, entiendo",
        "Entendido",
        "Aceptar todo",
        "Aceptar",
        "Accept",
    )
    for name in labels:
        try:
            btn = page.get_by_role("button", name=name)
            if btn.count() > 0:
                first = btn.first
                if first.is_visible():
                    first.click(timeout=2500)
                    return
        except Exception:
            continue
