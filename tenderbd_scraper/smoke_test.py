"""Live smoke test — verifies the e-GP portal is reachable and the
scraper's three data paths behave as expected:

1. RSS feeds (expected: currently 404 on the live portal — reported,
   not fatal).
2. Search servlet POST (expected: 10 rows + total pages).
3. One notice detail page (expected: full field set).

Writes nothing to the database. Exits 0 if search + notice work
(RSS failure alone does not fail the test), 1 otherwise.

Usage (from the repo root, venv active):
    python -m tenderbd_scraper.smoke_test
    python -m tenderbd_scraper.smoke_test --tender-id 1361116 --days 2
"""

from __future__ import annotations

import argparse

from .config import SETTINGS  # noqa: F401  (kept for parity with the old script)
from .fetcher import fetch_notice, recent_window, search_page
from .http import FetchError, PoliteSession
from .rss import fetch_rss_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tender-id", type=int, default=1361116)
    parser.add_argument("--days", type=int, default=2)
    args = parser.parse_args()

    session = PoliteSession()
    ok = True
    try:
        print("== 1. RSS feeds ==")
        items = fetch_rss_items(session)
        if items:
            print(f"OK: {len(items)} RSS items")
        else:
            print("NOTE: no RSS items (feeds return 404 on the live "
                  "portal as of 2026-11-14; search poll is the data path)")

        print("\n== 2. Search servlet ==")
        pub_from, pub_to = recent_window(args.days)
        try:
            page = search_page(session, 1, pub_from=pub_from, pub_to=pub_to)
            rows = page["tenders"]
            print(f"OK: page 1 returned {len(rows)} rows, "
                  f"total_pages={page['total_pages']}")
            if rows:
                r = rows[0]
                print(f"   first row: id={r['tender_id']} "
                      f"title={(r['title'] or '')[:60]!r} "
                      f"close={r['close_dt']}")
            if not rows:
                print("WARN: search returned 0 rows for the window "
                      f"{pub_from}..{pub_to}")
        except FetchError as exc:
            print(f"FAIL: search servlet: {exc}")
            ok = False

        print("\n== 3. Notice detail ==")
        try:
            notice = fetch_notice(session, args.tender_id)
            filled = sum(1 for v in notice.values()
                         if v not in (None, "", [], {}))
            print(f"OK: notice {args.tender_id} parsed, "
                  f"{filled} fields filled")
            print(f"   ministry={notice.get('ministry')}")
            print(f"   district={notice.get('district')}, "
                  f"method={notice.get('method')}")
            print(f"   doc price={notice.get('document_price_bdt')}, "
                  f"EMD={notice.get('emd_bdt')}, "
                  f"lots={len(notice.get('lots') or [])}")
            print(f"   close={notice.get('close_dt')}")
        except FetchError as exc:
            print(f"FAIL: notice detail: {exc}")
            ok = False
    finally:
        session.close()

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
