"""Store tests — SQLite backend (Postgres needs a live server)."""

import pytest

from tenderbd_scraper.config import Settings
from tenderbd_scraper.db import Store


@pytest.fixture()
def store(tmp_path):
    settings = Settings()
    settings.database_url = ""
    settings.sqlite_path = str(tmp_path / "test.db")
    s = Store(settings)
    s.init_schema()
    yield s
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
        "source_url": f"https://eprocure.gov.bd/resources/common/ViewTender.jsp?id={tender_id}&h=t",
    }
    row.update(overrides)
    return row


def test_upsert_new_then_updated(store):
    assert store.upsert_tender(_row()) == "new"
    assert store.upsert_tender(_row(title="Changed title")) == "updated"
    tender = store.get_tender(1363322)
    assert tender["title"] == "Changed title"
    assert tender["first_seen_at"]  # preserved across updates


def test_search_filters(store):
    store.upsert_tender(_row(1, district="Dhaka", method="OTM"))
    store.upsert_tender(_row(2, district="Chattogram", method="LTM"))
    rows, total = store.search_tenders(district="Dhaka")
    assert total == 1 and rows[0]["tender_id"] == 1
    rows, total = store.search_tenders(query="Test tender")
    assert total == 2
    rows, total = store.search_tenders(method="LTM")
    assert total == 1 and rows[0]["tender_id"] == 2


def test_stats(store):
    store.upsert_tender(_row(1))
    stats = store.stats()
    assert stats["total_tenders"] == 1
