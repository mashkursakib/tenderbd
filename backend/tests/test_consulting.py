"""Consulting request tests + admin reply."""

from backend.tests.helpers import (auth_headers, make_admin, make_premium_user,
                      make_user)


def test_create_consulting_premium(client, store):
    _, token = make_premium_user(client, store, "cons@example.com")
    resp = client.post("/api/v1/consulting",
                       json={"topic": "Eligibility question",
                             "message": "Am I eligible for this tender?",
                             "tender_id": 1001},
                       headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "Open"
    assert body["tender_title"] == "Construction of school building"
    assert body["reply"] is None
    mine = client.get("/api/v1/consulting/mine",
                      headers=auth_headers(token)).json()
    assert len(mine) == 1
    assert mine[0]["id"] == body["id"]


def test_create_consulting_validation(client, store):
    _, token = make_premium_user(client, store, "consval@example.com")
    resp = client.post("/api/v1/consulting",
                       json={"topic": "Hi",
                             "message": "This message is long enough."},
                       headers=auth_headers(token))
    assert resp.status_code == 422  # topic too short
    resp = client.post("/api/v1/consulting",
                       json={"topic": "Valid topic",
                             "message": "Too short"},
                       headers=auth_headers(token))
    assert resp.status_code == 422  # message too short
    resp = client.post("/api/v1/consulting",
                       json={"topic": "Valid topic",
                             "message": "This message is long enough.",
                             "tender_id": 9999999},
                       headers=auth_headers(token))
    assert resp.status_code == 404


def test_create_consulting_free_forbidden(client, store):
    _, token = make_user(client, "consfree@example.com")
    resp = client.post("/api/v1/consulting",
                       json={"topic": "Help",
                             "message": "Please help me with this."},
                       headers=auth_headers(token))
    assert resp.status_code == 403


def test_admin_reply(client, store):
    _, token = make_premium_user(client, store, "consreply@example.com")
    request = client.post("/api/v1/consulting",
                          json={"topic": "Eligibility question",
                                "message": "Am I eligible for this?"},
                          headers=auth_headers(token)).json()
    _, admin_token = make_admin(client, store)
    resp = client.post(f"/api/v1/admin/consulting/{request['id']}/reply",
                       json={"reply": "Yes, your turnover covers it."},
                       headers=auth_headers(admin_token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "Answered"
    assert resp.json()["reply"] == "Yes, your turnover covers it."
    assert resp.json()["replied_at"] is not None
    mine = client.get("/api/v1/consulting/mine",
                      headers=auth_headers(token)).json()
    assert mine[0]["status"] == "Answered"
    assert mine[0]["reply"] == "Yes, your turnover covers it."


def test_admin_reply_requires_admin(client, store):
    _, token = make_premium_user(client, store, "consnoadmin@example.com")
    request = client.post("/api/v1/consulting",
                          json={"topic": "Eligibility question",
                                "message": "Am I eligible for this?"},
                          headers=auth_headers(token)).json()
    resp = client.post(f"/api/v1/admin/consulting/{request['id']}/reply",
                       json={"reply": "Self-reply."},
                       headers=auth_headers(token))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access only."


def test_admin_reply_missing_request(client, store):
    _, admin_token = make_admin(client, store)
    resp = client.post("/api/v1/admin/consulting/999999/reply",
                       json={"reply": "Nope."},
                       headers=auth_headers(admin_token))
    assert resp.status_code == 404
