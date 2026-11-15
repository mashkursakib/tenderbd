"""run_refresh tests — network calls monkeypatched, temp SQLite store.

Covers the callable refresh entrypoint the backend uses for
POST /refresh (tenderbd_scraper.scrape.run_refresh). No live
network access: fetch_rss_items, search_all and fetch_notice are
all stubbed out.
"""

import pytest

import tenderbd_scraper.scrape as scrape_mod
from tenderbd_scraper.config import Settings
from tenderbd_scraper.db import Store
from tenderbd_scraper.http import FetchError, PoliteSession


@pytest.fixture()
def store(tmp_path):
    settings = Settings()
    settings.database_url = ""
    settings.sqlite_path = str(tmp_path / "refresh.db")
    s = Store(settings)
    s.init_schema()
    yield s
    s.close()


@pytest.fixture()
def session():
    s = PoliteSession()
    yield s
    s.close()


def _row(tender_id):
    return {
        "tender_id": tender_id,
        "title": f"Tender {tender_id}",
        "status": "Live",
        "ministry": "Ministry of Test",
    }


def _detail(tender_id):
    row = _row(tender_id)
    row.update({
        "district": "Dhaka",
        "method": "OTM",
        "document_price_bdt": 2000,
        "emd_bdt": 150000,
    })
    return row


def _runs_logged(store):
    cur = store._execute("SELECT COUNT(*) FROM fetch_runs")
    return cur.fetchone()[0]


def test_run_refresh_happy_path(store, session, monkeypatch):
    monkeypatch.setattr(scrape_mod, "fetch_rss_items", lambda s: [])
    monkeypatch.setattr(scrape_mod, "search_all",
                        lambda s, **kw: [_row(1), _row(2)])
    monkeypatch.setattr(scrape_mod, "fetch_notice",
                        lambda s, tid, **kw: _detail(tid))

    summary = scrape_mod.run_refresh(store, session, days=2,
                                     max_pages=1, enrich_limit=1)

    assert summary["success"] is True
    assert summary["found"] == 2
    assert summary["new"] == 2
    assert summary["updated"] == 0
    assert summary["details_fetched"] == 1  # enrich_limit honoured
    assert summary["errors"] == 0
    assert summary["notes"] == ""
    assert _runs_logged(store) == 1
    # Both rows stored; exactly one enriched with district/EMD.
    assert store.tender_exists(1) and store.tender_exists(2)
    enriched = [t for t in (store.get_tender(1), store.get_tender(2))
                if t["detail_fetched_at"]]
    assert len(enriched) == 1
    assert enriched[0]["district"] == "Dhaka"
    assert enriched[0]["emd_bdt"] == 150000


def test_run_refresh_second_run_counts_updated(store, session, monkeypatch):
    monkeypatch.setattr(scrape_mod, "fetch_rss_items", lambda s: [])
    monkeypatch.setattr(scrape_mod, "search_all",
                        lambda s, **kw: [_row(1)])
    monkeypatch.setattr(scrape_mod, "fetch_notice",
                        lambda s, tid, **kw: _detail(tid))

    first = scrape_mod.run_refresh(store, session, enrich_limit=0)
    second = scrape_mod.run_refresh(store, session, enrich_limit=0)
    assert (first["new"], first["updated"]) == (1, 0)
    assert (second["new"], second["updated"]) == (0, 1)


def test_run_refresh_passes_max_pages(store, session, monkeypatch):
    seen = {}

    def fake_search(s, **kwargs):
        seen["max_pages"] = kwargs["settings"].max_search_pages_per_run
        return []

    monkeypatch.setattr(scrape_mod, "fetch_rss_items", lambda s: [])
    monkeypatch.setattr(scrape_mod, "search_all", fake_search)

    summary = scrape_mod.run_refresh(store, session, max_pages=3)
    assert summary["success"] is True
    assert seen["max_pages"] == 3


def test_run_refresh_search_failure(store, session, monkeypatch):
    monkeypatch.setattr(scrape_mod, "fetch_rss_items", lambda s: [])

    def boom(s, **kwargs):
        raise FetchError("Empty response from search servlet (page 1)")

    monkeypatch.setattr(scrape_mod, "search_all", boom)

    summary = scrape_mod.run_refresh(store, session)
    assert summary["success"] is False
    assert summary["found"] == 0
    assert summary["errors"] == 1
    assert "search servlet" in summary["notes"].lower()
    assert _runs_logged(store) == 1


def test_run_refresh_no_enrich(store, session, monkeypatch):
    monkeypatch.setattr(scrape_mod, "fetch_rss_items", lambda s: [])
    monkeypatch.setattr(scrape_mod, "search_all",
                        lambda s, **kw: [_row(1)])
    calls = []
    monkeypatch.setattr(scrape_mod, "fetch_notice",
                        lambda s, tid, **kw: calls.append(tid))

    summary = scrape_mod.run_refresh(store, session, enrich=False)
    assert summary["success"] is True
    assert summary["details_fetched"] == 0
    assert calls == []
