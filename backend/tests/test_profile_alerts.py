"""Company profile + alert prefs/matching tests."""

from backend.tests.helpers import (auth_headers, make_premium_user, make_user,
                      save_profile)


def test_profile_get_null_then_save(client, store):
    _, token = make_user(client, "prof@example.com")
    assert client.get("/api/v1/profile/company",
                      headers=auth_headers(token)).json() is None
    saved = save_profile(client, token)
    assert saved["company_name"] == "Test Builders Ltd"
    assert saved["categories"] == "Works, Construction"
    assert saved["annual_turnover_bdt"] == 5000000
    assert saved["similar_works"][0]["title"] == "School building"
    fetched = client.get("/api/v1/profile/company",
                         headers=auth_headers(token)).json()
    assert fetched["id"] == saved["id"]
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()
    assert me["has_profile"] is True


def test_profile_save_not_plan_gated(client, store):
    # Free users can save a profile.
    _, token = make_user(client, "proffree@example.com")
    resp = client.put("/api/v1/profile/company",
                      json={"company_name": "Free Co"},
                      headers=auth_headers(token))
    assert resp.status_code == 200


def test_profile_update_overwrites(client, store):
    _, token = make_user(client, "profup@example.com")
    save_profile(client, token)
    resp = client.put("/api/v1/profile/company",
                      json={"company_name": "Renamed Ltd",
                            "categories": ["Goods"]},
                      headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["company_name"] == "Renamed Ltd"
    assert resp.json()["categories"] == "Goods"
    assert resp.json()["annual_turnover_bdt"] is None


def test_profile_requires_company_name(client, store):
    _, token = make_user(client, "profreq@example.com")
    resp = client.put("/api/v1/profile/company", json={},
                      headers=auth_headers(token))
    assert resp.status_code == 422


def test_alerts_get_empty(client, store):
    _, token = make_user(client, "alert@example.com")
    body = client.get("/api/v1/alerts", headers=auth_headers(token)).json()
    assert body == {"prefs": None, "matches": []}


def test_alerts_save_and_match(client, store):
    _, token = make_premium_user(client, store, "alertmatch@example.com")
    resp = client.put("/api/v1/alerts",
                      json={"keywords": "paint", "categories": "Goods",
                            "districts": "Chittagong",
                            "organisations": "RHD"},
                      headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["keywords"] == "paint"
    body = client.get("/api/v1/alerts", headers=auth_headers(token)).json()
    assert body["prefs"]["keywords"] == "paint"
    assert len(body["matches"]) == 1
    assert body["matches"][0]["tender_id"] == 1002


def test_alerts_and_across_groups(client, store):
    _, token = make_premium_user(client, store, "alertand@example.com")
    # Keywords match 1002 but the district does not: AND => no match.
    # (Note "paint" also substring-matches "painting" in 1001, so use
    # a district neither tender has.)
    client.put("/api/v1/alerts",
               json={"keywords": "paint", "districts": "Sylhet"},
               headers=auth_headers(token))
    body = client.get("/api/v1/alerts", headers=auth_headers(token)).json()
    assert body["matches"] == []
    # Within one group, values are OR-ed.
    client.put("/api/v1/alerts",
               json={"keywords": "paint, school"},
               headers=auth_headers(token))
    body = client.get("/api/v1/alerts", headers=auth_headers(token)).json()
    assert {m["tender_id"] for m in body["matches"]} == {1001, 1002}


def test_alerts_read_not_gated(client, store):
    _, token = make_user(client, "alertfree@example.com")
    assert client.get("/api/v1/alerts",
                      headers=auth_headers(token)).status_code == 200
