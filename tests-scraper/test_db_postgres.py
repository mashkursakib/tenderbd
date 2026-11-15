"""Store tests — PostgreSQL backend.

Skipped unless TENDERBD_TEST_DATABASE_URL is set. Point it at a
THROWAWAY database: the tests TRUNCATE tenders and fetch_runs in it.

    TENDERBD_TEST_DATABASE_URL=postgresql://user:pass@host:5432/db \\
        pytest tests-scraper/test_db_postgres.py

These tests exist because the Postgres branch of Store was never
live-tested in the original repo: dict rows do not support index
access, so tenders_needing_details, search_tenders (COUNT) and
stats() all raised KeyError on Postgres until fixed (2026-11-15).
"""

import os
from datetime import datetime, timezone

import pytest

from tenderbd_scraper.config import Settings
from tenderbd_scraper.db import Store

PG_URL = os.environ.get("TENDERBD_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="TENDERBD_TEST_DATABASE_URL not set")


@pytest.fixture()
def store():
    settings = Settings()
    settings.database_url = PG_URL
    s = Store(settings)
    assert s.is_postgres
    s.init_schema()
    s._execute("TRUNCATE tenders, fetch_runs")
    yield s
    s._execute("TRUNCATE tenders, fetch_runs")
    s.close()


def _row(tender_id=1363322, **overrides):
    row = {
        "tender_id": tender_id,
        "ref_no": "REF-1",
        "title": "Test tender",
        "status": "Live",
        "ministry": "Ministry of Test",
        "district": "Dhaka",
        "method": "OTM",
        "close_dt": datetime(2026, 12, 21, 14, 0, tzinfo=timezone.utc),
        "lots": [{"lot_no": "Lot-1", "security_bdt": 1000}],
        "source_url": f"https://eprocure.gov.bd/resources/common/ViewTender.jsp?id={tender_id}&h=t",
    }
    row.update(overrides)
    return row


def test_upsert_new_then_updated_preserves_first_seen(store):
    assert store.upsert_tender(_row()) == "new"
    first_seen = store.get_tender(1363322)["first_seen_at"]
    assert store.upsert_tender(_row(title="Changed title")) == "updated"
    tender = store.get_tender(1363322)
    assert tender["title"] == "Changed title"
    assert tender["first_seen_at"] == first_seen
    # JSONB lots and TIMESTAMPTZ datetimes round-trip.
    assert tender["lots"] == [{"lot_no": "Lot-1", "security_bdt": 1000}]
    assert tender["close_dt"].startswith("2026-12-21")


def test_tenders_needing_details(store):
    store.upsert_tender(_row(1))
    store.upsert_tender(_row(2), detail_fetched=True)
    assert store.tenders_needing_details(10) == [1]


def test_search_tenders_count_and_filters(store):
    store.upsert_tender(_row(1, district="Dhaka", method="OTM"))
    store.upsert_tender(_row(2, district="Chattogram", method="LTM"))
    rows, total = store.search_tenders(district="Dhaka")
    assert total == 1 and rows[0]["tender_id"] == 1
    rows, total = store.search_tenders(query="Test tender")
    assert total == 2
    rows, total = store.search_tenders(method="LTM")
    assert total == 1 and rows[0]["tender_id"] == 2


def test_stats_and_log_run(store):
    store.upsert_tender(_row(1))
    stats = store.stats()
    assert stats["total_tenders"] == 1
    assert stats["open_tenders"] == 1
    assert stats["last_seen_at"]
    store.log_run(source="run", tenders_found=1, tenders_new=1)
    cur = store._execute(
        "SELECT source, tenders_found, tenders_new FROM fetch_runs")
    run = cur.fetchone()
    assert run["source"] == "run"
    assert run["tenders_found"] == 1
    assert run["tenders_new"] == 1
