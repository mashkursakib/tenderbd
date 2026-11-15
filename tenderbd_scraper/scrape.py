"""TenderBD scraper CLI — the scheduled job entry point.

Usage (from the repo root, venv active):
    python -m tenderbd_scraper.scrape run            # incremental run
    python -m tenderbd_scraper.scrape run --days 7   # wider window
    python -m tenderbd_scraper.scrape rss            # RSS check only
    python -m tenderbd_scraper.scrape search --days 2
    python -m tenderbd_scraper.scrape notice 1361116
    python -m tenderbd_scraper.scrape init-db

What `run` does, in order:
1. RSS check (best-effort; currently 404 on the live portal, so this
   usually finds nothing and the run continues).
2. Search poll over the publish-date window (default: last 2 days),
   paging through TenderDetailsServlet results.
3. Upsert every row into the store (dedupe by Tender ID).
4. Enrich NEW tenders with their full notice page (up to the per-run
   limit), so eligibility text, document price, EMD and lots are stored.
5. Log the run in fetch_runs and print a summary.

Public data only. No login, no credentials, no tender documents.

Callable entrypoint for the backend (POST /refresh):
    from tenderbd_scraper.scrape import run_refresh
    summary = run_refresh(store, session, days=3, max_pages=5,
                          enrich_limit=12)
    # -> {"found", "new", "updated", "details_fetched", "errors",
    #     "notes", "success"}
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from datetime import date

from . import __version__
from .config import SETTINGS
from .db import Store
from .fetcher import (fetch_notice, notice_source_url, recent_window,
                      search_all)
from .http import FetchError, PoliteSession
from .rss import fetch_rss_items

log = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S")


def cmd_init_db(store: Store) -> int:
    store.init_schema()
    print("Database schema ready "
          f"({'PostgreSQL' if store.is_postgres else 'SQLite'}).")
    return 0


def cmd_rss(session: PoliteSession) -> int:
    items = fetch_rss_items(session)
    print(f"RSS: {len(items)} items "
          f"({sum(1 for i in items if i['tender_id'])} with tender ids)")
    for item in items[:20]:
        print(f"  {item['tender_id'] or '-':>8}  {item['title'][:90]}")
    if not items:
        print("No RSS items — the e-GP feeds currently return 404, "
              "so the search poll is the data path (see README).")
    return 0


def cmd_search(session: PoliteSession, store: Store, days: int) -> int:
    pub_from, pub_to = recent_window(days)
    print(f"Searching notices published {pub_from} .. {pub_to} ...")
    rows = search_all(session, pub_from=pub_from, pub_to=pub_to)
    new, updated = _store_rows(store, rows)
    print(f"Search: {len(rows)} rows, {new} new, {updated} updated.")
    return 0


def _store_rows(store: Store, rows: list[dict]) -> tuple[int, int]:
    new, updated = 0, 0
    for row in rows:
        row["source_url"] = notice_source_url(row["tender_id"])
        result = store.upsert_tender(row)
        if result == "new":
            new += 1
        else:
            updated += 1
    return new, updated


def cmd_notice(session: PoliteSession, store: Store, tender_id: int) -> int:
    notice = fetch_notice(session, tender_id)
    result = store.upsert_tender(notice, detail_fetched=True)
    print(f"Notice {tender_id}: stored ({result}).")
    print(f"  Title: {(notice.get('title') or '')[:100]}")
    print(f"  PE: {notice.get('procuring_entity')}")
    print(f"  District: {notice.get('district')}, "
          f"Method: {notice.get('method')}, "
          f"Doc price: {notice.get('document_price_bdt')}, "
          f"EMD: {notice.get('emd_bdt')}")
    print(f"  Close: {notice.get('close_dt')}")
    return 0


def run_refresh(store: Store, session: PoliteSession, days: int = 3,
                max_pages: int = 5, enrich_limit: int = 12,
                enrich: bool = True) -> dict:
    """Callable refresh entrypoint for the backend (POST /refresh).

    Runs one incremental refresh: an RSS hint (best-effort), a search
    poll over the publish-date window, upsert of every row found, then
    notice-detail enrichment for tenders that have none yet (capped by
    enrich_limit, so tenders skipped by one run are picked up later).

    The caps default to the API contract (SPEC section 4): days=3,
    max_pages=5, enrich_limit=12. The CLI passes the wider settings
    caps instead (see cmd_run).

    Returns a summary dict:
        {"found": int, "new": int, "updated": int,
         "details_fetched": int, "errors": int, "notes": str,
         "success": bool}
    The run is logged in fetch_runs. Nothing is raised: a failed
    search poll is reported as success=False with the error in notes.
    """
    store.init_schema()  # safe: CREATE TABLE IF NOT EXISTS
    notes: list[str] = []
    errors = 0
    # 1. RSS (best-effort hint only).
    rss_ids: set[int] = set()
    try:
        for item in fetch_rss_items(session):
            if item["tender_id"]:
                rss_ids.add(item["tender_id"])
    except Exception as exc:  # noqa: BLE001 - RSS must never break a run
        log.warning("RSS check failed: %s", exc)
        errors += 1
        notes.append(f"RSS check failed: {exc}")
    log.info("RSS hint: %d tender ids", len(rss_ids))

    # 2. Search poll over the window.
    pub_from, pub_to = recent_window(days)
    log.info("Polling search for notices published %s .. %s",
             pub_from, pub_to)
    search_settings = dataclasses.replace(
        session.settings, max_search_pages_per_run=max_pages)
    try:
        rows = search_all(session, settings=search_settings,
                          pub_from=pub_from, pub_to=pub_to)
    except FetchError as exc:
        log.error("Search poll failed: %s", exc)
        store.log_run(source="search", errors=1, notes=str(exc))
        notes.append(f"Search poll failed: {exc}")
        return {"found": 0, "new": 0, "updated": 0, "details_fetched": 0,
                "errors": errors + 1, "notes": "; ".join(notes),
                "success": False}
    found_ids = {r["tender_id"] for r in rows}
    log.info("Search found %d tenders (%d also seen via RSS)",
             len(rows), len(found_ids & rss_ids))

    # 3. Upsert rows.
    new, updated = 0, 0
    for row in rows:
        is_new = not store.tender_exists(row["tender_id"])
        row["source_url"] = notice_source_url(row["tender_id"])
        store.upsert_tender(row)
        if is_new:
            new += 1
        else:
            updated += 1

    # 4. Enrich tenders with full notice pages (capped per run). The
    # queue is "tenders without a fetched notice page", so tenders
    # skipped by a previous run's cap are picked up by later runs.
    details = 0
    if enrich:
        todo = store.tenders_needing_details(enrich_limit)
        log.info("Enrichment queue: %d tenders without notice details "
                 "(limit %d this run)", len(todo), enrich_limit)
        for tender_id in todo:
            try:
                notice = fetch_notice(session, tender_id,
                                      settings=search_settings)
                store.upsert_tender(notice, detail_fetched=True)
                details += 1
            except FetchError as exc:
                log.warning("Detail fetch failed for %s: %s", tender_id, exc)
                errors += 1
                notes.append(f"Detail fetch failed for {tender_id}: {exc}")
        log.info("Enriched %d/%d tenders with notice details",
                 details, len(todo))

    store.log_run(source="run", tenders_found=len(rows),
                  tenders_new=new, tenders_updated=updated,
                  details_fetched=details, errors=errors,
                  notes="; ".join(notes))
    return {"found": len(rows), "new": new, "updated": updated,
            "details_fetched": details, "errors": errors,
            "notes": "; ".join(notes), "success": True}


def cmd_run(session: PoliteSession, store: Store, days: int,
            enrich: bool = True) -> int:
    """Full incremental run: RSS hint + search poll + detail enrichment.

    Thin CLI wrapper over run_refresh with the wider settings caps.
    """
    summary = run_refresh(
        store, session, days=days,
        max_pages=SETTINGS.max_search_pages_per_run,
        enrich_limit=SETTINGS.max_detail_fetches_per_run,
        enrich=enrich)
    if not summary["success"]:
        print(f"ERROR: search poll failed: {summary['notes']}")
        return 1
    print(f"Run complete: {summary['found']} found, {summary['new']} new, "
          f"{summary['updated']} updated, "
          f"{summary['details_fetched']} details fetched, "
          f"{summary['errors']} errors.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tenderbd-scraper",
        description="TenderBD e-GP scraper — public notices only, "
                    "no login, no credentials.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--log-level", default=SETTINGS.log_level,
                        help="DEBUG, INFO, WARNING, ERROR")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create database tables.")
    sub.add_parser("rss", help="Check the official RSS feeds.")
    p_search = sub.add_parser("search", help="Poll the public search.")
    p_search.add_argument("--days", type=int,
                          default=SETTINGS.default_lookback_days,
                          help="Publish-date lookback window (default 2)")
    p_notice = sub.add_parser("notice", help="Fetch one notice by ID.")
    p_notice.add_argument("tender_id", type=int)
    p_run = sub.add_parser("run", help="Full incremental run.")
    p_run.add_argument("--days", type=int,
                       default=SETTINGS.default_lookback_days,
                       help="Publish-date lookback window (default 2)")
    p_run.add_argument("--no-enrich", action="store_true",
                       help="Skip notice-detail enrichment")

    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    store = Store()
    session = PoliteSession()
    try:
        if args.command == "init-db":
            return cmd_init_db(store)
        store.init_schema()  # safe: CREATE TABLE IF NOT EXISTS
        if args.command == "rss":
            return cmd_rss(session)
        if args.command == "search":
            return cmd_search(session, store, args.days)
        if args.command == "notice":
            return cmd_notice(session, store, args.tender_id)
        if args.command == "run":
            return cmd_run(session, store, args.days,
                           enrich=not args.no_enrich)
    except FetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
