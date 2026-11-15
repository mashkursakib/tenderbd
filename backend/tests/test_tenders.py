"""Tender list filters + facets, detail, enrich, stats, health."""

from tenderbd_scraper.http import FetchError
from backend.app.services import refresh as refresh_service
from backend.tests.helpers import auth_headers, make_premium_user, make_user


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "sqlite"}
    assert client.get("/health").json()["status"] == "ok"


def test_stats(client):
    body = client.get("/api/v1/stats").json()
    assert body["total"] == 5
    assert body["open_now"] == 4  # 1003 is closed
    assert body["last_run"] is None


def test_list_all_and_facets(client):
    body = client.get("/api/v1/tenders").json()
    assert body["total"] == 5
    assert len(body["tenders"]) == 5
    assert body["work_type_counts"] == {
        "Works": 2, "Goods": 1, "Services": 1, "Consultancy": 1}
    assert body["department_counts"] == {
        "LGED": 1, "RHD": 1, "PWD": 1, "BWDB": 1, "BREB": 1}
    assert body["districts"] == ["Chittagong", "Dhaka", "Khulna",
                                 "Rajshahi", "Sylhet"]
    # Chittagong is aliased to the Chattogram division.
    assert body["divisions"] == ["Chattogram", "Dhaka", "Khulna",
                                 "Rajshahi", "Sylhet"]
    assert body["methods"] == ["OTM", "QCBS", "RFQ"]


def test_list_default_sort_closing_soonest(client):
    ids = [t["tender_id"] for t in client.get("/api/v1/tenders").json()["tenders"]]
    # 1003 already closed (past), then 1005 (+2d), 1002 (+3d), 1001, 1004.
    assert ids == [1003, 1005, 1002, 1001, 1004]


def test_list_sort_options(client):
    base = "/api/v1/tenders"
    newest = [t["tender_id"] for t in
              client.get(base, params={"sort": "newest_id"}).json()["tenders"]]
    assert newest == [1005, 1004, 1003, 1002, 1001]
    high = [t["tender_id"] for t in
            client.get(base, params={"sort": "value_high"}).json()["tenders"]]
    assert high == [1004, 1001, 1002, 1005, 1003]  # 1003 has no EMD
    low = [t["tender_id"] for t in
           client.get(base, params={"sort": "value_low"}).json()["tenders"]]
    assert low == [1005, 1002, 1001, 1004, 1003]
    published = [t["tender_id"] for t in
                 client.get(base, params={"sort": "published"}).json()["tenders"]]
    assert published[0] in (1002, 1005)  # both published yesterday
    assert published[-1] == 1003
    assert client.get(base, params={"sort": "bogus"}).status_code == 400


def test_list_keyword_search(client):
    body = client.get("/api/v1/tenders", params={"q": "paint"}).json()
    assert body["total"] == 1
    assert body["tenders"][0]["tender_id"] == 1002
    body = client.get("/api/v1/tenders", params={"q": "1004"}).json()
    assert body["total"] == 1
    assert client.get("/api/v1/tenders",
                      params={"q": "zzz-no-match"}).json()["total"] == 0


def test_list_work_type_filter(client):
    body = client.get("/api/v1/tenders",
                      params={"work_types[]": ["Works"]}).json()
    assert body["total"] == 2
    assert {t["tender_id"] for t in body["tenders"]} == {1001, 1005}
    # Plain (non-bracketed) param form also works.
    body = client.get("/api/v1/tenders",
                      params={"work_types": ["Goods", "Services"]}).json()
    assert body["total"] == 2
    assert {t["tender_id"] for t in body["tenders"]} == {1002, 1003}


def test_list_department_filter(client):
    body = client.get("/api/v1/tenders",
                      params={"departments[]": ["LGED", "RHD"]}).json()
    assert body["total"] == 2
    assert {t["tender_id"] for t in body["tenders"]} == {1001, 1002}


def test_list_division_and_district_filter(client):
    body = client.get("/api/v1/tenders",
                      params={"division": "Chattogram"}).json()
    assert body["total"] == 1
    assert body["tenders"][0]["tender_id"] == 1002
    # District filter understands the alias too.
    body = client.get("/api/v1/tenders",
                      params={"district": "Chattogram"}).json()
    assert body["total"] == 1
    assert body["tenders"][0]["tender_id"] == 1002
    body = client.get("/api/v1/tenders",
                      params={"district": "Dhaka"}).json()
    assert body["total"] == 1


def test_list_value_filter_on_emd(client):
    body = client.get("/api/v1/tenders",
                      params={"value_min": 60000}).json()
    assert {t["tender_id"] for t in body["tenders"]} == {1001, 1004}
    body = client.get("/api/v1/tenders",
                      params={"value_min": 20000,
                              "value_max": 60000}).json()
    assert {t["tender_id"] for t in body["tenders"]} == {1002}
    # Tenders without EMD never match a value filter.
    body = client.get("/api/v1/tenders",
                      params={"value_min": 0}).json()
    assert 1003 not in {t["tender_id"] for t in body["tenders"]}


def test_list_status_filter(client):
    base = "/api/v1/tenders"
    # "active" matches any non-closed bucket.
    body = client.get(base, params={"statuses[]": ["active"]}).json()
    assert {t["tender_id"] for t in body["tenders"]} == {1001, 1002, 1004, 1005}
    body = client.get(base, params={"statuses[]": ["closing_soon"]}).json()
    assert {t["tender_id"] for t in body["tenders"]} == {1002, 1005}
    body = client.get(base, params={"statuses[]": ["closed"]}).json()
    assert {t["tender_id"] for t in body["tenders"]} == {1003}
    body = client.get(base, params={"statuses[]": ["closed", "active"]}).json()
    assert body["total"] == 5


def test_list_method_filter_and_pagination(client):
    body = client.get("/api/v1/tenders", params={"method": "OTM"}).json()
    assert {t["tender_id"] for t in body["tenders"]} == {1001, 1003, 1005}
    page1 = client.get("/api/v1/tenders",
                       params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/api/v1/tenders",
                       params={"limit": 2, "offset": 2}).json()
    assert page1["total"] == 5
    assert len(page1["tenders"]) == 2
    assert len(page2["tenders"]) == 2
    assert {t["tender_id"] for t in page1["tenders"]} .isdisjoint(
        {t["tender_id"] for t in page2["tenders"]})


def test_list_classification_fields(client):
    body = client.get("/api/v1/tenders", params={"q": "school"}).json()
    tender = body["tenders"][0]
    assert tender["work_type"] == "Works"
    assert tender["departments"] == ["LGED"]
    assert tender["computed_division"] == "Dhaka"
    assert tender["status_bucket"] == "active"


def test_get_tender_detail(client):
    body = client.get("/api/v1/tenders/1001").json()
    assert body["tender_id"] == 1001
    assert body["work_type"] == "Works"
    assert body["emd_bdt"] == 100000
    assert client.get("/api/v1/tenders/9999999").status_code == 404


def test_get_tender_enriches_on_first_open(client, store, monkeypatch):
    def fake_fetch_notice(session, tender_id, settings=None):
        assert tender_id == 1005
        return {"tender_id": 1005,
                "title": "Supply of electric poles (enriched)",
                "description": "Enriched description from the notice page.",
                "district": "Rajshahi", "emd_bdt": 12000}

    monkeypatch.setattr(refresh_service, "fetch_notice", fake_fetch_notice)
    body = client.get("/api/v1/tenders/1005").json()
    assert body["title"] == "Supply of electric poles (enriched)"
    assert body["emd_bdt"] == 12000
    row = store.get_tender(1005)
    assert row["detail_fetched_at"] is not None


def test_get_tender_enrich_failure_returns_stored(client, monkeypatch):
    def boom(session, tender_id, settings=None):
        raise FetchError("portal down")

    monkeypatch.setattr(refresh_service, "fetch_notice", boom)
    body = client.get("/api/v1/tenders/1005").json()
    assert body["tender_id"] == 1005
    assert body["title"] == "Supply of electric poles"
    assert body["detail_fetched_at"] is None


def test_get_tender_no_refetch_when_enriched(client, store, monkeypatch):
    calls = []

    def fake_fetch_notice(session, tender_id, settings=None):
        calls.append(tender_id)
        raise FetchError("should not be called")

    monkeypatch.setattr(refresh_service, "fetch_notice", fake_fetch_notice)
    resp = client.get("/api/v1/tenders/1001")
    assert resp.status_code == 200
    assert calls == []
