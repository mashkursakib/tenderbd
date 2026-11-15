"""Extractive summarize tests (SPEC.md section 8)."""

from tenderbd_scraper.http import FetchError
from backend.app.services import refresh as refresh_service
from backend.app.services.summarize import has_enough_text, summarize
from backend.tests.helpers import (LONG_DESCRIPTION, LONG_ELIGIBILITY, auth_headers,
                      make_premium_user)


def _tender(**overrides):
    tender = {
        "tender_id": 1, "title": "Construction of school building",
        "procuring_entity": "LGED, Dhaka", "district": "Dhaka",
        "method": "OTM", "proc_nature": "Works",
        "description": LONG_DESCRIPTION,
        "eligibility_text": LONG_ELIGIBILITY,
        "document_price_bdt": 2000, "emd_bdt": 100000,
        "close_dt": "2026-12-15T15:00:00+06:00",
        "doc_last_selling_dt": "2026-12-13T17:00:00+06:00",
    }
    tender.update(overrides)
    return tender


def test_summarize_english_shape():
    result = summarize(_tender(), lang="en")
    assert result["headline"] == "Construction of school building"
    assert "two-storey school building" in result["scope"]
    assert len(result["eligibility_points"]) >= 2
    assert any("trade licence" in p for p in result["eligibility_points"])
    # The turnover sentence is already an eligibility point, so it is
    # not repeated here; the equipment sentence comes from the scope.
    assert any("equipment" in p.lower()
               for p in result["key_requirements"])
    assert not set(result["key_requirements"]) & set(
        result["eligibility_points"])
    assert any("15 Dec 2026" in w for w in result["watch_outs"])
    assert any("BDT 100,000" in w for w in result["watch_outs"])


def test_summarize_only_uses_notice_facts():
    result = summarize(_tender(description="Short but sufficient text "
                               "about a bridge project in Sylhet. "
                               "The work is straightforward.",
                               eligibility_text=""), lang="en")
    assert "Sylhet" in result["scope"] or "bridge" in result["scope"]
    # No invented figures: the only numbers come from the notice.
    assert "BDT" not in result["scope"]


def test_summarize_bangla_labels():
    result = summarize(_tender(), lang="bn")
    # Headline stays as printed; composed lines use Bangla labels.
    assert result["headline"] == "Construction of school building"
    assert any("জমা দেওয়ার শেষ তারিখ" in w
               for w in result["watch_outs"])
    assert any("টেন্ডার সিকিউরিটি" in w for w in result["watch_outs"])
    # Facts (dates, figures) stay as printed.
    assert any("15 Dec 2026" in w for w in result["watch_outs"])


def test_has_enough_text_guard():
    assert has_enough_text(_tender()) is True
    assert has_enough_text(_tender(description="Poles.",
                                   eligibility_text="")) is False
    assert has_enough_text(_tender(description="",
                                   eligibility_text="")) is False


def test_summarize_api_en(client, store):
    _, token = make_premium_user(client, store, "sumen@example.com")
    resp = client.post("/api/v1/tenders/1001/summarize",
                       json={"lang": "en"}, headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["headline"] == "Construction of school building"
    assert body["eligibility_points"]
    assert body["watch_outs"]


def test_summarize_api_bn(client, store):
    _, token = make_premium_user(client, store, "sumbn@example.com")
    resp = client.post("/api/v1/tenders/1001/summarize",
                       json={"lang": "bn"}, headers=auth_headers(token))
    assert resp.status_code == 200
    assert any("জমা দেওয়ার শেষ তারিখ" in w
               for w in resp.json()["watch_outs"])


def test_summarize_api_too_little_text(client, store, monkeypatch):
    _, token = make_premium_user(client, store, "sumlittle@example.com")

    def boom(session, tender_id, settings=None):
        raise FetchError("portal down")

    # 1005 is unenriched; the enrich attempt fails and the stored
    # short text triggers the guard.
    monkeypatch.setattr(refresh_service, "fetch_notice", boom)
    resp = client.post("/api/v1/tenders/1005/summarize",
                       json={"lang": "en"}, headers=auth_headers(token))
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "This notice publishes too little text on the public page to "
        "summarize.")


def test_summarize_api_bad_lang(client, store):
    _, token = make_premium_user(client, store, "sumlang@example.com")
    resp = client.post("/api/v1/tenders/1001/summarize",
                       json={"lang": "fr"}, headers=auth_headers(token))
    assert resp.status_code == 422
