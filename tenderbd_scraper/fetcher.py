"""Fetching logic for e-GP public pages.

Two paths, both public and login-free:

1. Search poll (the reliable path): POST to /TenderDetailsServlet with
   funName=AllTenders — the same call the portal's own Advanced Search
   page makes from JavaScript (verified live 2026-11-14). The servlet
   returns HTML table rows. IMPORTANT: the POST must include the full
   parameter set (empty values included) plus a browser-like
   User-Agent/Accept/Referer, or the servlet answers HTTP 200 with an
   empty body.
2. Notice detail: GET /resources/common/ViewTender.jsp?id=<tender id>
   (the portal itself POSTs a form there, but GET works too — verified).

Every tender keeps its official source URL so the portal can link back
to eprocure.gov.bd.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from urllib.parse import urlencode

from .config import SETTINGS
from .http import FetchError, PoliteSession
from .parsers import parse_notice, parse_search_rows

log = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0 Safari/537.36"),
    "Accept": "*/*",
}


def notice_source_url(tender_id: int, settings: Settings = SETTINGS) -> str:
    """Canonical public URL of a tender notice (for 'view on e-GP')."""
    return f"{settings.notice_url}?{urlencode({'id': tender_id, 'h': 't'})}"


def _search_params(*, page_no: int, size: int, view_type: str = "Live",
                   pub_from: date | None = None, pub_to: date | None = None,
                   close_from: date | None = None,
                   close_to: date | None = None,
                   tender_id: int | None = None,
                   keyword: str | None = None) -> dict:
    """Full parameter set for the AllTenders servlet call.

    The portal's JS sends every field on each call; sending a partial
    set returns an empty body, so defaults are empty strings.
    """
    def fmt(d: date | None) -> str:
        return d.strftime("%d/%m/%Y") if d else ""

    params = {
        "funName": "AllTenders",
        "departmentId": "",
        "viewType": view_type,
        "office": "",
        "procNature": "",
        "budgetType": "",
        "procType": "",
        "procMethod": "",
        "tenderId": str(tender_id) if tender_id else "",
        "refNo": "",
        "pubDtFrm": fmt(pub_from),
        "pubDtTo": fmt(pub_to),
        "closeDtFrm": fmt(close_from),
        "closeDtTo": fmt(close_to),
        "cpvCategory": "",
        "isFrame": "",
        "pageNo": str(page_no),
        "size": str(size),
        "h": "t",
    }
    if keyword:
        params["keyword"] = keyword
    return params


def search_page(session: PoliteSession, page_no: int, *,
                settings: Settings = SETTINGS, **filters) -> dict:
    """Fetch one search-result page; returns parse_search_rows output."""
    params = _search_params(page_no=page_no,
                            size=settings.search_page_size, **filters)
    headers = dict(_BROWSER_HEADERS)
    headers["Referer"] = settings.advanced_search_url
    resp = session.post(settings.search_servlet_url, data=params,
                        headers=headers)
    if not resp.content.strip():
        raise FetchError(
            f"Empty response from search servlet (page {page_no}); "
            "the portal may have changed its search call — see README.")
    return parse_search_rows(resp.text)


def search_all(session: PoliteSession, *,
               settings: Settings = SETTINGS, **filters) -> list[dict]:
    """Walk search pages until the last page or the run limit.

    Returns every row found. Stops early on an empty page.
    """
    all_rows: list[dict] = []
    page_no = 1
    while page_no <= settings.max_search_pages_per_run:
        page = search_page(session, page_no, settings=settings, **filters)
        rows = page["tenders"]
        total = page["total_pages"]
        log.info("Search page %d/%s: %d rows",
                 page_no, total or "?", len(rows))
        if not rows:
            break
        all_rows.extend(rows)
        if total is not None and page_no >= total:
            break
        page_no += 1
    if page_no > settings.max_search_pages_per_run:
        log.warning("Stopped at max search pages per run (%d); "
                    "widen TENDERBD_MAX_SEARCH_PAGES or narrow the window.",
                    settings.max_search_pages_per_run)
    return all_rows


def fetch_notice(session: PoliteSession, tender_id: int, *,
                 settings: Settings = SETTINGS) -> dict:
    """Fetch + parse one public notice detail page."""
    url = notice_source_url(tender_id, settings)
    resp = session.get(url)
    if "Invalid Page" in resp.text[:2000] or "e-GP Invalid" in resp.text[:2000]:
        raise FetchError(f"Notice page not found (invalid page): {url}")
    notice = parse_notice(resp.text, tender_id=tender_id)
    notice["source_url"] = url
    return notice


def recent_window(days: int | None = None,
                  settings: Settings = SETTINGS) -> tuple[date, date]:
    """Publish-date window for an incremental run: [today-days, today]."""
    days = days if days is not None else settings.default_lookback_days
    today = date.today()
    return today - timedelta(days=days), today
