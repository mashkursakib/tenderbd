"""Favourites + bid pipeline tests."""

from backend.tests.helpers import (auth_headers, make_premium_user, make_pro_user,
                      make_user)


def test_toggle_and_list(client, store):
    _, token = make_user(client, "fav@example.com")
    resp = client.post("/api/v1/favourites/1001/toggle",
                       headers=auth_headers(token))
    assert resp.json() == {"favourite": True}
    resp = client.post("/api/v1/favourites/1002/toggle",
                       headers=auth_headers(token))
    assert resp.json() == {"favourite": True}
    body = client.get("/api/v1/favourites",
                      headers=auth_headers(token)).json()
    assert body["favourite_ids"] == [1002, 1001] or set(
        body["favourite_ids"]) == {1001, 1002}
    assert len(body["favourites"]) == 2
    first = body["favourites"][0]
    assert first["stage"] == "Shortlisted"
    assert first["tender"]["tender_id"] == first["tender_id"]
    assert first["tender"]["work_type"] in ("Works", "Goods")
    # Toggle off.
    resp = client.post("/api/v1/favourites/1001/toggle",
                       headers=auth_headers(token))
    assert resp.json() == {"favourite": False}
    body = client.get("/api/v1/favourites",
                      headers=auth_headers(token)).json()
    assert body["favourite_ids"] == [1002]


def test_toggle_missing_tender_404(client, store):
    _, token = make_user(client, "fav404@example.com")
    resp = client.post("/api/v1/favourites/9999999/toggle",
                       headers=auth_headers(token))
    assert resp.status_code == 404


def test_toggle_requires_auth(client):
    assert client.post("/api/v1/favourites/1001/toggle").status_code == 401
    assert client.get("/api/v1/favourites").status_code == 401


def test_stage_patch_pro(client, store):
    _, token = make_pro_user(client, store, "stagepro@example.com")
    client.post("/api/v1/favourites/1001/toggle",
                headers=auth_headers(token))
    resp = client.patch("/api/v1/favourites/1001/stage",
                        json={"stage": "Preparing"},
                        headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == {"tender_id": 1001, "stage": "Preparing"}
    body = client.get("/api/v1/favourites",
                      headers=auth_headers(token)).json()
    assert body["favourites"][0]["stage"] == "Preparing"


def test_stage_patch_invalid_stage(client, store):
    _, token = make_pro_user(client, store, "stagebad@example.com")
    client.post("/api/v1/favourites/1001/toggle",
                headers=auth_headers(token))
    resp = client.patch("/api/v1/favourites/1001/stage",
                        json={"stage": "Dreaming"},
                        headers=auth_headers(token))
    assert resp.status_code == 400


def test_stage_patch_missing_favourite(client, store):
    _, token = make_pro_user(client, store, "stagemiss@example.com")
    resp = client.patch("/api/v1/favourites/1001/stage",
                        json={"stage": "Preparing"},
                        headers=auth_headers(token))
    assert resp.status_code == 404


def test_stage_patch_premium_forbidden(client, store):
    _, token = make_premium_user(client, store, "stageprem@example.com")
    client.post("/api/v1/favourites/1001/toggle",
                headers=auth_headers(token))
    resp = client.patch("/api/v1/favourites/1001/stage",
                        json={"stage": "Preparing"},
                        headers=auth_headers(token))
    assert resp.status_code == 403
    assert "Pro feature" in resp.json()["detail"]
