"""Playwright fallback — only if the requests path stops working.

The primary fetcher uses requests + BeautifulSoup against the portal's
own search servlet, which works today (verified 2026-11-14). If the
portal ever starts requiring JavaScript execution (e.g. a JS challenge
on the search page), this module renders the Advanced Search page in a
real headless Chromium and returns the loaded HTML, from which the
normal parsers can extract rows.

This is deliberately a fallback, not the default: a headless browser
is heavier, slower, and harder to run on free tiers. Install with:
    pip install playwright && playwright install chromium

Public pages only — this module never fills in the login form.
"""

from __future__ import annotations

import logging

from .config import SETTINGS

log = logging.getLogger(__name__)


def fetch_search_page_rendered(*, pub_from: str = "", pub_to: str = "",
                               settings: Settings = SETTINGS,
                               timeout_ms: int = 60_000) -> str:
    """Render the Advanced Search page and return its HTML.

    Dates are dd/mm/yyyy strings. The page's own JavaScript loads the
    first result page automatically; we wait for the result table.
    Raises RuntimeError with install instructions if Playwright is
    missing, or the underlying Playwright error on page failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install it with: "
            "pip install playwright && playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=settings.user_agent)
            page.goto(settings.advanced_search_url,
                      timeout=timeout_ms, wait_until="networkidle")
            # Fill the publish-date window and submit the search, if the
            # fields exist; otherwise return the default (Live) results.
            try:
                if pub_from:
                    page.fill("#pubDtFrm", pub_from)
                if pub_to:
                    page.fill("#pubDtTo", pub_to)
                page.click("#btnSearch")
                page.wait_for_selector("#resultTable tr", timeout=30_000)
            except Exception as exc:  # noqa: BLE001 - fall back to raw HTML
                log.warning("Playwright search interaction failed (%s); "
                            "returning rendered page as-is", exc)
            return page.content()
        finally:
            browser.close()
