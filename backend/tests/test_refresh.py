"""Refresh endpoint tests. The fetcher is mocked; the live e-GP
portal is never hit."""

from tenderbd_scraper.http import FetchError
from backend.app.services import refresh as refresh_service
from backend.tests.helpers import (REFRESH_TOKEN, auth_headers,
                                   make_admin, make_user)


def test_refresh_requires_token(client):
    resp = client.post("/api/v1/refresh", json={})
    assert resp.status_code == 403
    resp = client.post("/api/v1/refresh", json={},
                       headers={"X-Refresh-Token": "wrong"})
    assert resp.status_code == 403


def test_refresh_unconfigured(client, monkeypatch):
    monkeypatch.delenv("REFRESH_TOKEN")
    resp = client.post("/api/v1/refresh", json={},
                       headers={"X-Refresh-Token": REFRESH_TOKEN})
    assert resp.status_code == 503


def test_refresh_success_with_mocked_fetcher(client, store, monkeypatch):
    def fake_search_all(session, settings=None, **filters):
        return [
            {"tender_id": 2001, "title": "New mocked tender",
             "status": "Live", "proc_nature": "Works",
             "district": "Dhaka", "method": "OTM"},
            {"tender_id": 1001, "title": "Construction of school building",
             "status": "Live"},
        ]

    def fake_fetch_notice(session, tender_id, settings=None):
        return {"tender_id": tender_id,
                "description": "Mocked notice detail text.",
                "emd_bdt": 777}

    monkeypatch.setattr(refresh_service, "search_all", fake_search_all)
    monkeypatch.setattr(refresh_service, "fetch_notice", fake_fetch_notice)
    resp = client.post("/api/v1/refresh",
                       json={"days": 3, "max_pages": 5,
                             "enrich_limit": 12},
                       headers={"X-Refresh-Token": REFRESH_TOKEN})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tenders_found"] == 2
    assert body["tenders_new"] == 1
    assert body["tenders_updated"] == 1
    # Enrichment ran over tenders without details (2001 + 1005).
    assert body["details_fetched"] == 2
    assert body["errors"] == 0
    assert store.get_tender(2001) is not None
    assert store.get_tender(2001)["emd_bdt"] == 777
    last_run = store.last_run()
    assert last_run is not None
    assert last_run["source"] == "api-refresh"
    assert last_run["tenders_new"] == 1


def test_refresh_search_failure_502(client, store, monkeypatch):
    def boom(session, settings=None, **filters):
        raise FetchError("portal down")

    monkeypatch.setattr(refresh_service, "search_all", boom)
    resp = client.post("/api/v1/refresh", json={},
                       headers={"X-Refresh-Token": REFRESH_TOKEN})
    assert resp.status_code == 502
    assert store.last_run() is not None
    assert store.last_run()["errors"] == 1


def test_refresh_enrich_failure_counted(client, store, monkeypatch):
    def fake_search_all(session, settings=None, **filters):
        return []

    def boom(session, tender_id, settings=None):
        raise FetchError("notice gone")

    monkeypatch.setattr(refresh_service, "search_all", fake_search_all)
    monkeypatch.setattr(refresh_service, "fetch_notice", boom)
    resp = client.post("/api/v1/refresh", json={"enrich_limit": 1},
                       headers={"X-Refresh-Token": REFRESH_TOKEN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenders_found"] == 0
    # 1005 still needs details; its enrich attempt failed.
    assert body["details_fetched"] == 0
    assert body["errors"] == 1


def test_refresh_admin_session_without_token(client, store, monkeypatch):
    """A signed-in admin may refresh from the UI without the shared
    token (the browser cannot carry it)."""
    def fake_search_all(session, settings=None, **filters):
        return []

    monkeypatch.setattr(refresh_service, "search_all", fake_search_all)
    _, token = make_admin(client, store)
    resp = client.post("/api/v1/refresh", json={"enrich_limit": 0},
                       headers=auth_headers(token))
    assert resp.status_code == 200, resp.text


def test_refresh_non_admin_session_denied(client, store):
    _, token = make_user(client, "plain@example.com")
    resp = client.post("/api/v1/refresh", json={},
                       headers=auth_headers(token))
    assert resp.status_code == 403


def test_refresh_admin_session_when_unconfigured(client, store, monkeypatch):
    """Admin refresh does not need REFRESH_TOKEN to be set."""
    monkeypatch.delenv("REFRESH_TOKEN")

    def fake_search_all(session, settings=None, **filters):
        return []

    monkeypatch.setattr(refresh_service, "search_all", fake_search_all)
    _, token = make_admin(client, store)
    resp = client.post("/api/v1/refresh", json={"enrich_limit": 0},
                       headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
