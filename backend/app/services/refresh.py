"""Refresh / enrich paths.

Read-only use of the tenderbd_scraper package: search polling and
notice enrichment reuse fetcher + Store; nothing in the scraper is
copied or rewritten. The RSS hint step from the CLI run is skipped
here (the feeds return 404 on the live portal; the search poll is
the reliable data path).

run_refresh(days, max_pages, enrich_limit) mirrors the CLI `run`
steps with the API's caps and returns a summary dict. enrich_tender
fetches one public notice page for the detail endpoint; failures
raise FetchError and the caller falls back to the stored row.
"""

from __future__ import annotations

import dataclasses
import logging

from tenderbd_scraper.config import SETTINGS
from tenderbd_scraper.fetcher import (fetch_notice, notice_source_url,
                                      recent_window, search_all)
from tenderbd_scraper.http import FetchError, PoliteSession

from ..db import AppStore

log = logging.getLogger(__name__)


def run_refresh(store: AppStore, *, days: int = 3, max_pages: int = 5,
                enrich_limit: int = 12) -> dict:
    """Synchronous refresh: search poll + upsert + enrichment."""
    settings = dataclasses.replace(
        SETTINGS,
        max_search_pages_per_run=max_pages,
        max_detail_fetches_per_run=enrich_limit)
    session = PoliteSession(settings=settings)
    errors = 0
    try:
        pub_from, pub_to = recent_window(days, settings=settings)
        try:
            rows = search_all(session, settings=settings,
                              pub_from=pub_from, pub_to=pub_to)
        except FetchError as exc:
            log.error("Refresh search poll failed: %s", exc)
            store.log_run(source="api-refresh", errors=1, notes=str(exc))
            raise
        new, updated = 0, 0
        for row in rows:
            is_new = not store.tender_exists(row["tender_id"])
            row["source_url"] = notice_source_url(row["tender_id"],
                                                  settings=settings)
            store.upsert_tender(row)
            if is_new:
                new += 1
            else:
                updated += 1
        details = 0
        todo = store.tenders_needing_details(enrich_limit)
        for tender_id in todo:
            try:
                notice = fetch_notice(session, tender_id,
                                      settings=settings)
                store.upsert_tender(notice, detail_fetched=True)
                details += 1
            except FetchError as exc:
                log.warning("Detail fetch failed for %s: %s",
                            tender_id, exc)
                errors += 1
        store.log_run(source="api-refresh", tenders_found=len(rows),
                      tenders_new=new, tenders_updated=updated,
                      details_fetched=details, errors=errors)
        return {"tenders_found": len(rows), "tenders_new": new,
                "tenders_updated": updated, "details_fetched": details,
                "errors": errors}
    finally:
        session.close()


def enrich_tender(store: AppStore, tender_id: int) -> dict:
    """Fetch one public notice page and store it (detail_fetched)."""
    session = PoliteSession()
    try:
        notice = fetch_notice(session, tender_id)
    finally:
        session.close()
    store.upsert_tender(notice, detail_fetched=True)
    return store.get_tender(tender_id)
