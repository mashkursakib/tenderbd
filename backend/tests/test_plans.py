"""Plan-gate tests: Premium and Pro enforcement, Free favourite cap."""

from backend.tests.helpers import (auth_headers, make_premium_user, make_pro_user,
                      make_user, save_profile)


def test_free_cannot_evaluate(client, store):
    _, token = make_user(client, "free-eval@example.com")
    resp = client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == (
        "This is a Premium feature. Your current plan is Free. "
        "Upgrade from the Plans tab to unlock it.")


def test_free_cannot_summarize(client, store):
    _, token = make_user(client, "free-sum@example.com")
    resp = client.post("/api/v1/tenders/1001/summarize",
                       json={"lang": "en"}, headers=auth_headers(token))
    assert resp.status_code == 403
    assert "Premium feature" in resp.json()["detail"]


def test_free_cannot_upload_document(client, store):
    _, token = make_user(client, "free-doc@example.com")
    resp = client.post("/api/v1/documents",
                       files={"file": ("licence.pdf", b"fake-pdf",
                                       "application/pdf")},
                       data={"doc_type": "Trade licence"},
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert "Premium feature" in resp.json()["detail"]


def test_free_cannot_save_alerts(client, store):
    _, token = make_user(client, "free-alert@example.com")
    resp = client.put("/api/v1/alerts", json={"keywords": "road"},
                      headers=auth_headers(token))
    assert resp.status_code == 403
    assert "Premium feature" in resp.json()["detail"]


def test_free_cannot_request_consulting(client, store):
    _, token = make_user(client, "free-cons@example.com")
    resp = client.post("/api/v1/consulting",
                       json={"topic": "Help", "message": "Please help me "
                             "understand this tender."},
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert "Premium feature" in resp.json()["detail"]


def test_free_cannot_create_jv_post(client, store):
    _, token = make_user(client, "free-jv@example.com")
    resp = client.post("/api/v1/jv/posts",
                       json={"title": "Need a partner",
                             "need_description": "Looking for a JV "
                             "partner for a road project."},
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == (
        "This is a Pro feature. Your current plan is Free. "
        "Upgrade from the Plans tab to unlock it.")


def test_free_cannot_set_stage(client, store):
    _, token = make_user(client, "free-stage@example.com")
    client.post("/api/v1/favourites/1001/toggle",
                headers=auth_headers(token))
    resp = client.patch("/api/v1/favourites/1001/stage",
                        json={"stage": "Preparing"},
                        headers=auth_headers(token))
    assert resp.status_code == 403
    assert "Pro feature" in resp.json()["detail"]


def test_premium_can_use_premium_features_but_not_pro(client, store):
    _, token = make_premium_user(client, store, "prem@example.com")
    save_profile(client, token)
    assert client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token)).status_code == 200
    assert client.post("/api/v1/tenders/1001/summarize",
                       json={"lang": "en"},
                       headers=auth_headers(token)).status_code == 200
    assert client.put("/api/v1/alerts", json={"keywords": "road"},
                      headers=auth_headers(token)).status_code == 200
    assert client.post("/api/v1/consulting",
                       json={"topic": "Help",
                             "message": "Please help me understand this."},
                       headers=auth_headers(token)).status_code == 200
    # Pro-only features stay locked for Premium.
    resp = client.post("/api/v1/jv/posts",
                       json={"title": "Need a partner",
                             "need_description": "Looking for a JV "
                             "partner for a road project."},
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == (
        "This is a Pro feature. Your current plan is Premium. "
        "Upgrade from the Plans tab to unlock it.")


def test_pro_can_use_everything(client, store):
    _, token = make_pro_user(client, store, "pro@example.com")
    save_profile(client, token)
    assert client.post("/api/v1/tenders/1001/evaluate",
                       headers=auth_headers(token)).status_code == 200
    resp = client.post("/api/v1/jv/posts",
                       json={"title": "Need a partner",
                             "need_description": "Looking for a JV "
                             "partner for a road project."},
                       headers=auth_headers(token))
    assert resp.status_code == 200, resp.text


def test_unauthenticated_premium_endpoints_401(client):
    assert client.post("/api/v1/tenders/1001/evaluate").status_code == 401
    assert client.post("/api/v1/tenders/1001/summarize",
                       json={"lang": "en"}).status_code == 401
    assert client.post("/api/v1/jv/posts",
                       json={"title": "Need a partner",
                             "need_description": "Looking for a JV "
                             "partner."}).status_code == 401


def test_free_favourite_cap(client, store):
    _, token = make_user(client, "cap@example.com")
    for tender_id in (1001, 1002, 1003):
        resp = client.post(f"/api/v1/favourites/{tender_id}/toggle",
                           headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["favourite"] is True
    resp = client.post("/api/v1/favourites/1004/toggle",
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == (
        "The Free plan keeps 3 favourites. Upgrade to Premium for "
        "unlimited favourites.")
    # Removing one frees a slot.
    resp = client.post("/api/v1/favourites/1001/toggle",
                       headers=auth_headers(token))
    assert resp.json()["favourite"] is False
    resp = client.post("/api/v1/favourites/1004/toggle",
                       headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["favourite"] is True


def test_premium_no_favourite_cap(client, store):
    _, token = make_premium_user(client, store, "nocap@example.com")
    for tender_id in (1001, 1002, 1003, 1004, 1005):
        resp = client.post(f"/api/v1/favourites/{tender_id}/toggle",
                           headers=auth_headers(token))
        assert resp.status_code == 200, resp.text
